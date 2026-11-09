"""Durable own-job claims, fresh containers, bounded streams and actual counters."""
from __future__ import annotations
import hashlib
import math
import os
from pathlib import Path
import socket
import struct
import time
from owner.io import Artifact, ContractError, canonical, capture, decode, ordinary
from .contracts import digest, profile
from .engine import Engine, inspect_config

LABELS=('neural063.attempt','neural063.stage','neural063.controller','neural063.job')

class JobFailure(ContractError):
 def __init__(self,message,receipt):super().__init__(message);self.receipt=receipt

def attempt_label(attempt):return hashlib.sha256(attempt.encode()).hexdigest()

def write_record(ctx,relative,value,role):
 return ctx.store.json(relative,value,role=role,visibility='operator',producer=ctx.stage)

def authenticate_file(ref,ctx):
 ref=ref if isinstance(ref,Artifact) else Artifact.parse(ref)
 path=ordinary(ref.path);fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
 h=hashlib.sha256();n=0
 with os.fdopen(fd,'rb') as stream:
  from owner.io import identity
  before=os.fstat(stream.fileno())
  if before.st_size!=ref.bytes or before.st_mode&0o222:raise ContractError('immutable exact mount body required')
  while True:
   chunk=stream.read(1024*1024)
   if not chunk:break
   n+=len(chunk);ctx.store.meter.read(len(chunk));h.update(chunk)
   if n>ref.bytes:raise ContractError('mount body grew')
  if identity(before)!=identity(os.fstat(stream.fileno())) or n!=ref.bytes or h.hexdigest()!=ref.sha256:raise ContractError('mount source changed')
 return ref

def source_mounts(ctx,p,directory,operation):
 mounts=[]
 for name,raw in sorted(p['runtime_files'].items()):
  ref=Artifact.parse(raw)
  if Path(ref.path).absolute()!=Path(__file__).parent.joinpath(name).absolute():raise ContractError('runtime must mount the actual frozen source files')
  body=capture(ref.path,2_000_000,descriptor=ref,meter=ctx.store.meter)
  copy=ctx.store.write(directory+'/'+name,body,role='runtime_source_copy',visibility='operator',producer=ctx.stage)
  os.chmod(copy.path,0o444)
  mounts.append({'Type':'bind','Source':copy.path,'Target':'/code/'+name,'ReadOnly':True,'BindOptions':{'Propagation':'rprivate'}})
 if operation in {'reference','validation'}:
  for name,raw in sorted(p['trusted_tool_files'].items()):
   ref=Artifact.parse(raw)
   if Path(ref.path).absolute()!=Path(__file__).parent.parent.joinpath(name).absolute():raise ContractError('tool source must be actual frozen implementation closure')
   body=capture(ref.path,2_000_000,descriptor=ref,meter=ctx.store.meter)
   relative=directory+'/'+name;ctx.store.mkdir(str(Path(relative).parent))
   copy=ctx.store.write(relative,body,role='runtime_source_copy',visibility='operator',producer=ctx.stage);os.chmod(copy.path,0o444)
   mounts.append({'Type':'bind','Source':copy.path,'Target':'/code/'+name,'ReadOnly':True,'BindOptions':{'Propagation':'rprivate'}})
 return mounts

def seccomp(ctx,p):
 ref=Artifact.parse(p['seccomp']);obj=decode(capture(ref.path,1_000_000,descriptor=ref,meter=ctx.store.meter))
 if obj.get('defaultAction') not in {'SCMP_ACT_ERRNO','SCMP_ACT_KILL','SCMP_ACT_KILL_PROCESS'}:raise ContractError('default-deny seccomp profile required')
 forbidden={'kill','tkill','tgkill','mount','umount2','pivot_root','setns','unshare','ptrace','process_vm_readv','process_vm_writev','bpf','perf_event_open','kexec_load','init_module','finit_module','delete_module','reboot','keyctl','add_key','request_key','open_by_handle_at'}
 allowed={name for group in obj.get('syscalls',[]) if group.get('action')=='SCMP_ACT_ALLOW' for name in group.get('names',[])}
 if forbidden&allowed:raise ContractError('seccomp permits forbidden namespace/credential/peer operations')
 return json_text(obj)

