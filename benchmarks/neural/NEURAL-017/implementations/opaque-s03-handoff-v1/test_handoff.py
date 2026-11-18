"""Generated full-support metadata/shuffle/worker controls; no authentic input."""
import argparse
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
import numpy as np

HERE = Path(__file__).resolve().parent
DEFAULT = HERE.parent / 'registered-runtime/complete-operator/nlb'
parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('--dependency-root', type=Path, default=DEFAULT)
options, remaining = parser.parse_known_args()
sys.argv = [sys.argv[0], *remaining]
PREFIX = '_n017_opaque_s03_controls'
package = types.ModuleType(PREFIX); package.__path__ = []; sys.modules[PREFIX] = package
modules = {}
for name in ('contracts', 'programme', 'arrays', 'views', 'operator_roster', 'opaque_s03', 'worker', 'operator_compiler'):
    path = (DEFAULT if name in ('opaque_s03', 'worker', 'operator_compiler') else options.dependency_root) / (name+'.py')
    module = types.ModuleType(PREFIX+'.'+name); module.__package__ = PREFIX; module.__file__ = str(path)
    sys.modules[module.__name__] = module; setattr(package, name, module)
    exec(compile(path.read_bytes(), str(path), 'exec'), module.__dict__)
    modules[name] = module
H, C, V, W, A, P = (modules[n] for n in ('opaque_s03','operator_compiler','views','worker','arrays','programme'))


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


class Inputs:
    def __init__(self, selected, captured, produced, seed):
        self.data = {selected['inputs'][k]['path']:v for k,v in captured.items()}
        self.data[selected['inputs']['opaque_public']['path']] = b'generated-public-archive'
        self.data[selected['inputs']['protected_shuffle_seed']['path']] = seed
        self.pins = {}
        for name, value in produced.items():
            raw = H.canonical(value); self.pins[name]=desc('opaque/'+name+'.json',raw)
            self.data[self.pins[name]['path']] = raw
    def read(self, d, cap):
        raw=self.data[d['path']]
        if len(raw)>cap or desc(d['path'],raw)!=d: raise ValueError('generated exact capture failure')
        return raw
    def json(self,d,cap=8*2**20):return H.parse(self.read(d,cap))


def public_fixture(planned, fingerprint, manifest, physical_query_order=None):
    out = {k:np.asarray(planned[k]) for k in (*H.AXES,'train_condition_ids','eval_condition_ids','bin_left_edges_ms')}
    # Real opaque exports preserve the original float64 grid, while planned JSON remains integers.
    if fingerprint != H.SOURCE_FP: out['bin_left_edges_ms'] = np.asarray(planned['bin_left_edges_ms'], dtype=np.float64)
    q = np.arange(574,dtype=np.uint16) if physical_query_order is None else np.asarray(physical_query_order,dtype=np.uint16)
    out.update(train_counts_heldin=np.broadcast_to(np.zeros((1,1,1),dtype=np.uint8),(1721,140,137)),
        train_counts_heldout=np.broadcast_to(np.zeros((1,1,1),dtype=np.uint8),(1721,140,45)),
        eval_counts_heldin=np.broadcast_to(q[:,None,None],(574,140,137)),
        eval_valid_mask=np.broadcast_to(np.asarray(True),(574,140,45)),
        panel_fingerprint=np.asarray(fingerprint),source_manifest_sha256=np.asarray(manifest))
    return out


