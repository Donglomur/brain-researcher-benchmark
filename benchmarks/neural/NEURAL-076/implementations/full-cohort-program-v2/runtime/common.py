"""Bounded source/metadata I/O and full650 resource accounting; no data on import."""
import hashlib,json,math,os,re,stat,time
from pathlib import Path
PEOPLE=tuple('Subject'+str(i)for i in range(1,6))
ROIS=('V1','V2','V3','V4','LOC','FFA','PPA','LVC','HVC','VC')
FAMILIES=tuple('cnn'+str(i)for i in range(1,9))+('hmax1','hmax2','hmax3','gist','sift')
KEYS=tuple(f'{p}/{r}/{f}'for p in PEOPLE for r in ROIS for f in FAMILIES)
MIB=2**20;PRED=24*MIB;VIEW=256*MIB;PHASE=26*MIB;RETAIN=19*2**30;FLOOR=20*2**30
READS=2_000_000_000_000;WRITES=256_000_000_000
FILES={'training.npz','queries.npz','bank.npz','context.json','COMPLETE.json'}

def need(ok,message='NEURAL076 fixed boundary'):
    if not ok:raise ValueError(message)
def before(end):need(type(end)in(int,float)and math.isfinite(end)and time.monotonic()<end,'original deadline')
def short(b):return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def encode(d):return (json.dumps(d,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def decode(b):
    def pairs(rows):
        d={}
        for k,v in rows:need(k not in d,'duplicate key');d[k]=v
        return d
    def num(s):
        v=float(s);need(math.isfinite(v),'nonfinite number');return v
    return json.loads(b.decode('utf-8'),object_pairs_hook=pairs,parse_float=num,parse_constant=lambda _:need(False,'nonfinite constant'))
def path(p):
    p=Path(p).absolute();need('..'not in p.parts and not any(x.is_symlink()for x in(p,*p.parents)),'canonical ordinary path');need(not any(c in str(p)for c in ',\n\r\0'),'mount path');return p
def identity(s):return tuple(getattr(s,k)for k in('st_dev','st_ino','st_mode','st_size','st_nlink','st_mtime_ns','st_ctime_ns'))
def capture(p,cap,pin=None,body=True,tick=lambda:None):
    p=path(p);tick();fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        a=os.fstat(fd);need(stat.S_ISREG(a.st_mode)and a.st_nlink==1 and 0<a.st_size<=cap,'bounded ordinary file')
        h=hashlib.sha256();parts=[];n=0
        while n<a.st_size:
            tick();b=os.read(fd,min(MIB,a.st_size-n));need(b,'complete read');h.update(b);n+=len(b)
            if body:parts.append(b)
        need(not os.read(fd,1)and identity(a)==identity(os.fstat(fd))==identity(p.lstat()),'stable exact capture')
    finally:os.close(fd)
    seen={'bytes':n,'sha256':h.hexdigest()};need(pin is None or seen=={k:pin[k]for k in('bytes','sha256')},'exact pin');tick();return (b''.join(parts)if body else None),seen

def inventory(root,limit=24000):
    root=path(root);todo=[root]if os.path.lexists(root)else[];files={};dirs=[];used=0;dev=root.parent.stat().st_dev;count=0
    while todo:
        p=todo.pop();s=p.lstat();count+=1;need(count<=limit and s.st_dev==dev,'bounded same-filesystem tree');used+=max(s.st_size,s.st_blocks*512)
        if stat.S_ISDIR(s.st_mode):
            dirs.append(p)
            with os.scandir(p)as it:
                for x in it:need(count+len(todo)<limit,'bounded tree');todo.append(p/x.name)
        else:need(stat.S_ISREG(s.st_mode)and s.st_nlink==1,'ordinary single-link tree');files[p.relative_to(root).as_posix()]=(p,identity(s))
    return files,dirs,used

def syncdir(p):
    fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
def write(p,b,cap):
    p=path(p);need(type(b)is bytes and 0<len(b)<=cap,'bounded write');fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o444)
    try:
        off=0
        while off<len(b):n=os.write(fd,b[off:]);need(n>0,'short write');off+=n
        os.fsync(fd)
    finally:os.close(fd)
    syncdir(p.parent);return short(b)

class Budget:
    def __init__(self,root,other,end):
        self.root=path(root);self.other=other;self.end=end;self.reads=0;self.writes=0;self.serial=0
        need(type(other)is int and other>=0,'current OTHER')
    def tick(self):before(self.end)
    def check(self,extra=0):
        self.tick();used=inventory(self.root)[2];need(used+extra<=RETAIN,'whole retained allowance')
        fs=os.statvfs(self.root.parent);need(fs.f_bavail*fs.f_frsize>=FLOOR+self.other+max(0,RETAIN-used),'complete remaining allowance')
    def charge(self,kind,key,reads,writes):
        self.check();need(self.reads+reads<=READS and self.writes+writes<=WRITES,'whole cumulative traffic')
        self.reads+=reads;self.writes+=writes;self.serial+=1
        self.save(self.root/'traffic'/f'{self.serial:04d}.json',{'phase':kind,'key':key,'reserved_read_bytes':reads,'reserved_write_bytes':writes,'cumulative_reads':self.reads,'cumulative_writes':self.writes,'refunded':False},8192)
    def save(self,p,d,cap):
        b=encode(d);self.check(len(b)+65536);need(self.writes+len(b)<=WRITES,'metadata cumulative write');self.writes+=len(b);v=write(p,b,cap);self.tick();return v
    def mkdir(self,p,mode=0o700):
        self.check(65536);p=path(p);need(p==self.root or self.root in p.parents,'owned directory');p.mkdir(mode=mode);syncdir(p.parent);self.writes+=65536
    def other_for_phase(self,phase_cap):
        used=inventory(self.root)[2];return self.other+max(0,RETAIN-used-phase_cap)
    def record(self):return {'read_reservations':self.reads,'write_charges_and_reservations':self.writes,'phase_count':self.serial,'retained_cap':RETAIN,'no_refunds':True}
