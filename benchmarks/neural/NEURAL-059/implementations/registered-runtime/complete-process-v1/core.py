"""Task-specific ordinary custody and bounded protocol; no activation on import."""
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import stat

TASK = 'NEURAL-059'
CONDITIONS = ('SH', 'SHN', 'SBH', 'SBHN')
STATUS = 'source_only_unqualified'


def need(value, reason):
    if not value:
        raise ValueError(reason)


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=True, allow_nan=False) + '\n').encode()


def parse(body):
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    return json.loads(body, object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'nonfinite JSON'))


def pin(body):
    if type(body) is not bytes:
        body = encode(body)
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def keys(value, names):
    need(type(value) is dict and set(value) == set(names), 'exact schema: ' + ','.join(names))


def integer(value, minimum=1):
    need(type(value) is int and value >= minimum, 'positive selected integer')
    return value


def positive(value):
    need(type(value) in (int, float) and math.isfinite(value) and value > 0,
         'positive finite selected quantity')
    return value


def literal(path):
    p = Path(path)
    need(p.is_absolute() and '..' not in p.parts and
         not any(x.is_symlink() for x in (p, *p.parents)), 'literal absolute unlinked path')
    return p


def read(path, cap, budget=None):
    p = literal(path); integer(cap); fd = None
    if budget is not None:
        budget.admit_read(cap + 1)
    try:
        fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        st = os.fstat(fd)
        need(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and st.st_size <= cap,
             'bounded single-link ordinary source/operand')
        out = bytearray()
        while len(out) <= cap:
            chunk = os.read(fd, min(65536, cap + 1 - len(out)))
            out.extend(chunk)
            if budget is not None:
                budget.read(len(chunk))
            if not chunk:
                break
        after = os.fstat(fd)
        need(len(out) == st.st_size and all(getattr(st, k) == getattr(after, k)
             for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_nlink')),
             'stable complete captured operand')
        return bytes(out)
    finally:
        if fd is not None:
            os.close(fd)


def capture(descriptor, budget=None):
    keys(descriptor, ('path', 'bytes', 'sha256'))
    body = read(descriptor['path'], descriptor['bytes'], budget)
    need(pin(body) == {k: descriptor[k] for k in ('bytes','sha256')}, 'exact frozen operand body')
    return body


def verify_file(descriptor,budget):
    """Stream immutable checkpoint bodies; never allocate an entire weight shard."""
    keys(descriptor,('path','bytes','sha256')); p=literal(descriptor['path'])
    fd=None; count=0; digest=hashlib.sha256(); expected=descriptor['bytes']
    need(type(expected) is int and expected>=0,'finite selected checkpoint extent')
    budget.admit_read(expected+1)
    try:
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK); before=os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==expected,
             'ordinary exact checkpoint body')
        while count<=expected:
            chunk=os.read(fd,min(65536,expected+1-count)); count+=len(chunk)
            digest.update(chunk); budget.read(len(chunk))
            if not chunk: break
        after=os.fstat(fd)
        need(count==expected and digest.hexdigest()==descriptor['sha256'] and
             all(getattr(before,k)==getattr(after,k) for k in
                 ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_nlink')),
             'complete stable original checkpoint identity')
    finally:
        if fd is not None: os.close(fd)
    return {k:descriptor[k] for k in ('bytes','sha256')}


def decode_body(value, cap):
    need(type(value) is str and len(value) <= 4*((cap+2)//3), 'bounded encoded actor artifact')
    body = base64.b64decode(value, validate=True)
    need(0 < len(body) <= cap, 'nonempty bounded actual actor artifact')
    return body


def source_body(value):
    return base64.b64encode(value).decode('ascii')
