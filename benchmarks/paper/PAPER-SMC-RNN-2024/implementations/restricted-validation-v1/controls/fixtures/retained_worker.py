"""Fixed trusted producer entry and release helper inside the selected image.

Parent-owned cgroup accounting covers the entire producer tree, including this
entry and its fixed release helper. RLIMIT_CPU is per-process defense only.
No candidate/site code runs before observed parent custody and explicit release.
"""
import hashlib
import fcntl
import json
import math
import os
from pathlib import Path
import resource
import runpy
import stat
import sys
import time

REQUEST = Path('/request.json')
JOB = Path('/execution.json')
READY = Path('/work/.smc-ready.json')
RELEASE = Path('/work/.smc-release.json')
META_CAP = 1024**2


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def compact(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def metadata(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        st = os.fstat(stream.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or not 0 < st.st_size <= META_CAP:
            raise ValueError('Bounded ordinary immutable metadata')
        raw = stream.read(META_CAP + 1)
        after = os.fstat(stream.fileno())
    named = path.lstat()
    fields = ('st_dev', 'st_ino', 'st_mode', 'st_size', 'st_nlink', 'st_mtime_ns', 'st_ctime_ns')
    if len(raw) != st.st_size or any(getattr(st, k) != getattr(after, k) or getattr(st, k) != getattr(named, k) for k in fields):
        raise ValueError('Metadata changed during authentication')
    def unique(rows):
        value = {}
        for key, item in rows:
            if key in value:
                raise ValueError('Duplicate metadata key')
            value[key] = item
        return value
    value = json.loads(raw, object_pairs_hook=unique,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite metadata')))
    return raw, value


def before_deadline(request):
    clock = request['clock']
    if (type(clock) is not dict or set(clock) != {'origin', 'phase_deadline'}
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in clock.values())
            or not 0 <= clock['origin'] <= time.monotonic() < clock['phase_deadline']):
        raise TimeoutError('Original request interval expired; no fresh worker clock')


def authenticated_inputs():
    _, spec = metadata(JOB)
    request_raw, request = metadata(REQUEST)
    if request_raw != compact(request):
        raise ValueError('Exact compact request encoding required')
    if (request.get('schema') != 'smc_aggregate_phase_request_v1'
            or spec.get('schema') != 'smc_aggregate_execution_job_v1'
            or request['source'] != spec['source'] or request['phase_id'] != spec['condition']
            or spec['outcome'] not in ('reproduction', 'improvement')):
        raise ValueError('Current source, phase and complete job binding')
    cpu, wall = (75000, 86400) if spec['outcome'] == 'reproduction' else (7200, 10800)
    profile = {'cpu_seconds': cpu, 'wall_seconds': wall, 'memory_bytes': 8589934592, 'threads': 6}
    if (spec['resource_profile'] != profile or request['resources']['cpu_seconds'] != cpu
            or request['resources']['producer_seconds'] != wall
            or request['resources']['memory_bytes'] != 8589934592
            or request['resources']['cpu_nanos'] != 6000000000
            or type(request['resources']['pids']) is not int or request['resources']['pids'] < 1
            or spec['submission_keys'] != (['causal', 'noncausal'] if spec['outcome'] == 'reproduction' else ['offline'])):
        raise ValueError('Exact matched aggregate profile and original output set')
    before_deadline(request)
    return spec, request_raw, request


def marker(request_raw, request, kind):
    return {'schema': 'smc_aggregate_' + kind + '_v1',
            'request_sha256': hashlib.sha256(request_raw).hexdigest(),
            'phase_id': request['phase_id'], 'source': request['source'],
            'original_phase_deadline': request['clock']['phase_deadline']}


def publish_marker(path, value, request):
    before_deadline(request)
    lock_path = path.with_name(path.name + '.publish-lock')
    temporary = path.with_name(path.name + '.next')
    # This exclusive claim also prevents a second trusted helper overwriting
    # a previous release. Waiters share the lock, never a partial publication.
    lock = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    linked = False
    temporary_created = False
    try:
        fcntl.flock(lock, fcntl.LOCK_EX)
        before_deadline(request)
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
        temporary_created = True
        with os.fdopen(fd, 'wb') as stream:
            stream.write(compact(value))
            stream.flush()
            os.fchmod(stream.fileno(), 0o444)  # Exact public marker under umask077.
            os.fsync(stream.fileno())
        before_deadline(request)
        os.link(temporary, path, follow_symlinks=False)  # Atomic, no replacement.
        linked = True
        temporary.unlink()
        temporary_created = False
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        before_deadline(request)
    except BaseException:
        # Preserve the exclusive claim as failed evidence; never overwrite a
        # previously existing final marker. Any cleanup failure remains failure.
        if linked:
            path.unlink()
        if temporary_created and temporary.exists():
            temporary.unlink()
        raise
    finally:
        os.close(lock)


def marker_available(path, expected, request):
    before_deadline(request)
    try:
        lock = os.open(path.with_name(path.name + '.publish-lock'), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return False
    try:
        st = os.fstat(lock)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
            raise ValueError('Ordinary exclusive publication claim')
        try:
            fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        try:
            raw, actual = metadata(path)
        except FileNotFoundError:
            return False
        if actual != expected or raw != compact(expected):
            raise ValueError('Exact request-bound original-clock marker required')
        before_deadline(request)
        return True
    finally:
        os.close(lock)


def wait_marker(path, expected, request):
    while True:
        before_deadline(request)
        if marker_available(path, expected, request):
            return
        time.sleep(min(0.01, max(0, request['clock']['phase_deadline'] - time.monotonic())))


def release(spec, request_raw, request):
    """Only the fixed Provider exec after the parent's attachment ACK calls this."""
    if RELEASE.exists():
        raise ValueError('No stale or repeated producer release')
    wait_marker(READY, marker(request_raw, request, 'ready'), request)
    publish_marker(RELEASE, marker(request_raw, request, 'release'), request)
    print(compact({'schema': 'smc_producer_release_v1', 'phase_id': request['phase_id'],
                  'request_sha256': hashlib.sha256(request_raw).hexdigest(),
                  'source': request['source'], 'phase_deadline': request['clock']['phase_deadline']}).decode(), end='')


def pin_file(path, cap):
    st = path.lstat()
    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or not 0 < st.st_size <= cap:
        raise ValueError('One bounded ordinary output file required')
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024**2), b''):
            h.update(block)
    after = path.lstat()
    fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_nlink')
    if any(getattr(st, key) != getattr(after, key) for key in fields):
        raise ValueError('Output changed during opaque capture')
    return {'bytes': st.st_size, 'sha256': h.hexdigest()}


def main():
    if sys.argv[1:] not in ([], ['--release']):
        raise ValueError('Only fixed candidate entry or trusted release helper')
    spec, request_raw, request = authenticated_inputs()
    if sys.argv[1:] == ['--release']:
        return release(spec, request_raw, request)
    cpu = spec['resource_profile']['cpu_seconds']
    if type(cpu) is not int or cpu not in (75000, 7200):
        raise ValueError('Exact adopted cumulative CPU limit')
    # This limits only this process. The parent meters and closes the full
    # delegated tree, including threads, descendants and the release helper.
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
    if resource.getrlimit(resource.RLIMIT_CPU) != (cpu, cpu):
        raise ValueError('Hard process CPU limit was not installed')
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'OMP_THREAD_LIMIT',
                'MKL_NUM_THREADS', 'NUMBA_NUM_THREADS', 'NUMEXPR_NUM_THREADS',
                'VECLIB_MAXIMUM_THREADS'):
        os.environ[key] = '6'
    if READY.exists() or RELEASE.exists():
        raise ValueError('Fresh worker handshake only')
    publish_marker(READY, marker(request_raw, request, 'ready'), request)
    wait_marker(RELEASE, marker(request_raw, request, 'release'), request)
    # Host argv includes -S: image .pth/sitecustomize hooks cannot execute
    # before the kernel CPU ceiling. Enable admitted image packages only now.
    before_deadline(request)
    import site
    site.main()
    sys.argv = ['/program/program.py', '--input', '/materials', '--out', '/output',
                '--outcome', spec['outcome'], '--declaration', '/declaration.json']
    try:
        before_deadline(request)
        runpy.run_path('/program/program.py', run_name='__main__')
    except SystemExit as exc:
        if exc.code not in (None, 0):
            raise
    root = Path('/output')
    expected = {key + '.h5' for key in spec['submission_keys']}
    if {p.name for p in root.iterdir()} != expected:
        raise ValueError('Complete original prediction files only; no extra outputs')
    files = {name: pin_file(root / name, spec['max_file_bytes']) for name in sorted(expected)}
    before_deadline(request)
    result = encode({'schema': 'smc_aggregate_program_result_v1',
                     'outcome': spec['outcome'], 'condition': spec['condition'],
                     'program_sha256': spec['program_sha256'],
                     'declaration_sha256': spec['declaration_sha256'],
                     'submission_keys': spec['submission_keys']})
    with (root / 'RESULT.json').open('xb') as handle:
        handle.write(result)
    files['RESULT.json'] = {'bytes': len(result), 'sha256': hashlib.sha256(result).hexdigest()}
    envelope = {'schema': 'osl_transport_output_manifest_v1',
                'phase_id': request['phase_id'],
                'request_sha256': hashlib.sha256(request_raw).hexdigest(), 'files': files}
    with (root / 'OUTPUTS.json').open('xb') as handle:
        handle.write(encode(envelope))


if __name__ == '__main__':
    main()
