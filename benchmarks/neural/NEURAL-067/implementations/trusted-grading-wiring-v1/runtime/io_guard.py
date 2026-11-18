"""Small source/report guards for this generated-only diagnostic."""
import hashlib
import json
import os
from pathlib import Path
import stat


def need(ok, message):
    if not ok:
        raise ValueError(message)


def parse(body):
    def pairs(items):
        out = {}
        for key, value in items:
            need(key not in out, 'duplicate JSON key')
            out[key] = value
        return out
    def bad(_):
        raise ValueError('nonfinite JSON')
    return json.loads(body, object_pairs_hook=pairs, parse_constant=bad)


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def signature(s):
    return (s.st_dev, s.st_ino, s.st_size, s.st_nlink, s.st_mtime_ns, s.st_ctime_ns)


def capture(path, cap, expected=None):
    path = Path(path).absolute()
    need(not any(p.is_symlink() for p in (path, *path.parents)), 'no linked path')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        a = os.fstat(fd)
        need(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and 0 <= a.st_size <= cap, 'bounded regular source')
        with os.fdopen(fd, 'rb', closefd=False) as f:
            body = f.read(cap + 1)
        need(len(body) == a.st_size and signature(a) == signature(os.fstat(fd))
             == signature(path.lstat()), 'unchanged same-open bytes')
        if expected is not None:
            need(pin(body) == {k: expected[k] for k in ('bytes', 'sha256')}, 'source pin')
        return body
    finally:
        os.close(fd)


def publish(path, value, cap):
    """Exclusive publication; external natural exit0 remains mandatory.

    Failure cleanup can itself fail. A surviving marker then remains unadmitted.
    """
    path = Path(path)
    body = (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
    need(len(body) <= cap and not path.exists(), 'fresh bounded metadata')
    pending = path.with_name('.' + path.name + '.pending')
    linked = False
    with pending.open('xb') as f:
        f.write(body); f.flush(); os.fsync(f.fileno()); os.fchmod(f.fileno(), 0o444)
        own = os.fstat(f.fileno())
    try:
        os.link(pending, path); linked = True
        pending.unlink()
        fd = os.open(path.parent, os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)
    except BaseException:
        if linked:
            current = path.lstat()
            if (current.st_dev, current.st_ino) == (own.st_dev, own.st_ino):
                path.unlink()
        raise
    return pin(body)
