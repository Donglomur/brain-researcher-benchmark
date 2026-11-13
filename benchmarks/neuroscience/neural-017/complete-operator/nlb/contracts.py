"""Closed descriptors, authority, original resource envelopes and strong failure custody."""
from dataclasses import dataclass,field
from pathlib import Path
import hashlib,json,math,os,stat,time,unicodedata

class Refusal(ValueError):pass
def need(v,why):
 if not v:raise Refusal(why)
def closed(v,keys):need(type(v)is dict and set(v)==set(keys),'closed schema');return v
def integer(v,lo=0,hi=2**63-1):need(type(v)is int and lo<=v<=hi,'integer domain');return v
def finite(v):need(type(v)in(int,float)and math.isfinite(v),'finite scalar');return v
def canonical(v):return(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)+'\n').encode()
def parse(raw):
 def pairs(xs):
  out={}
  for k,v in xs:need(k not in out,'duplicate JSON key');out[k]=v
  return out
 def real(s):v=float(s);finite(v);return v
 def bad(s):raise Refusal('nonfinite JSON '+s)
 return json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_float=real,parse_constant=bad)
def digest(raw):return hashlib.sha256(raw).hexdigest()
def alias(s):return unicodedata.normalize('NFKC',s).casefold().rstrip(' .')
def relative(s):
 need(type(s)is str and 0<len(s)<=4096 and not s.startswith('/')and'\\'not in s,'relative path')
 need(all(x and x not in('.','..')and x==x.rstrip(' .')and unicodedata.normalize('NFC',x)==x and alias(x)!='.git'and'openbmi-full216-identity-keys'not in alias(x)for x in s.split('/')),'path component')
 need(all(ord(c)>=32 and ord(c)!=127 for c in s),'path control');return s
def descriptor(d):
 closed(d,{'path','bytes','sha256'});relative(d['path']);integer(d['bytes']);need(type(d['sha256'])is str and len(d['sha256'])==64 and all(x in'0123456789abcdef'for x in d['sha256']),'digest');return d
def root_path(s):
 p=Path(s);need(type(s)is str and p.is_absolute()and str(p)==s and'..'not in p.parts,'absolute root')
 need(all(alias(x)!='.git'and'openbmi-full216-identity-keys'not in alias(x)for x in p.parts),'excluded root')
 for q in[p,*p.parents]:need(not q.is_symlink(),'symlink root')
 return p
def stable(st):return(st.st_dev,st.st_ino,st.st_size,st.st_mode,st.st_nlink,st.st_mtime_ns,st.st_ctime_ns)

def diagnostic(e):
 cls=type(e);name='nonbuiltin_exception'
 for known,label in ((Refusal,'Refusal'),(OSError,'OSError'),(ValueError,'ValueError'),(RuntimeError,'RuntimeError'),(TypeError,'TypeError'),(KeyError,'KeyError'),(TimeoutError,'TimeoutError'),(KeyboardInterrupt,'KeyboardInterrupt'),(SystemExit,'SystemExit')):
  if cls is known:name=label;break
 # Obtain the builtin descriptor from BaseException itself, bypassing all
 # subclass args/__dict__/__traceback__ properties and metaclass callbacks.
 try:args=type.__getattribute__(BaseException,'__dict__')['args'].__get__(e,BaseException)
 except TypeError:args=()
 text=args[0]if type(args)is tuple and args and type(args[0])is str else name
 text=str.encode(text[:1024],'ascii','backslashreplace')[:2048].decode('ascii')
 return{'type':name,'detail':text,'identity':id(e)}

