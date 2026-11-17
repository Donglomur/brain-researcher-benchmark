"""Strict finite JSON and bounded ordinary-file identity primitives."""
import hashlib
import json
import math
import os
import stat
from pathlib import Path


def need(value, message):
    if not value:
        raise ValueError(message)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, 'duplicate JSON key: ' + key)
        result[key] = value
    return result


def parse(raw):
    def invalid(value):
        raise ValueError('nonfinite JSON token: ' + value)
    return json.loads(raw, object_pairs_hook=_pairs, parse_constant=invalid)


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=False, allow_nan=False) + '\n').encode('utf8')


def pin(raw, path=None):
    result = {'bytes':len(raw), 'sha256':hashlib.sha256(raw).hexdigest()}
    if path is not None:
        result['path'] = str(path)
    return result


def relative(name):
    need(type(name) is str and name and '\\' not in name and '\0' not in name,
         'ordinary relative path spelling')
    p = Path(name)
    need(not p.is_absolute() and all(s not in ('', '.', '..') for s in name.split('/')),
         'no absolute or traversing relative paths')
    return p


def descriptor(value):
    need(type(value) is dict and set(value) == {'path','bytes','sha256'},
         'exact file descriptor')
    relative(value['path'])
    need(type(value['bytes']) is int and value['bytes'] >= 0, 'nonnegative byte count')
    h = value['sha256']
    need(type(h) is str and len(h) == 64 and all(c in '0123456789abcdef' for c in h),
         'SHA256 spelling')
    return dict(value)


def capture(root, declared, *, cap, meter=None):
    """Capture a pinned ordinary body once, refusing symlinks and unstable extents.

    Caller selects source versus authentic-data authority. This function grants
    neither. `meter` records the reservation before any file operation.
    """
    d = descriptor(declared)
    need(type(cap) is int and d['bytes'] <= cap, 'complete body fits selected cap')
    if meter is not None:
        meter.reserve_read(d['bytes'] + 1)
        meter.check_deadline('before_capture')
    root = Path(root).absolute()
    path = root / relative(d['path'])
    need(not any(p.is_symlink() for p in (path, *path.parents)), 'ordinary path ancestry')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    primary = None
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == d['bytes'],
             'regular single-link exact extent')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(d['bytes'] + 1)
        after = os.fstat(fd)
        named = path.lstat()
        fields = ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_nlink')
        need(all(getattr(before,k) == getattr(after,k) == getattr(named,k) for k in fields),
             'file capture identity changed')
        need(pin(raw) == {'bytes':d['bytes'],'sha256':d['sha256']}, 'file hash mismatch')
        if meter is not None:
            meter.complete_read(len(raw))
            meter.check_deadline('after_capture')
        return raw
    except BaseException as error:
        primary = error
        raise
    finally:
        try:
            os.close(fd)
        except BaseException as error:
            if primary is None:
                raise
            primary.add_note('File descriptor cleanup uncertainty: ' + type(error).__name__)


def finite_number(value):
    return type(value) in (int,float) and math.isfinite(value)
