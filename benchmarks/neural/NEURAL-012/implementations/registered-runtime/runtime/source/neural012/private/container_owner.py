"""Concrete future Docker custody. BUILD never calls this module's native entrypoints.

Selection identifies operator-authorized artifacts/resources; it is not an image qualification
certificate. InvocationOwner describes actual subprocess/stream/container occurrences only.
"""
import hashlib,json,os,selectors,subprocess,time,math,stat
from pathlib import Path
import io_contract as io
from execution_boundary import validate_selection,CID,digest,stage
from case_contract import validate_fit_state
class CommandFailure(RuntimeError):
 def __init__(self,observation):super().__init__(observation['error']);self.observation=observation
class InvocationOwner:
 def __init__(self,staged,selection):
  from execution_boundary import StagedCase
  io.need(type(staged)is StagedCase,'actual staging owner, never a metadata plan')
  self.staged=staged;self.selection=validate_selection(selection)
  self.started=False;self.complete=False;self.container_id=None;self.container_removed=False
  self.commands=[];self.first_error=None;self.secondary_errors=[];self.output=None;self.output_raw=None;self.receipt_write_completed=False
  self.fit_capture=None
 def retain(self,error):
  if self.first_error is None:self.first_error=error
  else:self.secondary_errors.append(error)
 def command(self,args,wall,kind,cleanup=False):
  lim=self.selection['limits'];io.need(sum(len(x.encode())+1 for x in args)<=lim['argv_bytes'],'complete argv admission')
  if not cleanup:wall=min(wall,self.staged.budget.check())
  start=time.monotonic_ns();deadline=start+int(wall*1000000000)
  item={'kind':kind,'argv':list(args),'started_ns':start,'pid':None,'returncode':None,'stdout':b'','stderr':b'','error':None,'cleanup_errors':[],'streams_closed':False,'stdout_eof':False,'stderr_eof':False,'completed_before_cleanup':False}
  self.commands.append(item);child=None;selector=None;primary=None
  try:
   child=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
    env={'HOME':str(self.staged.root/'private'),'PATH':'/usr/bin:/bin'},close_fds=True,start_new_session=True)
   item['pid']=child.pid;selector=selectors.DefaultSelector()
   for name in ('stdout','stderr'):
    stream=getattr(child,name);os.set_blocking(stream.fileno(),False);selector.register(stream,selectors.EVENT_READ,name)
   while selector.get_map():
    remaining=(deadline-time.monotonic_ns())/1000000000
    if remaining<=0:raise TimeoutError(kind+' original selected wall limit')
    for key,_ in selector.select(remaining):
     name=key.data;cap=lim[name+'_bytes'];chunk=os.read(key.fileobj.fileno(),min(65536,cap-len(item[name])+1))
     if not chunk:item[name+'_eof']=True;selector.unregister(key.fileobj);continue
     # Retain consumed prefix before refusal. One excess byte witnesses the cap violation.
     item[name]+=chunk
     if len(item[name])>cap:raise ValueError(kind+' '+name+' selected cap exceeded')
   remaining=(deadline-time.monotonic_ns())/1000000000
   if remaining<=0:raise TimeoutError(kind+' exit observation deadline')
   item['returncode']=child.wait(timeout=remaining)
   if item['returncode']!=0:raise RuntimeError(kind+' original nonzero exit '+str(item['returncode']))
   item['completed_before_cleanup']=True
  except BaseException as error:primary=error;item['error']=repr(error)
  finally:
   if child is not None:
    if primary is not None:
     try:child.kill()
     except ProcessLookupError:pass
     except BaseException as e:item['cleanup_errors'].append(repr(e))
     try:item['returncode']=child.wait(timeout=self.selection['limits']['admin_wall_seconds'])
     except BaseException as e:item['cleanup_errors'].append(repr(e))
    for name in ('stdout','stderr'):
     try:getattr(child,name).close()
     except BaseException as e:item['cleanup_errors'].append(repr(e))
   if selector is not None:
    try:selector.close()
    except BaseException as e:item['cleanup_errors'].append(repr(e))
   item['streams_closed']=child is not None and not item['cleanup_errors']
   try:item['finished_ns']=time.monotonic_ns()
   except BaseException as e:item['cleanup_errors'].append(repr(e))
  if primary is not None or item['cleanup_errors']:
   if item['error']is None:item['error']='original cleanup/final clock failure'
   raise CommandFailure(item)from primary
  return item
 def docker(self,tail,wall,kind,cleanup=False):
  s=self.selection;config=self.staged.root/'private/docker-config'
  return self.command([s['docker']['path'],'--host',s['endpoint'],'--config',str(config)]+tail,wall,kind,cleanup=cleanup)
 def retain_created_container(self,observation,argv):
  io.need(any(x is observation for x in self.commands),'same retained original command occurrence')
  io.need(observation['kind']=='original container create'and observation['argv']==argv,'same original create argv')
  io.need(observation['completed_before_cleanup']is True and observation['stdout_eof']is True and observation['stderr_eof']is True and type(observation['returncode'])is int and observation['returncode']==0,'original successful create and complete streams before cleanup')
  io.need(type(observation['pid'])is int and observation['pid']>0,'actual original create process')
  raw=observation['stdout'];io.need(type(raw)is bytes,'original byte output')
  text=raw.decode('ascii')
  if text.endswith('\n'):text=text[:-1]
  io.need(CID.fullmatch(text),'one complete original CID line, no partial/extra output')
  io.need(self.container_id is None,'one original created container')
  self.container_id=text;self.create_observation=observation
 def custody_summary(self):
  # Diagnostic projection only; actual byte prefixes and exception objects remain
  # on this same acquired InvocationOwner even when its own receipt write fails.
  commands=[]
  for item in self.commands:
   row={k:v for k,v in item.items()if k not in('stdout','stderr')}
   row['stdout']={'bytes':len(item['stdout']),'sha256':digest(item['stdout'])}
   row['stderr']={'bytes':len(item['stderr']),'sha256':digest(item['stderr'])}
   commands.append(row)
  return {'phase':self.staged.case['phase'],'logical_job':self.staged.logical_job,'started':self.started,'complete':self.complete,'container_id':self.container_id,
   'container_removed':self.container_removed,'receipt_write_completed':self.receipt_write_completed,
   'fit_capture':None if self.fit_capture is None else self.fit_capture.observation(),
   'first_error':None if self.first_error is None else repr(self.first_error),
   'secondary_errors':[repr(e)for e in self.secondary_errors],'commands':commands,
   'raw_prefix_custody':'same retained invocation.commands objects; this JSON is diagnostic, not owner authority'}
 def run(self):
  io.need(not self.started,'one original invocation, no replay');self.started=True;s=self.selection;root=self.staged.root
  try:
   self.staged.require_original()
   io.read(s['docker']['path'],s['docker']['bytes'],s['docker']['sha256'])
   config=root/'private/docker-config';config.mkdir(mode=0o700);io.write(config/'config.json',{'auths':{}})
   image=self.docker(['image','inspect',s['image_id']],s['limits']['admin_wall_seconds'],'original image observation')
   values=io.strict(image['stdout']);io.need(type(values)is list and len(values)==1,'one original image observation')
   actual=values[0];io.need(actual['Id']==s['image_id']and actual['Os']=='linux'and not actual['Config'].get('Volumes')and actual['Config'].get('Env')==s['image_env'],'selected Linux image/environment, no implicit volumes')
   argv=list(self.staged.argv);argv[3:3]=['--config',str(config)]
   try:created=self.command(argv,s['limits']['admin_wall_seconds'],'original container create')
   except CommandFailure as failure:
    # Original successful create can precede a later pipe/selector/clock failure.
    # Register only its own complete output before propagating that first failure.
    try:self.retain_created_container(failure.observation,argv)
    except BaseException as invalid:self.secondary_errors.append(invalid)
    raise
   self.retain_created_container(created,argv);cid=self.container_id
   self.docker(['container','start','--attach',cid],s['limits']['wall_seconds'],'original candidate invocation')
   stopped=self.docker(['container','inspect',cid],s['limits']['admin_wall_seconds'],'original stopped-container observation')
   observed=io.strict(stopped['stdout']);io.need(type(observed)is list and len(observed)==1,'one original stopped-container record')
   container=observed[0];state=container['State']
   io.need(container['Id']==cid and container['Image']==s['image_id'],'same original created container/image')
   io.need(state['Status']=='exited'and all(state[k]is False for k in('Running','Paused','Restarting','OOMKilled','Dead'))and type(state['Pid'])is int and state['Pid']==0 and type(state['ExitCode'])is int and state['ExitCode']==0 and state['Error']=='','actual clean stopped process; CLI status alone is insufficient')
  except BaseException as e:self.retain(e)
  finally:
   if self.container_id is not None:
    try:
     self.docker(['container','rm','--force',self.container_id],s['limits']['admin_wall_seconds'],'original container removal',cleanup=True)
     self.container_removed=True
    except BaseException as e:self.retain(e)
  if self.first_error is None:
   try:
    io.need(self.container_removed,'same original container removal completed')
    self.staged.require_original()
    name='fit-state.json'if self.staged.case['phase']=='fit'else'prediction.json'
    cap=s['fit_state_limits']['bytes']if self.staged.case['phase']=='fit'else s['limits']['output_bytes']
    io.need({p.name for p in(root/'output').iterdir()}=={name},'one complete phase output artifact')
    self.output_raw=io.read(root/'output'/name,cap)
    self.output=io.strict(self.output_raw);self.check_output_support()
    self.complete=True
   except BaseException as e:self.retain(e)
  self.publish_receipt()
  if self.first_error is not None:raise self.first_error
  return self
 def check_output_support(self):
  out=self.output;case=self.staged.case
  if case['phase']=='fit':
   validate_fit_state(out,digest(self.staged.case_raw),case['arm'],self.selection['fit_state_limits'])
   return
  io.fields(out,['schema_version','task_id','arm','records'])
  io.need(type(out['schema_version'])is int and out['schema_version']==1 and out['task_id']==io.TASK and out['arm']==case['arm'],'same actual case/output arm')
  expected={r['recording_id']:r['duration_seconds']for r in case['query']};seen=set()
  io.need(type(out['records'])is list and len(out['records'])==len(expected),'complete original query output')
  for r in out['records']:
   io.fields(r,['recording_id','scores','events']);rid=r['recording_id']
   io.need(rid in expected and rid not in seen,'unique original query output');seen.add(rid);d=expected[rid]
   io.need(type(r['scores'])is list and len(r['scores'])==d and all(type(x)in(int,float)and math.isfinite(x)and 0<=x<=1 for x in r['scores']),'full score support')
   io.need(type(r['events'])is list,'events retained; exact scientific event inverse is checked by unchanged merger')
 def capture_fit(self):
  """Retain the exact successful original fit state before any query staging."""
  try:
   io.need(self.fit_capture is None,'one original fit capture')
   io.need(self.staged.case['phase']=='fit'and self.complete and self.first_error is None and self.container_removed and self.receipt_write_completed,'only completed removed fit invocation can publish a capture')
   self.staged.budget.check()
   capture=CapturedFit(_FIT_CAPTURE,self)
   # Acquire before publication effects; failed capture publication remains owned.
   self.fit_capture=capture
   capture.publish()
   capture.require_lineage(self.staged.case['arm'],digest(self.staged.case_raw),self.staged.manifest_raw,self.staged.logical_job)
   return capture
  except BaseException as error:
   self.complete=False;self.retain(error);raise
 def publish_receipt(self):
  root=self.staged.root;observations=[]
  try:
   for i,item in enumerate(self.commands):
    values={k:v for k,v in item.items()if k not in('stdout','stderr')}
    for name in ('stdout','stderr'):
     b=item[name];path=root/'private'/('command'+str(i)+'-'+name+'.bin')
     with path.open('xb')as f:f.write(b)
     values[name]={'file':path.name,'bytes':len(b),'sha256':digest(b)}
    observations.append(values)
   receipt={'schema':'neural012_actual_invocation_v3','phase':self.staged.case['phase'],'logical_job':self.staged.logical_job,'case_sha256':digest(self.staged.case_raw),'programme_sha256':digest(self.staged.manifest_raw),
    'runtime_selection_sha256':digest(io.encoded(self.selection)),'view':self.staged.view,'commands':observations,
    'actual_container_id':self.container_id,'container_removal_command_completed':self.container_removed,
    'invocation_complete':self.complete,'first_error':None if self.first_error is None else repr(self.first_error),
    'secondary_errors':[repr(e)for e in self.secondary_errors],
    'output':None if self.output_raw is None else{'bytes':len(self.output_raw),'sha256':digest(self.output_raw)},
    'parent_fit_capture':None if self.staged.fit_capture is None else self.staged.fit_capture.observation(),
    'cleanup_after_campaign_deadline':time.monotonic_ns()>self.staged.budget.deadline_ns,'actual_fit_use_verified':False,'native_isolation_qualified':False,'scientifically_qualified':False,
    'costs':{'cpu':None,'physical_io':None,'peak_memory':None,'retained_stream_bytes':sum(len(c['stdout'])+len(c['stderr'])for c in self.commands)}}
   io.write(root/'private/invocation.json',receipt)
   self.receipt_write_completed=True
  except BaseException as e:self.complete=False;self.retain(e)

