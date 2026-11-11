"""Source-owned arm-specific staging and Docker argv. No metadata is qualification."""
import hashlib,math,re,os,stat,time
from pathlib import Path,PurePosixPath
import io_contract as io
from case_contract import validate_case,validate_fit_state,validate_fit_limits
from scientific_contract import project_reference,require_source_authority
SHA=re.compile(r'[0-9a-f]{64}\Z')
CID=re.compile(r'[0-9a-f]{64}\Z')
def digest(raw):return hashlib.sha256(raw).hexdigest()
def absolute(value):
 io.need(type(value)is str and Path(value).is_absolute()and not any(c in value for c in ',\n\r\0'),'absolute single Docker mount argument')
 return value
def relative(value):
 io.need(type(value)is str and value and not value.startswith('/')and all(p not in ('','..','.')for p in value.split('/'))and not any(c in value for c in ',\n\r\0'),'confined source member')
 return value
def validate_selection(s):
 io.fields(s,['schema','docker','endpoint','image_id','python_path','image_env','uid','gid','limits','fit_state_limits','qualification_reference'])
 io.need(s['schema']=='neural012_container_runtime_selection_v4','selected two-phase runtime with original-owner postprediction bounds')
 io.fields(s['docker'],['path','bytes','sha256']);absolute(s['docker']['path'])
 io.need(type(s['docker']['bytes'])is int and s['docker']['bytes']>0 and type(s['docker']['sha256'])is str and SHA.fullmatch(s['docker']['sha256']),'selected Docker binary')
 io.need(type(s['endpoint'])is str and s['endpoint'].startswith('unix:///'),'local qualified daemon endpoint only')
 absolute(s['endpoint'][7:]);absolute(s['python_path'])
 io.need(type(s['image_id'])is str and s['image_id'].startswith('sha256:')and SHA.fullmatch(s['image_id'][7:]),'immutable local image, never a tag')
 io.need(type(s['image_env'])is list and all(type(x)is str and '\0'not in x and '='in x for x in s['image_env'])and len({x.split('=',1)[0]for x in s['image_env']})==len(s['image_env']),'complete independently selected image environment')
 io.need(type(s['uid'])is int and s['uid']>0 and type(s['gid'])is int and s['gid']>0,'nonroot identity')
 lim=s['limits'];io.fields(lim,['cpus','memory_bytes','pids','wall_seconds','admin_wall_seconds','stdout_bytes','stderr_bytes','output_bytes','tmp_bytes','file_bytes','argv_bytes','staging_bytes','signal_read_bytes','campaign_wall_seconds','campaign_staging_bytes','campaign_signal_read_bytes','campaign_stdout_bytes','campaign_stderr_bytes','campaign_output_bytes','postprediction_read_bytes','postprediction_write_bytes'])
 io.need(type(lim['cpus'])is str and re.fullmatch(r'[0-9]+(?:\.[0-9]+)?',lim['cpus'])and math.isfinite(float(lim['cpus']))and float(lim['cpus'])>0,'selected positive CPU cap')
 for k in ('wall_seconds','admin_wall_seconds','campaign_wall_seconds'):
  io.need(type(lim[k])in(int,float)and math.isfinite(lim[k])and lim[k]>0,'selected finite time cap')
 for k in ('memory_bytes','pids','stdout_bytes','stderr_bytes','output_bytes','tmp_bytes','file_bytes','argv_bytes','staging_bytes','signal_read_bytes','campaign_staging_bytes','campaign_signal_read_bytes','campaign_stdout_bytes','campaign_stderr_bytes','campaign_output_bytes','postprediction_read_bytes','postprediction_write_bytes'):
  io.need(type(lim[k])is int and lim[k]>0,'selected positive bound; no defaults')
 io.fields(s['qualification_reference'],['path','bytes','sha256'])
 io.need(type(s['qualification_reference']['bytes'])is int and s['qualification_reference']['bytes']>0 and SHA.fullmatch(s['qualification_reference']['sha256']),'external qualification artifact selector, not a verified report')
 absolute(s['qualification_reference']['path'])
 validate_fit_limits(s['fit_state_limits'])
 return s