@dataclass
class Custody:
 operation:str
 first_error:object=None
 phase:str='not_started'
 errors:list=field(default_factory=list)
 events:list=field(default_factory=list)
 facts:dict=field(default_factory=dict)
 resources:list=field(default_factory=list)
 complete:bool=False
 receipt:object=None
 def fail(self,error,phase,owner=None):
  # Explicit source-owned transfer; never attach state to an arbitrary exception.
  if owner is not None and owner is not self:
   need(type(owner)is Custody,'actual owned custody transfer')
   if not any(x is owner for x in self.resources):self.resources.append(owner)
   if owner.first_error is not None:self.fail(owner.first_error,phase+':'+owner.phase)
   for secondary in owner.errors:self.fail(secondary,phase+':secondary')
  if error is None:return
  if self.first_error is None:self.first_error=error;self.phase=phase
  elif error is not self.first_error:self.errors.append(error)
  self.complete=False
 def capture(self,error,phase):
  """Retain the caught raw object before optional source-carrier transfer.

The caught observation never changes. Only exact shared carrier identities may
transfer their earlier source owner. No scientific imports or arbitrary error
attributes are used; an unknown subclass is an opaque raw failure.
"""
  caught=Custody('caught:'+phase);caught.fail(error,phase);self.resources.append(caught)
  try:
   owner=failure_owner(error)
   self.fail(None if owner is not None and owner.first_error is not None else error,phase,owner)
  except BaseException as secondary:
   self.fail(error,phase);self.fail(secondary,phase+':owner_transfer')
  return caught
 def raise_if_failed(self):
  if self.first_error is not None:raise self.first_error
 def snapshot(self):

  return{'operation':self.operation,'phase':self.phase,'complete':self.complete,'first_error':None if self.first_error is None else diagnostic(self.first_error),'secondary_errors':[diagnostic(x)for x in self.errors],'events':list(self.events),'facts':dict(self.facts),'resources':[x.snapshot()for x in self.resources],'receipt':self.receipt}

# Shared metadata-only failure carriers. Their original module APIs re-export
# these exact types; no scientific algorithm is imported by the learner image.
class ScientificFailure(RuntimeError):
    """Exact source-created carrier; arbitrary subclasses never supply custody."""
    def __init__(self, message, original=None, observations=None, custody=None):
        self.custody = custody if type(custody) is Custody else Custody("scientific_failure")
        if original is not None and self.custody.first_error is None:
            self.custody.fail(original, "scientific_original")
        self.original_exception = original
        self.original_observations = observations if observations is not None else []
        self.secondary_exceptions = self.custody.errors
        self.scientific_reason = "scientific_producer_failed"
        super().__init__(message)


class UncertaintyDrawFailure(ValueError):
 """Strong original protected draw custody, including publication failures."""
 def __init__(self,family,seed,index,indices,blocks,denominator,values,original):
  self.original_exception=original;self.original_indices=indices;self.original_blocks=blocks
  self.original_denominator=denominator;self.original_values=values;self.custody=Custody("uncertainty_draw");self.custody.fail(original,"draw_original");self.secondary_exceptions=self.custody.errors
  self.custody.original_draw_operands={'indices':indices,'blocks':blocks,'denominator':denominator,'values':values}
  self.protected_observation={'schema':'NLB017_original_failed_uncertainty_draw_v1','family':family,'seed':seed,'draw_index':index,'protected_only':True,'redraw_performed':False,'capture_complete':False}
  super().__init__('uncertainty '+family+' draw '+str(index)+' failed')


def failure_owner(error):
 """Lookup only exact source-created carriers; never inspect an opaque error."""
 if type(error)is ScientificFailure or type(error)is UncertaintyDrawFailure:
  owner=error.custody
  return owner if type(owner)is Custody else None
 return None

class Handles:
 def __init__(self,custody):self.live={};self.closed=[];self.custody=custody;custody.resources.append(self)
 def own(self,fd,kind,label):
  row={'fd':fd,'kind':kind,'label':label,'identity':None,'state':'owned','attempts':0};self.live[fd]=row
  try:
   st=os.fstat(fd);row['identity']=(st.st_dev,st.st_ino,stat.S_IFMT(st.st_mode))
  except BaseException as e:self.custody.fail(e,'adopt_handle');raise
  return fd
 def close(self,fd):
  row=self.live[fd]
  # A failed close may have consumed the descriptor. No probe can prove that
  # the same integer has not been reused, even with the same inode identity.
  need(row['state']=='owned'and row['attempts']==0,'original descriptor close attempted once')
  row['attempts']=1
  try:os.close(fd)
  except BaseException as e:
   row['state']='unknown_after_close_error';self.custody.fail(e,'close_handle');raise
  else:row['state']='closed';self.closed.append(self.live.pop(fd))
 def finish(self):
  for fd,row in list(self.live.items()):
   if row['state']=='owned'and row['attempts']==0:
    try:self.close(fd)
    except BaseException:pass
  if self.live:self.custody.fail(Refusal('unresolved handle ownership'),'finish_handles')
 def snapshot(self):return{'live':[dict(x)for x in self.live.values()],'closed':[dict(x)for x in self.closed],'all_closed':not self.live}

