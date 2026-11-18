"""Changed S03 binding controls: generated full shapes, no authentic inputs.

Fixture metadata construction is retained from the accepted handoff controls;
this suite executes the new core and original numeric projection/serialization.
The synthetic source receipt is a fixture, not an acquisition assertion.
"""
import argparse, copy, hashlib, importlib.util, json, os
from pathlib import Path
import sys, tempfile, time, types, unittest
from unittest.mock import patch
import numpy as np
HERE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(add_help=False)
parser.add_argument('--dependency-root',type=Path,default=HERE.parent)
parser.add_argument('--fixture-root',type=Path)
args,rest=parser.parse_known_args();sys.argv=[sys.argv[0],*rest]
spec=importlib.util.spec_from_file_location('_new_s03_core',HERE/'core.py');K=importlib.util.module_from_spec(spec);spec.loader.exec_module(K)
S=K.load_sources(HERE,args.dependency_root)
H=S.opaque_s03
for row in json.loads((HERE/'TEST_DEPENDENCIES.json').read_text())['files']:
 path=args.dependency_root/row['path'];raw=K.snapshot(path,{k:row[k]for k in ('bytes','sha256')},65536)
 name=S.prefix+'.'+row['role'];mod=types.ModuleType(name);mod.__package__=S.prefix;mod.__file__=str(path)
 sys.modules[name]=mod;exec(compile(raw,str(path),'exec'),mod.__dict__)
C=sys.modules[S.prefix+'.operator_compiler'];P=S.programme
spec=importlib.util.spec_from_file_location('_new_s03_controller',HERE/'authoring/s03-worker/controller.py');CTL=importlib.util.module_from_spec(spec);spec.loader.exec_module(CTL)

