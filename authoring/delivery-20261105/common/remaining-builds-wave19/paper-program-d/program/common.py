"""Bounded operator I/O; no scientific work on import."""
import hashlib,json,math,os,re,stat,time
from pathlib import Path
TASK='PAPER-FIND-050'
HEX=re.compile(r'[a-f0-9]{64}')

def need(ok,why):
    if not ok:raise ValueError(why)

def encode(x):return (json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def pin(b):return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def parse(b):
    def pairs(rows):
        d={}
        for k,v in rows:need(k not in d,'duplicate JSON member');d[k]=v
        return d
    return json.loads(b,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'nonfinite JSON'))
def descriptor(x):
    need(type(x)is dict and type(x.get('bytes'))is int and x['bytes']>=0 and type(x.get('sha256'))is str and HEX.fullmatch(x['sha256']),'exact byte/hash descriptor');return {k:x[k] for k in ('bytes','sha256')}
def ordinary(p):
    p=Path(p).absolute();need('..' not in p.parts and not any(q.is_symlink() for q in (p,*p.parents)),'ordinary owned path');return p

def sync(p):
    fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)

def identity(s):return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_nlink,s.st_mode)

class Budget:
    def __init__(self,limits,origin):
        required={'read_bytes','write_bytes','retained_bytes','other_future_bytes','free_floor_bytes','wall_seconds'}
        need(type(limits)is dict and set(limits)==required and all(type(v)is int and v>0 for k,v in limits.items() if k!='other_future_bytes') and type(limits['other_future_bytes'])is int and limits['other_future_bytes']>=0,'explicit complete resource limits')
        need(type(origin)in(int,float) and math.isfinite(origin) and 0<=origin<=time.monotonic(),'real original clock');self.origin=origin;self.end=origin+limits['wall_seconds'];self.limits=limits;self.read=0;self.write=0;self.retained=0
    def tick(self):need(time.monotonic()<self.end,'original whole-program deadline')
    def reading(self,n):self.tick();need(type(n)is int and n>=0,'read charge');self.read+=n;need(self.read<=self.limits['read_bytes'],'read ceiling')
    def writing(self,n):self.tick();need(type(n)is int and n>=0,'write charge');self.write+=n;self.retained+=n;need(self.write<=self.limits['write_bytes'] and self.retained<=self.limits['retained_bytes'],'write/retention ceiling')
    def reserve(self,path,n):
        self.tick();need(type(n)is int and n>=0,'prospective retained component');s=os.statvfs(ordinary(path));free=s.f_bavail*s.f_frsize
        need(free>=self.limits['free_floor_bytes']+self.limits['other_future_bytes']+n,'actual free space versus floor/OTHER/incremental component');return free
    def retire(self,n):need(type(n)is int and 0<=n<=self.retained,'retired exact allocation charge');self.retained-=n

def authority(path,expected_sha256,origin,limit_key='limits'):
    """Read at most 1 MiB + EOF probe before limits are known; carry charge forward.

    Startup failures report materialized bytes but cannot adopt untrusted limits.
    The complete successful operation retains the caller's original clock.
    """
    cap=1048576;used=0;fd=None
    try:
        need(type(origin)in(int,float) and math.isfinite(origin) and 0<=time.monotonic()-origin<120,'original bounded startup clock')
        need(type(expected_sha256)is str and HEX.fullmatch(expected_sha256),'expected authority hash')
        p=ordinary(path);fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);before=os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and 0<=before.st_size<=cap,'bounded ordinary authority before materialization')
        parts=[]
        while used<=cap:
            need(time.monotonic()-origin<120,'original startup read deadline');b=os.read(fd,min(65536,cap+1-used));used+=len(b)
            if not b:break
            parts.append(b)
        need(used<=cap and used==before.st_size and identity(before)==identity(os.fstat(fd))==identity(p.lstat()),'stable bounded authority and EOF');raw=b''.join(parts);need(hashlib.sha256(raw).hexdigest()==expected_sha256,'exact selected authority');v=parse(raw);budget=Budget(v[limit_key],origin);budget.reading(used);return raw,v,budget
    except BaseException as exc:
        raise ValueError(f'authority refused after {used} materialized bytes: {type(exc).__name__}: {exc}') from exc
    finally:
        if fd is not None:os.close(fd)

