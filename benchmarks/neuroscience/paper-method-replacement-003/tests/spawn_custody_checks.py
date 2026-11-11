"""Three new current-source startup-custody cases; no old campaign replay."""
from pathlib import Path
import json,os,sys,time,subprocess,signal
P=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(Path(__file__).resolve().parent))
import spawn_binding_checks as fixtures
fixtures.ROOT=Path(os.environ['C4_SOURCE_TEST_ROOT'])/'spawn-custody'

if __name__=='__mp_main__':
 case=os.environ.get('C4_CUSTODY_CASE')
 if case=='failure_frame':
  import types
  sys.modules['npyx']=types.ModuleType('npyx')
 elif case=='deadline_prefix':time.sleep(0.3)

def leaf_errors(exc):
 if isinstance(exc,BaseExceptionGroup):return[y for x in exc.exceptions for y in leaf_errors(x)]
 return[exc]

def run_case(name):
 root,runtime,checkout,fixturepins=fixtures.fixture(name)
 before=[fixtures.pin(fixtures.OUT/'c4_distribution'/n)for n in fixtures.HELPERS]
 sys.path[:0]=[str(root/'ambient'),str(runtime)]
 from c4_distribution import dependencies,spawn_guard
 from c4_distribution.import_guard import activate_originals
 dependencies.prepare_dependencies(root/'prepared',source_root=checkout)
 activate_originals(root/'prepared')
 from npyx.c4.run_deep_classifier import CustomDataset
 os.environ['C4_CUSTODY_CASE']=name
 if name=='deadline_prefix':spawn_guard._STARTUP_SECONDS=0.08
 count=0
 def check(v):
  nonlocal count
  count+=1
  if not v:raise AssertionError((name,count))
 with spawn_guard.source_worker_scope()as owner:
  ctx=spawn_guard.worker_context();parent,child=ctx.Pipe()
  worker=ctx.Process(target=fixtures.receive,args=(CustomDataset('custody-'+name),child,False))
  if name=='complete_startup':
   worker.start();child.close();check(parent.poll(3));parent.recv();worker.join(3)
   custody=worker._popen._c4_startup
   check(custody['sent_bytes']==custody['expected_bytes']and custody['sent_bytes']>0)
   check(custody['unacknowledged']==0 and len(custody['acknowledgements'])==2)
   check(custody['raw_ack_prefix'].endswith(b'\n')and not custody['unparsed_ack_suffix'])
   check(worker.exitcode==0)
  else:
   try:worker.start()
   except BaseException as exc:
    leaves=leaf_errors(exc);values=[x.c4_spawn_startup for x in leaves if hasattr(x,'c4_spawn_startup')]
    check(bool(values));custody=values[0]
    check(0<=custody['sent_bytes']<=custody['expected_bytes'])
    check(custody['unacknowledged']>0)
    if name=='failure_frame':
     check(custody['acknowledgements'][-1]=={'stage':'failed','error_type':'SourceError'})
     check(b'SourceError'in custody['raw_ack_prefix'])
    else:check(not custody['acknowledgements'])
    check(not owner.active and owner.retired_count==1)
   else:raise AssertionError('startup refusal expected')
   finally:child.close()
  parent.close()
 check(not owner.active and owner.retired_count==1)
 after=[fixtures.pin(fixtures.OUT/'c4_distribution'/n)for n in fixtures.HELPERS]
 check(before==after)
 r={'case':name,'status':'pass','assertions':count,'source_before':before,'source_after':after,'fixture_helper_versions':fixturepins,'no_science_network_original_execution':True}
 fixtures.put(root/'RESULT.json',fixtures.encode(r));print(json.dumps(r))

if __name__=='__main__':
 if len(sys.argv)==3 and sys.argv[1]=='--case':run_case(sys.argv[2])
 else:
  fixtures.ROOT.mkdir(parents=True,exist_ok=False);results=[]
  for name in ['complete_startup','failure_frame','deadline_prefix']:
   cmd=[sys.executable,'-I','-S','-B',str(Path(__file__).resolve()),'--case',name]
   proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
   try:out,err=proc.communicate(timeout=20)
   except subprocess.TimeoutExpired:
    os.killpg(proc.pid,signal.SIGKILL);out,err=proc.communicate(timeout=2)
    fixtures.put(fixtures.ROOT/(name+'.timeout.json'),fixtures.encode({'returncode':proc.returncode,'stdout':out.decode(),'stderr':err.decode()}));raise
   record={'request':cmd,'returncode':proc.returncode,'stdout':out.decode(),'stderr':err.decode()}
   fixtures.put(fixtures.ROOT/(name+'.tool.json'),fixtures.encode(record))
   if proc.returncode:raise RuntimeError('new custody control failed '+name)
   results.append(json.loads(out))
  r={'status':'pass','cases':3,'assertions':sum(x['assertions']for x in results),'results':results,'scope':'new exact source startup diagnostics; previous eight cases not replayed'}
  fixtures.put(fixtures.ROOT.parent/'SPAWN_CUSTODY_RESULTS.json',fixtures.encode(r));print(json.dumps({k:v for k,v in r.items()if k!='results'}))