class Budget:
 KEYS=('cpu_seconds','read_bytes','write_bytes','stream_bytes','model_tokens','created_files','tool_calls')
 IO_KEYS=('read_bytes','write_bytes','created_files')
 def __init__(self,limits,deadline,*,parent=None,clock=time.monotonic,custody=None):
  closed(limits,self.KEYS)
  for k,v in limits.items():
   finite(v);need(v>=0,'nonnegative budget')
   if k!='cpu_seconds':integer(v)
  finite(deadline);need(deadline>0,'deadline');self.limits=dict(limits);self.used=dict.fromkeys(self.KEYS,0);self.reserved=dict.fromkeys(self.KEYS,0);self.held=dict.fromkeys(self.KEYS,0);self.deadline=deadline;self.clock=clock;self.parent=parent;self.custody=custody;self.stops=[];self.child_leases={};self.lease_digest='0'*64
  if parent:need(deadline<=parent.deadline,'no deadline renewal')
 def guard(self):
  if self.parent:self.parent.guard()
  need(self.clock()<self.deadline,'original deadline exceeded')
  if hasattr(self,'authority'):need(time.time()<self.authority.expires_at,'current authority expired')
 def charge(self,key,value):
  finite(value);need(key in self.used and value>=0,'resource delta');self.used[key]+=value
  if self.parent:self.parent.charge(key,value)
  if self.used[key]+self.held[key]>self.limits[key]:self.stop('resource limit '+key);raise Refusal('resource limit '+key)
 def reserve(self,key,value,*,release=False):
  finite(value)
  if release:
   need(key in self.IO_KEYS and value>=0 and value<=self.reserved[key],'release only unused original IO reservation')
   if self.parent:self.parent.reserve(key,value,release=True)
   self.reserved[key]-=value;return
  need(value>=0 and key in self.reserved and max(self.used[key],self.reserved[key]+value)+self.held[key]<=self.limits[key],'reservation '+key)
  if self.parent:self.parent.reserve(key,value)
  self.reserved[key]+=value
 def stop(self,reason):
  """Prevent further dispatch without preventing bounded final custody work."""
  if reason not in self.stops:self.stops.append(reason)
  if self.parent:self.parent.stop(reason)
 def admit(self):
  self.guard()
  if self.parent:self.parent.admit()
  need(not self.stops,'resource pool stopped: '+repr(self.stops))
  need(all(max(self.used[k],self.reserved[k])+self.held[k]<=self.limits[k]for k in self.KEYS),'consumed resource pool')
 def available(self,key):
  amount=self.limits[key]-max(self.used[key],self.reserved[key])-self.held[key]
  return min(amount,self.parent.available(key))if self.parent else amount
 def _hold(self,key,delta):
  need(self.held[key]+delta>=0 and (delta<=0 or delta<=self.available(key)),'finite child hold')
  if self.parent:self.parent._hold(key,delta)
  self.held[key]+=delta
 def lease_io(self,job,requested,completion):
  self.admit();closed(requested,self.IO_KEYS);closed(completion,self.IO_KEYS);need(job not in self.child_leases,'one original child allocation')
  limits={}
  for k in self.IO_KEYS:
   integer(requested[k]);integer(completion[k]);limits[k]=min(requested[k],self.available(k)-completion[k]);need(limits[k]>=0,'parent completion reservation unavailable')
  row={'limits':limits,'completion_allowance':dict(completion),'status':'allocated','joined':False,'worker_snapshot':None};self.child_leases[job]=row
  for k,v in limits.items():self._hold(k,v)
  self.lease_digest=digest(canonical({'previous':self.lease_digest,'job':job,'event':'allocated','limits':limits}))
  return dict(limits)
 def settle_io(self,job,snapshot):
  row=self.child_leases[job];need(not row['joined'],'child counters joined exactly once')
  try:
   closed(snapshot,{'limits','used','reserved'})
   for k in self.IO_KEYS:
    need(snapshot['limits'][k]==row['limits'][k],'original residual child limits')
    for field in('used','reserved'):integer(snapshot[field][k]);need(snapshot[field][k]<=row['limits'][k],'child original resource excess')
   # Retain the original before charging; a later accounting failure cannot replay.
   row['worker_snapshot']=snapshot;row['joined']=True;row['status']='joining'
   for k,v in row['limits'].items():self._hold(k,-v)
   for k in self.IO_KEYS:self.reserve(k,snapshot['reserved'][k]);self.charge(k,snapshot['used'][k])
   row['status']='joined'
   self.lease_digest=digest(canonical({'previous':self.lease_digest,'job':job,'event':'joined','original_counters':snapshot}))
  except BaseException:
   self.stop('unresolved child accounting '+job);row['status']='unresolved';raise
 def unknown_child(self,job):
  row=self.child_leases[job];row['status']='unknown';self.stop('unknown child accounting '+job);self.lease_digest=digest(canonical({'previous':self.lease_digest,'job':job,'event':'unknown'}))
 def snapshot(self):
  # Do not serialize all earlier case ledgers into every later receipt. Each
  # original process owns its exact allocation/counters; this summary is bounded.
  summary={'allocated':len(self.child_leases),'joined':sum(r['status']=='joined'for r in self.child_leases.values()),'unknown_or_unresolved':sum(r['status']in('unknown','unresolved')for r in self.child_leases.values()),'event_chain_sha256':self.lease_digest}
  return{'limits':dict(self.limits),'used':dict(self.used),'reserved':dict(self.reserved),'held':dict(self.held),'deadline':self.deadline,'stops':list(self.stops),'child_accounting':summary,'unknown_is_not_zero':True}

