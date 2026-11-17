"""Bounded regular-FD JSON capture; no scientific code imported."""
import json
import math
import os
import stat
from pathlib import Path
import re

TASK='NEURAL-100'
CONTRACT='neural100_released_panel_draft_v1'
ID=re.compile(r'[A-Za-z0-9_-]{1,100}')
MAX_JSON=64_000_000

class Invalid(ValueError):pass

def capture_regular(path,cap=MAX_JSON):
    """Capture one bounded regular FD; reject symlinks, FIFOs and changed files."""
    fd=None
    try:
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        before=os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size>cap:
            raise Invalid('bounded regular file required')
        body=bytearray()
        while True:
            chunk=os.read(fd,min(1_048_576,cap+1-len(body)))
            if not chunk:break
            body.extend(chunk)
            if len(body)>cap:raise Invalid('JSON byte cap')
        after=os.fstat(fd);named=os.lstat(path)
        fields=('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')
        if any(getattr(before,k)!=getattr(after,k) for k in fields) or \
                any(getattr(after,k)!=getattr(named,k) for k in fields) or \
                not stat.S_ISREG(named.st_mode) or len(body)!=after.st_size:
            raise Invalid('file changed during capture')
        return bytes(body)
    except OSError as e:
        raise Invalid('regular file capture failed: '+type(e).__name__) from e
    finally:
        if fd is not None:os.close(fd)

def decode_json(body):
    def pairs(items):
        d={}
        for k,v in items:
            if k in d:raise Invalid('duplicate JSON key')
            d[k]=v
        return d
    try:
        return json.loads(body,object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(Invalid('nonfinite JSON')))
    except (ValueError,UnicodeError,RecursionError) as e:
        raise Invalid('invalid JSON: '+type(e).__name__) from e

def read_json(path,cap=MAX_JSON):
    return decode_json(capture_regular(path,cap))

