"""Original postprediction target custody; no receipt or callback issues authority.

Concrete reads/writes are future operator actions. BUILD exercises only declared
invented metadata and inert leaves; genuine source qualification remains absent.
"""
import hashlib,os,stat,time
from pathlib import Path
import io_contract as io
import analysis
from scientific_contract import profile_sha256
from source_validation import SourceValidationOwner

def digest(raw):return hashlib.sha256(raw).hexdigest()
def identity(value):return tuple(getattr(value,k)for k in('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns'))
def target_descriptor(value):
 io.fields(value,['path','bytes','sha256','panel_sha256','scientific_profile_sha256','source_targets_sha256'])
 p=value['path'];io.need(type(p)is str and Path(p).is_absolute()and '\0'not in p and all(x not in('.','..')for x in p.split('/')[1:]),'absolute confined original target path')
 io.need(type(value['bytes'])is int and 0<value['bytes']<=io.MAX_JSON,'selected complete target extent, not authoring member cap')
 for k in('sha256','panel_sha256','scientific_profile_sha256','source_targets_sha256'):
  io.need(type(value[k])is str and analysis.SHA.fullmatch(value[k]),'exact target selection identity')
 return value

def validate_targets(raw,panel_raw,source_targets_raw,selection):
 """Complete structural join only; authentic origin is a separate live-owner gate."""
 target_descriptor(selection);io.need(type(raw)is bytes and len(raw)==selection['bytes']and digest(raw)==selection['sha256'],'same complete selected target bytes')
 p=io.strict(panel_raw);records=analysis.panel(p);profile=profile_sha256(p['scientific_profile'])
 io.need(panel_raw==io.encoded(p)and digest(panel_raw)==selection['panel_sha256']and profile==selection['scientific_profile_sha256']and digest(source_targets_raw)==selection['source_targets_sha256'],'original panel/profile/source target selection join')
 gold=io.strict(raw);io.fields(gold,['panel_sha256','scientific_profile_sha256','records'])
 io.need(raw==io.encoded(gold)and gold['panel_sha256']==selection['panel_sha256']and gold['scientific_profile_sha256']==profile,'canonical selected target profile/panel')
 io.need(type(gold['records'])is list and len(gold['records'])==727,'whole727 target rows')
 targets={}
 for row in gold['records']:
  io.fields(row,['recording_id','events']);rid=row['recording_id']
  io.need(type(rid)is str and rid in records and rid not in targets,'unique full target membership')
  targets[rid]=analysis.interval_list(row['events'],records[rid]['duration_seconds'])
 io.need(list(targets)==sorted(records),'complete canonical target order')
 source={'panel_sha256':selection['panel_sha256'],'scientific_profile_sha256':profile,'records':[{'recording_id':rid,'events':targets[rid]}for rid in targets if records[rid]['cohort']=='CHB']}
 io.need(io.encoded(source)==source_targets_raw,'same actual original canonical686 CHB target subset')
 io.need(sum(len(targets[rid])for rid in targets if records[rid]['cohort']=='Siena')==47,'all47 original Siena T1 entries retained')
 return gold

class _RetainedIO:
 def __init__(self,owner,path,kind):
  self.owner=owner;self.path=Path(path);self.kind=kind;self.started=False;self.complete=False
  self.fds=[];self.first_error=None;self.secondary_errors=[];self.close_attempted=False;self.close_completed=False
  self.before=None;self.after=None;self.bytes_observed=0;self.raw=None
 def retain(self,error):
  if self.first_error is None:self.first_error=error
  else:self.secondary_errors.append(error)
 def close(self):
  self.close_attempted=bool(self.fds);clean=True
  for fd in reversed(self.fds):
   try:os.close(fd)
   except BaseException as error:clean=False;self.retain(error)
  self.close_completed=bool(self.fds)and clean
 def summary(self):
  return {'kind':self.kind,'path':str(self.path),'started':self.started,'complete':self.complete,'fds_acquired':len(self.fds),'close_attempted':self.close_attempted,'close_completed':self.close_completed,'bytes_observed':self.bytes_observed,'before':self.before,'after':self.after,'first_error':None if self.first_error is None else repr(self.first_error),'secondary_errors':[repr(e)for e in self.secondary_errors]}

