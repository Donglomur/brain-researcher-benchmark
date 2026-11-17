"""Bounded NEURAL100 host custody; no neural-array interpretation."""
import hashlib,json,math,os,re,shutil,stat,time,types
from pathlib import Path
TASK="NEURAL-100"
CASES=tuple(range(47))
FLOOR=21474836480
RETAIN=512000000
READS=1500000000
WRITES=160000000
def need(ok,message):
    if not ok:raise ValueError(message)

def validate_natural_exit(value):
    """Exact selected Docker exit-state projection; JSON numeric equality is insufficient."""
    fields={'Status','Running','Dead','Pid','ExitCode','OOMKilled'}
    need(type(value)is dict and set(value)==fields,'exact natural exit fields')
    need(type(value['Status'])is str and value['Status']=='exited','natural exited status')
    for name in ('Running','Dead','OOMKilled'):
        need(value[name] is False,'strict stopped non-OOM state')
    for name in ('Pid','ExitCode'):
        need(type(value[name])is int and value[name]==0,'strict natural integer zero')
    return value

def pin(raw):return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def encoded(v):return (json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()

def parse(raw):
    def pairs(rows):
        out={}
        for key,value in rows:need(key not in out,'duplicate JSON key');out[key]=value
        return out
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'nonfinite JSON'))

def exact_pin(p):
    need(type(p)is dict and set(p)=={'bytes','sha256'} and type(p['bytes'])is int and 0<p['bytes']<=100000000 and type(p['sha256'])is str and re.fullmatch('[0-9a-f]{64}',p['sha256']),'exact content pin')
    return p

def only_pin(p):return exact_pin({k:p[k] for k in ('bytes','sha256')})

def path(p):
    p=Path(p).absolute()
    need('..' not in p.parts and not any(x.is_symlink() for x in (p,*p.parents)) and not any(x in str(p) for x in (',','\0','\n','\r')),'ordinary canonical path')
    return p

def before(deadline):need(time.monotonic()<deadline,'original deadline')

def stamp(s):return tuple(getattr(s,k) for k in ('st_dev','st_ino','st_mode','st_nlink','st_size','st_uid','st_gid','st_mtime_ns','st_ctime_ns'))

def capture(p,cap,expected=None,tick=lambda:None,charge=lambda n:None):
    tick();p=path(p);fd=os.open(p,os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW)
    try:
        a=os.fstat(fd);need(stat.S_ISREG(a.st_mode) and a.st_nlink==1 and 0<a.st_size<=cap,'bounded ordinary file')
        charge(a.st_size+1);tick();chunks=[];remaining=a.st_size+1
        while remaining:
            tick();b=os.read(fd,min(65536,remaining));tick()
            if not b:break
            chunks.append(b);remaining-=len(b)
        raw=b''.join(chunks);need(len(raw)==a.st_size and stamp(a)==stamp(os.fstat(fd))==stamp(p.lstat()),'stable complete capture')
    finally:os.close(fd)
    tick();need(expected is None or pin(raw)==exact_pin(expected),'content identity');return raw

def inventory(root,cap=RETAIN,max_entries=15000):
    root=path(root);todo=[root];files={};dirs=[];usage=0;count=0
    while todo:
        p=todo.pop();s=p.lstat();count+=1;need(count<=max_entries,'bounded inventory')
        need(stat.S_ISDIR(s.st_mode) or stat.S_ISREG(s.st_mode) and s.st_nlink==1,'ordinary owned tree')
        usage+=max(s.st_size,s.st_blocks*512);need(usage<=cap,'owned allocation ceiling')
        if stat.S_ISDIR(s.st_mode):
            dirs.append(p)
            with os.scandir(p) as it:
                for row in it:need(count+len(todo)<max_entries,'bounded enumeration');todo.append(p/row.name)
        else:files[p.relative_to(root).as_posix()]=(p,stamp(s))
    return files,dirs,usage

def sync_dir(directory,tick=lambda:None):
    tick();fd=os.open(path(directory),os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:tick();os.fsync(fd);tick()
    finally:os.close(fd)

def save(p,raw,cap,tick=lambda:None,charge=lambda n:None):
    need(type(raw)is bytes and 0<len(raw)<=cap,'bounded publication');p=path(p)
    charge(len(raw));tick();fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400)
    try:
        view=memoryview(raw)
        while view:tick();n=os.write(fd,view);need(n>0,'complete write');view=view[n:]
        tick();os.fsync(fd);tick()
    finally:os.close(fd)
    sync_dir(p.parent,tick);return pin(raw)

class Budget:
    def __init__(self, root, other, end):
        need(type(other) is int and other >= 0, 'current OTHER')
        self.root=path(root);self.other=other;self.end=end
        self.reads=0;self.writes=0;self.phases=[]
    def tick(self):before(self.end)
    def read(self,n):
        need(type(n) is int and n>=0 and self.reads+n<=READS,'managed read reservation')
        self.reads+=n;self.tick()
    def capacity(self,extra=0):
        self.tick();used=inventory(self.root,RETAIN,2000)[2] if self.root.exists() else 0
        need(used+extra<=RETAIN,'full-panel allocation cap')
        where=self.root if self.root.exists() else self.root.parent
        st=os.statvfs(where);need(st.f_frsize<=4096,'bounded allocation granularity')
        need(shutil.disk_usage(where).free>=FLOOR+self.other+RETAIN-used,'original remaining custody')
        self.tick();return used
    def write(self,n):
        need(type(n) is int and n>=0 and self.writes+n<=WRITES,'managed write cap')
        self.capacity(((n+4095)//4096)*4096+16384);self.writes+=n
    def native(self,case):
        # Preventively charge bounded CLI responses, not physical candidate I/O.
        self.read(130000000);self.phases.append(case)
    def record(self):
        return dict(read_reservations=self.reads,write_reservations=self.writes,
                    native_cases_reserved=list(self.phases),physical_IO_measured=False,
                    failed_and_retired_costs_retained=True)

def load(source, expected, deadline):
    """Authenticate every local member before compiling any local runtime code."""
    raw=capture(source,65536,exact_pin(expected),lambda:before(deadline));m=parse(raw)
    need(set(m)=={'schema','files'} and m['schema']=='neural100_full47_program_source_v1','source schema')
    need(type(m['files']) is dict and len(m['files'])<=16,'bounded source member count')
    bodies={};total=len(raw)+1
    for name,p in m['files'].items():
        need(type(name) is str and Path(name).name==name,'local source basename')
        need(exact_pin(p)['bytes']<=1000000,'member source cap')
        total+=p['bytes']+1;need(total<=1000000,'source read cap')
        bodies[name]=capture(Path(source).parent/name,p['bytes'],p,lambda:before(deadline))
    return m,bodies,total

def module(bodies,name,here,**bindings):
    m=types.ModuleType('neural100_'+name.replace('.','_'));m.__file__=str(here/name)
    m.__dict__.update(bindings);exec(compile(bodies[name],m.__file__,'exec'),m.__dict__)
    return m

def readable(p,tick):
    tick();fd=os.open(path(p),os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:os.fchmod(fd,0o444);os.fsync(fd);tick()
    finally:os.close(fd)
    sync_dir(Path(p).parent,tick)