class ReadOwner:
 """Original read reservations, known bytes and unknown effects stay distinct.

 Each owner alone may consume its unused original reservation. Unreturned
 capacity is never reported as actual bytes or refunded. A failed read retains
 its requested upper bound and quarantines further dispatch on the same pool.
 """
 def __init__(self,budget,custody,label):
  self.budget=budget;self.custody=custody;self.label=label;self.credit=0;self.allocated=0;self.known_returned=0;self.unknown_capacity=0;self.chunks=[];self.last_returned=None;self.events=[];self.quarantined=False;custody.resources.append(self)
 def reserve(self,extent):
  integer(extent);need(extent>=0 and not self.quarantined,'original read reservation');self.budget.admit()
  # A cumulative reservation counter can trail already charged usage (for
  # example an admitted external receipt). New owner credit must come from
  # actual residual capacity, not the gap between those two original ledgers.
  need(extent<=self.budget.available('read_bytes'),'original read reservation exceeds remaining capacity')
  self.budget.reserve('read_bytes',extent);self.credit+=extent;self.allocated+=extent
 def quarantine(self,error,phase):
  self.custody.fail(error,phase);self.quarantined=True
  try:self.budget.stop('uncertain or failed original read '+self.label)
  except BaseException as secondary:self.custody.fail(secondary,'read_quarantine')
 def read(self,fd,maximum,pending=None):
  integer(maximum);need(maximum>0,'positive bounded read extent');need(pending is None or type(pending)is bytearray,'owned read prefix buffer')
  self.budget.admit();need(not self.quarantined,'read owner quarantined')
  if self.credit==0:
   capacity=min(maximum,self.budget.available('read_bytes'));need(capacity>0,'original read capacity unavailable');self.reserve(capacity)
  # Credit authorizes consumption of this owner's reservation; it does not
  # create new budget. Earlier or intervening charged use can exceed a pool's
  # reservation counter. Bound the OS effect by actual unspent capacity at
  # EVERY original enclosing pool, including any still-held child allowance.
  capacity=min(maximum,self.credit);pool=self.budget
  while pool is not None:
   capacity=min(capacity,pool.limits['read_bytes']-pool.used['read_bytes']-pool.held['read_bytes']);pool=pool.parent
  need(type(capacity)is int and capacity>0,'original read capacity unavailable')
  event={'requested_bytes':capacity,'returned_bytes':None,'effect':'attempted','unknown_upper_bound':0};self.events.append(event)
  try:raw=os.read(fd,capacity)
  except BaseException as error:
   self.custody.fail(error,'original_read:'+self.label);event['effect']='unknown';event['unknown_upper_bound']=capacity;self.unknown_capacity+=capacity
   self.quarantine(error,'original_read:'+self.label);self.custody.raise_if_failed()
  # Hold the actual bytes before append, decoding, cost debit or publication.
  self.last_returned=raw
  try:
   need(type(raw)is bytes,'OS read must return exact bytes');event['returned_bytes']=len(raw);event['effect']='returned';self.known_returned+=len(raw);self.chunks.append(raw)
   if pending is not None:pending.extend(raw)
   need(len(raw)<=capacity,'OS read exceeded admitted request');self.credit-=len(raw)
   self.budget.charge('read_bytes',len(raw))
  except BaseException as error:
   self.quarantine(error,'original_read_accounting:'+self.label);self.custody.raise_if_failed()
  return raw
 def snapshot(self):
  return {'operation':self.label,'allocated_read_capacity':self.allocated,'unused_original_capacity':self.credit,'known_returned_bytes':self.known_returned,'unknown_consumption_upper_bound':self.unknown_capacity,'quarantined':self.quarantined,'attempts':[dict(x)for x in self.events],'known_prefix_retained_privately':self.last_returned is not None or bool(self.chunks),'raw_prefix_published':False,'reservation_is_not_actual_bytes':True}

