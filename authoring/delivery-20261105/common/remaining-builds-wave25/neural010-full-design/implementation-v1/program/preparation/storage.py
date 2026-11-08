"""Bounded operator preparation I/O; no scientific invocation at import."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import time

HEX = re.compile(r'[0-9a-f]{64}\Z')
ID = re.compile(r'[0-9a-f]{24}\Z')

def need(ok, why):
    if not ok: raise ValueError(why)

def strict(raw):
    def pairs(items):
        result = {}
        for k,v in items:
            need(k not in result, 'duplicate JSON field'); result[k]=v
        return result
    def bad(value): raise ValueError('nonfinite JSON constant')
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=bad)

def encoded(value, newline=True):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False,
                      separators=(',', ':')).encode() + (b'\n' if newline else b'')

def descriptor(body):
    return {'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}

def valid_pin(pin):
    need(type(pin) is dict and set(pin)=={'bytes','sha256'}, 'exact descriptor')
    need(type(pin['bytes']) is int and pin['bytes']>0 and type(pin['sha256']) is str
         and HEX.fullmatch(pin['sha256']), 'typed descriptor')
    return pin

def canonical(value):
    need(type(value) is str and value.startswith('/') and not value.startswith('//')
         and '\x00' not in value and str(Path(value))==value
         and all(x not in ('.','..','') for x in value.split('/')[1:]), 'canonical absolute path')
    p=Path(value)
    for q in [p,*p.parents]:
        if q.exists() or q.is_symlink(): need(not q.is_symlink(), 'no symlink components')
    return p

def disjoint(*paths):
    for i,p in enumerate(paths):
        for q in paths[i+1:]:
            need(p!=q and not p.is_relative_to(q) and not q.is_relative_to(p), 'disjoint roots')

def stamp(s): return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]

class Budget:
    def __init__(self, limits, origin):
        need(type(limits) is dict and set(limits)=={'read_bytes','write_bytes','whole_seconds','project_peak_bytes'},'exact preparation limits')
        for k in ('read_bytes','write_bytes','project_peak_bytes'):
            need(type(limits[k]) is int and limits[k]>0, 'positive integer resource ceiling')
        need(type(origin) in (int,float) and math.isfinite(origin) and origin>0, 'external original clock')
        need(type(limits['whole_seconds']) in (int,float) and math.isfinite(limits['whole_seconds']) and limits['whole_seconds']>0,'whole seconds')
        self.limits=dict(limits);self.origin=float(origin);self.end=self.origin+limits['whole_seconds']
        self.read_bytes=0;self.write_bytes=0;self.annotations=[];self.tick()
    def tick(self): need(time.monotonic()<self.end, 'original preparation deadline')
    def reserve(self,kind,n):
        self.tick();need(type(n)is int and n>=0,'typed reservation')
        k=kind+'_bytes';v=getattr(self,k)+n;need(v<=self.limits[k],'preparation '+kind+' bound')
        setattr(self,k,v)
    def record(self):
        return {'original_origin':self.origin,'deadline':self.end,'logical_reserved_read_bytes':self.read_bytes,
                'logical_reserved_write_bytes':self.write_bytes,'limits':self.limits,
                'physical_IO_or_RSS_measured':False}

def capture(path,pin,budget,cap=None):
    valid_pin(pin);need(cap is None or pin['bytes']<=cap,'input extent cap')
    budget.reserve('read',pin['bytes']+1)
    fd=os.open(path,os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW)
    try:
        a=os.fstat(fd);need(stat.S_ISREG(a.st_mode) and a.st_nlink==1 and a.st_size==pin['bytes'],'ordinary exact single-link source')
        out=bytearray()
        while len(out)<=pin['bytes']:
            b=os.read(fd,min(65536,pin['bytes']+1-len(out)))
            if not b:break
            out.extend(b);budget.tick()
        z=os.fstat(fd);need(stamp(a)==stamp(z),'source immutable during capture')
        body=bytes(out);need(descriptor(body)==pin,'captured source identity');budget.tick();return body
    finally:os.close(fd)

def hash_file(path,budget,cap):
    budget.reserve('read',cap+1);fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        a=os.fstat(fd);need(stat.S_ISREG(a.st_mode) and a.st_nlink==1 and 0<a.st_size<=cap,'bounded exact output')
        h=hashlib.sha256();n=0
        while True:
            b=os.read(fd,min(1048576,cap+1-n))
            if not b:break
            n+=len(b);need(n<=cap,'hash cap');h.update(b);budget.tick()
        need(n==a.st_size and stamp(a)==stamp(os.fstat(fd)),'hashed output immutable')
        budget.tick();return {'bytes':n,'sha256':h.hexdigest()}
    finally:os.close(fd)

def sync_directory(path,budget):
    budget.tick();fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        need(stat.S_ISDIR(os.fstat(fd).st_mode),'owned directory')
        os.fsync(fd)
    finally:os.close(fd)
    budget.tick()

def mkdir_fresh(path,budget):
    budget.tick();os.mkdir(path,0o700)
    sync_directory(path,budget);sync_directory(Path(path).parent,budget)

def mkdirs_owned(path,root,budget):
    path=Path(path);root=Path(root)
    need(path.is_relative_to(root) and path!=root,'owned descendant directory')
    current=root
    for part in path.relative_to(root).parts:
        current=current/part
        if current.exists():
            need(not current.is_symlink() and stat.S_ISDIR(current.lstat().st_mode),'existing owned directory')
        else:mkdir_fresh(current,budget)

def sync_owned_file(path,budget):
    budget.tick();fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink==1,'owned ordinary output')
        os.fsync(fd)
        need(stamp(before)==stamp(os.fstat(fd)),'owned output stable through sync')
    finally:os.close(fd)
    budget.tick();sync_directory(Path(path).parent,budget)

def write(path,body,budget):
    budget.reserve('write',len(body));fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400)
    try:
        v=memoryview(body)
        while v:
            n=os.write(fd,v);need(n>0,'complete write');v=v[n:];budget.tick()
        os.fsync(fd)
    finally:os.close(fd)
    sync_directory(Path(path).parent,budget);budget.tick();return descriptor(body)
