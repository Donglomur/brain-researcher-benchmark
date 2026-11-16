"""Invented end-to-end bridge/collector controls; Docker transport is simulated.

Only generated Python programs run on the host, under the unchanged bridge.
The real paired request, capture, output admission and scorer are exercised.
"""
import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import resource
import shutil
import sys
import tempfile
import time
import unittest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PAIRED = REPO/'components/purkinje-paired-access'
PRODUCER = Path(os.environ.get('PURKINJE_SOURCE_ROOT',
 str(REPO/'benchmarks/neuroscience/paper-find-rep-013-purkinje-morphology/program-v1')))
spec=importlib.util.spec_from_file_location('pair_exec',HERE/'paired_execution.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
METRICS={'generated_program_executions':0,'control_read_bytes':0,'control_reserved_writes':0,
         'maximum_observed_fixture_bytes':0,'original_body_reads':0,'docker_calls':0}
fixture_path=REPO/'components/purkinje-artifacts/numeric_fixtures.py'
fixture_body=M.captured_source(fixture_path,{'bytes':3601,'sha256':'15004f33e06fcb8fd91c210e10808e24d88bdc07d6a8c9ced1b18e197803c096'})
fixture_modules=M._module_graph(
 {'schema':M.captured_source(PRODUCER/'schema.py',{'bytes':2123,'sha256':M.DONORS['schema'][1]}),'fixture':fixture_body},
 {'schema':PRODUCER/'schema.py','fixture':fixture_path})
GOLD=fixture_modules['fixture'].reference


class InventedPair:
 def __init__(self, mode=None):
  self.root=Path(tempfile.mkdtemp(prefix='invented-exec-',dir=HERE)).resolve()
  self.events=[];self.mode=mode;self.target_calls=0
  self.x=M.PairExecutor(repo=REPO,paired_root=PAIRED,producer_root=PRODUCER,
                       expected_source=M.pin((HERE/'paired_execution.py').read_bytes()))
  self.C=self.x.C;self.p=self.x.paired;self.pm=self.x.paired_module
  self.p.common=copy.deepcopy(self.p.common);self.p.additions=copy.deepcopy(self.p.additions)
  self.p.contract=copy.deepcopy(self.p.contract)
  self.p.provider_root=self.root/'provider'
  for name,row in list(self.p.common['files'].items())+list(self.p.additions['B']['files'].items()):
   raw=(PAIRED/name).read_bytes() if name in ('TASK.md','SCHEMA.json','ATTRIBUTION.md') else (b'P'*622639 if name=='paper.html' else ('invented '+name+'\n').encode())
   dst=self.root/'provider'/name;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(raw)
   row.update(**M.pin(raw))
  self.p.references={'references':{n:{'path':'never-authentic/'+n,**M.pin(b)}for n,b in GOLD.items()}}
  self.p.contract['science']['references']=M.pin(self.pm.encode({n:M.pin(b)for n,b in GOLD.items()}))
  self.p.contract['manifests']={'COMMON.json':M.pin(self.pm.encode(self.p.common)),
    **{c+'.json':M.pin(self.pm.encode(self.p.additions[c]))for c in ('A','B')}}
  self.p.contract_pin=M.pin(self.pm.encode(self.p.contract));self.p._validate_contract()
  original=self.p.a.read
  def guarded(path,*args,**kw):
   path=Path(path).absolute()
   allowed_source={PAIRED/name for name in ('TASK.md','SCHEMA.json','ATTRIBUTION.md')}
   if self.root not in path.parents and path not in allowed_source:raise AssertionError('original body read attempted')
   return original(path,*args,**kw)
  self.p.a.read=guarded
  self.requests={};self.pins={};self.programs={};self.packets={};self.packet_receipts={}
  r=dict(agent_model='invented-only',harness_source=M.pin(b'invented harness'),
         toolset_source=M.pin(b'invented tools'),authoring_seconds=60,authoring_tokens=1000,
         tool_calls=20,program_seconds=60,program_cpu_millicores=1750,program_memory_bytes=3*1024**3)
  # Fixed invented files are intentional; this is a causality/control fixture,
  # not evidence that an arbitrary method is scientifically faithful.
  for c in ('A','B'):
   program=('# invented '+c+'\nfrom pathlib import Path\nimport argparse\np=argparse.ArgumentParser();p.add_argument("--input");p.add_argument("--out");a=p.parse_args()\nfiles='+repr(GOLD)+'\nfor n,b in files.items(): (Path(a.out)/n).write_bytes(b)\n').encode()
   dst=self.root/('candidate-'+c+'.py');dst.write_bytes(program)
   self.programs[c]={'path':str(dst),**M.pin(program)}
   packet=self.root/('packet-'+c);receipt=self.root/('packet-'+c+'.json')
   rp=self.p.materialize(c,packet,receipt,True);self.packets[c]=str(packet)
   self.packet_receipts[c]={'path':str(receipt),**rp}
   request=dict(schema='purkinje-paired-run/v1',task_id=M.TASK,pair_id='a'*64,condition=c,
     context_id=('b' if c=='A' else 'c')*64,execution_selected=True,
     packet=M.pin(self.pm.encode(self.p.packet_identity(c))),packet_receipt=rp,
     program=M.pin(program),resources=r,science=self.p.contract['science'],contract=self.p.contract_pin)
   self.requests[c]=request;self.pins[c]=M.pin(self.pm.encode(request))
  python=Path(sys.executable).resolve()
  self.runtime={'image':M.IMAGE,'docker':str(python),'docker_physical':list(self.C.signature(python.lstat())),
                'daemon_socket':str(self.root/'never-opened.sock'),'daemon_guard':{}}
  self.authorization={'schema':'purkinje-paired-program-owner-authorization/v1','task_id':M.TASK,
   'selected':True,'source':self.x.binding,'requests':self.pins,'runtime':self.runtime,
   'independent_source_review_accepted':True,'exact_runtime_and_mount_profile_qualified':True,
   'external_owner_deadline_and_cleanup_selected':True,'current_capacity_and_storage_admitted':True,
   'unconsumed_attempt_and_prior_costs_admitted':True}
  self.budget=self.C.Budget(time.monotonic()+25,16*1024**2,8*1024**2)
  # Only the Docker/daemon boundary is replaced. bridge execution, collector,
  # bundle decode, paired freeze/admission and target-last grade stay real.
  owner=self.x.owner
  owner.configure_cli=lambda *a:{'invented':True}
  owner.require_configured_cli=lambda *a:True
  owner.registered_clients=lambda: ({1:object()} if self.mode=='live-client' and self.events else {})
  def run(**kw):
   c=kw['root'].parent.name
   self.events.append('start-'+c)
   tree=ast.parse(kw['program'].read_bytes())
   embedded=ast.literal_eval(tree.body[-1].body[0].value.args[0])
   assert M.pin(embedded)==self.requests[c]['program']
   assert {str(p.relative_to(kw['input_dir']))for p in kw['input_dir'].rglob('*') if p.is_file()}==set(self.p.inventory(c))
   assert (kw['input_dir']/'paper.html').stat().st_size==622639
   assert ('HumanvsMousePaperAnalysis.Rmd' in self.p.inventory(c))==(c=='B')
   kw['root'].mkdir()
   if self.mode=='B-failure' and c=='B':
    self.events.append('closed-failure-B')
    return owner.ClosedFailure({'invented':True},'invented failure',owner._FAILED_TOKEN)
   if self.mode=='unclosed':
    return owner.ClosedRun({}, {}, object())
   temporary=kw['root']/'temporary';temporary.mkdir()
   outputs=self.x.modules['bridge'].execute_program(embedded,kw['input_dir'],kw['root']/'output',temporary)
   METRICS['generated_program_executions']+=1
   wire=self.x.modules['bundle'].encode(outputs)
   if self.mode=='corrupt-wire':wire=b'{"schema":"wrong"}'
   entry=self.C.write(kw['root']/'WIRE.bin',wire,self.budget)
   life=self.C.write(kw['root']/'LIFE.json',self.C.encode({'invented':True,'condition':c}),self.budget)
   self.events.append('closed-'+c)
   return owner.ClosedRun(entry,life,owner._CLOSED_TOKEN)
  owner.run_candidate=run
 def run(self):
  return self.x.execute_pair(requests=self.requests,request_pins=self.pins,programs=self.programs,
   packet_roots=self.packets,packet_receipts=self.packet_receipts,runtime=self.runtime,
   owner_authorization=self.authorization,owner_authorization_pin=self.C.pin(self.C.encode(self.authorization)),
   root=self.root/'execution',budget=self.budget,active_deadline=self.budget.deadline-1)
 def authority(self,closed):
  s=closed._state['state'];r=s['requests']['A']
  return dict(schema='purkinje-paired-authoring-review/v1',approved=True,pair_id=r['pair_id'],
   requests=s['request_pins'],receipts=s['receipts'],resources=r['resources'],
   harness_source=r['resources']['harness_source'],independent_fresh_contexts_observed=True,
   exact_effective_mounts_observed=True,network_and_parent_access_denied=True,equal_budget_enforced=True,
   no_cross_arm_history=True,no_target_feedback_before_both_closed=True,both_producers_closed=True,
   revised_science_and_fixed_reference_qualified=True,whole_owner_runtime_qualified=True)
 def grade(self,closed,authority=None):
  authority=self.authority(closed) if authority is None else authority
  def target():
   self.target_calls+=1;self.events.append('private-reference')
   assert self.events[:4]==['start-A','closed-A','start-B','closed-B']
   return GOLD
  return self.x.grade_closed_pair(closed,authority=authority,
   authority_pin=M.pin(self.pm.encode(authority)),reference_reader=target,budget=self.budget)
 def close(self):
  METRICS['control_read_bytes']+=self.budget.reads
  METRICS['control_reserved_writes']+=self.budget.reserved
  METRICS['maximum_observed_fixture_bytes']=max(METRICS['maximum_observed_fixture_bytes'],
   sum(p.stat().st_size for p in self.root.rglob('*') if p.is_file()))
  for p in self.root.rglob('*'):p.chmod(0o700 if p.is_dir() else 0o600)
  self.root.chmod(0o700);shutil.rmtree(self.root)


class Controls(unittest.TestCase):
 def make(self,mode=None):
  f=InventedPair.__new__(InventedPair)
  try:f.__init__(mode)
  except BaseException:
   if hasattr(f,'root'):
    for p in f.root.rglob('*'):p.chmod(0o700 if p.is_dir() else 0o600)
    shutil.rmtree(f.root)
   raise
  self.addCleanup(f.close);return f
 def test_01_real_bridge_capture_pair_and_target_order(self):
  f=self.make();closed=f.run()
  self.assertEqual(f.events,['start-A','closed-A','start-B','closed-B']);self.assertEqual(f.target_calls,0)
  result=f.grade(closed);self.assertEqual(f.target_calls,1)
  self.assertEqual(result['grades']['A'],result['grades']['B'])
  self.assertFalse(result['scientific_qualified'])
  with self.assertRaisesRegex(ValueError,'once'):f.grade(closed)
  with self.assertRaisesRegex(ValueError,'one_use'):f.run()
 def test_02_program_commitment_mismatch_before_producer(self):
  f=self.make();Path(f.programs['A']['path']).write_bytes(b'unrelated')
  with self.assertRaises(ValueError):f.run()
  self.assertEqual(f.events,[])
 def test_03_unclosed_token_prevents_freeze_and_other_arm(self):
  f=self.make('unclosed')
  with self.assertRaisesRegex(ValueError,'closed_candidate'):f.run()
  self.assertEqual(f.events,['start-A']);self.assertEqual(f.target_calls,0)
  self.assertFalse((f.root/'execution/A/sealed-submission').exists())
 def test_04_second_arm_failure_retains_first_no_pair_grade(self):
  f=self.make('B-failure')
  with self.assertRaisesRegex(ValueError,'closed_candidate'):f.run()
  self.assertTrue((f.root/'execution/A/sealed-submission/PAIR_SUBMISSION.json').is_file())
  self.assertFalse((f.root/'execution/BOTH_PROGRAMS_CLOSED.json').exists());self.assertEqual(f.target_calls,0)
 def test_05_corrupt_captured_wire_never_freezes(self):
  f=self.make('corrupt-wire')
  with self.assertRaisesRegex(ValueError,'wire_schema'):f.run()
  self.assertEqual(f.events,['start-A','closed-A']);self.assertEqual(f.target_calls,0)
 def test_06_A_rejects_extra_code_before_any_producer(self):
  f=self.make();p=Path(f.packets['A']);p.chmod(0o700);(p/'HumanvsMousePaperAnalysis.Rmd').write_bytes(b'extra');p.chmod(0o500)
  with self.assertRaisesRegex(ValueError,'namespace'):f.run()
  self.assertEqual(f.events,[])
 def test_07_refuse_9aaf_and_unselected_owner(self):
  for mode in ('image','approval'):
   f=self.make()
   if mode=='image':f.runtime['image']='sha256:9aaf'+'0'*60
   else:f.authorization['selected']=False
   with self.assertRaises(ValueError):f.run()
   self.assertEqual(f.events,[])
 def test_08_swapped_receipt_and_context_budget_before_producer(self):
  f=self.make();f.packet_receipts['A']=f.packet_receipts['B']
  with self.assertRaises(ValueError):f.run()
  self.assertEqual(f.events,[])
  g=self.make();g.requests['B']=copy.deepcopy(g.requests['B']);g.requests['B']['resources']['tool_calls']+=1
  g.pins['B']=M.pin(g.pm.encode(g.requests['B']))
  with self.assertRaisesRegex(ValueError,'matched_pair'):g.run()
  self.assertEqual(g.events,[])
 def test_09_live_client_fails_before_freeze(self):
  f=self.make('live-client')
  with self.assertRaisesRegex(ValueError,'owned_clients_closed'):f.run()
  self.assertFalse((f.root/'execution/A/sealed-submission').exists());self.assertEqual(f.target_calls,0)
 def test_10_post_close_output_change_before_target(self):
  f=self.make();closed=f.run();p=f.root/'execution/B/sealed-submission/summary.json'
  p.chmod(0o600);p.write_bytes(b'{}');p.chmod(0o400)
  with self.assertRaises(ValueError):f.grade(closed)
  self.assertEqual(f.target_calls,0)
 def test_11_missing_authority_and_forged_pair_before_target(self):
  f=self.make();closed=f.run();authority=f.authority(closed);authority['whole_owner_runtime_qualified']=False
  with self.assertRaisesRegex(ValueError,'authority'):f.grade(closed,authority)
  self.assertEqual(f.target_calls,0)
  with self.assertRaises(ValueError):
   f.x.grade_closed_pair(M.ClosedPair(f.x,{},object()),authority={},authority_pin={},
    reference_reader=lambda:self.fail('private reader called'),budget=f.budget)
 def test_12_source_pin_failure_and_no_global_module_collision(self):
  marker=object();previous=sys.modules.get('common');sys.modules['common']=marker
  try:
   f=self.make();self.assertIs(sys.modules['common'],marker)
   with self.assertRaisesRegex(ValueError,'source_identity'):
    M.PairExecutor(repo=REPO,paired_root=PAIRED,producer_root=PRODUCER,
     expected_source={'bytes':(HERE/'paired_execution.py').stat().st_size,'sha256':'0'*64})
  finally:
   if previous is None:sys.modules.pop('common',None)
   else:sys.modules['common']=previous

 def test_13_public_dependency_and_contract_relocation(self):
  x=M.PairExecutor(repo=REPO,paired_root=PAIRED,producer_root=PRODUCER,
   expected_source=M.pin((HERE/'paired_execution.py').read_bytes()))
  self.assertEqual(x.paired.contract_pin,M.CONTRACT)
  self.assertIsNone(x.paired.provider_root)
  self.assertEqual(x.paired.source_path(x.paired.common['files']['TASK.md']),PAIRED/'TASK.md')
  self.assertEqual(len(x.paired.inventory('A')),16)
  self.assertEqual(len(x.paired.inventory('B')),18)
  self.assertEqual(x.paired.inventory('A')['paper.html']['bytes'],622639)
  self.assertEqual(x.owner.IMAGE,M.IMAGE)
  source=json.loads((HERE/'SOURCE.json').read_text())
  self.assertEqual(source['source_files']['paired_execution.py'],M.pin((HERE/'paired_execution.py').read_bytes()))
  self.assertEqual(source['source_files']['test_paired_execution.py'],M.pin((HERE/'test_paired_execution.py').read_bytes()))
  for row in source['reused_dependencies']:
   self.assertEqual(M.pin((REPO/row['path']).read_bytes()),{k:row[k]for k in ('bytes','sha256')})
  self.assertFalse(json.loads((HERE/'OWNER_AUTHORIZATION.template.json').read_text())['selected'])


if __name__=='__main__':
 started=time.monotonic();cpu=time.process_time()
 relocation_only='--relocation-only' in sys.argv
 names=['test_01_real_bridge_capture_pair_and_target_order','test_12_source_pin_failure_and_no_global_module_collision','test_13_public_dependency_and_contract_relocation'] if relocation_only else unittest.defaultTestLoader.getTestCaseNames(Controls)
 result=unittest.TextTestRunner(verbosity=2,failfast=True).run(unittest.TestSuite(Controls(name)for name in names))
 report={'selection':'relocation-only' if relocation_only else 'all-generated','methods':result.testsRun,'passed':result.wasSuccessful(),'failures':len(result.failures),
  'errors':len(result.errors),'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-started,
  'max_RSS_native':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
  'RSS_unit':'bytes' if sys.platform=='darwin' else 'KiB',**METRICS,
  'scope':'Invented 10-cell/13-component/15-branch five-product integration; not authentic 21116-branch qualification.',
  'transport':'Only generated host Python via unchanged bridge; Docker/daemon boundary simulated.',
  'limits':'Observed fixture census is not an instrumented transient peak; source/interpreter/OS I/O not fully metered.'}
 (HERE/'CONTROL_RESULTS.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report));raise SystemExit(not result.wasSuccessful())
