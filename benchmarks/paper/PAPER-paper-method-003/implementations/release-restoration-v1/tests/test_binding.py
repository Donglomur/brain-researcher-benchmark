"""Generated metadata and actual complete private-ID joins; no arrays/scoring.

Reuses the real release emitter with an inert campaign barrier. Full private
restoration uses unchanged source over generated metadata, not authentic people.
"""
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


x = load('reve_release_binding_control', HERE/'binding.py')
fixture_path = HERE.parent/'opaque-submission-v1/tests/test_adapter.py'
assert hashlib.sha256(fixture_path.read_bytes()).hexdigest() == 'de716dd790fa9e6e9456e5e66dfd0ccf1a068813a17dde26fd7734095a1dbbcf'
f = load('reve_release_join_fixture', fixture_path)
b = load('reve_actual_release_emitter', HERE.parent/'development-boundary-v1/boundary.py')
a, m = x.dependencies()
CREATED = 0
FIXTURE_CAP = 2883584


def write(path, body):
    global CREATED
    CREATED += len(body)
    assert CREATED <= FIXTURE_CAP
    path.write_bytes(body); path.chmod(0o600)


def emitted(role='A', profile=x.PROFILES[0]):
    info = f.INFOS[0 if role=='A' else 1]
    rows = [{'event_id':eid,'scores':[i,i+1,-i,i/4096]}
            for i,eid in enumerate(reversed(info['test_ids']),1)]
    episode = object.__new__(b.Episode)
    episode.id = ('a' if role=='A' else 'b')*64
    episode.info = info; episode.profile = profile
    episode.declaration = {'uses_unlabeled_test_context':profile==x.PROFILES[1],
                           'description':'Generated source control; no actual candidate.'}
    episode.artifact = {'artifact_identity':'c'*64}; episode.design_identity='d'*64
    episode.barrier = SimpleNamespace(release=lambda:{'roster_identity':'e'*64})
    episode.results = {'schema':'reve-candidate-predictions-v1',
                       'materials_identity':info['materials_identity'],'predictions':rows}
    result = episode.complete_predictions()
    return result, {key:deepcopy(result['release'][key]) for key in x.CONTEXT}


RELEASED, CONTEXT = emitted()


class ReleaseMetadata(unittest.TestCase):
    def test_actual_emitter_full_panel_and_both_conditions(self):
        for role,info in zip(('A','B'),f.INFOS):
            released,context = emitted(role)
            accepted = x.validate_release(released,context,info,a)
            self.assertEqual(accepted,released)
            self.assertEqual(len(accepted['predictions']['predictions']),1803)
            self.assertEqual(len({r['event_id'] for r in accepted['predictions']['predictions']}),1803)
            self.assertEqual(f.DOCS[0]['data_identity'],f.DOCS[1]['data_identity'])

    def test_context_rejects_cross_arm_roster_artifact_design_episode_and_release(self):
        for field in ('episode_id','roster_identity','artifact_identity','design_identity','release_identity','materials_identity'):
            wrong = deepcopy(CONTEXT); wrong[field]='0'*64
            with self.subTest(field=field), self.assertRaises(x.Refusal):
                x.validate_release(RELEASED,wrong,f.INFOS[0],a)
        wrong = deepcopy(CONTEXT); wrong['role']='B'
        with self.assertRaises(x.Refusal): x.validate_release(RELEASED,wrong,f.INFOS[0],a)
        release_b,context_b = emitted('B')
        with self.assertRaises(x.Refusal): x.validate_release(release_b,context_b,f.INFOS[0],a)

    def test_release_wrapper_digest_and_prediction_pin_required(self):
        with self.assertRaises(x.Refusal): x.validate_release(RELEASED['predictions'],CONTEXT,f.INFOS[0],a)
        for change in ('declaration','value','missing','extra'):
            released = deepcopy(RELEASED)
            if change=='declaration': released['release']['declaration']['description']='changed'
            elif change=='value': released['predictions']['predictions'][0]['scores'][0]+=1
            elif change=='missing': released['predictions']['predictions'].pop()
            else: released['release']['foreign']='field'
            with self.subTest(change=change), self.assertRaises(ValueError):
                x.validate_release(released,CONTEXT,f.INFOS[0],a)

    def test_prospective_profile_is_preserved_and_cannot_remove_outcome_flag(self):
        released,context = emitted(profile=x.PROFILES[1])
        accepted = x.validate_release(released,context,f.INFOS[0],a)
        self.assertTrue(accepted['release']['requires_separate_outcome_binding'])
        released['release']['requires_separate_outcome_binding']=False
        released['release'].pop('release_identity')
        released['release']['release_identity']=a.digest(released['release'])
        context['release_identity']=released['release']['release_identity']
        with self.assertRaises(x.Refusal):x.validate_release(released,context,f.INFOS[0],a)

    def test_qualification_promotions_refused_even_with_new_digest(self):
        for field in ('scientific_qualification','current_paper_win_qualified'):
            released=deepcopy(RELEASED);released['release'][field]=True
            released['release'].pop('release_identity');released['release']['release_identity']=a.digest(released['release'])
            context={k:deepcopy(released['release'][k]) for k in x.CONTEXT}
            with self.subTest(field=field),self.assertRaises(x.Refusal):
                x.validate_release(released,context,f.INFOS[0],a)


