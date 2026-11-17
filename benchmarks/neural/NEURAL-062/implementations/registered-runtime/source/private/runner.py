"""Concrete Linux tmpfs + OCI phase runner; all native qualification remains external.

Bounded tmpfs outputs, bounded pipes, explicit container retirement and independent
unmount are real source calls. Construction never executes any of them.
"""
from pathlib import Path
import hashlib,json,os,selectors,stat,subprocess,time
import delivery_io as io
def source_tree(root,limit=32_000_000):
 root=io.regular(root);io.need(root.is_dir(),'state directory');rows=[];total=0;pending=[root];count=0
 while pending:
  directory=pending.pop()
  with os.scandir(directory)as entries:
   for entry in entries:
    count+=1;io.need(count<=1024,'finite complete output tree')
    p=io.regular(Path(entry.path));s=p.lstat()
    if stat.S_ISDIR(s.st_mode):pending.append(p);continue
    io.need(stat.S_ISREG(s.st_mode)and s.st_nlink==1,'ordinary single-link state')
    total+=s.st_size;io.need(total<=limit,'complete output extent')
    rows.append({'path':str(p.relative_to(root)),**io.read(p,s.st_size,empty=True,retain=False)})
 return sorted(rows,key=lambda r:r['path'])
def native_call(argv,owner,timeout,cap=65536):
 """Bounded combined stdout/stderr and deterministic independent process cleanup."""
 proc=None;selector=None;body=bytearray();first=None;code=None;start=time.monotonic()
 try:
  owner.check();proc=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,close_fds=True)
  selector=selectors.DefaultSelector();selector.register(proc.stdout,selectors.EVENT_READ)
  while selector.get_map():
   if time.monotonic()-start>timeout:raise TimeoutError('native command deadline')
   for key,_ in selector.select(min(.1,max(.001,timeout-(time.monotonic()-start)))):
    b=os.read(key.fileobj.fileno(),min(8192,cap-len(body)+1))
    if not b:selector.unregister(key.fileobj);continue
    io.need(len(body)+len(b)<=cap,'bounded native command output');body.extend(b)
  code=proc.wait(timeout=max(.001,timeout-(time.monotonic()-start)))
 except BaseException as e:first=e;owner.retain(e,'native_call')
 finally:
  if proc is not None:
   for name,fn in [('client_kill',lambda:proc.kill()if proc.poll()is None else None),('client_wait',lambda:proc.wait(timeout=10)),('client_pipe_close',lambda:proc.stdout.close())]:
    try:fn()
    except BaseException as e:
     if first is None:first=e
     owner.retain(e,name)
  if selector is not None:
   try:selector.close()
   except BaseException as e:
    if first is None:first=e
    owner.retain(e,'selector_close')
 if first is not None:raise first
 return code,bytes(body)
def cleanup_call(argv,timeout=30):
 # Cleanup must still run after the main owner is failed; bounded independent child.
 from custody import Owner
 cleanup=Owner({'read_bytes':1000000,'write_bytes':1000000,'jobs':1,'wall_seconds':timeout+20})
 return native_call(argv,cleanup,timeout)
def container_identity(cidfile):
 """Read only the full ID written by Docker into this invocation's fresh host directory.
 The host-only receipt is never mounted into the candidate; a name is not authority.
 """
 body=io.read(cidfile,65)
 if body.endswith(b'\n'):body=body[:-1]
 io.need(len(body)==64 and all(x in b'0123456789abcdef' for x in body),'exact acquired container ID')
 return body.decode('ascii')
