"""Strict source-owned metadata, original-clock reservations and fresh artifacts."""
import hashlib,json,math,os,re,stat,time
from pathlib import Path

TASK='NEURAL-010'
ARMS=('candidate','signal_reference','montage_only','matched_no_eeg')
VIEWS=('full_waveform','waveform_withheld')
MODES=('frozen_program','case_adaptive_equal_inputs_tools_compute')
PEOPLE=23
RECORDS=686
FIT_COUNT=9706

def need(value,reason):
    if not value:raise ValueError(reason)
def integer(value,minimum=0,maximum=2**63-1):
    need(type(value)is int and minimum<=value<=maximum,'strict bounded integer');return value
def finite(value,minimum=None):
    need(type(value)in(int,float)and math.isfinite(value),'finite number, not bool')
    value=float(value);need(minimum is None or value>=minimum,'number below minimum');return value
def exact(value,keys):
    need(type(value)is dict and set(value)==set(keys),'exact object fields');return value
def typed_equal(a,b):
    if type(a)is not type(b):return False
    if type(a)is dict:return a.keys()==b.keys()and all(type(k)is str and typed_equal(a[k],b[k])for k in a)
    if type(a)is list:return len(a)==len(b)and all(typed_equal(x,y)for x,y in zip(a,b))
    if type(a)is float:return math.isfinite(a)and math.isfinite(b)and a.hex()==b.hex()
    return type(a)in(str,int,bool,type(None))and a==b
def encoded(value,newline=True):
    return (json.dumps(value,sort_keys=True,ensure_ascii=True,allow_nan=False,separators=(',',':'))+('\n'if newline else'')).encode()
def parse(raw):
    def pairs(rows):
        out={}
        for k,v in rows:need(k not in out,'duplicate JSON key');out[k]=v
        return out
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'nonfinite JSON'))
def pin(raw):return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
def digest(value):
    need(type(value)is str and re.fullmatch('[0-9a-f]{64}',value),'64-hex digest');return value
def ident(value):
    need(type(value)is str and re.fullmatch('[0-9a-f]{24}',value),'opaque original24-hex identity');return value
def absolute(value):
    need(type(value)is str and value.startswith('/')and not value.startswith('//')and '\\'not in value,'canonical absolute POSIX spelling')
    p=Path(value);need(str(p)==value and all(x not in('','.','..')for x in value.split('/')[1:]),'canonical path without aliases');return p
def descriptor(value,allow_empty=False):
    exact(value,('path','bytes','sha256'));absolute(value['path']);integer(value['bytes'],0 if allow_empty else 1);digest(value['sha256']);return value
def within(path,roots):
    p=absolute(str(path));need(any(p==r or p.is_relative_to(r)for r in roots),'operand outside selected read roots')
    need(not any(q.is_symlink()for q in(p,*p.parents)),'linked operand');return p

class Budget:
    """Logical reservations, not an RSS/physical-I/O measurement."""
    def __init__(self,origin,limits,clock=time.monotonic):
        exact(limits,('seconds','read_bytes','write_bytes','native_cpu_seconds','native_processes','host_processes','provider_requests','provider_tokens','stream_bytes','tool_processes'))
        self.clock=clock;self.origin=finite(origin,0);self.seconds=finite(limits['seconds'],0)
        need(self.seconds>0,'positive original-clock interval');self.end=self.origin+self.seconds
        self.limits={k:integer(v,0)for k,v in limits.items()if k!='seconds'};self.used={k:0 for k in self.limits};self.check_clock()
    def check_clock(self):need(self.clock()<self.end,'original whole-study deadline exceeded')
    def charge(self,key,amount):
        self.check_clock();integer(amount,0);need(key in self.used and self.used[key]+amount<=self.limits[key],'prospective resource reservation exceeded: '+key)
        self.used[key]+=amount
    def snapshot(self):return {'original_origin':self.origin,'original_deadline':self.end,'logical_used':dict(self.used),'limits':dict(self.limits),'physical_IO_or_RSS_measured':False}

def capture(desc,budget,roots,*,empty=False):
    descriptor(desc,empty);budget.charge('read_bytes',desc['bytes']+1);p=within(desc['path'],roots)
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd);need(stat.S_ISREG(before.st_mode)and before.st_nlink==1 and before.st_size==desc['bytes'],'ordinary exact operand extent')
        with os.fdopen(fd,'rb',closefd=False)as stream:raw=stream.read(desc['bytes']+1)
        after=os.fstat(fd);named=p.lstat();fields=('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_mode','st_nlink')
        need(all(getattr(before,k)==getattr(after,k)==getattr(named,k)for k in fields)and pin(raw)=={k:desc[k]for k in('bytes','sha256')},'stable complete captured operand')
    finally:os.close(fd)
    budget.check_clock();return raw