class PrivateRestoration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global CREATED
        cls.temp=tempfile.TemporaryDirectory(prefix='reve-release-binding-')
        cls.root=Path(cls.temp.name).resolve();cls.inputs=cls.root/'inputs';cls.inputs.mkdir(mode=0o700)
        for name,value in [('panel.json',f.PANEL),('mapping.json',f.MAP),('materials.json',f.DOCS[0])]:
            write(cls.inputs/name,x.canonical(value))
        cls.output=cls.root/'restored'
        cls.arguments={'expected_context':CONTEXT,'panel_path':cls.inputs/'panel.json',
                       'mapping_path':cls.inputs/'mapping.json','materials_path':cls.inputs/'materials.json',
                       'expected_panel_identity':f.PANEL['panel_identity'],
                       'expected_mapping_identity':f.MAP['mapping_identity'],
                       'expected_data_identity':f.DOCS[0]['data_identity']}
        cls.result=x.restore(RELEASED,output=cls.output,**cls.arguments)
        CREATED+=cls.result['created_file_bytes'];assert CREATED<=FIXTURE_CAP
        cls.verification={k:cls.arguments[k] for k in ('expected_context','expected_panel_identity','expected_mapping_identity','expected_data_identity')}
        cls.verification['expected_binding_pin']=cls.result['binding_pin']

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_exact_1803_distinct_values_and_original_source_order(self):
        observed=x.verify(self.output,original_like_only=True,**self.verification)
        actual=observed['restored']['predictions']
        values={r['event_id']:r['scores'] for r in RELEASED['predictions']['predictions']}
        expected=[{'event_id':row['source_event_id'],'scores':values[row['event_id']]} for row in f.MAP['records']]
        self.assertEqual(actual,expected)
        self.assertEqual(observed['binding']['release'],RELEASED['release'])
        self.assertEqual(len({tuple(r['scores']) for r in actual}),1803)
        self.assertEqual(observed['restored']['candidate_submission_identity'],a.digest(RELEASED['predictions']))
        self.assertFalse(observed['scientific_qualification'])

    def test_private_bundle_modes_and_closed_membership(self):
        self.assertEqual(stat.S_IMODE(self.output.stat().st_mode),0o700)
        self.assertEqual({p.name for p in self.output.iterdir()},{'opaque.json','original.json','BINDING.json'})
        for path in self.output.iterdir():
            self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600)
            self.assertEqual(path.stat().st_nlink,1)

    def test_independent_binding_pin_is_mandatory(self):
        for value in (None,{},False,{'bytes':1,'sha256':'0'*64}):
            kwargs={**self.verification,'expected_binding_pin':value}
            with self.subTest(pin=value),self.assertRaises(ValueError):x.verify(self.output,**kwargs)

    def test_wrong_selected_data_mapping_and_context_refused(self):
        for field in ('expected_data_identity','expected_panel_identity','expected_mapping_identity'):
            kwargs={**self.verification,field:'0'*64}
            with self.subTest(field=field),self.assertRaises(x.Refusal):x.verify(self.output,**kwargs)
        context=deepcopy(CONTEXT);context['roster_identity']='0'*64
        with self.assertRaises(x.Refusal):x.verify(self.output,**{**self.verification,'expected_context':context})

    def test_prospective_binding_cannot_enter_original_route(self):
        # Only the bound metadata read is inert here; no second original-ID export.
        observed=x.verify(self.output,**self.verification)
        prospective,context=emitted(profile=x.PROFILES[1])
        binding=deepcopy(observed['binding']);binding['release']=prospective['release'];binding['expected_context']=context
        changed=x.pin(x.canonical(binding));calls=[]
        def only_binding(path,*args,**kwargs):
            calls.append(Path(path).name)
            self.assertEqual(Path(path).name,'BINDING.json')
            return binding,changed
        with patch.object(x,'read_document',side_effect=only_binding),self.assertRaisesRegex(x.Refusal,'prospective full-test-context'):
            x.verify(self.output,original_like_only=True,**{**self.verification,'expected_context':context,'expected_binding_pin':changed})
        self.assertEqual(calls,['BINDING.json'])

    def test_native_score_raw_bytes_join_and_preprocessing_profile_distinct(self):
        observed=x.verify(self.output,**self.verification)
        score={'panel_identity':f.PANEL['panel_identity'],
               'prediction_file_sha256':observed['restored_pin']['sha256'],
               'profile':m.PROFILE,'generated_only_metric':0.25,'paper_win':None,
               'author_prediction_file_sha256':'f'*64}
        path=self.root/'generated-score.json';body=(json.dumps(score,indent=2)+'\n').encode();write(path,body)
        self.assertNotEqual(x.pin(body),x.pin(x.canonical(score)))
        joined=x.join_score(self.output,path,expected_score_pin=x.pin(body),**self.verification)
        self.assertEqual(joined['native_score'],score)
        self.assertEqual(joined['native_score_pin'],x.pin(body))
        self.assertEqual(joined['release']['profile'],x.PROFILES[0])
        self.assertFalse(joined['current_paper_win_qualified'])
        with self.assertRaises(ValueError):x.join_score(self.output,path,expected_score_pin=None,**self.verification)
        wrong={**score,'prediction_file_sha256':'0'*64};wrong_body=x.canonical(wrong)
        bad=self.root/'wrong-score.json';write(bad,wrong_body)
        with self.assertRaises(x.Refusal):x.join_score(self.output,bad,expected_score_pin=x.pin(wrong_body),**self.verification)

    def test_changed_output_bytes_refused_without_rewriting_full_artifact(self):
        global CREATED
        with (self.output/'original.json').open('r+b') as stream:
            first=stream.read(1);stream.seek(0);stream.write(b'X');stream.flush();CREATED+=1
            try:
                with self.assertRaisesRegex(x.Refusal,'externally retained file pin'):
                    x.verify(self.output,**self.verification)
            finally:
                stream.seek(0);stream.write(first);stream.flush();CREATED+=1

    def test_failed_final_publication_keeps_private_partial_and_conservative_cost(self):
        global CREATED
        output=self.root/'failed-publication'
        with (patch.object(x.os,'rename',side_effect=OSError(5,'generated publication I/O failure')),
              self.assertRaises(x.BindingFailure) as raised):
            x.restore(RELEASED,output=output,**self.arguments)
        CREATED+=sum(p.stat().st_size for p in output.iterdir() if p.is_file());assert CREATED<=FIXTURE_CAP
        self.assertFalse((output/'BINDING.json').exists())
        self.assertTrue((output/'BINDING.pending.json').is_file())
        detail=raised.exception.detail
        self.assertEqual(detail['stage'],'publish_binding');self.assertEqual(detail['errno'],5)
        self.assertGreaterEqual(detail['metadata_read_charge_bytes'],4*(m.MAX_JSON_BYTES+1))
        self.assertGreaterEqual(detail['write_charge_upper_bytes'],m.MAX_JSON_BYTES)
        self.assertTrue(detail['partial_output_must_not_be_used'])

    def test_existing_or_input_nested_destination_refused(self):
        for output in (self.output,self.inputs/'nested'):
            with self.subTest(output=str(output)),self.assertRaises(x.BindingFailure):
                x.restore(RELEASED,output=output,**self.arguments)
        self.assertFalse((self.inputs/'nested').exists())


if __name__=='__main__':
    try:unittest.main(verbosity=2)
    finally:print(json.dumps({'generated_cumulative_file_write_bytes':CREATED,'authentic_data_bodies':0,
                             'native_scorer_calls':0,'real_release_emitter_with_inert_barrier':True}))
