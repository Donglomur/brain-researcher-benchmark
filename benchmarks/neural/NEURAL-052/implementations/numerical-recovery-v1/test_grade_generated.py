import copy,unittest,hashlib,json,tempfile,types,sys
from pathlib import Path
from unittest.mock import patch
import grade
from test_report_contract_generated import design_fixture,complete_fixture
from grade import compare

def report():
 summary={'status':'defined','value':.25,'conditional_concept_bootstrap':{'lower':.1,'upper':.4,'defined_draws':1000,'undefined_draws':0}}
 return {'participants':[{'subject_id':s,'voxel_support':{'V1':100,'IT':200},'roi_metrics':{'macro_primary':{r:{m:copy.deepcopy(summary)for m in('animacy_given_size','size_given_animacy','joint')}for r in('V1','IT')}}}for s in('01','02','03')]}
class Tests(unittest.TestCase):
 def test_exact(self):
  r=report();z=compare(r,r);self.assertTrue(z['full_reconstruction']);self.assertEqual(z['primary_error'],0)
 def test_valid_numeric_alternative(self):
  r=report();a=copy.deepcopy(r);a['participants'][0]['roi_metrics']['macro_primary']['V1']['joint']['value']+=.18
  z=compare(a,r);self.assertFalse(z['full_reconstruction']);self.assertAlmostEqual(z['primary_error'],.01)
 def test_support_not_reward(self):
  r=report();a=copy.deepcopy(r);a['participants'][0]['voxel_support']['V1']=99;z=compare(a,r);self.assertIsNone(z['primary_error']);self.assertFalse(z['full_reconstruction'])
 def test_secondary_mismatch_preserves_primary_error(self):
  r=report();r['secondary_support']=2;a=copy.deepcopy(r);a['secondary_support']=1;z=compare(a,r);self.assertEqual(z['primary_error'],0);self.assertFalse(z['full_reconstruction'])
 def test_null_is_not_zero(self):
  r=report();r['participants'][0]['roi_metrics']['macro_primary']['V1']['joint'].update(status='undefined_voxel_sst',value=None);z=compare(r,r);self.assertIsNone(z['primary_error']);self.assertTrue(z['full_reconstruction'])
 def test_large_numbers(self):
  r=report();a=copy.deepcopy(r)
  for p in a['participants']:
   for v in p['roi_metrics']['macro_primary'].values():
    for s in v.values():s['value']=1e308
  z=compare(a,r);self.assertEqual(z['primary_error'],1e308)
 def test_boolean_not_numeric(self):
  r=report();a=copy.deepcopy(r);a['participants'][0]['roi_metrics']['macro_primary']['V1']['joint']['value']=True;z=compare(a,r);self.assertFalse(z['full_reconstruction']);self.assertIsNone(z['primary_error'])
class BoundaryTests(unittest.TestCase):
 def test_all_candidate_faults_before_numeric_loader(self):
  design=design_fixture();db=json.dumps(design).encode();calls=[]
  def forbidden(*a,**k):calls.append(True);raise AssertionError('numeric loader reached')
  fake=types.SimpleNamespace(load_packet=forbidden)
  with tempfile.TemporaryDirectory()as tmp:
   root=Path(tmp);(root/'private').mkdir();(root/'private/DESIGN.json').write_bytes(db)
   valid=complete_fixture(design);bad=copy.deepcopy(valid);del bad['analysis']['participants'][-1]
   bodies=[b'',b'{"task_id":"NEURAL-052"}',json.dumps(bad).encode()]
   with patch.object(grade,'DESIGN_SHA',hashlib.sha256(db).hexdigest()),patch.dict(sys.modules,{'data_io':fake}):
    for i,b in enumerate(bodies):
     p=root/f'candidate{i}.json';p.write_bytes(b);self.assertEqual(grade.grade_submission(p,root)['status'],'invalid_submission')
   self.assertEqual(calls,[])
if __name__=='__main__':unittest.main()
