"""Portable bounded file transport. No candidate execution or global state."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat


def need(ok, message):
    if not ok:
        raise ValueError(message)


def exact(value, fields):
    need(type(value) is dict and set(value) == set(fields), 'Exact object fields')


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                       allow_nan=False) + '\n').encode('ascii')


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def check_pin(value, cap, empty=False):
    exact(value, ['bytes', 'sha256'])
    need(type(value['bytes']) is int and int(not empty) <= value['bytes'] <= cap and
         type(value['sha256']) is str and re.fullmatch('[a-f0-9]{64}', value['sha256']), 'Exact bounded pin')


def resolve(root, relative):
    need(type(relative) is str and relative and not Path(relative).is_absolute() and
         all(x not in ('', '.', '..') for x in relative.split('/')) and '\\' not in relative,
         'Safe relative input path')
    return Path(root) / relative


def regular(path):
    path = Path(path).absolute()
    need(all(not p.is_symlink() for p in (path, *path.parents)), 'No linked paths')
    return path


def read(path, cap, expected=None, empty=False, retain=True):
    path = regular(path)
    if expected is not None:
        check_pin(expected, cap, empty)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
             int(not empty) <= before.st_size <= cap, 'Bounded ordinary single-link input')
        if expected is not None:
            need(before.st_size == expected['bytes'], 'Exact byte size')
        digest = hashlib.sha256(); count = 0; chunks = []
        for block in iter(lambda: stream.read(1048576), b''):
            count += len(block); need(count <= cap, 'Bounded stream')
            digest.update(block)
            if retain:
                chunks.append(block)
        after = os.fstat(stream.fileno())
        need(count == before.st_size and all(getattr(before, key) == getattr(after, key)
             for key in ('st_dev', 'st_ino', 'st_size', 'st_nlink', 'st_mtime_ns', 'st_ctime_ns')), 'Stable full file')
    observed = {'bytes': count, 'sha256': digest.hexdigest()}
    need(expected is None or observed == expected, 'Exact content binding')
    return b''.join(chunks) if retain else observed


def decode(body):
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'Duplicate JSON field'); result[key] = value
        return result
    def finite(value):
        number = float(value); need(math.isfinite(number), 'Finite JSON number'); return number
    def integer(value):
        need(len(value) <= 18, 'Bounded integer'); return int(value)
    def invalid(value):
        raise ValueError('Nonstandard JSON constant')
    try:
        return json.loads(body.decode('utf-8'), object_pairs_hook=pairs, parse_float=finite,
                          parse_int=integer, parse_constant=invalid)
    except (UnicodeError, RecursionError, OverflowError) as error:
        raise ValueError('Malformed bounded JSON') from error


def json_file(path, cap=524288, expected=None):
    return decode(read(path, cap, expected))


def put(path, value, cap=524288):
    path = regular(path); body = canonical(value); need(len(body) <= cap, 'Output cap')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(body); stream.flush(); os.fsync(stream.fileno())
    path.chmod(0o444)
    return pin(body)


def fresh(path):
    path = regular(path)
    need(not path.exists() and path.parent.is_dir(), 'Fresh owned output directory')
    path.mkdir(mode=0o700)
    return path


def asset(root, record, decode_json=False):
    expected = {k: record[k] for k in ('bytes', 'sha256')}
    path = resolve(root, record['path'])
    if decode_json:
        return json_file(path, record['bytes'], expected)
    return read(path, record['bytes'], expected, retain=False)


def program_pin(value):
    check_pin(value, 131072)


from contextlib import contextmanager
@contextmanager
def verified_stream(path, expected):
    """Hash and decode a single open regular file; recheck identity after decoder closes."""
    check_pin(expected, expected['bytes'])
    path = regular(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
             before.st_size == expected['bytes'], 'Exact ordinary source')
        digest = hashlib.sha256(); count = 0
        for block in iter(lambda: stream.read(1048576), b''):
            count += len(block); need(count <= expected['bytes'], 'Source cap')
            digest.update(block)
        need({'bytes': count, 'sha256': digest.hexdigest()} == expected, 'Source content pin')
        stream.seek(0)
        try:
            yield stream
        finally:
            after = os.fstat(stream.fileno())
            need(all(getattr(before, key) == getattr(after, key) for key in
                     ('st_dev', 'st_ino', 'st_size', 'st_nlink', 'st_mtime_ns', 'st_ctime_ns')),
                 'Source changed during decoding')
