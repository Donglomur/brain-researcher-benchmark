"""Actual bounded worker lifecycle, original custody first, shared clocks/quota."""
import os,signal,subprocess,time,selectors
from pathlib import Path
from .common import require,Refusal,write_new,seal_tree,verify_tree,census,identity,plain_path,canonical,decode,load,make_dir,append_record
from .lifecycle import current,LifecycleError,DeadlineExceeded,BudgetExceeded,UnresolvedContainment,error_record

def observed_writable(roots):
 total=0;entries=0;unsafe=[];errors=[]
 for root in roots:
  for base,dirs,files in os.walk(root,followlinks=False,onerror=lambda e:errors.append(str(e))):
   for name in dirs+files:
    p=Path(base)/name;entries+=1
    try:
     s=p.lstat()
     if p.is_symlink()or(p.is_file()and s.st_nlink!=1):unsafe.append(str(p))
     if p.is_file()and not p.is_symlink():total+=s.st_size
    except OSError as e:unsafe.append(str(p));errors.append(str(e))
 return {'bytes':total,'entries':entries,'unsafe_entries':unsafe,'counters_complete':not errors,'counter_errors':errors}

class Supervisor:
 def __init__(self,root,budget,execution,full_deadline,job_id):
  self.root=plain_path(root);self.budget=budget;self.execution=execution;self.deadline=full_deadline;self.job_id=job_id;self.attempts=[];self.total_wall=0;self.total_wall_observed=True;self.request_count=0
 def run(self,stage_id,argv,mounts,request_id,source_id,dialogue=None):
  context=current();require(context is not None,'supervisor requires original campaign');require(self.deadline==context.deadline,'supervisor original condition deadline binding')
  with context.nested('phase '+self.job_id+'/'+stage_id,self.budget['phase_seconds'])as c:
   return self._run(c,stage_id,argv,mounts,request_id,source_id,dialogue)
 def _run(self,c,stage_id,argv,mounts,request_id,source_id,dialogue):
  campaign=c.campaign;ledger=campaign.ledger;b=self.budget;begin=campaign.clock();attempt,slot=campaign.register(self.job_id,stage_id,request_id,source_id);self.attempts.append(attempt)
  process=None;selector=None;forced=False;cleanup=[];commits=[];responses=[];outputseal=None;lease=None;container_name=None;intent=None;intent_identifier=None;primary=None;containment=True;reaped=False;returncode=None
  root=self.root/stage_id;out=root/'output';scratch=root/'scratch';work=root/'workspace';stdout=root/'stdout.log';stderr=root/'stderr.log'
  def fail(error):
   nonlocal primary
   if primary is None:primary=error
   campaign.note(attempt,error)
  def terminate(reason):
   nonlocal forced
   forced=True
   try:os.killpg(process.pid,signal.SIGKILL);cleanup.append({'action':'killpg','reason':reason,'delivered':True})
   except BaseException as error:
    cleanup.append({'action':'killpg','reason':reason,'delivered':False,'error':str(error)})
    if process.poll()is None:
     try:process.kill();cleanup.append({'action':'kill_original_pid','delivered':True})
     except BaseException as e:cleanup.append({'action':'kill_original_pid','delivered':False,'error':str(e)})
  try:
   c.check('stage setup');self.request_count+=1+(len(dialogue)if dialogue is not None else 0);require(self.request_count<=b['request_limit'],'complete request budget exhausted')
   make_dir(root)
   for p in(out,scratch,work):make_dir(p)
   ro={name:Path(path)for name,path in mounts.items()};sealed={name:seal_tree(path,b['file_count'],max(b['source_bytes'],b['input_bytes'],b['output_bytes']))for name,path in ro.items()}
   mode=self.execution['mode'];mapping={**{k:'/'+k if mode=='qualified_docker'else str(v)for k,v in ro.items()},'output':'/output'if mode=='qualified_docker'else str(out),'scratch':'/scratch'if mode=='qualified_docker'else str(scratch),'request':'/request/request.json'if mode=='qualified_docker'else str(ro['request']/'request.json')}
   actual=[mapping.get(x[1:-1],x)if x.startswith('{')and x.endswith('}')else x for x in argv]
   if mode!='qualified_docker':actual=[next((str(v)+x[len('/'+k):]for k,v in ro.items()if x.startswith('/'+k+'/')),x)for x in actual]
   if mode=='qualified_docker':
    e=self.execution;require(e['image'].startswith('sha256:')and e['qualified_readonly_isolation']and e['qualified_physical_quotas'],'qualified isolation/physical quotas required');container_name='ofc-'+identity({'root':str(root),'source':source_id})[:24]
    command=[e['docker_executable'],'run','--name',container_name,'--rm','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit',str(b['pids']),'--memory',str(b['memory_bytes']),'--cpus',str(b['cpus']),'--user',e['uid_gid'],'--tmpfs','/tmp:rw,noexec,nosuid,size='+str(b['tmp_bytes']),'--workdir','/workspace']
    for name,path in ro.items():command+=['--mount',f'type=bind,src={path},dst=/{name},readonly']
    for name,path in [('output',out),('scratch',scratch),('workspace',work)]:command+=['--mount',f'type=bind,src={path},dst=/{name}']
    command +=[e['image'],*actual]
   else:
    require(mode=='trusted_inert_engineering'and source_id in self.execution['allowed_inert_source_ids']and not self.execution['scientific_operations'],'unreviewed inert source');command=actual
   intent={'stage_id':stage_id,'argv':command,'request_id':request_id,'source_id':source_id,'mount_seals':sealed,'budget':b,'mode':mode,'start_monotonic':begin,'original_deadline':c.deadline};intent_identifier=identity(intent);write_new(root/'INTENT.json',intent)
   # Conservative full declared storage charge is consumed before any launch.
   lease=ledger.lease(b['output_bytes']+b['scratch_bytes']+b['log_bytes'],b['file_count']+3,self.job_id+'/'+stage_id)
   c.check('Popen original current clock');campaign.assert_contained()
   with stdout.open('xb')as so,stderr.open('xb')as se:
    c.check('Popen after log opens')
    process=subprocess.Popen(command,cwd=work,env={'PATH':self.execution['path'],'LANG':'C','LC_ALL':'C','PYTHONDONTWRITEBYTECODE':'1'},stdin=subprocess.PIPE if dialogue is not None else subprocess.DEVNULL,stdout=subprocess.PIPE if dialogue is not None else so,stderr=se,start_new_session=True,close_fds=True)
    attempt.update(launched=True,pid=process.pid,containment_resolved=False,status='running');slot.put({'state':'original_launched','job_id':self.job_id,'stage_id':stage_id,'pid':process.pid,'request_id':request_id,'source_id':source_id,'original_deadline':c.deadline})
    write_new(root/'STARTED.json',{'pid':process.pid,'stage_id':stage_id,'intent_id':intent_identifier})
    pending=b'';received=b'';sent=False;index=0;protocol_open=dialogue is not None;stdout_closed=dialogue is None
    if dialogue is not None:
     require(dialogue,'nonempty stream');selector=selectors.DefaultSelector();os.set_blocking(process.stdin.fileno(),False);os.set_blocking(process.stdout.fileno(),False);selector.register(process.stdout,selectors.EVENT_READ);selector.register(process.stdin,selectors.EVENT_WRITE)
     def next_message(i):
      q=dialogue[i];return {'schema':'ofc-prefix-query-v1','request_id':identity({'stage_request_id':request_id,'ordinal':i,'query':q}),'query':q}
     message=next_message(0);pending=canonical(message)+b'\n';require(len(pending)<=b['input_bytes'],'query byte quota')
    while process.poll()is None or not stdout_closed:
     c.check('process poll/EOF');observed=observed_writable([out,scratch,work]);logs=stdout.stat().st_size+stderr.stat().st_size
     require(observed['counters_complete']and observed['entries']<=b['file_count']and not observed['unsafe_entries'],'writable entry safety/quota');require(observed_writable([out])['bytes']<=b['output_bytes'],'output quota');require(observed_writable([scratch,work])['bytes']<=b['scratch_bytes'],'scratch/workspace quota');require(logs<=b['log_bytes'],'log quota')
     if selector is None:time.sleep(min(.01,max(0,c.deadline-campaign.clock())))
     else:
      for key,event in selector.select(min(.01,max(0,c.deadline-campaign.clock()))):
       c.check('stream read/write')
       if key.fileobj is process.stdin and pending:
        n=os.write(process.stdin.fileno(),pending[:65536]);pending=pending[n:]
        if not pending:sent=True;selector.unregister(process.stdin)
       elif key.fileobj is process.stdout:
        chunk=os.read(process.stdout.fileno(),65536)
        if not chunk:selector.unregister(process.stdout);stdout_closed=True;continue
        require(stdout.stat().st_size+stderr.stat().st_size+len(chunk)<=b['log_bytes'],'prospective stdout frame quota');so.write(chunk);so.flush();received+=chunk;require(len(received)<=b['output_bytes'],'response frame quota')
        if b'\n'in received:
         line,tail=received.split(b'\n',1);require(not tail and sent and index<len(dialogue),'unsolicited or extra response');response=decode(line);require(set(response)=={'request_id','row'}and response['request_id']==message['request_id'],'stream response identity');row=response['row'];require(row['query_id']==dialogue[index]['query_id']and row['family_id']==dialogue[index]['family_id'],'stream response key')
         receipt={'ordinal':index,'query_request_id':message['request_id'],'query_id':row['query_id'],'query_hash':identity(dialogue[index]),'response_hash':identity(response),'committed_before_next_query':True}
         append_record(root/'PREFIX_COMMITS.jsonl',{'receipt':receipt,'response':response});commits.append(receipt);responses.append(row);index+=1;received=b'';sent=False;c.check('next prefix admission')
         if index<len(dialogue):message=next_message(index);pending=canonical(message)+b'\n';require(len(pending)<=b['input_bytes'],'query byte quota');selector.register(process.stdin,selectors.EVENT_WRITE)
         else:process.stdin.close();protocol_open=False
    c.check('original wait');returncode=process.wait(timeout=max(.001,min(2,c.deadline-campaign.clock())));reaped=True;c.check('after original wait')
    if dialogue is not None:require(index==len(dialogue)and not received and not protocol_open,'incomplete prefix stream')
   require(returncode==0,'submitted process failed');c.check('completion admission')
   census(out,b['file_count'],b['output_bytes']);census(scratch,b['file_count'],b['scratch_bytes']);census(work,b['file_count'],b['scratch_bytes']);require(observed_writable([out,scratch,work])['entries']<=b['file_count'],'joint writable entry quota');require(observed_writable([scratch,work])['bytes']<=b['scratch_bytes'],'joint scratch quota');require(stdout.stat().st_size+stderr.stat().st_size<=b['log_bytes'],'completion log quota')
   for name,path in ro.items():verify_tree(path,sealed[name],b['file_count'],max(b['source_bytes'],b['input_bytes'],b['output_bytes']))
  except BaseException as e:fail(e)
  finally:
   # All fallible tail work preserves first cause. Even unavailable measurement
   # and ordinary publication must reach the already reserved terminal slot.
   writable=None;logs=None;entries=None;measurement_errors=[]
   def secondary(action,error):
    cleanup.append({'action':action,'error':error_record(error)});fail(error)
   def measure_elapsed(label):
    try:
     end=campaign.clock();duration=end-begin
     attempt.update(elapsed_seconds=duration,elapsed_observed=True,elapsed_measured_until_monotonic=end,elapsed_measurement_label=label)
    except BaseException as e:
     fail(e);attempt.update(elapsed_seconds=None,elapsed_observed=False,elapsed_measured_until_monotonic=None,elapsed_measurement_label=label)
   try:
    if selector is not None:
     try:selector.close()
     except BaseException as e:secondary('selector_close',e)
    if process is not None:
     try:
      if process.poll()is None:terminate('original_failure_or_expiry')
     except BaseException as e:
      containment=False;secondary('original_poll_or_termination',e)
      try:process.kill();cleanup.append({'action':'fallback_original_kill','delivered':True})
      except BaseException as secondary_error:secondary('fallback_original_kill',secondary_error)
     try:returncode=process.wait(timeout=2);reaped=True
     except BaseException as e:containment=False;secondary('bounded_original_wait',e)
     try:os.killpg(process.pid,0)
     except ProcessLookupError:pass
     except BaseException as e:containment=False;secondary('final_group_probe',e)
     else:
      containment=False
      try:terminate('descendants_survived_original')
      except BaseException as e:secondary('descendant_termination',e)
      cleanup.append({'action':'final_group_probe','group_still_present':True})
    if container_name is not None and primary is not None:
     try:
      with (root/'container-cleanup.log').open('xb')as log:r=subprocess.run([self.execution['docker_executable'],'rm','--force',container_name],stdout=log,stderr=log,timeout=2,check=False)
      cleanup.append({'action':'container_rm_force','returncode':r.returncode});containment=containment and r.returncode==0
     except BaseException as e:containment=False;secondary('container_rm_force',e)
    attempt.update(original_returncode=returncode,original_reaped=reaped,containment_resolved=containment,forced_stop=forced,cleanup_events=cleanup)
    if not containment:fail(UnresolvedContainment('original process/group/container absence not established'))
    try:
     writable=observed_writable([out,scratch,work])
     if not writable['counters_complete']:raise LifecycleError('post-reap writable counters unavailable')
    except BaseException as e:measurement_errors.append(error_record(e));fail(e)
    observed_logs=0;observed_log_entries=0
    try:
     for path in (stdout,stderr,root/'container-cleanup.log'):
      try:info=path.stat()
      except FileNotFoundError:continue
      observed_logs+=info.st_size;observed_log_entries+=1
     logs=observed_logs
    except BaseException as e:measurement_errors.append(error_record(e));fail(e)
    measured=writable is not None and writable.get('counters_complete')is True and logs is not None
    if lease is not None:
     if measured:
      entries=writable['entries']+observed_log_entries
      try:ledger.settle(lease,writable['bytes']+logs,entries)
      except BaseException as e:
       lease.update(settlement_error=error_record(e),settlement_outcome_qualified=False);measurement_errors.append(error_record(e));fail(e)
     else:lease.update(settlement_outcome_qualified=False,measurement_status='unavailable_reservation_retained',measurement_errors=list(measurement_errors))
    if primary is None:
     try:
      c.protected('post-cleanup output collection')
      if dialogue is not None:
       require(not(out/'response.json').exists(),'stream worker cannot author trusted aggregate');bootstrap=load(ro['request']/'request.json');write_new(out/'response.json',{'schema':'ofc-response-v1','request_id':request_id,'source_id':source_id,'model_id':bootstrap['model_id'],'rows':responses})
      outputseal=seal_tree(out,b['file_count'],b['output_bytes']);c.check('after final output seal');attempt['status']='completed_naturally'
     except BaseException as e:fail(e)
   except BaseException as e:
    # This outer catch prevents any newly introduced tail adapter from jumping
    # past the reserved terminal attempt. No measured value is invented.
    fail(e);measurement_errors.append(error_record(e))
   finally:
    attempt.update(original_returncode=returncode,original_reaped=reaped,containment_resolved=containment,forced_stop=forced,cleanup_events=cleanup,request_count=self.request_count,observed_writable=writable,log_bytes=logs,measurement_status='complete'if not measurement_errors and writable is not None and logs is not None else'unavailable_or_partial',measurement_errors=measurement_errors,output_seal=outputseal,prefix_commits=commits,intent_id=intent_identifier,aggregate_origin='trusted_host_from_original_stdout_commits'if dialogue is not None else'participant_output_files')
    measure_elapsed('before ordinary observation publication')
    try:write_new(root/'OBSERVATION.json',attempt,closing=True)
    except BaseException as e:fail(e)
    try:c.check('observation publication completion')
    except BaseException as e:fail(e)
    measure_elapsed('before reserved terminal publication')
    try:
     terminal_error=campaign.put_terminal(slot,attempt)
     if terminal_error is not None:fail(terminal_error)
    except BaseException as e:fail(e);attempt['terminal_custody_saved']=False
    # Initial reservation + launch + two terminal attempts fit four precharged
    # writes. A failed physical write never becomes successful custody.
    correction_needed=not attempt.get('terminal_custody_saved',False)
    try:c.check('reserved terminal publication completion')
    except BaseException as e:fail(e);correction_needed=True
    measure_elapsed('after first reserved terminal publication')
    if not attempt['elapsed_observed']:correction_needed=True
    if correction_needed:
     try:
      terminal_error=campaign.put_terminal(slot,attempt)
      if terminal_error is not None:fail(terminal_error)
     except BaseException as e:fail(e);attempt['terminal_custody_saved']=False
    measure_elapsed('after all reserved terminal attempts')
    try:c.check('final stage return')
    except BaseException as e:fail(e)
    if attempt['elapsed_observed'] and self.total_wall_observed:
     self.total_wall+=attempt['elapsed_seconds'];attempt['cumulative_elapsed_seconds']=self.total_wall
    else:self.total_wall_observed=False;attempt['cumulative_elapsed_seconds']=None
  if primary is not None:raise primary
  if not attempt.get('terminal_custody_saved'):raise LifecycleError('original terminal custody unavailable')
  return out,attempt
