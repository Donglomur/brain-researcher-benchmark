"""Maintained ordinary-admission controls: fake lifecycle and tiny generated files only."""
import ast,builtins,copy,hashlib,importlib.util,json,os,signal,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace,ModuleType
from unittest.mock import patch
BASE=Path(__file__).resolve().parents[1];SOURCE=BASE/'source'
sys.dont_write_bytecode=True
s=importlib.util.spec_from_file_location('ordinary_runner',SOURCE/'run_programme.py');runner=importlib.util.module_from_spec(s);s.loader.exec_module(runner);ad=runner.admission
C=SOURCE/'authoring/rtt-neural-forecast-v1/causal-runtime-v1'

def body(v):return ad.canonical(v)
def descriptor(p):return {'path':str(p),**ad.pin(p.read_bytes())}
def fixture(folder,mode='ordinary'):
 root=Path(folder);(root/'authoring').mkdir();(root/'program.py').write_bytes(b'# generated programme\n');(root/'method.json').write_bytes(body({'schema_version':1,'method_id':'generated','method_description':'generated test','training_policy':'unknown test','limitations':'not executed'}));(root/'case.json').write_bytes(b'{}\n')
 chosen={'task_id':'NEURAL-024','mode':mode,'programme':descriptor(root/'program.py'),'method':descriptor(root/'method.json'),'case_manifest':descriptor(root/'case.json'),'source_manifest_pin':ad.pin(b'{}\n'),'run':str(root/'artifacts-build/test-001'),'docker_host':'unix:///generated-only.sock','host_runtime':{'executable':'/generated/python','base_executable':'/generated/python','real_executable':'/generated/python','version':[3,11,6],'no_site':0,'prefix_matches_base':True,'has_pythonexecutable_override':False},'runtime_dependencies':[descriptor(root/'program.py')],'limits':copy.deepcopy(ad.LIMITS)}
 review={'schema':'neural024-programme-operation-review/v1','decision':'accepted_for_one_operator_released_attempt','spec_sha256':ad.pin(body(chosen))['sha256']};(root/'review.json').write_bytes(body(review))
 admission={'schema':'neural024-programme-admission/v1','execution_authorized':True,'spec':chosen,'independent_review':descriptor(root/'review.json')};(root/'admission.json').write_bytes(body(admission));return chosen,admission
