"""Actual original worker supervision through unchanged reviewed pidfd source."""
import base64,math
from central_io import need,encoded,pin,parse,IO
from .observer_vendor.host import observe_controller
BOOTSTRAP="import base64,hashlib,sys; b=base64.b64decode(sys.argv[1],validate=True); assert hashlib.sha256(b).hexdigest()==sys.argv[2]; p=sys.argv[3]; sys.argv=[p,*sys.argv[4:]]; exec(compile(b,p,'exec'),{'__name__':'__main__','__file__':p})"
class ObserverBudget:
 def __init__(self,io,root):self.io=io;self.root=root;self.events=[]
 def tick(self):return self.io.tick()
 def read(self,n):
  self.io.tick();need(type(n)is int and n>=0,'Exact observer request extent');self.io.reads+=n;need(self.io.reads<=self.io.read_cap,'Full observer requested-read charge')
 def event(self,value):
  need(len(self.events)<64,'Bounded original observer journal');raw=encoded(value);need(len(raw)<=262144,'Complete observer journal body')
  d=self.io.save(self.root/(str(len(self.events))+'.json'),raw);self.events.append(d);return d

def binding(bound,q):
 clock=bound['original_clock'];p=bound['profile']
 # Round toward the earlier side; floating observer clocks never extend a
 # selected original integer deadline.
 end=math.nextafter((clock['outer_ns']-p['entry_finish_ns'])/1e9,-math.inf)
 cutoff=math.nextafter((clock['outer_ns']-p['entry_finish_ns']-p['worker_grace_seconds']*10**9)/1e9,-math.inf)
 return {'schema':'neural004_central_worker_binding_v1','repository':str(bound['repository']),'central_root':q['bindings']['central_root'],
  'source_manifest_pin':q['source_manifest_pin'],'source_freeze_pin':q['source_freeze_pin'],
  'parent_manifest_pin':q['parent_manifest_pin'],'profile':p,'operation':{'path':bound['operation_path'],**bound['operation_pin']},
  'config':{'path':bound['config_path'],**bound['config_body_pin']},'output':str(bound['output']),
  'origin':clock['origin_ns']/1e9,'deadline':end,'cutoff':cutoff,'original_clock':clock}

def argv_for(bound,q):
 b=binding(bound,q);p=bound['profile'];repo=bound['repository'];raw=q['own']['worker.py'];text=encoded(b).decode()
 need(len(raw)<=65536 and len(text.encode())<=65536,'Exact bounded worker bootstrap arguments')
 argv=[p['worker_python']['path'],'-I','-S','-B','-c',BOOTSTRAP,base64.b64encode(raw).decode(),pin(raw)['sha256'],str(repo/q['bindings']['central_root']/'worker.py'),text]
 return b,argv

def observe(io,bound,q):
 b,argv=argv_for(bound,q);p=bound['profile'];root=bound['output']
 oio=IO(p['observer_read_bytes'],p['observer_write_bytes'],p['observer_retained_bytes'],b['origin'],b['deadline'])
 journal=root/'observer-journal';oio.directories(journal);budget=ObserverBudget(oio,journal)
 close=None;close_pin=None;ret=None;ret_pin=None;failure=None;errors=[];logs={}
 try:close=observe_controller(argv,root,{'origin':b['origin'],'deadline':b['deadline']},b['cutoff'],budget,p['worker_grace_seconds'],p['worker_log_bytes'],p['worker_memory_bytes'])
 except BaseException as error:errors.append({'stage':'observe','type':type(error).__name__,'message':str(error)[:1000]})
 if close is not None:
  raw_logs=close.pop('logs_data',{})
  for name in ('stdout','stderr'):
   try:
    data=raw_logs[name];need(type(data)is bytes and pin(data)==close['logs'][name],'Exact complete original worker stream')
    logs[name]=oio.save(root/('worker.'+name+'.log'),data)
   except BaseException as error:errors.append({'stage':'stream_'+name,'type':type(error).__name__})
  try:close_pin=oio.save(root/'WORKER_CLOSE.json',encoded(close))
  except BaseException as error:errors.append({'stage':'close_publication','type':type(error).__name__})
 try:
  data=io.capture(root/'WORKER_RETURN.json',cap=p['worker_return_bytes']);ret=parse(data);ret_pin=pin(data)
 except BaseException as error:errors.append({'stage':'return_capture','type':type(error).__name__})
 try:
  data=io.capture(root/'WORKER_FAILURE.json',cap=p['worker_return_bytes']);failure={'pin':pin(data),'record':parse(data)};errors.append({'stage':'worker_failure_present','type':'WorkerFailure'})
 except FileNotFoundError:pass
 except BaseException as error:errors.append({'stage':'failure_capture','type':type(error).__name__})
 for name,tick in (('observer_clock',oio.tick),('entry_clock',io.tick)):
  try:tick()
  except BaseException as error:errors.append({'stage':name,'type':type(error).__name__})
 return {'binding':b,'argv':argv,'close':close,'close_pin':close_pin,'worker_return':ret,'worker_return_pin':ret_pin,'worker_failure':failure,
  'logs':logs,'observer_costs':oio.snapshot(),'observer_events':budget.events,'errors':errors,'automatic_retry':False}
