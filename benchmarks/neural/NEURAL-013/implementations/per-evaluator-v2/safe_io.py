"""Bounded JSON and exclusive writes; no pickle, imports or candidate execution."""
import json
import math
import os
from pathlib import Path
import stat

from core import ContractError, canonical, need


def read_bytes(path, cap):
    path = Path(path).absolute()
    need(not any(p.is_symlink() for p in (path, *path.parents)), 'linked path rejected')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap,
             'bounded ordinary single-link file required')
        body = stream.read(cap + 1)
        after = os.fstat(stream.fileno())
        need(len(body) == before.st_size and
             (before.st_ino, before.st_size, before.st_mtime_ns) ==
             (after.st_ino, after.st_size, after.st_mtime_ns), 'file changed while reading')
    return body


def parse_json(body):
    def unique(pairs):
        result = {}
        for k, v in pairs:
            need(k not in result, 'duplicate JSON field')
            result[k] = v
        return result
    def bad(value):
        raise ContractError('nonfinite JSON constant')
    def integer(value):
        need(len(value) <= 18, 'oversized JSON integer')
        return int(value)
    def number(value):
        result = float(value)
        need(math.isfinite(result), 'nonfinite JSON number')
        return result
    try:
        return json.loads(body.decode('utf-8'), object_pairs_hook=unique,
                          parse_constant=bad, parse_int=integer, parse_float=number)
    except (UnicodeError, RecursionError, json.JSONDecodeError) as exc:
        raise ContractError('malformed JSON') from exc


def read_json(path, cap=64000000):
    return parse_json(read_bytes(path, cap))


def write_bytes(path, body):
    path = Path(path).absolute()
    need(not any(p.is_symlink() for p in (path, *path.parents)), 'linked output path')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())


def write_json(path, value):
    write_bytes(path, canonical(value) + b'\n')
