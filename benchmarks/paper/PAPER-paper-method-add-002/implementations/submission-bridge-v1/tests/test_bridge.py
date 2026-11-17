"""Generated complete packet controls; no fits or authentic bank access."""
import copy
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock
import numpy as np

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('slicetca_bridge_review',HERE.parent/'bridge.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
CONDITIONS=(20,22,10,34,18,39,32,5,37,35,26,31)


def fixture_bank():
 t=np.arange(150.)[:,None];trial=np.arange(511.)[None,:]
 movement=np.stack((np.broadcast_to(t,(150,511)),2*t+trial/100),axis=-1)
 return {'manifest_sha256':'b'*64,'neural':np.broadcast_to(np.linspace(0,1,150)[None,None,:],b.SHAPE),
  'movement':movement,'target_angle':np.resize(np.arange(12,dtype=float),511),
  'target_pos':np.column_stack((np.arange(511.),np.arange(511.)/2)),
  'condition':np.resize(np.array(CONDITIONS),511),'source_trial_indices':np.arange(511)}


def fixture_plan(mask):
 return {'task_id':b.TASK,'bank_manifest_sha256':'b'*64,'evaluation_profile_sha256':'e'*64,'recipe':'source_code_ridge1',
  'component_routes':{'region_map':'source_code_92_90','target_projection_route':'source_raw_factor','subspace_route':'source_default_axes','preparatory_time_indices':None},
  'reconstruction_cells':[{'id':'generated_cell','source_result_id':'generated_source_cell','rank_specification':{'slice':[12,0,1]},'seed':0,'cut_bins':2,'training_mask_sha256':b.mask_digest(mask)}],
  'reconstruction_roster_identity':'a'*64}


def fixture_components(bank):
 weights=np.ones((12,511));slices=np.zeros((12,182,150))
 for n in range(182):slices[:,n,n%150]=1+np.arange(12)
 preparatory=(np.arange(511)[:,None]%13+np.arange(182)[None,:]%17)/30
 order=np.concatenate([np.flatnonzero(bank['condition'][lo:hi]==label)+lo for lo,hi in ((0,265),(265,511)) for label in CONDITIONS])
 components={'trial_weights':weights,'trial_slices':slices,'time_vector':np.ones((1,150)),
  'preparatory_trial_neuron_slice':preparatory,'condition_sorted_trial_indices':order,
  'trial_slice_peak_bin_by_neuron':slices.argmax(axis=2),'first_supplied_trial_component_neuron_order':np.argsort(slices[0].argmax(axis=1)),
  'condition_correlations':{'all':np.corrcoef(preparatory[order]),'source_code_M1':np.corrcoef(preparatory[order,:92]),'source_code_PMd':np.corrcoef(preparatory[order,92:])},
  'target_projections':{'straight':{'prediction':np.zeros((265,2))},'curved':{'prediction':np.zeros((246,2))}},
  'region_mapping':'source_code_92_90','target_projection_route':'source_raw_factor','preparatory_time_indices':None}
 axes=np.eye(182,3)
 sub={'route':'source_default_axes','coordinates':preparatory[265:]@axes,'projection_axes':axes,
  'source_class_labels':np.where(np.isin(bank['condition'][265:],(5,18,20,22,26,35,39)),0,1),
  'source_trial_indices':np.arange(265,511)}
 return components,sub


def fixture_family(bank,error):
 window=bank['movement'][65:-5];per_reach={}
 for reach in b.e.CONDITIONS:
  indices=b.e.source_schedule(reach)['test']
  prediction=np.stack([np.stack([window[:,ids] for ids in repeat]) for repeat in indices])
  prediction[:,:,1:]+=error
  per_reach[reach]={'prediction':prediction,'test_indices':indices,'summary':{'mean_trial_fold_repeat_r2':123456789.}}
 single={model:{'recipe':'source_code_ridge1','conditions':per_reach} for model in b.MODELS}
 averaged={'recipe':'source_code_ridge1','conditions':{}}
 schedules=b.average_schedule()
 for reach,(lo,hi) in b.e.CONDITIONS.items():
  labels=np.unique(bank['target_angle'][lo:hi]);rows=[]
  for repeat in range(20):
   pair=[]
   for half in range(2):
    train=schedules[reach]['train'][repeat,half];test=schedules[reach]['test'][repeat,half]
    target=np.stack([window[:,test[bank['target_angle'][test]==label]].mean(axis=1) for label in labels],axis=1)
    prediction=target.copy();prediction[1:]+=error
    pair.append({'condition_labels':labels,'prediction':prediction,'target':np.full_like(target,999.),'r2':np.full(12,123456789.),'train_indices':train,'test_indices':test})
   rows.append(pair)
  averaged['conditions'][reach]={'rows':rows}
 components,sub=fixture_components(bank)
 return {'single_trial_decoding':single,'raw_condition_average_control':averaged,'component_results':components,'preparatory_subspace':sub}


def declaration(role):
 return {'role':role,'information_condition':'operator_reference' if role=='operator_reference' else 'paper_data',
  'analysis_code_sha256':'c'*64,'analysis_config_sha256':'d'*64,'reference_identity':'generated_operator_reference',
  'reference_kind':'fresh_source_calibration' if role=='operator_reference' else 'candidate'}


def rehash_manifest(root,manifest):
 path=root/'MANIFEST.json';path.write_bytes(b.canonical(manifest));return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_array(root,key,value,*,record_shape=None):
 manifest=json.loads((root/'MANIFEST.json').read_text());row=manifest['files'][key]
 stream=io.BytesIO();np.save(stream,value,allow_pickle=False)
 payload=gzip.compress(stream.getvalue(),compresslevel=1,mtime=0);(root/row['file']).write_bytes(payload)
 row.update({'bytes':len(payload),'sha256':hashlib.sha256(payload).hexdigest(),'dtype':value.dtype.str})
 if record_shape is not None:row['shape']=list(record_shape)
 return rehash_manifest(root,manifest)


class NativeSubmission(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temporary=tempfile.TemporaryDirectory(dir=HERE);cls.root=Path(cls.temporary.name)
  cls.bank=fixture_bank();time_mask=np.ones(150,dtype=np.uint8);time_mask[60:90]=0
  cls.mask=np.broadcast_to(time_mask[None,None,:],b.SHAPE);cls.plan=fixture_plan(cls.mask)
  cls.families={};cls.receipts={}
  for role,error in [('operator_reference',2.),('submission',1.)]:
   family=fixture_family(cls.bank,error);cls.families[role]=family
   cls.receipts[role]=b.write_packet(family,cls.root/role,plan=cls.plan,declaration=declaration(role),reconstruction_predictions={'generated_cell':cls.bank['neural']+error})
 @classmethod
 def tearDownClass(cls):cls.temporary.cleanup()

 def packet(self,role):return b.Packet(self.root/role,self.receipts[role]['manifest_sha256'],self.plan)

 def copied_packet(self):
  temporary=tempfile.TemporaryDirectory(dir=HERE);path=Path(temporary.name)/'copy'
  shutil.copytree(self.root/'submission',path)
  self.addCleanup(temporary.cleanup);return path

 def test_complete_roundtrip_recomputes_all_paired_metrics_without_scalar_trust(self):
  reference=self.packet('operator_reference');candidate=self.packet('submission')
  report=b.comparison(reference,candidate,self.bank,{'generated_cell':self.mask})
  self.assertEqual(report['reference_packet_manifest_sha256'],self.receipts['operator_reference']['manifest_sha256'])
  self.assertEqual(report['submission_packet_manifest_sha256'],self.receipts['submission']['manifest_sha256'])
  self.assertEqual(report['producer_sha256'],b.PRODUCER_SHA)
  self.assertEqual(report['endpoints_sha256'],hashlib.sha256(Path(b.e.__file__).read_bytes()).hexdigest())
  self.assertEqual(len(report['canonical_findings']),14)
  self.assertEqual(len(report['mixed_companion_findings']),4)
  self.assertEqual(set(report['reconstruction_cells']),{'generated_cell'})
  fixed={name for name,row in report['canonical_findings'].items() if row['comparison_role']=='fixed_control'}
  self.assertEqual(fixed,{'fig2_raw_straight_trajectory_r2','fig2_raw_curved_trajectory_r2','fig2_condition_average_straight_trajectory_r2','fig2_condition_average_curved_trajectory_r2'})
  for name,row in report['canonical_findings'].items():
   if name in fixed:self.assertEqual(row['improvement']['claim_role'],'diagnostic_only')
   else:self.assertEqual(row['comparison_role'],'method_result')
  expected_gain=474/213300
  for row in list(report['canonical_findings'].values())+list(report['mixed_companion_findings'].values()):
   self.assertAlmostEqual(row['reference'],1-632/213300,places=12)
   self.assertAlmostEqual(row['submission'],1-158/213300,places=12)
   self.assertAlmostEqual(row['improvement']['directional_delta'],expected_gain,places=12)
   self.assertEqual(row['reproduction']['decision'],'unavailable');self.assertEqual(row['improvement']['decision'],'unavailable')
  reconstruction=report['reconstruction_cells']['generated_cell']
  self.assertAlmostEqual(reconstruction['reference']['source_cv_root_error'],2,places=12)
  self.assertAlmostEqual(reconstruction['submission']['source_cv_root_error'],1,places=12)
  self.assertAlmostEqual(reconstruction['improvement']['directional_rmse_gain'],1,places=12)
  self.assertEqual(reconstruction['reference']['heldout_entries_after_trim'],511*182*26)
  self.assertTrue(all(v=='unavailable' for v in report['scientific_decisions'].values()))
  self.assertIn('incomplete',report['independent_computation_verification'])
  self.assertEqual(report['private_submission_details']['fig2_raw_straight_trajectory_r2']['r2'].shape,(20,5,53))
  self.assertEqual(report['private_submission_details']['fig2_condition_average_straight_trajectory_r2']['r2'].shape,(20,2,12))

 def test_cumulative_half_schedule_preserves_middle_test_only_trial(self):
  schedule=b.average_schedule();rng=np.random.RandomState(0)
  for _ in range(20):rng.permutation(246)
  order=np.arange(265)
  for repeat in range(20):
   order=order[rng.permutation(265)];middle=order[132]
   for half,current in enumerate((order,order[::-1])):
    np.testing.assert_array_equal(schedule['straight']['train'][repeat,half],current[:132])
    np.testing.assert_array_equal(schedule['straight']['test'][repeat,half],current[132:])
    self.assertNotIn(middle,schedule['straight']['train'][repeat,half]);self.assertIn(middle,schedule['straight']['test'][repeat,half])

 def test_writer_requires_complete_models_and_cell_roster(self):
  family=copy.deepcopy(self.families['submission']);family['single_trial_decoding'].pop('lfads')
  with self.assertRaisesRegex(ValueError,'roster'):b.collect_arrays(family,self.plan,{'generated_cell':self.bank['neural']})
  with self.assertRaisesRegex(ValueError,'roster'):b.collect_arrays(self.families['submission'],self.plan,{})

 def test_writer_rejects_invalid_finite_dtype_and_split_payloads(self):
  for kind in ('nan','dtype','split'):
   with self.subTest(kind=kind):
    family=copy.deepcopy(self.families['submission'])
    if kind=='nan':family['component_results']['trial_weights'][0,0]=np.nan
    elif kind=='dtype':family['component_results']['trial_weights']=np.ones((12,511),dtype=np.float16)
    else:family['raw_condition_average_control']['conditions']['straight']['rows'][0][0]['test_indices']=np.zeros(133,dtype=np.int64)
    with self.assertRaises(ValueError):b.collect_arrays(family,self.plan,{'generated_cell':self.bank['neural']})

 def test_packet_plan_hash_and_post_construction_content_change_are_rejected(self):
  altered=copy.deepcopy(self.plan);altered['evaluation_profile_sha256']='f'*64
  with self.assertRaisesRegex(ValueError,'plan'):b.Packet(self.root/'submission',self.receipts['submission']['manifest_sha256'],altered)
  root=self.copied_packet();packet=b.Packet(root,self.receipts['submission']['manifest_sha256'],self.plan)
  key='components/time_vector';path=root/packet.manifest['files'][key]['file'];payload=bytearray(path.read_bytes());payload[-1]^=1;path.write_bytes(payload)
  with self.assertRaisesRegex(ValueError,'changed'):packet.get(key)

 def test_manifest_is_parsed_from_the_exact_hashed_bytes(self):
  root=self.copied_packet();original_hash=b.p.file_hash
  def swap_after_hash(path):
   result=original_hash(path)
   if Path(path).name=='MANIFEST.json':
    changed=json.loads(Path(path).read_text());changed['declaration']['analysis_code_sha256']='9'*64
    Path(path).write_bytes(b.canonical(changed))
   return result
  with mock.patch.object(b.p,'file_hash',side_effect=swap_after_hash):
   packet=b.Packet(root,self.receipts['submission']['manifest_sha256'],self.plan)
  self.assertEqual(packet.manifest['declaration']['analysis_code_sha256'],'c'*64)

 def test_packet_keeps_independent_snapshot_of_operator_plan(self):
  plan=copy.deepcopy(self.plan)
  packet=b.Packet(self.root/'submission',self.receipts['submission']['manifest_sha256'],plan)
  plan['evaluation_profile_sha256']='9'*64
  plan['reconstruction_cells'][0]['seed']=999
  self.assertEqual(packet.plan['evaluation_profile_sha256'],'e'*64)
  self.assertEqual(packet.plan['reconstruction_cells'][0]['seed'],0)

 def test_post_construction_symlink_is_rejected(self):
  root=self.copied_packet();packet=b.Packet(root,self.receipts['submission']['manifest_sha256'],self.plan)
  key='components/time_vector';path=root/packet.manifest['files'][key]['file'];backup=root/'replacement';path.rename(backup);path.symlink_to(backup)
  with self.assertRaises(OSError):packet.get(key)

 def test_header_shape_forgery_rejected_before_numeric_array_use(self):
  root=self.copied_packet();key='components/time_vector'
  manifest_hash=replace_array(root,key,np.ones((1,149)),record_shape=(1,150))
  packet=b.Packet(root,manifest_hash,self.plan)
  with self.assertRaisesRegex(ValueError,'shape/dtype'):packet.get(key)

 def test_nonfinite_packet_data_cannot_bypass_writer_validation(self):
  root=self.copied_packet();value=np.ones((1,150));value[0,0]=np.inf
  manifest_hash=replace_array(root,'components/time_vector',value)
  packet=b.Packet(root,manifest_hash,self.plan)
  with self.assertRaisesRegex(ValueError,'finite'):packet.get('components/time_vector')

 def test_operator_mask_and_bank_identity_fail_before_metric_scoring(self):
  packet=self.packet('submission');wrong=self.mask.copy();wrong[0,0,0]=0
  with mock.patch.object(b.e,'score_condition') as scoring:
   with self.assertRaisesRegex(ValueError,'mask'):b.score_packet(packet,self.bank,{'generated_cell':wrong})
   scoring.assert_not_called()
  bank=dict(self.bank);bank['manifest_sha256']='f'*64
  with self.assertRaisesRegex(ValueError,'bank'):b.score_packet(packet,bank,{'generated_cell':self.mask})

 def test_operator_mask_loader_exact_roster_and_content_binding(self):
  with tempfile.TemporaryDirectory(dir=HERE) as temporary:
   root=Path(temporary);path=root/'generated_cell.npy'
   with path.open('wb') as handle:np.save(handle,self.mask,allow_pickle=False)
   masks=b.load_operator_masks(root,self.plan)
   self.assertEqual(set(masks),{'generated_cell'})
   self.assertEqual(masks['generated_cell'].shape,b.SHAPE)
   self.assertEqual(b.mask_digest(masks['generated_cell']),self.plan['reconstruction_cells'][0]['training_mask_sha256'])
   del masks
   extra=root/'extra.txt';extra.write_text('generated unexpected file')
   with self.assertRaisesRegex(ValueError,'roster'):b.load_operator_masks(root,self.plan)
   extra.unlink()
   with path.open('r+b') as handle:
    version=np.lib.format.read_magic(handle)
    reader=np.lib.format.read_array_header_1_0 if version==(1,0) else np.lib.format.read_array_header_2_0
    reader(handle);handle.write(b'\x00')
   with self.assertRaisesRegex(ValueError,'content/shape'):b.load_operator_masks(root,self.plan)

 def test_reader_rejects_forged_negative_native_component(self):
  root=self.copied_packet();values=np.ones((1,150));values[0,0]=-1
  manifest_hash=replace_array(root,'components/time_vector',values)
  packet=b.Packet(root,manifest_hash,self.plan)
  with self.assertRaisesRegex(ValueError,'nonnegative'):b.score_packet(packet,self.bank,{'generated_cell':self.mask})

 def test_reader_rejects_component_row_permutation_not_just_shape(self):
  root=self.copied_packet();order=np.arange(511,dtype=np.int64)
  manifest_hash=replace_array(root,'components/condition_sorted_trial_indices',order)
  packet=b.Packet(root,manifest_hash,self.plan)
  with self.assertRaisesRegex(ValueError,'order|condition'):b.score_packet(packet,self.bank,{'generated_cell':self.mask})

 def test_reference_candidate_roles_are_not_interchangeable(self):
  reference=self.packet('operator_reference');candidate=self.packet('submission')
  with self.assertRaisesRegex(ValueError,'role'):b.comparison(candidate,reference,self.bank,{'generated_cell':self.mask})


if __name__=='__main__':unittest.main(verbosity=2)
