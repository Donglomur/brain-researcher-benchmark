"""Focused int-metadata/float64-public support-binding controls, generated only.

No full view projection, archive or authentic data read. The original execute
path is exercised through the unchanged strict support guard, then stopped at
the donor-map boundary. Original shuffle identity is separately compared.
"""
import argparse, copy, hashlib, importlib.util
from pathlib import Path
import sys, types, unittest
from unittest.mock import patch
import numpy as np
HERE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(add_help=False);parser.add_argument('--dependency-root',type=Path,default=HERE.parent)
args,rest=parser.parse_known_args();sys.argv=[sys.argv[0],*rest]
spec=importlib.util.spec_from_file_location('_n017_typed_support_core',HERE/'core.py');K=importlib.util.module_from_spec(spec);spec.loader.exec_module(K)
S=K.load_sources(HERE,args.dependency_root);W=S.worker;P=S.programme;C=S.contracts
class Boundary(Exception):pass

def fixture():
 plan={'schema':'NLB017_target_free_planned_support_v2',
  'source_release':{'dandiset':'000128','version':'0.220113.0400','asset_id':'26e85f09-39b7-480f-b337-278a8f034007','raw_bytes':690612247,'raw_sha256':'a27f84f9c31f077011062fd99a6ced199fdf19e656151f056c3c6244a408a3c4'},
  'split_identity':{'path':'original/generated.json','bytes':9,'sha256':hashlib.sha256(b'generated').hexdigest()},
  'shape':{'training':[1721,140,137,45],'query':[574,140,137,45]},'bin_left_edges_ms':list(range(-250,450,5))}
 for axis,size in S.opaque_s03.AXES.items():plan[axis]=[axis+'-%04d'%i for i in range(size)]
 plan['train_condition_ids']=['c%d'%(i%7)for i in range(1721)];plan['eval_condition_ids']=['c%d'%(i%7)for i in range(574)]
 plan['chronological_eval_trial_ids']=plan['eval_trial_ids'][::2]+plan['eval_trial_ids'][1::2]
 public={k:np.asarray(plan[k])for k in (*S.opaque_s03.AXES,'train_condition_ids','eval_condition_ids')}
 public['bin_left_edges_ms']=np.arange(-250,450,5,dtype=np.float64);public['panel_fingerprint']=np.asarray('a'*64)
 return plan,public

