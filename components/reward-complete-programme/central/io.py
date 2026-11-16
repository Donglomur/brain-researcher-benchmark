"""Bounded ordinary-file custody and whole-attempt resource observations."""
from pathlib import Path
import hashlib,json,math,os,stat,time

class Refusal(ValueError):pass
def need(value,message):
    if not value:raise Refusal(message)
def encode(value):return (json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)+'\n').encode()
def sha(body):return hashlib.sha256(body).hexdigest()
def digest(value):return sha(encode(value))
def decode(body):
    def pairs(items):
        out={}
        for k,v in items:
            need(k not in out,'duplicate JSON key');out[k]=v
        return out
    def constant(x):raise Refusal('nonfinite JSON constant')
    return json.loads(body,object_pairs_hook=pairs,parse_constant=constant)
def positive(x):return type(x) in (int,float) and math.isfinite(x) and x>0
def ordinary(path,exists=True):
    p=Path(path).absolute()
    need(not any(q.is_symlink() for q in (p,*p.parents)),'symlink in namespace')
    if exists:
        s=p.stat();need(stat.S_ISREG(s.st_mode) and s.st_nlink==1,'ordinary single-link file required')
    return p
def capture(path,pin=None,cap=8<<20):
    p=ordinary(path);before=p.stat();need(before.st_size<=cap,'read cap')
    body=p.read_bytes();after=p.stat()
    need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns),'file changed during capture')
    need(len(body)<=cap,'read cap')
    if pin is not None:need(type(pin['bytes']) is int and len(body)==pin['bytes'] and sha(body)==pin['sha256'],'exact file pin')
    return body
def pin(path):
    b=capture(path);return {'bytes':len(b),'sha256':sha(b)}
def relative(root,name):
    need(isinstance(name,str) and name and not Path(name).is_absolute() and '..' not in Path(name).parts and '\\' not in name and Path(name).as_posix()==name,'canonical relative member')
    return Path(root)/name

class Budget:
    def __init__(self,limits,started=None,cpu=None):
        required={'wall_seconds','cpu_seconds','read_bytes','write_bytes','retained_bytes','files','output_bytes','candidate_seconds'}
        need(set(limits)==required and all(positive(v) for v in limits.values()),'complete positive resource envelope')
        need(all(type(limits[k]) is int for k in required-{'wall_seconds','cpu_seconds','candidate_seconds'}),'integer byte/file limits')
        self.limits=limits;self.start=started or time.monotonic();self.cpu=cpu or time.process_time();self.reads=0;self.writes=0;self.readset=[];self.peak_bytes=0;self.peak_files=0
    def guard(self,root=None):
        need(time.monotonic()-self.start<=self.limits['wall_seconds'],'whole-attempt wall budget')
        need(time.process_time()-self.cpu<=self.limits['cpu_seconds'],'controller CPU budget')
        need(self.reads<=self.limits['read_bytes'] and self.writes<=self.limits['write_bytes'],'logical I/O budget')
        if root is not None:
            count=size=0
            for p in Path(root).rglob('*'):
                need(not p.is_symlink(),'output symlink')
                if p.is_file():
                    ordinary(p);count+=1;size+=p.stat().st_size
            self.peak_bytes=max(self.peak_bytes,size);self.peak_files=max(self.peak_files,count)
            need(size<=self.limits['retained_bytes'] and count<=self.limits['files'],'retained output budget')
    def read(self,path,pin=None,cap=8<<20):
        self.guard();s=ordinary(path).stat().st_size;need(self.reads+s<=self.limits['read_bytes'],'pre-read reservation')
        b=capture(path,pin,cap);self.reads+=len(b);self.readset.append({'path':str(Path(path).absolute()),'bytes':len(b),'sha256':sha(b)});self.guard();return b
    def write(self,path,value):
        return self.write_raw(path,encode(value))
    def write_raw(self,path,b):
        need(type(b) is bytes and self.writes+len(b)<=self.limits['write_bytes'],'pre-write reservation')
        p=ordinary(path,False);p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as f:f.write(b)
        self.writes+=len(b);self.guard();return {'path':str(p),'bytes':len(b),'sha256':sha(b)}
    def reserve_time(self,seconds):
        self.guard();need(time.monotonic()-self.start+seconds+1<self.limits['wall_seconds'],'remaining whole-attempt clock')
    def snapshot(self):return {'logical_read_bytes':self.reads,'logical_controller_write_bytes':self.writes,'observed_retained_peak_bytes':self.peak_bytes,'observed_retained_peak_files':self.peak_files,'wall_seconds':time.monotonic()-self.start,'controller_cpu_seconds':time.process_time()-self.cpu,'physical_OS_IO_RSS_and_transient_child_peak_measured':False}
