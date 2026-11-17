"""Original process custody. No process is started merely by importing this module."""
from dataclasses import dataclass,field
import os,selectors,signal,subprocess,time
from .contracts import Custody,need,canonical,digest,Refusal,finite

@dataclass
class Observation:
 job:str
 request:dict
 dispatched:bool=False
 launch_attempted:bool=False
 pid:object=None
 exit_code:object=None
 reaped:bool=False
 stdout:bytearray=field(default_factory=bytearray)
 stderr:bytearray=field(default_factory=bytearray)
 stream_eof:dict=field(default_factory=lambda:{'stdout':False,'stderr':False})
 absence:object=None
 costs:dict=field(default_factory=lambda:{'cpu_seconds':None,'memory_peak_bytes':None})
 custody:object=None
 started:object=None
 ended:object=None
 persistence:dict=field(default_factory=dict)
 service_stdin:bytearray=field(default_factory=bytearray)
 service_events:list=field(default_factory=list)
 initial_stdin_bytes_written:int=0
 def public(self):
  request={**self.request,'stdin':{'bytes':len(self.request['stdin']),'sha256':digest(self.request['stdin'])}}
  return {'job':self.job,'request':request,'dispatched':self.dispatched,'launch_attempted':self.launch_attempted,'dispatch_status':'observed_started'if self.dispatched else'unknown_after_launch_attempt'if self.launch_attempted else'not_attempted','pid':self.pid,'exit_code':self.exit_code,'reaped':self.reaped,'stream_eof':dict(self.stream_eof),'absence':self.absence,'costs':dict(self.costs),'started':self.started,'ended':self.ended,'stdout':{'bytes':len(self.stdout),'sha256':digest(bytes(self.stdout))},'stderr':{'bytes':len(self.stderr),'sha256':digest(bytes(self.stderr))},'persistence':dict(self.persistence),'initial_stdin_bytes_written':self.initial_stdin_bytes_written,'service_stdin':{'bytes':len(self.service_stdin),'sha256':digest(bytes(self.service_stdin))},'service_events':list(self.service_events),'terminal':self.custody.snapshot()}