class _Read(_RetainedIO):
 def __init__(self,owner,path,extent,pin,kind):
  super().__init__(owner,path,kind);self.extent=extent;self.pin=pin;self.parts=[]
 def run(self):
  io.need(not self.started,'one original target/stream read');self.started=True;budget=self.owner.execution.budget
  try:
   self.owner.require_io()
   io.need(self.path.is_absolute()and self.path.parts[0]=='/'and all(p not in('','.','..')for p in self.path.parts[1:]),'absolute confined snapshot path')
   io.need(type(self.extent)is int and 0<self.extent<=io.MAX_JSON,'bounded selected snapshot extent')
   budget.reserve_postprediction_read(self.extent+1)
   flags=os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK
   # Keep every acquired directory descriptor before any subsequent operation.
   fd=os.open('/',flags|os.O_DIRECTORY);self.fds.append(fd)
   io.need(stat.S_ISDIR(os.fstat(fd).st_mode),'ordinary root directory')
   for part in self.path.parts[1:-1]:
    budget.check();fd=os.open(part,flags|os.O_DIRECTORY,dir_fd=fd);self.fds.append(fd)
    io.need(stat.S_ISDIR(os.fstat(fd).st_mode),'ordinary confined directory')
   budget.check();fd=os.open(self.path.name,flags,dir_fd=fd);self.fds.append(fd)
   before=os.fstat(fd);self.before=identity(before)
   io.need(stat.S_ISREG(before.st_mode)and before.st_nlink==1 and before.st_size==self.extent,'exact ordinary single-link selected extent')
   h=hashlib.sha256()
   while True:
    budget.check();chunk=os.read(fd,min(65536,self.extent+1-self.bytes_observed))
    if not chunk:break
    self.parts.append(chunk);self.bytes_observed+=len(chunk);h.update(chunk)
    io.need(self.bytes_observed<=self.extent,'selected snapshot overflow witness retained')
   after=os.fstat(fd);self.after=identity(after)
   io.need(self.bytes_observed==self.extent and self.before==self.after and h.hexdigest()==self.pin,'unchanged complete original target/stream snapshot')
  except BaseException as error:self.retain(error)
  finally:self.close()
  if self.first_error is None:
   try:budget.check();self.raw=b''.join(self.parts);self.complete=True
   except BaseException as error:self.retain(error)
  if self.first_error is not None:raise self.first_error
  return self

class _Write(_RetainedIO):
 def __init__(self,owner,path,raw,kind):super().__init__(owner,path,kind);self.expected_raw=raw
 def run(self):
  io.need(not self.started and type(self.expected_raw)is bytes,'one original bounded write');self.started=True;budget=self.owner.execution.budget
  try:
   self.owner.require_io()
   io.need(0<len(self.expected_raw)<=io.MAX_JSON,'complete bounded postprediction artifact')
   budget.reserve_postprediction_write(len(self.expected_raw));budget.check()
   io.need(self.path.is_absolute()and self.path.parts[0]=='/'and all(p not in('','.','..')for p in self.path.parts[1:]),'absolute confined artifact path')
   flags=os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK
   fd=os.open('/',flags|os.O_DIRECTORY);self.fds.append(fd)
   io.need(stat.S_ISDIR(os.fstat(fd).st_mode),'ordinary root directory')
   for part in self.path.parts[1:-1]:
    budget.check();fd=os.open(part,flags|os.O_DIRECTORY,dir_fd=fd);self.fds.append(fd)
    io.need(stat.S_ISDIR(os.fstat(fd).st_mode),'ordinary confined directory')
   budget.check();fd=os.open(self.path.name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_NONBLOCK,0o600,dir_fd=fd);self.fds.append(fd)
   before=os.fstat(fd);self.before=identity(before);io.need(stat.S_ISREG(before.st_mode)and before.st_nlink==1,'new ordinary single-link artifact')
   while self.bytes_observed<len(self.expected_raw):
    budget.check();part=self.expected_raw[self.bytes_observed:self.bytes_observed+65536];n=os.write(fd,part)
    io.need(type(n)is int and 0<n<=len(part),'complete original artifact write progress');self.bytes_observed+=n
   os.fchmod(fd,0o444);self.after=identity(os.fstat(fd));io.need(self.after[2]==len(self.expected_raw),'full original artifact extent')
  except BaseException as error:self.retain(error)
  finally:self.close()
  if self.first_error is None:
   try:budget.check();self.complete=True
   except BaseException as error:self.retain(error)
  if self.first_error is not None:raise self.first_error
  return self

