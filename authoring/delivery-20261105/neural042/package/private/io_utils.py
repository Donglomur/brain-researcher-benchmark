"""Small nonblocking JSON boundary for trusted descriptors and untrusted submissions."""
import hashlib
import json
import os
from pathlib import Path
import stat


def ordinary_bytes(path, limit):
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, 'O_NOFOLLOW', 0))
    try:
        meta = os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode) or meta.st_size > limit:
            raise ValueError('Expected bounded ordinary file')
        parts, remaining = [], limit + 1
        while remaining:
            chunk = os.read(fd, min(65536, remaining))
            if not chunk:
                break
            parts.append(chunk)
            remaining -= len(chunk)
        body = b''.join(parts)
        if len(body) > limit:
            raise ValueError('File exceeds byte limit')
        return body
    finally:
        os.close(fd)


def strict_json(body):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    def constant(value):
        raise ValueError('Nonfinite JSON number')
    return json.loads(body.decode('utf-8', errors='strict'), object_pairs_hook=pairs,
                      parse_constant=constant)


def read_json(path, limit=33554432):
    return strict_json(ordinary_bytes(path, limit))


def pinned_json(base, descriptor, limit=33554432):
    if not isinstance(descriptor, dict) or set(descriptor) != {'path', 'bytes', 'sha256'}:
        raise ValueError('Malformed operator asset descriptor')
    relative = Path(descriptor['path'])
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Operator descriptor path must stay within package')
    body = ordinary_bytes(Path(base) / relative, limit)
    if type(descriptor['bytes']) is not int or len(body) != descriptor['bytes'] or hashlib.sha256(body).hexdigest() != descriptor['sha256']:
        raise ValueError('Operator asset pin mismatch')
    return strict_json(body)
