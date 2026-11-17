"""Bounded metadata custody, first/later failures and inherited clocks."""
import hashlib,json,math,os,stat,time
from pathlib import Path

def need(value,message):
    if not value:raise ValueError(message)
def integer(x,minimum=0):
    need(type(x)is int and x>=minimum,'ordinary bounded integer');return x
def finite(x):
    need(type(x)in(int,float)and math.isfinite(x),'finite ordinary clock');return float(x)
def encode(x):return (json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def parse(raw):
    def pairs(rows):
        out={}
        for k,v in rows:need(k not in out,'duplicate key');out[k]=v
        return out
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'nonfinite metadata'))
def pin(raw):return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
def only_pin(x):
    need(type(x)is dict,'pin object');n=integer(x['bytes']);h=x['sha256']
    need(type(h)is str and len(h)==64 and all(c in '0123456789abcdef'for c in h),'SHA256 pin')
    return {'bytes':n,'sha256':h}
def path(x):
    raw=str(x);p=Path(raw)
    need(raw.startswith('/')and not raw.startswith('//')and str(p)==raw and '\\'not in raw and '\0'not in raw
         and '..'not in p.parts and (raw=='/'or all(z not in('','.','..')for z in raw.split('/')[1:])),'canonical absolute path')
    return p
def parents(p):
    p=path(p)
    for q in reversed(p.parents):need(stat.S_ISDIR(os.lstat(q).st_mode),'ordinary nonsymlink parents')
    return p
def disjoint(a,b):
    a=path(a);b=path(b);return a!=b and a not in b.parents and b not in a.parents
def stamp(s):return tuple(getattr(s,k)for k in('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns'))
def close(fd):
    import sys
    first=sys.exception()
    try:os.close(fd)
    except BaseException as later:
        if first is not None:raise BaseExceptionGroup('operation and independent close',[first,later])from None
        raise
class Host:
    def __init__(self,entry_start):
        self.entry_start=finite(entry_start);self.origin=self.entry_start;self.deadline=self.origin+120
        self.read_cap=512*1048576;self.write_cap=4*1048576;self.reads=self.writes=0;self.root=None;self.prepared=False
        self.unknown_setup=False;self.limit_establishment={'attempted':False,'syscall_returned':False,'clock_closed':False,'state_unknown':False};self.protected=();self.clock=time.monotonic
    def tick(self):
        now=finite(self.clock());need(self.origin<=now<self.deadline,'original central clock');return now
    def reserve(self,n):
        self.tick();n=integer(n);need(self.reads+n<=self.read_cap,'central read cap');self.reads+=n
    def reserve_read(self,n):return self.reserve(n)
    @property
    def read_bytes(self):return self.reads
    @property
    def write_bytes(self):return self.writes
    def reserve_write(self,n):
        self.tick();n=integer(n);need(self.writes+n<=self.write_cap,'central write cap');self.writes+=n
    def record(self):return {'origin':self.origin,'entry_start':self.entry_start,'deadline':self.deadline,'read_reserved':self.reads,'write_reserved':self.writes,'read_cap':self.read_cap,'write_cap':self.write_cap,'root_setup_returned':self.prepared,'limit_establishment':dict(self.limit_establishment),'uncertain_setup':self.unknown_setup,'physical_io_unmeasured':True,'snapshot_precedes_publication':True}
    def admit_path(self,p):
        p=path(p);need(all(p!=q and q not in p.parents for q in self.protected),'private/secrets operands excluded before open');return p
    def read(self,p,cap,expected=None,readonly=False,retain=True):
        p=parents(self.admit_path(p));self.tick();integer(cap,1)
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            a=os.fstat(fd);need(stat.S_ISREG(a.st_mode)and a.st_nlink==1 and 0<=a.st_size<=cap,'ordinary bounded single-link metadata')
            if expected is not None:need(a.st_size==only_pin(expected)['bytes'],'exact extent')
            if readonly:need(a.st_mode&0o222==0,'sealed readonly metadata')
            self.reserve(a.st_size+1);left=a.st_size;parts=[];h=hashlib.sha256()
            while left:
                self.tick();b=os.read(fd,min(left,65536));need(b,'short capture');left-=len(b);h.update(b)
                if retain:parts.append(b)
            need(not os.read(fd,1),'overflow sentinel');need(stamp(a)==stamp(os.fstat(fd))==stamp(os.lstat(p)),'same-open/current-name custody')
            got={'bytes':a.st_size,'sha256':h.hexdigest()}
            if expected is not None:need(got==only_pin(expected),'exact body pin')
        finally:close(fd)
        need(stamp(a)==stamp(os.lstat(p)),'postclose current name');self.tick()
        return b''.join(parts)if retain else got
    def sync(self,p):
        fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:os.fsync(fd)
        finally:close(fd)
        self.tick()
    def prepare(self,p,required_free):
        import shutil
        p=parents(self.admit_path(p));self.tick();need(not os.path.lexists(p),'fresh output only')
        need(shutil.disk_usage(p.parent).free>=integer(required_free),'selected parent+central+other storage')
        self.unknown_setup=True;os.mkdir(p,0o700);self.sync(p.parent);self.root=p;self.prepared=True;self.unknown_setup=False
    def save(self,name,value,cap=131072):
        need(self.prepared and name in('INTENT.json','CAMPAIGN.json','CALLER.json','RESULT.json','FAILED.json','caller.stdout','caller.stderr',
                                      'failure.stdout','failure.stderr','FAILURE_CALLER.json'),'owned fixed publication')
        raw=value if type(value)is bytes else encode(value);need(len(raw)<=integer(cap,1),'publication bound')
        p=parents(self.root/name);self.reserve_write(len(raw));fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        try:
            a=os.fstat(fd);view=memoryview(raw)
            while view:self.tick();n=os.write(fd,view);need(n>0,'short write');view=view[n:]
            os.fchmod(fd,0o444);os.fsync(fd);z=os.fstat(fd);need(z.st_ino==a.st_ino and z.st_dev==a.st_dev and z.st_nlink==1 and z.st_size==len(raw),'published FD custody')
            need(stamp(z)==stamp(os.lstat(p)),'published name')
        finally:close(fd)
        self.sync(p.parent);need(stamp(z)==stamp(os.lstat(p)),'durable name');result=pin(raw);self.tick();return result