def authenticate_source(root,manifest,budget,required):
    """External authority pins the manifest; authenticate every source member."""
    raw=read(manifest['path'],manifest,budget,1048576);m=parse(raw)
    need(m['schema']=='critical_init_program_source_v1' and m['task_id']==TASK and type(m['files'])is dict and 1<=len(m['files'])<=128 and set(required)<=set(m['files']),'complete exact runtime source dependencies')
    root=ordinary(root);bodies={}
    for name,d in m['files'].items():
        need(type(name)is str and name and not Path(name).is_absolute() and '..'not in Path(name).parts,'relative source member')
        bodies[name]=read(root/name,d,budget,16777216)
    return bodies,descriptor(manifest)

def read(path,expected,budget,cap,retain=True):
    p=ordinary(path);d=descriptor(expected);need(d['bytes']<=cap,'bounded expected input');budget.reading(d['bytes']+1)
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd);need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==d['bytes'],'ordinary exact input');h=hashlib.sha256();chunks=[];left=d['bytes']
        while left:
            budget.tick();b=os.read(fd,min(left,1048576));need(bool(b),'complete source');left-=len(b);h.update(b)
            if retain:chunks.append(b)
        need(not os.read(fd,1) and h.hexdigest()==d['sha256'] and identity(before)==identity(os.fstat(fd))==identity(p.lstat()),'exact stable input and EOF')
        return b''.join(chunks) if retain else d
    finally:os.close(fd)

def write(path,b,budget,readonly=True):
    p=ordinary(path);need(type(b)is bytes,'encoded bytes');p.parent.mkdir(parents=True,exist_ok=True,mode=0o700);budget.reserve(p.parent,len(b)+8192);budget.writing(len(b)+8192)
    fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400)
    try:
        v=memoryview(b)
        while v:n=os.write(fd,v);need(n>0,'complete owned write');v=v[n:]
        os.fchmod(fd,0o444 if readonly else 0o600);os.fsync(fd)
    finally:os.close(fd)
    sync(p.parent);budget.tick();return pin(b)

def copy(path,target,expected,budget):
    p=ordinary(path);q=ordinary(target);d=descriptor(expected);budget.reserve(q.parent,d['bytes']+8192);budget.reading(d['bytes']+1);budget.writing(d['bytes']+8192)
    src=dst=None
    try:
        src=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);s=os.fstat(src);need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_size==d['bytes'],'exact source copy');dst=os.open(q,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400);left=d['bytes'];h=hashlib.sha256()
        while left:
            budget.tick();b=os.read(src,min(left,1048576));need(b,'copy EOF');left-=len(b);h.update(b);v=memoryview(b)
            while v:n=os.write(dst,v);need(n>0,'copy write');v=v[n:]
        need(not os.read(src,1) and h.hexdigest()==d['sha256'] and identity(s)==identity(os.fstat(src))==identity(p.lstat()),'stable authenticated copy');os.fchmod(dst,0o444);os.fsync(dst)
    finally:
        if src is not None:os.close(src)
        if dst is not None:os.close(dst)
    sync(q.parent);return d

def captured(path,budget,cap):
    p=ordinary(path);s=p.lstat();need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and 0<=s.st_size<=cap,'bounded regular output');budget.reading(s.st_size+1);h=hashlib.sha256();fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        need(identity(s)==identity(os.fstat(fd)),'capture identity');left=s.st_size
        while left:b=os.read(fd,min(left,1048576));need(b,'capture EOF');left-=len(b);h.update(b);budget.tick()
        need(not os.read(fd,1) and identity(s)==identity(os.fstat(fd))==identity(p.lstat()),'stable capture');os.fchmod(fd,0o444);os.fsync(fd)
    finally:os.close(fd)
    sync(p.parent);return {'bytes':s.st_size,'sha256':h.hexdigest()}
