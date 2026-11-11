"""Own future full source observations; matching bytes never issues authenticity.

No receipt loader or caller-provided observation can create a completed owner.
The independent authentic release/adjudication issuer remains unavailable.
"""
import hashlib,math,os,stat,time
from pathlib import Path,PurePosixPath
import io_contract as io
import source_evidence as evidence
from scientific_contract import require_source_authority,SourceQualificationUnavailable,project_reference
from case_contract import phase_rows

HEADER_CAP=131328
IDENTITY_FIELDS=('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')

def identity(value):return tuple(getattr(value,k)for k in IDENTITY_FIELDS)
def digest(raw):return hashlib.sha256(raw).hexdigest()
def cloned(value):return io.strict(io.encoded(value))
def validate_limits(value):
 io.fields(value,('files','file_bytes','read_bytes','captured_bytes','projection_read_bytes','projection_chunk_bytes','wall_seconds','chunk_bytes'))
 io.need(all(type(value[k])is int and value[k]>0 for k in ('files','file_bytes','read_bytes','captured_bytes','projection_read_bytes','projection_chunk_bytes','chunk_bytes')),'explicit positive observation byte/count limits')
 io.need(value['chunk_bytes']<=1048576 and type(value['wall_seconds'])in(int,float)and math.isfinite(value['wall_seconds'])and value['wall_seconds']>0,'bounded transport chunk and finite original observation time')
 return value
def asset_path(roots,asset):
 root=roots[asset['root']];rel=asset['path'];p=PurePosixPath(rel)
 io.need(type(rel)is str and rel and not p.is_absolute()and str(p)==rel and all(x not in ('','..','.')for x in p.parts)and '\0'not in rel,'confined original asset member')
 result=Path(root)/rel
 io.need(not any(x.is_symlink()for x in(result,*result.parents)),'no source symlink ancestry')
 return result
def observation_identity(value):
 io.fields(value,('asset_id','bytes','sha256','captured_bytes','captured_sha256','before_identity','after_identity'))
 body=value['captured_bytes'];io.need(type(body)is bytes and value['captured_sha256']==digest(body),'same original captured byte prefix')
 return io.encoded({k:v for k,v in value.items()if k!='captured_bytes'})

class ObservationBudget:
 def __init__(self,limits):
  self.limits=validate_limits(cloned(limits));self.started_ns=time.monotonic_ns()
  self.deadline_ns=self.started_ns+int(self.limits['wall_seconds']*1000000000)
  self.bytes_read=0;self.bytes_captured=0;self.projection_bytes_read=0;self.read_calls=0;self.files_started=0
 def check(self):io.need(time.monotonic_ns()<=self.deadline_ns,'same original source-observation deadline')
 def begin_file(self):
  self.check();self.files_started+=1;io.need(self.files_started<=self.limits['files'],'whole source file budget')
 def charge_read(self,n):
  self.bytes_read+=n;self.read_calls+=1
  io.need(self.bytes_read<=self.limits['read_bytes'],'cumulative original source-read byte budget');self.check()
 def charge_capture(self,n):
  self.bytes_captured+=n
  io.need(self.bytes_captured<=self.limits['captured_bytes'],'cumulative original captured-metadata budget');self.check()
 def charge_projection(self,n):
  io.need(type(n)is int and n>=0,'explicit nonnegative logical projection-read charge')
  self.projection_bytes_read+=n
  io.need(self.projection_bytes_read<=self.limits['projection_read_bytes'],'cumulative original projection-read byte budget');self.check()

