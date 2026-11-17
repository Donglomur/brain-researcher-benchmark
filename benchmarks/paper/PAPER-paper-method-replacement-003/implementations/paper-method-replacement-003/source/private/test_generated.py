"""Invented observations only. No empirical files, model fit or author imports."""
import copy,hashlib,json,math,os,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'public'),str(ROOT/'private')]
import contract as C
import score as S
import prepare as P
import stage as V

def fixture():
    q=dict(schema='c4_query_v1',task_id=C.TASK,source_revision=C.REV,classes=list(C.CLASSES),repeats=10,input_index_sha256='a'*64,selection_sha256='b'*64,pretraining_sha256='c'*64,run_config_sha256='d'*64,scope='full_selected_c4_mouse_monkey',domains={d:dict(unit_ids=[d+'_'+str(i) for i in range(5)],label_basis='mouse_source_ground_truth' if d=='mouse_loo' else 'monkey_expert_reference',model_members_per_repeat={m:5 if d=='monkey_transfer' and m in ('deep','improved') else 1 for m in C.METHODS}) for d in C.DOMAINS})
    t={'schema':'c4_target_v1','query_sha256':C.digest(q),'labels':{d:list(C.CLASSES) for d in C.DOMAINS},'groups':{d:[dict(animal='animal'+str(i//2),session='s'+str(i),lab='lab') for i in range(5)] for d in C.DOMAINS}}
    s={'schema':'c4_predictions_v1','task_id':C.TASK,'query_sha256':C.digest(q),'information_arm':C.ARMS[0],'method_description':'invented fixture','predictions':{m:{d:[{'unit_id':u,'probabilities':[[int(c==i) for c in range(5)] for _ in range(10)]} for i,u in enumerate(q['domains'][d]['unit_ids'])] for d in C.DOMAINS} for m in C.METHODS}}
    return q,s,t

def idx():
    q,_,t=fixture();names=['hull_unlabelled','lisberger','medina_unlabelled','hausser','hull_labelled'];sizes=[30589152758,41387556732,5950752328,43408452946,2268498044];md5s=['89c03497f029ffb60b02d323e084d57a','ae4977105191e53f860f0571f8d98c18','346a13f6fd6b1cb388efbc63a9cc690a','56a60394ebb2a0515a8509d74124ca9c','6928f38e1d3ef5d3f940d57d6003452d']
    x=dict(schema='c4_normalized_index_v1',source_revision=C.REV,selection_sha256='b'*64,pretraining_sha256='c'*64,run_config_sha256='d'*64,original_files=[dict(name='C4_database_'+n+'.h5',bytes=b,published_md5=m,sha256='e'*64) for n,b,m in zip(names,sizes,md5s)],units={d:[dict(unit_id=u,source_key='source-'+u,label=C.CLASSES[i],animal='a'+str(i),session='s'+str(i),lab='lab',feature={'path':u+'.json','bytes':100,'sha256':'a'*64}) for i,u in enumerate(q['domains'][d]['unit_ids'])] for d in C.DOMAINS},pretraining_units=[],exclusions=[],model_members_per_repeat={d:q['domains'][d]['model_members_per_repeat'] for d in C.DOMAINS});return x

def ftr():return dict(waveform=[0]*120,acg_3d=[[0]*201 for _ in range(10)],engineered={k:1 for k in C.ENGINEERED_COLUMNS},layer='unknown')
class Tests(unittest.TestCase):
 def test_query_full(self):
    q,_,_=fixture();C.query(q,False)
    with self.assertRaises(ValueError):C.query(q)
 def test_perfect(self):
    q,s,t=fixture();r=S.grade(s,q,t);self.assertEqual(r['metrics']['deep']['mouse_loo']['all_units']['accuracy'],1);self.assertIsNone(r['binary_reward'])
 def test_wrong(self):
    q,s,t=fixture()
    for row in s['predictions']['deep']['mouse_loo']:row['probabilities']=[[0,0,0,0,1]]*10
    self.assertEqual(S.grade(s,q,t)['metrics']['deep']['mouse_loo']['all_units']['accuracy'],.2)
 def test_mean_before_ratio(self):
    rows=[{'probabilities':[[1,0,0,0,0]]*5+[[0,1,0,0,0]]*5}];p=S.mean_prob(rows)[0];self.assertFalse(S.ratio_at_least(p,2))
 def test_ratio_boundary(self):self.assertTrue(S.ratio_at_least([.5,.25,.25,0,0],2))
 def test_zero_second(self):self.assertTrue(S.ratio_at_least([1,0,0,0,0],10))
 def test_no_retained(self):
    r=S.summary([[.2]*5],['GoC'],[False]);self.assertIsNone(r['accuracy']);self.assertIsNone(r['confusion_row_conditional'][0][0]);self.assertEqual(r['unclassified_fraction'][0],1)
 def test_missingclass(self):self.assertIsNone(S.summary([[1,0,0,0,0]],['GoC'],[True])['macro_recall'])
 def test_fractional_ties(self):
    p=[[.2]*5]*4;r=S.weighted_accuracy(p,['GoC','MLI','MLI','GoC'],.25);self.assertEqual(r['retained_weight'],1);self.assertEqual(r['accuracy'],.5)
 def test_ratio_subnormal(self):self.assertEqual(S.ratio_cmp([1,1e-310,0,0,0],[1,2e-310,0,0,0]),1)
 def test_row_order(self):
    q,s,t=fixture();s['predictions']['deep']['mouse_loo'].reverse()
    with self.assertRaises(ValueError):S.grade(s,q,t)
 def test_probability_nonfinite(self):
    for v in (float('nan'),float('inf'),10**400,True):
     with self.assertRaises(ValueError):C.probability([v,0,0,0,0])
 def test_probability_sum(self):
    with self.assertRaises(ValueError):C.probability([.1]*5)
 def test_duplicate_keys(self):
    with self.assertRaises(ValueError):C.decode(b'{"a":1,"a":2}')
 def test_fifo(self):
    with tempfile.TemporaryDirectory() as td:
     p=Path(td)/'fifo';os.mkfifo(p)
     with self.assertRaises(ValueError):C.capture(p)
 def test_dangling_output(self):
    with tempfile.TemporaryDirectory() as td:
     p=Path(td)/'out';p.symlink_to('absent')
     with self.assertRaises(ValueError):C.fresh(p)
 def test_wrong_target(self):
    q,s,t=fixture();t['query_sha256']='f'*64
    with self.assertRaises(ValueError):S.grade(s,q,t)
 def test_train_test_split(self):
    x=idx();r=P.project(x,'mouse_loo_0',lambda u:ftr(),False);self.assertEqual(len(r['training']),4);self.assertEqual(r['query'][0]['unit_id'],'mouse_loo_0');self.assertNotIn('label',r['query'][0]);V.fold(r)
 def test_monkey_never_train(self):
    r=P.project(idx(),'monkey_transfer',lambda u:ftr(),False);self.assertTrue(all(v['unit_id'].startswith('mouse') for v in r['training']));self.assertTrue(all(v['unit_id'].startswith('monkey') for v in r['query']))
 def test_pretraining_overlap(self):
    x=idx();u=x['units']['mouse_loo'][0];x['pretraining_units']=[{k:u[k] for k in ('unit_id','feature')}]
    with self.assertRaises(ValueError):P.index(x,False)
 def test_geometry(self):
    x=ftr();x['acg_3d'][0].pop()
    with self.assertRaises(ValueError):P.features(x)
 def test_full_originals(self):
    x=idx();x['original_files'].pop()
    with self.assertRaises(ValueError):P.index(x,False)
 def test_feature_hash(self):
    with tempfile.TemporaryDirectory() as td:
     p=Path(td)/'x.json';p.write_bytes(C.enc(ftr()));u={'feature':{'path':'x.json','bytes':p.stat().st_size,'sha256':'a'*64}}
     with self.assertRaises(ValueError):P.read_feature(td,u)
 def test_path_escape(self):
    with self.assertRaises(ValueError):P.feature_pin({'path':'../x','bytes':1,'sha256':'a'*64})
 def test_same_columns(self):
    r=P.project(idx(),'monkey_transfer',lambda u:ftr(),False);r['query'][0]['features']['engineered']={'other':1}
    with self.assertRaises(ValueError):V.fold(r)
 def test_group_macro(self):
    q,s,t=fixture();r=S.grade(s,q,t);self.assertEqual(r['metrics']['deep']['mouse_loo']['group_descriptive']['animal']['macro_accuracy'],1)
 def test_cli_bad_submission_before_target(self):
    from unittest.mock import patch
    q,s,t=fixture();s['query_sha256']='f'*64;seen=[]
    def read(path):
     seen.append(path)
     if path=='target':raise AssertionError('private read too early')
     return q if path=='q' else s
    with patch.object(S,'load',read),patch.object(S,'query',lambda x:x),patch.object(S,'fresh',lambda p:None),patch.object(sys,'argv',['score','--query','q','--submission','s','--target','target','--output','out']):
     with self.assertRaises(ValueError):S.main()
    self.assertEqual(seen,['q','s'])
 def test_stager_a_b(self):
    with tempfile.TemporaryDirectory() as td:
     packet=Path(td)/'fold.json';packet.write_bytes(C.enc(P.project(idx(),'monkey_transfer',lambda u:ftr(),False)));pin=hashlib.sha256(packet.read_bytes()).hexdigest()
     for arm in C.ARMS:
      dest=Path(td)/arm;V.stage(packet,pin,arm,dest)
      self.assertEqual((dest/'public/official_code').exists(),arm==C.ARMS[1]);self.assertFalse((dest/'private').exists());self.assertEqual((dest/'public/FOLD.json').read_bytes(),packet.read_bytes())
 def test_stager_cap_prewrite(self):
    with tempfile.TemporaryDirectory() as td:
     packet=Path(td)/'fold.json';packet.write_bytes(C.enc(P.project(idx(),'monkey_transfer',lambda u:ftr(),False)));pin=hashlib.sha256(packet.read_bytes()).hexdigest();out=Path(td)/'out'
     with self.assertRaises(ValueError):V.stage(packet,pin,C.ARMS[0],out,cap=10)
     self.assertFalse(out.exists())
 def test_schema_end(self):
    import re
    schema=json.loads((ROOT/'public/OUTPUT_SCHEMA.json').read_text());pat=schema['properties']['query_sha256']['pattern'];self.assertIsNotNone(re.search(pat,'a'*64));self.assertIsNone(re.search(pat,'a'*64+'\n'))
 def test_source_command_flags(self):
    import ast
    import reference_recipe as R
    commands=R.commands('/data','/features');mapping={'dataset':'dataset_init.py','monkey':'monkey_dataset_init.py','baseline_template':'run_baseline_classifier.py','deep_template':'run_deep_classifier.py'}
    for k,f in mapping.items():
     tree=ast.parse((ROOT/'private/official_code/npyx/c4'/f).read_text());allowed={a.value for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='add_argument' for a in n.args if isinstance(a,ast.Constant) and isinstance(a.value,str)}
     for flag in commands[k]:
      if flag.startswith('--'):self.assertIn(flag,allowed)
 def test_source_baseline_pooled_vs_deep_mean(self):
    q,s,t=fixture()
    for m in ('deep','random_forest'):
     for row in s['predictions'][m]['mouse_loo']:row['probabilities']=[[1,0,0,0,0]]*5+[[0,1,0,0,0]]*5
    r=S.grade(s,q,t)['metrics'];self.assertEqual(r['random_forest']['mouse_loo']['source_plot_probability_thresholds']['0.9']['retained'],50);self.assertEqual(r['deep']['mouse_loo']['source_plot_probability_thresholds']['0.9']['retained'],0);self.assertIn('0.4',r['deep']['mouse_loo']['source_plot_probability_thresholds']);self.assertNotIn('0.4',r['random_forest']['mouse_loo']['source_plot_probability_thresholds'])
 def test_baseline_model_count(self):
    q,_,_=fixture();q['domains']['monkey_transfer']['model_members_per_repeat']['random_forest']=202
    with self.assertRaises(ValueError):C.query(q,False)
 def test_observed_union_f1(self):
    r=S.summary([[1,0,0,0,0]],['GoC'],[True]);self.assertIsNone(r['macro_f1']);self.assertEqual(r['observed_union_macro_f1'],1)
 def test_no_engineered_label_leak(self):
    v=ftr();v['engineered']['label']=1
    with self.assertRaises(ValueError):P.features(v)
 def test_engineered_source_columns(self):
    import ast
    tree=ast.parse((ROOT/'private/official_code/npyx/feat.py').read_text());cols=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='FEATURES' for t in n.targets));self.assertEqual(tuple(c for c in cols if c not in ['label','dataset','unit','relevant_channel','any_somatic','max_peaks']),C.ENGINEERED_COLUMNS)
 def test_documented_isolated_stage_cli(self):
    import subprocess
    with tempfile.TemporaryDirectory() as td:
     packet=Path(td)/'fold.json';packet.write_bytes(C.enc(P.project(idx(),'monkey_transfer',lambda u:ftr(),False)));pin=hashlib.sha256(packet.read_bytes()).hexdigest();out=Path(td)/'view'
     r=subprocess.run([sys.executable,'-I','-S','-B',str(ROOT/'private/stage.py'),'--packet',str(packet),'--packet-sha256',pin,'--arm',C.ARMS[0],'--output',str(out)],capture_output=True,timeout=10)
     self.assertEqual(r.returncode,0,r.stderr.decode());self.assertTrue((out/'VIEW.json').is_file())
if __name__=='__main__':unittest.main()