class HandoffControls(unittest.TestCase):
    def make(self):
        selected,docs,seed=fixture(); selected,captured=pack(selected,docs)
        made=H.prepare(selected,captured); inputs=Inputs(selected,captured,made,seed)
        compiled=C.compile_opaque_s03(selected,inputs.pins)
        return selected,docs,seed,captured,made,inputs,compiled

    def test_full_metadata_membership_order_and_chronology(self):
        selected,docs,seed,captured,made,inputs,compiled=self.make()
        before=H.canonical(docs)
        for axis,size in H.AXES.items():
            self.assertEqual(made['support'][axis],sorted(docs['private_binding']['core']['axes'][axis]['opaque_in_source_order']))
            self.assertEqual(len(made['support'][axis]),size)
        mapping=dict(zip(docs['original_support']['eval_trial_ids'],docs['private_binding']['core']['axes']['eval_trial_ids']['opaque_in_source_order']))
        self.assertEqual(made['support']['chronological_eval_trial_ids'],[mapping[x] for x in docs['original_support']['chronological_eval_trial_ids']])
        aliases=docs['private_binding']['core']['axes']['train_trial_ids']['opaque_in_source_order']
        for name in ('fit_indices','validation_indices'):
            self.assertEqual({made['support']['train_trial_ids'][i] for i in made['split'][name]},
                             {aliases[i] for i in docs['original_split'][name]})
            self.assertEqual(made['split'][name],sorted(made['split'][name]))
        self.assertEqual(made['split']['descriptor'],docs['original_split']['descriptor'])
        self.assertEqual(H.canonical(docs),before)

    def test_metadata_bytes_and_axis_order_authentication(self):
        selected,docs,seed,captured,made,inputs,compiled=self.make()
        bad=dict(captured);bad['original_split']+=b' '
        with self.assertRaises(ValueError):H.prepare(selected,bad)
        docs['private_binding']['core']['axes']['eval_trial_ids']['source'].reverse()
        selection,raw=pack(selected,docs)
        with self.assertRaises(ValueError):H.prepare(selection,raw)
        selected,docs,seed=fixture()
        values=docs['private_binding']['core']['axes']['eval_trial_ids']['opaque_in_source_order']
        values[-1]=values[0]
        selection,raw=pack(selected,docs)
        with self.assertRaises(ValueError):H.prepare(selection,raw)
        selected,docs,seed=fixture();del docs['original_support']['train_condition_ids']
        selection,raw=pack(selected,docs)
        with self.assertRaises(ValueError):H.prepare(selection,raw)

    def test_original_split_and_seed_roles_refuse(self):
        selected,docs,seed=fixture();docs['original_split']['fit_indices'][0]=True
        selected,raw=pack(selected,docs)
        with self.assertRaises(ValueError):H.prepare(selected,raw)
        selected,docs,seed=fixture();docs['original_split']['descriptor']['source_split_sha256']='0'*64
        selected,raw=pack(selected,docs)
        with self.assertRaises(ValueError):H.prepare(selected,raw)
        selected,docs,seed=fixture();docs['private_binding']['core']['key_sha256']=docs['original_shuffle']['seed_sha256']
        selected,raw=pack(selected,docs)
        with self.assertRaises(ValueError):H.prepare(selected,raw)

    def test_original_donor_pairs_survive_opaque_permutation(self):
        selected,docs,seed,captured,made,inputs,compiled=self.make()
        q=np.arange(574)[::-1]
        public=public_fixture(made['support'],selected['opaque_fingerprint'],docs['private_binding']['public_manifest_sha256'],q)
        public['panel_fingerprint']=selected['opaque_fingerprint']
        actual=H.mapping_for_s03(compiled['request']['body'],inputs,public,made['support'],seed,made['shuffle'])
        original=V.shuffle_map(seed,docs['original_support'],docs['original_shuffle'])
        self.assertTrue(np.array_equal(q[actual],original[q]))
        fresh={**docs['original_shuffle'],'planned_support_sha256':H.digest(H.canonical(made['support']))}
        changed=V.shuffle_map(seed,made['support'],fresh)
        self.assertFalse(np.array_equal(actual,changed),'A fresh opaque-seeded draw is a different control')
        self.assertEqual(sorted(actual.tolist()),list(range(574)))

    def test_cross_export_and_changed_handoff_refuse(self):
        selected,docs,seed,captured,made,inputs,compiled=self.make()
        public=public_fixture(made['support'],'f'*64,docs['private_binding']['public_manifest_sha256'])
        public['panel_fingerprint']='f'*64
        with self.assertRaises(ValueError):H.mapping_for_s03(compiled['request']['body'],inputs,public,made['support'],seed,made['shuffle'])
        made['handoff']['opaque_split_sha256']='0'*64
        inputs=Inputs(selected,captured,made,seed);compiled=C.compile_opaque_s03(selected,inputs.pins)
        public['panel_fingerprint']=selected['opaque_fingerprint']
        with self.assertRaises(ValueError):H.mapping_for_s03(compiled['request']['body'],inputs,public,made['support'],seed,made['shuffle'])

    def test_compiler_exact_original_role_roster_and_holds(self):
        selected,docs,seed,captured,made,inputs,compiled=self.make()
        self.assertEqual(compiled['stage'],'S03');self.assertEqual(compiled['action']['job'],'prepare/views')
        self.assertEqual(compiled['request']['role'],'project_views')
        self.assertEqual(compiled['conditions'],list(P.CONDITIONS))
        self.assertEqual(len(compiled['outputs']),12)
        self.assertFalse(compiled['full_campaign_compiled']);self.assertFalse(compiled['E_products_issued'])
        self.assertFalse(compiled['downstream_physical_target_scoring_adopted'])
        self.assertEqual({x['pin']['path'] for x in compiled['initial_artifacts']},
                         {p['path']for p in selected['inputs'].values()}|{p['path']for p in inputs.pins.values()})
        bad=dict(inputs.pins);bad['support']=selected['inputs']['opaque_public']
        with self.assertRaises(ValueError):C.compile_opaque_s03(selected,bad)

    def run_worker(self, opaque):
        selected,docs,seed,captured,made,inputs,compiled=self.make()
        if opaque:
            planned=made['support'];fp=selected['opaque_fingerprint'];namespace=docs['private_binding']['public_manifest_sha256'];q=np.arange(574)[::-1]
            request=compiled['request'];expected_donor=V.shuffle_map(seed,docs['original_support'],docs['original_shuffle'])
            expected_query=expected_donor[q]
        else:
            planned=docs['original_support'];fp=H.SOURCE_FP;namespace=H.SOURCE_MANIFEST;q=np.arange(574)
            request={'role':'project_views','body':{'public':selected['inputs']['opaque_public'],
                'planned_support':selected['inputs']['original_support'],
                'shuffle_commitment':selected['inputs']['original_shuffle'],
                'protected_shuffle_seed':selected['inputs']['protected_shuffle_seed']}}
            expected_query=V.shuffle_map(seed,planned,docs['original_shuffle'])
        public=public_fixture(planned,fp,namespace,q);pending={};observed={};serial=[0]
        def dump(arrays,*a,**k):
            token=('generated-array-%d'%serial[0]).encode();serial[0]+=1
            info={'keys':set(arrays),'shapes':{name:np.asarray(value).shape for name,value in arrays.items()}}
            if 'eval_counts_heldin'in arrays:info['query_trial_values']=arrays['eval_counts_heldin'][:,0,0].copy()
            if 'train_count_totals'in arrays:info['opportunities']=int(arrays['train_bin_opportunities'])
            if 'donor_index'in arrays:info['donor_index']=arrays['donor_index'].copy()
            pending[token]=info;return token
        class Outputs:
            def write(self,name,raw,cap):
                observed[name]=pending.pop(raw)if raw in pending else {'json':H.parse(raw)}
                return desc('generated-output/'+name,raw)
        with patch.object(A,'load_arrays',side_effect=lambda raw,*a,**k:dict(public)),patch.object(A,'dump_arrays',side_effect=dump):
            products=W.execute(request,inputs,Outputs(),lambda event:None)
        self.assertEqual(len(products),12)
        for condition in P.CONDITIONS:
            t=observed[condition+'_training.npz'];v=observed[condition+'_query.npz']
            if condition=='training_rate_only':self.assertEqual(t['opportunities'],1721*140)
            else:self.assertEqual(t['shapes']['train_counts_heldout'],(1721,140,45))
            self.assertEqual(v['shapes']['eval_trial_ids'],(574,))
            if condition in ('context_only','training_rate_only'):
                self.assertNotIn('eval_counts_heldin',v['keys']);self.assertNotIn('train_counts_heldin',t['keys'])
            elif condition=='within_condition_shuffle':np.testing.assert_array_equal(v['query_trial_values'],expected_query)
            else:np.testing.assert_array_equal(v['query_trial_values'],q)
        self.assertEqual(observed['support.json']['json']['panel_fingerprint'],fp)

    def test_original_worker_branch_unchanged_full_five_views(self):self.run_worker(False)
    def test_opaque_worker_branch_full_five_views(self):self.run_worker(True)

    def metadata_cli(self, wrong_source=False, short_response=False):
        selected,docs,seed,captured,made,inputs,compiled=self.make()
        selection_raw=H.canonical(selected); selection_pin=desc('operator/selection.json',selection_raw)
        available={selected['inputs'][k]['path']:v for k,v in captured.items()}
        available[selection_pin['path']]=selection_raw
        class ShortOutput(io.BytesIO):
            def write(self,body):return super().write(body[:-1])
        reads=[];writes={};directories=[]
        out=types.SimpleNamespace(buffer=ShortOutput() if short_response else io.BytesIO())
        class Node:
            def __init__(self,name):self.name=name;self.parent=self
            def is_dir(self):return True
            def exists(self):return False
            def mkdir(self,mode):directories.append((self.name,mode))
        class Store:
            def __init__(self,*args):pass
            def read(self,d,cap):
                reads.append(d['path']);raw=available[d['path']]
                if len(raw)>cap or desc(d['path'],raw)!=d:raise ValueError('pinned metadata only')
                return raw
            def path(self,name):return Node(name)
            def write(self,name,raw,cap):
                if name in writes or len(raw)>cap:raise ValueError('exclusive bounded metadata output')
                writes[name]=raw;return desc(name,raw)
        bootstrap={'manifest_sha256':'0'*64 if wrong_source else selected['source_manifest']['sha256']}
        argv=['--root','/generated/owned-study','--selection',selection_pin['path'],
              '--selection-bytes',str(selection_pin['bytes']),'--selection-sha256',selection_pin['sha256'],
              '--output-prefix','opaque-meta']
        error=None
        with patch.object(modules['contracts'],'Store',Store),patch.object(sys,'stdout',out), \
             patch.object(sys,'_nlb017_bootstrap',bootstrap,create=True):
            try:H.main(argv)
            except ValueError as exc:error=exc
        return selected,reads,writes,directories,out.buffer.getvalue(),error

    def test_metadata_cli_captures_only_five_pinned_documents(self):
        selected,reads,writes,dirs,out,error=self.metadata_cli()
        self.assertIsNone(error)
        self.assertEqual(set(reads),{'operator/selection.json'}|{selected['inputs'][k]['path']for k in H.META})
        self.assertNotIn(selected['inputs']['opaque_public']['path'],reads)
        self.assertNotIn(selected['inputs']['protected_shuffle_seed']['path'],reads)
        self.assertEqual(len(writes),5);self.assertEqual(dirs,[('opaque-meta',0o700)])
        result=json.loads(out);self.assertFalse(result['array_operation_performed'])
        self.assertFalse(result['benchmark_ready'])
        self.assertEqual(json.loads(writes['opaque-meta/S03_COMPILATION.json'])['conditions'],list(P.CONDITIONS))

    def test_metadata_cli_wrong_bootstrap_refuses_before_input_capture(self):
        selected,reads,writes,dirs,out,error=self.metadata_cli(wrong_source=True)
        self.assertIsNotNone(error);self.assertEqual(reads,['operator/selection.json'])
        self.assertEqual(writes,{});self.assertEqual(dirs,[]);self.assertEqual(out,b'')

    def test_metadata_cli_short_response_refuses_with_outputs_retained(self):
        selected,reads,writes,dirs,out,error=self.metadata_cli(short_response=True)
        self.assertIsNotNone(error);self.assertIn('Complete bounded metadata response',str(error))
        self.assertEqual(len(writes),5);self.assertTrue(out)
        self.assertFalse(out.endswith(b'\n'))