class AssetReadOwner:
 """Original descriptor/open/read/close occurrence, retained before its first effect."""
 def __init__(self,collection,asset,path):
  self.collection=collection;self.asset=cloned(asset);self.path=path;self.path_raw=str(path);self.fd=None;self.started=False
  self.opened_descriptor=None;self.open_attempted=False;self.close_attempted=False;self.close_completed=False
  self.before=None;self.after=None;self.total=0;self.calls=0;self.complete=False
  self.first_error=None;self.secondary_errors=[];self.observation=None;self.observation_raw=None
 def retain(self,error):
  if self.first_error is None:self.first_error=error
  else:self.secondary_errors.append(error)
 def run(self):
  io.need(not self.started,'one original asset-read occurrence');self.started=True
  budget=self.collection.budget;asset=self.asset;captured=bytearray();header_extent=None;hasher=hashlib.sha256()
  try:
   budget.begin_file();self.open_attempted=True
   self.fd=os.open(self.path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);self.opened_descriptor=self.fd
   self.before=os.fstat(self.fd)
   io.need(stat.S_ISREG(self.before.st_mode)and self.before.st_nlink==1 and self.before.st_size==asset['bytes'],'exact single-link ordinary source extent')
   while True:
    budget.check();block=os.read(self.fd,min(budget.limits['chunk_bytes'],asset['bytes']+1-self.total));self.calls+=1
    io.need(type(block)is bytes,'original read returns bytes');budget.charge_read(len(block))
    if not block:break
    self.total+=len(block);io.need(self.total<=asset['bytes'],'no source byte beyond selected original extent');hasher.update(block)
    if asset['capture']=='whole_metadata':captured.extend(block)
    elif asset['capture']=='edf_header':
     bound=HEADER_CAP if header_extent is None else header_extent
     captured.extend(block[:max(0,bound-len(captured))])
     if header_extent is None and len(captured)>=256:
      io.need(bytes(captured[:8]).decode('ascii').strip()=='0','original EDF version 0')
      header_extent=int(bytes(captured[184:192]).decode('ascii').strip())
      channels=int(bytes(captured[252:256]).decode('ascii').strip())
      io.need(0<channels<=512 and header_extent==256*(channels+1)and 256<header_extent<=HEADER_CAP and header_extent<=asset['bytes'],'original complete fixed EDF header extent')
      del captured[header_extent:]
   self.after=os.fstat(self.fd);budget.check()
   io.need(self.total==asset['bytes']and hasher.hexdigest()==asset['sha256']and identity(self.before)==identity(self.after),'unchanged complete source bytes and selected identity')
   if asset['capture']=='edf_header':io.need(header_extent is not None and len(captured)==header_extent,'complete original EDF header prefix')
   elif asset['capture']=='whole_metadata':io.need(len(captured)==asset['bytes'],'complete original metadata body')
   else:io.need(asset['capture']=='none'and not captured,'no raw sample payload retained')
   budget.charge_capture(len(captured))
  except BaseException as error:self.retain(error)
  finally:
   if self.fd is not None:
    self.close_attempted=True
    try:os.close(self.fd);self.close_completed=True;self.fd=None
    except BaseException as error:self.retain(error)
  if self.first_error is None:
   try:
    budget.check();io.need(self.close_completed,'completed original descriptor close')
    body=bytes(captured)
    self.observation={'asset_id':asset['asset_id'],'bytes':self.total,'sha256':hasher.hexdigest(),'captured_bytes':body,'captured_sha256':digest(body),'before_identity':identity(self.before),'after_identity':identity(self.after)}
    self.observation_raw=observation_identity(self.observation);self.complete=True
   except BaseException as error:self.retain(error)
  if self.first_error is not None:
   for error in self.secondary_errors:self.first_error.add_note('secondary original source close/read failure: '+repr(error))
   raise self.first_error
  return self
 def require_original(self):
  io.need(type(self)is AssetReadOwner and self.complete and self.first_error is None and self.close_completed and self.fd is None,'same successful original source-read owner')
  io.need(str(self.path)==self.path_raw==str(Path(self.collection.roots[self.asset['root']])/self.asset['path']),'same original source path and selected root/member')
  io.need(self.observation_raw==observation_identity(self.observation),'same immutable original observation')
  io.need(self.observation['bytes']==self.asset['bytes']and self.observation['sha256']==self.asset['sha256']and self.observation['before_identity']==self.observation['after_identity'],'source observation still bound to descriptor and extent')
  return self.observation

