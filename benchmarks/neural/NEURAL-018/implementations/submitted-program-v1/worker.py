"""Container-side opaque programme capture; no numerical private targets."""
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

CAP = 34 * 1024**2


def main():
    request = Path('/request.json').read_bytes()
    value = json.loads(request)
    output = Path('/output')
    if set(output.iterdir()):
        raise ValueError('Fresh empty programme output')
    code = subprocess.run([sys.executable, '-I', '-B', '/program/program.py', '--input', '/input', '--out', '/output'],
                          stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                          close_fds=True).returncode
    if code != 0 or {item.name for item in output.iterdir()} != {'predictions.npz'}:
        raise ValueError('Successful programme with exactly predictions.npz required')
    fd = os.open(output / 'predictions.npz', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or not 0 < info.st_size <= CAP:
            raise ValueError('Bounded ordinary prediction archive')
        total, digest = 0, hashlib.sha256()
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            while chunk := stream.read(min(1048576, CAP + 1 - total)):
                total += len(chunk)
                if total > CAP:
                    raise ValueError('Prediction grew past cap')
                digest.update(chunk)
        after = os.fstat(fd)
        if total != info.st_size or (info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns) != (
                after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError('Prediction changed while capturing')
    finally:
        os.close(fd)
    result = b'{"schema":"neural018_program_exit_v1","candidate_exit_code":0}\n'
    (output / 'RESULT.json').write_bytes(result)
    manifest = {'schema': 'osl_transport_output_manifest_v1', 'phase_id': value['phase_id'],
                'request_sha256': hashlib.sha256(request).hexdigest(), 'files': {
                    'predictions.npz': {'bytes': total, 'sha256': digest.hexdigest()},
                    'RESULT.json': {'bytes': len(result), 'sha256': hashlib.sha256(result).hexdigest()}}}
    (output / 'OUTPUTS.json').write_text(json.dumps(manifest, sort_keys=True, separators=(',', ':')) + '\n')


if __name__ == '__main__':
    main()