_TARGET=object()
class ProtectedTargetOwner:
 """One original target/analysis attempt, retained before all external effects."""
 def __init__(self,token,execution):
  io.need(token is _TARGET,'only original campaign acquisition')
  self.execution=execution;self.source_owner=execution.source_owner;self.selection=execution.target_selection
  self.selection_raw=io.encoded(self.selection);self.started=False;self.capture_complete=False;self.released=False;self.complete=False
  self.reads=[];self.writes=[];self.first_error=None;self.secondary_errors=[];self.target_read=None
  self.panel_raw=None;self.stream_raw=None;self.seal_raw=None;self.evidence=None;self.gold_raw=None;self.packet_raw=None
 def retain(self,error):
  if self.first_error is None:self.first_error=error
  elif error is not self.first_error:self.secondary_errors.append(error)
 def require_original(self):
  from campaign_owner import CampaignOwner
  e=self.execution
  io.need(type(e)is CampaignOwner and e.target_owner is self and e.source_owner is self.source_owner and e.target_selection is self.selection,'same original campaign/source/target owner chain')
  io.need(type(self.source_owner)is SourceValidationOwner,'actual source validation owner')
  self.source_owner.require_target_selection(self.selection);io.need(io.encoded(self.selection)==self.selection_raw,'unchanged original target selection')
  p=io.strict(e.panel_raw);analysis.panel(p)
  self.source_owner.require_original(e.panel_raw,e.reference_raw,e.source_targets_raw,profile_sha256(p['scientific_profile']))
  io.need(e.complete and e.first_error is None and e.receipt_write_completed,'complete original campaign before protected target access')
  e.budget.check();target_descriptor(self.selection)
  io.need(self.selection['panel_sha256']==digest(e.panel_raw)and self.selection['source_targets_sha256']==digest(e.source_targets_raw)and self.selection['scientific_profile_sha256']==profile_sha256(p['scientific_profile']),'source-owned target selection joins original campaign inputs')
  return p
 def require_io(self):
  p=self.require_original()
  io.need(self.started and self.first_error is None,'same active error-free target attempt before every I/O effect')
  self.source_owner.require_qualified('protected_target_admission',digest(self.selection_raw))
  if p['scientific_profile']['label_profile']=='C2_edf_aligned':
   self.source_owner.require_qualified('C2_target_alignment',digest(io.encoded({'panel_sha256':self.selection['panel_sha256'],'scientific_profile_sha256':self.selection['scientific_profile_sha256'],'targets_sha256':self.selection['sha256']})))
  return self
 def read_snapshot(self,path,extent,pin,kind):
  item=_Read(self,path,extent,pin,kind);self.reads.append(item)
  return item.run()
 def write_snapshot(self,path,raw,kind):
  item=_Write(self,path,raw,kind);self.writes.append(item);item.run()
  # This original closed write is read back through another retained reader.
  observed=self.read_snapshot(path,len(raw),digest(raw),kind+' readback')
  io.need(observed.raw==raw,'same complete closed written artifact');return item
 def capture(self):
  """Fixed original pipeline only; there is no supplied provider or callback."""
  io.need(not self.started,'one original target attempt');self.started=True
  try:
   p=self.require_original();self.panel_raw=self.execution.panel_raw
   self.source_owner.require_qualified('protected_target_admission',digest(self.selection_raw))
   if p['scientific_profile']['label_profile']=='C2_edf_aligned':
    self.source_owner.require_qualified('C2_target_alignment',digest(io.encoded({'panel_sha256':self.selection['panel_sha256'],'scientific_profile_sha256':self.selection['scientific_profile_sha256'],'targets_sha256':self.selection['sha256']})))
   self.stream_raw={}
   for arm in analysis.ARMS:
    original=self.execution.stream_raw[arm]
    item=self.read_snapshot(self.execution.root/(arm+'-stream.json'),len(original),digest(original),'frozen '+arm+' stream')
    io.need(item.raw==original,'same original emitted complete stream');self.stream_raw[arm]=item.raw
   self.evidence=self.execution.analysis_evidence(self.panel_raw,self.stream_raw)
   from prepare_analysis import build_seal
   self.seal_raw=build_seal(self,self.evidence)
   self.write_snapshot(self.execution.root/'analysis-seal.json',self.seal_raw,'original prediction seal')
   # Recheck the same live authority after seal publication, before target open.
   self.require_original();self.source_owner.require_qualified('protected_target_admission',digest(self.seal_raw))
   self.target_read=_Read(self,self.selection['path'],self.selection['bytes'],self.selection['sha256'],'protected targets')
   self.reads.append(self.target_read);self.target_read.run()
   io.need(self.target_read.complete and self.target_read.close_completed,'closed successful original target read')
   self.source_owner.require_target_content(self.target_read.raw)
   validate_targets(self.target_read.raw,self.panel_raw,self.execution.source_targets_raw,self.selection)
   self.execution.budget.check();self.gold_raw=self.target_read.raw;self.capture_complete=True
  except BaseException as error:self.retain(error);raise
  return self
 def release_for_analysis(self):
  io.need(not self.released,'one original release; a rejected repeat cannot rewrite its first result')
  try:
   self.require_io();io.need(self.capture_complete and not self.released and self.first_error is None,'one complete closed target release')
   io.need(self.target_read is not None and self.target_read in self.reads and self.target_read.complete and self.target_read.close_completed and self.gold_raw is self.target_read.raw,'same original closed target bytes')
   self.source_owner.require_target_content(self.gold_raw)
   validate_targets(self.gold_raw,self.panel_raw,self.execution.source_targets_raw,self.selection)
   self.released=True;return self.gold_raw
  except BaseException as error:self.retain(error);raise
 def publish_analysis(self,packet):
  io.need(not self.complete,'one original completed analysis publication')
  try:
   self.require_original();io.need(self.released and self.capture_complete and not self.complete and self.first_error is None,'one original analysis publication')
   raw=io.encoded(packet);self.write_snapshot(self.execution.root/'analysis.json',raw,'complete analysis packet')
   self.execution.budget.check();self.packet_raw=raw;self.complete=True;self.execution.analysis_complete=True
  except BaseException as error:self.retain(error);raise
  return self
 def observation(self):
  return {'schema':'neural012_protected_target_owner_observation_v1','target_selection_sha256':digest(self.selection_raw),'started':self.started,'capture_complete':self.capture_complete,'released':self.released,'analysis_complete':self.complete,'reads':[x.summary()for x in self.reads],'writes':[x.summary()for x in self.writes],'seal_sha256':None if self.seal_raw is None else digest(self.seal_raw),'packet_sha256':None if self.packet_raw is None else digest(self.packet_raw),'first_error':None if self.first_error is None else repr(self.first_error),'secondary_errors':[repr(e)for e in self.secondary_errors],'source_qualified':False,'native_isolation_qualified':False,'scientifically_qualified':False}

def acquire_target_owner(execution):
 from campaign_owner import CampaignOwner
 io.need(type(execution)is CampaignOwner and execution.target_owner is None,'one target owner acquired by original campaign')
 owner=ProtectedTargetOwner(_TARGET,execution);execution.target_owner=owner
 return owner