def programme_manifest(value):
 io.fields(value,['schema','entrypoint','files'])
 io.need(value['schema']=='neural012_selected_programme_v3'and type(value['files'])is list and value['files'],'closed two-phase source selection')
 names=set()
 for r in value['files']:
  io.fields(r,['path','bytes','sha256']);n=relative(r['path'])
  io.need(n.endswith('.py')and n not in names and type(r['bytes'])is int and 0<r['bytes']<=1048576 and SHA.fullmatch(r['sha256']),'explicit ordinary programme code only')
  names.add(n)
 io.need(relative(value['entrypoint'])in names,'selected actual entrypoint')
 return value
def view_plan(case,source_manifest):
 validate_case(case);programme_manifest(source_manifest)
 part='train'if case['phase']=='fit'else'query'
 signal_rows=[]if case['arm']=='timing'else[r['signal']for r in case[part]]
 io.need(len({r['file']for r in signal_rows})==len(signal_rows),'no repeated signal mount')
 return {'schema':'neural012_phase_view_v3','arm':case['arm'],'phase':case['phase'],
 'case_sha256':digest(io.encoded(case)),'programme_sha256':digest(io.encoded(source_manifest)),
 'source_files':source_manifest['files'],'signals':signal_rows,
 'reference_binding_required':case['arm']!='timing','fit_state_required':case['phase']=='predict','network':'none','other_host_inputs':[]}
def mount(source,target,readonly=True):
 absolute(str(source));absolute(target)
 return ['--mount','type=bind,src='+str(source)+',dst='+target+(',readonly'if readonly else'')]
def create_argv(s,view,workspace,signal_paths):
 validate_selection(s);root=Path(absolute(str(workspace)));lim=s['limits']
 io.need(type(signal_paths)is dict and set(signal_paths)=={r['file']for r in view['signals']},'exact source-owned arm mount inverse')
 if view['arm']=='timing':io.need(not signal_paths and not view['reference_binding_required'],'no timing waveform/reference capability')
 argv=[s['docker']['path'],'--host',s['endpoint'],'container','create','--pull=never','--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges:true','--user',str(s['uid'])+':'+str(s['gid']),'--pids-limit',str(lim['pids']),'--cpus',lim['cpus'],'--memory',str(lim['memory_bytes']),'--memory-swap',str(lim['memory_bytes']),'--ulimit','fsize='+str(lim['file_bytes'])+':'+str(lim['file_bytes']),'--ipc=none','--log-driver=none','--no-healthcheck','--restart=no','--workdir=/program','--entrypoint',s['python_path'],'--tmpfs','/tmp:rw,noexec,nosuid,nodev,size='+str(lim['tmp_bytes'])]
 argv+=mount(root/'input/case.json','/input/case.json')+mount(root/'program','/program')+mount(root/'output','/output',False)
 for r in view['signals']:argv+=mount(signal_paths[r['file']],'/input/'+r['file'])
 if view['reference_binding_required']:argv+=mount(root/'input/reference.json','/input/reference.json')
 if view['fit_state_required']:argv+=mount(root/'input/fit-state.json','/input/fit-state.json')
 output='fit-state.json'if view['phase']=='fit'else'prediction.json'
 argv += [s['image_id'],'-B','-s','-E','/program/'+view['entrypoint'],'--case','/input/case.json','--output','/output/'+output]
 argv+=['--fit-state-limits',io.encoded(s['fit_state_limits']).decode('utf8').strip()]
 if view['fit_state_required']:argv+=['--fit-state','/input/fit-state.json','--fit-state-sha256',view['fit_state_sha256']]
 if view['reference_binding_required']:argv+=['--signal-root','/input','--reference-binding','/input/reference.json','--reference-binding-sha256',view['reference_binding_sha256']]
 io.need(sum(len(x.encode())+1 for x in argv)<=lim['argv_bytes'],'full source-derived argv fits selected original bound')
 return argv
def job_identity(value):
 io.fields(value,['job_id','plan_sha256'])
 io.need(type(value['job_id'])is str and 0<len(value['job_id'])<=128 and type(value['plan_sha256'])is str and SHA.fullmatch(value['plan_sha256']),'original host-only logical job identity')
 return value
