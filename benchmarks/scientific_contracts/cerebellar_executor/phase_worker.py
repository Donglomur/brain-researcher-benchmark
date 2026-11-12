"""Trusted NEURAL-030 phase worker; definition alone grants no run authority.

Only the separately owned container provider may invoke main. This module does
not certify model consumption, scientific correctness, or hostile-code safety.
The parent binds the complete procedure, grid, worker, mounts, and image before
execution and independently admits the provider's real closure and exports.
Absolute monotonic deadlines require a qualified shared clock domain between
the Provider and this container. Source tests do not establish that condition.
Process-group operations below have authority only inside the owned container;
this module must never be used to signal candidate groups on the host.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import subprocess
import time


RESOURCE_KEYS = {
    'setup_seconds', 'producer_seconds', 'capture_seconds', 'cleanup_seconds',
    'memory_bytes', 'cpu_nanos', 'pids', 'scratch_bytes', 'max_files',
    'max_directories', 'max_file_bytes', 'max_output_bytes', 'manifest_bytes',
    'max_cli_calls', 'max_cli_bytes', 'inventory_bytes', 'source_read_bytes',
    'host_write_bytes',
}
REQUEST_KEYS = {
    'schema', 'phase_id', 'action', 'role', 'image', 'command', 'workdir',
    'source', 'exposure', 'clock', 'resources', 'output',
}
JOB_KEYS = {
    'schema', 'phase', 'session_id', 'arm', 'procedure_pin', 'recipe_index',
    'stdout_bytes', 'stderr_bytes',
}
ENVIRONMENT = {
    'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': '/work', 'TMPDIR': '/work',
    'PYTHONDONTWRITEBYTECODE': '1', 'OPENBLAS_NUM_THREADS': '1',
    'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1', 'NUMEXPR_NUM_THREADS': '1',
}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       allow_nan=False) + '\n').encode('utf-8')


def decoded(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    def bad_constant(value):
        raise ValueError('Nonfinite JSON constant: ' + value)
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=bad_constant)


def descriptor(value):
    need(type(value) is dict and set(value) == {'bytes', 'sha256'},
         'Exact byte/hash pin')
    need(type(value['bytes']) is int and value['bytes'] > 0,
         'Positive nonboolean pin extent')
    need(type(value['sha256']) is str and
         re.fullmatch('[0-9a-f]{64}', value['sha256']), 'Exact SHA256')


def validate_request(request):
    need(type(request) is dict and set(request) == REQUEST_KEYS,
         'Exact transport request')
    need(request['schema'] == 'osl_owned_phase_request_v1', 'Transport schema')
    need(request['action'] == 'held_attempt' and request['role'] == 'A',
         'Fixed candidate transport action/role')
    need(type(request['phase_id']) is str and
         re.fullmatch('[A-Za-z0-9_-]{1,96}', request['phase_id']), 'Phase ID')
    need(type(request['image']) is str and
         re.fullmatch('sha256:[0-9a-f]{64}', request['image']), 'Immutable image')
    command = request['command']
    need(type(command) is list and 1 <= len(command) <= 64 and
         all(type(x) is str and 0 < len(x.encode()) <= 4096 and '\0' not in x
             for x in command) and command[0].startswith('/'), 'Bounded transport argv')
    need(request['workdir'] == '/work', 'Fixed worker directory')
    descriptor(request['source'])
    descriptor(request['exposure'])
    clock = request['clock']
    need(type(clock) is dict and set(clock) == {'origin', 'phase_deadline'},
         'Original clock fields')
    need(all(type(x) in (int, float) and math.isfinite(x)
             for x in clock.values()) and
         0 <= clock['origin'] < clock['phase_deadline'], 'Finite original clock')
    limits = request['resources']
    need(type(limits) is dict and set(limits) == RESOURCE_KEYS,
         'Explicit complete resource bounds')
    need(all(type(x) is int and x > 0 for x in limits.values()),
         'Positive nonboolean resource bounds')
    need(limits['memory_bytes'] >= 134217728 and limits['scratch_bytes'] % 4096 == 0
         and limits['max_output_bytes'] % 4096 == 0, 'Transport allocation bounds')
    need(limits['manifest_bytes'] <= limits['max_file_bytes'] <= limits['max_output_bytes']
         and limits['inventory_bytes'] >= 4096, 'Nested output bounds')
    need(request['output'] == {'kind': 'generic', 'manifest': 'OUTPUTS.json'},
         'Exact generic output contract')
    return request


def validate_job(job):
    need(type(job) is dict and set(job) == JOB_KEYS and
         job['schema'] == 'neural030_frozen_phase_job_v1', 'Exact frozen phase job')
    need(job['phase'] in ('select', 'fit', 'infer'), 'Fixed candidate phase')
    need(type(job['session_id']) is str and
         re.fullmatch('[0-9a-f]{32}', job['session_id']),
         'Exact opaque session identifier')
    need(job['arm'] in ('context_handle', 'grc', 'cf', 'joint'), 'Fixed arm')
    descriptor(job['procedure_pin'])
    index = job['recipe_index']
    need(index is None if job['phase'] == 'select' else
         type(index) is int and index >= 0, 'Exact phase recipe index')
    need(all(type(job[key]) is int and job[key] > 0
             for key in ('stdout_bytes', 'stderr_bytes')), 'Explicit stream bounds')
    return job


def candidate_argv(job):
    validate_job(job)
    argv = ['/usr/local/bin/python', '-I', '-B', '/candidate/main.py',
            '--view', '/view/VIEW.json', '--output', '/output/artifacts']
    if job['phase'] in ('fit', 'infer'):
        argv += ['--recipe', '/recipe.json']
    if job['phase'] == 'infer':
        argv += ['--model', '/model']
    return argv


def fixed_environment():
    return dict(ENVIRONMENT)


def deadlines(request, now):
    validate_request(request)
    clock, limits = request['clock'], request['resources']
    need(type(now) in (int, float) and math.isfinite(now) and now >= clock['origin'],
         'Current monotonic clock after original origin')
    end = min(clock['phase_deadline'] - limits['capture_seconds'] - limits['cleanup_seconds'],
              now + limits['producer_seconds'])
    need(now < end, 'Original producer interval remains')
    # Child, trusted output finalization, and local reaping share the same
    # absolute producer cutoff. The separate Provider owns reserved cleanup.
    return {'child_end': end, 'finish_end': end, 'cleanup_end': end}


def tick(now, end):
    if end is not None:
        need(now() < end, 'Original producer cutoff cannot renew')


def run_child(argv, timing, stdout_cap, stderr_cap, *, popen=None,
              selector_factory=None, read=None, killpg=None, now=None):
    """One real future subprocess; injections are for inert engineering tests."""
    popen = subprocess.Popen if popen is None else popen
    selector_factory = selectors.DefaultSelector if selector_factory is None else selector_factory
    read = os.read if read is None else read
    killpg = os.killpg if killpg is None else killpg
    now = time.monotonic if now is None else now
    tick(now, timing['child_end'])
    process = None
    selector = None
    streams = {'stdout': bytearray(), 'stderr': bytearray()}
    caps = {'stdout': stdout_cap, 'stderr': stderr_cap}
    error = None
    cleanup_errors = []
    try:
        process = popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE, start_new_session=True,
                        close_fds=True, cwd='/work', env=fixed_environment())
        selector = selector_factory()
        for name in streams:
            selector.register(getattr(process, name), selectors.EVENT_READ, name)
        while selector.get_map():
            tick(now, timing['child_end'])
            for event, _ in selector.select(min(.05, max(0, timing['child_end'] - now()))):
                tick(now, timing['child_end'])
                name = event.data
                raw = read(event.fileobj.fileno(), min(65536, caps[name] - len(streams[name]) + 1))
                if not raw:
                    selector.unregister(event.fileobj)
                    event.fileobj.close()
                    continue
                room = caps[name] - len(streams[name])
                streams[name].extend(raw[:room])
                need(len(raw) <= room, 'Stream byte ceiling; no successful truncation')
        tick(now, timing['child_end'])
        need(process.wait(timeout=max(0, timing['child_end'] - now())) == 0,
             'Natural successful candidate exit')
        tick(now, timing['child_end'])
        try:
            killpg(process.pid, 0)
        except ProcessLookupError:
            pass
        else:
            raise ValueError('Candidate process group remains after leader exit')
    except BaseException as exc:
        error = exc
    finally:
        if selector is not None:
            try:
                selector.close()
            except BaseException as exc:
                cleanup_errors.append(type(exc).__name__)
        if process is not None:
            if error is not None or cleanup_errors:
                try:
                    killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                except BaseException as exc:
                    cleanup_errors.append(type(exc).__name__)
                try:
                    process.wait(timeout=max(0, timing['cleanup_end'] - now()))
                except BaseException as exc:
                    cleanup_errors.append(type(exc).__name__)
            for name in streams:
                stream = getattr(process, name)
                if stream is not None and not stream.closed:
                    try:
                        stream.close()
                    except BaseException as exc:
                        cleanup_errors.append(type(exc).__name__)
    if error is None and cleanup_errors:
        error = ValueError('Incomplete candidate stream cleanup')
    if error is not None:
        error.worker_streams = {key: bytes(value) for key, value in streams.items()}
        error.worker_cleanup_errors = cleanup_errors
        raise error
    return {key: bytes(value) for key, value in streams.items()}


def file_body(path, cap):
    """Small fixed metadata only; no following links or special files."""
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= cap,
         'Bounded ordinary metadata file')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as handle:
        opened = os.fstat(handle.fileno())
        need((before.st_dev, before.st_ino) == (opened.st_dev, opened.st_ino), 'Stable metadata identity')
        body = handle.read(cap + 1)
        after = os.fstat(handle.fileno())
    need(len(body) == before.st_size <= cap and
         (before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
         (after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'Stable metadata extent')
    return body


def inventory(output, job, limits, *, expect_logs=False, expect_result=False,
              now=time.monotonic, end=None):
    """Complete bounded tree admission; no model deserialization or data parsing."""
    need(stat.S_ISDIR(output.lstat().st_mode), 'Ordinary output root')
    files, directories = {}, set()
    pending = [(output, '')]
    total = 0
    while pending:
        directory, prefix = pending.pop()
        tick(now, end)
        with os.scandir(directory) as entries:
            for entry in entries:
                tick(now, end)
                name = prefix + entry.name
                need(re.fullmatch('[A-Za-z0-9_.-]+', entry.name) and
                     entry.name not in ('.', '..'), 'Ordinary output path component')
                info = entry.stat(follow_symlinks=False)
                if stat.S_ISDIR(info.st_mode):
                    directories.add(name)
                    need(len(directories) + 1 <= limits['max_directories'], 'Directory count cap')
                    pending.append((Path(entry.path), name + '/'))
                    continue
                need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
                     'No linked or special output members')
                need(len(files) + 1 <= limits['max_files'] and
                     info.st_size <= limits['max_file_bytes'], 'File count/extent cap')
                total += info.st_size
                need(total <= limits['max_output_bytes'], 'Complete output byte cap')
                fd = os.open(entry.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                digest, size = hashlib.sha256(), 0
                with os.fdopen(fd, 'rb') as handle:
                    opened = os.fstat(handle.fileno())
                    need((info.st_dev, info.st_ino, info.st_size) ==
                         (opened.st_dev, opened.st_ino, opened.st_size), 'Stable ordinary output inode')
                    while True:
                        tick(now, end)
                        raw = handle.read(min(65536, info.st_size - size + 1))
                        if not raw:
                            break
                        size += len(raw)
                        need(size <= info.st_size, 'No output growth during capture')
                        digest.update(raw)
                    after = os.fstat(handle.fileno())
                need(size == info.st_size and
                     (info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_nlink) ==
                     (after.st_size, after.st_mtime_ns, after.st_ctime_ns, after.st_nlink),
                     'Stable complete output body')
                files[name] = {'bytes': size, 'sha256': digest.hexdigest()}
                need(len(encoded(files)) <= limits['inventory_bytes'], 'Inventory metadata cap')
    expected = set()
    if expect_logs:
        expected.update(('STDOUT.txt', 'STDERR.txt'))
    if expect_result:
        expected.add('RESULT.json')
    if job['phase'] in ('select', 'infer'):
        expected.add('artifacts/' + ('SELECTION.json' if job['phase'] == 'select' else 'PREDICTIONS.json'))
        need(set(files) == expected and directories == {'artifacts'}, 'Exact phase export set')
    else:
        model = set(files) - expected
        need(expected <= set(files) and model and
             all(name.startswith('artifacts/model/') for name in model) and
             sum(files[name]['bytes'] for name in model) > 0, 'Nonempty model-only fit export')
        wanted = {'artifacts', 'artifacts/model'}
        for name in model:
            parts = name.split('/')
            wanted.update('/'.join(parts[:i]) for i in range(1, len(parts)))
        need(directories == wanted, 'No unrelated or empty model directories')
    return dict(sorted(files.items()))


def publish(path, raw):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException as exc:
        # This call exclusively created the name. Never leave a complete-looking
        # trusted envelope after a flush failure, and never overwrite a producer
        # export that predated this call.
        try:
            path.unlink()
        except OSError as cleanup_error:
            exc.worker_publication_cleanup_errors = [type(cleanup_error).__name__]
        raise
    return pin(raw)


def execute(request_raw, job, output, *, runner=None, now=time.monotonic):
    """Trusted orchestration; test runner seam never enters the production CLI."""
    request = validate_request(decoded(request_raw))
    validate_job(job)
    limits = request['resources']
    need(max(job['stdout_bytes'], job['stderr_bytes']) <= limits['max_file_bytes'] and
         job['stdout_bytes'] + job['stderr_bytes'] < limits['max_output_bytes'],
         'Stream caps fit original output allowance')
    timing = deadlines(request, now())
    need(stat.S_ISDIR(output.lstat().st_mode) and not any(output.iterdir()),
         'Fresh ordinary output root')
    (output / 'artifacts').mkdir(mode=0o700)
    runner = run_child if runner is None else runner
    owned_success = []
    try:
        streams = runner(candidate_argv(job), timing, job['stdout_bytes'], job['stderr_bytes'], now=now)
        need(type(streams) is dict and set(streams) == {'stdout', 'stderr'} and
             all(type(streams[name]) is bytes and len(streams[name]) <= job[name + '_bytes']
                 for name in streams), 'Complete bounded child streams')
        tick(now, timing['finish_end'])
        inventory(output, job, limits, now=now, end=timing['finish_end'])
        for name, raw in streams.items():
            publish(output / (name.upper() + '.txt'), raw)
        result = {'schema': 'neural030_trusted_phase_completion_v1',
                  'phase_id': request['phase_id'], 'request_sha256': pin(request_raw)['sha256'],
                  'phase': job['phase'], 'session_id': job['session_id'], 'arm': job['arm'],
                  'procedure_pin': job['procedure_pin'], 'producer_completed': True,
                  'scientific_qualification': False}
        raw = encoded(result)
        need(len(raw) <= limits['max_file_bytes'], 'Trusted result extent cap')
        tick(now, timing['finish_end'])
        publish(output / 'RESULT.json', raw)
        owned_success.append(output / 'RESULT.json')
        files = inventory(output, job, limits, expect_logs=True, expect_result=True,
                          now=now, end=timing['finish_end'])
        manifest = encoded({'schema': 'osl_transport_output_manifest_v1',
                            'phase_id': request['phase_id'],
                            'request_sha256': pin(request_raw)['sha256'], 'files': files})
        need(len(manifest) <= limits['manifest_bytes'] and len(files) + 1 <= limits['max_files']
             and sum(row['bytes'] for row in files.values()) + len(manifest) <= limits['max_output_bytes'],
             'Whole output including manifest fits original caps')
        tick(now, timing['finish_end'])
        publish(output / 'OUTPUTS.json', manifest)
        owned_success.append(output / 'OUTPUTS.json')
        tick(now, timing['finish_end'])
        return result
    except BaseException as exc:
        cleanup_errors = []
        for path in reversed(owned_success):
            try:
                path.unlink()
            except OSError as cleanup_error:
                cleanup_errors.append(type(cleanup_error).__name__)
        # Capped partial logs are diagnostic exports only. Without a successful
        # manifest the Provider cannot admit them as a completed phase.
        for name, raw in getattr(exc, 'worker_streams', {}).items():
            if name in ('stdout', 'stderr') and type(raw) is bytes:
                path = output / (name.upper() + '.txt')
                try:
                    publish(path, raw[:job[name + '_bytes']])
                except OSError:
                    pass
        if cleanup_errors:
            exc.worker_publication_cleanup_errors = cleanup_errors
        raise


def main():
    request_raw = file_body(Path('/request.json'), 1048576)
    job = decoded(file_body(Path('/job.json'), 65536))
    execute(request_raw, job, Path('/output'))


if __name__ == '__main__':
    main()
