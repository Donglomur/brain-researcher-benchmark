"""Generated metadata and inert state-machine controls; zero fixture file writes."""
from copy import deepcopy
import hashlib
import importlib.util
import math
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name,path)
    loaded = importlib.util.module_from_spec(spec); spec.loader.exec_module(loaded); return loaded


r = module('generated_matched_recipe',HERE/'recipe.py')
n = module('generated_matched_native',HERE/'native.py')
old_path = HERE.parent/'opaque-submission-v1/tests/test_adapter.py'
assert hashlib.sha256(old_path.read_bytes()).hexdigest() == 'de716dd790fa9e6e9456e5e66dfd0ccf1a068813a17dde26fd7734095a1dbbcf'
old = module('generated_predecessor_fixture',old_path)
INFO = old.INFOS[0]


class InertBackend:
    """Integer states and generated validation numbers; no tensors or fitted model."""
    def __init__(self, policy):
        self.policy = policy; self.state = [0]; self.selected = None; self.transitions = []; self.scheduler = []
    def begin_stage(self,spec): self.stage = spec['name']; self.transitions.append((self.stage,self.state[0]))
    def train_epoch(self,epoch): self.epoch = epoch; self.state[0] += 1
    def validation_metrics(self):
        ba = self.policy(self.stage,self.epoch)
        return {'accuracy':0.3,'balanced_accuracy':ba}
    def snapshot_selected(self): self.selected = self.state.copy()
    def step_scheduler(self,accuracy): self.scheduler.append((self.stage,self.epoch,accuracy))
    def restore_selected(self): self.state = self.selected.copy()


def inert_receipt():
    backend = InertBackend(lambda stage,epoch:(epoch+1)/100)
    result = r.drive_fit(backend)
    audit = [{'stage':row['stage'],'epoch':row['epoch'],'presentations':6300,'step_attempts':197,
              'order_identity':'a'*64,'initial_rng':'b'*64,'final_rng':'c'*64} for row in result['history']]
    doc = {**result,'schema':'reve-matched-fit-receipt-v1','recipe':r.reference_spec(42),
           'materials_identity':INFO['materials_identity'],'data_identity':INFO['data_identity'],
           'checkpoint':{'bytes':100,'sha256':'d'*64},'audit':audit,'initial_rng':'e'*64,'final_rng':'f'*64,
           'attention_profile':'native_sdpa_dispatch','runtime':{'torch':'generated','numpy':'generated','safetensors':'generated'},
           'initial_head_identity':'1'*64,'reuse_policy':'operator_reference_only_same_data_identity_across_both_primary_conditions',
           'historical_classifier_authenticated':False,'scientific_qualification':False}
    doc['identity'] = r.identity(doc); return doc


def repin(doc):
    doc.pop('identity',None);doc['identity']=r.identity(doc);return doc


def common_files():
    return {'encoder.safetensors':old.a.ENCODER,'encoder-config.json':r.CONFIG_PIN,
            'ENCODER_ARCHITECTURE.json':r.ARCHITECTURE_PIN,'MODEL_LICENSE.txt':r.LICENSE_PIN}


def primary_pair():
    packets = []; programs = []
    for i,info in enumerate(old.INFOS):
        sizes = {row['signal']:math.prod(row['shape'])*8+128 for row in info['records']}
        packets.append(old.a.packet_mount(info,Path('/generated')/info['condition'],info['manifest_pin'],sizes))
        programs.append({'path':f'/generated/program{i}','kind':'directory','purpose':'program',
                         'files':{'solution.py':old.a.pin(b'inert unexecuted generated program')}})
    return r.primary_requests(old.INFOS,packets,programs,r.primary_common('/generated/common',common_files()),
        phase_ids=['primaryA','primaryB'],image='sha256:'+'d'*64,exposure_pins=[old.a.pin(b'A'),old.a.pin(b'B')],
        origin=time.monotonic(),deadline=time.monotonic()+120,resources=old.resources())


