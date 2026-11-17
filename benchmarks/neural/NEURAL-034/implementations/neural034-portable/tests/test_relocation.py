"""Focused generated relocation/admission controls; no Docker/data/numerical run."""
from pathlib import Path
import copy,hashlib,importlib.util,json,math,os,shutil,sys,tempfile,time,unittest
from unittest import mock
ROOT=Path(__file__).resolve().parents[1]
LOCAL='authoring/glial-context-v1/ordinary-completion-v1/'
def pin(b):return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def enc(v):return (json.dumps(v,sort_keys=True)+'\n').encode()
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(enc(v));return pin(p.read_bytes())
def module(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

class Portable(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name).resolve();self.env=dict(os.environ)
  for k in tuple(os.environ):
   if k.startswith('DOCKER_'):os.environ.pop(k)
  os.environ['NEURAL034_DOCKER']='/generated/no-execute/docker'
  os.environ['NEURAL034_DOCKER_HOST']='unix:///generated/no-execute/docker.sock'
 def tearDown(self):
  os.environ.clear();os.environ.update(self.env);self.tmp.cleanup()
 def relocated(self):
  target=self.base/'relocated';shutil.copytree(ROOT,target,ignore=shutil.ignore_patterns('__pycache__'))
  a=module('admission',target/LOCAL/'admission.py');sys.modules['admission']=a
  freeze=a.descriptor(target/LOCAL/'SOURCE_FREEZE.json')
  return target,a,freeze
 def test_complete_relocation_and_import_without_payloads(self):
  target,a,f=self.relocated();_,bodies=a.source_gate(f)
  self.assertEqual(a.ROOT,target);self.assertFalse((target/'artifacts-build/glial-context-002').exists())
  r=module('neural034_portable_runtime',target/LOCAL/'runtime.py');api=r.load(bodies)
  self.assertEqual(api.profile.ROOT,target)
  held=api.grader.runtime().scorer()
  self.assertEqual(held.ROOT,target);self.assertEqual(held.DOCKER,os.environ['NEURAL034_DOCKER'])
  self.assertEqual(held.IMAGE,'sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156')
  self.assertEqual(api.unit.ROOT,target)
  bad=target/'authoring/dmfc-timing/program-runner-v2/engine.py';bad.write_bytes(bad.read_bytes()+b'\n')
  with self.assertRaises(ValueError):a.source_gate(f)
 def test_full_seven_fold_provisioning_contract(self):
  source=json.loads((ROOT/'INPUTS.json').read_bytes())
  self.assertEqual(len(source['files']),10);self.assertEqual([x['role']for x in source['files'][:7]],[f'fold-{i:02d}'for i in range(7)])
  profile=json.loads((ROOT/'authoring/shared-program-runner-v2/profiles/NEURAL-034.json').read_bytes())
  self.assertEqual(len(profile['schedule']['units']),7)
  for unit in profile['schedule']['units']:
   self.assertEqual(len(unit['public_inputs']),1);self.assertEqual(unit['public_inputs'][0]['mount_destination'],'/input/public.npz')
   self.assertEqual(unit['expected_query_count'],20)
  self.assertFalse(profile['schedule']['cross_unit_mutable_state_allowed'])
  self.assertTrue(profile['schedule']['no_private_or_score_feedback'])
 def test_explicit_transport_and_external_qualification(self):
  target,a,_=self.relocated()
  evidence={'candidate_id':'NEURAL-034','image':a.IMAGE,'docker_binary':os.environ['NEURAL034_DOCKER'],'docker_host':os.environ['NEURAL034_DOCKER_HOST'],'qualified':True}
  p=target/'operator/generated-qualification.json';write(p,evidence)
  runtime={k:evidence[k]for k in ('image','docker_binary','docker_host','qualified')};runtime['qualification']=a.descriptor(p)
  review={'portable_runtime':runtime};self.assertEqual(a.runtime_environment(review),runtime)
  wrong=copy.deepcopy(review);wrong['portable_runtime']['image']='sha256:'+'9'*64
  with self.assertRaises(ValueError):a.runtime_environment(wrong)
  wrong=copy.deepcopy(review);wrong['portable_runtime']['docker_host']='unix:///different/socket'
  with self.assertRaises(ValueError):a.runtime_environment(wrong)
  os.environ['DOCKER_CONTEXT']='unadmitted'
  with self.assertRaises(ValueError):a.runtime_environment(review)
  os.environ.pop('DOCKER_CONTEXT');os.environ['DOCKER_API_VERSION']='9.99'
  with self.assertRaises(ValueError):a.runtime_environment(review)
  os.environ.pop('DOCKER_API_VERSION');p.unlink()
  with self.assertRaises(FileNotFoundError):a.runtime_environment(review)
 def test_historical_cost_is_carried_and_mismatch_refused(self):
  target,a,f=self.relocated()
  receipt={'candidate_id':'NEURAL-034','runtime_id':a.RUNTIME_ID,'cost_family_id':'astrocyte_source_family','source_freeze':a.HISTORICAL_SOURCE_FREEZE,'status':'program_scored','known_seconds_before':a.BASELINE,'charged_seconds':480,'known_seconds_after':a.BASELINE+480}
  for k in ('all_owned_absent','all_process_groups_absent_and_reaped','all_owned_cli_processes_absent','controller_direct_handle_reaped'):receipt[k]=True
  p=target/'operator/generated-prior.json';write(p,receipt)
  self.assertEqual(a.known_cost(a.descriptor(p),f),3159.932040249051)
  receipt['source_freeze']={'path':'wrong','bytes':1,'sha256':'0'*64};write(p,receipt)
  with self.assertRaises(ValueError):a.known_cost(a.descriptor(p),f)
  for name,body in [('a.py',b'print(1)\n'),('b.py',b'print(2)\n')]:
   p=target/'candidates'/name;p.parent.mkdir(exist_ok=True);p.write_bytes(body)
  self.assertNotEqual(a.descriptor(target/'candidates/a.py')['sha256'],a.descriptor(target/'candidates/b.py')['sha256'])
 def fixture(self):
  source=self.base/'source';source.mkdir();roles=[f'fold-{i:02d}'for i in range(7)]+['public_panel','private_targets','private_references'];rows=[];locators={}
  for i,role in enumerate(roles):
   b=('generated-'+role).encode();p=self.base/('input-'+str(i));p.write_bytes(b);locators[role]=str(p)
   rows.append({'role':role,'path':'generated-inputs/'+role+'.bin',**pin(b)})
  write(source/'INPUTS.json',{'files':rows})
  manifest={'task_id':'NEURAL-034','execution_authority':False,'files':{'INPUTS.json':pin((source/'INPUTS.json').read_bytes())}}
  write(source/'SOURCE_MANIFEST.json',manifest)
  return source,locators,pin((source/'SOURCE_MANIFEST.json').read_bytes())['sha256']
 def test_generated_copy_and_refusals_preserve_partial(self):
  p=module('provision_generated',ROOT/'provision.py');source,locators,h=self.fixture();dest=self.base/'workspace'
  result=p.provision(source,dest,locators,time.monotonic()+10,h)
  self.assertEqual(result['status'],'complete_inputs_and_source_only');self.assertEqual(len(result['inputs']),10)
  self.assertEqual(dest.stat().st_mode&0o777,0o700)
  with self.assertRaises(ValueError):p.provision(source,dest,locators,time.monotonic()+10,h)
  missing=dict(locators);del missing['fold-06']
  with self.assertRaises(ValueError):p.provision(source,self.base/'missing',missing,time.monotonic()+10,h)
  self.assertFalse((self.base/'missing').exists())
  with self.assertRaises(ValueError):p.provision(source,self.base/'wrong-manifest',locators,time.monotonic()+10,'0'*64)
  bad=dict(locators);bad['fold-01']=locators['fold-02']
  with self.assertRaises(ValueError):p.provision(source,self.base/'partial',bad,time.monotonic()+10,h)
  saved=json.loads((self.base/'partial/PROVISION_RECEIPT.json').read_bytes())
  self.assertEqual(saved['status'],'partial');self.assertEqual(len(saved['inputs']),1)
  linked=self.base/'linked';linked.symlink_to(locators['fold-00'])
  bad=dict(locators);bad['fold-00']=str(linked)
  with self.assertRaises(ValueError):p.provision(source,self.base/'linked-refused',bad,time.monotonic()+10,h)
 def current_fixture(self):
  source,inputs,_=self.fixture();old=b'# generated old inspector\n';new=b'# generated current inspector\n'
  historical=json.loads((source/'SOURCE_MANIFEST.json').read_bytes());historical['files']['check_result.py']=pin(old)
  old_pin=write(source/'SOURCE_MANIFEST.json',historical);(source/'check_result.py').write_bytes(new)
  current={'schema':'neural034-current-source/v1','task_id':'NEURAL-034','execution_authority':False,'native_qualification':False,
           'historical_manifest':{'path':'SOURCE_MANIFEST.json',**old_pin},'changed_members':['check_result.py'],
           'files':{**historical['files'],'check_result.py':pin(new)}}
  path=self.base/'current-source.json';current_pin=write(path,current)
  return source,inputs,old_pin['sha256'],path,current_pin['sha256']
 def test_current_source_provision_preserves_original_and_explicit_successor(self):
  p=module('provision_current_generated',ROOT/'provision.py');source,inputs,h,path,current_hash=self.current_fixture()
  original=(source/'SOURCE_MANIFEST.json').read_bytes();descriptor=path.read_bytes();dest=self.base/'current-workspace'
  result=p.provision(source,dest,inputs,time.monotonic()+10,h,path,current_hash)
  self.assertEqual(result['status'],'complete_inputs_and_source_only');self.assertFalse(result['execution_authority']);self.assertFalse(result['runtime_qualified'])
  self.assertEqual((dest/'SOURCE_MANIFEST.json').read_bytes(),original)
  self.assertEqual((dest/'CURRENT_SOURCE_MANIFEST.json').read_bytes(),descriptor)
  self.assertEqual((dest/'check_result.py').read_bytes(),(source/'check_result.py').read_bytes())
  self.assertEqual(result['current_source_manifest_sha256'],current_hash)
  with self.assertRaises(ValueError):p.provision(source,self.base/'old-only-refused',inputs,time.monotonic()+10,h)
  self.assertFalse((self.base/'old-only-refused').exists())
 def test_current_source_requires_independent_paired_descriptor_hash(self):
  p=module('provision_current_identity',ROOT/'provision.py');source,inputs,h,path,current_hash=self.current_fixture()
  for i,args in enumerate(((path,None),(None,current_hash),(path,'0'*64))):
   destination=self.base/f'bad-current-{i}'
   with self.subTest(args=args),self.assertRaises(ValueError):p.provision(source,destination,inputs,time.monotonic()+10,h,*args)
   self.assertFalse(destination.exists())
 def test_current_source_rejects_member_predecessor_runtime_and_body_drift(self):
  p=module('provision_current_drift',ROOT/'provision.py');source,inputs,h,path,_=self.current_fixture()
  original=json.loads(path.read_bytes())
  for case in ('predecessor','extra-member','source-body','runtime-change'):
   current=copy.deepcopy(original);destination=self.base/case
   if case=='predecessor':current['historical_manifest']['sha256']='0'*64
   elif case=='extra-member':current['files']['unselected.py']=pin(b'# extra\n')
   elif case=='source-body':current['files']['check_result.py']=pin(b'# different\n')
   else:
    current['files']['INPUTS.json']={'bytes':1,'sha256':'0'*64};current['changed_members']=['INPUTS.json','check_result.py']
   cp=write(path,current)
   with self.subTest(case=case),self.assertRaises(ValueError):p.provision(source,destination,inputs,time.monotonic()+10,h,path,cp['sha256'])
   self.assertFalse(destination.exists())
 def completed(self):
  root=self.base/'result';attempt=root/'attempt';attempt.mkdir(parents=True);program=b'# arbitrary generated programme\n'
  (attempt/'program.py').write_bytes(program);ps=pin(program)['sha256'];prev=None;commits=[];units=[];rows=[]
  for i in range(7):
   folder=attempt/f'fold-{i:02d}';folder.mkdir()
   subset=[{'query_id':format(i*20+j,'024x'),'probability':.2}for j in range(20)]
   op=write(folder/'probabilities.json',{'schema_version':1,'probabilities':subset})
   v={'status':'removed_producer_output_committed','program_sha256':ps,'previous_commit_sha256':prev,'producer_removed_before_capture':True,'all_candidate_holder_volume_absent':True,'output':op}
   cp=write(folder/'commit.json',v);prev=cp['sha256'];commits.append(prev)
   ep=write(folder/'execution.json',{'candidate_id':'NEURAL-034','unit_id':f'fold-{i:02d}','status':'unit_committed','all_owned_absent':True,'program_sha256':ps,'commit_sha256':prev,'output':op})
   units.append({'unit_id':f'fold-{i:02d}','status':'unit_committed','all_owned_absent':True,'execution_sha256':ep['sha256']})
   rows.extend({'fold':i,**r}for r in subset)
  ap=write(attempt/'probabilities.json',{'schema_version':1,'probabilities':rows})
  write(attempt/'aggregate_commit.json',{'status':'all_seven_removed_producers_committed','all_units_absent_before_private_grade':True,'program_sha256':ps,'submission_sha256':ap['sha256'],'unit_commit_sha256':commits,'last_commit_sha256':prev})
  metrics={'balanced_accuracy':.3,'log_loss':2.0}
  grade={'status':'scored','per_mouse':[{'fold':i,**metrics}for i in range(7)],'co_primary_metrics':metrics,'signed_candidate_minus_reference':{x:{'balanced_accuracy':-.2,'log_loss':1.}for x in module('result_checker_names',ROOT/'check_result.py').COMPARATORS}}
  gp=write(attempt/'grade/score.json',grade)
  inner={'status':'program_scored','all_owned_absent':True,'private_grade_dispatched':True,'units':units,'program_sha256':ps,'grade':{'score_sha256':gp['sha256'],'submission_sha256':ap['sha256'],'absence_verified':True}}
  ip=write(attempt/'execution.json',inner)
  outer={'candidate_id':'NEURAL-034','status':'program_scored','inner_execution_sha256':ip['sha256']}
  for k in ('all_owned_absent','all_process_groups_absent_and_reaped','all_owned_cli_processes_absent','controller_direct_handle_reaped'):outer[k]=True
  write(root/'outer_execution.json',outer);return root
 def rehash_grade(self,root,grade):
  updated=write(root/'attempt/grade/score.json',grade)
  p=root/'attempt/execution.json';inner=json.loads(p.read_bytes());inner['grade']['score_sha256']=updated['sha256'];updated=write(p,inner)
  p=root/'outer_execution.json';outer=json.loads(p.read_bytes());outer['inner_execution_sha256']=updated['sha256'];write(p,outer)
 def test_co_primary_domains_and_equal_mouse_means_reject_rehashed_metrics(self):
  c=module('result_checker_co_primary',ROOT/'check_result.py');root=self.completed()
  baseline=json.loads((root/'attempt/grade/score.json').read_bytes())
  for metrics in ({'balanced_accuracy':2.,'log_loss':-4.},
                  {'balanced_accuracy':.9,'log_loss':.1},
                  {'balanced_accuracy':math.nextafter(.3,1.),'log_loss':2.}):
   with self.subTest(metrics=metrics):
    grade=copy.deepcopy(baseline);grade['co_primary_metrics']=metrics;self.rehash_grade(root,grade)
    with self.assertRaises(ValueError):c.check(root)
 def test_unequal_mouse_metrics_use_the_frozen_graders_exact_reduction(self):
  c=module('result_checker_equal_mouse',ROOT/'check_result.py');root=self.completed()
  grade=json.loads((root/'attempt/grade/score.json').read_bytes())
  accuracies=[0.,1.,.1,.2,.3,.4,.5];losses=[0.,.1,.2,.3,1.,2.,3.]
  grade['per_mouse']=[{'fold':i,'balanced_accuracy':accuracies[i],'log_loss':losses[i]}for i in reversed(range(7))]
  expected={'balanced_accuracy':math.fsum(accuracies)/7,'log_loss':math.fsum(losses)/7}
  grade['co_primary_metrics']=expected;self.rehash_grade(root,grade)
  self.assertEqual(c.check(root)['score'],expected)
 def test_grade_submission_identity_is_required_and_matches_aggregate(self):
  c=module('result_checker_submission_binding',ROOT/'check_result.py');root=self.completed()
  for identity in (None,'0'*64):
   with self.subTest(identity=identity):
    p=root/'attempt/execution.json';inner=json.loads(p.read_bytes())
    if identity is None:inner['grade'].pop('submission_sha256',None)
    else:inner['grade']['submission_sha256']=identity
    updated=write(p,inner)
    p=root/'outer_execution.json';outer=json.loads(p.read_bytes());outer['inner_execution_sha256']=updated['sha256'];write(p,outer)
    with self.assertRaisesRegex(ValueError,'grade binds committed aggregate'):c.check(root)
 def test_last_setup_write_cannot_publish_late_success(self):
  p=module('provision_late_generated',ROOT/'provision.py');source,locators,h=self.fixture();clock=[0.];original=Path.write_text
  def late(path,*args,**kw):
   answer=original(path,*args,**kw)
   if path.name=='config.json':clock[0]=121.
   return answer
  with mock.patch.object(p.time,'monotonic',lambda:clock[0]),mock.patch.object(Path,'write_text',late):
   with self.assertRaises(ValueError):p.provision(source,self.base/'late',locators,120.,h)
  receipt=json.loads((self.base/'late/PROVISION_RECEIPT.json').read_bytes())
  self.assertEqual(receipt['status'],'partial');self.assertIn('deadline',receipt['failure'])
 def test_contradictory_unit_body_is_rejected_after_rehash(self):
  c=module('result_checker_contradiction',ROOT/'check_result.py');root=self.completed()
  p=root/'attempt/fold-00/execution.json';v=json.loads(p.read_bytes());v['status']='candidate_program_failed';v['all_owned_absent']=False;updated=write(p,v)
  p=root/'attempt/execution.json';v=json.loads(p.read_bytes());v['units'][0]['execution_sha256']=updated['sha256'];updated=write(p,v)
  p=root/'outer_execution.json';v=json.loads(p.read_bytes());v['inner_execution_sha256']=updated['sha256'];write(p,v)
  with self.assertRaises(ValueError):c.check(root)
 def test_missing_per_mouse_metrics_rejected_after_rehash(self):
  c=module('result_checker_metrics',ROOT/'check_result.py');root=self.completed()
  p=root/'attempt/grade/score.json';v=json.loads(p.read_bytes());v['per_mouse']=[{'fold':i}for i in range(7)];updated=write(p,v)
  p=root/'attempt/execution.json';v=json.loads(p.read_bytes());v['grade']['score_sha256']=updated['sha256'];updated=write(p,v)
  p=root/'outer_execution.json';v=json.loads(p.read_bytes());v['inner_execution_sha256']=updated['sha256'];write(p,v)
  with self.assertRaises(ValueError):c.check(root)
 def test_complete_weak_output_is_accepted_missing_closure_is_not(self):
  c=module('result_checker',ROOT/'check_result.py');root=self.completed();result=c.check(root)
  self.assertEqual(result['score'],{'balanced_accuracy':.3,'log_loss':2.0})
  p=root/'outer_execution.json';v=json.loads(p.read_bytes());v['all_owned_absent']=False;write(p,v)
  with self.assertRaises(ValueError):c.check(root)
 def test_commit_mismatch_is_not_a_partial_success(self):
  c=module('result_checker_two',ROOT/'check_result.py');root=self.completed()
  p=root/'attempt/fold-06/probabilities.json';v=json.loads(p.read_bytes());v['probabilities'].pop();write(p,v)
  with self.assertRaises(ValueError):c.check(root)

if __name__=='__main__':unittest.main()