def selected_phase_runtime(selection,budget):
 s=validate_selection(selection);base=budget.selection
 admitted=io.strict(io.encoded(s));admitted['limits']['wall_seconds']=base['limits']['wall_seconds']
 io.need(admitted==base and s['limits']['wall_seconds']<=base['limits']['wall_seconds'],'same selected campaign runtime; only shorter phase wall limit allowed')
 return s
def stage(case_raw,manifest_raw,program_root,workspace,selection,signal_root=None,reference_raw=None,budget=None,fit_capture=None,logical_job=None,source_owner=None):
 io.need(type(budget)is ExecutionBudget,'actual original campaign budget');budget.check()
 from source_validation import SourceValidationOwner
 io.need(type(source_owner)is SourceValidationOwner,'original host source owner, never a serialized candidate receipt')
 case=validate_case(io.strict(case_raw));s=selected_phase_runtime(selection,budget);manifest=programme_manifest(io.strict(manifest_raw))
 logical_job=job_identity(logical_job);fit_raw=None;fit_admitted_ns=None
 source_owner.require_phase(case,reference_raw,logical_job)
 source_owner.require_qualified('phase_input_admission',digest(case_raw))
 if case['phase']=='fit':io.need(fit_capture is None,'fit cannot receive prior fitted state')
 else:
  from container_owner import CapturedFit
  io.need(type(fit_capture)is CapturedFit,'original completed fit capture, not supplied metadata')
  fit_capture.require_original(case,manifest_raw,logical_job,budget)
  fit_admitted_ns=time.monotonic_ns()
  fit_raw=fit_capture.raw
  validate_fit_state(io.strict(fit_raw),case['fit_case_sha256'],case['arm'],s['fit_state_limits'])
 # Refuse inappropriate operands before any signal-root operation or source read.
 if case['arm']=='timing':io.need(signal_root is None and reference_raw is None,'timing has no physical operands')
 else:
  io.need(signal_root is not None and type(reference_raw)is bytes,'signal arm original physical operands')
  rows=case['train'if case['phase']=='fit'else'query']
  reference_raw=io.encoded(project_reference(io.strict(reference_raw),rows))
  reference=io.strict(reference_raw)
  io.need(digest(io.encoded(reference['scientific_profile']))==case['scientific_profile_sha256'],'same phase scientific policy identity')
  # Genuine provenance belongs to the original trusted host owner. Only local
  # consistency metadata and admitted signal snapshots enter the candidate.
  source_owner.require_qualified('physical_signal_inputs',digest(reference_raw))
 root=Path(absolute(str(workspace)));io.need(not root.exists()and not root.is_symlink(),'fresh original workspace')
 io.need(os.geteuid()==s['uid']and os.getegid()==s['gid']and os.geteuid()>0,'same original nonroot operator/output identity')
 program_root=Path(absolute(str(program_root)));files={}
 planned=view_plan(case,manifest);signal_total=sum(r['bytes']for r in planned['signals'])
 capture_reservation=s['fit_state_limits']['bytes']if case['phase']=='fit'else len(fit_raw)
 io.need(len(case_raw)+sum(r['bytes']for r in manifest['files'])+(len(reference_raw)if reference_raw is not None else 0)+signal_total+capture_reservation<=s['limits']['staging_bytes'],'whole phase staging and immutable state capacity before first source read')
 io.need(3*signal_total+3*len(planned['signals'])<=s['limits']['signal_read_bytes'],'full before/after signal read demand before source reads')
 for r in manifest['files']:
  target=program_root/r['path'];io.need(not any(x.is_symlink()for x in [target,*target.parents]),'no programme symlink ancestry')
  files[r['path']]=io.read(target,r['bytes'],r['sha256'])
 view=view_plan(case,manifest);view['case_sha256']=digest(case_raw);view['programme_sha256']=digest(manifest_raw);view['entrypoint']=manifest['entrypoint'];paths={}
 if fit_raw is not None:
  view['fit_state_sha256']=digest(fit_raw);view['fit_capture_admitted_ns']=fit_admitted_ns
 if case['arm']!='timing':
  view['reference_binding_sha256']=digest(reference_raw)
  for r in view['signals']:
   target=Path(absolute(str(signal_root)))/r['file']
   io.need(not any(x.is_symlink()for x in [target,*target.parents]),'no signal mount symlink ancestry')
   st=target.lstat();io.need(stat.S_ISREG(st.st_mode)and st.st_size==r['bytes'],'exact selected ordinary signal extent')
   # Full signal hash/calibration is verified by the source reader; native snapshot isolation remains qualification.
   paths[r['file']]=str(target)
 signal_bytes=sum(r['bytes']for r in view['signals'])
 io.need(3*signal_bytes+3*len(view['signals'])<=s['limits']['signal_read_bytes'],'all source copy and before/after staged digest reads admitted')
 staging_bytes=len(case_raw)+sum(map(len,files.values()))+(len(reference_raw)if reference_raw is not None else 0)+signal_bytes+capture_reservation
 io.need(staging_bytes<=s['limits']['staging_bytes'],'whole arm staging admitted before effects; no missing record truncation')
 output_cap=s['fit_state_limits']['bytes']if case['phase']=='fit'else s['limits']['output_bytes']
 budget.reserve_phase(staging_bytes,3*signal_bytes+3*len(view['signals']),output_cap);budget.check()
 root.mkdir(mode=0o700)
 for n in ('input','program','output','private'): (root/n).mkdir(mode=0o700)
 def raw_write(path,raw):
  with path.open('xb')as f:f.write(raw)
 raw_write(root/'input/case.json',case_raw)
 if reference_raw is not None:raw_write(root/'input/reference.json',reference_raw)
 if fit_raw is not None:raw_write(root/'input/fit-state.json',fit_raw)
 for r in view['signals']:
  target=root/'input'/r['file'];target.parent.mkdir(parents=True,exist_ok=True)
  copy_signal(Path(paths[r['file']]),target,r,budget)
  paths[r['file']]=str(target)
 for n,b in files.items():
  target=root/'program'/n;target.parent.mkdir(parents=True,exist_ok=True);raw_write(target,b);target.chmod(0o444)
 # Nonroot container can traverse the exact read-only roots and owns its sole output directory.
 for d in [root/'input',root/'program',*(x for x in (root/'program').rglob('*')if x.is_dir())]:d.chmod(0o555)
 for f in (root/'input').rglob('*'):f.chmod(0o555 if f.is_dir()else 0o444)
 (root/'output').chmod(0o700)
 argv=create_argv(s,view,root,paths)
 io.write(root/'private/view.json',view)
 return StagedCase(_STAGING,root,case,case_raw,manifest,manifest_raw,view,argv,files,reference_raw,budget,fit_capture,fit_raw,logical_job,source_owner)

