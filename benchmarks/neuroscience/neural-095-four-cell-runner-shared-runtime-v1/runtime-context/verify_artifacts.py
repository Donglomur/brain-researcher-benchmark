"""Verify a finite existing wheel directory; no acquisition or imports."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat


def need(ok, message):
    if not ok:
        raise ValueError(message)


def verify(root, lock):
    root = Path(root).absolute()
    need(root.is_dir() and all(not p.is_symlink() for p in (root, *root.parents)), 'ordinary existing wheel directory')
    need(lock['schema'] == 'shared-science-wheel-metadata-lock/v1', 'selected wheel lock schema')
    wheels = lock['wheels']; expected = {x['filename']: x for x in wheels}
    need(len(expected) == len(wheels) == lock['wheel_count'] and 0 < len(wheels) <= 64, 'finite unique artifact inventory')
    need(all(Path(n).name == n and n.endswith('.whl') and '\0' not in n for n in expected), 'literal wheel basenames')
    need({p.name for p in root.iterdir()} == set(expected), 'exact wheel allowlist; no extra files')
    total = 0
    for name, value in sorted(expected.items()):
        path = root / name
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            before = os.fstat(fd)
            need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == value['bytes']
                 and type(value['bytes']) is int and 0 < value['bytes'] <= 64 * 1024**2, 'exact ordinary bounded wheel size')
            digest = hashlib.sha256(); count = 0
            with os.fdopen(fd, 'rb', closefd=False) as stream:
                while True:
                    body = stream.read(min(1024**2, value['bytes'] - count + 1))
                    if not body:
                        break
                    count += len(body); need(count <= value['bytes'], 'no wheel growth')
                    digest.update(body)
            after = os.fstat(fd)
            fields = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
            need(count == value['bytes'] and all(getattr(before, f) == getattr(after, f) for f in fields)
                 and digest.hexdigest() == value['sha256'], 'stable complete wheel hash')
            total += count; need(total <= 128 * 1024**2, 'complete selected artifact byte ceiling')
        finally:
            os.close(fd)
    need(total == lock['future_wheel_download_bytes'], 'whole artifact byte identity')
    return {'status': 'exact_wheel_artifacts_verified', 'files': len(wheels), 'bytes': total,
            'packages_imported': False, 'execution_authority': False}


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--root', type=Path, required=True)
    p.add_argument('--lock', type=Path, required=True); a = p.parse_args()
    need(0 < a.lock.stat().st_size <= 262144 and not a.lock.is_symlink(), 'bounded selected metadata lock')
    print(json.dumps(verify(a.root, json.loads(a.lock.read_bytes())), indent=2))


if __name__ == '__main__':
    main()