class Store:
 """Anchored finite ordinary artifacts. Protected/primary roles are explicit per call."""
 def __init__(self,root,budget,custody):self.root=root_path(str(root));self.budget=budget;self.custody=custody
 def path(self,name):
  relative(name);p=self.root/name
  for q in[p,*p.parents]:
   need(not q.is_symlink(),'artifact symlink')
   if q==self.root:break
  return p
 def parent(self,name,h):
  relative(name);parts=(*self.root.parts[1:],*name.split('/')[:-1]);fd=h.own(os.open('/',os.O_RDONLY|os.O_DIRECTORY),'directory','/')
  for part in parts:
   self.budget.guard();matches=[n for n in os.listdir(fd)if alias(n)==alias(part)];need(matches==[part],'exact directory spelling')
   nxt=h.own(os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd),'directory',part);h.close(fd);fd=nxt
  leaf=name.split('/')[-1];matches=[n for n in os.listdir(fd)if alias(n)==alias(leaf)];need(not matches or matches==[leaf],'exact artifact spelling');return fd,leaf
 def read(self,d,cap):
  descriptor(d);need(d['bytes']<=cap,'read cap');self.budget.admit();h=Handles(self.custody);reader=ReadOwner(self.budget,self.custody,'artifact:'+d['path']);raw=None
  try:
   parent,leaf=self.parent(d['path'],h);before=os.stat(leaf,dir_fd=parent,follow_symlinks=False);need(stat.S_ISREG(before.st_mode)and before.st_nlink==1 and before.st_size==d['bytes'],'ordinary read');reader.reserve(d['bytes'])
   fd=h.own(os.open(leaf,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=parent),'file',d['path']);need(stable(before)==stable(os.fstat(fd)),'read inode');n=0
   while n<d['bytes']:
    b=reader.read(fd,min(65536,d['bytes']-n));need(bool(b),'short ordinary read');n+=len(b)
   # Exact regular-file extent plus stable before/after metadata proves this
   # snapshot. No cap+1/EOF byte is consumed beyond the admitted extent.
   raw=b''.join(reader.chunks);need(stable(before)==stable(os.fstat(fd))==stable(os.stat(leaf,dir_fd=parent,follow_symlinks=False)),'read changed');need(len(raw)==d['bytes']and digest(raw)==d['sha256'],'read identity')
  except BaseException as e:self.custody.fail(e,'read')
  finally:h.finish()
  self.custody.raise_if_failed();self.budget.guard();return raw
 def write(self,name,raw,cap):
  need(type(raw)is bytes and len(raw)<=cap,'write body');self.budget.guard();p=self.path(name);need(p.parent.is_dir(),'preexisting output parent');h=Handles(self.custody);event={'path':name,'accepted_bytes':0,'created':False,'durable':False};self.custody.events.append(event)
  try:
   self.budget.reserve('write_bytes',len(raw));self.budget.reserve('created_files',1)
   parent,leaf=self.parent(name,h);fd=h.own(os.open(leaf,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=parent),'file',name);event['created']=True;self.budget.charge('created_files',1)
   while event['accepted_bytes']<len(raw):
    self.budget.guard();n=os.write(fd,raw[event['accepted_bytes']:]);need(n>0,'short write');event['accepted_bytes']+=n;self.budget.charge('write_bytes',n)
   os.fsync(fd);os.fsync(parent);event['durable']=True
  except BaseException as e:self.custody.fail(e,'write');event['durable']=False
  finally:h.finish()
  self.custody.raise_if_failed();self.budget.guard();d={'path':name,'bytes':len(raw),'sha256':digest(raw)};return d
 def json(self,d,cap=8*2**20):return parse(self.read(d,cap))
 def capture(self,name,cap):
  """Discover a new ordinary producer artifact only after its absence barrier."""
  relative(name);self.budget.admit();h=Handles(self.custody);reader=ReadOwner(self.budget,self.custody,'capture:'+name);raw=None
  try:
   parent,leaf=self.parent(name,h);st=os.stat(leaf,dir_fd=parent,follow_symlinks=False);need(stat.S_ISREG(st.st_mode)and st.st_nlink==1 and st.st_size<=cap,'captured artifact domain');reader.reserve(st.st_size)
   fd=h.own(os.open(leaf,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=parent),'file',name);need(stable(st)==stable(os.fstat(fd)),'capture inode');n=0
   while n<st.st_size:
    b=reader.read(fd,min(65536,st.st_size-n));need(bool(b),'short captured read');n+=len(b)
   raw=b''.join(reader.chunks);need(stable(st)==stable(os.fstat(fd))==stable(os.stat(leaf,dir_fd=parent,follow_symlinks=False))and len(raw)==st.st_size,'stable complete capture')
  except BaseException as e:self.custody.fail(e,'capture')
  finally:h.finish()
  self.custody.raise_if_failed();self.budget.guard();return {'path':name,'bytes':len(raw),'sha256':digest(raw)},raw

@dataclass(frozen=True)
class Authority:
 campaign:str
 root_source:str
 expires_at:float
 stages:frozenset
 native_roles:frozenset
 input_pins:tuple
 output_root:str
 runtime:dict
 def check(self,stage,role=None,now=time.time):
  need(now()<self.expires_at,'authority expired');need(stage in self.stages,'stage not selected')
  if role is not None:need(role in self.native_roles,'native role not selected')
 @classmethod
 def from_selected(cls,store,pin,expected_source):
  d=store.json(pin,128*2**20);closed(d,{'schema','campaign','root_source','expires_at','stages','native_roles','input_pins','output_root','runtime','allow_authentic_execution'})
  need(d['schema']=='NLB017_current_operator_authority_v1'and d['allow_authentic_execution']is True,'no default execution authority');need(d['root_source']==expected_source,'source authority mismatch')
  finite(d['expires_at']);root_path(d['output_root']);need(len(set(d['stages']))==len(d['stages']),'duplicate authority stage')
  for p in d['input_pins']:descriptor(p)
  out=cls(d['campaign'],d['root_source'],d['expires_at'],frozenset(d['stages']),frozenset(d['native_roles']),tuple(d['input_pins']),d['output_root'],d['runtime']);out.check('S01');return out
