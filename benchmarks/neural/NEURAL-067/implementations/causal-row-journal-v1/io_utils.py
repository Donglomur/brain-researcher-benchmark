"""Exact source-derived file/encoding helpers for the row journal; stdlib only."""
import hashlib, json, os, stat
from pathlib import Path

def need(ok,message):
    if not ok:raise ValueError(message)
def identity(b):return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def parse(b):
    def pairs(rows):
        out={}
        for k,v in rows:need(k not in out,'duplicate JSON');out[k]=v
        return out
    return json.loads(b,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'nonfinite JSON'))
def encoded(v):return (json.dumps(v,sort_keys=True,allow_nan=False,separators=(',',':'))+'\n').encode()
def ordinary(p):
    p=Path(p).absolute();need('..' not in p.parts and not any(q.is_symlink() for q in (p,*p.parents)),'unlinked literal path');return p
def stamp(s):return s.st_dev,s.st_ino,s.st_mode,s.st_size,s.st_nlink,s.st_mtime_ns,s.st_ctime_ns
def capture(path,cap,expected=None):
    p=ordinary(path);fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        a=os.fstat(fd);need(stat.S_ISREG(a.st_mode) and a.st_nlink==1 and 0<a.st_size<=cap,'bounded regular file')
        if expected:need(a.st_size==expected['bytes'],'pre-read extent')
        with os.fdopen(fd,'rb',closefd=False) as f:b=f.read(cap+1)
        need(len(b)==a.st_size and stamp(a)==stamp(os.fstat(fd))==stamp(p.lstat()),'same-open identity')
        if expected:need(identity(b)=={k:expected[k] for k in ('bytes','sha256')},'exact byte pin')
        return b
    finally:os.close(fd)
def sync(p):
    fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)