def original_fixture():
    # Generated metadata only. Pad to the fixed source extents; patch only source
    # hashes in controls, never claim these bytes authenticate the real dataset.
    raw = {'schema_version':1,'dandiset_version':'000128/0.220113.0400',
        'asset_id':'26e85f09-39b7-480f-b337-278a8f034007',
        'source_sha256':'a27f84f9c31f077011062fd99a6ced199fdf19e656151f056c3c6244a408a3c4',
        'selection_before_spike_values':True,'all_source_trial_ids_present':True,
        'observation_masks_identical_within_partition':True,'fixed_bin_ms':5,
        'fixed_relative_left_edges_ms':list(range(-250,450,5)),
        'heldin_unit_ids':list(range(137)), 'heldout_unit_ids':list(range(137,182)),
        'selected_trials':[{'row':i,'trial_id':100000-3*i,'split':'train' if i<1721 else 'val',
                            'condition':[i%7,i%2]} for i in range(2295)]}
    d0 = {'schema_version':1,'candidate_id':'NEURAL-017','train_trial_count':1721,
        'inner_validation_count':340,'inner_fit_count':1381,'regenerate_with_new_numpy_version':False,
        'inner_validation_trial_ids':['train-nwb:trial-'+str(100000-3*i) for i in range(0,1700,5)],
        'source':desc('original/method.md',b'generated retained source declaration'),
        'source_rule':{'seed':20261030,'final_validation_order':'ascending original training row index'}}
    return raw,d0