class RecipeControls(unittest.TestCase):
    def test_exact_source_tensor_dimensions(self):
        self.assertEqual(r.validate_shapes(r.pretrained_shapes()),{'tensor_count':140,'parameters':69189632})
        self.assertEqual(r.validate_shapes(r.classifier_shapes(),complete_classifier=True),{'tensor_count':143,'parameters':69847556})
        self.assertEqual(512+r.FLAT+4*r.FLAT+4,658436)
    def test_encoder_only_is_not_a_classifier(self):
        with self.assertRaises(r.Refusal):r.validate_shapes(r.pretrained_shapes(),complete_classifier=True)
    def test_wrong_query_or_head_shape_refused(self):
        for key in ('cls_query_token','linear_head.3.weight'):
            shapes=r.classifier_shapes();shapes[key]=[4,512]
            with self.assertRaises(r.Refusal):r.validate_shapes(shapes,complete_classifier=True)
    def test_recipe_preserves_consumed_source_and_declares_changes(self):
        spec=r.reference_spec(42)
        self.assertEqual((spec['dropout'],spec['mixup'],spec['grad_scaler_enabled']),(0.0,False,False))
        self.assertEqual(spec['optimizer']['betas'],[0.92,0.999]);self.assertEqual(spec['optimizer']['eps'],1e-9)
        self.assertEqual((spec['patches_per_channel'],spec['unused_final_samples']),(4,60))
        self.assertIn('8persistent',spec['loader_deviation']);self.assertFalse(spec['historical_Table12_equivalent'])
    def test_unregistered_or_boolean_seed_refused(self):
        for seed in (True,0,142):
            with self.assertRaises(r.Refusal):r.reference_spec(seed)
    def test_paired_work_plan_full_and_unadmitted(self):
        plan=r.work_plan();self.assertEqual(len(plan['fits']),40)
        for condition in ('paper_data','paper_data_code'):
            rows=[row for row in plan['fits'] if row['condition']==condition]
            self.assertEqual(sum(row['held_predictions_after_freeze'] for row in rows),18030)
            self.assertEqual(sum(row['train_presentation_cap'] for row in rows),3150000)
        self.assertTrue(all(v is None for v in plan['hardware_and_agent_budgets'].values()))
    def test_maximum_source_horizon_and_scheduler(self):
        backend=InertBackend(lambda stage,epoch:(epoch+1)/100);result=r.drive_fit(backend)
        self.assertEqual((result['validation_panels'],result['training_presentations']),(25,157500))
        self.assertEqual(backend.transitions,[('lp',0),('ft',20)])
        self.assertEqual(backend.scheduler, [('lp',i,0.3) for i in range(6,20)]+[('ft',i,0.3) for i in range(1,5)])
    def test_final_lp_not_best_lp_starts_fine_tuning(self):
        backend=InertBackend(lambda stage,epoch:0.9 if stage=='lp' and epoch==0 else 0.2)
        result=r.drive_fit(backend)
        self.assertEqual(backend.transitions,[('lp',0),('ft',7)])
        self.assertEqual((result['selected_stage'],result['selected_epoch']),('ft',0))
        self.assertEqual(backend.state,[8])
    def test_source_retains_lp_best_if_ft_never_positive(self):
        backend=InertBackend(lambda stage,epoch:0.9 if stage=='lp' else 0)
        result=r.drive_fit(backend)
        self.assertEqual((result['selected_stage'],result['selected_epoch']),('lp',0));self.assertEqual(backend.state,[1])
    def test_no_positive_checkpoint_refused(self):
        backend=InertBackend(lambda stage,epoch:0)
        with self.assertRaises(r.Refusal):r.drive_fit(backend)
        self.assertEqual(backend.transitions,[('lp',0),('ft',6)])
    def test_ties_do_not_replace_state_and_patience_is_strict(self):
        control=r.StageController('lp');self.assertTrue(control.observe(accuracy=.9,balanced_accuracy=.4)['save_best'])
        for _ in range(5):self.assertFalse(control.observe(accuracy=.9,balanced_accuracy=.4)['stop'])
        self.assertTrue(control.observe(accuracy=.9,balanced_accuracy=.4)['stop'])
        with self.assertRaises(r.Refusal):control.observe(accuracy=.9,balanced_accuracy=.5)
    def test_nonfinite_and_out_of_range_validation_refused(self):
        for value in (float('nan'),float('inf'),-.1,1.1,True):
            with self.assertRaises(r.Refusal):r.StageController('ft').observe(accuracy=.2,balanced_accuracy=value)
    def test_fit_excludes_test_data_and_preserves_all_permitted_labels(self):
        rows=r.phase_data(INFO,'fit');self.assertEqual(sum(len(x['labels']) for x in rows),8034)
        self.assertEqual({x['split'] for x in rows},{'train','val'})
        self.assertEqual(len(n.PacketDataset('/generated',rows,'train',object())),6300)
        self.assertEqual(len(n.PacketDataset('/generated',rows,'val',object())),1734)
    def test_complete_opaque_prediction_phase(self):
        rows=r.phase_data(INFO,'predict');self.assertEqual(len(rows),1803)
        self.assertTrue(all('labels' not in row and 'participant' not in row for row in rows))
        result={'schema':'reve-candidate-predictions-v1','materials_identity':INFO['materials_identity'],
                'predictions':[{'event_id':eid,'scores':[i+.1,i+.2,i+.3,i+.4]} for i,eid in enumerate(INFO['test_ids'])]}
        self.assertEqual(len(old.a.admit_result(result,INFO)['predictions']),1803)
    def test_test_labels_and_incomplete_phase_refused(self):
        info=deepcopy(INFO);info['records'][-1]['labels']=[0]
        with self.assertRaises(r.Refusal):r.phase_data(info,'predict')
        info=deepcopy(INFO);info['records'].pop()
        with self.assertRaises(r.Refusal):r.phase_data(info,'predict')


