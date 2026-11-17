"""Logical input custody only; native/OS accounting authority remains external."""
from dataclasses import dataclass
from pathlib import Path
import os,stat,hashlib,json
from programme.contracts import need,Pin,Asset

class Ledger:
    def __init__(self):self.events=[];self.first=None
    def record(self,where,error):
        self.events.append((where,error))
        if self.first is None:self.first=error
    def propagated(self,where,error):
        if not any(error is old for _,old in self.events):self.record(where,error)
    def attempt(self,where,fn):
        try:return fn()
        except BaseException as e:self.record(where,e);return None
    def raise_first(self):
        if self.first is not None:raise self.first
    def summary(self):return [{'where':w,'error_type':type(e).__name__,'occurrence':i} for i,(w,e) in enumerate(self.events)]

class Accounting:
    def __init__(self,read_limit,write_limit):
        need(type(read_limit) is int and type(write_limit) is int and min(read_limit,write_limit)>0,'explicit finite byte allowances')
        self.read_limit,self.write_limit=read_limit,write_limit;self.read=0;self.write=0
    def charge(self,kind,n):
        need(kind in ('read','write') and type(n) is int and n>=0,'logical charge before effects')
        value=getattr(self,kind)+n;need(value<=getattr(self,kind+'_limit'),'complete logical budget exceeded')
        setattr(self,kind,value)
    def report(self):return {'logical_read_reserved':self.read,'logical_write_reserved':self.write,'basis':'prospective charges for explicit requested bytes; not measured library or OS IO','physical_native_process_cost':'UNKNOWN','qualification':False}

def stable(a,b):
    return all(getattr(a,k)==getattr(b,k) for k in ('st_dev','st_ino','st_size','st_nlink','st_mtime_ns','st_ctime_ns'))

def open_pinned(root,asset,accounting,ledger):
    need(type(asset) is Asset,'typed exact input member')
    root=Path(root);path=root/asset.path
    for part in (path,*path.parents):need(not part.is_symlink(),'no source symlink ancestor')
    accounting.charge('read',asset.pin.bytes+1)
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    f=None
    try:
        before=os.fstat(fd);need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==asset.pin.bytes,'exact ordinary source extent before decoder')
        f=os.fdopen(fd,'rb');fd=None;h=hashlib.sha256();n=0
        while True:
            b=f.read(min(1048576,asset.pin.bytes-n+1))
            if not b:break
            n+=len(b);need(n<=asset.pin.bytes,'no source growth');h.update(b)
        need(n==asset.pin.bytes and h.hexdigest()==asset.pin.sha256 and stable(before,os.fstat(f.fileno())),'whole stable source identity')
        f.seek(0);return f,before
    except BaseException as error:
        ledger.record('source-admission',error)
        if f is not None:ledger.attempt('admission-stream-close',f.close)
        elif fd is not None:ledger.attempt('admission-fd-close',lambda:os.close(fd))
        raise error


def encoded(value):return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()

def write_fresh(path,body,accounting,ledger):
    path=Path(path);need(type(body) is bytes,'exact captured bytes')
    ledger.raise_first();accounting.charge('write',len(body));fd=None;stream=None
    try:
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        stream=os.fdopen(fd,'wb');fd=None
        stream.write(body);stream.flush();os.fsync(stream.fileno())
    except BaseException as error:ledger.record('capture-write',error)
    finally:
        if stream is not None:ledger.attempt('capture-stream-close',stream.close)
        elif fd is not None:ledger.attempt('capture-fd-close',lambda:os.close(fd))
    ledger.raise_first()
    return Pin(len(body),hashlib.sha256(body).hexdigest())
