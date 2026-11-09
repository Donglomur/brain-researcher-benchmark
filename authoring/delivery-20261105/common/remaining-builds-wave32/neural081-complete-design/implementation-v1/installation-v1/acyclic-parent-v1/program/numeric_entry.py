"""Literal python -I -B entry: authenticate bootstrap before any custom import."""
import argparse
import hashlib
import os
import stat
import time
import types
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    for name in ('request', 'request-bytes', 'request-sha256', 'bootstrap', 'bootstrap-bytes',
                 'bootstrap-sha256', 'read-cap', 'write-cap', 'origin', 'deadline', 'entry-bytes'):
        parser.add_argument('--' + name, required=True)
    a = parser.parse_args()
    origin, deadline = float(a.origin), float(a.deadline)
    read_cap, write_cap = int(a.read_cap), int(a.write_cap)
    used = int(a.entry_bytes)  # Interpreter source demand, separate from later authentication.
    if not (0 <= origin < time.monotonic() < deadline and read_cap > 0 and write_cap > 0):
        raise ValueError('invalid original worker bounds')

    def capture(path, size, digest):
        nonlocal used
        size = int(size)
        if size < 1 or size > 16 * 2**20 or used + size + 1 > read_cap:
            raise ValueError('bootstrap capture reservation')
        used += size + 1
        p = Path(path)
        if not p.is_absolute() or str(p) != path or any(x.is_symlink() for x in (p, *p.parents)):
            raise ValueError('ordinary exact bootstrap path')
        fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            first = os.fstat(fd)
            if not stat.S_ISREG(first.st_mode) or first.st_nlink != 1 or first.st_size != size:
                raise ValueError('bootstrap extent')
            with os.fdopen(fd, 'rb', closefd=False) as stream:
                raw = stream.read(size + 1)
            last, named = os.fstat(fd), p.lstat()
            fields = ('st_dev', 'st_ino', 'st_size', 'st_mode', 'st_nlink', 'st_mtime_ns', 'st_ctime_ns')
            if len(raw) != size or hashlib.sha256(raw).hexdigest() != digest or any(
                    getattr(first, k) != getattr(last, k) or getattr(first, k) != getattr(named, k) for k in fields):
                raise ValueError('bootstrap complete source identity')
        finally:
            os.close(fd)
        if time.monotonic() >= deadline:
            raise ValueError('original deadline exceeded')
        return raw

    boot = capture(a.bootstrap, a.bootstrap_bytes, a.bootstrap_sha256)
    request = capture(a.request, a.request_bytes, a.request_sha256)
    module = types.ModuleType('worker_bootstrap')
    module.__file__ = a.bootstrap
    exec(compile(boot, a.bootstrap, 'exec'), module.__dict__)
    module.start(request, {'path': a.request, 'bytes': int(a.request_bytes), 'sha256': a.request_sha256},
                 {'path': a.bootstrap, 'bytes': int(a.bootstrap_bytes), 'sha256': a.bootstrap_sha256},
                 origin=origin, deadline=deadline, read_cap=read_cap, write_cap=write_cap,
                 initial_read_bytes=used, entry_path=str(Path(__file__)), entry_bytes=int(a.entry_bytes))


if __name__ == '__main__':
    main()