def capture_json(desc,budget,roots):return parse(capture(desc,budget,roots))
def authenticate_stream(desc,budget,roots,*,empty=False):
    descriptor(desc,empty);budget.charge('read_bytes',desc['bytes']+1);p=within(desc['path'],roots)
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd);need(stat.S_ISREG(before.st_mode)and before.st_nlink==1 and before.st_size==desc['bytes'],'exact ordinary streamed input extent')
        h=hashlib.sha256();n=0
        while n<=desc['bytes']:
            budget.check_clock();b=os.read(fd,min(1048576,desc['bytes']+1-n))
            if not b:break
            n+=len(b);h.update(b)
        fields=('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_mode','st_nlink');after=os.fstat(fd);named=p.lstat()
        need(n==desc['bytes']and h.hexdigest()==desc['sha256']and all(getattr(before,k)==getattr(after,k)==getattr(named,k)for k in fields),'complete stable streamed artifact')
    finally:os.close(fd)
    budget.check_clock();return desc
def sync_directory(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)
def new_directory(path,budget):
    budget.check_clock();p=absolute(str(path));need(not any(q.is_symlink()for q in p.parents),'ordinary output parents');p.mkdir(mode=0o700);sync_directory(p);sync_directory(p.parent);budget.check_clock();return p
def publish(path,raw,budget):
    p=absolute(str(path));budget.charge('write_bytes',len(raw));need(not any(q.is_symlink()for q in p.parents),'ordinary output parents')
    fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,'wb',closefd=False)as stream:stream.write(raw);stream.flush();os.fsync(fd)
    finally:os.close(fd)
    sync_directory(p.parent);budget.check_clock();return {'path':str(p),**pin(raw)}
def publish_json(path,value,budget):return publish(path,encoded(value),budget)

def copy_stream(desc,path,budget,roots):
    """Fresh full-copy custody, never a reduced or lazily omitted input."""
    descriptor(desc,True);p=within(desc['path'],roots);destination=absolute(str(path))
    need(not any(q.is_symlink()for q in destination.parents),'ordinary copy parents')
    budget.charge('read_bytes',desc['bytes']+1);budget.charge('write_bytes',desc['bytes'])
    source=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(source);need(stat.S_ISREG(before.st_mode)and before.st_nlink==1 and before.st_size==desc['bytes'],'full ordinary copy source')
        out=os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        h=hashlib.sha256();n=0
        try:
            with os.fdopen(out,'wb',closefd=False)as stream:
                while n<=desc['bytes']:
                    budget.check_clock();block=os.read(source,min(1048576,desc['bytes']+1-n))
                    if not block:break
                    n+=len(block);need(n<=desc['bytes'],'copy source grew');h.update(block);stream.write(block)
                stream.flush();os.fsync(out)
        finally:os.close(out)
        after=os.fstat(source);named=p.lstat();fields=('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_mode','st_nlink')
        need(n==desc['bytes']and h.hexdigest()==desc['sha256']and all(getattr(before,k)==getattr(after,k)==getattr(named,k)for k in fields),'complete stable copied source')
    finally:os.close(source)
    sync_directory(destination.parent);budget.check_clock();return {'path':str(destination),'bytes':n,'sha256':h.hexdigest()}

class LocalBudget:
    """Per-context counters debit the unchanged enclosing study exactly once."""
    def __init__(self,parent,limits):
        exact(limits,('seconds',*parent.limits));self.parent=parent;self.origin=parent.origin
        self.started_monotonic=parent.clock();self.end=min(parent.end,self.started_monotonic+finite(limits['seconds'],0));self.clock=parent.clock
        need(limits['seconds']>0,'positive local duration');self.limits={k:integer(limits[k])for k in parent.limits};self.used={k:0 for k in self.limits};self.check_clock()
    def check_clock(self):self.parent.check_clock();need(self.clock()<self.end,'original local context deadline exceeded')
    def charge(self,key,amount):
        self.check_clock();integer(amount);need(key in self.used and self.used[key]+amount<=self.limits[key],'local resource reservation exceeded')
        self.parent.charge(key,amount);self.used[key]+=amount
    def snapshot(self):return {'original_origin':self.origin,'started_monotonic':self.started_monotonic,'original_deadline':self.end,'logical_used':dict(self.used),'limits':dict(self.limits),'physical_IO_or_RSS_measured':False}

class Journal:
    def __init__(self,directory,budget):self.directory=directory;self.budget=budget;self.sequence=0;self.previous=None
    def append(self,kind,payload):
        integer(self.sequence,0);need(type(kind)is str and kind,'journal event kind')
        row={'schema':'neural010-original-operation-event-v1','sequence':self.sequence,'kind':kind,'previous':self.previous,'payload':payload,'budget':self.budget.snapshot()}
        d=publish_json(self.directory/('%06d.json'%self.sequence),row,self.budget);self.previous=d;self.sequence+=1;return d

def source_authority(authority,source):
    """Only exact separately issued qualifications admit later actual execution."""
    need(type(authority)is dict and authority.get('schema')=='neural010-source-execution-authority-v1','separate operator authority')
    need(authority.get('execution_selected')is True and typed_equal(authority.get('source'),source),'exact selected operative source')
    for role in ('input','method','native','physical_custody','provider','resources','observer'):
        d=authority.get('qualification',{}).get(role)
        need(type(d)is dict and d.get('status')=='qualified'and d.get('source')==source and d.get('independent_issuer_selected')is True,'missing independently selected '+role+' qualification')
    return authority