class AccessAndReceiptControls(unittest.TestCase):
    def test_exact_literal_access_pair(self):
        pair=primary_pair()
        self.assertEqual(pair[0]['mounts']['/common'],pair[1]['mounts']['/common'])
        self.assertEqual(set(pair[0]['mounts']['/common']['files']),r.PRIMARY_FILES)
        self.assertNotIn('official-code.tar.gz',pair[0]['mounts']['/input']['files'])
        self.assertIn('official-code.tar.gz',pair[1]['mounts']['/input']['files'])
        self.assertEqual(pair[0]['request']['resources'],pair[1]['request']['resources'])
        self.assertFalse(pair[0]['runtime_qualified'])
    def test_assisted_encoder_runtime_is_rejected(self):
        files=common_files();files['encoder-runtime.py']=old.a.pin(b'author source')
        with self.assertRaises(r.Refusal):r.primary_common('/generated',files)
    def test_disguised_source_in_neutral_asset_rejected(self):
        for name in ('encoder-config.json','MODEL_LICENSE.txt','ENCODER_ARCHITECTURE.json'):
            files=deepcopy(common_files());files[name]=old.a.pin(b'embedded executable source')
            with self.assertRaises(r.Refusal):r.primary_common('/generated',files)
    def test_pinned_benchmark_architecture_cannot_mutate(self):
        with patch.object(Path,'read_bytes',return_value=b'foreign source'):
            with self.assertRaises(r.Refusal):r.primary_common('/generated',common_files())
    def test_complete_selected_fit_metadata_admission(self):
        doc=inert_receipt();self.assertIs(r.validate_fit_receipt(doc,INFO,doc['identity']),doc)
        self.assertIs(r.validate_fit_receipt(doc,old.INFOS[1],doc['identity']),doc)
    def test_self_hash_without_selected_identity_refused(self):
        doc=inert_receipt()
        with self.assertRaises(r.Refusal):r.validate_fit_receipt(doc,INFO,'0'*64)
    def test_changed_recipe_or_receipt_field_refused(self):
        for change in ('schema','recipe','reuse_policy','historical_classifier_authenticated'):
            doc=inert_receipt()
            if change=='recipe':doc['recipe']['dropout']=.5
            else:doc[change]=True if change=='historical_classifier_authenticated' else 'foreign'
            repin(doc)
            with self.assertRaises(r.Refusal):r.validate_fit_receipt(doc,INFO,doc['identity'])
    def test_stage_checkpoint_and_work_trace_tampering_refused(self):
        for change in ('selected_epoch','training_presentations','validation_panels'):
            doc=inert_receipt();doc[change]+=1;repin(doc)
            with self.assertRaises(r.Refusal):r.validate_fit_receipt(doc,INFO,doc['identity'])
        doc=inert_receipt();doc['history'][0]['save_best']=False;repin(doc)
        with self.assertRaises(r.Refusal):r.validate_fit_receipt(doc,INFO,doc['identity'])
    def test_native_entrypoints_refuse_before_import_or_access(self):
        with patch.object(n,'load_source',side_effect=AssertionError('native import')),patch.object(n,'file_pin',side_effect=AssertionError('file read')):
            for call in (lambda:n.NativeReference(source='',encoder_path='',packet_root='',fit_rows=[],seed=42),
                         lambda:n.fit_reference(info={},packet_root='',source='',encoder_path='',seed=42,checkpoint_output=''),
                         lambda:n.predict_selected(info={},packet_root='',source='',checkpoint_path='',fit_receipt={},expected_fit_identity='')):
                with self.assertRaises(ValueError):call()
    def test_source_import_has_not_loaded_scientific_packages(self):
        self.assertTrue(all(name not in sys.modules for name in ('torch','numpy','safetensors')))
    def test_validation_accuracy_is_distinct_from_balanced_accuracy(self):
        class Values:
            def __init__(self,values):self.values=values
            def tolist(self):return self.values
            def argmax(self,dim):return self
        backend=n.NativeReference.__new__(n.NativeReference)
        labels=[0]*1000+[1]*500+[2]*200+[3]*34
        backend._decisions=lambda loader:iter([(None,Values(labels),Values([0]*1734))])
        backend.val_loader=object()
        self.assertEqual(backend.validation_metrics(),{'accuracy':1000/1734,'balanced_accuracy':.25})
    def test_validation_missing_class_is_rejected(self):
        class Values:
            def tolist(self):return [0]*1734
            def argmax(self,dim):return self
        backend=n.NativeReference.__new__(n.NativeReference)
        backend._decisions=lambda loader:iter([(None,Values(),Values())]);backend.val_loader=object()
        with self.assertRaises(ValueError):backend.validation_metrics()


if __name__=='__main__':
    try: unittest.main(verbosity=2)
    finally: print('Generated fixture logical writes: 0 bytes; no native/model/data/scoring execution.')
