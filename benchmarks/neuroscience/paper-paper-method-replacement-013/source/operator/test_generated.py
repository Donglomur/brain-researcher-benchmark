"""All numeric arrays invented. No fits, author imports, network or weights."""
import unittest,sys,tempfile,copy,os,json,math,hashlib
from pathlib import Path
PACKAGE=Path(__file__).resolve().parents[1]
ROOT=PACKAGE if (PACKAGE/'public/contract.py').is_file() else PACKAGE.parent
sys.path[:0]=[str(PACKAGE/'operator'),str(ROOT/'public'),str(ROOT/'operator'),str(ROOT/'tests'),str(Path(__file__).parent)]
import numpy as np
from contract import *
import metrics
from stage import stage
from fixtures import make,candidate
from prepare import publish
from score import admit,grade

class Numeric(unittest.TestCase):
 def test_constant_decimal(self):self.assertIsNone(metrics.pearson([.1]*7,list(range(7))))
 def test_perfect_small(self):self.assertAlmostEqual(metrics.pearson([1e-300,2e-300,3e-300],[1e-300,2e-300,3e-300]),1)
 def test_perfect_extreme(self):self.assertEqual(metrics.regression([1e308,-1e308],[1e308,-1e308])['r2'],1)
 def test_extreme_constant_prediction(self):
  v=metrics.regression([1e308,-1e308]*2,[0.]*4);self.assertEqual(v['r2'],0);self.assertEqual(v['rmse'],1e308)
 def test_negative(self):self.assertLess(metrics.regression([0.,1.],[10.,10.])['r2'],0)
 def test_missing_neural_support(self):self.assertIsNone(metrics.event_counts([0,0],[0,0])['count_intersection_f1'])
 def test_count_vs_presence(self):
  r=metrics.event_counts([2,0],[1,0]);self.assertAlmostEqual(r['count_intersection_f1'],2/3);self.assertEqual(r['presence_f1'],1)
 def test_no_matches(self):self.assertEqual(metrics.event_counts([2,0],[0,1])['count_intersection_f1'],0)
 def test_absent_class_not_full_ba(self):self.assertIsNone(metrics.classification([0,1],[[1/25]*25]*2,list(range(25)))['balanced_accuracy'])
 def test_nonfinite(self):
  with self.assertRaises(ValueError):metrics.pearson([1.,math.inf],[1.,2.])
 def test_original_f1_shortcut_is_preserved_not_endorsed(self):
  v=metrics.source_interval_id_scores([{0,1},{2},set()],[{0},{2,3},{4}])
  self.assertEqual(v['compute_scores_true_present_intervals']['f1'],1)
  self.assertEqual(v['compute_scores_true_present_intervals']['included_intervals'],2)
  self.assertAlmostEqual(v['compute_scores_scikit_predicted_present_intervals']['weighted_binary_f1'],1/3)
  self.assertEqual(v['complete_intervals'],3);self.assertFalse(v['paper_branch_and_window_conversion_qualified'])
 def test_source_empty_support_is_null_not_full_score(self):
  v=metrics.source_interval_id_scores([set()],[set()]);self.assertIsNone(v['compute_scores_true_present_intervals']['f1']);self.assertIsNone(v['compute_scores_scikit_predicted_present_intervals']['weighted_binary_f1'])
 def test_reproduction_and_improvement_are_distinct(self):
  from score import compare
  actual={'query_sha256':'a'*64,'rows':[{'case_id':'case','metrics':{'speed':{'pearson_r':.7,'rmse':2.}},'biological_macro':{'equal_animal_mean':{'speed/pearson_r':.7,'speed/rmse':2.}}}]}
  ref={'schema':'neuroformer_fixed_metrics_v1','task_id':TASK,'query_sha256':'a'*64,'reference_program_sha256':'b'*64,'reference_run_sha256':'c'*64,
    'rows':[{'case_id':'case','metrics':{'speed':{'pearson_r':.8,'rmse':3.}},'equal_animal_mean':{'speed/pearson_r':.8,'speed/rmse':3.}}]}
  values=compare(actual,ref)['rows'][0]['metrics'];self.assertAlmostEqual(values['/pooled/speed/pearson_r']['absolute_deviation'],.1)
  self.assertLess(values['/pooled/speed/pearson_r']['favorable_signed_change'],0);self.assertEqual(values['/pooled/speed/rmse']['favorable_signed_change'],1)

