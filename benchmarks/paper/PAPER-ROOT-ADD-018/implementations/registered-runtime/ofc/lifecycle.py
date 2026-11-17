"""Original clocks, conservative logical write admission and reserved custody.

Physical filesystem/OS quotas remain an external qualification. Child leases
charge their whole declared storage maximum cumulatively before launch; unused
cumulative credit is never recycled. This is a logical materialization budget,
not a claim to measure overwritten physical I/O inside a process.
"""
import contextlib,contextvars,hashlib,json,os,time
from pathlib import Path

class LifecycleError(ValueError):pass
class DeadlineExceeded(LifecycleError):pass
class BudgetExceeded(LifecycleError):pass
class UnresolvedContainment(LifecycleError):pass
class UnresolvedCustody(LifecycleError):pass
_CURRENT=contextvars.ContextVar('ofc_lifecycle',default=None)
SLOT_BYTES=8192

def current():return _CURRENT.get()
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def error_record(error):
 # Error rendering is itself fallible. Keep original objects separately; an
 # unavailable rendering is not an empty message or a successful measurement.
 try:
  text=str(error);body=text.encode('utf-8',errors='replace')
  return {'type':type(error).__name__,'message_prefix':text[:1024],'message_bytes':len(body),'message_sha256':hashlib.sha256(body).hexdigest(),'message_observed':True}
 except BaseException as secondary:
  return {'type':type(error).__name__,'message_prefix':None,'message_bytes':None,'message_sha256':None,'message_observed':False,'rendering_error_type':type(secondary).__name__}
def guard(label):
 c=current()
 if c is not None:c.check(label)
def _under(path,root):
 p=Path(path).absolute()
 if p!=root and root not in p.parents:raise LifecycleError('write outside original campaign root')
 for q in (p,*p.parents):
  if q.is_symlink():raise LifecycleError('symlink in campaign path')
 return p

