"""Task-local metadata budgets and exclusive durable publication; stdlib only."""
import hashlib,json,os,stat,time,types,sys
from pathlib import Path

OWN=320000000
META=16000000
READ=10000000000
WRITE=512000000
FLOOR=20*1024**3

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
def module(body,name,path):
    m=types.ModuleType(name);m.__file__=str(path);sys.modules[name]=m;exec(compile(body,str(path),'exec'),m.__dict__);return m
def allocated(root):
    if not root.exists():return 0
    total=0
    for p in [root,*root.rglob('*')]:
        s=p.lstat();need(not stat.S_ISLNK(s.st_mode) and (stat.S_ISDIR(s.st_mode) or stat.S_ISREG(s.st_mode) and s.st_nlink==1),'ordinary owned tree')
        total+=max(s.st_size,s.st_blocks*512)
    return total

class Budget:
    def __init__(self,root,other,end,phase_roots=None,write_limit=WRITE,meta_limit=META):
        self.root=ordinary(root);self.roots=tuple(ordinary(p) for p in (phase_roots or (self.root,)))
        need(len(set(self.roots))==len(self.roots) and self.root in self.roots,'explicit unique shared phase roots')
        need(0<write_limit<=WRITE and 0<meta_limit<=META,'bounded actor allocation')
        self.write_limit=write_limit;self.meta_limit=meta_limit
        self.other=other;self.end=end;self.written=0;self.reads=0;self.meta=0;self.peak=0
    def tick(self):need(time.monotonic()<self.end,'whole normal deadline')
    def read(self,n):need(type(n)is int and 0<=n<=READ-self.reads,'controlled read reservation');self.reads+=n
    def guard(self,extra=0):
        self.tick();used=sum(allocated(p) for p in self.roots);self.peak=max(self.peak,used)
        need(used+extra<=OWN,'live phase cap');existing=next(p for p in (self.root,*self.root.parents) if p.exists());s=os.statvfs(existing)
        need(s.f_bavail*s.f_frsize>=FLOOR+self.other+max(0,OWN-used),'live physical reserve')
        return used
    def mkdir(self,path,mode=0o700):
        p=ordinary(path);need(p==self.root or p.is_relative_to(self.root),'owned directory')
        self.debit(8192,receipt=True);p.mkdir(mode=mode);sync(p.parent);self.tick()
    def check(self,n,receipt=False):
        need(type(n)is int and 0<=n<=self.write_limit-self.written,'write cap')
        if receipt:need(n<=self.meta_limit-self.meta,'metadata reserve')
        self.guard(n+8192)
    def debit(self,n,receipt=False):
        self.check(n,receipt);self.written+=n
        if receipt:self.meta+=n
    def write(self,path,body,receipt=False,mode=0o444,replace=False):
        p=ordinary(path);need(p.is_relative_to(self.root) and p!=self.root,'owned write');need(type(body)is bytes,'exact bytes')
        self.debit(len(body),receipt);pending=p.with_name('.'+p.name+'.pending')
        fd=os.open(pending,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        try:
            with os.fdopen(fd,'wb',closefd=False) as f:
                need(f.write(body)==len(body),'complete write');f.flush();os.fchmod(fd,mode);os.fsync(fd)
        finally:os.close(fd)
        self.tick()
        if replace:os.replace(pending,p)
        else:os.link(pending,p,follow_symlinks=False);pending.unlink()
        sync(p.parent);self.tick();return len(body)
    def save(self,path,value,cap=200000,replace=False):
        b=encoded(value);need(len(b)<=cap,'bounded metadata');self.write(path,b,receipt=True,replace=replace);return identity(b)