class Boundaries(unittest.TestCase):
 def test_utf8_only(self):
  with self.assertRaises(Exception):decode('{"x":1}'.encode('utf16'))
 def test_duplicate(self):
  with self.assertRaises(ValueError):decode(b'{"x":1,"x":2}')
 def test_huge_int(self):
  with self.assertRaises(ValueError):number(10**400)
 def test_fifo(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'fifo';os.mkfifo(p)
   with self.assertRaises(ValueError):capture(p)
 def test_context_overlap(self):
  rows=[{'id':str(i),'recording':'r','animal':'m','start_tick':50+i*10,'stop_tick':60+i*10,'context_start_tick':10+i*10,'split':s} for i,s in enumerate(('train','validation','test'))]
  with self.assertRaises(ValueError):validate_support(rows,'blocked_time')
 def test_held_session_refusal(self):
  rows=[{'id':str(i),'recording':'r','animal':'m','start_tick':50+i*100,'stop_tick':60+i*100,'context_start_tick':10+i*100,'split':s} for i,s in enumerate(('train','validation','test'))]
  with self.assertRaises(ValueError):validate_support(rows,'held_session')
 def test_exact_constant_features(self):
  from reference_linear import normalize_fit,normalize
  x=np.full((7,2),.1);state=normalize_fit(x);self.assertTrue((normalize(x,state)==0).all())

class Packet(unittest.TestCase):
 def setUp(self):
  from unittest.mock import patch
  self.paper_patch=patch('stage.captured_paper',return_value={'paper.pdf':b'%PDF invented common asset','PAPER_ASSET.json':b'{"generated":true}'})
  self.root_patch=patch('stage.ROOT',ROOT);self.paper_patch.start();self.root_patch.start()
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.obs=self.root/'obs';self.obs.mkdir();self.q,self.b=make(self.obs)
 def tearDown(self):
  self.temp.cleanup();self.paper_patch.stop();self.root_patch.stop()
 def test_complete_panel(self):query(self.q,False);self.assertEqual(len(PANEL),46)
 def test_missing_case(self):
  self.q['cases'].pop()
  with self.assertRaises(ValueError):query(self.q,False)
 def test_wrong_native_neurons(self):
  with self.assertRaises(ValueError):query(self.q,True)
 def test_fewshot_pair(self):
  c=next(c for c in self.q['cases'] if c['definition']['family']=='fewshot_speed');rows_for(self.q,c)[0]['start_tick']+=10
  with self.assertRaises(ValueError):query(self.q,False)
 def test_public_index_no_labels_or_rows(self):
  j=json.dumps(output_index(self.q));self.assertNotIn('support',j);self.assertNotIn('train_ids',j)
 def test_one_byte_under_metadata_cap(self):
  publish(self.q,self.b,self.obs,self.root/'ok',1_000_000,False);size=sum(p.stat().st_size for p in (self.root/'ok').iterdir())
  with self.assertRaises(ValueError):publish(self.q,self.b,self.obs,self.root/'bad',size-1,False)
  self.assertFalse((self.root/'bad').exists())
 def test_generation_history_not_teacher_forced(self):
  target=publish(self.q,self.b,self.obs,self.root/'packet',1_000_000,False)
  cid='medial--neural_ablation--past--100';v=stage(self.q,target,self.obs,cid,'paper_and_data',self.root/'view',2_000_000,False)
  self.assertFalse((self.root/'view/test_neural_history.npy').exists());self.assertFalse((self.root/'view/test_labels.npy').exists())
  a=np.load(self.root/'view/test_initial_neural_history.npy',allow_pickle=False);self.assertEqual(a.shape,(1,30,2))
 def test_behavior_has_no_query_targets(self):
  target=publish(self.q,self.b,self.obs,self.root/'packet',1_000_000,False)
  stage(self.q,target,self.obs,'lateral--joint_speed_gaze--neuroformer--100','paper_and_data',self.root/'view',2_000_000,False)
  names={p.name for p in (self.root/'view').iterdir()};self.assertFalse(any(x.startswith('test_') and ('gaze' in x or 'speed' in x or 'label' in x or 'video' in x) for x in names))
 def test_invalid_candidate_before_target(self):
  pred=self.root/'pred';pred.mkdir();v=candidate(pred,self.q);v['predictions'].pop();owned=self.root/'owned';owned.mkdir();calls=[]
  with self.assertRaises(ValueError):
   admit(v,self.q,pred,owned);grade(v,self.q,owned,lambda:calls.append(1),self.obs,production=False)
  self.assertEqual(calls,[])
 def test_full_generated_roundtrip(self):
  target=publish(self.q,self.b,self.obs,self.root/'packet',1_000_000,False);pred=self.root/'pred';pred.mkdir();v=candidate(pred,self.q);owned=self.root/'owned';owned.mkdir();admit(v,self.q,pred,owned)
  out=grade(v,self.q,owned,lambda:target,self.obs,production=False);self.assertEqual(len(out['rows']),46);self.assertIsNone(out['binary_reward'])
 def test_invalid_probabilities_before_callback(self):
  pred=self.root/'pred';pred.mkdir();v=candidate(pred,self.q);i=next(i for i,c in enumerate(self.q['cases']) if c['definition']['kind']=='classification')
  from array_io import describe
  name=v['predictions'][i]['array']['path'];a=np.ones(self.q['cases'][i]['output_shape']);np.save(pred/name,a,allow_pickle=False);v['predictions'][i]['array']=describe(pred/name,name,a.shape,a.dtype.str);calls=[]
  with self.assertRaises(ValueError):grade(v,self.q,pred,lambda:calls.append(1),self.obs,production=False)
  self.assertEqual(calls,[])
 def test_staging_preflight_before_array_read(self):
  from unittest.mock import patch
  target=publish(self.q,self.b,self.obs,self.root/'packet',1_000_000,False)
  with patch('stage.windows',side_effect=AssertionError('must not read arrays')):
   with self.assertRaises(ValueError):stage(self.q,target,self.obs,'medial--speed_regression--neuroformer--100','paper_and_data',self.root/'small',1,False)
  self.assertFalse((self.root/'small').exists())
 def test_closed_snapshot_survives_candidate_mutation(self):
  target=publish(self.q,self.b,self.obs,self.root/'packet',1_000_000,False);pred=self.root/'pred';pred.mkdir();v=candidate(pred,self.q)
  def load_target():
   np.save(pred/v['predictions'][0]['array']['path'],np.full((2,1),float('nan')),allow_pickle=False)
   return target
  out=grade(v,self.q,pred,load_target,self.obs,production=False);self.assertEqual(len(out['rows']),46)
 def test_biological_macro_does_not_pool_long_session(self):
  from score import biological_macro
  support=[{'animal':'mouse1','recording':'r1'}]*2+[{'animal':'mouse2','recording':'r2'}]*4
  y=np.array([0,1,0,1,2,3],dtype=float).reshape(-1,1);p=np.array([0,1,3,2,1,0],dtype=float).reshape(-1,1)
  v=biological_macro('regression',y,p,support,None);self.assertAlmostEqual(v['equal_animal_mean']['speed/pearson_r'],0)
 def test_pretraining_has_no_behavior_or_query(self):
  from stage_pretraining import stage_pretraining
  target=publish(self.q,self.b,self.obs,self.root/'packet',1_000_000,False)
  v=stage_pretraining(self.q,target,self.obs,'medial',self.root/'pretrain',2_000_000,False)
  self.assertFalse(v['behavior_labels_included']);self.assertFalse(v['validation_or_test_included']);self.assertEqual(v['files'][0]['shape'][0],100)
  self.assertEqual({p.name for p in (self.root/'pretrain').iterdir()},{'neural_history.npy','neural_current.npy','video.npy','PRETRAINING.json'})
 def test_pretraining_under_cap_never_reads(self):
  from stage_pretraining import stage_pretraining
  from unittest.mock import patch
  target=publish(self.q,self.b,self.obs,self.root/'packet',1_000_000,False)
  with patch('stage_pretraining.windows',side_effect=AssertionError('must not decode')):
   with self.assertRaises(ValueError):stage_pretraining(self.q,target,self.obs,'medial',self.root/'bad',1,False)
  self.assertFalse((self.root/'bad').exists())
 def test_later_seed_must_not_reveal_prior_query(self):
  sp=self.q['supports']['medial-source'];test=[r for r in sp['rows'] if r['split']=='test'];test[1]['start_tick']=1160;test[1]['stop_tick']=1170;test[1]['context_start_tick']=1120
  with self.assertRaises(ValueError):query(self.q,False)
 def test_baselines_must_share_assessment(self):
  sp=copy.deepcopy(self.q['supports']['medial-source']);sp['rows'][-1]['id']='changed';self.q['supports']['separate']=sp;self.q['cases'][0]['support_id']='separate'
  with self.assertRaises(ValueError):query(self.q,False)
 def test_bridge_swap_refused_before_arrays(self):
  from unittest.mock import patch
  target=publish(self.q,self.b,self.obs,self.root/'packet',1_000_000,False);target['bridge']['original_inputs'][0]['sha256']='f'*64;target['bridge_sha256']=digest(target['bridge'])
  with patch('stage.windows',side_effect=AssertionError('must not read substituted arrays')):
   with self.assertRaises(ValueError):stage(self.q,target,self.obs,'medial--speed_regression--neuroformer--100','paper_and_data',self.root/'swap',2_000_000,False)
 def test_ab_same_invented_data_exact_source_added_only(self):
  target=publish(self.q,self.b,self.obs,self.root/'packet',1_000_000,False);cid='medial--speed_regression--neuroformer--100'
  a=stage(self.q,target,self.obs,cid,'paper_and_data',self.root/'a',2_000_000,False)
  b=stage(self.q,target,self.obs,cid,'paper_data_official_code',self.root/'b',2_000_000,False)
  ap={r['path']:(r['bytes'],r['sha256']) for r in a['files']};bp={r['path']:(r['bytes'],r['sha256']) for r in b['files']}
  self.assertEqual(ap,{k:v for k,v in bp.items() if not k.startswith('official_code/')});self.assertEqual(len(bp)-len(ap),26)
  self.assertFalse((self.root/'a/official_code').exists());self.assertTrue((self.root/'b/official_code/LICENSE').is_file());self.assertNotIn('torch',sys.modules)
 def test_b_full_source_cap_before_array_reads(self):
  from unittest.mock import patch
  target=publish(self.q,self.b,self.obs,self.root/'packet',1_000_000,False)
  with patch('stage.windows',side_effect=AssertionError('must not decode')):
   with self.assertRaises(ValueError):stage(self.q,target,self.obs,'medial--speed_regression--neuroformer--100','paper_data_official_code',self.root/'small',1,False)
  self.assertFalse((self.root/'small').exists())
 def test_bad_author_copy_refused_before_arrays(self):
  from unittest.mock import patch
  target=publish(self.q,self.b,self.obs,self.root/'packet',1_000_000,False)
  with patch('author_source.capture',return_value=b'substitute source'),patch('stage.windows',side_effect=AssertionError('must not decode')):
   with self.assertRaises(ValueError):stage(self.q,target,self.obs,'medial--speed_regression--neuroformer--100','paper_data_official_code',self.root/'badsource',2_000_000,False)
  self.assertFalse((self.root/'badsource').exists())
 def test_native_recipe_is_source_only(self):
  from native_plan import plan
  value=plan('joint_behavior',25);self.assertFalse(value['may_execute']);self.assertEqual(value['programs_invoked'],0)
  self.assertEqual(value['source']['files'],26);self.assertIn('configs/Visnav/lateral/mconf_predict_all.yaml',value['training_argv']);self.assertNotIn('torch',sys.modules)
  with self.assertRaises(ValueError):plan('invented_medial_config',25)

if __name__=='__main__':unittest.main()
