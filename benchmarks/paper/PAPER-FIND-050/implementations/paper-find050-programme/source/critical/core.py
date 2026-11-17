"""Bounded ordinary I/O and explicit operation costs; no numerical imports."""
from dataclasses import dataclass,field
from pathlib import Path,PurePosixPath
import hashlib,json,os,stat,time

class Refusal(ValueError): pass
def need(ok,message):
 if not ok: raise Refusal(message)
def exact(value,keys,label):
 need(type(value) is dict and set(value)==set(keys),label+": exact fields")
def relative(value):
 need(type(value) is str and 0<len(value)<=4096 and "\\" not in value,"relative path string")
 p=PurePosixPath(value);need(not p.is_absolute() and all(x not in ("",".","..") for x in value.split("/")),"confined relative path")
 return p
def sha(value):
 need(type(value) is str and len(value)==64 and all(c in "0123456789abcdef" for c in value),"SHA-256")
 return value
def pin(body):return {"bytes":len(body),"sha256":hashlib.sha256(body).hexdigest()}
def encode(value):return (json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode()
def decode(body,cap=1048576):
 need(type(body) is bytes and 0<len(body)<=cap,"bounded JSON")
 def pairs(rows):
  out={}
  for k,v in rows:need(k not in out,"duplicate JSON key");out[k]=v
  return out
 def bad(v):raise Refusal("non-JSON numeric token")
 return json.loads(body,object_pairs_hook=pairs,parse_constant=bad)
@dataclass
class Costs:
 read_limit:int
 write_limit:int
 read:int=0
 write:int=0
 reserved_read:int=0
 reserved_write:int=0
 operations:list=field(default_factory=list)
 started:float=field(default_factory=time.monotonic)
 _io_operations:list=field(default_factory=list,init=False,repr=False)
 def __post_init__(self):
  need(type(self.read_limit) is int and type(self.write_limit) is int and self.read_limit>=0 and self.write_limit>=0,"typed aggregate cost limits")
 def reserve(self,kind,n):
  need(type(n) is int and n>=0,"finite reservation")
  used=getattr(self,kind);held=getattr(self,"reserved_"+kind);limit=getattr(self,kind+"_limit")
  need(used+held+n<=limit,kind+" capacity")
  setattr(self,"reserved_"+kind,held+n)
 def finish(self,kind,reserved,actual):
  need(type(actual) is int and 0<=actual<=reserved,"actual cost prefix")
  setattr(self,"reserved_"+kind,getattr(self,"reserved_"+kind)-reserved)
  setattr(self,kind,getattr(self,kind)+actual)
 def report(self):
  return {"logical_read_bytes":self.read,"logical_write_bytes":self.write,
          "unreleased_read_reservation":self.reserved_read,"unreleased_write_reservation":self.reserved_write,
          "wall_seconds":time.monotonic()-self.started,"physical_io_cpu_rss":"UNKNOWN","operations":[owner.observation() for owner in self._io_operations]}
def ordinary(path):
 p=Path(path).absolute()
 need(not any(x.is_symlink() for x in (p,*p.parents)),"no symlink namespace")
 return p
class OrdinaryIO:
 """OS leaves. Engineering controls replace only this leaf interface."""
 def path(self,p):return ordinary(p)
 def open(self,*a):return os.open(*a)
 def fstat(self,*a):return os.fstat(*a)
 def lstat(self,p):return p.lstat()
 def read(self,*a):return os.read(*a)
 def write(self,*a):return os.write(*a)
 def fsync(self,*a):return os.fsync(*a)
 def close(self,*a):return os.close(*a)
class IOOperation:
 """Original source owner; retained by the same Costs before owned effects.

 The ordinary record append is attempted once. Costs.report observes these
 actual retained owners, including append-failure tails, without publishing
 again. This registry is not a native capability or a new cost allowance.
 """
 def __init__(self,name,cost,io):
  from .lifecycle import Custody
  need(type(cost) is Costs,'actual typed cost ledger')
  self.name=name;self.cost=cost;self.io=io;self.held=[];self.fds=[]
  self.prefix={'read':0,'write':0};self.unknown=[];self.calls=[]
  self.custody=Custody('ordinary_io:'+name)
  self.retirement=[];self.exited=False
  self.publication={'attempted':False,'completed':False,'effects':'none'}
  self.published_record=None
  cost._io_operations.append(self)
 def __enter__(self):return self
 def reserve(self,kind,n):
  self.cost.reserve(kind,n);self.held.append((kind,n))
 def call(self,name,*args):
  self.calls.append(name)
  try:return getattr(self.io,name)(*args)
  except BaseException:
   if name in ('open','read','write','fsync','close'):self.unknown.append(name)
   raise
 def own(self,fd):self.fds.append(fd);return fd
 def observation(self):
  # All acquired-resource retirement precedes diagnostic rendering. Custody
  # retains diagnostic raw errors and caches finite descriptions. Subsequent
  # cost consumers see the actual publication tail, not a provisional row.
  snapshot=self.custody.snapshot()
  return {'operation':self.name,
   'status':'failed' if self.custody.first is not None else ('complete' if self.exited else 'in_progress'),
   'first_error':snapshot['first_error'],
   'known_read_prefix':self.prefix['read'],'known_write_prefix':self.prefix['write'],
   'unknown_syscall_effects':list(self.unknown),
   'cleanup_failures':[x for x in snapshot['errors'] if x['phase'].startswith(('close:','finish:'))],
   'calls':list(self.calls),'retry_performed':False,'physical_IO':'UNKNOWN',
   'failure_custody':snapshot,'retirement':[dict(x) for x in self.retirement],
   'cost_record_publication':dict(self.publication)}
 def __exit__(self,typ,first,tb):
  if self.exited:
   self.custody.capture(Refusal('ordinary I/O retirement is one-shot'),'duplicate_exit','none')
   self.custody.raise_first()
  self.exited=True
  # Raw first is owned before any description, even for hostile BaseException
  # hooks. Fresh close/finish catches get distinct owner/index occurrences.
  if first is not None:self.custody.capture(first,'body')
  for i,fd in enumerate(self.fds):
   row={'phase':'close:'+str(i),'fd':fd,'attempted':True,'completed':False,'effects':'unknown'}
   self.retirement.append(row)
   try:self.call('close',fd)
   except BaseException as exc:self.custody.capture(exc,row['phase'])
   else:row.update(completed=True,effects='returned')
  for i,(kind,n) in enumerate(self.held):
   row={'phase':'finish:'+str(i)+':'+kind,'reserved':n,'known_prefix':self.prefix[kind],
        'attempted':True,'completed':False,'effects':'unknown'}
   self.retirement.append(row)
   try:self.cost.finish(kind,n,self.prefix[kind])
   except BaseException as exc:self.custody.capture(exc,row['phase'])
   else:row.update(completed=True,effects='returned')
  # There is no uncertain retry or rollback: a failing append/finish may have
  # changed its destination. The retained owner survives that ambiguity.
  self.publication.update(attempted=True,effects='unknown')
  try:
   self.published_record=self.observation()
   self.cost.operations.append(self.published_record)
  except BaseException as exc:self.custody.capture(exc,'cost_record_publication')
  else:self.publication.update(completed=True,effects='returned')
  if first is not None:
   self.custody.attach()
   return False
  self.custody.raise_first()
  return False

def read(path,cap,cost,expected=None,*,_io=None):
 io=OrdinaryIO() if _io is None else _io
 with IOOperation('read',cost,io) as op:
  p=op.call('path',path);op.reserve('read',cap)
  fd=op.own(op.call('open',p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK));a=op.call('fstat',fd)
  need(stat.S_ISREG(a.st_mode) and a.st_nlink==1 and 0<=a.st_size<=cap,"bounded single-link file")
  chunks=[]
  while op.prefix['read']<a.st_size:
   part=op.call('read',fd,min(65536,a.st_size-op.prefix['read']));need(bool(part),"short read")
   op.prefix['read']+=len(part);chunks.append(part)
  b=b"".join(chunks);z=op.call('fstat',fd);q=op.call('lstat',p)
  fields=("st_dev","st_ino","st_mode","st_size","st_mtime_ns","st_ctime_ns","st_nlink")
  need(all(getattr(a,k)==getattr(z,k)==getattr(q,k) for k in fields),"stable captured file")
  if expected is not None:need(pin(b)=={k:expected[k] for k in ("bytes","sha256")},"exact selected bytes")
  return b
def write(path,body,cost,*,_io=None):
 io=OrdinaryIO() if _io is None else _io
 with IOOperation('write',cost,io) as op:
  p=op.call('path',path);need(type(body) is bytes,"encoded output");op.reserve('write',len(body))
  fd=op.own(op.call('open',p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600))
  while op.prefix['write']<len(body):
   n=op.call('write',fd,body[op.prefix['write']:]);need(n>0,"short write");op.prefix['write']+=n
  op.call('fsync',fd)
def number(value):
 import math
 need(type(value) in (int,float) and math.isfinite(value),"finite scalar excluding bool")
 return value
def copy_selected(source,destination,expected,cost,*,_io=None):
 """Stream an admitted ordinary file without holding a whole neural file in RAM."""
 io=OrdinaryIO() if _io is None else _io
 with IOOperation('copy_selected',cost,io) as op:
  p=op.call('path',source);q=op.call('path',destination);n=expected['bytes'];sha(expected['sha256'])
  need(type(n) is int and n>=0,"finite copy size");op.reserve('read',n);op.reserve('write',n);h=hashlib.sha256()
  src=op.own(op.call('open',p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK));before=op.call('fstat',src)
  need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==n,"exact selected input extent")
  dst=op.own(op.call('open',q,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600))
  while op.prefix['read']<n:
   part=op.call('read',src,min(65536,n-op.prefix['read']));need(bool(part),'short source');op.prefix['read']+=len(part);h.update(part);at=0
   while at<len(part):
    k=op.call('write',dst,part[at:]);need(k>0,'short destination');at+=k;op.prefix['write']+=k
  after=op.call('fstat',src);leaf=op.call('lstat',p);fields=('st_dev','st_ino','st_size','st_mode','st_nlink','st_mtime_ns','st_ctime_ns')
  need(all(getattr(before,k)==getattr(after,k)==getattr(leaf,k) for k in fields),'stable complete copy')
  need(h.hexdigest()==expected['sha256'],'authenticated streamed copy');op.call('fsync',dst)
