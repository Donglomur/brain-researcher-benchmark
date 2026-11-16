"""NEURAL078 deferred-grade source/byte binding; never parses scientific arrays."""
import hashlib, json, os, stat, shutil
from pathlib import Path

def need(ok, message):
    if not ok: raise ValueError(message)

def ordinary(path):
    p=Path(path).absolute()
    need('..' not in p.parts and not any(x.is_symlink() for x in (p,*p.parents)), 'Unlinked literal path')
    need(not any(c in str(p) for c in ',\r\n\0'), 'Unambiguous mounted path')
    return p

def identity(body): return {'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}

READ_BYTES=0
READ_CAP=16000000
def capture(path,cap,pin=None,*,allowed_links=(1,)):
    global READ_BYTES
    p=ordinary(path);fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        a=os.fstat(fd);need(stat.S_ISREG(a.st_mode) and a.st_nlink in allowed_links and 0<a.st_size<=cap,'Bounded ordinary file')
        if pin is not None: need(a.st_size==pin['bytes'],'Pinned size before read')
        READ_BYTES+=a.st_size+1;need(READ_BYTES<=READ_CAP,'Whole host captured-byte read ceiling')
        with os.fdopen(fd,'rb',closefd=False) as f: raw=f.read(a.st_size+1)
        z=os.fstat(fd);keys=('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_nlink')
        need(len(raw)==a.st_size and all(getattr(a,k)==getattr(z,k)==getattr(p.lstat(),k) for k in keys),'Stable captured bytes')
        if pin is not None: need(identity(raw)=={k:pin[k] for k in ('bytes','sha256')},'Pinned bytes')
        return raw
    finally: os.close(fd)

def parse(raw):
    def pairs(rows):
        result={}
        for k,v in rows: need(k not in result,'Duplicate JSON key');result[k]=v
        return result
    return json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,
        parse_constant=lambda _:need(False,'Nonfinite JSON'))

def encoded(value):return (json.dumps(value,sort_keys=True,allow_nan=False,indent=2)+'\n').encode()

def fsync_dir(path):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)

class Budget:
    """Sixty-four MB retained,128 MB cumulative writes;2 MB closing receipt reserve."""
    def __init__(self,root,other_reserve_bytes=0):
        self.root=ordinary(root);self.written=0;self.other=other_reserve_bytes
        need(type(self.other)is int and self.other>=0,'Explicit current OTHER')
    ALLOCATION_QUANTUM=65536
    def physical(self,planned=0):
        need(type(planned)is int and planned>=0,'Explicit prospective allocation')
        allocated=self.root.lstat().st_blocks*512
        for root,dirs,files in os.walk(self.root,followlinks=False):
            for name in dirs+files:
                s=(Path(root)/name).lstat()
                need(not stat.S_ISLNK(s.st_mode) and (stat.S_ISDIR(s.st_mode) or stat.S_ISREG(s.st_mode)),'Ordinary owned allocation')
                allocated+=s.st_blocks*512
        need(allocated+planned<=64000000,'Owned prospective physical allocation cap')
        need(shutil.disk_usage(self.root).free>=20*1024**3+self.other+max(0,64000000-allocated),'Physical floor plus remaining owned allowance')
    def mkdir(self,path,*,parents=False,exist_ok=False):
        p=ordinary(path);need(p.is_relative_to(self.root),'Owned directory')
        if p.exists():need(exist_ok and p.is_dir(),'Existing ordinary directory');return
        if parents and not p.parent.exists():self.mkdir(p.parent,parents=True,exist_ok=True)
        self.physical(2*self.ALLOCATION_QUANTUM);p.mkdir(mode=0o700);fsync_dir(p.parent);self.physical()
    def admit_created_directory(self,path):
        p=ordinary(path);need(p.is_relative_to(self.root) and p.is_dir(),'Inherited owned directory')
        self.physical();fsync_dir(p.parent);self.physical()
    def used(self):
        total=0
        for root,dirs,files in os.walk(self.root,followlinks=False):
            for name in dirs+files:
                p=Path(root)/name;s=p.lstat()
                need(not stat.S_ISLNK(s.st_mode),'No linked retained item')
                if not stat.S_ISDIR(s.st_mode):need(stat.S_ISREG(s.st_mode) and s.st_nlink==1,'Ordinary retained item');total+=s.st_size
        return total
    def check(self,n,receipt=False):
        need(type(n)is int and n>=0,'Finite write length')
        q=self.ALLOCATION_QUANTUM;self.physical(((n+q-1)//q+2)*q)
        need(type(n)is int and n>=0 and self.written+n<=128000000,'Cumulative write cap')
        need(self.used()+n<=64000000-(0 if receipt else 2000000),'Retained cap and closing reserve')
    def write(self,path,body,*,receipt=False,mode=0o444,replace=False,publication=None):
        p=ordinary(path);need(p.is_relative_to(self.root) and p!=self.root,'Owned destination')
        need(type(body)is bytes and (replace or not p.exists()),'Fresh exact bytes')
        self.check(len(body),receipt);self.written+=len(body)
        tmp=p.with_name('.'+p.name+'.pending');need(not tmp.exists(),'Fresh atomic temporary')
        fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        try:
            with os.fdopen(fd,'wb',closefd=False) as f:
                f.write(body);f.flush();os.fchmod(fd,mode);os.fsync(fd);saved=os.fstat(fd)
        finally:os.close(fd)
        if replace:
            os.replace(tmp,p)
            if publication is not None:publication.update(st_dev=saved.st_dev,st_ino=saved.st_ino,**identity(body))
        else:
            # Fresh publication cannot overwrite an unexpected concurrently created path.
            os.link(tmp,p,follow_symlinks=False)
            if publication is not None:publication.update(st_dev=saved.st_dev,st_ino=saved.st_ino,**identity(body))
            tmp.unlink()
        fsync_dir(p.parent);self.physical();return len(body)
    def save(self,path,value,cap=200000,replace=False,publication=None):
        body=encoded(value);need(len(body)<=cap,'Receipt cap')
        self.write(path,body,receipt=True,replace=replace,publication=publication);return identity(body)
