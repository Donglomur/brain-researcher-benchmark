"""Container-only adapter for the original single-program CLI.

This file does not implement a host fallback. The operator mounts it readonly;
the concrete transport removes the entire producer before output capture.
"""
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def main():
    if (Path('/request.json').is_file() is not True or not Path('/input/manifest.json').is_file()
            or str(Path.cwd()) != '/work'):
        raise RuntimeError('Container-only fixed worker paths')
    raw = Path('/request.json').read_bytes()
    request = json.loads(raw)
    env = os.environ.copy()
    # Preserve original paired programme's two numerical threads; 1.75 CPU
    # and 3 GiB are independently enforced by the unchanged Docker transport.
    for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
                'VECLIB_MAXIMUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        env[key] = '2'
    subprocess.run([sys.executable, '-I', '-B', '/program/program.py', '--input', '/input', '--out', '/output'],
                   env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   check=True, close_fds=True)
    output = Path('/output')
    if {p.name for p in output.iterdir()} != {'predictions.npz'}:
        raise ValueError('Candidate must emit only predictions.npz')
    path = output / 'predictions.npz'
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or not 0 < info.st_size <= 1048576:
            raise ValueError('Bounded ordinary prediction file')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            body = stream.read(1048577)
        if len(body) != info.st_size:
            raise ValueError('Complete output required')
    finally:
        os.close(fd)
    result = encoded({'schema': 'neural008_program_exit_v1', 'candidate_exit_code': 0})
    with (output / 'RESULT.json').open('xb') as stream:
        stream.write(result)
    manifest = {'schema': 'osl_transport_output_manifest_v1', 'phase_id': request['phase_id'],
                'request_sha256': pin(raw)['sha256'], 'files': {'RESULT.json': pin(result), 'predictions.npz': pin(body)}}
    with (output / 'OUTPUTS.json').open('xb') as stream:
        stream.write(encoded(manifest))


if __name__ == '__main__':
    main()