class SourceValidationOwner:
 """Full original file observations and joins, separately unqualified authentic origin."""
 def __init__(self,selection_raw,roots,limits):
  io.need(type(selection_raw)is bytes,'explicit original source selection bytes')
  self.selection_raw=selection_raw;self.selection=evidence.validate_selection(io.strict(selection_raw))
  self.selection_canonical=io.encoded(self.selection);self.roots=cloned(roots);self.roots_raw=io.encoded(self.roots)
  io.need(type(self.roots)is dict and self.roots,'explicit source roots')
  for name,root in self.roots.items():
   io.need(type(name)is str and name and type(root)is str and Path(root).is_absolute()and '..'not in Path(root).parts and '\0'not in root,'absolute original source-root selection')
  self.limits=validate_limits(cloned(limits));self.limits_raw=io.encoded(self.limits)
  self.assets=cloned(evidence.asset_requirements(self.selection));self.assets_raw=io.encoded(self.assets)
  io.need(type(self.assets)is list and self.assets and len(self.assets)<=self.limits['files'],'complete derived source roster within selected file budget')
  ids=set();paths=set();capture=0
  for asset in self.assets:
   io.fields(asset,('asset_id','root','path','bytes','sha256','capture'))
   aid=asset['asset_id'];io.need(type(aid)is str and aid and len(aid)<=256 and aid not in ids,'unique original asset identity');ids.add(aid)
   io.need(asset['root']in self.roots and type(asset['bytes'])is int and 0<asset['bytes']<=self.limits['file_bytes'],'selected source root and exact positive extent')
   io.need(type(asset['sha256'])is str and len(asset['sha256'])==64 and all(c in '0123456789abcdef'for c in asset['sha256']),'exact selected SHA256 syntax')
   io.need(asset['capture']in('none','edf_header','whole_metadata'),'closed source capture mode')
   path=asset_path(self.roots,asset);io.need(str(path)not in paths,'one original owned path per asset');paths.add(str(path))
   capture+=min(asset['bytes'],HEADER_CAP)if asset['capture']=='edf_header'else asset['bytes']if asset['capture']=='whole_metadata'else 0
  io.need(sum(a['bytes']+1 for a in self.assets)<=self.limits['read_bytes']and capture<=self.limits['captured_bytes'],'complete source plus EOF probes and worst-case metadata capture admitted before reads')
  self.target_selection=cloned(self.selection['target_selection']);self.target_raw=io.encoded(self.target_selection)
  evidence.validate_target_selection(self.selection,self.target_selection)
  io.need(str(Path(self.target_selection['path']))not in paths,'protected target selection is never a source observation asset')
  self.budget=None;self.read_owners=[];self.asset_owners={};self.observations={};self.validation=None;self.validation_raw=None;self.raw_observations_complete=False;self.projection_owner=None
  self.started=False;self.complete=False;self.first_error=None;self.secondary_errors=[];self.qualification_error=None;self.qualification_errors=[]
 @property
 def successfully_observed(self):return self.complete and self.first_error is None
 def retain(self,error):
  if self.first_error is None:self.first_error=error
  else:self.secondary_errors.append(error)
 def selection_intact(self):
  io.need(io.encoded(self.selection)==self.selection_canonical and io.encoded(self.roots)==self.roots_raw and io.encoded(self.limits)==self.limits_raw and io.encoded(self.assets)==self.assets_raw,'same original source-selection/root/resource descriptors')
  io.need(io.encoded(evidence.validate_selection(io.strict(self.selection_raw)))==self.selection_canonical and io.encoded(evidence.asset_requirements(self.selection))==self.assets_raw,'same complete source requirements')
 def observe(self):
  io.need(not self.started,'one original full source-observation collection');self.started=True
  try:
   self.selection_intact();self.budget=ObservationBudget(self.limits)
   for asset in self.assets:
    self.budget.check();owner=AssetReadOwner(self,asset,asset_path(self.roots,asset));self.read_owners.append(owner);self.asset_owners[asset['asset_id']]=owner
    result=owner.run();io.need(result is owner,'same original asset-read owner')
    self.observations[asset['asset_id']]=owner.require_original()
   self.validation=evidence.validate_observations(self.selection,self.observations)
   self.validation_raw=io.encoded(self.validation);self.selection_intact();self.budget.check();self.raw_observations_complete=True
   from source_projection import ProjectionValidationOwner
   self.projection_owner=ProjectionValidationOwner(self)
   projected=self.projection_owner.run()
   io.need(projected is self.projection_owner and type(projected)is ProjectionValidationOwner,'same retained original full projection-validation owner')
   self.projection_owner.require_original(self);self.budget.check();self.complete=True
  except BaseException as error:self.retain(error)
  if self.first_error is not None:raise self.first_error
  return self
 def require_raw_observed(self):
  io.need(type(self)is SourceValidationOwner and self.raw_observations_complete and self.first_error is None and self.started,'same complete original raw source-observation owner')
  self.budget.check()
  self.selection_intact();io.need(len(self.read_owners)==len(self.assets)==len(self.observations)==len(self.asset_owners)and set(self.asset_owners)==set(self.observations),'full original source observation support')
  for asset,owner in zip(self.assets,self.read_owners):
   io.need(owner.collection is self and owner.asset==asset and self.asset_owners[asset['asset_id']]is owner and self.observations[asset['asset_id']]is owner.observation,'same original per-asset occurrence and descriptor')
   owner.require_original()
  io.need(io.encoded(self.validation)==self.validation_raw and io.encoded(evidence.validate_observations(self.selection,self.observations))==self.validation_raw,'same complete source/profile/header/annotation joins')
  self.budget.check()
  return self
 def require_observed(self):
  self.require_raw_observed()
  io.need(self.successfully_observed,'same completed full source and projection validation owner')
  from source_projection import ProjectionValidationOwner
  io.need(type(self.projection_owner)is ProjectionValidationOwner,'original full projection-validation owner required')
  self.projection_owner.require_original(self);return self
 def require_original(self,panel_raw,reference_raw,source_targets_raw,profile_pin):
  self.require_observed()
  evidence.validate_consumer_binding(self.selection,panel_raw,reference_raw,source_targets_raw,profile_pin)
  self.require_target_selection(self.target_selection);return self
 def require_phase(self,case,reference_raw,logical_job,reference_view='full'):
  self.require_observed()
  io.need(reference_view in('full','projected'),'explicit full or projected phase reference view')
  if case['arm']=='timing':
   io.need(reference_raw is None,'timing phase has no source reference operand');projected=None
  else:
   selected=io.encoded(self.selection['reference'])
   projected=io.encoded(project_reference(self.selection['reference'],phase_rows(case)))
   io.need(type(reference_raw)is bytes and reference_raw==(selected if reference_view=='full'else projected),'same exact selected full or phase-projected physical reference bytes')
  evidence.validate_phase_binding(self.selection,case,projected,logical_job);return self
 def require_target_selection(self,value):
  self.selection_intact()
  io.need(value is self.target_selection and io.encoded(value)==self.target_raw,'same predeclared original protected-target selection')
  evidence.validate_target_selection(self.selection,value);return value
 def require_target_content(self,raw):
  self.require_observed();selected=self.require_target_selection(self.target_selection)
  io.need(type(raw)is bytes and len(raw)==selected['bytes']and digest(raw)==selected['sha256'],'same exact original protected target bytes')
  value=io.strict(raw);io.fields(value,('panel_sha256','scientific_profile_sha256','records'))
  io.need(raw==io.encoded(value)and value['panel_sha256']==selected['panel_sha256']and value['scientific_profile_sha256']==selected['scientific_profile_sha256'],'canonical complete target and scientific-profile identity')
  labels=self.validation['labels'];expected={r['recording_id']for r in self.selection['panel']['records']}
  io.need(len(expected)==727 and set(labels)==expected and type(value['records'])is list and len(value['records'])==727,'complete original727 target-label support')
  seen=set()
  for row in value['records']:
   io.fields(row,('recording_id','events'));rid=row['recording_id']
   io.need(type(rid)is str and rid in expected and rid not in seen,'unique original target record');seen.add(rid)
   io.need(type(labels[rid])is list and type(row['events'])is list and io.encoded(row['events'])==io.encoded(labels[rid]),'exact typed target events from retained original label validation; no invalid or unresolved C2 substitution')
  io.need(seen==expected,'whole original target inverse');return value
 def require_qualified(self,purpose,binding_sha256):
  self.require_observed()
  if self.qualification_error is not None:raise self.qualification_error
  try:
   require_source_authority(purpose,binding_sha256)
   # No issuer return contract exists. A replaced function returning a boolean,
   # JSON receipt or None cannot turn observation into genuine qualification.
   raise SourceQualificationUnavailable('No original authentic issuer capability exists; observed source matches and supplied declarations remain unqualified')
  except BaseException as error:
   self.qualification_error=error;self.qualification_errors.append(error);raise
 def observation_report(self):
  return {'schema':'neural012_original_source_observation_v1','selection_sha256':digest(self.selection_raw),'successfully_observed':self.successfully_observed,'raw_observations_complete':self.raw_observations_complete,'projection_owner_acquired':self.projection_owner is not None,'projection_logical_read_allowance_charged':None if self.budget is None else self.budget.projection_bytes_read,'original_asset_occurrences':len(self.read_owners),'asset_outcomes':[{'asset_id':o.asset['asset_id'],'bytes_read':o.total,'read_calls':o.calls,'started':o.started,'open_attempted':o.open_attempted,'close_attempted':o.close_attempted,'close_completed':o.close_completed,'complete':o.complete,'first_error':None if o.first_error is None else repr(o.first_error),'secondary_errors':[repr(e)for e in o.secondary_errors]}for o in self.read_owners],'first_error':None if self.first_error is None else repr(self.first_error),'secondary_errors':[repr(e)for e in self.secondary_errors],'qualification_error':None if self.qualification_error is None else repr(self.qualification_error),'source_authenticity_qualified':False,'original_projection_qualified':False,'original_target_derivation_qualified':False,'native_or_scientific_qualified':False}
