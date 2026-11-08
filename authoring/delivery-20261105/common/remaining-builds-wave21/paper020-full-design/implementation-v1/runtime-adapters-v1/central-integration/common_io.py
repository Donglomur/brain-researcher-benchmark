"""Bounded stdlib source/metadata custody. Not an OS accountant or authority."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time

def need(ok, message):
    if not ok: raise ValueError(message)

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

def scientific_digest(value):
    # Original scientific strict.encoded uses UTF-8 rather than ASCII escapes;
    # adapter envelopes/wire manifests deliberately retain their own encoding.
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()

def sha(body): return hashlib.sha256(body).hexdigest()
def pin(body): return {'bytes':len(body),'sha256':sha(body)}
def only_pin(value):
    need(type(value)is dict and type(value.get('bytes'))is int and value['bytes']>=0,'exact nonnegative extent')
    need(type(value.get('sha256'))is str and re.fullmatch('[0-9a-f]{64}',value['sha256']),'SHA256 required')
    return {k:value[k]for k in ('bytes','sha256')}

def parse(body):
    def pairs(items):
        out={}
        for k,v in items: need(k not in out,'duplicate JSON key');out[k]=v
        return out
    def constant(value): raise ValueError('nonfinite JSON constant')
    return json.loads(body,object_pairs_hook=pairs,parse_constant=constant)

def relative(value):
    need(type(value)is str and value and '\\' not in value and not value.startswith('/')
         and all(x not in ('','.','..')for x in value.split('/')),'canonical relative path required')
    return value

def absolute(value):
    need(type(value)is str and value.startswith('/') and str(Path(value))==value
         and '..' not in Path(value).parts,'canonical absolute path required')
    return Path(value)

def components(path):
    path=absolute(str(path));current=Path('/')
    for part in path.parts[1:]:
        current=current/part
        need(not current.is_symlink(),'symlink component forbidden')
    return path

def descriptor(value):
    need(type(value)is dict and set(value)=={'path','bytes','sha256'},'exact path/pin descriptor')
    absolute(value['path']);only_pin(value);return value

class Reader:
    def __init__(self,origin,deadline,read_limit=100_000_000,write_limit=100_000_000,clock=time.monotonic_ns):
        self.origin,self.deadline,self.clock=origin,deadline,clock
        self.read_limit,self.write_limit=read_limit,write_limit
        self.read_reserved=self.read_observed=self.write_bytes=self.hash_bytes=0
    def tick(self):
        now=self.clock();need(type(now)is int and self.origin<=now<self.deadline,'original strict deadline exceeded');return now
    def reserve_read(self,n):
        need(type(n)is int and n>=0 and self.read_reserved+n<=self.read_limit,'source/metadata read bound exceeded')
        self.read_reserved+=n
    def read(self,path,cap,expected=None):
        self.tick();path=components(path);info=path.lstat()
        need(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and info.st_size<=cap,'bounded regular single-link file required')
        if expected is not None: need(info.st_size==only_pin(expected)['bytes'],'pinned file extent differs')
        self.reserve_read(info.st_size+1)
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            before=os.fstat(fd);need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==info.st_size,'opened file extent differs')
            with os.fdopen(fd,'rb',closefd=False)as stream: raw=stream.read(info.st_size+1)
            after,named=os.fstat(fd),path.lstat()
            fields=('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_nlink')
            need(all(getattr(info,k)==getattr(before,k)==getattr(after,k)==getattr(named,k)for k in fields)
                 and len(raw)==info.st_size,'file changed during capture')
        finally:os.close(fd)
        self.read_observed+=len(raw);self.hash_bytes+=len(raw)
        if expected is not None:need(pin(raw)==only_pin(expected),'source/metadata pin differs')
        self.tick();return raw
    def json(self,path,cap,expected=None):
        raw=self.read(path,cap,expected);return parse(raw),pin(raw)
    def file_pin(self,path,expected):
        """Opaque streaming hash; never deserializes an authentic array."""
        expected=only_pin(expected);path=components(path);self.tick();before=path.lstat()
        need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==expected['bytes'],'exact immutable artifact extent')
        self.reserve_read(before.st_size+1);fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        h=hashlib.sha256();size=0
        try:
            opened=os.fstat(fd)
            while size<=before.st_size:
                raw=os.read(fd,min(65536,before.st_size+1-size))
                if not raw:break
                size+=len(raw);self.read_observed+=len(raw);self.hash_bytes+=len(raw);h.update(raw);self.tick()
            after,named=os.fstat(fd),path.lstat()
            fields=('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_nlink')
            need(all(getattr(before,k)==getattr(opened,k)==getattr(after,k)==getattr(named,k)for k in fields),'artifact changed during hash')
        finally:os.close(fd)
        result={'bytes':size,'sha256':h.hexdigest()};need(result==expected,'artifact content differs');self.tick();return result
    def write(self,path,raw):
        self.tick();path=components(path)
        need(type(raw)is bytes and self.write_bytes+len(raw)<=self.write_limit,'metadata write bound exceeded')
        self.write_bytes+=len(raw)
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400)
        try:
            with os.fdopen(fd,'wb',closefd=False)as stream:stream.write(raw);stream.flush();os.fsync(fd)
        finally:os.close(fd)
        self.tick();return pin(raw)
    def report(self):
        return {'logical_read_reserved':self.read_reserved,'logical_read_observed':self.read_observed,
                'logical_write_bytes':self.write_bytes,'hash_input_bytes':self.hash_bytes,
                'physical_accounting':False}

def freeze_directories(root):
    # Called only for a fresh source-owned staging tree, never shared source.
    for current,dirs,files in os.walk(root,topdown=False):
        for name in files:os.chmod(Path(current)/name,0o400)
        os.chmod(current,0o500)
