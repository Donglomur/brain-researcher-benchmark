"""Bounded JSON contract helpers. Import performs no file or numerical work."""
import hashlib
import json
import math
import os
import re
import stat
from pathlib import Path

TASK = 'PAPER-paper-method-replacement-013'
REVISION = '36ed94084628c253098d448048c980d3dea0050d'
ARMS = ('paper_and_data', 'paper_data_official_code')
MAX_JSON = 32_000_000


def require(condition, message):
    if not condition:
        raise ValueError(message)


def exact(value, keys):
    require(type(value) is dict and set(value) == set(keys), 'exact object fields')


def identifier(value):
    require(type(value) is str and re.fullmatch(r'[A-Za-z0-9_-]{1,96}', value) is not None,
            'bounded opaque identifier')


def sha256(value):
    require(type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None, 'sha256')


def number(value):
    require(type(value) in (int, float), 'numeric scalar, not boolean')
    try:
        finite = math.isfinite(value)
    except (OverflowError, ValueError):
        finite = False
    require(finite, 'finite scalar')
    return value


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def digest(value):
    return hashlib.sha256(encode(value)).hexdigest()


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate JSON key')
        result[key] = value
    return result


def decode(body):
    return json.loads(body.decode('utf8'), object_pairs_hook=unique_pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def capture(path, cap=MAX_JSON):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_size <= cap, 'bounded regular file')
        body = bytearray()
        while len(body) <= cap:
            block = os.read(fd, min(1048576, cap + 1 - len(body)))
            if not block:
                break
            body.extend(block)
        after = os.fstat(fd)
        fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        require(len(body) == before.st_size and
                all(getattr(before, k) == getattr(after, k) for k in fields), 'stable file')
        return bytes(body)
    finally:
        os.close(fd)


def load(path):
    return decode(capture(path))


def fresh(path):
    path = Path(path)
    require(not path.exists() and not path.is_symlink(), 'fresh output')
    return path


def save(path, value):
    body = encode(value)
    require(len(body) <= MAX_JSON, 'output byte cap')
    with Path(path).open('xb') as stream:
        stream.write(body)


def unique_ids(values, expected=None):
    require(type(values) is list and 0 < len(values) <= 100000, 'bounded nonempty IDs')
    for value in values:
        identifier(value)
    require(len(set(values)) == len(values), 'unique IDs')
    require(expected is None or len(values) == expected, 'complete cohort')
    return values
