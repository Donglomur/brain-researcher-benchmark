"""Trusted holder: retain output tmpfs, then stream one closed producer's file."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import time

CAP = 100000000


def capture(root=Path('/capture'), destination=Path('/export')):
    if sorted(p.name for p in root.iterdir()) != ['submission.json']:
        raise ValueError('Exactly one submission.json required; extra output refused')
    source = root / 'submission.json'
    fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if not (stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
                0 < before.st_size <= CAP):
            raise ValueError('Bounded regular single-link submission')
        out = os.open(destination / 'submission.json',
                      os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        digest = hashlib.sha256(); total = 0
        try:
            while True:
                block = os.read(fd, min(1048576, CAP + 1 - total))
                if not block:
                    break
                total += len(block)
                if total > CAP:
                    raise ValueError('Complete submission cap')
                digest.update(block)
                view = memoryview(block)
                while view:
                    count = os.write(out, view)
                    if count <= 0:
                        raise OSError('Incomplete capture write')
                    view = view[count:]
            after = os.fstat(fd); linked = source.lstat()
            attrs = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size',
                     'st_mtime_ns', 'st_ctime_ns')
            if total != before.st_size or any(getattr(before, k) != getattr(after, k)
                    or getattr(after, k) != getattr(linked, k) for k in attrs):
                raise ValueError('Stable full submission capture')
            os.fsync(out)
        finally:
            os.close(out)
        os.chmod(destination / 'submission.json', 0o444)
        directory = os.open(destination, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        return {'status': 'captured', 'bytes': total, 'sha256': digest.hexdigest()}
    finally:
        os.close(fd)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('hold', 'capture'))
    args = parser.parse_args()
    if args.operation == 'capture':
        print(json.dumps(capture(), sort_keys=True))
    else:
        print('HOLDER_READY', flush=True)
        while True:
            time.sleep(1)