def json_text(value):return canonical(value).decode().strip()

def container_config(p,claim,mounts,request,remaining,seccomp_text):
 gpu=request['operation']=='model'
 return {'Image':p['image_id'],'User':'0:0',
 'Env':['PATH=/usr/local/bin:/usr/bin:/bin','LANG=C.UTF-8','HOME=/scratch','TMPDIR=/scratch','PYTHONDONTWRITEBYTECODE=1','PYTHONHASHSEED=632026','OMP_NUM_THREADS=8','OPENBLAS_NUM_THREADS=8','MKL_NUM_THREADS=8','TRANSFORMERS_OFFLINE=1','HF_HUB_OFFLINE=1','HF_DATASETS_OFFLINE=1','MPLCONFIGDIR=/scratch/matplotlib'],
 'Entrypoint':['python3','-I','-B','/code/capsule.py'],'Cmd':[],'WorkingDir':'/','Labels':claim['labels'],'Tty':False,'OpenStdin':False,'AttachStdout':True,'AttachStderr':True,'Healthcheck':{'Test':['NONE']},
 'HostConfig':{'NetworkMode':'none','ReadonlyRootfs':True,'Privileged':False,'CapDrop':['ALL'],'CapAdd':['SETUID','SETGID'],
 'SecurityOpt':['no-new-privileges=true','seccomp='+seccomp_text],'PidsLimit':128,'Memory':remaining['ram_bytes'],'MemorySwap':remaining['ram_bytes'],'NanoCpus':8000000000,'CpusetCpus':','.join(map(str,p['cpu_ids'])),'IpcMode':'private','PidMode':'','UTSMode':'','CgroupnsMode':'private',
 'Tmpfs':{'/scratch':'rw,noexec,nosuid,nodev,size='+str(min(remaining['scratch_bytes'],remaining['write_bytes']))+',mode=700,uid='+str(p['worker_uid'])+',gid='+str(p['worker_gid'])},
 'Mounts':mounts,'DeviceRequests':[{'Driver':'nvidia','Count':0,'DeviceIDs':[p['gpu_uuid']],'Capabilities':[['gpu']],'Options':{}}] if gpu else [],
 'LogConfig':{'Type':'none','Config':{}},'RestartPolicy':{'Name':'no','MaximumRetryCount':0},'AutoRemove':False}}

def nvml_observation(p,allowed_pids):
 # This installed host dependency is a mandatory external runtime gate. It is
 # imported only during an authorized real job, never during source controls.
 import pynvml as nv
 nv.nvmlInit()
 try:
  handle=nv.nvmlDeviceGetHandleByUUID(p['gpu_uuid']);mem=nv.nvmlDeviceGetMemoryInfo(handle)
  if mem.total!=p['gpu_total_bytes']:raise ContractError('physical GPU differs from exact full-device quota')
  processes=nv.nvmlDeviceGetComputeRunningProcesses(handle)
  if any(x.pid not in allowed_pids for x in processes):raise ContractError('unrelated GPU process occupies exclusive device; never stop it')
  used=sum(int(x.usedGpuMemory) for x in processes)
  if used>p['gpu_partition_bytes']:raise ContractError('actual VRAM allocation exceeded')
  return {'uuid':p['gpu_uuid'],'total_bytes':mem.total,'used_bytes':used,'pids':sorted(x.pid for x in processes),'driver_version':str(nv.nvmlSystemGetDriverVersion()),'nvml_version':str(nv.nvmlSystemGetNVMLVersion())}
 finally:nv.nvmlShutdown()