class AdmissionChecks(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.blocks=[patch.object(subprocess,'run',side_effect=AssertionError('real CLI forbidden')),patch.object(subprocess,'Popen',side_effect=AssertionError('real launch forbidden'))]
  for p in cls.blocks:p.start()
 @classmethod
 def tearDownClass(cls):
  for p in reversed(cls.blocks):p.stop()
 def test_original_method_schema_and_utf8(self):
  for bad in({'schema_version':True,'method_id':'x','method_description':'x','training_policy':'x','limitations':'x'},{'schema_version':1,'method_id':'','method_description':'x','training_policy':'x','limitations':'x'}):
   with self.assertRaises(ValueError):ad.method(body(bad))
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent,prefix='generated-')as d:
   chosen,_=fixture(d);(Path(d)/'program.py').write_bytes(b'\xff');chosen['programme']=descriptor(Path(d)/'program.py')
   with self.assertRaises(UnicodeDecodeError):ad.selected_programme(chosen)
 def test_mode_and_selected_bytes_bound_by_operation_review(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent,prefix='generated-')as d:
   chosen,admission=fixture(d)
   with patch.object(ad,'ROOT',Path(d)):
    self.assertEqual(ad.read_admission(Path(d)/'admission.json',ad.pin(body(admission))['sha256']),chosen)
    for mutate in(lambda v:v['spec'].update(mode='calibration_rate'),lambda v:v['spec']['programme'].update(sha256='0'*64),lambda v:v.update(execution_authorized=False)):
     bad=copy.deepcopy(admission);mutate(bad);p=Path(d)/'bad.json';p.write_bytes(body(bad))
     with self.assertRaises(ValueError):ad.read_admission(p,ad.pin(body(bad))['sha256'])
 def test_fixed_mode_refuses_changed_programme_or_method(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent,prefix='generated-')as d:
   chosen,_=fixture(d,'calibration_rate')
   with self.assertRaises(ValueError):ad.selected_programme(chosen)
 def test_source_closure_rejects_extra_or_changed_dependency(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent,prefix='generated-')as d:
   chosen,_=fixture(d);root=Path(d);p=root/'run_programme.py';p.write_bytes(b'# runner\n');p.chmod(0o444)
   manifest={'schema':'neural024-ordinary-source/v1','files':{'run_programme.py':ad.pin(p.read_bytes())}};(root/'SOURCE_MANIFEST.json').write_bytes(body(manifest));chosen['source_manifest_pin']=ad.pin(body(manifest))
   with patch.object(ad,'ROOT',root):
    ad.source_closure(chosen)
    q=root/'authoring/extra.py';q.write_bytes(b'# extra\n')
    with self.assertRaises(ValueError):ad.source_closure(chosen)
 def test_source_or_method_link_refused_before_execution(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent,prefix='generated-')as d:
   chosen,_=fixture(d);p=Path(d)/'linked.py';p.symlink_to(Path(d)/'program.py');chosen['programme']['path']=str(p)
   with self.assertRaises(ValueError):ad.selected_programme(chosen)
 def test_owned_activation_uses_same_controller_gate_directory(self):
  tree=ast.parse((C/'prepared_control.py').read_bytes());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='require_owned_activation');seen=[];run=Path('/generated/artifacts-build/a');here=Path('/generated/authoring/rtt-neural-forecast-v1/causal-runtime-v1');args=SimpleNamespace(deadline=100.0)
  saved={'child_argv':[sys.executable,str(here/'prepared_control.py'),'--run',str(run),'--deadline','100.0'],'pid':42,'pgid':42,'seconds':720,'pid_recorded_before_activation':True,'token':'a'*32}
  owner=SimpleNamespace(expected=lambda p:(seen.append(p)or(saved,[])),read=lambda p:(seen.append(p)or{'token':'a'*32,'activate':True}))
  namespace={'RUN':run,'HERE':here,'owner':owner,'need':ad.need,'sys':sys,'os':SimpleNamespace(getppid=lambda:42,getpgrp=lambda:42)}
  exec(compile(ast.Module(body=[node],type_ignores=[]),'<exact activation>','exec'),namespace);namespace['require_owned_activation'](args)
  self.assertEqual(seen,[run/'controller',run/'controller/process_gate.json'])
 def outer(self,mode='ordinary',gain=-0.25,parity=False,launch_error=False,child_changes=None):
  events=[]
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent,prefix='generated-')as d:
   root=Path(d);chosen,selected=fixture(d,mode);run=Path(chosen['run']);here=root/'authoring/rtt-neural-forecast-v1/causal-runtime-v1';here.mkdir(parents=True)
   sourcepin={'bytes':1,'sha256':'1'*64};closure={'files':{str((here/'prepared_control.py').relative_to(root)):sourcepin}}
   class Budget:
    def __init__(self,*a):pass
    def write(self,p,b,**kw):
     p=Path(p)
     with p.open('xb')as f:f.write(b)
     p.chmod(kw.get('mode',0o444))
   def save(p,v,budget,cap=131072):
    raw=body(v);self.assertLessEqual(len(raw),cap);budget.write(p,raw,mode=0o444);return {'path':str(p.relative_to(root)),**ad.pin(raw)}
   fake_common=ModuleType('common');fake_common.HostBudget=Budget;fake_common.Engine=lambda *a:None;fake_common.sync=lambda p:None;fake_common.save=save
   fake_recovery=ModuleType('rtt_recovery');fake_recovery.recover_all=lambda *a:(events.append('recover')or[{'absence_verified':True},{'absence_verified':True}])
   fake_binding=ModuleType('prepared_binding');fake_binding.packet=lambda:(events.append('custody_metadata')or{})
   def launch(argv,folder,seconds,desc):
    events.append('launch');self.assertEqual(folder,run/'controller');self.assertTrue((run/'source_commit.json').exists())
    committed=json.loads((run/'source_commit.json').read_bytes());self.assertTrue(committed['before_candidate_activation']);self.assertTrue(committed['historical_preparation_preceded_commitment'])
    self.assertEqual((run/'program.py').read_bytes(),b'# generated programme\n');self.assertEqual(os.environ['NEURAL024_DOCKER_HOST'],'unix:///generated-only.sock')
    if launch_error:raise OSError('after durable activation')
    grade=run/'grade/output';grade.mkdir(parents=True)
    score={'status':'scored','complete_scored_panel':True,'support':{'cells':2120640,'rows':22090,'channels':96,'reference_arms_verified':6},'bits_per_spike_vs_calibration_rate':gain,'comparisons':{'calibration_rate':{'log_likelihood_gain':gain*100,'bits_per_spike_gain':gain,'mean_nll_reduction':gain/100}}}
    (grade/'score.json').write_bytes(body(score));(grade/'grade_receipt.json').write_bytes(body({'generated':True}))
    child={'status':'scored','protocol_complete':True,'candidate_chronology_verified':True,'committed_prediction_count':22100,'private_grader_dispatched':True,'new_reference_fits':0,'model_api_calls_by_controller':0,'prepared_inputs_recomputed':False,'operation_mode':mode,'control_checks':None,'candidate_fit_count':None,'candidate_authorship':'unknown','candidate_training_policy_verified':False,'ordinary_scored_without_accuracy_floor':True,'score':ad.pin(body(score)),'grade_receipt':ad.pin(body({'generated':True}))}
    if mode=='calibration_rate':child.update(candidate_fit_count=0,candidate_authorship='disclosed_fixed_control',candidate_training_policy_verified=True,ordinary_scored_without_accuracy_floor=False,control_checks={'passed':parity,'label':'calibration_rate','calibration_rate_control':{'exact_parity':parity,'zero_primary_gain':gain==0}})
    child.update(child_changes or{})
    (run/'result.json').write_bytes(body(child));return object()
   owner=SimpleNamespace(launch=launch,stop=lambda *a,**k:(events.append('stop')or{'absence_verified':True}));fake_common.owner=owner
   real_import=builtins.__import__
   def imports(name,*a,**kw):
    if name in('common','rtt_recovery','prepared_binding'):
     self.assertEqual(os.environ['NEURAL024_OPERATION_ADMISSION'],str(root/'admission.json'));self.assertEqual(os.environ['NEURAL024_DOCKER_HOST'],'unix:///generated-only.sock');events.append('import:'+name)
    return real_import(name,*a,**kw)
   chosen_read=lambda *a:(events.append('admission')or chosen)
   def selected_programme(v):events.append('programme_validation');return {'program.py':b'# generated programme\n','method.json':(root/'method.json').read_bytes()}
   patches=[patch.object(runner,'ROOT',root),patch.object(runner,'HERE',here),patch.object(ad,'ROOT',root),patch.object(ad,'read_admission',chosen_read),patch.object(ad,'source_closure',lambda x:(events.append('source_closure')or closure)),patch.object(ad,'runtime_identity',lambda x:events.append('runtime_identity')),patch.object(ad,'selected_programme',selected_programme),patch.object(runner,'await_child',lambda *a:{'returncode':0}),patch.dict(sys.modules,{'common':fake_common,'rtt_recovery':fake_recovery,'prepared_binding':fake_binding}),patch('builtins.__import__',side_effect=imports),patch.object(signal,'signal',lambda *a:None),patch.object(signal,'setitimer',lambda *a:None),patch.object(signal,'getitimer',lambda *a:(0.,0.)),patch.object(sys,'argv',['run_programme.py','--admission',str(root/'admission.json'),'--admission-sha256',ad.pin(body(selected))['sha256']]),patch.dict(os.environ,{'DOCKER_HOST':'tcp://must-be-removed','DOCKER_CONTEXT':'foreign','NEURAL024_OPERATION_ADMISSION':'wrong'})]
   for p in patches:p.start()
   try:code=runner.main();result=json.loads((run/'operation_result.json').read_bytes())
   finally:
    for p in reversed(patches):p.stop()
   return code,result,events
 def test_actual_outer_negative_ordinary_score_and_admission_order(self):
  code,r,e=self.outer();self.assertEqual(code,0);self.assertEqual(r['score']['primary_bits_per_spike_gain'],-0.25);self.assertIsNone(r['candidate_fit_count']);self.assertEqual(r['candidate_authorship'],'unknown')
  self.assertLess(e.index('source_closure'),e.index('import:common'));self.assertLess(e.index('programme_validation'),e.index('custody_metadata'));self.assertLess(e.index('stop'),e.index('recover'))
 def test_actual_outer_fixed_control_nonparity_refused(self):
  code,r,e=self.outer(mode='calibration_rate',gain=0,parity=False);self.assertEqual(code,2);self.assertEqual(r['status'],'failed_or_incomplete')
 def test_actual_outer_fixed_control_exact_parity_accepted(self):
  code,r,e=self.outer(mode='calibration_rate',gain=0,parity=True);self.assertEqual(code,0);self.assertEqual(r['status'],'fixed_calibration_control_verified_pending_outer_exit')
 def test_actual_outer_launch_error_stops_then_recovers(self):
  code,r,e=self.outer(launch_error=True);self.assertEqual(code,2);self.assertEqual(e[-3:],['launch','stop','recover']);self.assertEqual(r['outcome']['native_error'],'OSError')
 def test_prepared_control_ordinary_has_no_fixed_accuracy_floor(self):
  tree=ast.parse((C/'prepared_control.py').read_bytes());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='control_check');ns={'need':ad.need};exec(compile(ast.Module(body=[node],type_ignores=[]),'<actual control check>','exec'),ns)
  self.assertIsNone(ns['control_check']('ordinary',{'status':'scored'},None))
 def test_actual_outer_incomplete_or_misrepresented_ordinary_refused(self):
  for change in({'committed_prediction_count':22099},{'candidate_chronology_verified':False},{'candidate_fit_count':0}):
   with self.subTest(change=change):
    code,result,events=self.outer(child_changes=change)
    self.assertEqual(code,2);self.assertEqual(result['status'],'failed_or_incomplete')
    self.assertEqual(events[-2:],['stop','recover'])
 def test_changed_source_bytes_refused(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent,prefix='generated-')as d:
   chosen,_=fixture(d);root=Path(d);p=root/'run_programme.py';p.write_bytes(b'# original\n');p.chmod(0o444)
   manifest={'schema':'neural024-ordinary-source/v1','files':{'run_programme.py':ad.pin(p.read_bytes())}};(root/'SOURCE_MANIFEST.json').write_bytes(body(manifest));chosen['source_manifest_pin']=ad.pin(body(manifest))
   p.chmod(0o644);p.write_bytes(b'# changed!\n');p.chmod(0o444)
   with patch.object(ad,'ROOT',root):
    with self.assertRaises(ValueError):ad.source_closure(chosen)
 def portable_packet(self,root,custody,corrupt_hash=False):
  path=root/'custody.json';path.write_bytes(body(custody));chosen={'run':str(SOURCE/'artifacts-build/generated'),'case_manifest':descriptor(path)}
  if corrupt_hash:chosen['case_manifest']['sha256']='0'*64
  identity=json.loads((C/'CASE_IDENTITY.json').read_bytes())
  tree=ast.parse((C/'prepared_binding.py').read_bytes());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='packet')
  ns={'selected':lambda:chosen,'strict':ad.strict,'meta':ad.meta,'regular':ad.meta,'HERE':C,'need':ad.need,'Path':Path,'contract':SimpleNamespace(PUBLIC_PINS=identity['public'])}
  exec(compile(ast.Module(body=[node],type_ignores=[]),'<actual portable packet>','exec'),ns);return ns['packet']()
 def test_relocated_custody_retains_exact_identity_and_role_boundaries(self):
  custody={'schema':'neural024-prepared-custody/v1','public_root':'/relocated/banks','private_root':'/relocated/case','metadata_paths':{'bank_qualification':'/relocated/meta/bank.json','bank_root_closure':'/relocated/meta/bank-root.json','case_root_closure':'/relocated/meta/case-root.json'}}
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent,prefix='generated-')as d:
   value=self.portable_packet(Path(d),custody);identity=json.loads((C/'CASE_IDENTITY.json').read_bytes())
   self.assertEqual({k:{z:r[z]for z in('bytes','sha256')}for k,r in value['public'].items()},identity['public'])
   self.assertTrue(all(r['path'].startswith('/relocated/case/')for r in value['private'].values()))
   tree=ast.parse((C/'rtt_profile.py').read_bytes());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='mapping')
   ns={'need':ad.need,'LABELS':('candidate','grade'),'packet':lambda:value,'HERE':C,'ROOT':SOURCE,'assets':lambda:json.loads((C/'ASSETS.json').read_bytes())}
   exec(compile(ast.Module(body=[node],type_ignores=[]),'<actual role mapping>','exec'),ns)
   candidate=ns['mapping'](Path(value['new_run']),'candidate');grade=ns['mapping'](Path(value['new_run']),'grade')
   self.assertEqual(len(candidate),5);self.assertFalse(any(k.startswith('/private/')for k in candidate));self.assertEqual(candidate['/training/source_counts.npz'],('/relocated/banks/source_counts.npz',True))
   self.assertEqual(grade['/private/observations.jsonl'],('/relocated/case/observations.jsonl',True));self.assertEqual(len(grade),14)
 def test_portable_custody_refuses_hash_role_or_relative_root_changes(self):
  original={'schema':'neural024-prepared-custody/v1','public_root':'/relocated/banks','private_root':'/relocated/case','metadata_paths':{'bank_qualification':'/relocated/meta/bank.json','bank_root_closure':'/relocated/meta/bank-root.json','case_root_closure':'/relocated/meta/case-root.json'}}
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent,prefix='generated-')as d:
   with self.assertRaises(ValueError):self.portable_packet(Path(d),original,True)
   for change in(lambda v:v['metadata_paths'].update(extra='/extra'),lambda v:v.update(public_root='relative/banks')):
    value=copy.deepcopy(original);change(value)
    with self.assertRaises(ValueError):self.portable_packet(Path(d),value)
 def test_shipped_source_manifest_matches_complete_public_bundle(self):
  manifest=json.loads((SOURCE/'SOURCE_MANIFEST.json').read_bytes())
  actual={str(p.relative_to(SOURCE))for p in(SOURCE/'authoring').rglob('*')if p.is_file()}|{'run_programme.py'}
  self.assertEqual(set(manifest['files']),actual)
  for relative,expected in manifest['files'].items():
   self.assertEqual(ad.pin((SOURCE/relative).read_bytes()),expected,relative)
if __name__=='__main__':unittest.main(verbosity=2)
