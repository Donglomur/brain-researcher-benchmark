"""Restricted single-process candidate entry, used only inside the admitted image.

The existing provider must enforce pids=1, init=false, no network, read-only
binds and 4 GiB. This is an additional execution restriction, not a replacement
for the generic primary profile. The host never imports participant code.
"""
import hashlib
import json
import os
from pathlib import Path
import resource
import runpy
import stat
import sys


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


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
    spec = json.loads(Path('/execution.json').read_text())
    request_raw = Path('/request.json').read_bytes()
    request = json.loads(request_raw)
    cpu = spec['resource_profile']['cpu_seconds']
    if type(cpu) is not int or cpu not in (75000, 7200):
        raise ValueError('Exact adopted cumulative CPU limit')
    # With the separately enforced pids=1 cgroup, no fork or additional thread
    # can escape this hard process CPU limit. Participant code cannot raise it.
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
    if resource.getrlimit(resource.RLIMIT_CPU) != (cpu, cpu):
        raise ValueError('Hard process CPU limit was not installed')
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'OMP_THREAD_LIMIT',
                'MKL_NUM_THREADS', 'NUMBA_NUM_THREADS', 'NUMEXPR_NUM_THREADS',
                'VECLIB_MAXIMUM_THREADS'):
        os.environ[key] = '1'
    # Host argv includes -S: image .pth/sitecustomize hooks cannot execute
    # before the kernel CPU ceiling. Enable admitted image packages only now.
    import site
    site.main()
    sys.argv = ['/program/program.py', '--input', '/materials', '--out', '/output',
                '--outcome', spec['outcome'], '--declaration', '/declaration.json']
    try:
        runpy.run_path('/program/program.py', run_name='__main__')
    except SystemExit as exc:
        if exc.code not in (None, 0):
            raise
    root = Path('/output')
    expected = {key + '.h5' for key in spec['submission_keys']}
    if {p.name for p in root.iterdir()} != expected:
        raise ValueError('Complete original prediction files only; no extra outputs')
    files = {name: pin_file(root / name, spec['max_file_bytes']) for name in sorted(expected)}
    result = encode({'schema': 'smc_restricted_program_result_v1',
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