def run_capsule(ctx,p,controller,ordinal,request,budget,*,checkpoint_mounts=()):
 """Fresh container per action; request/model data never shared with siblings."""
 ctx.require_scientific();p=profile(p)
 if budget['retained_bytes']<16384:raise ContractError('remaining transcript allowance cannot contain bounded attach/framing failure evidence')
 meter_start=ctx.store.meter.snapshot()
 capsule_deadline=min(time.monotonic()+budget['wall_seconds'],ctx.limits['monotonic_deadline']-p['cleanup_wall_seconds'])
 if capsule_deadline<=time.monotonic():raise ContractError('attempt lifetime cannot contain capsule and cleanup')
 request=dict(request,supervision={'wall_seconds':max(0,capsule_deadline-time.monotonic()),'deadline_monotonic':capsule_deadline,'attempt_expires_at':ctx.limits['attempt_expires_at'],'cpu_core_seconds':math.floor(budget['cpu_core_seconds']),'supervisor_uid':p['uid'],'supervisor_gid':p['gid'],'worker_uid':p['worker_uid'],'worker_gid':p['worker_gid']})
 label=attempt_label(ctx.attempt);job=digest({'attempt':ctx.attempt,'stage':ctx.stage,'controller':controller,'ordinal':ordinal,'request_sha256':digest(request)})
 name='n063-'+job[:48];directory='runtime-jobs/'+ctx.stage+'/'+controller+'/'+str(ordinal)
 ctx.store.mkdir(directory)
 labels=dict(zip(LABELS,(label,ctx.stage,controller,job)))
 claim={'schema':'neural063_runtime_job_claim_v1','attempt':ctx.attempt,'stage':ctx.stage,'controller':controller,'ordinal':ordinal,'job':job,'name':name,'labels':labels,'profile_sha256':digest(p),'request_sha256':digest(request),'operation':request['operation'],'budget':budget,'created_ns':time.time_ns()}
 claim_ref=write_record(ctx,directory+'/claim.json',claim,'runtime_job_claim')
 # This durable claim exists before create; deterministic name closes the
 # create-response/crash gap. A failure never deletes its claim or receipts.
 request_body=canonical(request)
 if len(request_body)>budget['read_bytes'] or len(request_body)>budget['write_bytes']:raise ContractError('complete immutable request cannot fit this controller read/write allocation')
 req_ref=ctx.store.write(directory+'/request.json',request_body,role='runtime_capsule_request',visibility='operator',producer=ctx.stage);os.chmod(req_ref.path,0o444)
 mounts=source_mounts(ctx,p,directory,request['operation'])
 mounts.append({'Type':'bind','Source':req_ref.path,'Target':'/input/request.json','ReadOnly':True,'BindOptions':{'Propagation':'rprivate'}})
 for item in checkpoint_mounts:
  ref=authenticate_file(item['artifact'],ctx)
  if not ordinary(ref.path).stat().st_mode&0o004:raise ContractError('operator-private ancestor with container-readable immutable checkpoint body required')
  mounts.append({'Type':'bind','Source':ref.path,'Target':'/checkpoint/'+item['name'],'ReadOnly':True,'BindOptions':{'Propagation':'rprivate'}})
 config=container_config(p,claim,mounts,request,budget,seccomp(ctx,p))
 config_ref=write_record(ctx,directory+'/config.json',config,'runtime_container_config')
 engine=Engine(p,ctx.store.meter,deadline=capsule_deadline)
 engine_identity=engine.qualify();ident=None;actual=None;stream=None;stdout=bytearray();stderr=bytearray();buffer=b'';started=time.monotonic();last_stats={};gpu_peak=0;failure=None;closure=None;inspections=[];gpu_observations=[]
 lock=None;gpu=request['operation']=='model';done=False
 try:
  if gpu:
   lock=Path(p['gpu_exclusive_lock'])
   if lock.absolute()!=ctx.store.root/'runtime-jobs'/'gpu.lock':raise ContractError('GPU lock must be exact attempt output custody path')
   fd=os.open(lock,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400)
   with os.fdopen(fd,'wb') as f:f.write(canonical({'attempt':ctx.attempt,'stage':ctx.stage,'job':job,'name':name}));f.flush();os.fsync(f.fileno())
   nvml_observation(p,set())
  response=engine.request('POST','/containers/create?name='+name,config,allowed=(201,));ident=response['Id'];engine.ident(ident)
  write_record(ctx,directory+'/created.json',{'id':ident,'name':name,'claim':claim_ref.object(),'warnings':response.get('Warnings')},'runtime_created')
  actual=engine.inspect(ident);inspections.append(inspect_config(actual,config))
  stream,buffer=engine.attach(ident)
  engine.request('POST','/containers/'+ident+'/start',allowed=(204,))
  next_poll=0.0;done=False
  # Process termination and stream EOF are independent observations. A stopped
  # process may still have queued stdout/stderr frames in the attached stream.
  while not done:
   now=time.monotonic()
   if now>=capsule_deadline or time.time()>=ctx.limits['attempt_expires_at']:raise ContractError('capsule/attempt wall deadline exceeded')
   try:
    capacity=budget['retained_bytes']-len(stdout)-len(stderr)-len(buffer)
    if capacity<=0:raise ContractError('capsule transcript allowance exhausted before EOF; complete received prefix retained')
    stream.settimeout(min(0.05,max(0.001,capsule_deadline-time.monotonic())))
    chunk=stream.recv(min(65536,capacity))
    if chunk:buffer+=chunk;ctx.store.meter.read(len(chunk))
    else:done=True
   except socket.timeout:pass
   while len(buffer)>=8:
    channel=buffer[0];length=struct.unpack('>I',buffer[4:8])[0]
    if channel not in (1,2) or buffer[1:4]!=b'\0\0\0':raise ContractError('invalid Docker stream frame')
    if length>budget['retained_bytes'] or len(stdout)+len(stderr)+length>budget['retained_bytes']:raise ContractError('capsule transcript retention allowance exceeded')
    if len(buffer)<8+length:break
    target=stdout if channel==1 else stderr;target.extend(buffer[8:8+length]);buffer=buffer[8+length:]
   if now>=next_poll:
    actual=engine.inspect(ident);inspections.append(inspect_config(actual,config))
    if actual['State'].get('Running'):
     last_stats=engine.request('GET','/containers/'+ident+'/stats?stream=false&one-shot=true')
     cpu=last_stats.get('cpu_stats',{}).get('cpu_usage',{}).get('total_usage',0)/1e9
     ram=last_stats.get('memory_stats',{}).get('usage',0)
     if cpu>budget['cpu_core_seconds'] or ram>budget['ram_bytes']:raise ContractError('aggregate remaining CPU/RAM allowance exceeded')
     if gpu:
      top=engine.request('GET','/containers/'+ident+'/top?ps_args=-eo%20pid')
      processes=top.get('Processes',[])
      if not processes:raise ContractError('actual GPU process membership unavailable')
      pids={int(x[0]) for x in processes}
      observation=nvml_observation(p,pids);gpu_observations.append(dict(observation,observed_ns=time.time_ns()));gpu_peak=max(gpu_peak,observation['used_bytes'])
    next_poll=time.monotonic()+0.1
  if not done:raise ContractError('capsule EOF was not observed')
  if buffer:raise ContractError('truncated capsule stream at actual EOF')
  final=engine.inspect(ident);inspections.append(inspect_config(final,config))
  if final['State'].get('Running') or final['State'].get('ExitCode')!=0 or final['State'].get('OOMKilled'):raise ContractError('capsule did not exit successfully within its allocation')
  value=decode(bytes(stdout))
  if value.get('schema')!='neural063_capsule_result_v1' or value.get('operation')!=request['operation']:raise ContractError('wrong capsule result protocol')
 except BaseException as exc:
  failure={'class':type(exc).__name__,'message':str(exc)[:2048],'backend_response':getattr(exc,'response',None),'last_observed_container':actual};value=None
 finally:
  if stream is not None:stream.close()
  # Use a separately bounded cleanup connection after the work deadline. The
  # parent hook independently repeats this reconciliation even after SIGKILL.
  cleanup=Engine(p,ctx.store.meter,deadline=min(time.monotonic()+p['cleanup_wall_seconds'],ctx.limits['monotonic_deadline']))
  try:
   actual=cleanup.inspect(ident or name,absent=True)
   if actual and 'Id' in actual:
    if actual.get('Config',{}).get('Labels')!=labels:raise ContractError('registered name now belongs to another job')
    if actual.get('State',{}).get('Running'):cleanup.request('POST','/containers/'+actual['Id']+'/kill',allowed=(204,409))
    final=cleanup.inspect(actual['Id'])
    if final['State'].get('Running') or final['State'].get('Pid',0)!=0:raise ContractError('runtime writers still exist')
    closure={'id':actual['Id'],'state':final['State'],'observed_ns':time.time_ns(),'labels':labels}
    # Keep stopped containers until parent reconciliation; no opaque removal.
   else:closure={'name':name,'absent':True,'observed_ns':time.time_ns(),'labels':labels}
   if lock is not None and lock.exists():
    lock_value=decode(capture(lock,4096,meter=ctx.store.meter))
    if lock_value!={'attempt':ctx.attempt,'stage':ctx.stage,'job':job,'name':name}:raise ContractError('GPU lock ownership changed')
    lock.unlink()
  except BaseException as exc:
   failure={'class':type(exc).__name__,'message':'cleanup: '+str(exc)[:2048],'backend_response':getattr(exc,'response',None),'prior_failure':failure};closure={'unresolved':True}
  out_ref=ctx.store.write(directory+'/stdout.bin',bytes(stdout),role='runtime_stdout',visibility='operator',producer=ctx.stage,media_type='application/octet-stream')
  err_ref=ctx.store.write(directory+'/stderr.bin',bytes(stderr),role='runtime_stderr',visibility='operator',producer=ctx.stage,media_type='application/octet-stream')
  tail_ref=ctx.store.write(directory+'/unparsed-stream.bin',buffer,role='runtime_unparsed_stream',visibility='operator',producer=ctx.stage,media_type='application/octet-stream')
  receipt={'schema':'neural063_runtime_job_v1','claim':claim_ref.object(),'config':config_ref.object(),'request':req_ref.object(),'engine':engine_identity,'inspections':inspections,'closure':closure,'failure':failure,'stdout':out_ref.object(),'stderr':err_ref.object(),'unparsed_stream':tail_ref.object(),'stream_eof_observed':done,'unread_stream_bytes':0 if done else None,'wall_seconds':time.monotonic()-started,'gpu_device_seconds':time.monotonic()-started if gpu else 0,'gpu_peak_bytes':gpu_peak,'gpu_observations':gpu_observations,'last_engine_stats':last_stats,'trusted_capsule_usage':value.get('usage') if value else None,'runtime':value.get('runtime') if value else None,'actual_capsule_identity':value.get('isolation') if value else None,'operator_logical_io_before_receipt':{'read_bytes':ctx.store.meter.read_bytes-meter_start['logical_read_bytes'],'write_bytes':ctx.store.meter.write_bytes-meter_start['logical_write_bytes'],'basis':'charged explicit file and local-engine transport bytes; physical OS I/O unmeasured'}}
  receipt_ref=write_record(ctx,directory+'/receipt.json',receipt,'runtime_job_receipt')
 if failure:raise JobFailure(failure['message'],receipt_ref.object())
 return value['result'],value['usage'],receipt_ref.object()
