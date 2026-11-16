"""Strict same-capture UTF-8 JSON and bounded ordinary file reads."""
import hashlib
import json
import os
import stat

CAP = 512_000_000


def need(v, message):
    if not v:
        raise ValueError(message)


def decode(body):
    need(type(body) is bytes, 'JSON bytes required')
    def pairs(items):
        d = {}
        for k,v in items:
            need(k not in d, 'duplicate JSON key')
            d[k] = v
        return d
    def bad(value):
        raise ValueError('nonfinite JSON literal')
    return json.loads(body.decode('utf-8',errors='strict'), object_pairs_hook=pairs, parse_constant=bad)


def capture(path, cap=CAP, sha256=None):
    fd = os.open(path, os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_size<=cap, 'bounded ordinary file')
        with os.fdopen(fd,'rb',closefd=False) as f:
            body = f.read(cap+1)
        after = os.fstat(fd)
        need(len(body)==before.st_size<=cap and all(getattr(before,k)==getattr(after,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')), 'stable bounded capture')
    finally:
        os.close(fd)
    digest=hashlib.sha256(body).hexdigest()
    need(sha256 is None or digest==sha256,'exact captured file pin')
    return body,digest


def read(path, cap=CAP, sha256=None):
    body,digest=capture(path,cap,sha256)
    return decode(body),digest


def encode(obj):
    return (json.dumps(obj,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n').encode('utf-8')