def run(job,request,budget,isolation,*,popen=subprocess.Popen,clock=time.monotonic,observation=None,reference_service=None):
 """Strong Observation is attached before every fallible publication/cleanup.

 The isolation object is a qualified LinuxCgroupSandbox in production. Inert
 controls replace only that native boundary, never claim native containment.
 """
 o=observation if observation is not None else Observation(job,dict(request),custody=Custody('process:'+job));c=o.custody;c.original=o
 from .isolation import LinuxCgroupSandbox
 if type(isolation)is LinuxCgroupSandbox:isolation.custody=c;isolation.store.custody=c
 proc=None;sel=None;opened=[];cpu_charged=False;cpu_joined=0.0
 pending=[];pending_offset=0;line=bytearray();discard_line=False;active_event=None
 from .reference_service import PREFIX,FRAME_CAP
 def close_pipe(name,pipe,phase):
  # The source owner records transfer BEFORE either early EOF delivery or final
  # cleanup calls close. A failed close never proves that the descriptor remains
  # owned, even if a later .closed observation is false.
  status=c.facts['pipe_closes'][name]
  if status['attempted']:return
  status['attempted']=True;status['attempt_phase']=phase;status['ownership']='close_attempted'
  try:pipe.close();status['closed']=True;status['ownership']='released'
  except BaseException as error:
   status['ownership']='unknown_after_close';status['close_failed_or_unknown']=True
   c.fail(error,phase+':'+name)
   try:status['closed']=pipe.closed
   except BaseException as secondary:c.fail(secondary,'pipe_close_observation:'+name)
 def stream_cap(admit=False,pipe=None,name=None,drain=None):
  used=len(o.stdout)+len(o.stderr)+len(o.service_stdin)
  if not admit and pipe is None:
   need(used<=request['stream_limit'],'complete bidirectional stream cap');return
  # Host process transport retains its original stream_bytes attribution.
  # Artifact/worker input reads keep their separate original read_bytes ledger.
  budget.admit();need(clock()<budget.deadline,'original pipe effect deadline')
  capacity=min(65536,budget.available('stream_bytes'),request['stream_limit']-used)
  need(type(capacity)is int and capacity>0,'original pipe residual stream capacity unavailable')
  if pipe is None:return capacity
  need(name in('stdout','stderr'),'owned original output stream')
  need(os.get_blocking(pipe.fileno())is False,'original output pipe nonblocking state unknown')
  key=('final_'if drain is not None else'normal_')+name
  row=c.facts.setdefault('pipe_read_accounting',{}).setdefault(key,
      {'attempts':0,'known_returned_bytes':0,'unknown_consumption_capacity':0,
       'last_capacity':None,'last_status':None,'last_returned_bytes':None})
  row['attempts']+=1;row['last_capacity']=capacity;row['last_status']='attempted';row['last_returned_bytes']=None
  if drain is not None:drain['admitted']=True;drain['read_attempts']+=1
  try:b=os.read(pipe.fileno(),capacity)
  except BlockingIOError:
   # EAGAIN is a known no-byte result, not permission to block or infer EOF.
   row['last_status']='would_wait';row['last_returned_bytes']=0;raise
  except BaseException as error:
   # Retain the raw cause before conservative unknown-effect accounting.
   c.fail(error,'original_pipe_read:'+key);row['last_status']='unknown_consumption'
   row['unknown_consumption_capacity']+=capacity;budget.stop('unknown original stream read '+job)
   try:budget.charge('stream_bytes',capacity)
   except BaseException as secondary:c.fail(secondary,'unknown_stream_read_charge:'+key)
   c.raise_if_failed()
  row['last_returned_bytes']=len(b);row['known_returned_bytes']+=len(b);row['last_status']='returned'
  # Keep actual bytes before a later accounting error; never charge a new pool.
  getattr(o,name).extend(b)
  if drain is not None:drain['accepted_bytes']+=len(b)
  budget.charge('stream_bytes',len(b));stream_cap()
  return b
 def join_cpu(total):
  nonlocal cpu_joined
  finite(total);need(type(total)in(int,float)and total>=cpu_joined,'known monotone original cgroup CPU')
  delta=total-cpu_joined
  # Charge increments counters before any resource-limit exception; retain the
  # same joined extent before charging so finalization cannot double-count it.
  cpu_joined=total;budget.charge('cpu_seconds',delta)
 def dispatch(raw):
  nonlocal pending,pending_offset,active_event
  need(reference_service is not None and not pending,'one synchronous original service request')
  budget.admit();need(len(raw)+len(PREFIX)<=FRAME_CAP,'bounded original service request frame')
  event={'request':{'bytes':len(raw),'sha256':digest(raw)},'requested_at':clock(),
         'pause_attempted':False,'paused_at':None,'cpu_joined':None,'resume_attempted':False,
         'resumed_at':None,'response':None,'delivered_bytes':0,'delivery_complete':False}
  o.service_events.append(event);active_event=event
  try:
   event['pause_attempted']=True;isolation.pause(budget.deadline);event['paused_at']=clock()
   join_cpu(isolation.running_cpu());event['cpu_joined']=cpu_joined;budget.admit()
   frames=reference_service.exchange(raw);budget.admit()
   need(type(frames)is list and frames and all(type(x)is bytes and x.endswith(b'\n')and len(x)<=FRAME_CAP for x in frames),'closed bounded service response frames')
   extent=sum(map(len,frames));need(extent<=budget.available('stream_bytes')and len(o.stdout)+len(o.stderr)+len(o.service_stdin)+extent<=request['stream_limit'],'residual original bidirectional stream allowance')
   event['response']={'bytes':extent,'sha256':digest(b''.join(frames))}
   pending=frames;pending_offset=0
  except BaseException as error:c.fail(error,'reference_service_exchange',reference_service.custody)
  finally:
   # A failed pause may still have frozen the actor; always attempt thaw.
   if event['pause_attempted']:
    event['resume_attempted']=True
    try:isolation.resume(budget.deadline);event['resumed_at']=clock()
    except BaseException as error:c.fail(error,'reference_service_resume')
  c.raise_if_failed()
  need(proc is not None and not proc.stdin.closed,'original response pipe open')
  try:sel.get_key(proc.stdin)
  except KeyError:sel.register(proc.stdin,selectors.EVENT_WRITE,'stdin')
 def inspect_stdout(raw,eof=False):
  nonlocal discard_line
  # Keep only a possible prefixed control line. Arbitrary programme stdout
  # remains verbatim in Observation and has no new per-line restriction.
  for fragment in raw.splitlines(keepends=True):
   complete=fragment.endswith(b'\n')
   if not discard_line:
    line.extend(fragment)
    possible=PREFIX.startswith(bytes(line))or line.startswith(PREFIX)
    if not possible:line.clear();discard_line=True
    else:
     need(len(line)<=FRAME_CAP,'bounded original service request line')
     if complete:
      need(line.startswith(PREFIX),'complete service request prefix');body=bytes(line[len(PREFIX):]);line.clear();dispatch(body)
   if complete:line.clear();discard_line=False
  if eof and line:need(not(PREFIX.startswith(bytes(line))or line.startswith(PREFIX)),'truncated original service request')
 try:
  budget.admit();need(o.job==job and o.request==request,'caller-owned original observation');isolation.validate(request);argv,env,preexec=isolation.command(request)
  c.phase='launch';o.started=clock();o.launch_attempted=True;proc=popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,cwd='/',start_new_session=True,preexec_fn=preexec,close_fds=True)
  opened=[('stdout',proc.stdout),('stderr',proc.stderr),('stdin',proc.stdin)]
  c.facts['pipe_closes']={name:{'owned':True,'attempted':False,'closed':False,'nonblocking_setup_attempted':False,'nonblocking_setup_observed':False}for name,pipe in opened}
  o.dispatched=True;o.pid=proc.pid;c.phase='running';sel=selectors.DefaultSelector()
  for name,pipe in opened:
   state=c.facts['pipe_closes'][name];state['nonblocking_setup_attempted']=True
   os.set_blocking(pipe.fileno(),False);need(os.get_blocking(pipe.fileno())is False,'original pipe nonblocking setup observed');state['nonblocking_setup_observed']=True
   sel.register(pipe,selectors.EVENT_WRITE if name=='stdin'else selectors.EVENT_READ,name)
  payload=request['stdin'];need(type(payload)is bytes,'literal stdin bytes');offset=0
  if reference_service is not None:need(payload.endswith(b'\n')and payload.count(b'\n')==1,'one original newline envelope before service frames')
  while sel.get_map()or proc.poll()is None:
   budget.guard();isolation.check_runtime()
   if reference_service is not None:need(isolation.running_cpu()-cpu_joined<=budget.available('cpu_seconds'),'remaining combined actor/service CPU allowance')
   code=proc.poll()
   if code is not None:o.exit_code=code;o.reaped=True
   for key,mask in sel.select(min(.1,max(0,budget.deadline-clock()))):
    name=key.data
    if name=='stdin':
     if offset<len(payload):
      try:
       n=os.write(key.fileobj.fileno(),payload[offset:offset+65536]);offset+=n;o.initial_stdin_bytes_written+=n
      except BrokenPipeError:
       if reference_service is not None:raise
       offset=len(payload)
     elif pending:
      capacity=stream_cap(admit=True)
      need(os.get_blocking(key.fileobj.fileno())is False,'original service pipe nonblocking state unknown')
      raw=pending[0][pending_offset:pending_offset+capacity]
      n=os.write(key.fileobj.fileno(),raw);need(n>0,'original service pipe progress')
      # Retain actual delivered bytes before a later charge can fail.
      o.service_stdin.extend(raw[:n]);active_event['delivered_bytes']+=n;pending_offset+=n
      budget.charge('stream_bytes',n);stream_cap()
      if pending_offset==len(pending[0]):pending.pop(0);pending_offset=0
      if not pending:active_event['delivery_complete']=True;active_event['delivered_at']=clock()
     if offset==len(payload)and not pending:
      sel.unregister(key.fileobj)
      if reference_service is None:
       close_pipe('stdin',key.fileobj,'initial_stdin_close');c.raise_if_failed()
    else:
     b=stream_cap(pipe=key.fileobj,name=name)
     if not b:
      o.stream_eof[name]=True;sel.unregister(key.fileobj)
      if name=='stdout'and reference_service is not None:inspect_stdout(b'',eof=True)
     else:
      if name=='stdout'and reference_service is not None:inspect_stdout(b)
  need(not pending,'original service response not fully delivered')
  o.exit_code=proc.wait(timeout=max(.001,budget.deadline-clock()));o.reaped=True;c.phase='original_exit';need(o.exit_code==0,'original child nonzero')
 except BaseException as e:c.fail(e,c.phase)
 finally:
  # Capture the original observed result before cleanup can fail. A missing
  # PROCESS file never changes dispatched into not_dispatched.
  if proc is not None:
   try:
    code=proc.poll()
    if code is not None:o.exit_code=code;o.reaped=True
   except BaseException as e:c.fail(e,'observe_original_exit')
   # Cgroup termination failure cannot suppress the independent direct-child
   # termination attempt or its original bounded wait.
   if not o.reaped:
    try:isolation.kill()
    except BaseException as e:c.fail(e,'terminate_group')
    try:proc.kill()
    except BaseException as e:c.fail(e,'terminate_direct_child')
   try:
    if not o.reaped:o.exit_code=proc.wait(timeout=max(.001,min(2,budget.deadline-clock())));o.reaped=True
   except BaseException as e:c.fail(e,'reap')
  try:o.absence=isolation.quiesce(budget.deadline)
  except BaseException as e:c.fail(e,'descendant_absence')
  try:
   measured=isolation.measure();c.original_final_resource_observation=measured;o.costs.update(measured)
   need(o.costs['cpu_seconds']is not None,'unknown CPU cannot certify budget');join_cpu(o.costs['cpu_seconds'])
   # A live or unobserved descendant can consume more CPU after this snapshot.
   # Charge the known observed delta once, but never label it the final total.
   need(o.absence is True,'final CPU unknown without original descendant absence');cpu_charged=True
  except BaseException as e:
   o.costs['observed_cpu_seconds_lower_bound']=cpu_joined;o.costs['cpu_seconds']=None
   c.fail(e,'final_resource_observation');budget.stop('unknown or exceeded final CPU '+job)
  # No blocking cleanup read is permitted. An early selector/setup failure may
  # leave these adopted pipes blocking; unknown descendant custody may leave a
  # writer alive. Preserve unknown EOF and already delivered bytes in either
  # case. Independent close attempts below do not depend on drain admission.
  c.facts['final_pipe_drains']={}
  for name in('stdout','stderr'):
   pipe=getattr(proc,name,None)if proc else None
   drain={'admitted':False,'nonblocking_attempted':False,'nonblocking_observed':False,'absence':o.absence,'read_attempts':0,'accepted_bytes':0,'eof_observed':False,'reason':None};c.facts['final_pipe_drains'][name]=drain
   try:
    if pipe is None or pipe.closed:drain['reason']='pipe_unavailable_or_closed';continue
    if o.stream_eof[name]:drain['reason']='original_eof_already_observed';continue
    if o.absence is not True:drain['reason']='original_descendant_absence_unknown';continue
    budget.admit();need(clock()<budget.deadline,'original final drain deadline')
    drain['nonblocking_attempted']=True;os.set_blocking(pipe.fileno(),False)
    need(os.get_blocking(pipe.fileno())is False,'final pipe nonblocking state unknown');drain['nonblocking_observed']=True
    while True:
     try:b=stream_cap(pipe=pipe,name=name,drain=drain)
     except BlockingIOError:drain['reason']='nonblocking_read_would_wait';break
     if not b:o.stream_eof[name]=True;drain['eof_observed']=True;drain['reason']='original_eof';break
   except BaseException as e:drain['reason']='drain_admission_or_read_failed';c.fail(e,'final_stream_read:'+name)
  for name,pipe in opened:
   close_pipe(name,pipe,'pipe_close')
  if sel is not None:
   try:sel.close()
   except BaseException as e:c.fail(e,'selector_close')
  try:o.ended=clock()
  except BaseException as e:c.fail(e,'final_clock');budget.stop('unknown final clock '+job)
  if reference_service is not None:
   try:c.facts['reference_service']=reference_service.finish()
   except BaseException as e:c.fail(e,'reference_service_closure',reference_service.custody)
  c.facts['original_cgroup_cpu_joined']=cpu_joined
  try:c.facts['resource_snapshot']=budget.snapshot()
  except BaseException as e:c.fail(e,'final_resource_snapshot');budget.stop('unknown final resource snapshot '+job)
  try:
   budget.guard();need(o.reaped and all(o.stream_eof.values())and o.absence is True and cpu_charged,'incomplete original process custody');need(o.exit_code==0,'original child nonzero')
  except BaseException as e:c.fail(e,'completion')
  c.complete=c.first_error is None
 return o

def persist(observation,store,prefix):
 """Caller always retains observation, even if no JSON can be published."""
 o=observation;c=o.custody
 from .contracts import Store
 def publish(name,raw,cap):
  publication=Custody('terminal_publication:'+name);writer=Store(store.root,store.budget,publication)
  try:return writer.write(name,raw,cap)
  finally:c.fail(None,'original_terminal_publication',publication)
 for name in(('stdin','stdout','stderr','service_stdin')if o.service_events or o.service_stdin else('stdin','stdout','stderr')):
  try:o.persistence[name]=publish(prefix+'.'+name,o.request['stdin']if name=='stdin'else bytes(getattr(o,name)),max(len(o.request['stdin']),o.request['stream_limit']))
  except BaseException as e:c.fail(e,'publish_'+name)
 try:
  # Do not serialize the recursive original_observation strong carrier.
  body=o.public();o.persistence['process']=publish(prefix+'.process.json',canonical(body),8*2**20)
 except BaseException as e:c.fail(e,'publish_process')
 return o
