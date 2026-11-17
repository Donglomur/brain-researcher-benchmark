"""Invented-array/source-metadata construction checks only; no models or real data."""
import sys,unittest,hashlib,json,tempfile,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'private'),str(ROOT/'public')]
import numpy as np
from metrics import auc,exact_summary,aggregate,improvement
from intervals import validate_segments
from design import contexts,outputs,validate_public,TASK_ID,SOURCE_PROTOCOL_SHA
from protocol import digest
from arrays import write_array
from io_contract import put,capture
import score
from prepare import check_seed_support

def row(person,seed,value):
 return {'protocol':'random_nonoverlap','person':person,'task':'speech_vs_nonspeech','fold':0,'seed':seed,'model':'channels_channels','roc_auc':value}

class Generated(unittest.TestCase):
 def test_auc_ties(self):self.assertEqual(auc(np.array([0,1,0,1]),np.array([.5,.5,.2,.8]))['roc_auc'],.875)
 def test_auc_single_class(self):self.assertIsNone(auc(np.ones(3,dtype=int),np.zeros(3))['roc_auc'])
 def test_no_missing_predictions(self):
  for p in (np.array([.2,np.nan]),np.array([1.01,0.])):
   with self.assertRaises(ValueError):auc(np.array([0,1]),p)
 def test_constant_sem(self):self.assertEqual(exact_summary([.1]*35)['sem'],0.)
 def test_native_and_person_weighting_differ(self):
  rows=[row(1,i,.9) for i in range(3)]+[row(2,0,.1)];out=aggregate(rows,rows)[0]
  self.assertAlmostEqual(out['source_session_seed_fold_summary']['mean'],.7);self.assertEqual(out['prospective_equal_person_summary']['mean'],.5)
 def test_complete_order(self):
  rows=[row(1,0,.8),row(2,0,.6)]
  with self.assertRaises(ValueError):aggregate(rows[:-1],rows)
  with self.assertRaises(ValueError):aggregate(rows[::-1],rows)
 def test_undefined_propagates(self):
  rows=[row(1,0,.8),row(2,0,None)];d=aggregate(rows,rows)[0];self.assertIsNone(d['source_session_seed_fold_summary']['mean']);self.assertIsNone(d['prospective_equal_person_summary']['mean'])
 def test_trusted_comparison_complete(self):
  rows=[row(1,0,.8),row(2,0,.6)];trusted=[row(1,0,.7),row(2,0,.5)]
  d=improvement(rows,rows,trusted);self.assertAlmostEqual(d['paired_auc_gain']['mean'],.1)
  with self.assertRaises(ValueError):improvement(rows,rows,trusted[::-1])

 def test_finetuning_seed_cannot_change_support(self):
  pin={'path':'a.npy','bytes':144,'sha256':'a'*64,'shape':[2],'dtype':'<f8'}
  d={'recording':'sub_1_trial001','native_fold':0,'channels':['A'],'spatial_ids':pin,'labels':pin,'partitions':{'train':[0],'validation':[1],'query':[2]},'rows':[{'id':'original','start_sample':0,'end_sample':6144,'neural':pin}],'provenance':{'raw_recording':'b'*64,'split_indices':'c'*64,'checkpoint_exposure':'d'*64}}
  e={'protocol':'random_nonoverlap','person':1,'task':'sentence_onset','fold':0,'seed':1};seen={};check_seed_support(d,e,seen)
  other=copy.deepcopy(d);other['labels']['path']='alias.npy';other['provenance']['checkpoint_exposure']='e'*64;check_seed_support(other,dict(e,seed=2),seen)
  other['rows'][0]['neural']['sha256']='f'*64
  with self.assertRaises(ValueError):check_seed_support(other,dict(e,seed=2),seen)

 def test_interval_touch_and_within_partition_overlap(self):
  rows=[{'id':'a','start_sample':0,'end_sample':6144},{'id':'b','start_sample':6144,'end_sample':12288},{'id':'c','start_sample':12288,'end_sample':18432}];parts={'train':[0],'validation':[1],'query':[2]}
  self.assertTrue(validate_segments(rows,parts,force_nonoverlap=True)['native_window_overlap_checked'])
  rows.append({'id':'d','start_sample':1,'end_sample':6145});parts['train'].append(3)
  with self.assertRaises(ValueError):validate_segments(rows,parts,force_nonoverlap=False)
  rows[3]={'id':'d','start_sample':0,'end_sample':6144}
  validate_segments(rows,parts,force_nonoverlap=False)
  with self.assertRaises(ValueError):validate_segments(rows,parts,force_nonoverlap=True)
 def test_interval_support_and_clock(self):
  rows=[{'id':str(i),'start_sample':i*6144,'end_sample':(i+1)*6144} for i in range(3)];parts={'train':[0],'validation':[1],'query':[2]}
  rows[1]['end_sample']-=1
  with self.assertRaises(ValueError):validate_segments(rows,parts,force_nonoverlap=True)
  rows[1]['end_sample']+=1;parts['query']=[0]
  with self.assertRaises(ValueError):validate_segments(rows,parts,force_nonoverlap=True)
 def test_complete_grid_and_input_generation(self):
  public=public_panel();validate_public(public);self.assertEqual(len(contexts()),770);self.assertEqual(len(list(outputs(public))),22960)
  public['contexts'].pop();public['panel_id']=digest({k:v for k,v in public.items() if k!='panel_id'})
  with self.assertRaises(ValueError):validate_public(public)
  public=public_panel();public['generation_commitment']='b'*64
  with self.assertRaises(ValueError):validate_public(public)
 def test_paper_source_cohort_metadata(self):
  src=ROOT/'source' if (ROOT/'source').is_dir() else ROOT/'private/source'
  b=capture(src/'PROTOCOL.json');self.assertEqual(hashlib.sha256(b).hexdigest(),SOURCE_PROTOCOL_SHA);d=json.loads(b);self.assertEqual(d['counts'],{'people':10,'recordings':26,'pretraining_recordings':17,'downstream_validation_recordings':2,'downstream_test_recordings':7})
  self.assertEqual(d['spatial_count_by_person']['6']['channels'],134);self.assertEqual(next(r for r in d['recordings'] if r['source_session']=='HOLDSUBJ_6_HS6_4')['recording'],'sub_6_trial004')
 def test_full_candidate_admission_before_private_targets(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td).resolve();public=public_panel();put(root/'PUBLIC.json',public);pb=capture(root/'PUBLIC.json');pin=write_array(root/'p.npy',np.array([.1,.9,.2,.8]));preds=[{k:e[k] for k in ('id','arm','model','query_ids_sha256')}|{'values':pin} for e in outputs(public)];sub={'task_id':TASK_ID,'panel_id':public['panel_id'],'predictions':preds};put(root/'SUB.json',sub)
   provenance={k:'a'*64 for k in ('program_sha256','training_config_sha256','checkpoint_sha256','exposure_audit_sha256','execution_receipt_sha256','baseline_artifact_sha256')};provenance['metadata_is_not_execution_attestation']=True
   gold={'schema':'barista_gold_binding_v1','panel_id':public['panel_id'],'public_sha256':hashlib.sha256(pb).hexdigest(),'contexts':[{'id':e['id'],'query_ids_sha256':e['query_ids_sha256']} for e in public['contexts']],'trusted_reference_provenance':provenance};put(root/'GOLD.json',gold);calls=[]
   def loader(row,e):calls.append(e['id']);return np.array([0,1,0,1]),np.full(4,.5)
   result=score.grade(root/'PUBLIC.json',root/'GOLD.json',root/'SUB.json',loader);self.assertEqual(result['primary'],{'paper_and_data':1.,'paper_data_official_code':1.});self.assertEqual(len(calls),22960)
   main=result['source_classification']['paper_and_data'];self.assertEqual(main[0]['source_session_seed_fold_summary']['count'],35);self.assertEqual(main[-1]['source_session_seed_fold_summary']['count'],175)
   calls.clear();sub['predictions'][-1]['values']={**pin,'path':'absent.npy'};put(root/'BAD.json',sub);result=score.grade(root/'PUBLIC.json',root/'GOLD.json',root/'BAD.json',loader);self.assertEqual(result['status'],'invalid_submission');self.assertFalse(result['private_numeric_inputs_opened']);self.assertEqual(calls,[])


def public_panel():
 rows=[dict(e,query_count=4,query_ids_sha256=digest([e['id'],'invented'])) for e in contexts()]
 d={'schema':'barista_public_panel_v1','task_id':TASK_ID,'source_protocol_sha256':SOURCE_PROTOCOL_SHA,'contexts':rows,'generation_commitment':'a'*64};d['panel_id']=digest(d);return d

if __name__=='__main__':unittest.main()
