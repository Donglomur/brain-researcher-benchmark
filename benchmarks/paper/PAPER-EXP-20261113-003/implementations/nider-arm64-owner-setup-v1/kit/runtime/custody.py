"""Owner-only bounded artifact admission; no execution at import."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat


class Invalid(ValueError):
    pass


def need(condition, code):
    if not condition:
        raise Invalid(code)


def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'duplicate_json_key')
            result[key] = value
        return result
    def constant(_):
        raise Invalid('nonfinite_json')
    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise Invalid('invalid_json') from error


def plain(path):
    p = Path(path)
    need(p.is_absolute() and '..' not in p.parts, 'absolute_path_required')
    need(not any(x.is_symlink() for x in (p, *p.parents)), 'symlink_path')
    return p


def pin(raw, path):
    return {'path': str(path), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def read_pin(entry, maximum=1048576):
    need(type(entry) is dict and set(entry) == {'path', 'bytes', 'sha256'}, 'pin_keys')
    need(type(entry['bytes']) is int and 0 <= entry['bytes'] <= maximum, 'pin_extent')
    need(type(entry['sha256']) is str and re.fullmatch('[0-9a-f]{64}', entry['sha256']), 'pin_digest')
    path = plain(entry['path'])
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == entry['bytes'], 'regular_unique_file')
        raw = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
    current = path.lstat()
    for field in ('st_dev', 'st_ino', 'st_size', 'st_mode', 'st_nlink', 'st_mtime_ns', 'st_ctime_ns'):
        need(getattr(before, field) == getattr(after, field) == getattr(current, field), 'input_changed')
    need(pin(raw, path) == entry, 'input_identity')
    return raw


def write_new(path, raw):
    path = plain(path)
    with path.open('xb') as stream:
        stream.write(raw)
    path.chmod(0o600)
    return pin(raw, path)


def encoded(value):
    return (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()
