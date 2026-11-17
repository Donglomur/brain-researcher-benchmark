"""Local route controls: ROS/classifier doubles are explicit; no real-ROS parity claim."""
import ast
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import warnings

import _control_support as support
from _control_support import route, PipelineTrace, run_source, assert_trace_pair

ROUTE_SHA='0a805257cee463aadab9627f39af4c09b5cdf5509c6e0d2852c6975b93eaa5aa'
GENERATED_FILE_BYTES=0


class CurrentRouteControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if hashlib.sha256((support.COMPONENT/'route.py').read_bytes()).hexdigest()!=ROUTE_SHA:
            raise AssertionError('reviewed route bytes changed')
        cls.temporary=tempfile.TemporaryDirectory(prefix='generated-nuclr-route-')
        cls.root=Path(cls.temporary.name).resolve()
        cls.protected=cls.root/'original'; cls.protected.mkdir()
        cls.sidecars=cls.root/'sidecars'; cls.sidecars.mkdir()
        _,_,cls.reader,cls.native,cls.source=route._dependencies(support.IMPLEMENTATIONS)
        cls.guards=[]
        for name in ('NativeArray','prepare_source','inspect_session','session_neurons','read_prepared_block'):
            guard=patch.object(cls.native,name,side_effect=AssertionError('no neural array/preparation operation'))
            guard.start(); cls.guards.append(guard)
        manifest,joined,completion=support.full_generated_documents(cls.reader)
        cls.original_hashes=(route.digest(manifest),route.digest(joined))
        cls.binding=route.bind_generated_control_metadata(manifest=manifest,joined=joined,completion=completion,
            protected_run_root=cls.protected,implementation_root=support.IMPLEMENTATIONS)
        cls.selection=route.select_current_route(cls.binding,label_level='ei',panel='transductive')
        cls.ids=list(cls.selection._joined_record['ordered_ids'])
        cls.checkpoints=[]
        for epoch in (2,10,100):
            cls.checkpoints.append({'id':f'epoch_{epoch}','epoch':epoch,'ids':list(cls.ids),
                'embeddings':[[float(index)+0.123456789,float((index%7)*3)+0.234567891] for index in range(len(cls.ids))]})
        cls.built=route.build_current_route_packet(cls.selection,cls.checkpoints,input_role='generated_engineering_control',
            context_variant='population_context',representation_training_sessions=sorted(cls.binding._inputs.sessions))

    @classmethod
    def tearDownClass(cls):
        for guard in reversed(cls.guards): guard.stop()
        cls.temporary.cleanup()
        print('LOCAL_ROUTE_CONTROL_ACCOUNTING='+json.dumps({'fixture_bytes_written':GENERATED_FILE_BYTES,
            'retained_fixture_bytes':0,'real_RandomOverSampler_executed':False,
            'real_classifier_fit_executed':False,'native_arrays_read':False,
            'source_differential_scope':'literal source AST and unchanged evaluator under common labelled doubles; actual NumPy scaling',
            'route_sha256':hashlib.sha256((support.COMPONENT/'route.py').read_bytes()).hexdigest()}))

    def test_pinned_definition_and_metadata_only_selection_preserve_all_records(self):
        definition=route.route_definition()
        self.assertEqual(definition['root_decision_sha256'],'b477b1593d03f9fd3adba3bbeb6c0dd57fdcead6920e533bb243445786802adc')
        receipt=self.selection.receipt
        self.assertEqual(receipt['phase'],'selected_no_fit')
        self.assertEqual(receipt['metadata_binding_role'],'generated_control_metadata_only')
        self.assertEqual(len(receipt['original_panel_inventory']),9)
        self.assertEqual(sum(not x['matches_registered_topology'] for x in receipt['original_panel_inventory']),1)
        self.assertTrue(receipt['legacy_transductive_source_route_unresolved'])
        self.assertFalse(receipt['scientific_qualification'])
        self.assertFalse(receipt['metadata_binding_authenticates_native_arrays'])
        self.assertIsNone(receipt['accepted_input_receipt_sha256'])
        self.assertEqual((route.digest(self.binding._inputs.manifest),route.digest(self.binding._inputs.joined)),self.original_hashes)

    def test_authentic_binding_rejects_generated_file_hashes_before_input_reader(self):
        with patch.object(self.reader,'NativeInputs',side_effect=AssertionError('must refuse before file input load')):
            with self.assertRaisesRegex(route.RouteError,'exact accepted three metadata'):
                route.bind_preparation_metadata(self.protected,file_sha256={},protected_run_root=self.root,
                    implementation_root=support.IMPLEMENTATIONS)
        with self.assertRaisesRegex(route.RouteError,'generated metadata binding'):
            route.build_current_route_packet(self.selection,self.checkpoints,input_role='authentic_candidate',
                context_variant='population_context',representation_training_sessions=sorted(self.binding._inputs.sessions))

    def test_invalid_EI_selector_precedes_route_compatibility_and_unknowns_refuse(self):
        original=self.source.splits.select_readout_panel
        with patch.object(self.source.splits,'select_readout_panel',wraps=original) as called:
            with self.assertRaisesRegex(ValueError,'CV crosses test/train boundary'):
                route.select_current_route(self.binding,label_level='ei',panel='inductive_zero_shot',route_id='unsupported')
            self.assertEqual(called.call_count,1)
        with self.assertRaisesRegex(route.RouteError,'unsupported current-source route'):
            route.select_current_route(self.binding,label_level='ei',panel='transductive',route_id='unknown')
        with self.assertRaisesRegex(route.RouteError,'unsupported current-source route'):
            route.select_current_route(self.binding,label_level='subclass',panel='inductive_zero_shot')

    def test_packet_keeps_nonlexical_IDs_numeric_epochs_and_native_addresses(self):
        packet,receipt=self.built['packet'],self.built['route_receipt']
        self.assertNotEqual(self.ids,sorted(self.ids))
        self.assertEqual([c['epoch'] for c in packet['checkpoints']],[2,10,100])
        self.assertEqual(packet['checkpoints'][0]['ids'],self.ids)
        self.assertEqual([r['unit_id'] for r in receipt['ordered_native_addresses']],self.ids)
        self.assertEqual(receipt['phase'],'packet_bound_no_fit')
        self.assertEqual(receipt['required_readout_fits'],4)
        self.assertFalse(receipt['authentic_execution_authorized_by_receipt'])
        self.assertFalse(receipt['source_exposure']['readout_test_labels_used_for_checkpoint_selection'])
        self.assertEqual(packet['class_balance'],'resample')

    def test_literal_author_loader_sorts_numeric_epochs_and_preserves_IDs(self):
        import numpy as np
        tree=ast.parse(support.pinned(support.OFFICIAL/'utils.py',support.UTILS_SHA))
        fn=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='load_embs']
        seen=[]; ids=np.asarray(['u10','u2'])
        def load(path):
            seen.append(int(path.stem.split('_')[-1])); return np.ones((2,1),dtype=np.float32),ids
        fake=SimpleNamespace(is_dir=lambda:True,iterdir=lambda:[Path('epoch_100'),Path('epoch_2'),Path('epoch_10')])
        namespace={'np':np,'Path':Path,'load_emb':load,'tqdm':lambda values:values}
        exec(compile(ast.Module(body=fn,type_ignores=[]),'<literal-source-loader>','exec'),namespace)
        arrays,returned=namespace['load_embs'](fake)
        self.assertEqual(seen,[2,10,100]); np.testing.assert_array_equal(returned,ids)
        self.assertEqual(len(arrays),3)

    def test_changed_epochs_checkpoint_order_and_class_weight_refuse(self):
        for mode in ('duplicate_epoch','lexical_epoch','ID_order','weight'):
            bad=deepcopy(self.built['packet'])
            if mode=='duplicate_epoch': bad['checkpoints'][1]['epoch']=2
            elif mode=='lexical_epoch': bad['checkpoints']=[bad['checkpoints'][1],bad['checkpoints'][2],bad['checkpoints'][0]]
            elif mode=='ID_order': bad['checkpoints'][1]['ids'].reverse()
            else: bad['class_balance']='weight'
            with self.subTest(mode=mode),self.assertRaises(ValueError):
                route._validate_packet_binding(self.selection,bad)

    def test_mutated_binding_or_selection_receipt_refuse(self):
        fake_inputs=SimpleNamespace(**vars(self.binding._inputs))
        fake_inputs.manifest=dict(fake_inputs.manifest,order_policy='changed')
        with self.assertRaisesRegex(route.RouteError,'documents changed'):
            route.select_current_route(replace(self.binding,_inputs=fake_inputs),label_level='ei',panel='transductive')
        altered=deepcopy(self.selection.receipt); altered['scientific_qualification']=True
        with self.assertRaisesRegex(route.RouteError,'selection changed'):
            route._check_selection(replace(self.selection,receipt=altered))
        definition=bytearray((support.COMPONENT/'route-adoption.json').read_bytes()); definition[-2]=ord(' ')
        with patch.object(route,'ADOPTION_SHA256','0'*64):
            with self.assertRaisesRegex(route.RouteError,'source pin'):
                route.route_definition()

    def test_source_trace_single_dictionary_ROS_before_scaling_and_selected_refit(self):
        import numpy as np
        source=PipelineTrace(); adapter=PipelineTrace()
        oracle=run_source(self.built['packet'],source.Sampler,source.Scaler,source.Classifier)
        with adapter.installed():
            actual=route.evaluate_current_route(self.selection,self.built['packet'],self.built['route_receipt'])
        result=actual['readout_result']
        self.assertEqual((len(source.samples),len(adapter.samples)),(6,4))
        self.assertEqual(oracle['selected_index'],0)
        self.assertEqual(result['selected'][0]['epoch'],2)
        self.assertTrue(oracle['input_float32'])
        for k in range(3): assert_trace_pair(self,source,adapter,2*k,k)
        assert_trace_pair(self,source,adapter,1,3)
        self.assertEqual([r['pred'] for r in result['records']],oracle['pred'])
        self.assertEqual([r['true'] for r in result['records']],oracle['true'])
        self.assertEqual(result['metrics']['macro_f1'],oracle['f1'])
        self.assertEqual(result['metrics']['balanced_accuracy'],oracle['bacc'])
        spec=self.source.evaluator.validate_packet(self.built['packet'])
        split=spec['splits'][0]
        X=np.asarray(self.built['packet']['checkpoints'][0]['embeddings'],dtype=np.float32)
        self.assertTrue(any(float(value)!=float(np.float32(value)) for value in self.built['packet']['checkpoints'][0]['embeddings'][0]))
        for index,population in ((0,split['cv'][0][0]),(3,split['train'])):
            ordered=[i for i,uid in enumerate(self.ids) if uid in population]
            expected=X[ordered][adapter.samples[index]['picked']]
            np.testing.assert_array_equal(adapter.scalers[index]['X'],expected)
            self.assertTrue(set(population).isdisjoint(split['test']))
        raw_train=X[[i for i,uid in enumerate(self.ids) if uid in split['cv'][0][0]]]
        self.assertFalse(np.array_equal(raw_train.mean(axis=0,dtype=np.float64),adapter.scalers[0]['mean']))
        test_ids=[uid for uid in self.ids if uid in split['test']]
        self.assertEqual([r['unit_id'] for r in result['records']],test_ids)
        self.assertEqual(actual['route_receipt']['imbalanced_learn_version'],'TRACE_DOUBLE_NOT_REAL_ROS')
        self.assertFalse(actual['route_receipt']['scientific_qualification'])

    def test_macro_F1_selects_epoch10_over_higher_balanced_accuracy_and_earlier_tie(self):
        packet=support.tiny_packet(self.source.evaluator)
        source=PipelineTrace(macro_reverse=True); adapter=PipelineTrace(macro_reverse=True)
        oracle=run_source(packet,source.Sampler,source.Scaler,source.Classifier)
        with adapter.installed():
            result=self.source.evaluator.evaluate(packet)
        self.assertEqual(oracle['selected_index'],1)
        self.assertEqual(result['selected'][0]['epoch'],10)
        scores=result['selected'][0]['cv_metrics']
        self.assertGreater(scores[0]['balanced_accuracy'],scores[1]['balanced_accuracy'])
        self.assertLess(scores[0]['macro_f1'],scores[1]['macro_f1'])
        self.assertEqual(scores[1]['macro_f1'],scores[2]['macro_f1'])
        self.assertEqual([r['pred'] for r in result['records']],oracle['pred'])
        true=['EC']*8+['IN']*2; pred=['EC']*10
        self.assertEqual(self.source.evaluator.classification_metrics(true,pred,['EC','IN','UNUSED'])['macro_f1'],4/9)

    def test_missing_real_dependency_refuses_without_fallback(self):
        import sklearn.linear_model
        with patch.dict(sys.modules,{'imblearn':None,'imblearn.over_sampling':None}),\
             patch.object(sklearn.linear_model,'LogisticRegression',side_effect=AssertionError('fit must not start')):
            with self.assertRaisesRegex(ValueError,'imbalanced-learn; no fallback'):
                route.evaluate_current_route(self.selection,self.built['packet'],self.built['route_receipt'])

    def test_nonconvergence_refuses_without_execution_receipt(self):
        from sklearn.exceptions import ConvergenceWarning
        trace=PipelineTrace()
        def warn_fit(self,*args):
            warnings.warn('generated nonconvergence control',ConvergenceWarning)
        with trace.installed(),patch.object(trace.Classifier,'fit',warn_fit):
            with self.assertRaisesRegex(ValueError,'failed to converge'):
                route.evaluate_current_route(self.selection,self.built['packet'],self.built['route_receipt'])

    def test_incomplete_output_refuses_at_route_result_boundary(self):
        spec=self.source.evaluator.validate_packet(self.built['packet'])
        expected=[uid for uid in self.ids if uid in spec['splits'][0]['test']]
        fake={'packet_sha256':route.digest(self.built['packet']),'selected':[{}],
            'records':[{'unit_id':uid} for uid in expected[:-1]],'resources':{'readout_fits':4},
            'research_qualified':False,'full_contract_complete':False}
        with patch.object(self.source.evaluator,'evaluate',return_value=fake):
            with self.assertRaisesRegex(route.RouteError,'result coverage'):
                route.evaluate_current_route(self.selection,self.built['packet'],self.built['route_receipt'])

    def test_exclusive_private_sibling_receipt_and_no_original_write(self):
        global GENERATED_FILE_BYTES
        target=self.sidecars/'selected.json'
        info=route.write_receipt_new(self.selection,target,self.selection.receipt)
        GENERATED_FILE_BYTES+=info['bytes']
        self.assertLessEqual(GENERATED_FILE_BYTES,support.MAX_GENERATED_BYTES)
        self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(),info['file_sha256'])
        self.assertEqual(stat.S_IMODE(target.stat().st_mode),0o600)
        with self.assertRaises(FileExistsError): route.write_receipt_new(self.selection,target,self.selection.receipt)
        with self.assertRaisesRegex(route.RouteError,'outside the entire original'):
            route.write_receipt_new(self.selection,self.protected/'forbidden.json',self.selection.receipt)
        self.assertEqual(list(self.protected.iterdir()),[])

    def test_sidecar_parent_symlink_traversal_and_receipt_tamper_refuse(self):
        alias=self.sidecars/'alias'; alias.symlink_to(self.protected,target_is_directory=True)
        with self.assertRaises((OSError,route.RouteError)):
            route.write_receipt_new(self.selection,alias/'forbidden.json',self.selection.receipt)
        with self.assertRaisesRegex(route.RouteError,'parent traversal'):
            route.write_receipt_new(self.selection,self.sidecars/'..'/'original'/'forbidden.json',self.selection.receipt)
        bad=deepcopy(self.selection.receipt); bad['scientific_qualification']=True
        with self.assertRaisesRegex(route.RouteError,'custody identities'):
            route.write_receipt_new(self.selection,self.sidecars/'bad.json',bad)
        self.assertEqual(list(self.protected.iterdir()),[])

    def test_protected_run_directory_replacement_refuses(self):
        old=self.root/'old-original'
        self.protected.rename(old); self.protected.mkdir()
        try:
            with self.assertRaisesRegex(route.RouteError,'directory identity changed'):
                route.write_receipt_new(self.selection,self.sidecars/'replaced.json',self.selection.receipt)
        finally:
            self.protected.rmdir(); old.rename(self.protected)


if __name__=='__main__':
    unittest.main(verbosity=2)
