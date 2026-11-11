"""Explicit logical source custody; this is not a deployment/admission issuer."""
import hashlib
import io
import json
import os
from pathlib import Path
import stat

def need(ok, message):
    if not ok:
        raise ValueError(message)

def integer(value, low, high):
    return type(value) is int and low <= value <= high

def digest(value):
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)

def descriptor(row, max_bytes=100_000_000):
    need(type(row) is dict and set(row) == {'path','bytes','sha256'}, 'Closed input descriptor')
    need(integer(row['bytes'], 1, max_bytes) and digest(row['sha256']), 'Bounded input identity')
    need(type(row['path']) is str,'String input path')
    p=Path(row['path'])
    need(type(row['path']) is str and not p.is_absolute() and p.parts and all(x not in ('.','..') for x in p.parts), 'Relative local input path')
    return row

class Owner:
    """Caller-selected logical limits and raw-first exception custody only.

    No default allowances; limits are not measured native peak/CPU or authority.
    A qualified deployment must separately constrain native libraries and memory.
    """
    def __init__(self, limits):
        need(type(limits) is dict and set(limits)=={'read_bytes','write_bytes','retained_bytes','attempts'}, 'Original explicit limits')
        need(all(integer(x,1,2**63-1) for x in limits.values()), 'Positive integer limits')
        self.limits=dict(limits);self.used=dict.fromkeys(limits,0);self.attempts=[]
    def reserve(self, key, amount):
        need(integer(amount,0,2**63-1) and self.used[key]+amount<=self.limits[key], 'Logical source capacity exhausted: '+key)
        self.used[key]+=amount
    def begin(self, label):
        self.reserve('attempts',1)
        record={'operation':label,'state':'entered','first':None,'secondary':[]}
        self.attempts.append(record)
        return record
    def failure(self, record, exc):
        if record['first'] is None:record['first']=exc
        else:record['secondary'].append(exc)
        record['state']='failed'
    def close(self, record, callback):
        try:callback()
        except BaseException as exc:self.failure(record,exc)
    def complete(self, record):
        if record['first'] is not None:raise record['first']
        record['state']='complete'

def capture(root, row, owner, *, max_bytes=100_000_000):
    rec=owner.begin('capture')
    fd=None;stream=None;data=None;fds=[]
    try:
        descriptor(row,max_bytes)
        owner.reserve('read_bytes',row['bytes']+1)
        owner.reserve('retained_bytes',row['bytes'])
        # Walk every component through descriptors; never resolve an alias.
        parent=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);fds.append(parent)
        parts=Path(row['path']).parts
        for part in parts[:-1]:
            parent=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parent);fds.append(parent)
        fd=os.open(parts[-1],os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=parent)
        before=os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_size==row['bytes'],'Exact regular input extent')
        stream=os.fdopen(fd,'rb',closefd=False)
        data=stream.read(row['bytes']+1)
        after=os.fstat(fd)
        state=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        need(state(before)==state(after) and len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256'],'Exact captured bytes')
    except BaseException as exc:owner.failure(rec,exc)
    finally:
        if stream is not None:owner.close(rec,stream.close)
        if fd is not None:owner.close(rec,lambda:os.close(fd))
        for handle in reversed(fds):owner.close(rec,lambda h=handle:os.close(h))
    owner.complete(rec)
    return data

class Writer:
    def __init__(self, root, owner):
        self.root=Path(root);self.owner=owner;self.files=[]
        rec=owner.begin('create_output')
        try:self.root.mkdir(parents=False,exist_ok=False)
        except BaseException as exc:owner.failure(rec,exc)
        owner.complete(rec)
    def put(self, name, body):
        rec=self.owner.begin('write:'+name);fd=None;stream=None
        try:
            need(type(name) is str and Path(name).name==name and name not in ('.','..'),'Output basename')
            self.owner.reserve('write_bytes',len(body))
            fd=os.open(self.root/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            stream=os.fdopen(fd,'wb',closefd=False)
            need(stream.write(body)==len(body),'Complete output write');stream.flush()
            row={'path':name,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}
            self.files.append(row)
        except BaseException as exc:self.owner.failure(rec,exc)
        finally:
            if stream is not None:self.owner.close(rec,stream.close)
            if fd is not None:self.owner.close(rec,lambda:os.close(fd))
        self.owner.complete(rec);return row
    def array(self, name, array):
        rec=self.owner.begin('serialize_array:'+name);buffer=None;result=None
        try:
            import numpy as np
            need(array.dtype.kind in 'fiub' and not array.dtype.hasobject and np.isfinite(array).all(),'Finite primitive output')
            self.owner.reserve('retained_bytes',int(array.nbytes)+4096)
            buffer=io.BytesIO();np.save(buffer,array,allow_pickle=False)
            result=self.put(name,buffer.getvalue())
        except BaseException as exc:self.owner.failure(rec,exc)
        finally:
            if buffer is not None:self.owner.close(rec,buffer.close)
        self.owner.complete(rec);return result
    def document(self,name,obj):
        rec=self.owner.begin('serialize_json:'+name);result=None
        try:result=self.put(name,(json.dumps(obj,allow_nan=False,separators=(',',':'))+'\n').encode())
        except BaseException as exc:self.owner.failure(rec,exc)
        self.owner.complete(rec);return result