class SupportBindingControls(unittest.TestCase):
 def through_guard(self,plan,public,opaque=True):
  body={'public':{'path':'public'},'planned_support':{'path':'planned'},'shuffle_commitment':{'path':'commitment'},'protected_shuffle_seed':{'path':'seed'}}
  if opaque:body['opaque_handoff']={'path':'handoff'}
  inputs=types.SimpleNamespace(read=lambda d,cap:b'g'*32 if d['path']=='seed'else b'generated',json=lambda d:plan if d['path']=='planned'else {})
  outputs=types.SimpleNamespace(write=lambda *a,**k:self.fail('No projection/output is part of this focused test'))
  def stop(*arguments):
   actual=arguments[3]if opaque else arguments[1]
   self.assertIs(actual,plan);self.assertTrue(all(type(v)is int for v in actual['bin_left_edges_ms']))
   if opaque:self.assertIs(arguments[2]['bin_left_edges_ms'],public['bin_left_edges_ms'])
   raise Boundary()
  owner=S.opaque_s03 if opaque else S.views;name='mapping_for_s03'if opaque else'shuffle_map'
  with patch.object(S.arrays,'load_arrays',return_value=dict(public)),patch.object(owner,name,side_effect=stop):
   W.execute({'role':'project_views','body':body},inputs,outputs,lambda e:None)
 def test_actual_integer_metadata_float64_public_passes_strict_guard(self):
  plan,public=fixture();before=C.canonical(plan);grid=public['bin_left_edges_ms'];copygrid=grid.copy()
  self.assertNotEqual(C.canonical(grid.tolist()),C.canonical(plan['bin_left_edges_ms']))
  with self.assertRaises(Boundary):self.through_guard(plan,public)
  self.assertEqual(C.canonical(plan),before);self.assertTrue(np.array_equal(grid,copygrid));self.assertEqual(grid.dtype,np.dtype('<f8'))
 def test_comparison_only_grid_preserves_hash_and_original_donors(self):
  plan,public=fixture();before=C.canonical(plan);seed=b'g'*32
  commitment={'schema':'NLB017_target_free_shuffle_commitment_v2','planned_support_sha256':C.digest(before),'seed_sha256':C.digest(seed),'numpy_version':np.__version__,'rule':copy.deepcopy(P.SHUFFLE_RULE)}
  donor=S.views.shuffle_map(seed,plan,commitment);comp=W._prepared_public_comparison(public,plan)
  self.assertIsNot(comp,public);self.assertIsNot(comp['bin_left_edges_ms'],public['bin_left_edges_ms'])
  for k in public:
   if k!='bin_left_edges_ms':self.assertIs(comp[k],public[k])
  self.assertEqual(C.canonical(comp['bin_left_edges_ms'].tolist()),C.canonical(plan['bin_left_edges_ms']))
  self.assertEqual(C.canonical(plan),before);self.assertEqual(C.digest(before),commitment['planned_support_sha256'])
  self.assertTrue(np.array_equal(S.views.shuffle_map(seed,plan,commitment),donor))
 def test_public_grid_type_shape_and_numeric_mutations_refuse(self):
  plan,public=fixture();grid=public['bin_left_edges_ms']
  mutations=[grid.astype(np.int64),grid.astype(np.float32),grid.astype(bool),grid.astype(str),grid[:-1],grid[::-1],grid.tolist()]
  signed_zero=grid.copy();signed_zero[50]=-0.0;mutations.append(signed_zero)
  for change in (0.5,float('nan'),float('inf')):
   bad=grid.copy();bad[1]=change;mutations.append(bad)
  for value in mutations:
   with self.subTest(type=str(type(value)),dtype=str(getattr(value,'dtype',None))):
    with self.assertRaises(ValueError):W._prepared_public_comparison({**public,'bin_left_edges_ms':value},plan)
 def test_declared_grid_coercions_and_changed_values_refuse(self):
  plan,public=fixture();original=plan['bin_left_edges_ms']
  cases=[[float(x)for x in original],[str(x)for x in original],tuple(original),original[:-1],list(reversed(original))]
  for changed in (True,-244,-244.5):
   values=original.copy();values[1]=changed;cases.append(values)
  for values in cases:
   with self.subTest(values_type=str(type(values))):
    with self.assertRaises(ValueError):W._prepared_public_comparison(public,{**plan,'bin_left_edges_ms':values})
 def test_other_field_canonical_checks_stay_strict(self):
  plan,public=fixture()
  for key in ('train_trial_ids','eval_trial_ids','heldin_unit_ids','heldout_unit_ids','train_condition_ids','eval_condition_ids'):
   bad=dict(public);bad[key]=public[key].copy();bad[key][0]='changed'
   with self.subTest(key=key):
    with self.assertRaisesRegex(ValueError,'exact canonical prepared support'):self.through_guard(plan,bad)
 def test_physical_branch_retains_original_behavior(self):
  plan,public=fixture();public['bin_left_edges_ms']=np.asarray(plan['bin_left_edges_ms'],dtype=np.int64)
  with patch.object(W,'_prepared_public_comparison',side_effect=AssertionError('opaque-only binding')):
   with self.assertRaises(Boundary):self.through_guard(plan,public,opaque=False)
  public['bin_left_edges_ms']=np.asarray(plan['bin_left_edges_ms'],dtype=np.float64)
  with self.assertRaisesRegex(ValueError,'exact canonical prepared support'):self.through_guard(plan,public,opaque=False)

if __name__=='__main__':unittest.main()
