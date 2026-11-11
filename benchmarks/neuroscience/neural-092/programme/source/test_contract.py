"""Invented investigation/control fixture; no authentic array access."""
import json,tempfile,unittest
from pathlib import Path
import numpy as np
from analysis import reconstruct,numeric_report,PAIR_KEYS
from score import admit_candidate,evaluate
from state_core import AREAS

def fixture():
 rows=[]
 for i,phase in enumerate(('FIT','VALIDATION','QUERY','QUERY')):
  rows.append({'id':str(i),'onset':i*10.,'condition_key':'same stimulus','block':2 if phase=='FIT' else 5 if phase=='VALIDATION' else 7,'run_bin':'REST' if i%2==0 else 'RUN','pupil_bin':'MISSING','split':phase})
 meta={'unit_ids':['a','b'],'mouse_id':'m','rows':rows,'baseline_rates':[1.,1.],'areas':['VISp','VISl'],'exposure_seconds':1.9,'unit_metadata':[{'unit_id':x,'area':area,'FITbaseline':1.,'presence_ratio':.99,'isi_violations':.1,'amplitude_cutoff':.05} for x,area in zip(('a','b'),('VISp','VISl'))]}
 return meta,np.array([[1,3],[3,1]],dtype=np.int64)
class Contract(unittest.TestCase):
 def test_observed_reconstruction_not_hidden_prediction(self):
  m,c=fixture();truth=reconstruct(m,c);answer=numeric_report(truth);result=evaluate({'s':answer},{'s':m},lambda sid:c)
  self.assertTrue(result['admitted']);self.assertIsNone(result['explanatory_gain']);self.assertFalse(result['causal_effect_identified'])
  self.assertLess(result['primary_running_reconstruction_error']['primary_mean_absolute_error']['value'],1e-14)
  self.assertEqual(result['separate_pupil_reconstruction_error']['primary_mean_absolute_error']['status'],'undefined_required_session')
 def test_target_sign_change_requires_changed_answer(self):
  m,c=fixture();answer=numeric_report(reconstruct(m,c));r=evaluate({'s':answer},{'s':m},lambda sid:c[::-1]);self.assertGreater(r['primary_running_reconstruction_error']['primary_mean_absolute_error']['value'],1.)
 def test_no_selected_area_drop(self):
  m,c=fixture();a=numeric_report(reconstruct(m,c));a['running']['areas'].pop('VISam')
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'x';p.write_text(json.dumps({'schema':'neuropixels_state_submission_v1','task_id':'NEURAL-092','sessions':{'s':a}}))
   with self.assertRaises(ValueError):admit_candidate(p,['s'])
 def test_unsupported_control_null_required(self):
  m,c=fixture();a=numeric_report(reconstruct(m,c));a['pupil']['matched']['VISp|VISl']=0.
  with self.assertRaises(ValueError):evaluate({'s':a},{'s':m},lambda sid:c)
 def test_unit_counts_retained_separately(self):
  m,c=fixture();t=reconstruct(m,c)['running'];self.assertEqual(t['areas'].unit_counts['VISp'],1);self.assertEqual(t['areas'].unit_counts['VISam'],0);self.assertEqual(len(t['matched']),15)
if __name__=='__main__':unittest.main()
