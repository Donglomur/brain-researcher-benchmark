"""Full272/92 generated replay/score controls; no authentic data or native runs."""
import copy
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('neural021_visual_grade_under_test',HERE/'grade.py')
g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)


def generated_packet(delivery):
    conditions = [0]*52+[1]*40
    cases = {'schema':'neural021_public_cases_v1','task_id':'NEURAL-021','time_bins':30,
             'feature_shape':[30,6,65],'units':'m/s','conditions':{'0':'active','1':'passive'},
             'queries':[{'trial_id':f'q{i:04d}','condition':delivery.CONDITIONS[c]} for i,c in enumerate(conditions)]}
    counts = tuple(tuple((b+2*u)%13 for u in range(65)) for b in range(35))
    history = delivery.expand_counts(counts)
    trajectory = [[float(t),float(2*t)] for t in range(30)]
    training = {'spike_counts':[history]*272,'condition':[0,1]*136,'velocity_m_s':[trajectory]*272}
    queries = {'spike_counts':[history]*92,'condition':conditions}
    packet = delivery.Packet.from_arrays(training,queries,delivery.encode(cases))
    gold = {'schema':'neural021_private_targets_v1','cases_sha256':packet.cases_sha256,
            'query_ids':[row['trial_id'] for row in cases['queries']],
            'velocity_m_s':[[list(pair) for pair in trajectory] for _ in range(92)]}
    return packet,gold


def finished(delivery,packet,mode,offset=0.):
    session = delivery.Session(packet,mode)
    session.calibration(0); session.calibration(271)
    for index in reversed(range(92)):
        key=f'q{index:04d}'
        session.view(key)
        if mode=='typed_viewer' and index==91:
            session.view(key,unit_start=60,unit_stop=65,bin_start=29,bin_stop=35)
        session.answer(key,[[float(t)+offset,float(2*t)+offset] for t in range(30)])
    return session.finish()


def rechain(receipt):
    previous='0'*64
    for index,row in enumerate(receipt['events']):
        row['sequence']=index; row['previous_sha256']=previous
        row['sha256']=g.pin(g.encode({key:value for key,value in row.items() if key!='sha256'}))['sha256']
        previous=row['sha256']
    return g.encode(receipt)


class ObservationGradeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources=g.load_sources(); cls.delivery=cls.sources['delivery']
        cls.packet,cls.gold=generated_packet(cls.delivery)
        cls.artifacts={mode:finished(cls.delivery,cls.packet,mode) for mode in g.MODES}

    def evaluate(self,mode='direct_observation',artifacts=None,packet=None,gold=None):
        submission,receipt=artifacts or self.artifacts[mode]
        calls=[]
        def target():
            calls.append('target')
            return self.gold if gold is None else gold
        result=g.evaluate(self.sources,packet or self.packet,mode,submission,receipt,target)
        self.assertEqual(calls,['target'])
        return result

    def refuses_before_target(self,submission,receipt,mode='direct_observation',packet=None):
        calls=[]
        def forbidden(): calls.append('target'); raise AssertionError('target opened too early')
        with self.assertRaises((ValueError,TypeError)):
            g.evaluate(self.sources,packet or self.packet,mode,submission,receipt,forbidden)
        self.assertEqual(calls,[])

    def test_complete_two_modes_original_score_and_calibration_scope(self):
        for mode in g.MODES:
            result=self.evaluate(mode)
            self.assertEqual(result['mode'],mode)
            self.assertEqual(result['score']['mean_condition_r2'],1.)
            self.assertEqual(result['replay']['queries'],92)
            self.assertEqual(result['replay']['calibration_trials_available'],272)
            self.assertEqual(result['replay']['distinct_calibration_trials_viewed'],2)
            self.assertFalse(result['runtime_qualified'])
            self.assertEqual(result['score']['conditions']['active']['trials'],52)
            self.assertEqual(result['score']['conditions']['passive']['trials'],40)

    def test_analytic_nonperfect_negative_and_constant_target_behavior(self):
        for offset in (1.,100.):
            result=self.evaluate(artifacts=finished(self.delivery,self.packet,'direct_observation',offset))
            expected=1.-2.*offset*offset/(5.*(30.*30.-1.)/12.)
            self.assertAlmostEqual(result['score']['mean_condition_r2'],expected,places=12)
        constant=copy.deepcopy(self.gold)
        constant['velocity_m_s']=[[[0.,0.] for _ in range(30)] for _ in range(92)]
        result=self.evaluate(gold=constant)
        self.assertIsNone(result['score']['mean_condition_r2'])
        self.assertEqual(result['score']['conditions']['active']['r2_status'],'undefined_constant_target')
        self.assertGreater(result['score']['conditions']['active']['squared_euclidean_loss_m2_s2'],0)

    def test_incomplete_final_query_fails_before_replay_or_target(self):
        raw,receipt=self.artifacts['direct_observation']; submission=json.loads(raw)
        submission['predictions'].pop()
        changed=g.encode(submission); record=json.loads(receipt); record['submission_sha256']=g.pin(changed)['sha256']
        self.refuses_before_target(changed,g.encode(record))

    def test_invalid_last_trajectory_boolean_and_extra_identity(self):
        raw,receipt=self.artifacts['direct_observation']
        for mutation in ('boolean','truncated','duplicate'):
            submission=json.loads(raw)
            if mutation=='boolean': submission['predictions'][-1]['velocity_m_s'][-1][-1]=True
            elif mutation=='truncated': submission['predictions'][-1]['velocity_m_s'].pop()
            else: submission['predictions'][-1]['trial_id']='q0000'
            changed=g.encode(submission); record=json.loads(receipt); record['submission_sha256']=g.pin(changed)['sha256']
            self.refuses_before_target(changed,g.encode(record))

    def test_expected_mode_refuses_relabelled_receipt(self):
        raw,receipt=self.artifacts['direct_observation']; record=json.loads(receipt); record['mode']='typed_viewer'
        self.refuses_before_target(raw,g.encode(record))
        raw,receipt=self.artifacts['typed_viewer']; record=json.loads(receipt); record['mode']='direct_observation'
        self.refuses_before_target(raw,g.encode(record))  # The typed crop is not a direct action.

    def test_changed_view_hash_is_detected_after_checksum_repair(self):
        raw,receipt=self.artifacts['direct_observation']; record=json.loads(receipt)
        next(row for row in record['events'] if row['operation']=='query_view')['svg_sha256']='0'*64
        self.refuses_before_target(raw,rechain(record))

    def test_changed_training_view_hash_is_detected_after_checksum_repair(self):
        raw,receipt=self.artifacts['direct_observation']; record=json.loads(receipt)
        record['events'][0]['svg_sha256']='0'*64
        self.refuses_before_target(raw,rechain(record))

    def test_changed_query_waveform_cannot_reuse_old_receipt(self):
        query=self.packet.queries[-1]
        counts=[list(row) for row in query.counts]; counts[-1][-1]+=1
        altered=replace(query,counts=tuple(tuple(row) for row in counts))
        packet=replace(self.packet,queries=self.packet.queries[:-1]+(altered,))
        # Even an unchanged declared observation hash cannot hide changed rendered content.
        self.refuses_before_target(*self.artifacts['direct_observation'],packet=packet)

    def test_missing_or_reordered_actions_fail_with_valid_rehashed_chain(self):
        raw,receipt=self.artifacts['direct_observation']
        record=json.loads(receipt); record['events'].pop()
        self.refuses_before_target(raw,rechain(record))
        record=json.loads(receipt); record['events'][2],record['events'][3]=record['events'][3],record['events'][2]
        self.refuses_before_target(raw,rechain(record))

    def test_changed_answer_hash_and_out_of_catalog_calibration(self):
        raw,receipt=self.artifacts['direct_observation']
        record=json.loads(receipt); next(row for row in record['events'] if row['operation']=='answer')['answer_sha256']='f'*64
        self.refuses_before_target(raw,rechain(record))
        record=json.loads(receipt); record['events'][0]['training_index']=272
        self.refuses_before_target(raw,rechain(record))

    def test_noncanonical_or_unexpected_receipt_fields_refused(self):
        raw,receipt=self.artifacts['direct_observation']
        self.refuses_before_target(raw,json.dumps(json.loads(receipt),indent=2).encode())
        record=json.loads(receipt); record['events'][0]['private_hint']='not allowed'
        self.refuses_before_target(raw,rechain(record))

    def test_private_generation_error_is_one_failed_grade_not_partial_score(self):
        raw,receipt=self.artifacts['direct_observation']; calls=[]
        gold=copy.deepcopy(self.gold); gold['query_ids'][-1]='q9999'
        def target(): calls.append(True); return gold
        with self.assertRaisesRegex(ValueError,'private target/public roster'):
            g.evaluate(self.sources,self.packet,'direct_observation',raw,receipt,target)
        self.assertEqual(calls,[True])

    def test_operator_bad_submission_pin_never_opens_target_or_public_payload(self):
        with tempfile.TemporaryDirectory(prefix='neural021-generated-grade-') as name:
            root=Path(name).resolve(); public=root/'public'; public.mkdir()
            submission=root/'submission.json'; submission.write_bytes(b'generated')
            receipt=root/'receipt.json'; receipt.write_bytes(b'generated')
            target=root/'targets.json'; target.write_bytes(b'generated protected sentinel')
            opened=[]; original=g.capture
            def observe(path,*args): opened.append(Path(path)); return original(path,*args)
            with patch.object(g,'capture',observe):
                with self.assertRaisesRegex(ValueError,'pin mismatch'):
                    g.operator_grade(public,'direct_observation',submission,{'bytes':9,'sha256':'0'*64},
                        receipt,g.pin(b'generated'),target,root/'result.json')
            self.assertNotIn(target,opened)
            self.assertFalse(any(path.is_relative_to(public) for path in opened))
            self.assertFalse((root/'result.json').exists())

    def test_operator_rejects_target_as_early_receipt(self):
        with tempfile.TemporaryDirectory(prefix='neural021-generated-roles-') as name:
            root=Path(name).resolve(); public=root/'public'; public.mkdir()
            target=root/'protected.json'
            with patch.object(g,'capture',side_effect=AssertionError('must reject before capture')):
                with self.assertRaisesRegex(ValueError,'Separate operator'):
                    g.operator_grade(public,'direct_observation',root/'sub.json',{},target,{},target,root/'out.json')

    def test_capture_rejects_symlink_and_changed_extent(self):
        with tempfile.TemporaryDirectory(prefix='neural021-generated-capture-') as name:
            root=Path(name).resolve(); body=root/'body'; body.write_bytes(b'abc')
            link=root/'link'; link.symlink_to(body)
            with self.assertRaisesRegex(ValueError,'unlinked'): g.capture(link,g.pin(b'abc'),100)
            with self.assertRaisesRegex(ValueError,'Exact single-link'): g.capture(body,g.pin(b'ab'),100)


if __name__=='__main__':
    unittest.main()
