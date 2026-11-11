"""New actual spawn/serialization ownership controls with invented ordinary source.

No PyTorch, original npyx, scientific arrays, network, model or old campaign runs.
Each case gets fresh helpers with only fixed-manifest constants rebound to an
invented descriptor. Actual source/import/bootstrap/process code stays unchanged.
"""
from pathlib import Path
import ast,base64,hashlib,json,os,re,signal,subprocess,sys,time

P=Path(__file__).resolve().parents[1]
OUT=P
import tempfile
if 'C4_SOURCE_TEST_ROOT' not in os.environ:
 os.environ['C4_SOURCE_TEST_ROOT']=str(Path(tempfile.mkdtemp(prefix='c4-source-tests-')).resolve())
ROOT=Path(os.environ['C4_SOURCE_TEST_ROOT'])/'spawn-cases'
HELPERS=('__init__.py','io_core.py','dependencies.py','import_guard.py','spawn_guard.py')

def pin(p):
 b=p.read_bytes();assert len(b)<=1048576
 return{'path':str(p.relative_to(P))if p.is_relative_to(P)else 'fixture/'+str(p.relative_to(ROOT)),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def encode(v):return(json.dumps(v,indent=2,sort_keys=True)+'\n').encode()
def put(p,b):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('xb')as f:f.write(b)
def check(v,label):
 global ASSERTIONS
 ASSERTIONS+=1
 if not v:raise AssertionError(label)

DATASET='''class CustomDataset:
    def __init__(self, token): self.token = token
    def __setstate__(self, state):
        from c4_distribution.import_guard import require_bound_source
        owner = require_bound_source()
        import sys
        assert type(sys.modules[__name__].__spec__.loader).__name__ == "_OriginalLoader"
        self.__dict__.update(state)
        self.bound_during_unpickle = owner.manifest_sha256
'''

def receive(dataset, connection, block):
 from c4_distribution.import_guard import require_bound_source
 v=require_bound_source()
 import npyx.c4.run_deep_classifier as original
 connection.send({'token':dataset.token,'bound_at_unpickle':dataset.bound_during_unpickle,
                  'manifest':v.manifest_sha256,'loader':type(original.__spec__.loader).__name__,
                  'root':str(v.root),'file_count':len(v.files)})
 if block:connection.recv()
 connection.close()

# Deliberate, bounded process-preparation failures. They occur after the source
# binder is installed but before the process/dataset pickle is read.
if __name__=='__mp_main__':
 case=os.environ.get('C4_SOURCE_CONTROL_CASE')
 if case=='preparation_replaces_namespace':
  import types
  sys.modules['npyx']=types.ModuleType('npyx')
 elif case=='blocked_preparation':
  time.sleep(0.3)
 elif case=='early_preparation_exit':
  os._exit(71)

def fixture(name):
 root=ROOT/name;runtime=root/'runtime';checkout=root/'invented-originals'
 spec=json.loads((OUT/'REQUIRED_ORIGINAL_SOURCE.json').read_bytes())
 for row in spec['files']:
  body=(DATASET if row['path']=='npyx/c4/run_deep_classifier.py'else '# invented ordinary fixture\n').encode()
  if row['path']=='npyx/histo.py':body=b''
  row['bytes']=len(body);row['sha256']=hashlib.sha256(body).hexdigest()
  row['git_blob']=hashlib.sha1(b'blob '+str(len(body)).encode()+b'\0'+body).hexdigest()
  put(checkout/row['path'],body)
 spec['total_bytes']=sum(r['bytes']for r in spec['files'])
 manifest=encode(spec);put(runtime/'REQUIRED_ORIGINAL_SOURCE.json',manifest)
 hashes=[]
 for n in HELPERS:
  raw=(OUT/'c4_distribution'/n).read_bytes()
  if n=='dependencies.py':
   text=raw.decode()
   text,n1=re.subn(r'^MANIFEST_SHA256 = "[a-f0-9]+"$', 'MANIFEST_SHA256 = "'+hashlib.sha256(manifest).hexdigest()+'"',text,flags=re.M)
   text,n2=re.subn(r'^MANIFEST_BYTES = [0-9]+$', 'MANIFEST_BYTES = '+str(len(manifest)),text,flags=re.M)
   assert(n1,n2)==(1,1);raw=text.encode()
  put(runtime/'c4_distribution'/n,raw);hashes.append(pin(runtime/'c4_distribution'/n))
 put(root/'ambient/npyx/__init__.py',b'raise RuntimeError("ambient npyx must never execute")\n')
 return root,runtime,checkout,hashes

def one_case(name):
 global ASSERTIONS
 ASSERTIONS=0
 root,runtime,checkout,helpers=fixture(name)
 before=[pin(OUT/'c4_distribution'/n)for n in HELPERS]
 sys.path[:0]=[str(root/'ambient'),str(runtime)]
 from c4_distribution import dependencies,spawn_guard
 from c4_distribution.import_guard import activate_originals
 prepared=root/'prepared'
 dependencies.prepare_dependencies(prepared,source_root=checkout)
 verified=activate_originals(prepared)
 from npyx.c4.run_deep_classifier import CustomDataset
 dataset=CustomDataset('captured-fixture-'+name)
 refusals=0
 if name=='four_workers_before_unpickle':
  with spawn_guard.source_worker_scope()as owner:
   context=spawn_guard.worker_context();children=[];connections=[]
   for _ in range(4):
    parent,child=context.Pipe()
    worker=context.Process(target=receive,args=(dataset,child,True));worker.start();child.close()
    check(parent.poll(3),'worker message available');value=parent.recv()
    check(value['token']==dataset.token,'captured class token')
    check(value['manifest']==verified.manifest_sha256==value['bound_at_unpickle'],'actual binding during __setstate__')
    check(value['loader']=='_OriginalLoader'and value['file_count']==41,'complete41 captured loader')
    children.append(worker);connections.append(parent)
   check(len(owner.active)==4,'four actual owned workers')
   try:context.Process(target=receive,args=(dataset,connections[0],False)).start()
   except dependencies.SourceError:refusals+=1
   else:raise AssertionError('fifth worker must refuse')
   for c in connections:c.send('finish');c.close()
   for c in children:c.join(3);check(c.exitcode==0,'normal child retirement')
  check(not owner.active and owner.retired_count==4,'all four observed retired')
 elif name=='captured_bytes_survive_original_disk_change':
  changed=prepared/'npyx/c4/run_deep_classifier.py';os.chmod(changed,0o644);changed.write_bytes(b'raise RuntimeError("changed disk original must not execute")\n')
  with spawn_guard.source_worker_scope()as owner:
   context=spawn_guard.worker_context();parent,child=context.Pipe()
   worker=context.Process(target=receive,args=(dataset,child,False));worker.start();child.close()
   check(parent.poll(3),'captured child result');value=parent.recv();parent.close();worker.join(3)
   check(value['token']==dataset.token and value['manifest']==verified.manifest_sha256,'child executes captured original bytes')
   check(worker.exitcode==0,'captured worker exit')
  check(not owner.active and owner.retired_count==1,'captured worker retired')
 elif name in ('preparation_replaces_namespace','blocked_preparation','early_preparation_exit','tampered_captured_original'):
  os.environ['C4_SOURCE_CONTROL_CASE']=name
  if name=='blocked_preparation':spawn_guard._STARTUP_SECONDS=0.08
  if name=='tampered_captured_original':
   original_snapshot=spawn_guard._snapshot
   def tampered():
    raw,identity=original_snapshot();capsule=json.loads(raw)
    capsule['originals']['npyx/c4/run_deep_classifier.py']=base64.b64encode(b'# not selected bytes\n').decode()
    return json.dumps(capsule).encode(),identity
   spawn_guard._snapshot=tampered
  with spawn_guard.source_worker_scope()as owner:
   context=spawn_guard.worker_context();parent,child=context.Pipe()
   try:context.Process(target=receive,args=(dataset,child,False)).start()
   except BaseException as exc:
    refusals+=1;check(hasattr(exc,'c4_spawn_owner'),'failed startup retains custody')
   else:raise AssertionError('invalid worker startup accepted')
   finally:parent.close();child.close()
   check(not owner.active and owner.retired_count==1,'failed startup positively retired')
  check(not owner.launch_unknown,'owned PID observed and retired')
 elif name=='live_worker_retired_on_scope_failure':
  marker=RuntimeError('invented operation failure');owner=None
  try:
   with spawn_guard.source_worker_scope()as owner:
    context=spawn_guard.worker_context();parent,child=context.Pipe()
    worker=context.Process(target=receive,args=(dataset,child,True));worker.start();child.close()
    check(parent.poll(3),'live child acknowledgement');parent.recv()
    raise marker
  except RuntimeError as exc:check(exc is marker and exc.c4_spawn_owner is owner,'primary failure preserved')
  finally:parent.close()
  check(not owner.active and owner.retired_count==1,'live child terminated and reaped')
  check(worker.exitcode is not None,'worker exit observed')
 elif name=='unobservable_retirement':
  class Unknown:
   pid=123456789;returncode=None
   def poll(self):raise OSError('invented poll failure')
   def terminate(self):raise OSError('invented terminate failure')
   def kill(self):raise OSError('invented kill failure')
   def wait(self,timeout):return None
  owner=spawn_guard._WorkerScope();worker=Unknown();owner.active[worker.pid]=worker
  errors=owner.retire_one(worker)
  check(len(errors)==4,'poll/TERM/KILL/unknown failures retained')
  check(owner.active[worker.pid]is worker and owner.retired_count==0,'unknown owner not retired')
  check('unknown'in str(errors[-1]),'explicit unknown cleanup')
  refusals+=1
 else:raise AssertionError(name)
 after=[pin(OUT/'c4_distribution'/n)for n in HELPERS]
 check(before==after,'actual current helper source unchanged during case')
 result={'case':name,'assertions':ASSERTIONS,'expected_refusals':refusals,'status':'pass',
         'actual_sources_before':before,'actual_sources_after':after,'fixture_helper_versions':helpers,
         'fixture_transform':'dependencies two manifest constants only; source process/import logic unchanged',
         'original_scientific_or_network_execution':False}
 put(root/'RESULT.json',encode(result));print(json.dumps(result))

def campaign():
 ROOT.mkdir(parents=True,exist_ok=False)
 names=['four_workers_before_unpickle','captured_bytes_survive_original_disk_change','preparation_replaces_namespace',
        'blocked_preparation','early_preparation_exit','tampered_captured_original','live_worker_retired_on_scope_failure','unobservable_retirement']
 results=[];records=[]
 for name in names:
  command=[sys.executable,'-I','-S','-B',str(Path(__file__).resolve()),'--case',name]
  child=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
  try:stdout,stderr=child.communicate(timeout=20)
  except subprocess.TimeoutExpired:
   os.killpg(child.pid,signal.SIGKILL)
   try:stdout,stderr=child.communicate(timeout=2)
   except subprocess.TimeoutExpired:raise RuntimeError('control process group retirement unknown')
   record={'case':name,'command':command,'returncode':child.returncode,'timeout':True,'stdout':stdout.decode(),'stderr':stderr.decode()}
   put(ROOT/(name+'.failure.json'),encode(record));raise
  record={'case':name,'command':command,'returncode':child.returncode,'stdout':stdout.decode(),'stderr':stderr.decode()}
  put(ROOT/(name+'.tool.json'),encode(record));records.append(record)
  if child.returncode:raise RuntimeError('new spawn control failed: '+name+'; exact outcome retained')
  results.append(json.loads(stdout))
 result={'status':'pass','cases':len(results),'assertions':sum(r['assertions']for r in results),
         'expected_refusals':sum(r['expected_refusals']for r in results),'results':results,
         'no_original_science_network_or_old_campaign_execution':True,
         'process_scope':'new tiny invented CPython spawn/serialization control processes only'}
 put(ROOT.parent/'SPAWN_CONTROL_RESULTS.json',encode(result));print(json.dumps({k:v for k,v in result.items()if k!='results'}))

if __name__=='__main__':
 if len(sys.argv)==3 and sys.argv[1]=='--case':one_case(sys.argv[2])
 elif len(sys.argv)==1:campaign()
 else:raise SystemExit('unexpected control arguments')
