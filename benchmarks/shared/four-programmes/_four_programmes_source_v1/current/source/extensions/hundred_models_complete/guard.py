"""Bounded file and deadline custody for this programme; no sandbox claim."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import time

class Unscorable(ValueError):
    def __init__(self, gate, reason):
        self.gate=gate; super().__init__(f'{gate}: {reason}')

def need(ok, why):
    if not ok: raise ValueError(why)

def encoded(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()

def bare(body): return {'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}

def strict(body):
    def pairs(items):
        out={}
        for k,v in items:
            need(k not in out,'duplicate JSON key');out[k]=v
        return out
    def floating(x):
        f=float(x);need(math.isfinite(f),'finite JSON number');return f
    return json.loads(body,object_pairs_hook=pairs,parse_float=floating,
                      parse_constant=lambda _: need(False,'nonfinite JSON constant'))

def relative(value):
    need(type(value)is str and 0<len(value)<=2048 and '\\'not in value and '\0'not in value,'relative path spelling')
    p=Path(value);need(not p.is_absolute() and all(x not in ('','.','..') for x in value.split('/')),'contained path')
    return p

def descriptor(value):
    need(type(value)is dict and set(value)=={'path','bytes','sha256'},'exact descriptor fields')
    relative(value['path']);need(type(value['bytes'])is int and value['bytes']>=0 and type(value['sha256'])is str and re.fullmatch('[a-f0-9]{64}',value['sha256']),'descriptor extent/hash')
    return value

class Budget:
    def __init__(self, *, read_bytes,write_bytes,work,deadline_ns):
        for x in (read_bytes,write_bytes,work,deadline_ns):need(type(x)is int and x>0,'positive explicit limits')
        self.limits={'read_bytes':read_bytes,'write_bytes':write_bytes,'work':work}
        self.used=dict.fromkeys(self.limits,0);self.deadline_ns=deadline_ns;self.failed=False
    def check(self):
        if self.failed:raise RuntimeError('terminal failed resource budget')
        if time.monotonic_ns()>=self.deadline_ns:
            self.failed=True;raise TimeoutError('whole operation deadline expired')
    def charge(self,kind,n):
        self.check();need(type(n)is int and n>=0,'nonnegative charge')
        self.used[kind]+=n
        if self.used[kind]>self.limits[kind]:
            self.failed=True;raise ValueError(kind+' limit; attempted reservation retained')
    def snapshot(self):return {'limits':dict(self.limits),'reserved':dict(self.used),'deadline_ns':self.deadline_ns,'terminal_failed':self.failed,'physical_IO_RSS_metered':False}

def ordinary(root,spelling):
    root=Path(root).absolute();p=root/relative(spelling)
    need(not any(x.is_symlink() for x in (p,*p.parents)),'no symlink ancestry')
    return p

def capture(root,d,budget,*,cap=16*1024*1024):
    descriptor(d);need(d['bytes']<=cap,'bounded input before read')
    budget.charge('read_bytes',d['bytes']+1);p=ordinary(root,d['path'])
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);primary=None
    try:
        before=os.fstat(fd);need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==d['bytes'],'ordinary exact single-link input')
        with os.fdopen(fd,'rb',closefd=False) as f:body=f.read(d['bytes']+1)
        after=os.fstat(fd);named=p.lstat();fields=('st_dev','st_ino','st_size','st_nlink','st_mode','st_mtime_ns','st_ctime_ns')
        need(all(getattr(before,k)==getattr(after,k)==getattr(named,k) for k in fields),'stable input identity')
        need(bare(body)=={k:d[k] for k in ('bytes','sha256')},'exact input bytes');budget.check();return body
    except BaseException as e:primary=e;raise
    finally:
        try:os.close(fd)
        except BaseException as e:
            if primary is None:raise
            primary.add_note('Input close failed: '+type(e).__name__)

def capture_created(root,spelling,budget,*,cap):
    """Capture a fresh owned child's unknown output after observed natural completion."""
    p=ordinary(root,spelling);fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);primary=None
    try:
        before=os.fstat(fd);need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and 0<=before.st_size<=cap,'bounded ordinary created output')
        budget.charge('read_bytes',before.st_size+1)
        with os.fdopen(fd,'rb',closefd=False) as f:body=f.read(before.st_size+1)
        after=os.fstat(fd);named=p.lstat();fields=('st_dev','st_ino','st_size','st_nlink','st_mode','st_mtime_ns','st_ctime_ns')
        need(len(body)==before.st_size and all(getattr(before,k)==getattr(after,k)==getattr(named,k) for k in fields),'stable actual created output')
        budget.check();return body,{'path':spelling,**bare(body)}
    except BaseException as e:primary=e;raise
    finally:
        try:os.close(fd)
        except BaseException as e:
            if primary is None:raise
            primary.add_note('Created output close failed: '+type(e).__name__)

class Publisher:
    def __init__(self,root,budget):
        self.root=Path(root).absolute();self.budget=budget;self.outputs=[];self.created=False
        budget.check();need(not os.path.lexists(self.root) and not any(x.is_symlink() for x in self.root.parents),'fresh owned output directory')
        self.root.mkdir(mode=0o700);self.created=True
        try:budget.check()
        except BaseException as e:e.known_output_prefix=self.state();raise
    def write(self,name,body):
        p=ordinary(self.root,name);need(p.parent==self.root,'flat owned output file')
        need(type(body)is bytes,'encoded output body');self.budget.charge('write_bytes',len(body))
        row={'path':name,**bare(body),'complete':False};self.outputs.append(row)
        try:
            fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,'wb') as f:
                offset=0
                while offset<len(body):
                    self.budget.check();n=f.write(body[offset:offset+65536]);need(type(n)is int and n>0,'forward output progress');offset+=n
                f.flush();os.fsync(f.fileno())
            self.budget.check();row['complete']=True;return {k:row[k] for k in ('path','bytes','sha256')}
        except BaseException as e:e.known_output_prefix=self.state();raise
    def state(self):return {'root':str(self.root),'created':self.created,'outputs':[dict(x) for x in self.outputs],'budget':self.budget.snapshot()}