def original_pack(raw,d0):
    bodies={}
    for role,doc,extent in [('raw_selection',raw,601926),('raw_D0',d0,10425)]:
        body=H.canonical(doc);assert len(body)<=extent
        bodies[role]=body+b' '*(extent-len(body))
    selected={'schema':'NLB017_original_S03_metadata_selection_v1',
        'source_manifest':desc('source/SOURCE_MANIFEST.json',b'generated captured source'),
        'inputs':{role:desc('private/'+role+'.json',body) for role,body in bodies.items()},
        'numpy_version':np.__version__,'shuffle_status':'prospectively_selected_no_historical_commitment_claim'}
    selected['inputs']['protected_shuffle_seed']=desc('private/selected-shuffle-seed.bin',b'x'*32)
    return selected,bodies


class OriginalMetadataControls(unittest.TestCase):
    def run_original(self,raw,d0):
        selected,bodies=original_pack(raw,d0)
        with patch.object(H,'SOURCE_MANIFEST',selected['inputs']['raw_selection']['sha256']), \
             patch.object(H,'D0',selected['inputs']['raw_D0']['sha256']):
            made=H.original_metadata(selected,bodies)
        return selected,bodies,made

    def test_original_projection_preserves_physical_ids_D0_and_order(self):
        raw,d0=original_fixture();selected,bodies,made=self.run_original(raw,d0)
        support=made['original_support'];split=made['original_split'];shuffle=made['original_shuffle']
        self.assertEqual(support['train_trial_ids'][0],'train-nwb:trial-100000')
        self.assertEqual(support['eval_trial_ids'][0],'train-nwb:trial-'+str(100000-3*1721))
        self.assertEqual(support['chronological_eval_trial_ids'],support['eval_trial_ids'])
        self.assertNotEqual(support['chronological_eval_trial_ids'],sorted(support['eval_trial_ids']))
        self.assertEqual([support['train_trial_ids'][i] for i in split['validation_indices']],d0['inner_validation_trial_ids'])
        self.assertEqual(split['validation_indices'],list(range(0,1700,5)))
        self.assertEqual(len(split['fit_indices']),1381)
        self.assertEqual(split['descriptor']['source_split'],selected['inputs']['raw_D0'])
        self.assertEqual(split['descriptor']['original_source_rule'],d0['source_rule'])
        self.assertEqual(support['train_condition_ids'][1],'[1,1]')
        self.assertEqual(support['heldout_unit_ids'][0],'Jenkins-20090925:unit-137')
        self.assertEqual(shuffle['planned_support_sha256'],H.digest(H.canonical(support)))
        self.assertEqual(shuffle['rule'],P.SHUFFLE_RULE)
        self.assertEqual(shuffle['numpy_version'],np.__version__)

    def test_original_projection_refuses_reselection_missing_duplicate_and_wrong_order(self):
        for kind in ('duplicate','assessment','reordered','row','split','condition','reselect'):
            with self.subTest(kind=kind):
                raw,d0=original_fixture()
                if kind=='duplicate':d0['inner_validation_trial_ids'][-1]=d0['inner_validation_trial_ids'][0]
                elif kind=='assessment':d0['inner_validation_trial_ids'][-1]='train-nwb:trial-'+str(100000-3*2294)
                elif kind=='reordered':d0['inner_validation_trial_ids'].reverse()
                elif kind=='row':raw['selected_trials'][0]['row']=raw['selected_trials'][1]['row']
                elif kind=='split':raw['selected_trials'][1720]['split']='val'
                elif kind=='condition':raw['selected_trials'][0]['condition']=[True,1]
                else:d0['regenerate_with_new_numpy_version']=True
                with self.assertRaises(ValueError):self.run_original(raw,d0)

    def test_original_capture_refuses_changed_bytes_or_historical_claim(self):
        raw,d0=original_fixture();selected,bodies=original_pack(raw,d0)
        with patch.object(H,'SOURCE_MANIFEST',selected['inputs']['raw_selection']['sha256']), \
             patch.object(H,'D0',selected['inputs']['raw_D0']['sha256']):
            wrong=dict(bodies);wrong['raw_D0']=bodies['raw_D0'][:-1]+b'x'
            with self.assertRaises(ValueError):H.original_metadata(selected,wrong)
            selected['shuffle_status']='historically_frozen'
            with self.assertRaises(ValueError):H.original_metadata(selected,bodies)

    def test_original_cli_only_reads_two_sources_and_retains_outputs_on_short_response(self):
        for short in (False,True):
            with self.subTest(short=short):
                raw,d0=original_fixture();selected,bodies=original_pack(raw,d0)
                selection_raw=H.canonical(selected);pin=desc('operator/original-selection.json',selection_raw)
                available={selected['inputs'][k]['path']:v for k,v in bodies.items()};available[pin['path']]=selection_raw
                reads=[];writes={};dirs=[]
                class Node:
                    def __init__(self,name):self.name=name;self.parent=self
                    def is_dir(self):return True
                    def exists(self):return False
                    def mkdir(self,mode):dirs.append((self.name,mode))
                class Store:
                    def __init__(self,*args):pass
                    def read(self,d,cap):
                        reads.append(d['path']);body=available[d['path']]
                        if len(body)>cap or desc(d['path'],body)!=d:raise ValueError('exact generated capture')
                        return body
                    def path(self,name):return Node(name)
                    def write(self,name,body,cap):
                        if name in writes or len(body)>cap:raise ValueError('bounded exclusive output')
                        writes[name]=body;return desc(name,body)
                class Output(io.BytesIO):
                    def write(self,body):return super().write(body[:-1] if short else body)
                out=types.SimpleNamespace(buffer=Output())
                argv=['--root','/generated/study','--selection',pin['path'],'--selection-bytes',str(pin['bytes']),
                    '--selection-sha256',pin['sha256'],'--output-prefix','original-meta']
                with patch.object(H,'SOURCE_MANIFEST',selected['inputs']['raw_selection']['sha256']), \
                     patch.object(H,'D0',selected['inputs']['raw_D0']['sha256']), \
                     patch.object(modules['contracts'],'Store',Store),patch.object(sys,'stdout',out), \
                     patch.object(sys,'_nlb017_bootstrap',{'manifest_sha256':selected['source_manifest']['sha256']},create=True):
                    if short:
                        with self.assertRaisesRegex(ValueError,'Complete bounded original metadata response'):H.original_main(argv)
                    else:self.assertEqual(H.original_main(argv),0)
                self.assertEqual(set(reads),{pin['path']}|{selected['inputs'][k]['path']for k in ('raw_selection','raw_D0')})
                self.assertEqual(len(writes),3);self.assertEqual(dirs,[('original-meta',0o700)])
                self.assertNotIn(selected['inputs']['protected_shuffle_seed']['path'],reads)
                if not short:
                    result=json.loads(out.buffer.getvalue());self.assertFalse(result['historical_shuffle_commitment_claimed'])
                    self.assertFalse(result['array_or_shuffle_operation_performed'])
                else:self.assertFalse(out.buffer.getvalue().endswith(b'\n'))


if __name__=='__main__':unittest.main(verbosity=2)
