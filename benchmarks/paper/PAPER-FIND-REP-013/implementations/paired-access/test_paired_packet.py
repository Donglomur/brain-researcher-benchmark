"""Generated exact inventories/full-wire outputs; no authentic empirical or gold I/O."""
import copy
import importlib.util
import json
from pathlib import Path
import resource
import shutil
import sys
import tempfile
import time
import unittest

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[4]
def module(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
M=module(HERE/'paired_packet.py','paired')

class PairedControls(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.p=M.Paired(REPO,HERE/'CONTRACT.json',M.pin((HERE/'CONTRACT.json').read_bytes()))
  cls.original_contract=copy.deepcopy(cls.p.contract)
  cls.root=Path(tempfile.mkdtemp(prefix='generated-paired-',dir=HERE)).resolve()
  cls.p.provider_root=cls.root/'provider'
  cls.p.common=copy.deepcopy(cls.p.common);cls.p.additions=copy.deepcopy(cls.p.additions);cls.p.contract=copy.deepcopy(cls.p.contract)
  for name,row in list(cls.p.common['files'].items())+list(cls.p.additions['B']['files'].items()):
   body=(HERE/name).read_bytes() if name in ('TASK.md','SCHEMA.json','ATTRIBUTION.md') else (b'P'*622639 if name=='paper.html' else ('invented '+name+'\n').encode())
   path=cls.root/'provider'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body)
   row.update(**M.pin(body))
  old=sys.modules.get('schema');sys.modules['schema']=cls.p.schema
  try:cls.fixture=module(REPO/'benchmarks/paper/PAPER-FIND-REP-013/implementations/artifacts/numeric_fixtures.py','paired_generated_fixture')
  finally:
   if old is None:sys.modules.pop('schema',None)
   else:sys.modules['schema']=old
  cls.gold=cls.fixture.files(cls.fixture.rows)
  cls.p.references={'references':{n:{'path':'never-authentic/'+n,**M.pin(b)} for n,b in cls.gold.items()}}
  cls.p.contract['science']['references']=M.pin(M.encode({n:M.pin(b) for n,b in cls.gold.items()}))
  cls.p.contract['manifests']={'COMMON.json':M.pin(M.encode(cls.p.common)),**{c+'.json':M.pin(M.encode(cls.p.additions[c])) for c in M.CONDITIONS}}
  cls.p.contract_pin=M.pin(M.encode(cls.p.contract));cls.p._validate_contract()
  cls.read_bytes=0;original=cls.p.a.read
  def counted(*args,**kw):
   body=original(*args,**kw);cls.read_bytes+=len(body)
   if cls.read_bytes>20*1024**2:raise RuntimeError('generated selected read allowance')
   return body
  cls.p.a.read=counted
  cls.packet_receipts={};cls.requests={};cls.request_pins={};cls.attempts={};cls.receipts={}
  program=b'# generated program commitment; never executed\n';cls.program=cls.root/'program.py';cls.program.write_bytes(program)
  cls.submission=cls.root/'outputs';cls.submission.mkdir()
  for n,b in cls.gold.items():(cls.submission/n).write_bytes(b)
  resources=dict(agent_model='invented-test-agent',harness_source=M.pin(b'invented harness'),toolset_source=M.pin(b'invented tools'),authoring_seconds=60,authoring_tokens=1000,tool_calls=20,program_seconds=60,program_cpu_millicores=1750,program_memory_bytes=3*1024**3)
  for c in M.CONDITIONS:
   packet=cls.root/('packet-'+c);receipt=cls.root/('packet-'+c+'.json')
   pp=cls.p.materialize(c,packet,receipt,True);cls.packet_receipts[c]=pp
   r=dict(schema='purkinje-paired-run/v1',task_id=M.TASK,pair_id='a'*64,condition=c,context_id=('b' if c=='A' else 'c')*64,execution_selected=True,
          packet=M.pin(M.encode(cls.p.packet_identity(c))),packet_receipt=pp,program=M.pin(program),resources=resources,science=cls.p.contract['science'],contract=cls.p.contract_pin)
   cls.requests[c]=r;cls.request_pins[c]=M.pin(M.encode(r));cls.attempts[c]=cls.root/('attempt-'+c)
   cls.receipts[c]=cls.p.freeze(r,cls.request_pins[c],receipt,pp,cls.program,cls.submission,cls.attempts[c],True)
  cls.peak_fixture_bytes=sum(p.stat().st_size for p in cls.root.rglob('*') if p.is_file())

 @classmethod
 def tearDownClass(cls):
  for p in cls.root.rglob('*'):
   p.chmod(0o700 if p.is_dir() else 0o600)
  cls.root.chmod(0o700);shutil.rmtree(cls.root)

 def authority(self,requests=None,pins=None,receipts=None):
  requests=self.requests if requests is None else requests;pins=self.request_pins if pins is None else pins;receipts=self.receipts if receipts is None else receipts
  r=requests['A']
  return dict(schema='purkinje-paired-authoring-review/v1',approved=True,pair_id=r['pair_id'],requests=pins,receipts=receipts,resources=r['resources'],harness_source=r['resources']['harness_source'],
   independent_fresh_contexts_observed=True,exact_effective_mounts_observed=True,network_and_parent_access_denied=True,equal_budget_enforced=True,no_cross_arm_history=True,
   no_target_feedback_before_both_closed=True,both_producers_closed=True,revised_science_and_fixed_reference_qualified=True,whole_owner_runtime_qualified=True)

 def compare(self,requests=None,pins=None,attempts=None,receipts=None,authority=None,gold=None):
  requests=self.requests if requests is None else requests;pins=self.request_pins if pins is None else pins;attempts=self.attempts if attempts is None else attempts;receipts=self.receipts if receipts is None else receipts
  authority=self.authority(requests,pins,receipts) if authority is None else authority
  self.target_calls=0
  def target():self.target_calls+=1;return self.gold if gold is None else gold
  return self.p.compare_closed_pair(requests,pins,attempts,receipts,authority,M.pin(M.encode(authority)),target)

 def test_09_portable_roots_and_missing_provider(self):
  p=M.Paired(REPO,HERE/'CONTRACT.json',M.pin((HERE/'CONTRACT.json').read_bytes()))
  self.assertIsNone(p.provider_root)
  with self.assertRaisesRegex(ValueError,'provider root'):
   p.materialize('A',self.root/'absent-provider',self.root/'absent-provider.json',True)
  self.assertFalse((self.root/'absent-provider').exists())
  self.assertEqual(p.source_path(p.common['files']['TASK.md']),HERE/'TASK.md')
  p.provider_root=self.root/'provider'
  self.assertEqual(p.source_path(p.common['files']['cells.json']),self.root/'provider/cells.json')
  p.provider_root=self.root/'new-provider'
  with self.assertRaisesRegex(ValueError,'overlap'):
   p.materialize('A',self.root/'new-provider',self.root/'outside-receipt.json',True)

 def test_10_descriptor_namespaces_and_provider_corruption(self):
  p=copy.copy(self.p);p.common=copy.deepcopy(self.p.common)
  for wrong in ('component/cells.json','provider/../cells.json','/private/cells.json'):
   p.common['files']['cells.json']['source']=wrong
   with self.assertRaisesRegex(ValueError,'portable asset'):p._validate_contract()
  p.common=copy.deepcopy(self.p.common)
  provider=self.root/'provider/cells.json';before=provider.read_bytes();provider.write_bytes(b'changed provider')
  try:
   with self.assertRaises(ValueError):p.materialize('A',self.root/'corrupt-packet',self.root/'corrupt-receipt.json',True)
   self.assertFalse((self.root/'corrupt-receipt.json').exists())
  finally:provider.write_bytes(before)
  self.assertTrue((self.root/'corrupt-packet').exists())  # retained failed copy

 def test_11_public_templates_and_exact_source(self):
  p=M.Paired(REPO,HERE/'CONTRACT.json',M.pin((HERE/'CONTRACT.json').read_bytes()))
  self.assertEqual(p.contract['artifact_source'],M.ARTIFACT_SOURCE)
  self.assertEqual(len(p.inventory('A')),16);self.assertEqual(len(p.inventory('B')),18)
  self.assertEqual(sum(r['bytes'] for r in p.inventory('A').values()),12610503)
  self.assertEqual(sum(r['bytes'] for r in p.inventory('B').values()),12845757)
  for arm in M.CONDITIONS:
   r=json.loads((HERE/('RUN_REQUEST_'+arm+'.template.json')).read_bytes())
   self.assertFalse(r['execution_selected']);self.assertEqual(r['contract'],p.contract_pin)
   with self.assertRaises(ValueError):p.validate_request(r)
  self.assertFalse(json.loads((HERE/'HARNESS_REVIEW.template.json').read_bytes())['approved'])

 def test_01_exact_assets_and_article_extent(self):
  self.assertEqual(len(self.p.common['empirical_names']),12)
  a=self.p.inventory('A');b=self.p.inventory('B')
  self.assertEqual(len(a),16);self.assertEqual(len(b),18)
  self.assertEqual(set(b)-set(a),M.CODE_NAMES)
  self.assertTrue(all(a[k]==b[k] for k in a))
  self.assertEqual(a['paper.html']['bytes'],622639);self.assertGreater(a['paper.html']['bytes'],600000)
  for c in M.CONDITIONS:self.assertEqual(self.p.verify_packet(self.root/('packet-'+c),c),self.requests[c]['packet'])
  self.assertFalse(self.original_contract['authoring_executor_implemented'])

 def test_02_materialization_selection_freshness_and_wrong_arm(self):
  with self.assertRaisesRegex(ValueError,'selection'):self.p.materialize('A',self.root/'unselected',self.root/'unselected.json',False)
  self.assertFalse((self.root/'unselected').exists())
  with self.assertRaisesRegex(ValueError,'fresh'):self.p.materialize('A',self.root/'packet-A',self.root/'packet-A.json',True)
  with self.assertRaisesRegex(ValueError,'known condition'):self.p.inventory('C')
  with self.assertRaisesRegex(ValueError,'condition packet'):self.p.packet_receipt(self.root/'packet-B.json',self.packet_receipts['B'],'A')

 def test_03_actual_packet_mutation_missing_extra(self):
  root=self.root/'packet-A';p=root/'cells.json';body=p.read_bytes();p.chmod(0o600);p.write_bytes(b'wrong');p.chmod(0o400)
  try:
   with self.assertRaises(ValueError):self.p.verify_packet(root,'A')
  finally:p.chmod(0o600);p.write_bytes(body);p.chmod(0o400)
  root.chmod(0o700);extra=root/'HumanvsMousePaperAnalysis.Rmd';extra.write_bytes(b'extra code');root.chmod(0o500)
  try:
   with self.assertRaisesRegex(ValueError,'namespace'):self.p.verify_packet(root,'A')
  finally:root.chmod(0o700);extra.unlink();root.chmod(0o500)
  root.chmod(0o700);p.rename(root/'renamed');root.chmod(0o500)
  try:
   with self.assertRaisesRegex(ValueError,'namespace'):self.p.verify_packet(root,'A')
  finally:root.chmod(0o700);(root/'renamed').rename(p);root.chmod(0o500)

 def test_04_request_identity_and_resource_aliases(self):
  for key in ('packet','contract','program'):
   r=copy.deepcopy(self.requests['A']);r[key]['sha256']='f'*64
   if key=='program':
    with self.assertRaises(ValueError):self.p.freeze(r,M.pin(M.encode(r)),self.root/'packet-A.json',self.packet_receipts['A'],self.program,self.submission,self.root/'wrong-program',True)
   else:
    with self.assertRaises(ValueError):self.p.validate_request(r)
  for key in self.requests['A']['science']:
   r=copy.deepcopy(self.requests['A']);r['science'][key]['sha256']='f'*64
   with self.assertRaises(ValueError):self.p.validate_request(r)
  for value in ('unknown','B'):
   r=copy.deepcopy(self.requests['A']);r['condition']=value
   with self.assertRaises(ValueError):self.p.validate_request(r,'A')
  r=copy.deepcopy(self.requests['A']);r['resources']['tool_calls']=True
  with self.assertRaises(ValueError):self.p.validate_request(r)

 def test_05_commitment_stop_invalid_output_before_capture(self):
  r=self.requests['A']
  with self.assertRaisesRegex(ValueError,'stopped'):self.p.freeze(r,self.request_pins['A'],self.root/'packet-A.json',self.packet_receipts['A'],self.program,self.submission,self.root/'unstopped',False)
  self.assertFalse((self.root/'unstopped').exists())
  invalid=self.root/'invalid-output';invalid.mkdir()
  for n,b in self.gold.items():(invalid/n).write_bytes(b if n!='summary.json' else b'{"x":NaN}')
  with self.assertRaises(ValueError):self.p.freeze(r,self.request_pins['A'],self.root/'packet-A.json',self.packet_receipts['A'],self.program,invalid,self.root/'invalid-attempt',True)
  self.assertFalse((self.root/'invalid-attempt').exists())

 def test_06_identical_full_wire_same_complete_score(self):
  result=self.compare();self.assertEqual(self.target_calls,1)
  self.assertEqual(result['reference_bundle_reader_calls'],1)
  self.assertEqual(result['grades']['A'],result['grades']['B'])
  expected=self.p.scorer.grade(self.gold,lambda:self.gold)
  self.assertEqual(result['grades']['A'],expected)
  self.assertEqual(expected['comparison']['metrics']['tables']['branches.csv']['fields']['length_um']['defined_cells'],10)
  self.assertEqual(expected['comparison']['metrics']['tables']['branches.csv']['fields']['length_um']['defined_rows'],15)
  self.assertFalse(result['code_access_effect_established']);self.assertFalse(result['authoring_isolation_implemented_here'])

 def test_07_cross_arm_receipt_feedback_and_budget_before_target(self):
  for mode in ('swap','request_pin','context','budget','no_authority','early_feedback'):
   req=copy.deepcopy(self.requests);pins=copy.deepcopy(self.request_pins);receipts=copy.deepcopy(self.receipts)
   if mode=='swap':receipts={'A':self.receipts['B'],'B':self.receipts['A']}
   if mode=='request_pin':pins['A']['sha256']='f'*64
   if mode=='context':req['B']['context_id']=req['A']['context_id']
   if mode=='budget':req['B']['resources']['tool_calls']+=1
   auth=self.authority(req,pins,receipts)
   if mode=='no_authority':auth['approved']=False
   if mode=='early_feedback':auth['no_target_feedback_before_both_closed']=False
   with self.assertRaises(ValueError):self.compare(req,pins,receipts=receipts,authority=auth)
   self.assertEqual(self.target_calls,0)

 def test_08_missing_topology_and_fixed_target_identity(self):
  rows=copy.deepcopy(self.fixture.rows);rows['branches.csv'].pop();incomplete=self.root/'incomplete';incomplete.mkdir()
  for n,b in self.fixture.files(rows).items():(incomplete/n).write_bytes(b)
  attempt=self.root/'incomplete-attempt';receipt=self.p.freeze(self.requests['A'],self.request_pins['A'],self.root/'packet-A.json',self.packet_receipts['A'],self.program,incomplete,attempt,True)
  attempts={**self.attempts,'A':attempt};receipts={**self.receipts,'A':receipt}
  result=self.compare(attempts=attempts,receipts=receipts)
  self.assertEqual(result['grades']['A']['status'],'incomplete_numerical_coverage');self.assertIsNone(result['grades']['A']['comparison']['metrics'])
  self.assertEqual(self.target_calls,1)
  wrong={**self.gold,'summary.json':b'{}'}
  with self.assertRaisesRegex(ValueError,'fixed common reference'):self.compare(gold=wrong)
  self.assertEqual(self.target_calls,1)

if __name__=='__main__':
 start=time.monotonic();cpu=time.process_time()
 names=['test_09_portable_roots_and_missing_provider','test_10_descriptor_namespaces_and_provider_corruption','test_11_public_templates_and_exact_source','test_06_identical_full_wire_same_complete_score','test_07_cross_arm_receipt_feedback_and_budget_before_target']
 result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(PairedControls(n) for n in names))
 report=dict(methods=result.testsRun,passed=result.wasSuccessful(),failures=len(result.failures),errors=len(result.errors),generated_only=True,
  selected_methods=names,authentic_empirical_reads=0,authentic_gold_reads=0,source_and_generated_reads=PairedControls.read_bytes,
  generated_scope='Five-product synthetic10-cell/13-component wire;15 invented branches, not authentic21116-branch qualification.',
  generated_fixture_bytes_before_variants=PairedControls.peak_fixture_bytes,CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-start,
  max_RSS_native=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,RSS_unit='bytes' if sys.platform=='darwin' else 'KiB')
 print(json.dumps(report,sort_keys=True));raise SystemExit(not result.wasSuccessful())
