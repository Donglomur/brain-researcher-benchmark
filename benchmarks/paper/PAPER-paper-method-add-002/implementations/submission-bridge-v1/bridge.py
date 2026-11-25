"""Source-native result interchange and paired numeric comparison, not admission.

No model/candidate code is executed. Targets and reconstruction masks come only
from the operator. Scientific reproduction/improvement decisions remain absent.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import stat
import numpy as np

HERE=Path(__file__).resolve().parent
PRODUCER=HERE.parent/'source-producer-v1'/'producer.py'
PRODUCER_SHA='c7746e42f4433a128418520e466e68ae1c92461a8e7a5fce4155e9d7a6c04de9'
_producer_source=PRODUCER.read_bytes()
if hashlib.sha256(_producer_source).hexdigest()!=PRODUCER_SHA:raise ValueError('producer dependency identity differs')
spec=importlib.util.spec_from_file_location('slicetca_native_producer',PRODUCER)
p=importlib.util.module_from_spec(spec)
# Execute the authenticated capture; a loader reopen or stale bytecode is not the pinned source.
exec(compile(_producer_source,str(PRODUCER),'exec'),p.__dict__)
e=p.endpoints
TASK='PAPER-paper-method-add-002'
SHAPE=(511,182,150)
PRIMARY={'raw':'raw','trial_nmf12':'trial12','neuron_nmf12':'neuron12','mixed_trial_only':'mixed_trial12_time1','tca12':'cp12','lfads':'lfads'}
COMPANIONS=('mixed_slice12_1','mixed_time_only')
MODELS=tuple(PRIMARY)+COMPANIONS
COMPONENT_SHAPES={'trial_weights':(12,511),'trial_slices':(12,182,150),'time_vector':(1,150),'preparatory_trial_neuron_slice':(511,182),'condition_sorted_trial_indices':(511,),'trial_slice_peak_bin_by_neuron':(12,182),'first_supplied_trial_component_neuron_order':(182,)}
REQUIRED_DECLARATION={'role','information_condition','analysis_code_sha256','analysis_config_sha256','reference_identity','reference_kind'}


def need(ok,message):
 if not ok:raise ValueError(message)


def canonical(value):return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def digest(value):return hashlib.sha256(canonical(value)).hexdigest()


def hexhash(value):return isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) is not None


def frozen_json(path,expected_sha256,maximum_bytes):
 need(hexhash(expected_sha256),'manifest SHA256 required')
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
 with os.fdopen(fd,'rb') as stream:
  st=os.fstat(stream.fileno());need(stat.S_ISREG(st.st_mode) and 0<st.st_size<=maximum_bytes,'manifest extent differs')
  payload=stream.read(maximum_bytes+1)
 need(len(payload)<=maximum_bytes and hashlib.sha256(payload).hexdigest()==expected_sha256,'manifest identity differs')
 value=json.loads(payload);need(isinstance(value,dict),'manifest must be an object');return value


def real(value,name,shape=None):
 a=np.asarray(value)
 need(a.dtype.kind in 'fiu' and a.size and np.isfinite(a).all(),'finite numeric array required: '+name)
 if shape is not None:need(a.shape==shape,'shape mismatch: '+name)
 return a


def same_indices(actual,expected,name):
 a=np.asarray(actual);need(a.dtype.kind in 'iu' and np.array_equal(a,expected),'source index order differs: '+name)


def average_schedule():
 """Explicit source two-half schedule, including the inherited RNG state."""
 rng=np.random.RandomState(0)
 for _ in range(20):rng.permutation(246)
 result={}
 for name,(start,stop) in e.CONDITIONS.items():
  order=np.arange(start,stop);half=len(order)//2;trains=[];tests=[]
  for _ in range(20):
   order=order[rng.permutation(len(order))]
   trains.append(np.stack((order[:half],order[::-1][:half])))
   tests.append(np.stack((order[half:],order[::-1][half:])))
  result[name]={'train':np.stack(trains),'test':np.stack(tests)}
 return result


def mask_digest(mask):
 m=np.asarray(mask);need(m.ndim==3 and m.size and m.dtype.kind in 'biuf' and np.isin(m,(0,1)).all(),'binary training mask required')
 h=hashlib.sha256(canonical({'shape':list(m.shape),'encoding':'uint8-C-training1-heldout0'}))
 h.update(np.ascontiguousarray(m,dtype=np.uint8).tobytes());return h.hexdigest()


def validate_plan(plan):
 keys={'task_id','bank_manifest_sha256','evaluation_profile_sha256','recipe','component_routes','reconstruction_cells','reconstruction_roster_identity'}
 need(isinstance(plan,dict) and set(plan)==keys,'exact operator plan fields required')
 need(plan['task_id']==TASK and hexhash(plan['bank_manifest_sha256']) and hexhash(plan['evaluation_profile_sha256']),'task/bank/profile identity differs')
 need(plan['recipe'] in e.RECIPES,'explicit source ridge or paper OLS recipe required')
 routes=plan['component_routes']
 need(isinstance(routes,dict) and set(routes)=={'region_map','target_projection_route','subspace_route','preparatory_time_indices'},'component routes must be explicit')
 need(routes['region_map'] in ('source_code_92_90','paper_counts_unbound'),'unknown region route')
 need(routes['target_projection_route'] in ('source_raw_factor','paper_partial_average_ols'),'unknown target route')
 need(routes['subspace_route'] in ('source_default_axes','source_orthogonal_span'),'unknown subspace route')
 if routes['target_projection_route']=='paper_partial_average_ols':
  indices=routes['preparatory_time_indices'];need(plan['recipe']=='paper_ols0' and isinstance(indices,list) and indices and all(type(i) is int and 0<=i<150 for i in indices) and len(set(indices))==len(indices),'paper target route requires OLS and explicit source bins')
 else:need(routes['preparatory_time_indices'] is None,'source target route does not use a declared time-average window')
 cells=plan['reconstruction_cells'];need(isinstance(cells,list),'explicit reconstruction cell roster required')
 seen=set()
 for cell in cells:
  need(isinstance(cell,dict) and set(cell)=={'id','source_result_id','rank_specification','seed','cut_bins','training_mask_sha256'},'exact reconstruction cell metadata required')
  ident=cell['id'];need(isinstance(ident,str) and re.fullmatch('[A-Za-z0-9_-]{1,80}',ident) and ident not in seen,'invalid/duplicate reconstruction cell ID');seen.add(ident)
  need(isinstance(cell['source_result_id'],str) and cell['source_result_id'] and isinstance(cell['rank_specification'],dict) and cell['rank_specification'],'source result/rank identity required')
  need(type(cell['seed']) is int and type(cell['cut_bins']) is int and cell['cut_bins']>=0 and hexhash(cell['training_mask_sha256']),'explicit cell seed/cut/mask identity required')
 need(plan['reconstruction_roster_identity'] is None or hexhash(plan['reconstruction_roster_identity']),'roster identity must be SHA256 or unavailable')
 if cells:need(hexhash(plan['reconstruction_roster_identity']),'nonempty cell roster needs an external source-identity pin')
 return plan


def _declaration(declaration):
 need(isinstance(declaration,dict) and set(declaration)==REQUIRED_DECLARATION,'exact submission declaration fields required')
 need(declaration['role'] in ('operator_reference','submission'),'explicit artifact role required')
 allowed=('operator_reference',) if declaration['role']=='operator_reference' else ('paper_data','paper_data_author_code')
 need(declaration['information_condition'] in allowed,'information condition and role disagree')
 need(hexhash(declaration['analysis_code_sha256']) and hexhash(declaration['analysis_config_sha256']),'frozen analysis code/config identities required')
 need(isinstance(declaration['reference_identity'],str) and declaration['reference_identity'],'reference identity string required; it does not authenticate provenance')
 kinds=('historical_published','fresh_source_calibration','unqualified_reference') if declaration['role']=='operator_reference' else ('candidate',)
 need(declaration['reference_kind'] in kinds,'explicit historical/calibration/candidate provenance kind required')


def _shape_keys(plan,angle_counts,subspace_dimensions):
 need(isinstance(angle_counts,dict) and set(angle_counts)==set(e.CONDITIONS),'both averaged angle counts required')
 shapes={}
 for model in MODELS:
  for reach,(lo,hi) in e.CONDITIONS.items():
   width=(hi-lo)//5
   shapes[f'decoding/{model}/{reach}/prediction']=(20,5,80,width,2)
   shapes[f'decoding/{model}/{reach}/test_indices']=(20,5,width)
 for reach,(lo,hi) in e.CONDITIONS.items():
  g=angle_counts[reach];need(type(g) is int and 1<=g<=hi-lo,'invalid angle-group count')
  shapes[f'averaged/{reach}/prediction']=(20,2,80,g,2)
  shapes[f'averaged/{reach}/labels']=(g,)
  shapes[f'averaged/{reach}/train_indices']=(20,2,(hi-lo)//2)
  shapes[f'averaged/{reach}/test_indices']=(20,2,(hi-lo)-(hi-lo)//2)
 shapes.update({'components/'+k:v for k,v in COMPONENT_SHAPES.items()})
 for label in ('all','source_code_M1','source_code_PMd') if plan['component_routes']['region_map']=='source_code_92_90' else ('all',):shapes['components/correlation/'+label]=(511,511)
 for reach,(lo,hi) in e.CONDITIONS.items():shapes['components/target_projection/'+reach]=(hi-lo,2)
 need(type(subspace_dimensions) is int and 1<=subspace_dimensions<=3,'subspace dimensions must be1..3')
 if plan['component_routes']['subspace_route']=='source_default_axes':need(subspace_dimensions==3,'default source axes must preserve all three coordinates')
 shapes['components/subspace/coordinates']=(246,subspace_dimensions)
 shapes['components/subspace/axes']=(182,subspace_dimensions)
 shapes['components/subspace/source_class_labels']=(246,)
 shapes['components/subspace/source_trial_indices']=(246,)
 for cell in plan['reconstruction_cells']:shapes['reconstruction/'+cell['id']]=SHAPE
 return shapes


def collect_arrays(family,plan,reconstruction_predictions):
 """Project owned producer outputs, discarding all submitted scores/targets."""
 validate_plan(plan);need(set(family['single_trial_decoding'])==set(MODELS),'complete eight-model source prediction roster required, including LFADS and mixed companions')
 arrays={};counts={}
 for model in MODELS:
  result=family['single_trial_decoding'][model]
  need(result['recipe']==plan['recipe'] and set(result['conditions'])==set(e.CONDITIONS),'model recipe/conditions differ')
  for reach in e.CONDITIONS:
   row=result['conditions'][reach];arrays[f'decoding/{model}/{reach}/prediction']=row['prediction'];arrays[f'decoding/{model}/{reach}/test_indices']=row['test_indices']
 averaged=family['raw_condition_average_control'];need(averaged['recipe']==plan['recipe'],'averaged recipe differs')
 for reach in e.CONDITIONS:
  rows=averaged['conditions'][reach]['rows'];need(len(rows)==20 and all(len(pair)==2 for pair in rows),'complete averaged repeats/halves required')
  labels=np.asarray(rows[0][0]['condition_labels']);counts[reach]=len(labels)
  need(all(np.array_equal(np.asarray(row['condition_labels']),labels) for pair in rows for row in pair),'averaged condition label order differs within packet')
  arrays[f'averaged/{reach}/labels']=labels
  for field in ('prediction','train_indices','test_indices'):arrays[f'averaged/{reach}/{field}']=np.stack([np.stack([row[field] for row in pair]) for pair in rows])
 comp=family['component_results'];sub=family['preparatory_subspace'];need(isinstance(comp,dict) and isinstance(sub,dict),'native component and subspace outputs required')
 routes=plan['component_routes']
 need(comp['region_mapping']==routes['region_map'] and comp['target_projection_route']==routes['target_projection_route'] and comp['preparatory_time_indices']==routes['preparatory_time_indices'] and sub['route']==routes['subspace_route'],'component routes differ from operator plan')
 for name in COMPONENT_SHAPES:arrays['components/'+name]=comp[name]
 for name,value in comp['condition_correlations'].items():arrays['components/correlation/'+name]=value
 for reach in e.CONDITIONS:arrays['components/target_projection/'+reach]=comp['target_projections'][reach]['prediction']
 for key,source in [('coordinates','coordinates'),('axes','projection_axes'),('source_class_labels','source_class_labels'),('source_trial_indices','source_trial_indices')]:arrays['components/subspace/'+key]=sub[source]
 dimensions=np.asarray(sub['coordinates']).shape[-1]
 need(set(reconstruction_predictions)=={x['id'] for x in plan['reconstruction_cells']},'reconstruction prediction roster differs')
 arrays.update({'reconstruction/'+k:v for k,v in reconstruction_predictions.items()})
 validate_arrays(arrays,plan,counts,dimensions)
 return arrays,counts,dimensions


def validate_arrays(arrays,plan,counts,dimensions):
 need(set(counts)==set(e.CONDITIONS),'both averaged conditions required')
 shapes=_shape_keys(plan,counts,dimensions);need(set(arrays)==set(shapes),'native array census differs')
 for key,shape in shapes.items():
  a=real(arrays[key],key,shape);need(a.dtype.itemsize in (4,8),'unsupported scalar dtype: '+key)
 for model in MODELS:
  for reach in e.CONDITIONS:same_indices(arrays[f'decoding/{model}/{reach}/test_indices'],e.source_schedule(reach)['test'],model+'/'+reach)
 schedule=average_schedule()
 for reach in e.CONDITIONS:
  for side in ('train','test'):same_indices(arrays[f'averaged/{reach}/{side}_indices'],schedule[reach][side],'averaged/'+reach+'/'+side)
  labels=real(arrays[f'averaged/{reach}/labels'],'angle labels');need(np.array_equal(np.unique(labels),labels),'angle labels must be unique sorted source values')
 for key in ('trial_weights','trial_slices','time_vector','preparatory_trial_neuron_slice'):need(np.all(arrays['components/'+key]>=0),'nonnegative exported components required')
 same_indices(arrays['components/subspace/source_trial_indices'],np.arange(265,511),'subspace rows')
 order=np.asarray(arrays['components/condition_sorted_trial_indices']);need(order.dtype.kind in 'iu' and np.array_equal(np.sort(order),np.arange(511)),'component condition order loses/duplicates rows')
 neuron_order=np.asarray(arrays['components/first_supplied_trial_component_neuron_order']);need(neuron_order.dtype.kind in 'iu' and np.array_equal(np.sort(neuron_order),np.arange(182)),'component neuron order differs')


def write_packet(family,destination,*,plan,declaration,reconstruction_predictions):
 _declaration(declaration);arrays,counts,dimensions=collect_arrays(family,plan,reconstruction_predictions)
 root=Path(destination);need(not root.exists(),'fresh packet destination required');root.mkdir(mode=0o700,parents=True)
 records={}
 for index,(key,value) in enumerate(sorted(arrays.items())):
  a=real(value,key);name=f'{index:04d}.npy.gz';path=root/name
  with path.open('xb') as raw:
   with gzip.GzipFile(filename='',fileobj=raw,mode='wb',compresslevel=1,mtime=0) as stream:np.save(stream,a,allow_pickle=False)
  os.chmod(path,0o600);records[key]={'file':name,'bytes':path.stat().st_size,'sha256':p.file_hash(path),'shape':list(a.shape),'dtype':a.dtype.str}
 manifest={'schema':'slicetca-native-submission-v1','task_id':TASK,'producer_sha256':PRODUCER_SHA,'plan_sha256':digest(plan),'bank_manifest_sha256':plan['bank_manifest_sha256'],'evaluation_profile_sha256':plan['evaluation_profile_sha256'],'recipe':plan['recipe'],'declaration':declaration,'angle_counts':counts,'subspace_dimensions':dimensions,'files':records,'scientific_admission':False,'independent_submitted_computation_verification':'incomplete: producer does not retain decoder coefficients/displacements or neural condition means'}
 (root/'MANIFEST.json').write_bytes(canonical(manifest));os.chmod(root/'MANIFEST.json',0o600)
 return {'manifest_sha256':p.file_hash(root/'MANIFEST.json'),'arrays':len(records),'scientific_admission':False}


class Packet:
 """Bounded lazy numeric input; untrusted scalar scores never enter the API."""
 def __init__(self,path,expected_manifest_sha256,plan):
  # Keep our own frozen configuration, independent of caller-owned dictionaries.
  plan=validate_plan(json.loads(canonical(plan)));self.root=Path(path);self.plan=plan;manifest=self.root/'MANIFEST.json'
  self.manifest=frozen_json(manifest,expected_manifest_sha256,1024**2);self.manifest_sha256=expected_manifest_sha256;m=self.manifest
  need(m['schema']=='slicetca-native-submission-v1' and m['task_id']==TASK and m['producer_sha256']==PRODUCER_SHA,'packet task/producer differs')
  need(m['plan_sha256']==digest(plan) and m['bank_manifest_sha256']==plan['bank_manifest_sha256'] and m['evaluation_profile_sha256']==plan['evaluation_profile_sha256'] and m['recipe']==plan['recipe'],'packet does not match frozen operator plan')
  _declaration(m['declaration']);self.shapes=_shape_keys(plan,m['angle_counts'],m['subspace_dimensions'])
  need(set(m['files'])==set(self.shapes),'packet array census differs')
  names=[]
  for key,row in m['files'].items():
   need(set(row)=={'file','bytes','sha256','shape','dtype'} and row['shape']==list(self.shapes[key]),'array declaration differs')
   need(isinstance(row['file'],str) and re.fullmatch(r'[0-9]{4}\.npy\.gz',row['file']),'unsafe array path')
   dtype=np.dtype(row['dtype']);need(dtype.kind in 'fiu' and dtype.itemsize in (4,8),'unsupported scalar dtype')
   need(type(row['bytes']) is int and 0<row['bytes']<=int(np.prod(self.shapes[key]))*dtype.itemsize+1024**2 and hexhash(row['sha256']),'array size/hash declaration differs')
   file=self.root/row['file'];st=file.lstat();need(stat.S_ISREG(st.st_mode) and st.st_size==row['bytes'],'array must be a regular file of exact extent')
   need(p.file_hash(file)==row['sha256'],'array content hash differs');names.append(row['file'])
  need(len(names)==len(set(names)) and {x.name for x in self.root.iterdir()}==set(names)|{'MANIFEST.json'},'extra, duplicate or missing packet files')
 def get(self,key):
  row=self.manifest['files'][key];shape=self.shapes[key];path=self.root/row['file']
  # Parse exactly the bytes whose digest was checked, even if the directory is
  # modified after construction. No symlink following or second path reopen.
  fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
  with os.fdopen(fd,'rb') as raw:
   st=os.fstat(raw.fileno());need(stat.S_ISREG(st.st_mode) and st.st_size==row['bytes'],'array extent changed')
   payload=raw.read(row['bytes']+1)
  need(len(payload)==row['bytes'] and hashlib.sha256(payload).hexdigest()==row['sha256'],'array content changed after admission')
  with gzip.GzipFile(fileobj=io.BytesIO(payload),mode='rb') as stream:
   version=np.lib.format.read_magic(stream)
   need(version in ((1,0),(2,0)),'numeric NPYv1/v2 required')
   actual_shape,fortran,dtype=(np.lib.format.read_array_header_1_0 if version==(1,0) else np.lib.format.read_array_header_2_0)(stream,max_header_size=4096)
   need(actual_shape==shape and dtype.str==row['dtype'] and not dtype.hasobject,'native NPY shape/dtype differs')
   size=int(np.prod(shape))*dtype.itemsize;data=stream.read(size+1);need(len(data)==size and not stream.read(1),'NPY decoded extent differs')
  return real(np.frombuffer(data,dtype=dtype).reshape(shape,order='F' if fortran else 'C'),key,shape)


PREPARED_SHAPES = {
 'neural.npy': SHAPE, 'movement.npy': (150,511,2),
 'target_angle.npy': (511,), 'target_pos.npy': (511,2),
 'condition.npy': (511,), 'source_trial_indices.npy': (511,),
}


def _captured_numeric_npy(path,shape,*,expected_bytes=None,expected_sha256=None):
 """Decode an immutable bounded capture, never reopen a hashed path or mmap.

 The same captured bytes are hashed and interpreted. Returned arrays retain the
 immutable bytes as their backing store, so later file mutation cannot alter
 operator targets or masks. This is file-input integrity, not process isolation.
 """
 need(isinstance(shape,tuple) and shape and all(type(n) is int and n>0 for n in shape),'positive fixed NPY shape required')
 count=1
 for n in shape:count*=n
 # Preserve numeric primitive precision, including 16-byte floating point.
 # The original published bank is float32/float64/integer. This maximum is an
 # allocation bound, not a permission to alter its expected source shape.
 maximum=count*16+8192
 need((expected_bytes is None)==(expected_sha256 is None),'NPY extent and hash must be supplied together')
 if expected_bytes is not None:
  need(type(expected_bytes) is int and 0<expected_bytes<=maximum and hexhash(expected_sha256),'invalid prepared NPY extent/hash')
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
 with os.fdopen(fd,'rb') as stream:
  before=os.fstat(stream.fileno())
  need(stat.S_ISREG(before.st_mode) and 0<before.st_size<=maximum,'operator NPY file extent/type differs')
  if expected_bytes is not None:need(before.st_size==expected_bytes,'prepared NPY extent differs')
  payload=stream.read(before.st_size+1)
 need(len(payload)==before.st_size,'operator NPY extent changed while capturing')
 if expected_sha256 is not None:need(hashlib.sha256(payload).hexdigest()==expected_sha256,'prepared NPY identity differs')
 stream=io.BytesIO(payload);version=np.lib.format.read_magic(stream)
 need(version in ((1,0),(2,0)),'numeric NPYv1/v2 required')
 actual_shape,fortran,dtype=(np.lib.format.read_array_header_1_0 if version==(1,0) else np.lib.format.read_array_header_2_0)(stream,max_header_size=4096)
 need(actual_shape==shape and dtype.kind in 'biuf' and not dtype.hasobject and dtype.fields is None and dtype.subdtype is None and dtype.itemsize in (1,2,4,8,16),'operator NPY shape/primitive dtype differs')
 offset=stream.tell();need(len(payload)-offset==count*dtype.itemsize,'operator NPY decoded extent differs')
 value=np.frombuffer(payload,dtype=dtype,count=count,offset=offset).reshape(shape,order='F' if fortran else 'C')
 need(np.isfinite(value).all(),'operator NPY nonfinite value')
 need(not value.flags.writeable,'operator NPY capture must be immutable')
 return value


def load_prepared_bank(directory,expected_manifest_sha256):
 root=Path(directory);need(root.is_dir() and not root.is_symlink(),'regular prepared bank directory required')
 manifest=frozen_json(root/'COMPLETE.json',expected_manifest_sha256,65536)
 need(manifest['task_id']==TASK and manifest['producer_sha256']==PRODUCER_SHA and manifest['status']=='complete_original_array_preparation_only','unrecognized prepared bank')
 arrays={}
 for name,shape in PREPARED_SHAPES.items():
  record=manifest['files'][name]
  value=_captured_numeric_npy(root/name,shape,expected_bytes=record['bytes'],expected_sha256=record['sha256'])
  arrays[name[:-4]]=real(value,name,shape)
 same_indices(arrays['source_trial_indices'],np.arange(SHAPE[0]),'prepared source rows')
 arrays['manifest_sha256']=expected_manifest_sha256
 return arrays


def _averaged_metrics(packet,bank,reach):
 lo,hi=e.CONDITIONS[reach];labels=np.unique(bank['target_angle'][lo:hi]);prediction=packet.get(f'averaged/{reach}/prediction')
 need(np.array_equal(packet.get(f'averaged/{reach}/labels'),labels),'averaged labels differ from operator data')
 schedule=average_schedule()[reach];trains=packet.get(f'averaged/{reach}/train_indices');tests=packet.get(f'averaged/{reach}/test_indices')
 same_indices(trains,schedule['train'],'averaged train');same_indices(tests,schedule['test'],'averaged test')
 movement=bank['movement'][65:-5];angles=bank['target_angle'];scores=[];group_counts=[]
 for repeat in range(20):
  for half in range(2):
   test=tests[repeat,half];train=trains[repeat,half]
   counts=np.array([[np.count_nonzero(angles[ids]==label) for label in labels] for ids in (train,test)])
   need(np.all(counts>0),'a source angle is absent from an averaged half')
   target=np.stack([movement[:,test[angles[test]==label]].mean(axis=1) for label in labels],axis=1)
   pred=prediction[repeat,half];need(np.array_equal(pred[0],target[0]),'averaged prediction must start at true group-mean position')
   scores.append(e.trajectory_r2(target,pred)['r2']);group_counts.append(counts)
 values=np.stack(scores).reshape(20,2,len(labels))
 return {'mean':float(values.mean()),'r2':values,'group_counts':np.stack(group_counts).reshape(20,2,2,len(labels)),'unit':'condition averages in dependent repeated halves'}


def validate_component_evidence(packet,bank):
 """Verify supplied-array algebra only, without fitting or matching a finding.

 The 1e-10 numerical tolerance here is for floating-point array algebra, not a
 scientific reproduction tolerance or component-gauge equivalence criterion.
 """
 arrays={key:packet.get(key) for key in packet.shapes if key.startswith('components/')}
 for key in ('trial_weights','trial_slices','time_vector','preparatory_trial_neuron_slice'):
  need(np.all(arrays['components/'+key]>=0),'nonnegative exported components required')
 slices=arrays['components/trial_slices'];preparatory=arrays['components/preparatory_trial_neuron_slice']
 same_indices(arrays['components/trial_slice_peak_bin_by_neuron'],slices.argmax(axis=2),'component peak bins')
 same_indices(arrays['components/first_supplied_trial_component_neuron_order'],np.argsort(slices[0].argmax(axis=1)),'component peak neuron order')
 condition=real(bank['condition'],'operator conditions',(511,))
 labels=(20,22,10,34,18,39,32,5,37,35,26,31)
 need(np.isin(condition,labels).all(),'unknown operator source condition')
 order=np.concatenate([np.flatnonzero(condition[lo:hi]==label)+lo for lo,hi in e.CONDITIONS.values() for label in labels])
 same_indices(arrays['components/condition_sorted_trial_indices'],order,'component source condition order')
 selections={'all':slice(None)}
 if packet.plan['component_routes']['region_map']=='source_code_92_90':selections.update({'source_code_M1':slice(0,92),'source_code_PMd':slice(92,None)})
 for label,columns in selections.items():
  values=preparatory[order,columns]
  need(np.all(values.std(axis=1)>0),'undefined component row correlation')
  need(np.allclose(arrays['components/correlation/'+label],np.corrcoef(values),rtol=1e-10,atol=1e-10),'component correlation does not follow supplied factors')
 same_indices(arrays['components/subspace/source_trial_indices'],np.arange(265,511),'subspace source rows')
 expected_classes=np.where(np.isin(condition[265:],(5,18,20,22,26,35,39)),0,1)
 same_indices(arrays['components/subspace/source_class_labels'],expected_classes,'subspace source class labels')
 axes=arrays['components/subspace/axes'];coordinates=arrays['components/subspace/coordinates']
 need(np.allclose(coordinates,preparatory[265:]@axes,rtol=1e-10,atol=1e-10),'subspace coordinates differ from supplied slice and axes')
 return 'native array algebra verified; fitted axes, factor provenance, gauge and scientific relationships remain unverified'


def score_packet(packet,bank,training_masks):
 need(bank['manifest_sha256']==packet.plan['bank_manifest_sha256'],'operator bank differs from packet plan')
 real(bank['movement'],'operator movement',(150,511,2));real(bank['target_angle'],'operator angles',(511,));real(bank['neural'],'operator neural',SHAPE)
 expected_cells={c['id'] for c in packet.plan['reconstruction_cells']};need(set(training_masks)==expected_cells,'operator mask roster differs')
 for cell in packet.plan['reconstruction_cells']:
  mask=training_masks[cell['id']];need(np.asarray(mask).shape==SHAPE and mask_digest(mask)==cell['training_mask_sha256'],'operator mask shape/content differs')
 metrics={};details={}
 for model in MODELS:
  for reach in e.CONDITIONS:
   prediction=packet.get(f'decoding/{model}/{reach}/prediction');indices=packet.get(f'decoding/{model}/{reach}/test_indices')
   summary,detail=e.score_condition(bank['movement'],reach,prediction,indices)
   key=f'fig2_{PRIMARY.get(model,model)}_{reach}_trajectory_r2'
   metrics[key]={'value':summary['mean_trial_fold_repeat_r2'],'direction':'higher','primary':model in PRIMARY,'population_sd':summary['mean_within_fold_population_sd']};details[key]=detail
 for reach in e.CONDITIONS:
  avg=_averaged_metrics(packet,bank,reach);key=f'fig2_condition_average_{reach}_trajectory_r2'
  metrics[key]={'value':avg['mean'],'direction':'higher','primary':True};details[key]=avg
 cells={}
 for cell in packet.plan['reconstruction_cells']:
  cells[cell['id']]=e.reconstruction_error(bank['neural'],packet.get('reconstruction/'+cell['id']),training_masks[cell['id']],cut_bins=cell['cut_bins'])
 # No factor-distance metric, new fitting or recovered-finding decision.
 component_status=validate_component_evidence(packet,bank)
 return {'metrics':metrics,'reconstruction':cells,'private_details':details,'component_status':component_status}


def comparison(reference,candidate,bank,training_masks):
 need(reference.plan==candidate.plan,'paired operator plans differ')
 need(reference.manifest['declaration']['role']=='operator_reference' and candidate.manifest['declaration']['role']=='submission','reference/submission roles reversed or missing')
 # Entire input/cell/schedule validation completes before any comparative result.
 ref=score_packet(reference,bank,training_masks);cand=score_packet(candidate,bank,training_masks)
 findings={}
 for key,row in ref['metrics'].items():
  observed=cand['metrics'][key];delta=observed['value']-row['value']
  fixed_control=key.startswith(('fig2_raw_','fig2_condition_average_'))
  findings[key]={'reference':row['value'],'submission':observed['value'],'primary':row['primary'],'comparison_role':'fixed_control' if fixed_control else 'method_result','reproduction':{'signed_difference':delta,'absolute_difference':abs(delta),'decision':'unavailable'},'improvement':{'direction':'higher','directional_delta':delta,'claim_role':'diagnostic_only' if fixed_control else 'method_result','decision':'unavailable'}}
 cells={}
 for ident,source in ref['reconstruction'].items():
  current=cand['reconstruction'][ident];delta=current['source_cv_root_error']-source['source_cv_root_error']
  cells[ident]={'reference':source,'submission':current,'reproduction':{'signed_rmse_difference':delta,'absolute_rmse_difference':abs(delta),'decision':'unavailable'},'improvement':{'direction':'lower','directional_rmse_gain':-delta,'decision':'unavailable'}}
 return {'task_id':TASK,'status':'numerical_comparison_only','plan_sha256':digest(reference.plan),'bank_manifest_sha256':bank['manifest_sha256'],'reference_packet_manifest_sha256':reference.manifest_sha256,'submission_packet_manifest_sha256':candidate.manifest_sha256,'producer_sha256':PRODUCER_SHA,'endpoints_sha256':p.ENDPOINTS_SHA256,'information_condition':candidate.manifest['declaration']['information_condition'],'reference_kind':reference.manifest['declaration']['reference_kind'],'reference_provenance_authenticated':False,'canonical_findings':{k:v for k,v in findings.items() if v['primary']},'mixed_companion_findings':{k:v for k,v in findings.items() if not v['primary']},'reconstruction_cells':cells,'native_component_verification':ref['component_status'],'independent_computation_verification':'incomplete: missing decoder fit receipts/coefficients, displacements and neural condition means','scientific_decisions':{'reproduction':'unavailable','improvement':'unavailable','joint_family':'unavailable'},'uncertainty':'not computed; folds and repeats are dependent','remaining_holds':['Historical reference and scientific comparator qualification','Source-supported reproduction criteria and meaningful improvement/uncertainty rule','Original component relationships/gauge criteria','Original reconstruction roster and mask/rank/seed authority' if not cells else 'Source authority for the supplied reconstruction roster remains externally unqualified','Protected paired execution, information access and resource protocol'],'private_reference_details':ref['private_details'],'private_submission_details':cand['private_details']}


def load_operator_masks(directory,plan):
 """Load only the exact externally frozen cell roster; never create a mask."""
 cells=plan['reconstruction_cells']
 if not cells:
  need(directory is None,'no mask directory allowed for an unresolved empty roster');return {}
 need(directory is not None,'operator mask directory required for reconstruction cells')
 root=Path(directory);need(root.is_dir() and not root.is_symlink(),'regular operator mask directory required')
 need({x.name for x in root.iterdir()}=={c['id']+'.npy' for c in cells},'operator mask file roster differs')
 result={}
 for cell in cells:
  path=root/(cell['id']+'.npy')
  value=_captured_numeric_npy(path,SHAPE)
  need(mask_digest(value)==cell['training_mask_sha256'],'operator mask content/shape differs')
  result[cell['id']]=value
 return result


def main():
 parser=argparse.ArgumentParser(description=__doc__)
 for name in ('plan','bank','reference','candidate','summary','private_details'):parser.add_argument('--'+name.replace('_','-'),required=True,type=Path)
 for name in ('reference_sha256','candidate_sha256'):parser.add_argument('--'+name.replace('_','-'),required=True)
 parser.add_argument('--mask-directory',type=Path)
 args=parser.parse_args();need(not args.summary.exists() and not args.private_details.exists(),'fresh operator outputs required')
 plan=validate_plan(json.loads(args.plan.read_text()));masks=load_operator_masks(args.mask_directory,plan)
 bank=load_prepared_bank(args.bank,plan['bank_manifest_sha256'])
 report=comparison(Packet(args.reference,args.reference_sha256,plan),Packet(args.candidate,args.candidate_sha256,plan),bank,masks)
 details={}
 for role in ('reference','submission'):
  for finding,record in report.pop('private_'+role+'_details').items():
   for key,value in record.items():
    if isinstance(value,np.ndarray):details[role+'/'+finding+'/'+key]=value
 with args.private_details.open('xb') as f:np.savez_compressed(f,**details)
 os.chmod(args.private_details,0o600);args.summary.write_bytes(canonical(report));os.chmod(args.summary,0o600)
 print(json.dumps({'status':report['status'],'canonical_findings':len(report['canonical_findings']),'scientific_decisions':report['scientific_decisions']}));return 0

if __name__=='__main__':raise SystemExit(main())
