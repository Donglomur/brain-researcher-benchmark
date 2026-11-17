"""Tiny end-to-end projection fixture, entirely invented; no empirical source."""
import hashlib,tempfile,unittest
from pathlib import Path
import h5py,numpy as np
from test_nwb_input import fixture,strings,descriptor
from prepare import build_one
import nwb_input

def complete_fixture(path,extra_query=False):
 fixture(path)
 with h5py.File(path,'r+') as f:
  f['identifier']='fake-session'
  for family,extra in nwb_input.FAMILY_EXTRA.items():
   del f['intervals/'+family+'_presentations'];g=f.create_group('intervals/'+family+'_presentations')
   n=30 if family=='drifting_gratings' else 20
   offset={'drifting_gratings':10,'gabors':410,'flashes':710,'static_gratings':1010}[family];t=offset+np.arange(n)*10.
   for field in nwb_input.BASE_FIELDS|extra:
    if field=='id':g[field]=np.arange(n)
    elif field=='start_time':g[field]=t
    elif field=='stop_time':g[field]=t+(2. if family=='drifting_gratings' else .25)
    elif field=='stimulus_block':g[field]=np.repeat([2.,5.,7.],10) if family=='drifting_gratings' else np.ones(n)
    elif field=='stimulus_name':strings(g,field,[family]*n)
    elif field in ('mask','size','units','color'):strings(g,field,['native']*n)
    elif field=='phase':strings(g,field,['0.0']*n)
    else:g[field]=np.arange(n,dtype=float)%10 if field=='orientation' else np.ones(n)
   strings(g,'tags',['stimulus']*n);g['tags_index']=np.arange(1,n+1);g['timeseries']=np.zeros(n);g['timeseries_index']=np.arange(1,n+1)
  spikes=np.arange(0.1,1300,.1)
  if extra_query:spikes=np.sort(np.concatenate([spikes,np.arange(1010.01,1210.,.03)]))
  del f['units/spike_times'];del f['units/spike_times_index'];f['units/spike_times']=spikes;f['units/spike_times_index']=[len(spikes)]*4
  for name in ('running_speed','running_speed_end_times'):
   g=f['processing/running/'+name];del g['timestamps'];del g['data'];t=np.arange(0.,1300.,.25);g['timestamps']=t+(.25 if name=='running_speed_end_times' else 0);g['timestamps'].attrs['unit']='seconds';g['data']=np.where((t//10).astype(int)%2,6.,0.);g['data'].attrs['unit']='cm/s'
class Preparation(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve();self.path=self.root/'fixture.nwb';complete_fixture(self.path)
 def tearDown(self):self.tmp.cleanup()
 def call(self,task):return build_one(self.path,descriptor(self.path),{'session_id':'fake-session','donor_id':'fake-mouse'},task)
 def test_both_task_geometries_and_public_no_spike_extent(self):
  for task in ('NEURAL-091','NEURAL-092'):
   m,p=self.call(task);self.assertEqual(m['unit_ids'],['101']);self.assertEqual(set(p),{'FIT','VALIDATION','QUERY'});self.assertTrue(all(x.shape[1]==1 for x in p.values()));self.assertTrue(all('spike_start' not in r and 'spike_stop' not in r for r in m['support']['all_unit_records']));self.assertEqual(m['baseline_rates'][0],(sum(int(x) for x in p['FIT'][:,0])+.5)/(len(p['FIT'])*m['exposure_seconds']))
 def test_held_static_activity_never_changes_fit_baseline(self):
  a,ap=self.call('NEURAL-091');self.path.unlink();complete_fixture(self.path,True);b,bp=self.call('NEURAL-091');self.assertEqual(a['baseline_rates'],b['baseline_rates']);np.testing.assert_array_equal(ap['FIT'],bp['FIT']);self.assertFalse(np.array_equal(ap['QUERY'],bp['QUERY']))
 def test_negative_qc_domain_not_admitted(self):
  with h5py.File(self.path,'r+') as f:f['units/isi_violations'][0]=-1.
  with nwb_input.opened(self.path,descriptor(self.path)) as f:
   result=nwb_input.select_units(f);self.assertEqual(result['units'],[]);self.assertIn('invalid_domain_isi_violations',result['all_units'][0]['reasons'])
if __name__=='__main__':unittest.main()
