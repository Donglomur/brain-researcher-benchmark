"""Ordinary generated full-campaign controls; no Docker or authentic export."""
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

import contract as c
import materials as m
import transport as t
from test_materials import generated_arrays, generated_asset_tree, generated_bank


class CampaignControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='spinal-delivery-generated-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.bank = generated_bank()
        self.bank.roster = {'expected_neurons':self.bank.metadata['expected_neurons'],
                            'records':self.bank.metadata['recordings']}
        self.bank.eligible = [r for r in self.bank.metadata['recordings'] if r['status']=='prepared']
        assets = self.root/'assets'; assets.mkdir()
        descriptor, _ = generated_asset_tree(assets)
        self.asset_patch = patch.object(m,'_asset_manifest',return_value=descriptor)
        self.asset_patch.start();self.addCleanup(self.asset_patch.stop)
        self.assets = {arm:m.capture_assets(assets,arm) for arm in c.ARMS}
        programs=[]
        for i in range(2):
            folder=self.root/f'program-{i}';folder.mkdir()
            (folder/'program.py').write_text('# inert generated program; never executed\n')
            programs.append(folder)
        self.pair,self.contents=c.freeze_pair(*programs,'improvement','hz')
        self.runtime=t.runtime_selection(1,536870912,0)
        self.calls=[];self.builders=[];self.previous=None
        self.break_closure=False;self.mutate_source=False;self.change_receipt=False
        self.repeat_namespace=False;self.change_data=False
        self.current=m.load_current()

    def build(self,bank,held,arm,purpose):
        attempt=self.root/'attempt'
        # Both immutable source/config snapshots and pair seal must predate labels.
        self.assertTrue((attempt/'PAIR_SEAL.json').is_file())
        for name in c.ARMS:
            self.assertEqual((attempt/'programs'/name/'program.py').read_bytes(),self.contents[name]['program.py'])
            self.assertEqual((attempt/'programs'/name/'config.json').read_bytes(),self.contents[name]['config.json'])
        self.builders.append((arm,held))
        packet=m.build_materials(bank,held,arm,purpose,array_loader=generated_arrays)
        if self.change_data and len(self.builders)==1:
            # Ordinary accidental changed projected observation, not source labels.
            packet['query']['fluorescence']=packet['query']['fluorescence'].copy()
            packet['query']['fluorescence'][0]+=1
        return packet

    def lifecycle(self,docker,trusted,cfg,lock,paths,attempt,verify_inputs,end):
        self.assertIsNone(docker)  # This fixture never starts a process/container.
        binding=json.loads((trusted/'PROGRAM_BINDING.json').read_bytes())
        fold=json.loads(paths['FOLD.json'].read_bytes())
        arm,held=binding['arm'],binding['held_neuron']
        if self.previous is not None:
            self.assertFalse((self.previous/'input').exists())
            self.assertFalse((self.previous/'trusted').exists())
        self.previous=attempt
        self.assertTrue(all(path.parent==attempt/'input' or attempt/'input' in path.parents for path in paths.values()))
        self.assertFalse(any('BANK' in name or 'CENSUS' in name for name in paths))
        self.assertEqual(set(paths),{'FOLD.json','training.npz','query.npz',*self.assets[arm]})
        self.assertFalse(any(row['neuron_id']==held for row in fold['training_records']))
        self.assertEqual({self.bank.metadata['expected_neurons'][r['neuron_id']] for r in fold['training_records']},{fold['cohort']})
        with np.load(paths['query.npz'],allow_pickle=False) as query:
            self.assertEqual(set(query.files),set(m.QUERY_FIELDS))
        with np.load(paths['training.npz'],allow_pickle=False) as train:
            self.assertEqual(set(train.files),set(m.TRAINING_FIELDS))
        self.calls.append((arm,held))
        if self.mutate_source:
            program=cfg['program_directory']/'program.py'
            program.chmod(0o600);program.write_bytes(b'changed after freeze\n')
        post=verify_inputs()
        if self.break_closure:
            return {'status':'failed','all_resources_closed':False,'cli_reaped':True,
                    'candidate_closed_before_capture':False,'namespace':'generated-failed'}
        n=sum(r['samples'] for r in binding['query_records'])
        self.assertEqual(lock['prediction_max_bytes'],8*n+1036)
        vector=np.arange(n,dtype='<f8')/100
        prediction=io.BytesIO();np.save(prediction,vector,allow_pickle=False)
        result={'schema':'spinal_current_fold_prediction_v1','condition_id':c.CONDITION,
                'held_neuron':held,'arm':arm,'purpose':binding['purpose'],
                'program_seal_sha256':binding['program_seal']['sha256'],
                'binding_sha256':c.pin(c.encoded(binding))['sha256'],'unit':binding['output_unit'],
                'query_recording_ids':[r['recording_id'] for r in binding['query_records']]}
        capture=attempt/'captured';capture.mkdir()
        rows=[]
        for name,body in [('fold.json',c.encoded(result)),('predictions.npy',prediction.getvalue())]:
            (capture/name).write_bytes(body);rows.append({'path':name,**c.pin(body)})
        namespace='generated-one' if self.repeat_namespace else f'generated-{arm}-{held}'
        receipt={'schema':'cascade44_fold_lifecycle_v1','status':'captured','all_resources_closed':True,'cli_reaped':True,
                'candidate_closed_before_capture':True,'namespace':namespace,'public_post_pin':post,
                'program_seal':cfg['program_seal'],'source_manifest':cfg['source_manifest'],
                'runtime_contract':cfg['runtime_contract'],
                'image':'sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156',
                'candidate_seconds':cfg['candidate_seconds'],'memory_bytes':cfg['memory_bytes'],
                'candidate_started':True,'private_scoring_called':False,
                'natural_exit':{'Status':'exited','Running':False,'Dead':False,'Pid':0,'ExitCode':0,'OOMKilled':False},
                'closures':[{'kind':k,'closed':True} for k in ('container','container','volume')],
                'outputs':rows}
        if self.change_receipt:
            receipt['program_seal']={'bytes':1,'sha256':'f'*64}
        return receipt

    def run_campaign(self):
        return t.run_pair(self.bank,self.assets,self.pair,self.contents,self.root/'attempt',self.runtime,
                          {'sha256':'0'*64,'bytes':1},None,enforce_space=False,
                          lifecycle=self.lifecycle,material_builder=self.build)

    def test_complete_botharms44folds116predictions_with_retired_views(self):
        result=self.run_campaign()
        self.assertEqual(len(self.calls),88)
        self.assertEqual(len(set(self.calls)),88)
        self.assertEqual(set(self.calls),{(arm,held) for arm in c.ARMS for held in self.bank.metadata['expected_neurons']})
        self.assertEqual(result['required_neurons'],44)
        self.assertEqual(result['source_recording_census'],132)
        self.assertEqual(result['eligible_recordings'],116)
        self.assertFalse(result['scientific_scoring_performed'])
        self.assertFalse(result['model_training_provenance_qualified'])
        self.assertGreaterEqual(result['budget']['precharged_managed_write_bytes'],t.TERMINAL_RECEIPTS)
        self.assertEqual(result['budget_snapshot_stage'],'before_worker_complete_and_host_exit')
        for arm in c.ARMS:
            path=self.root/'attempt'/arm/'candidate'
            pin=result['arms'][arm]['prediction_manifest']
            bundle=self.current.load_predictions(path,self.bank,role='candidate',manifest_sha256=pin['sha256'])
            self.assertEqual(len(bundle.by_id),116)
            for row in self.bank.eligible:
                values=self.current._prediction_arrays(bundle,row)['candidate']
                self.assertEqual(len(values),row['output_samples'])
            for held in self.bank.metadata['expected_neurons']:
                fold=self.root/'attempt'/arm/'folds'/held
                self.assertFalse((fold/'input').exists());self.assertFalse((fold/'trusted').exists())
                proof=json.loads((fold/'FOLD_PROOF.json').read_bytes())
                self.assertEqual(len(proof['held_all_source_records_excluded']),3)

    def test_first_context_failure_stops_without_partial_completion(self):
        self.break_closure=True
        with self.assertRaisesRegex(ValueError,'closure'):
            self.run_campaign()
        self.assertEqual(len(self.calls),1)
        root=self.root/'attempt'
        self.assertTrue((root/'FAILED.json').exists())
        self.assertFalse((root/'WORKER_COMPLETE.json').exists())
        self.assertFalse(any(root.rglob('PREDICTIONS.json')))

    def test_frozen_program_change_is_refused_before_capture(self):
        self.mutate_source=True
        with self.assertRaisesRegex(ValueError,'immutable complete'):
            self.run_campaign()
        self.assertEqual(len(self.calls),1)
        self.assertFalse(any((self.root/'attempt').rglob('PREDICTIONS.json')))

    def test_reused_context_refused(self):
        self.repeat_namespace=True
        with self.assertRaisesRegex(ValueError,'fresh context'):
            self.run_campaign()
        self.assertEqual(len(self.calls),2)

    def test_different_trusted_lifecycle_binding_refused(self):
        self.change_receipt=True
        with self.assertRaisesRegex(ValueError,'trusted live lifecycle joins'):
            self.run_campaign()
        self.assertEqual(len(self.calls),1)

    def test_incomplete_pair_never_builds_labels(self):
        del self.pair['arms'][c.ARMS[1]]
        with self.assertRaisesRegex(ValueError,'both programs'):
            self.run_campaign()
        self.assertEqual(self.builders,[])
        self.assertFalse((self.root/'attempt').exists())

    def test_changed_candidate_config_never_builds_labels(self):
        self.contents[c.ARMS[1]]['config.json']=b'{}\n'
        with self.assertRaisesRegex(ValueError,'complete frozen'):
            self.run_campaign()
        self.assertEqual(self.builders,[])