_STAGING=object()
class StagedCase:
 def __init__(self,token,root,case,case_raw,manifest,manifest_raw,view,argv,files,reference_raw,budget,fit_capture,fit_raw,logical_job,source_owner):
  io.need(token is _STAGING,'only actual stage creates this owner')
  self.root=root;self.case=case;self.case_raw=case_raw;self.manifest=manifest;self.manifest_raw=manifest_raw;self.view=view;self.argv=argv
  self.files=files;self.reference_raw=reference_raw;self.budget=budget
  self.fit_capture=fit_capture;self.fit_raw=fit_raw;self.logical_job=io.strict(io.encoded(logical_job));self.source_owner=source_owner
 def require_original(self):
  self.budget.check()
  from source_validation import SourceValidationOwner
  io.need(type(self.source_owner)is SourceValidationOwner,'original host input owner retained by each phase')
  self.source_owner.require_phase(self.case,self.reference_raw,self.logical_job,reference_view='projected')
  self.source_owner.require_qualified('phase_input_admission',digest(self.case_raw))
  io.need(io.read(self.root/'input/case.json',len(self.case_raw),digest(self.case_raw))==self.case_raw,'original case bytes')
  actual={str(q.relative_to(self.root/'program'))for q in(self.root/'program').rglob('*')if q.is_file()}
  io.need(actual==set(self.files),'exact whole programme source, no extra payload')
  for name,b in self.files.items():io.need(io.read(self.root/'program'/name,len(b),digest(b))==b,'same original selected source')
  expected={'case.json'}if self.reference_raw is None else{'case.json','reference.json','signals'}
  if self.fit_raw is not None:
   expected.add('fit-state.json')
   self.fit_capture.require_original(self.case,self.manifest_raw,self.logical_job,self.budget)
   io.need(io.read(self.root/'input/fit-state.json',self.fit_capture.limits['bytes'],digest(self.fit_raw))==self.fit_raw,'same immutable fit state input')
  io.need({q.name for q in(self.root/'input').iterdir()}==expected,'exact arm inputs')
  if self.reference_raw is not None:
   io.read(self.root/'input/reference.json',len(self.reference_raw),digest(self.reference_raw))
   io.need({q.name for q in(self.root/'input/signals').iterdir()}=={Path(r['file']).name for r in self.view['signals']},'whole exact source signal staging')
   for r in self.view['signals']:copy_signal(self.root/'input'/r['file'],None,r,self.budget)
  return self

