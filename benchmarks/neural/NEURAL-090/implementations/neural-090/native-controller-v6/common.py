"""NEURAL-090 ordinary custody and selected managed transfers, not syscall quotas."""
import hashlib,json,os,stat,time
from pathlib import Path

def need(ok,message):
    if not ok:raise ValueError(message)
def integer(n,minimum=0):need(type(n)is int and n>=minimum,'selected exact finite integer');return n
def encoded(v):return (json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def parse(raw):
    def pairs(rows):
        out={}
        for k,v in rows:need(k not in out,'duplicate JSON member');out[k]=v
        return out
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'nonfinite JSON'))
def pin(raw):return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
def fields(v,names):need(type(v)is dict and set(v)==set(names),'exact '+','.join(names));return v
def regular_path(p):
    p=Path(p).absolute();need('..'not in p.parts and all(not x.is_symlink() for x in(p,*p.parents)),'ordinary literal path');return p
def stamp(s):return(s.st_dev,s.st_ino,s.st_mode,s.st_nlink,s.st_size,s.st_uid,s.st_gid,s.st_mtime_ns,s.st_ctime_ns)
class Failure(RuntimeError):
    def __init__(self,first,events,record=None):
        self.first=first;self.events=tuple(events);self.record=record
        super().__init__('NEURAL-090 actual operation failed; raw first and secondary retained')
class Ledger:
    def __init__(self):self.events=[]
    def record(self,where,e):self.events.append((where,e))
    def attempt(self,where,f):
        try:return f()
        except BaseException as e:self.record(where,e)
    def raise_first(self,record=None):
        if self.events:raise Failure(self.events[0][1],self.events,record) from self.events[0][1]
    def metadata(self):return [{'where':w,'type':type(e).__name__,'message':str(e)[:1024]}for w,e in self.events]
class Budget:
    def __init__(self,reads,writes,end):
        self.read_limit=integer(reads,1);self.write_limit=integer(writes,1);self.end=end;self.reads=self.writes=0
    def tick(self):need(time.monotonic()<self.end,'original operation deadline')
    def read(self,n):
        integer(n);need(self.reads+n<=self.read_limit,'managed read reservation ceiling');self.reads+=n;self.tick()
    def write(self,n):
        integer(n);need(self.writes+n<=self.write_limit,'managed write reservation ceiling');self.writes+=n;self.tick()
    def report(self):return {'read_reserved':self.reads,'write_reserved':self.writes,'scope':'managed source/view/output/protocol transfers; excludes kernel, allocator and native syscall bytes'}
def capture(p,budget,cap,expected=None):
    p=regular_path(p);budget.tick();fd=None;raw=bytearray();errors=Ledger()
    try:
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);a=os.fstat(fd)
        need(stat.S_ISREG(a.st_mode)and a.st_nlink==1 and 0<=a.st_size<=cap,'bounded single-link ordinary member')
        budget.read(a.st_size+1)
        while len(raw)<=a.st_size:
            budget.tick();part=os.read(fd,min(65536,a.st_size+1-len(raw)))
            if not part:break
            raw.extend(part)
        need(len(raw)==a.st_size and stamp(a)==stamp(os.fstat(fd))==stamp(p.lstat()),'complete stable ordinary capture')
        need(expected is None or pin(raw)==expected,'selected whole content identity')
    except BaseException as e:errors.record('capture',e)
    finally:
        if fd is not None:errors.attempt('capture-close',lambda:os.close(fd))
    errors.raise_first({'path':str(p),'consumed_prefix':bytes(raw)});return bytes(raw)
def save(p,raw,budget,mode=0o400):
    p=regular_path(p);need(type(raw)is bytes,'exact bytes');budget.write(len(raw));fd=None;errors=Ledger()
    try:
        fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode);offset=0
        while offset<len(raw):
            budget.tick();n=os.write(fd,raw[offset:]);need(n>0,'complete fresh write');offset+=n
        os.fsync(fd)
    except BaseException as e:errors.record('save',e)
    finally:
        if fd is not None:errors.attempt('save-close',lambda:os.close(fd))
    errors.raise_first({'path':str(p),'intended_bytes':len(raw)});return pin(raw)
def private_directory(p):
    p=regular_path(p);s=p.stat();need(stat.S_ISDIR(s.st_mode)and s.st_uid==os.getuid()and stat.S_IMODE(s.st_mode)==0o700,'owned private directory');return p

def kernel_body(p,budget,cap):
    budget.read(cap+1);fd=None;raw=bytearray();errors=Ledger()
    try:
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
        while len(raw)<=cap:
            budget.tick();part=os.read(fd,min(65536,cap+1-len(raw)))
            if not part:break
            raw.extend(part)
        need(len(raw)<=cap,'bounded kernel metadata body')
    except BaseException as e:errors.record('kernel-read',e)
    finally:
        if fd is not None:errors.attempt('kernel-close',lambda:os.close(fd))
    errors.raise_first({'path':str(p),'prefix':bytes(raw)});return bytes(raw)

def bounded_names(path,cap,budget):
    """Return captured names and every raw inventory/close error independently."""
    iterator=None;names=[];errors=Ledger()
    try:
        iterator=os.scandir(path)
        for item in iterator:
            need(len(names)<cap,'finite complete name inventory plus refused probe')
            budget.read(len(item.name.encode())+1);names.append(item.name)
    except BaseException as error:errors.record('name-inventory',error)
    finally:
        if iterator is not None:errors.attempt('name-inventory-close',iterator.close)
    return names,errors

def admit_placement(path,expected_group,identity,record,budget):
    value=parse(capture(path,budget,16384))
    fields(value,('schema','pid','cgroup','identity','moved','readback','descriptor_closure_known','first','secondary','kernel_prefix_base64'))
    need(value['schema']=='n090-actual-placement-v1'and type(value['pid'])is int and value['pid']==record['pid'],'same actual owned leader placement')
    need(value['cgroup']==str(expected_group)and value['identity']==list(identity)and value['readback']=='0::/'+str(Path(expected_group).relative_to('/sys/fs/cgroup')),'exact observed selected cgroup join')
    need(value['moved']is True and value['descriptor_closure_known']is True and value['first']is None and value['secondary']==[],'actual error-free placement before exec')
    return value