class AccountingAndSourceControls(unittest.TestCase):
    def test_prospective_retained_bound_refuses_file_before_creation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve()/'attempt'
            budget=t.Budget(root,enforce_space=False)
            with patch.object(t,'RETAINED',65536),self.assertRaisesRegex(ValueError,'prospective retained'):
                budget.save(root/'too-large',b'x',100)
            self.assertFalse((root/'too-large').exists())

    def test_cumulative_budget_refuses_before_creation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve()/'attempt'
            budget=t.Budget(root,enforce_space=False)
            with patch.object(t,'WRITES',1),self.assertRaisesRegex(ValueError,'cumulative'):
                budget.save(root/'too-large',b'xx',100)
            self.assertFalse((root/'too-large').exists())

    def test_free_space_checked_before_attempt_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve()/'attempt'
            with patch.object(t.shutil,'disk_usage',return_value=type('Space',(),{'free':0})()),self.assertRaisesRegex(ValueError,'free-disk'):
                t.Budget(root)
            self.assertFalse(root.exists())

    def test_exact_reused_runtime_captured_without_ambient_import(self):
        import sys
        other=object()
        with patch.dict(sys.modules,{'runtime':other}):
            modules=c.load_reused()
            self.assertIs(modules['lifecycle'].r,modules['runtime'])
            self.assertIs(sys.modules['runtime'],other)
        self.assertEqual(modules['runtime'].IMAGE,'sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156')

    def test_source_manifest_exact_closure(self):
        body=(t.HERE/'SOURCE_MANIFEST.json').read_bytes()
        self.assertEqual(t.verify_source(c.pin(body)['sha256']),c.pin(body))
        with self.assertRaisesRegex(ValueError,'descriptor identity'):
            t.verify_source('0'*64)

    def test_runtime_selection_rejects_unbounded_or_wrong_types(self):
        for args in [(0,536870912,0),(1,1,0),(True,536870912,0),(1,536870912,-1)]:
            with self.subTest(args=args),self.assertRaises(ValueError):
                t.runtime_selection(*args)
        selected=t.runtime_selection(5,536870912,0)
        self.assertEqual(selected['worker_wall_seconds'],88*425+180)
        self.assertFalse(selected['automatic_retry'])


if __name__=='__main__':
    unittest.main()
