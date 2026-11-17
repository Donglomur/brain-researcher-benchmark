"""Bounded NEURAL083 host custody; no neural-array interpretation."""
import hashlib,json,math,os,re,shutil,stat,time,types
from pathlib import Path
TASK="NEURAL-083"
FLOOR=2147483648
RETAIN=32000000
READS=700000000
WRITES=64000000
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

def validate_cli_commands(rows,reply_cap):
    """Admit only complete, timely, source-compatible command closure evidence."""
    fields={'phase','returncode','error_type','observed_retained_bytes','seconds',
            'client_reaped','cleanup_complete','cleanup_before_original_cutoff',
            'owned_group_absence_observed','leader_exited_with_group_alive',
            'group_probe_or_cleanup_error'}
    if type(rows)is not list or not 1<=len(rows)<=64:raise ValueError('bounded complete CLI evidence')
    for row in rows:
        if type(row)is not dict or set(row)!=fields:raise ValueError('exact CLI evidence fields')
        if type(row['returncode'])is not int or row['returncode']!=0:raise ValueError('natural CLI zero')
        if row['error_type'] is not None or row['group_probe_or_cleanup_error'] is not None:raise ValueError('error-free CLI closure')
        for name in ('client_reaped','cleanup_complete','cleanup_before_original_cutoff','owned_group_absence_observed'):
            if row[name] is not True:raise ValueError('strict complete timely CLI closure')
        if row['leader_exited_with_group_alive'] is not False:raise ValueError('no surviving CLI descendants')
        if type(row['phase'])is not str or not 1<=len(row['phase'].encode('utf-8'))<=128:raise ValueError('bounded CLI phase')
        if type(row['observed_retained_bytes'])is not int or not 0<=row['observed_retained_bytes']<=reply_cap:raise ValueError('bounded CLI retained bytes')
        seconds=row['seconds']
        try:finite=type(seconds)in(int,float) and seconds>=0 and math.isfinite(seconds)
        except OverflowError:finite=False
        if not finite:raise ValueError('finite nonnegative CLI duration')

def pin(raw):return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def encoded(v):return (json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()

def parse(raw):
    def pairs(rows):
        out={}
        for key,value in rows:need(key not in out,'duplicate JSON key');out[key]=value
        return out
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'nonfinite JSON'))

def exact_pin(p):
    need(type(p)is dict and set(p)=={'bytes','sha256'} and type(p['bytes'])is int and 0<p['bytes']<=12000000000 and type(p['sha256'])is str and re.fullmatch('[0-9a-f]{64}',p['sha256']),'exact content pin')
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
    def __init__(self,root,other,end,limits):
        need(type(other)is int and other>=0,'fresh OTHER')
        self.root=path(root);self.other=other;self.end=end;self.limits=limits
        self.reads=0;self.writes=0;self.phases=[]
    def tick(self):before(self.end)
    def read(self,n):
        need(type(n)is int and n>=0 and self.reads+n<=self.limits['reads'],'whole managed read allowance')
        self.reads+=n;self.tick()
    def capacity(self,extra=0):
        self.tick();cap=self.limits['retained'];used=inventory(self.root,cap,500000)[2] if self.root.exists() else 0
        need(used+extra<=cap,'whole retained allocation allowance')
        where=self.root if self.root.exists() else self.root.parent
        need(os.statvfs(where).f_frsize<=4096,'bounded allocation granularity')
        need(shutil.disk_usage(where).free>=self.limits['free_floor_bytes']+self.other+cap-used,'fresh physical floor and remaining allowance')
        self.tick();return used
    def write(self,n):
        need(type(n)is int and n>=0 and self.writes+n<=self.limits['writes'],'whole cumulative writes')
        self.capacity(((n+4095)//4096)*4096+16384);self.writes+=n
    def native(self,kind,ordinal):
        amount=1000000000 if kind=='fit' else 16000000
        self.read(amount);self.phases.append({'kind':kind,'ordinal':ordinal,'reserved':amount})
    def record(self):
        return dict(read_reservations=self.reads,write_reservations=self.writes,native_phases=list(self.phases),physical_IO_measured=False,failed_and_retired_costs_retained=True)

def load(source, expected, deadline):
    """Authenticate every local member before compiling any local runtime code."""
    raw=capture(source,65536,exact_pin(expected),lambda:before(deadline));m=parse(raw)
    need(set(m)=={'schema','files'} and m['schema']=='neural083_full_program_source_v1','source schema')
    need(type(m['files']) is dict and len(m['files'])<=30,'bounded source member count')
    bodies={};total=len(raw)+1
    for name,p in m['files'].items():
        need(type(name) is str and Path(name).name==name,'local source basename')
        need(exact_pin(p)['bytes']<=1000000,'member source cap')
        total+=p['bytes']+1;need(total<=1000000,'source read cap')
        bodies[name]=capture(Path(source).parent/name,p['bytes'],p,lambda:before(deadline))
    return m,bodies,total

def module(bodies,name,here,**bindings):
    m=types.ModuleType('neural083_'+name.replace('.','_'));m.__file__=str(here/name)
    m.__dict__.update(bindings);exec(compile(bodies[name],m.__file__,'exec'),m.__dict__)
    return m

def readable(p,tick):
    tick();fd=os.open(path(p),os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:os.fchmod(fd,0o444);os.fsync(fd);tick()
    finally:os.close(fd)
    sync_dir(Path(p).parent,tick)
