"""Bounded source/data contracts. Validation is not original-data authentication."""
import hashlib
import json
import math
import os
import re
import stat
from pathlib import Path, PurePosixPath

MAX_FRAME = 2 * 1024 * 1024
IDENT = re.compile(r"[A-Za-z0-9_.:-]{1,160}\Z")


def need(condition, message):
    if not condition:
        raise ValueError(message)


def exact(value, keys, label):
    need(type(value) is dict and set(value) == set(keys), label + ': exact fields')
    return value


def ident(value):
    need(type(value) is str and IDENT.fullmatch(value) is not None, 'bounded identifier')
    return value


def finite(value, *, nonnegative=False):
    need(type(value) in (int, float) and math.isfinite(value), 'finite real, not boolean')
    need(not nonnegative or value >= 0, 'nonnegative real')
    return value


def integer(value, lower=0, upper=2**53):
    need(type(value) is int and lower <= value <= upper, 'bounded exact integer')
    return value


def sha(value):
    need(type(value) is str and re.fullmatch('[a-f0-9]{64}', value), 'SHA256 identity')
    return value


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def _pairs(rows):
    answer = {}
    for key, value in rows:
        need(key not in answer, 'duplicate JSON key')
        answer[key] = value
    return answer


def decode(raw):
    return json.loads(raw, object_pairs_hook=_pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def vector(value, width=None):
    need(type(value) is list and value and (width is None or len(value) == width), 'vector support')
    return [finite(x) for x in value]


def matrix(value, rows=None, columns=None):
    need(type(value) is list and value and (rows is None or len(value) == rows), 'matrix rows')
    width = len(vector(value[0], columns))
    return [vector(x, width) for x in value]


def descriptor(value):
    exact(value, ('path', 'bytes', 'sha256'), 'file descriptor')
    name = value['path']
    need(type(name) is str and 0 < len(name) <= 512, 'relative path length')
    path = PurePosixPath(name)
    need(not path.is_absolute() and all(p not in ('', '.', '..') for p in path.parts)
         and '\\' not in name and str(path) == name, 'normalized owned relative path')
    integer(value['bytes'], 0)
    sha(value['sha256'])
    return value


def bound_bytes(root, desc, maximum):
    """Future authorized operator reads only: no implicit traversal or deserialization."""
    descriptor(desc)
    integer(maximum, 1)
    need(desc['bytes'] <= maximum, 'declared file ceiling')
    root = Path(root)
    need(root.is_absolute(), 'absolute owned root')
    path = root.joinpath(*PurePosixPath(desc['path']).parts)
    need(all(not p.is_symlink() for p in (path, *path.parents)), 'no symlink path components')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_size == desc['bytes'], 'regular exact-size file')
        parts, total, h = [], 0, hashlib.sha256()
        while True:
            block = os.read(fd, min(65536, maximum + 1 - total))
            if not block:
                break
            total += len(block)
            need(total <= maximum, 'observed byte ceiling')
            h.update(block)
            parts.append(block)
        after = os.fstat(fd)
        need((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
             (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), 'file stable during capture')
        need(total == desc['bytes'] and h.hexdigest() == desc['sha256'], 'exact content identity')
        return b''.join(parts)
    finally:
        os.close(fd)


def bound_json(root, desc, maximum):
    return decode(bound_bytes(root, desc, maximum))


def close_numbers(left, right, atol=1e-10, rtol=1e-9):
    """No extra/missing/undefined leaf can disappear in bank agreement."""
    if type(left) is dict:
        need(type(right) is dict and set(left) == set(right), 'bank object support')
        for key in left:
            close_numbers(left[key], right[key], atol, rtol)
    elif type(left) is list:
        need(type(right) is list and len(left) == len(right), 'bank list support')
        for a, b in zip(left, right):
            close_numbers(a, b, atol, rtol)
    elif type(left) in (int, float):
        finite(left); finite(right)
        need(abs(left - right) <= atol + rtol * max(abs(left), abs(right)), 'independent numerical disagreement')
    else:
        need(type(left) is type(right) and left == right, 'bank literal equality')