def copy_signal(source,destination,pin,budget):
 """Future streaming snapshot. Cleanup cannot replace the first original failure."""
 fd=None;out=None;primary=None;secondary=[]
 try:
  budget.check();fd=os.open(source,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
  before=os.fstat(fd);io.need(stat.S_ISREG(before.st_mode)and before.st_nlink==1 and before.st_size==pin['bytes'],'stable selected source extent')
  if destination is not None:out=destination.open('xb')
  h=hashlib.sha256();total=0
  while True:
   budget.check();block=os.read(fd,min(65536,pin['bytes']+1-total))
   if not block:break
   total+=len(block);io.need(total<=pin['bytes'],'complete bounded source bytes');h.update(block)
   if out is not None:out.write(block)
  after=os.fstat(fd)
  io.need(total==pin['bytes']and h.hexdigest()==pin['sha256']and all(getattr(before,k)==getattr(after,k)for k in('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')),'same original complete signal snapshot')
 except BaseException as error:primary=error
 finally:
  for close in ([out.close]if out is not None else[])+([lambda:os.close(fd)]if fd is not None else[]):
   try:close()
   except BaseException as error:
    if primary is None:primary=error
    else:secondary.append(error)
 if primary is not None:
  for error in secondary:primary.add_note('secondary original snapshot cleanup: '+repr(error))
  raise primary
 if destination is not None:destination.chmod(0o444)

class ExecutionBudget:
 """Actual monotonic campaign origin; caps are external selected demands, not qualification."""
 def __init__(self,selection):
  self.selection=validate_selection(io.strict(io.encoded(selection)));self.started_ns=time.monotonic_ns()
  self.deadline_ns=self.started_ns+int(selection['limits']['campaign_wall_seconds']*1000000000)
  self.staging=0;self.signal_reads=0;self.invocations=0;self.stdout=0;self.stderr=0;self.output=0
  self.postprediction_reads=0;self.postprediction_writes=0
 def check(self):
  remaining=(self.deadline_ns-time.monotonic_ns())/1000000000
  io.need(remaining>0,'original campaign deadline; no productive reset')
  return remaining
 def reserve_postprediction_read(self,n):
  self.check();io.need(type(n)is int and n>=0,'exact nonnegative postprediction read charge')
  self.postprediction_reads+=n
  io.need(self.postprediction_reads<=self.selection['limits']['postprediction_read_bytes'],'same original campaign postprediction read allowance')
 def reserve_postprediction_write(self,n):
  self.check();io.need(type(n)is int and n>=0,'exact nonnegative postprediction write charge')
  self.postprediction_writes+=n
  io.need(self.postprediction_writes<=self.selection['limits']['postprediction_write_bytes'],'same original campaign postprediction write allowance')
 def reserve_phase(self,staging,signal_reads,output):
  self.check();lim=self.selection['limits'];self.invocations+=1
  self.staging+=staging;self.signal_reads+=signal_reads
  self.output+=output
  self.stdout+=5*(lim['stdout_bytes']+1);self.stderr+=5*(lim['stderr_bytes']+1)
  io.need(self.invocations<=192 and self.staging<=lim['campaign_staging_bytes']and self.signal_reads<=lim['campaign_signal_read_bytes']and self.stdout<=lim['campaign_stdout_bytes']and self.stderr<=lim['campaign_stderr_bytes']and self.output<=lim['campaign_output_bytes'],'original complete192-phase campaign reservation')