def desc(path, raw):
    return {'path': path, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def fixture():
    seed = b'0123456789abcdef' * 2
    assert len(seed) == 32
    sizes = H.AXES
    original = {'schema': 'NLB017_target_free_planned_support_v2',
        'source_release': {'dandiset':'000128','version':'0.220113.0400',
            'asset_id':'26e85f09-39b7-480f-b337-278a8f034007','raw_bytes':690612247,
            'raw_sha256':'a27f84f9c31f077011062fd99a6ced199fdf19e656151f056c3c6244a408a3c4'},
        'split_identity': desc('original/source-split.json', b'original source split'),
        'shape': {'training':[1721,140,137,45], 'query':[574,140,137,45]},
        'bin_left_edges_ms': list(range(-250,450,5))}
    axes = {}
    for axis, size in sizes.items():
        original[axis] = [axis+'-%04d'%i for i in range(size)]
        role = 'tr-' if 'trial' in axis else 'un-'
        # Different disjoint ranges preserve cross-role uniqueness.
        offset = list(sizes).index(axis)*10000
        opaque = [role+('%032x'%(offset+size-i)) for i in range(size)]
        axes[axis] = {'source': original[axis].copy(), 'opaque_in_source_order': opaque}
    original['train_condition_ids'] = ['condition-%d'%(i%7) for i in range(1721)]
    original['eval_condition_ids'] = ['condition-%d'%(i%7) for i in range(574)]
    original['chronological_eval_trial_ids'] = original['eval_trial_ids'][::2] + original['eval_trial_ids'][1::2]
    split = {'fit_indices':list(range(1381)), 'validation_indices':list(range(1381,1721)),
             'descriptor':{'source_split_sha256':H.D0,'preserved_generated_provenance':'original-role-membership'}}
    shuffle = {'schema':'NLB017_target_free_shuffle_commitment_v2',
        'planned_support_sha256':H.digest(H.canonical(original)), 'seed_sha256':hashlib.sha256(seed).hexdigest(),
        'numpy_version':np.__version__, 'rule':copy.deepcopy(P.SHUFFLE_RULE)}
    core = {'schema':'NLB017_opaque_delivery_v1','source_panel_fingerprint':H.SOURCE_FP,
        'source_manifest_sha256':H.SOURCE_MANIFEST,'axes':axes,
        'condition_policy':'original permitted labels retained verbatim and permuted with their trials',
        'key_sha256':hashlib.sha256(b'generated separate export key').hexdigest(),
        'permutation':'lexicographic opaque ID order separately within each split/axis',
        'counts_units':'spikes_per_5ms_bin'}
    binding = {'core':core,'public_manifest_sha256':H.opaque_digest(core),'public_panel_fingerprint':'d'*64}
    docs = {'original_support':original,'original_split':split,'original_shuffle':shuffle,'private_binding':binding}
    selected = {'schema':'NLB017_opaque_S03_selection_v1',
        'source_manifest':desc('source/SOURCE_MANIFEST.json', b'generated source manifest'),
        'inputs':{'opaque_public':desc('input/public.npz',b'generated-public-archive'),
                  'protected_shuffle_seed':desc('private/shuffle-seed.bin',seed)},
        'opaque_fingerprint':'d'*64,'binding_content_sha256':H.opaque_digest(binding),
        'export_implementation':{'bytes':15826,'sha256':'1'*64},
        'export_source_dependencies':{'bytes':1001,'sha256':'2'*64}}
    return selected, docs, seed


def pack(selected, docs):
    selected, docs = copy.deepcopy(selected), copy.deepcopy(docs)
    binding = docs['private_binding']
    binding['public_manifest_sha256'] = H.opaque_digest(binding['core'])
    selected['binding_content_sha256'] = H.opaque_digest(binding)
    raw = {name:H.canonical(value) for name,value in docs.items() if name!='export_receipt'}
    for name, body in raw.items(): selected['inputs'][name] = desc('private/'+name+'.json',body)
    receipt = {'schema':'neural017_opaque_file_export_v1','status':'complete','source':H.SOURCE_PUBLIC,
        'source_panel_fingerprint':H.SOURCE_FP,'public':H.byte_pin(selected['inputs']['opaque_public']),
        'public_panel_fingerprint':selected['opaque_fingerprint'],
        'binding':H.byte_pin(selected['inputs']['private_binding']),
        'binding_content_sha256':selected['binding_content_sha256'],
        'implementation':selected['export_implementation'], 'source_dependencies':selected['export_source_dependencies'],
        'support':H.SUPPORT,'condition_policy':'original permitted labels retained',
        'runtime':{'generated':True},'old_campaign_commitments_valid_for_this_export':False,
        'participant_execution_or_native_understanding_established':False}
    raw['export_receipt'] = H.canonical(receipt)
    selected['inputs']['export_receipt'] = desc('private/export_receipt.json',raw['export_receipt'])
    return selected,raw



class S03Controls(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=None
  if args.fixture_root is None:
   cls.tmp=tempfile.TemporaryDirectory(prefix='n017-s03-generated-');cls.root=Path(cls.tmp.name)
  else:
   cls.root=args.fixture_root.absolute();cls.root.mkdir(parents=True,exist_ok=False)
  cls.inputs=cls.root/'inputs';cls.output=cls.root/'output';cls.inputs.mkdir();cls.output.mkdir()
  cls.charged=0
  def put(path,raw):
   cls.charged+=len(raw)
   if cls.charged>1500000:raise ValueError('Prospective generated fixture write bound')
   path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
  cls.put=staticmethod(put)
  selected,docs,seed=fixture()
  aliases=docs['private_binding']['core']['axes']
  packet={axis:np.asarray(sorted(aliases[axis]['opaque_in_source_order']))for axis in H.AXES}
  for key,axis in (('train_condition_ids','train_trial_ids'),('eval_condition_ids','eval_trial_ids')):
   order=sorted(range(H.AXES[axis]),key=aliases[axis]['opaque_in_source_order'].__getitem__)
   packet[key]=np.asarray(docs['original_support'][key])[order]
  packet.update(bin_left_edges_ms=np.arange(-250,450,5,dtype=np.float64),
   train_counts_heldin=np.broadcast_to(np.asarray(0,dtype=np.uint16),(1721,140,137)),
   train_counts_heldout=np.broadcast_to(np.arange(45,dtype=np.uint16)[None,None,:],(1721,140,45)),
   eval_counts_heldin=np.broadcast_to(np.arange(574,dtype=np.uint16)[::-1,None,None],(574,140,137)),
   eval_valid_mask=np.broadcast_to(np.asarray(True),(574,140,45)),
   source_manifest_sha256=np.asarray(H.opaque_digest(docs['private_binding']['core'])))
  fp=S.delivery.fingerprint(packet);packet['panel_fingerprint']=np.asarray(fp)
  raw=S.arrays.dump_arrays(packet);del packet
  selected['opaque_fingerprint']=fp;docs['private_binding']['public_panel_fingerprint']=fp
  selected['inputs']['opaque_public']=desc('input/public.npz',raw)
  selected,captured=pack(selected,docs);made=H.prepare(selected,captured)
  put(cls.inputs/'input/public.npz',raw);del raw
  for name,body in captured.items():put(cls.inputs/selected['inputs'][name]['path'],body)
  put(cls.inputs/selected['inputs']['protected_shuffle_seed']['path'],seed)
  pins={}
  for name,value in made.items():
   raw=H.canonical(value);pins[name]=desc('opaque/'+name+'.json',raw);put(cls.inputs/pins[name]['path'],raw)
  cls.compiled=C.compile_opaque_s03(selected,pins);cls.table=K.compilation(cls.compiled)
  cls.fp=fp;cls.seed=seed;cls.docs=docs;cls.planned=made['support']
  # Charged cap checks wrap actual original Store writes; original byte/output semantics remain unchanged.
  write=S.contracts.Store.write
  def bounded_write(store,name,raw,cap):
   cls.charged+=len(raw)
   if cls.charged>1500000:raise ValueError('Prospective generated fixture output bound')
   return write(store,name,raw,cap)
  with patch.object(S.contracts.Store,'write',bounded_write):
   cls.result=K.run_projection(S,cls.compiled,cls.inputs,cls.output,fp,time.monotonic()+100)
  cls.summary=K.admit_public(S,cls.inputs,cls.table['input/opaque_public'],fp)
  donorraw=(cls.output/'protected_map.npz').read_bytes();cls.donor=S.arrays.load_arrays(donorraw)['donor_index']
  print(json.dumps({'generated_fixture_bytes_charged':cls.charged,'original_worker_executions':1,'authentic_inputs':False}))
 @classmethod
 def tearDownClass(cls):
  if cls.tmp is not None:cls.tmp.cleanup()
 def test_complete_original_numeric_projection_and_closed_imports(self):
  self.assertEqual(set(self.result['products']),set(K.OUTPUTS));self.assertEqual(len(self.result['validation']['views']),10)
  self.assertTrue(self.result['validation']['same_seed_and_donor_relation']);self.assertFalse(self.result['seed_generated'])
  self.assertFalse(self.result['benchmark_ready']);self.assertFalse(self.result['scientific_score_produced'])
  self.assertEqual(self.result['support'],dict(training_trials=1721,query_trials=574,bins=140,bin_ms=5,observed_units=137,withheld_units=45))
  with self.assertRaises(ModuleNotFoundError):__import__(S.prefix+'.scoring')
 def test_compiler_wrong_role_extra_operand_and_custody_refuse(self):
  for change in ('role','extra','custody','output'):
   bad=copy.deepcopy(self.compiled)
   if change=='role':bad['request']['role']='protected_score'
   elif change=='extra':bad['initial_artifacts'].append(bad['initial_artifacts'][0])
   elif change=='custody':bad['initial_artifacts'][0]['role']='target'
   else:bad['outputs']['support']['role']='target'
   with self.assertRaises(ValueError):K.compilation(bad)
 def test_public_mismatch_refuses_before_worker(self):
  with patch.object(S.worker,'execute',side_effect=AssertionError('must not execute'))as call:
   with self.assertRaises(ValueError):K.run_projection(S,self.compiled,self.inputs,self.output,'f'*64,time.monotonic()+10)
   call.assert_not_called()
 def test_view_field_content_and_shape_mutations_refuse(self):
  raw=(self.output/'context_only_query.npz').read_bytes();packet=S.arrays.load_arrays(raw)
  for mutation in ('field','content','shape'):
   bad=dict(packet)
   if mutation=='field':bad['eval_counts_heldin']=np.asarray([0])
   elif mutation=='content':bad['eval_trial_ids']=packet['eval_trial_ids'][::-1]
   else:bad['eval_valid_mask']=packet['eval_valid_mask'][:-1]
   with self.assertRaises(ValueError):K.validate_view(S,bad,'context_only','query',self.summary,self.donor)
 def test_shuffle_content_and_map_mutations_refuse(self):
  raw=(self.output/'within_condition_shuffle_query.npz').read_bytes();packet=S.arrays.load_arrays(raw)
  bad=dict(packet);bad['eval_counts_heldin']=packet['eval_counts_heldin'][::-1]
  with self.assertRaises(ValueError):K.validate_view(S,bad,'within_condition_shuffle','query',self.summary,self.donor)
  raw=S.arrays.dump_arrays({'donor_index':np.arange(574,dtype=np.int64)})
  original=K.snapshot
  def replaced(path,expected,cap):
   if Path(path).name=='protected_map.npz':return raw
   return original(path,expected,cap)
  store=types.SimpleNamespace(json=lambda pin:K.decode((self.inputs/pin['path']).read_bytes()))
  with patch.object(K,'snapshot',replaced):
   with self.assertRaisesRegex(ValueError,'Same protected donor map'):
    K.validate_products(S,store,self.output,self.result['products'],self.planned,self.summary,self.table,self.seed)
 def test_deadline_and_missing_product_refuse(self):
  with patch.object(K,'admit_public',side_effect=AssertionError('too late')):
   with self.assertRaises(ValueError):K.run_projection(S,self.compiled,self.inputs,self.output,self.fp,0,clock=lambda:1)
  bad=dict(self.result['products']);bad.pop('metadata_neutral_query')
  with self.assertRaises(ValueError):K.validate_products(S,None,self.output,bad,self.planned,self.summary,self.table,self.seed)
 def test_stable_capture_refuses_altered_bytes_and_links(self):
  path=self.inputs/self.table['opaque/support']['path'];pin={k:self.table['opaque/support'][k]for k in ('bytes','sha256')}
  self.assertEqual(K.byte_pin(K.snapshot(path,pin,200000)),pin)
  with self.assertRaises(ValueError):K.snapshot(path,{**pin,'sha256':'0'*64},200000)
  alias=self.root/'linked.json';alias.symlink_to(path)
  try:
   with self.assertRaises(ValueError):K.snapshot(alias,pin,200000)
  finally:alias.unlink()

class ProfileControls(unittest.TestCase):
 def test_exact_mounts_profile_and_readonly_custody(self):
  table={name:{'path':'role/'+str(i)}for i,name in enumerate(sorted(K.INPUT_NAMES))}
  value={'compilation_file':'/owned/recipe.json','dependency_root':'/owned/deps','dependencies':list(S.source_rows.values()),
   'input_files':{name:{'path':'/owned/input/'+str(i)}for i,name in enumerate(table)},
   'input_descriptors':table,'uid':501,'gid':20}
  with patch.object(CTL,'SELECT',Path('/owned/selection.json')),patch.object(CTL,'NATIVE',Path('/owned/native')):
   mounts=CTL.mapping(value);argv=CTL.create_args(mounts,'a'*64,value)
  self.assertEqual(len(mounts),24);self.assertEqual([k for k,v in mounts.items()if not v[1]],['/out'])
  self.assertEqual({k for k in mounts if k.startswith('/inputs/')},{'/inputs/'+d['path']for d in table.values()})
  self.assertIn('2147483648',argv);self.assertIn('none',argv);self.assertIn('--pull',argv)
  self.assertFalse(any('operator_targets' in str(x) or 'export_key' in str(x) for x in mounts.values()))

if __name__=='__main__':unittest.main()
