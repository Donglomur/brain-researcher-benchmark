"""Bounded ordinary metadata transport only; no native source/data permission."""
from pathlib import Path
from dataclasses import dataclass,field
import os,stat,hashlib,json

@dataclass
class Budget:
    read_cap:int
    write_cap:int
    reads_reserved:int=0
    writes_reserved:int=0
    known_read_bytes:int=0
    known_write_bytes:int=0
    unknown_effects:list=field(default_factory=list)
    def reserve(self,kind,n):
        if type(n)is not int or n<0:raise ValueError('reservation')
        field=kind+'s_reserved';cap=getattr(self,kind+'_cap')
        if getattr(self,field)+n>cap:raise ValueError(kind+' cap')
        setattr(self,field,getattr(self,field)+n)

class TransferError(Exception):
    def __init__(self,first,cleanup,known,unknown):
        self.first=first;self.cleanup=cleanup;self.known=known;self.unknown=unknown
        super().__init__(str(first))
    def record(self):return {'first':{'type':type(self.first).__name__,'message':str(self.first)},'cleanup':[{'type':type(x).__name__,'message':str(x)} for x in self.cleanup],'known_prefix':self.known,'unknown_effect':self.unknown}

class System:
    open=staticmethod(os.open);read=staticmethod(os.read);write=staticmethod(os.write);close=staticmethod(os.close)
    fsync=staticmethod(os.fsync);link=staticmethod(os.link);unlink=staticmethod(os.unlink)

def encoded(value):return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()

class Store:
    def __init__(self,root,budget,system=None):self.root=Path(root).resolve(strict=True);self.budget=budget;self.sys=system or System()
    def path(self,name):
        p=Path(name)
        if p.is_absolute() or '..' in p.parts or not p.parts:raise ValueError('path')
        current=self.root
        for part in p.parts:
            current=current/part
            if current.is_symlink():raise ValueError('symlink')
        if not current.parent.is_dir():raise ValueError('parent')
        return current
    def read(self,descriptor):
        p=self.path(descriptor['path']);n=descriptor['bytes']
        if type(n)is not int or not 0<=n<=1048576:raise ValueError('ordinary member bound')
        self.budget.reserve('read',n+1);fd=None;known=0;chunks=[];first=None;cleanup=[];unknown=False
        try:
            fd=self.sys.open(p,os.O_RDONLY|os.O_NOFOLLOW);st=os.fstat(fd)
            if not stat.S_ISREG(st.st_mode) or st.st_size!=n:raise ValueError('regular exact length')
            while known<n+1:
                try:block=self.sys.read(fd,min(65536,n+1-known))
                except BaseException:
                    unknown=True;self.budget.unknown_effects.append('read:'+descriptor['path']);raise
                if not block:break
                known+=len(block);self.budget.known_read_bytes+=len(block);chunks.append(block)
            body=b''.join(chunks)
            if len(body)!=n or hashlib.sha256(body).hexdigest()!=descriptor['sha256']:raise ValueError('exact body pin')
            if b'\0' in body:raise ValueError('NUL')
            body.decode('utf8')
        except BaseException as e:first=e
        finally:
            if fd is not None:
                try:self.sys.close(fd)
                except BaseException as e:
                    cleanup.append(e)
                    if first is None:first=e
        if first:raise TransferError(first,cleanup,known,unknown)
        return body
    def publish(self,name,body):
        if not isinstance(body,bytes) or len(body)>1048576 or b'\0' in body:raise ValueError('ordinary body')
        body.decode('utf8');p=self.path(name);part=self.path(name+'.partial');self.budget.reserve('write',len(body))
        fd=None;known=0;first=None;cleanup=[];unknown=False
        try:
            fd=self.sys.open(part,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            while known<len(body):
                try:n=self.sys.write(fd,body[known:])
                except BaseException:
                    unknown=True;self.budget.unknown_effects.append('write:'+name);raise
                if type(n)is not int or not 0<n<=len(body)-known:raise OSError('write progress')
                known+=n;self.budget.known_write_bytes+=n
            self.sys.fsync(fd)
        except BaseException as e:first=e
        finally:
            if fd is not None:
                try:self.sys.close(fd)
                except BaseException as e:
                    cleanup.append(e)
                    if first is None:first=e
        if first is None:
            try:self.sys.link(part,p)
            except BaseException as e:first=e
        if first is None:
            try:self.sys.unlink(part)
            except BaseException as e:first=e;cleanup.append(e)
        if first:raise TransferError(first,cleanup,known,unknown)
        return {'path':name,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}