def run_phase(env,script,public_code,input_view,state,output,kind,mode,phase,owner):
 first=None;mounted=False;attempted=False;identity_attempted=False;cid=None;retired=False;output=Path(output);label='n062-'+hashlib.sha256(str(output).encode()).hexdigest()[:24]
 start=time.monotonic();files=None
 try:
  owner.charge('jobs',1);owner.check()
  script=io.regular(script);input_view=io.regular(input_view);public_code=io.regular(public_code);output=io.fresh(output);scratch=io.fresh(output/'scratch')
  cidfile=output/'container.cid'
  io.need(not cidfile.exists(),'fresh host-only container receipt')
  cap=32_000_000 if phase=='fit'else 160_000_000
  mounted=True
  code,_=native_call(['mount','-t','tmpfs','-o',f'size={cap},nr_inodes=2048,nosuid,nodev,noexec,mode=0700', 'n062-output',str(scratch)],owner,30)
  io.need(code==0,'actual bounded tmpfs mount');mounted=True
  command=['docker','run','--name',label,'--cidfile',str(cidfile),'--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit',str(env['pids']),'--memory',str(env['memory_bytes']),'--memory-swap',str(env['memory_bytes']),'--cpus',str(env['cpus']),'--user',str(os.getuid())+':'+str(os.getgid()),'--tmpfs','/tmp:rw,noexec,nosuid,size=268435456','--mount','type=bind,src='+str(script)+',dst=/candidate/program.py,readonly','--mount','type=bind,src='+str(public_code)+',dst=/api,readonly','--mount','type=bind,src='+str(input_view)+',dst=/input,readonly','--mount','type=bind,src='+str(scratch)+',dst=/output','--env','PYTHONPATH=/api','--env','OPENBLAS_NUM_THREADS=1','--env','OMP_NUM_THREADS=1','--env','PYTHONDONTWRITEBYTECODE=1']
  if state is not None:command+=['--mount','type=bind,src='+str(io.regular(state))+',dst=/state,readonly']
  command += [env['image'],'python','-B','/candidate/program.py','--phase',phase,'--input','/input','--output','/output/result','--mode',mode]
  if kind!='participant':command+=['--kind',kind]
  if state is not None:command+=['--state','/state']
  # Reserve the maximum known receipt write before the Docker CLI effect.
  owner.charge('write_bytes',65);attempted=True
  code,log=native_call(command,owner,env['job_seconds'])
  io.need(code==0,'phase process failure')
  identity_attempted=True;cid=container_identity(cidfile)
  owner.events.append({'stage':'container_acquired','container_id':cid})
  io.put_bytes(output/'process.log',log,65536)
  code,inspect=native_call(['docker','inspect','--format','{{.State.Running}}',cid],owner,30)
  io.need(code==0 and inspect.strip()==b'false','actual completed container')
  code,_=native_call(['docker','rm','-f',cid],owner,30);io.need(code==0,'container removal');retired=True
  files=source_tree(scratch/'result',cap)
  if phase=='infer':io.need([r['path']for r in files]==['prediction.json'],'single exact prediction')
  dest=io.fresh(output/'result')
  for r in files:
   target=io.resolve(dest,r['path']);target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
   io.copy_exact(io.resolve(scratch/'result',r['path']),target,{k:r[k]for k in('bytes','sha256')})
 except BaseException as e:first=e;owner.retain(e,'phase_'+phase)
 finally:
  if attempted and cid is None:
   if not identity_attempted:
    def recover_identity():
     nonlocal cid,identity_attempted
     from custody import Owner
     recovery=Owner({'read_bytes':66,'write_bytes':0,'jobs':0,'wall_seconds':30})
     identity_attempted=True
     try:
      with io.using(recovery),recovery.stage('container_receipt_recovery'):
       cid=container_identity(cidfile)
     finally:
      recovery.close()
      owner.events.append({'stage':'container_receipt_recovery_cost','cost':recovery.snapshot()})
    owner.cleanup('container_identity_recovery',recover_identity)
   if cid is None:
    # No name-based fallback, retry or invented absence/retirement fact.
    owner.events.append({'stage':'container_cleanup','state':'identity_unavailable_cleanup_unknown','name_not_authority':label})
  if cid is not None and not retired:
   def retire():
    nonlocal retired
    code,_=cleanup_call(['docker','rm','-f',cid]);io.need(code==0,'independent container retirement');retired=True
   owner.cleanup('container_retirement',retire)
  if mounted:
   def unmount():
    code,_=cleanup_call(['umount',str(output/'scratch')]);io.need(code==0,'independent scratch unmount')
   owner.cleanup('scratch_unmount',unmount)
 if first is not None:raise first
 if owner.first is not None:raise owner.first
 return {'complete':True,'retired':retired,'phase':phase,'wall_seconds':time.monotonic()-start,'output_files':files,'image':env['image'],'native_cpu_io_peak':'unmeasured; runtime qualification remains open'}
def cell(env,script,public_code,fit,infer,output,kind,mode,owner):
 with owner.stage('owned_fit_infer_cell'):
  output=io.fresh(output)
  a=run_phase(env,script,public_code,fit,None,output/'fit',kind,mode,'fit',owner)
  state=output/'fit/result';pins=source_tree(state)
  for r in pins:(state/r['path']).chmod(0o444)
  b=run_phase(env,script,public_code,infer,state,output/'infer',kind,mode,'infer',owner)
  io.need(source_tree(state)==pins,'same sealed state after inference')
  path=output/'infer/result/prediction.json'
  return {'path':str(path),'pin':io.read(path,160_000_000,retain=False),'fit':a,'infer':b,'state_pin':io.pin(io.canonical(pins))}