class Ledger:
 def __init__(self,root,cap,file_cap=1000000):
  self.root=Path(root).absolute();self.cap=cap;self.file_cap=file_cap;self.cumulative=0;self.retained=0;self.entries=0;self.leases=[];self.events=[]
 def admit(self,size,entries,label):
  if size<0 or entries<0:raise BudgetExceeded('negative budget admission')
  if self.cumulative+size>self.cap or self.retained+size>self.cap or self.entries+entries>self.file_cap:raise BudgetExceeded('whole-output prospective budget: '+label)
  self.cumulative+=size;self.retained+=size;self.entries+=entries
 def directories(self,path):
  p=_under(path,self.root);missing=[]
  while p!=self.root and not p.exists():missing.append(p);p=p.parent
  for folder in reversed(missing):self.admit(0,1,'directory');folder.mkdir()
 def ordinary(self,path,body,append=False,closing=False):
  c=current()
  if c is not None and not closing:c.check('before trusted write')
  p=_under(path,self.root);self.directories(p.parent);new=not p.exists()
  if append and not new:
   s=p.lstat()
   if not p.is_file()or s.st_nlink!=1:raise LifecycleError('append target not ordinary')
  self.admit(len(body),int(new),'trusted append'if append else'trusted file')
  flags=os.O_WRONLY|os.O_CREAT|getattr(os,'O_NOFOLLOW',0)|(os.O_APPEND if append else os.O_EXCL)
  fd=os.open(p,flags,0o600)
  with os.fdopen(fd,'wb')as f:f.write(body);f.flush();os.fsync(f.fileno())
  if c is not None and not closing:c.check('after trusted write')
  return {'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}
 def reserve_slot(self,name,writes):
  # All future in-place writes count now. Retained size counts only once.
  cost=SLOT_BYTES*writes
  self.admit(cost,1,'reserved closure '+name);self.retained-=cost-SLOT_BYTES
  return FixedSlot(self,self.root/'custody'/name,writes)
 def lease(self,cap,entries,label):
  self.admit(cap,entries,'child storage lease '+label);lease={'label':label,'reserved_bytes':cap,'reserved_entries':entries,'settled':False};self.leases.append(lease);return lease
 def settle(self,lease,actual_bytes,actual_entries):
  if lease['settled']:raise LifecycleError('child lease settled twice')
  lease.update(settled=True,observed_bytes=actual_bytes,observed_entries=actual_entries)
  self.retained+=actual_bytes-lease['reserved_bytes'];self.entries+=actual_entries-lease['reserved_entries']
  if actual_bytes>lease['reserved_bytes']or actual_entries>lease['reserved_entries']:
   self.events.append({'kind':'observed_child_physical_overshoot','lease':dict(lease)})
   raise BudgetExceeded('child exceeded precharged storage lease; physical quota qualification failed')
 def snapshot(self):return {'cap_bytes':self.cap,'cumulative_logical_admitted_bytes':self.cumulative,'retained_upper_bytes':self.retained,'entry_upper':self.entries,'file_cap':self.file_cap,'child_leases':self.leases,'events':self.events,'physical_IO_measured':False}

class FixedSlot:
 def __init__(self,ledger,path,writes):
  self.ledger=ledger;self.path=path;self.remaining=writes;self.path.parent.mkdir(parents=True,exist_ok=True)
  self.file=self.path.open('x+b');self.put({'state':'reserved_before_effects','slot':path.name})
 def put(self,record):
  if self.remaining<=0:raise BudgetExceeded('reserved closure rewrite count exhausted')
  body=canonical(record)
  if len(body)>SLOT_BYTES:raise BudgetExceeded('reserved closure record too large')
  self.remaining-=1;self.file.seek(0);self.file.write(body.ljust(SLOT_BYTES,b' '));self.file.flush();os.fsync(self.file.fileno())
 def close(self):self.file.close()

class Context:
 def __init__(self,campaign,deadlines,label):self.campaign=campaign;self.deadlines=tuple(deadlines);self.label=label
 @property
 def deadline(self):return min(t for _,t in self.deadlines)
 def check(self,label):
  if self.campaign.fatal is not None:raise self.campaign.fatal
  instant=self.campaign.clock()
  for name,deadline in self.deadlines:
   if instant>=deadline:raise DeadlineExceeded(name+' deadline before '+label)
 def protected(self,label):self.check(label);self.campaign.assert_contained()
 @contextlib.contextmanager
 def nested(self,label,seconds):
  self.check('enter '+label);deadline=min(self.deadline,self.campaign.clock()+seconds);child=Context(self.campaign,self.deadlines+((label,deadline),),label);token=_CURRENT.set(child)
  try:yield child;child.check('return '+label)
  finally:_CURRENT.reset(token)

class Campaign:
 def __init__(self,root,cap,deadline,jobs,clock=time.monotonic,identity_binding=None):
  self.root=Path(root).absolute();self.identity_binding=identity_binding or {'root':str(self.root),'jobs':jobs,'deadline':deadline};self.id=hashlib.sha256(canonical(self.identity_binding)).hexdigest();self.clock=clock;self.deadline=deadline;self.ledger=Ledger(self.root,cap);self.attempts=[];self.condition_records=[];self.slots={};self.closure_errors=[];self.first_failure=None;self.fatal=None
  self.original_first_failure=None;self.original_attempt_errors={};self.original_closure_errors=[];self.final_summary=None
  # Reject an impossible closure allowance before creating the root or child.
  required=SLOT_BYTES*(3+sum(3+4*len(stages)for stages in jobs.values()))
  if required>cap:raise BudgetExceeded('whole-output budget cannot reserve complete original closure')
  if clock()>=deadline:raise DeadlineExceeded('campaign deadline at admission')
  if self.root.exists():raise LifecycleError('fresh campaign root required')
  self.root.mkdir();self.ledger.admit(0,1,'custody directory');(self.root/'custody').mkdir()
  self.campaign_slot=self.ledger.reserve_slot('campaign.json',3)
  for name,stages in jobs.items():
   key=hashlib.sha256(name.encode()).hexdigest()[:24];self.slots[(name,None)]=self.ledger.reserve_slot(key+'-condition.json',3)
   for stage in stages:self.slots[(name,stage)]=self.ledger.reserve_slot(key+'-'+stage+'.json',4)
  self.context=Context(self,(('campaign',deadline),),'campaign')
 @contextlib.contextmanager
 def active(self):
  token=_CURRENT.set(self.context)
  try:yield self.context
  finally:_CURRENT.reset(token)
 def assert_contained(self):
  if any(a.get('launched')and not a.get('containment_resolved')for a in self.attempts):raise UnresolvedContainment('original child containment unresolved; subsequent effects prohibited')
 def assert_terminal_custody(self):
  if any(not a.get('terminal_custody_saved',False)for a in self.attempts):raise UnresolvedCustody('original attempt terminal custody unavailable; subsequent work prohibited')
 def register(self,job,stage,request_id,source_id):
  self.assert_contained();self.assert_terminal_custody();c=current();c.check('register original attempt')
  slot=self.slots[(job,stage)];a={'campaign_id':self.id,'job_id':job,'stage_id':stage,'request_id':request_id,'source_id':source_id,'launched':False,'status':'admitted','containment_resolved':True,'original_returncode':None,'original_reaped':False,'failure':None,'secondary_errors':[],'start_monotonic':self.clock(),'deadline':c.deadline}
  self.attempts.append(a);return a,slot
 def note(self,a,error):
  original=self.original_attempt_errors.setdefault(id(a),[])
  if any(x is error for x in original):return
  original.append(error);record=error_record(error)
  if self.original_first_failure is None:self.original_first_failure=error;self.first_failure=record
  if isinstance(error,(BudgetExceeded,UnresolvedContainment,UnresolvedCustody))and self.fatal is None:self.fatal=error
  if a['failure']is None:a['failure']=record
  else:a['secondary_errors'].append(record)
  a['status']='failed'
 def put_terminal(self,slot,a):
  # Bounded authoritative custody; large prefix logs and complete observations
  # are separate ordinary artifacts. A digest never claims the body was saved.
  detail_error=None
  record={k:a.get(k)for k in ('campaign_id','job_id','stage_id','request_id','source_id','launched','pid','status','original_returncode','original_reaped','containment_resolved','failure','elapsed_seconds','deadline','forced_stop')}
  record.update(state='terminal',elapsed_measurement_cutoff='before this reserved publication; later clock failures remain explicit',secondary_errors=a['secondary_errors'][:3],secondary_error_count=len(a['secondary_errors']),resource_counters=None,resource_counters_observed=False,measurement_status=a.get('measurement_status','unavailable'),elapsed_observed=a.get('elapsed_observed',False),record_detail_complete=True)
  try:record['resource_counters']={k:v for k,v in self.ledger.snapshot().items()if k not in('child_leases','events')};record['resource_counters_observed']=True
  except BaseException as e:
   detail_error=e;self.note(a,e);record.update(resource_measurement_error=error_record(e),status=a['status'],failure=a['failure'],secondary_errors=a['secondary_errors'][:3],secondary_error_count=len(a['secondary_errors']))
  try:
   record.update(cleanup_events=a.get('cleanup_events',[])[:8],cleanup_event_count=len(a.get('cleanup_events',[])))
   # Check serialization before touching the precharged slot. On an encoding
   # failure, publish only the bounded original status and first-cause record.
   if len(canonical(record))>SLOT_BYTES:raise BudgetExceeded('terminal detail exceeds reserved slot')
  except BaseException as e:
   detail_error=e;self.note(a,e)
   record={k:a.get(k)for k in ('campaign_id','job_id','stage_id','request_id','source_id','launched','pid','status','original_returncode','original_reaped','containment_resolved','failure','deadline')}
   record.update(state='terminal',record_detail_complete=False,detail_error=error_record(e),measurement_status='unavailable',resource_counters=None,elapsed_seconds=None,elapsed_observed=False,secondary_error_count=len(a['secondary_errors']))
  try:slot.put(record);a['terminal_custody_path']=str(slot.path);a['terminal_custody_saved']=True;a['terminal_record_detail_complete']=record['record_detail_complete'];return detail_error
  except BaseException as e:
   a['terminal_custody_saved']=False;self.note(a,e);self.record_closure_error(e);return e
 def record_closure_error(self,error):
  if any(x is error for x in self.original_closure_errors):return
  self.original_closure_errors.append(error);self.closure_errors.append(error_record(error))
  self.record_primary_failure(error)
 def record_primary_failure(self,error):
  # The host/controller call this before entering any fallible failure closure,
  # including failures before the first worker was registered.
  if self.original_first_failure is None:self.original_first_failure=error;self.first_failure=error_record(error)
 def close_condition(self,job,record):
  self.condition_records.append(record)
  try:self.slots[(job,None)].put({'state':'condition_closed',**record})
  except BaseException as e:self.record_closure_error(e);raise
 def finish(self,error=None):
  # This return is the original controller's in-memory completion, not an
  # assertion that a record written earlier measured its own later close.
  if error is not None and self.first_failure is None:self.original_first_failure=error;self.first_failure=error_record(error)
  summary={'campaign_id':self.id,'identity_binding':self.identity_binding,'state':'campaign_terminal','status':'failed'if error is not None or self.closure_errors else'completed','first_failure':self.first_failure,'outward_failure':None if error is None else error_record(error),'closure_errors':self.closure_errors[:3],'conditions_closed':len(self.condition_records),'attempts':len(self.attempts),'launched':sum(bool(a['launched'])for a in self.attempts),'unresolved_containment':sum(a['launched']and not a['containment_resolved']for a in self.attempts),'resource_counters':None,'resource_counters_observed':False,'original_deadline':self.deadline,'finished_monotonic':None,'finished_clock_observed':False,'terminal_custody_saved':False,'custody_boundary':'record precedes its own close; original controller must check all descriptor closes and final output before success'}
  self.final_summary=summary
  def failed(e):
   self.record_closure_error(e);summary['status']='failed'
   if self.first_failure is None:self.original_first_failure=e;self.first_failure=error_record(e)
   summary['first_failure']=self.first_failure;summary['closure_errors']=self.closure_errors[:3]
  try:
   try:summary['resource_counters']={k:v for k,v in self.ledger.snapshot().items()if k not in('child_leases','events')};summary['resource_counters_observed']=True
   except BaseException as e:failed(e)
   try:summary['finished_monotonic']=self.clock();summary['finished_clock_observed']=True
   except BaseException as e:failed(e)
   try:self.campaign_slot.put(summary);summary['terminal_custody_saved']=True
   except BaseException as e:
    failed(e)
    # At most one reserved fallback; never claim an unsuccessful durable write.
    fallback={k:summary[k]for k in ('campaign_id','state','status','first_failure','outward_failure','original_deadline','finished_monotonic','finished_clock_observed','custody_boundary')}
    fallback.update(detail_complete=False,resource_counters=None,resource_counters_observed=False,closure_errors=self.closure_errors[:2])
    try:self.campaign_slot.put(fallback);summary['terminal_custody_saved']=True;summary['terminal_detail_complete']=False
    except BaseException as secondary:failed(secondary)
  finally:
   for slot in [self.campaign_slot,*self.slots.values()]:
    try:slot.close()
    except BaseException as e:failed(e)
   # No persistence is invented after descriptors close. The actual outer API
   # consumes this final disposition; it cannot accept the earlier receipt alone.
   try:
    instant=self.clock();summary['descriptor_close_completed_monotonic']=instant
    summary['descriptor_close_clock_observed']=True
    if instant>=self.deadline:failed(DeadlineExceeded('original campaign deadline after all descriptor closes'))
   except BaseException as e:
    summary['descriptor_close_completed_monotonic']=None;summary['descriptor_close_clock_observed']=False;failed(e)
   if self.closure_errors:summary['status']='failed';summary['closure_errors']=self.closure_errors[:3]
  return summary
 def require_outer_success(self,summary,label):
  # Called immediately before and after the real final API output callback.
  # This never restarts the original deadline or writes a fictitious receipt.
  if summary is not self.final_summary:raise LifecycleError('unbound final controller completion')
  try:
   instant=self.clock();summary['outer_boundary_monotonic']=instant;summary['outer_boundary_label']=label
   if instant>=self.deadline:raise DeadlineExceeded('original campaign deadline at '+label)
   if summary['status']!='completed' or self.closure_errors:
    if self.original_closure_errors:raise self.original_closure_errors[0]
    raise LifecycleError('original controller closure failed')
  except BaseException as error:
   self.record_closure_error(error);summary['status']='failed';summary['outer_failure']=error_record(error);summary['closure_errors']=self.closure_errors[:3]
   if self.first_failure is None:self.original_first_failure=error;self.first_failure=error_record(error)
   summary['first_failure']=self.first_failure
   raise
