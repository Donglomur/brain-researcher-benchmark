"""Generated numerical controls; no authentic arrays or decomposition fitting."""
import importlib.util
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.linalg import orth
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.linear_model import ridge_regression

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('slicetca_producer',HERE.parent/'producer.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
CONDITION_ORDER=(20,22,10,34,18,39,32,5,37,35,26,31)


def small_factors():
 rng=np.random.RandomState(21)
 return {'trial':(rng.rand(2,3),rng.rand(2,4,5)),
         'neuron':(rng.rand(1,4),rng.rand(1,3,5)),
         'time':(rng.rand(1,5),rng.rand(1,3,4))}


def mixed_factors():
 rng=np.random.RandomState(14)
 return {'trial':(rng.rand(12,511),rng.rand(12,182,150)),
         'neuron':(np.empty((0,182)),np.empty((0,511,150))),
         'time':(rng.rand(1,150),rng.rand(1,511,182))}


class Preprocessing(unittest.TestCase):
 def test_filter_reflect_count_to_hz_and_full_neuron_scale(self):
  x=np.zeros((3,2,19),dtype=np.float64)
  x[0,0,0]=1;x[1,0,9]=3;x[2,0,-1]=25
  x[0,1,:]=np.arange(19);x[1,1,:]=np.arange(19)[::-1]*2;x[2,1,10]=50
  original=x.copy();actual,meta=p.preprocess_neural(x)
  kernel=np.exp(-0.5*(np.arange(-8,9)/2)**2);kernel/=kernel.sum()
  smooth=np.empty_like(x)
  for trial in range(3):
   for neuron in range(2):smooth[trial,neuron]=np.convolve(np.pad(x[trial,neuron]*100,(8,8),mode='symmetric'),kernel,mode='valid')
  lower=np.min(smooth,axis=(0,2));span=np.max(smooth,axis=(0,2))-lower
  expected=(smooth-lower[None,:,None])/span[None,:,None]
  np.testing.assert_allclose(actual,expected.astype(np.float32),rtol=2e-7,atol=2e-8)
  np.testing.assert_allclose(meta['minimum_hz'],lower,atol=1e-12)
  np.testing.assert_allclose(meta['range_hz'],span,rtol=1e-14)
  np.testing.assert_array_equal(x,original)
  self.assertEqual(actual.dtype,np.float32)
  self.assertIn('all trials',meta['exposure'])
  self.assertLess(actual[:2,0].max(),0.9) # the held-out-like third trial still sets source scaling
  nearest=gaussian_filter1d(x*100,2,axis=2,mode='nearest')
  self.assertGreater(abs(nearest[0,0,0]-smooth[0,0,0]),1)

 def test_undefined_neuron_scale_and_negative_counts_rejected(self):
  with self.assertRaisesRegex(ValueError,'scaling'):p.preprocess_neural(np.ones((2,2,20)))
  with self.assertRaisesRegex(ValueError,'negative'):p.preprocess_neural(-np.ones((2,2,20)))


class AuthenticatedIntake(unittest.TestCase):
 def test_six_tiny_numeric_originals_hash_shape_finite_and_symlink_guards(self):
  with tempfile.TemporaryDirectory(dir=HERE) as temporary:
   root=Path(temporary);pins={};expected={}
   def store(name,value,shape=None):
    path=root/name
    with path.open('wb') as stream:np.save(stream,value,allow_pickle=False)
    pins[name]=(path.stat().st_size,hashlib.sha256(path.read_bytes()).hexdigest(),value.shape if shape is None else shape)
   for i,name in enumerate(p.ORIGINALS):
    expected[name]=np.array([0.,1.]) if name=='condition.npy' else np.arange(6,dtype=float).reshape(2,3)+i
    store(name,expected[name])
   with mock.patch.object(p,'ORIGINALS',pins):
    actual=p.load_originals(root)
    self.assertEqual(set(actual),set(expected))
    for name,value in expected.items():np.testing.assert_array_equal(actual[name],value)
    first=next(iter(pins));good_pin=pins[first]
    pins[first]=(good_pin[0],'0'*64,good_pin[2])
    with mock.patch.object(p.np,'load') as decode:
     with self.assertRaisesRegex(ValueError,'source hash'):p.load_originals(root)
     decode.assert_not_called()
    pins[first]=good_pin
    invalid=expected[first].copy();invalid[0,0]=np.nan;store(first,invalid)
    with self.assertRaisesRegex(ValueError,'nonfinite'):p.load_originals(root)
    store(first,expected[first],shape=(3,2))
    with self.assertRaisesRegex(ValueError,'source shape/type'):p.load_originals(root)
    store(first,expected[first])
    path=root/first;backup=root/'generated-backup.npy';path.rename(backup);path.symlink_to(backup)
    with self.assertRaises(OSError):p.load_originals(root)
    path.unlink();backup.rename(path)
    store('condition.npy',np.array([0.,0.5]))
    with self.assertRaisesRegex(ValueError,'noninteger'):p.load_originals(root)


class Reconstructions(unittest.TestCase):
 def test_named_slice_axes_and_partial_component_selection(self):
  f=small_factors();expected=np.zeros((3,4,5))
  for i in range(3):
   for j in range(4):
    for k in range(5):
     expected[i,j,k]=sum(f['trial'][0][r,i]*f['trial'][1][r,j,k] for r in range(2))+f['neuron'][0][0,j]*f['neuron'][1][0,i,k]+f['time'][0][0,k]*f['time'][1][0,i,j]
  np.testing.assert_allclose(p.slice_reconstruction(f,(3,4,5)),expected,atol=1e-15)
  parts=[p.slice_reconstruction(f,(3,4,5),modes=(mode,)) for mode in f]
  np.testing.assert_allclose(sum(parts),expected,atol=1e-15)
  selected=p.slice_reconstruction(f,(3,4,5),components={'trial':[1]})
  np.testing.assert_allclose(selected,np.multiply.outer(f['trial'][0][1],f['trial'][1][1]),atol=1e-15)
  with self.assertRaises(ValueError):p.slice_reconstruction(f,(3,4,5),components={'trials':[0]})
  with self.assertRaises(ValueError):p.slice_reconstruction(f,(3,4,5),components={'trial':[0,0]})

 def test_cp_outer_products_and_rank_mismatch(self):
  f={'trial':np.array([[1.,2.],[3.,4.]]),'neuron':np.array([[1.,2.,3.],[0.,1.,2.]]),'time':np.array([[1.,2.,3.,4.],[5.,6.,7.,8.]])}
  expected=sum(np.multiply.outer(np.multiply.outer(f['trial'][r],f['neuron'][r]),f['time'][r]) for r in range(2))
  np.testing.assert_array_equal(p.cp_reconstruction(f),expected)
  f['time']=f['time'][:1]
  with self.assertRaises(ValueError):p.cp_reconstruction(f)

 def test_rejects_negative_exported_factors(self):
  f=small_factors();f['trial'][0][0,0]=-1
  with self.assertRaisesRegex(ValueError,'nonnegative'):p.slice_reconstruction(f,(3,4,5))

 def test_callback_cannot_rewrite_source_rank_roster(self):
  def corrupt(neural,**kwargs):
   kwargs['model_spec']['ranks']['trial']=1
   return {'factors':{'trial':(np.ones((1,511)),np.ones((1,182,150))),
    'neuron':(np.empty((0,182)),np.empty((0,511,150))),
    'time':(np.ones((1,150)),np.ones((1,511,182)))}}
  with self.assertRaisesRegex(ValueError,'rank'):
   p.materialize_model(np.zeros((511,182,150),dtype=np.float32),'mixed_slice12_1',corrupt,seed=0,optimizer_spec={'kind':'generated control'},mask_identity='generated',reference_identity='generated')
  self.assertEqual(p.MODEL_ROSTER['mixed_slice12_1']['ranks'],{'trial':12,'neuron':0,'time':1})

 def test_mixed_callback_exports_distinct_full_and_partial_reconstructions(self):
  factors={'trial':(np.full((12,511),2.),np.full((12,182,150),3.)),
   'neuron':(np.empty((0,182)),np.empty((0,511,150))),
   'time':(np.full((1,150),4.),np.full((1,511,182),5.))}
  recipe={'phase':{'rate':0.02}}
  def generated_callback(neural,**kwargs):
   kwargs['optimizer_spec']['phase']['rate']=999
   return {'factors':factors}
  result=p.materialize_model(np.broadcast_to(np.array(0.),(511,182,150)),
   'mixed_slice12_1',generated_callback,seed=0,optimizer_spec=recipe,mask_identity='generated',reference_identity='generated')
  self.assertEqual(recipe,{'phase':{'rate':0.02}})
  partials=result['partial_reconstructions']
  self.assertEqual(set(partials),{'mixed_full','mixed_trial_only','mixed_time_only'})
  self.assertTrue(np.all(partials['mixed_trial_only']==72.))
  self.assertTrue(np.all(partials['mixed_time_only']==20.))
  self.assertTrue(np.all(partials['mixed_full']==92.))
  self.assertIs(partials['mixed_full'],result['reconstruction'])
  self.assertFalse(result['source_fit_authenticated'])


class Decoders(unittest.TestCase):
 def test_ols_affine_target_and_ridge_penalizes_appended_constant(self):
  x=np.array([[-2.,0.],[-1.,2.],[0.,-3.],[1.,1.],[3.,4.]])
  weight=np.array([[2.,-0.5],[-1.,3.]]);bias=np.array([7.,-4.]);y=x@weight.T+bias
  ols=p.fit_linear(x,y,recipe='paper_ols0')
  np.testing.assert_allclose(ols['weight'],weight,atol=1e-14)
  np.testing.assert_allclose(ols['bias'],bias,atol=1e-14)
  ridge=p.fit_linear(x,y,recipe='source_code_ridge1')
  reference=ridge_regression(np.column_stack((x,np.ones(len(x)))),y,alpha=1)
  np.testing.assert_allclose(ridge['weight'],reference[:,:-1],atol=2e-14)
  np.testing.assert_allclose(ridge['bias'],reference[:,-1],atol=2e-14)
  constant=p.fit_linear(np.zeros((4,1)),np.tile([10.,-5.],(4,1)),recipe='source_code_ridge1')
  np.testing.assert_allclose(constant['bias'],[8.,-4.],atol=1e-14)
  self.assertTrue(constant['bias_penalized'])

 def test_true_start_displacements_without_seconds_multiplier(self):
  rng=np.random.RandomState(4);x=rng.randn(7,3,2)
  w=np.array([[2.,-1.],[0.5,3.]]);b=np.array([0.3,-0.7]);initial=np.array([[10.,20.],[-3.,8.],[100.,-50.]])
  y=np.concatenate((initial[None],initial[None]+np.cumsum(x[:-1]@w.T+b,axis=0)))
  model=p.fit_velocity(x,y,recipe='paper_ols0');prediction=p.predict_positions(model,x,initial)
  np.testing.assert_allclose(prediction,y,atol=5e-14)
  np.testing.assert_array_equal(prediction[0],initial)
  self.assertEqual(prediction.shape,(7,3,2))

 def test_five_fold_twenty_schedule_preserves_curved_remainder(self):
  plan=p.endpoints.source_schedule('curved');self.assertEqual(plan['test'].shape,(20,5,49))
  self.assertEqual(plan['train'].shape,(20,5,197));rng=np.random.RandomState(0)
  for repeat in range(20):
   permutation=rng.permutation(246)+265
   np.testing.assert_array_equal(plan['permutations'][repeat],permutation)
   for fold in range(5):
    self.assertIn(permutation[-1],plan['train'][repeat,fold])
    self.assertNotIn(permutation[-1],plan['test'][repeat,fold])

 def test_averaged_half_uses_only_its_reach_condition_labels(self):
  t=np.arange(8.)[:,None,None];trial=np.arange(12.)[None,:,None]
  x=np.concatenate((t+trial,t-trial),axis=2)
  movement=np.concatenate((t*(trial+1),-t*(trial+2)),axis=2)
  angles=np.array([0,0,0,0,1,1,2,2,3,3,3,3])
  out=p.averaged_half(x,movement,angles,np.array([0,4]),np.array([1,5]),recipe='paper_ols0')
  np.testing.assert_array_equal(out['condition_labels'],[0,1])
  with self.assertRaisesRegex(ValueError,'condition is missing'):
   p.averaged_half(x,movement,angles,np.array([0,1]),np.array([4,5]),recipe='paper_ols0')

 def test_condition_average_cumulative_shuffle_and_odd_halves(self):
  rng=np.random.RandomState(3);x=rng.randn(80,511,3);y=np.cumsum(rng.randn(80,511,2),axis=0)
  movement=np.zeros((150,511,2));movement[65:-5]=y
  angles=np.r_[np.arange(265)%2,2+np.arange(246)%2]
  with mock.patch.object(p.endpoints,'source_windows',return_value=(x,y)):
   result=p.condition_average_control(x,movement,angles,recipe='source_code_ridge1')
  rng=np.random.RandomState(0)
  for _ in range(20):rng.permutation(246)
  for condition,(lo,hi) in p.endpoints.CONDITIONS.items():
   order=np.arange(lo,hi);half=(hi-lo)//2;rows=result['conditions'][condition]['rows']
   self.assertEqual(len(rows),20)
   for pair in rows:
    order=order[rng.permutation(len(order))]
    for entry,current in zip(pair,(order,order[::-1])):
     np.testing.assert_array_equal(entry['train_indices'],current[:half])
     np.testing.assert_array_equal(entry['test_indices'],current[half:])
   self.assertEqual(result['conditions'][condition]['r2'].shape,(20,2,2))
  first=result['conditions']['straight']['rows'][0]
  self.assertEqual((len(first[0]['train_indices']),len(first[0]['test_indices'])),(132,133))
  self.assertIn('not trial-wise five-fold',result['conditions']['straight']['independent_unit'])


class Components(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.factors=mixed_factors();cls.condition=np.resize(np.array(CONDITION_ORDER[::-1]),511)
  trial=np.arange(511,dtype=float);cls.targets=np.column_stack((np.sin(trial/13),np.cos(trial/17)))

 def result(self,**kwargs):
  options={'recipe':'source_code_ridge1','region_map':'source_code_92_90','target_projection_route':'source_raw_factor'};options.update(kwargs)
  return p.component_results(self.factors,self.condition,self.targets,**options)

 def test_source_condition_order_raw_factor_gauges_and_region_discrepancy(self):
  result=self.result()
  order=np.concatenate([np.flatnonzero(self.condition[lo:hi]==label)+lo for lo,hi in ((0,265),(265,511)) for label in CONDITION_ORDER])
  np.testing.assert_array_equal(result['condition_sorted_trial_indices'],order)
  np.testing.assert_array_equal(result['trial_weights'],self.factors['trial'][0])
  np.testing.assert_array_equal(result['trial_slices'],self.factors['trial'][1])
  np.testing.assert_array_equal(result['time_vector'],self.factors['time'][0])
  self.assertEqual(result['source_code_region_counts'],{'M1':92,'PMd':90})
  self.assertEqual(result['paper_region_counts'],{'M1':90,'PMd':92})
  raw=self.factors['time'][1][0]
  np.testing.assert_allclose(result['condition_correlations']['source_code_M1'],np.corrcoef(raw[order,:92]),atol=1e-14)
  for lo,hi,key in [(0,265,'straight'),(265,511,'curved')]:
   target=self.targets-self.targets.mean(axis=0);design=np.column_stack((raw[lo:hi],np.ones(hi-lo)))
   coefficients=ridge_regression(design,target[lo:hi],alpha=1)
   np.testing.assert_allclose(result['target_projections'][key]['prediction'],design@coefficients.T,rtol=2e-11,atol=2e-11)
   self.assertFalse(result['target_projections'][key]['paper_fivefold_target_projection_reproduced'])

 def test_paper_partial_average_requires_explicit_bins_and_ols(self):
  with self.assertRaisesRegex(ValueError,'requires OLS'):self.result(target_projection_route='paper_partial_average_ols',preparatory_time_indices=[0,1])
  with self.assertRaisesRegex(ValueError,'source-bin'):self.result(target_projection_route='paper_partial_average_ols',recipe='paper_ols0',preparatory_time_indices=None)
  f={k:(v.copy(),s.copy()) for k,(v,s) in self.factors.items()};f['time'][0][0,:2]=0
  result=p.component_results(f,self.condition,self.targets,recipe='paper_ols0',region_map='paper_counts_unbound',target_projection_route='paper_partial_average_ols',preparatory_time_indices=[0,1])
  centered=self.targets-self.targets.mean(axis=0)
  for key,(lo,hi) in p.endpoints.CONDITIONS.items():
   expected=np.broadcast_to(centered[lo:hi].mean(axis=0),(hi-lo,2))
   np.testing.assert_allclose(result['target_projections'][key]['prediction'],expected,atol=1e-14)
  self.assertEqual(set(result['condition_correlations']),{'all'})
  self.assertFalse(result['preparatory_physical_window_authenticated'])

 def test_source_subspace_no_intercept_and_whole_span_orth_are_distinct(self):
  raw=self.factors['time'][1][0,265:]
  labels=np.array([0 if c in (5,18,20,22,26,35,39) else 1 for c in self.condition[265:]])
  target=(self.targets-self.targets.mean(axis=0))[265:]
  lda=LinearDiscriminantAnalysis().fit(raw,labels).coef_
  target_axes=np.linalg.lstsq(raw,target,rcond=None)[0].T
  source_axes=np.concatenate((lda,target_axes),axis=0).T
  actual=p.preparatory_subspace(self.factors,self.condition,self.targets,route='source_default_axes')
  np.testing.assert_allclose(actual['projection_axes'],source_axes,rtol=1e-13,atol=1e-13)
  np.testing.assert_allclose(actual['coordinates'],raw@source_axes,rtol=1e-13,atol=1e-13)
  np.testing.assert_array_equal(actual['source_class_labels'],labels)
  alternate=p.preparatory_subspace(self.factors,self.condition,self.targets,route='source_orthogonal_span')
  expected_orth=orth(source_axes)
  np.testing.assert_allclose(alternate['projection_axes']@alternate['projection_axes'].T,expected_orth@expected_orth.T,atol=1e-13)
  self.assertFalse(actual['paper_target_axes_orthogonalization_reproduced'])
  self.assertFalse(alternate['paper_target_axes_orthogonalization_reproduced'])

 def test_result_family_keeps_absent_comparators_unavailable(self):
  prepared={'neural':np.broadcast_to(np.array(0.),(511,182,150)),
   'movement':None,'target_angle':None,'condition':None,'target_pos':None}
  with mock.patch.object(p,'repeated_decoding',return_value={'generated':'decoder'}),mock.patch.object(p,'condition_average_control',return_value={'generated':'average'}):
   result=p.source_result_family(prepared,{},recipe='source_code_ridge1',region_map='source_code_92_90',target_projection_route='source_raw_factor',subspace_route='source_default_axes')
  self.assertEqual(set(result['single_trial_decoding']),{'raw'})
  self.assertEqual(set(result['unavailable_required_models']),{'neuron_nmf12','trial_nmf12','tca12','mixed_slice12_1','lfads'})
  self.assertFalse(result['paper_reproduction_admitted'])
  self.assertFalse(result['paper_improvement_admitted'])
  self.assertIsNone(result['component_results'])
  self.assertIsNone(result['preparatory_subspace'])

 def test_result_family_rejects_mixed_full_partial_mismatch_before_decoding(self):
  shape=(511,182,150)
  prepared={'neural':np.broadcast_to(np.array(0.),shape),
   'movement':None,'target_angle':None,'condition':None,'target_pos':None}
  factors={'trial':(np.ones((12,511)),np.ones((12,182,150))),
   'neuron':(np.empty((0,182)),np.empty((0,511,150))),
   'time':(np.ones((1,150)),np.ones((1,511,182)))}
  model={'reconstruction':np.broadcast_to(np.array(99.),shape),'factors':factors}
  with mock.patch.object(p,'repeated_decoding') as decoder,mock.patch.object(p,'condition_average_control') as averaged:
   with self.assertRaisesRegex(ValueError,'reconstruction'):
    p.source_result_family(prepared,{'mixed_slice12_1':model},recipe='source_code_ridge1',region_map='source_code_92_90',target_projection_route='source_raw_factor',subspace_route='source_default_axes')
   decoder.assert_not_called();averaged.assert_not_called()
  factors['trial']=(factors['trial'][0][:-1],factors['trial'][1][:-1])
  with mock.patch.object(p,'repeated_decoding') as decoder:
   with self.assertRaisesRegex(ValueError,'rank'):
    p.source_result_family(prepared,{'mixed_slice12_1':model},recipe='source_code_ridge1',region_map='source_code_92_90',target_projection_route='source_raw_factor',subspace_route='source_default_axes')
   decoder.assert_not_called()


if __name__=='__main__':unittest.main(verbosity=2)