_FIT_CAPTURE=object()
class CapturedFit:
 """Original in-memory occurrence plus read-only JSON snapshot; never a learned-use certificate."""
 def __init__(self,token,owner):
  io.need(token is _FIT_CAPTURE and type(owner)is InvocationOwner,'only original fit owner creates capture')
  io.need(owner.staged.case['phase']=='fit'and owner.complete and owner.first_error is None and owner.container_removed and owner.receipt_write_completed,'actual successful removed fit occurrence')
  self.owner=owner;self.raw=owner.output_raw;self.limits=io.strict(io.encoded(owner.selection['fit_state_limits']))
  io.need(type(self.raw)is bytes and 0<len(self.raw)<=self.limits['bytes'],'bounded original fit artifact bytes')
  self.fit_case_sha256=digest(owner.staged.case_raw);self.programme_raw=owner.staged.manifest_raw
  self.arm=owner.staged.case['arm'];self.logical_job=io.strict(io.encoded(owner.staged.logical_job))
  validate_fit_state(io.strict(self.raw),self.fit_case_sha256,self.arm,self.limits)
  self.path=owner.staged.root/'private/captured-fit-state.json'
  self.started=False;self.complete=False;self.captured_ns=None;self.snapshot_write_started=False
  self.snapshot_write_completed=False;self.receipt_write_completed=False;self.first_error=None;self.secondary_errors=[]
 def publish(self):
  io.need(not self.started and self.owner.fit_capture is self,'one acquired original capture before publication')
  self.started=True;stream=None;primary=None
  try:
   self.owner.staged.budget.check();self.snapshot_write_started=True
   stream=self.path.open('xb');io.need(stream.write(self.raw)==len(self.raw),'complete original state snapshot write')
  except BaseException as error:primary=error
  finally:
   if stream is not None:
    try:stream.close()
    except BaseException as error:
     if primary is None:primary=error
     else:self.secondary_errors.append(error)
  try:
   if primary is not None:raise primary
   self.snapshot_write_completed=True
   self.path.chmod(0o444);io.need(io.read(self.path,self.limits['bytes'],digest(self.raw))==self.raw,'exact immutable captured bytes')
   self.captured_ns=time.monotonic_ns()
   # This pre-return observation cannot assert its own durable write completion.
   io.write(self.owner.staged.root/'private/fit-capture.json',self.observation())
   self.receipt_write_completed=True;self.complete=True
  except BaseException as error:
   self.first_error=error;raise
  return self
 def require_lineage(self,arm,fit_case_sha256,manifest_raw,logical_job):
  o=self.owner
  io.need(type(o)is InvocationOwner and o.fit_capture is self and o.complete and o.first_error is None and o.container_removed and o.receipt_write_completed and self.complete and self.first_error is None and self.receipt_write_completed,'same retained complete fit owner and capture')
  io.need(self.raw is o.output_raw and self.programme_raw is o.staged.manifest_raw,'same original bytes, not a reconstructed receipt')
  io.need(arm==self.arm==o.staged.case['arm']and fit_case_sha256==self.fit_case_sha256==digest(o.staged.case_raw),'same arm and fitted case lineage')
  io.need(manifest_raw==self.programme_raw and logical_job==self.logical_job==o.staged.logical_job,'same selected code and host logical job')
  validate_fit_state(io.strict(self.raw),fit_case_sha256,arm,self.limits)
  return self
 def require_original(self,case,manifest_raw,logical_job,budget):
  io.need(case['phase']=='predict','captured fit is a prediction input only')
  self.require_lineage(case['arm'],case['fit_case_sha256'],manifest_raw,logical_job)
  io.need(budget is self.owner.staged.budget,'same original campaign budget')
  budget.check()
  io.need(io.read(self.path,self.limits['bytes'],digest(self.raw))==self.raw,'same retained immutable captured state')
  return self
 def observation(self):
  return {'schema':'neural012_fit_capture_observation_v1','logical_job':self.logical_job,'arm':self.arm,
   'fit_case_sha256':self.fit_case_sha256,'programme_sha256':digest(self.programme_raw),
   'fit_container_id':self.owner.container_id,'artifact':{'bytes':len(self.raw),'sha256':digest(self.raw)},
   'captured_ns':self.captured_ns,'started':self.started,'complete':self.complete,
   'snapshot_write_started':self.snapshot_write_started,'snapshot_write_completed':self.snapshot_write_completed,
   'receipt_write_completed':self.receipt_write_completed,'first_error':None if self.first_error is None else repr(self.first_error),
   'secondary_errors':[repr(e)for e in self.secondary_errors],
   'semantic_fit_use_verified':False,'native_isolation_qualified':False}

def execute_phase(case_raw,manifest_raw,program_root,workspace,selection,signal_root=None,reference_raw=None,budget=None,fit_capture=None,logical_job=None,source_owner=None):
 """One selected phase with original source owner and, for predict, fit capture."""
 staged=stage(case_raw,manifest_raw,program_root,workspace,selection,signal_root,reference_raw,budget,fit_capture,logical_job,source_owner=source_owner)
 return InvocationOwner(staged,selection).run()
