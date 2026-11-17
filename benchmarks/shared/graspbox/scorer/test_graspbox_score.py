"""Invented full-extent controls, with analytic oracles independent of the scorer.

No native source data, realistic traces, authentic class counts or predictions.
Fixture cohort totals only match the accepted contract to exercise full coverage.
"""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import graspbox_score as s


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def fixture():
    # Counts repeated independently from the contract, not copied from s.COUNTS.
    expectations = [(5,148,148),(4,120,104),(4,120,100),(3,90,88),
                    (3,90,80),(3,90,83),(3,90,45),(4,120,110),
                    (4,120,109),(4,120,120),(4,120,115),(4,120,120),
                    (4,120,120),(3,90,38)]
    ids = ['person_%02d'%i for i in range(1,15)]
    manifest = {'schema':'graspbox_scoring_manifest_v1','class_order':['PG','UG','WH'],
                'evidence_kind':'invented_control','protocol_sha256':sha('invented protocol'),
                'admission':{'census_sha256':sha('invented census'),
                             'semantic_review_sha256':sha('invented semantic review'),
                             'gates':{name:'verified' for name in s.GATES}},
                'participants':[], 'trials':[], 'folds':[]}
    receipts, records = [], []
    for index,(pid,(blocks,trials,events)) in enumerate(zip(ids,expectations),1):
        manifest['participants'].append({'participant_id':pid,'cohort_index':index,
                                         'source_sha256':sha('invented original '+pid)})
        queries = []
        for row in range(trials):
            qid = 'q_'+sha('invented '+pid+' '+str(row))[:32]
            # Deliberately uneven counts: first person is 1 PG, 2 UG, 145 WH.
            label = ('PG' if row==0 else 'UG' if row<3 else 'WH') if index==1 else ['PG','UG','WH'][row%3]
            manifest['trials'].append({'query_id':qid,'participant_id':pid,
                                      'block_id':pid+'_block_'+str(row%blocks),
                                      'session_id':None,'source_row_one_based':row+1,
                                      'label':label,'event_complete':row<events})
            queries.append(qid)
            records.append({'query_id':qid,'fold_id':'fold_'+pid,
                            'probabilities':[1/3,1/3,1/3],'prediction':'PG'})
        training = [p for p in ids if p != pid]
        manifest['folds'].append({'fold_id':'fold_'+pid,'held_out_participant_id':pid,
                                  'training_participant_ids':training,'test_query_ids':queries,
                                  'inner_folds':[{'held_out_participant_id':v,
                                                  'training_participant_ids':[p for p in training if p!=v]}
                                                 for v in training]})
        # Zero fitted transforms is valid for a fixed uniform baseline.
        receipts.append({'fold_id':'fold_'+pid,'held_out_participant_id':pid,
                         'training_participant_ids':training,'isolation_id':'isolation_'+pid,
                         'conversation_id':'conversation_'+pid,'input_modalities':['scalp_EEG'],
                         'network_enabled':False,'cross_fold_state_reused':False,
                         'query_updates':False,'fit_records':[]})
    data = json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()
    header = {'schema':'graspbox_predictions_v1','class_order':['PG','UG','WH'],
              'manifest_sha256':hashlib.sha256(data).hexdigest(),
              'protocol_sha256':manifest['protocol_sha256'],'fold_receipts':receipts}
    return manifest,header,records,data


class ScoreTests(unittest.TestCase):
    def setUp(self):
        self.m,self.h,self.r,self.raw = fixture()
        self.digest = self.h['manifest_sha256']

    def result(self):
        return s.evaluate(self.m,self.h,self.r,self.digest)

    def reject(self, mutate, expression):
        mutate()
        with self.assertRaisesRegex(s.Invalid,expression):
            self.result()

    def onehot(self, shift=0):
        for truth,row in zip(self.m['trials'],self.r):
            index = (['PG','UG','WH'].index(truth['label'])+shift)%3
            row['probabilities'] = [int(i==index) for i in range(3)]
            row['prediction'] = ['PG','UG','WH'][index]

    def test_uniform_independent_closed_form(self):
        result = self.result()
        self.assertAlmostEqual(result['participant_macro']['balanced_accuracy'],1/3)
        self.assertAlmostEqual(result['participant_macro']['log_loss'],math.log(3))
        self.assertAlmostEqual(result['participant_macro']['brier_sum_over_classes'],2/3)
        self.assertEqual(result['coverage']['trials'],1558)
        self.assertEqual(result['coverage']['event_incomplete_retained'],178)
        self.assertEqual(result['participants']['person_01']['class_counts'],[1,2,145])

    def test_perfect_closed_form(self):
        self.onehot()
        macro = self.result()['participant_macro']
        self.assertEqual(macro['balanced_accuracy'],1)
        self.assertEqual(macro['log_loss'],0)
        self.assertEqual(macro['brier_sum_over_classes'],0)
        self.assertEqual(macro['ece_10_equal_width'],0)

    def test_always_wrong_and_valid_zero_floor(self):
        self.onehot(1)
        macro = self.result()['participant_macro']
        self.assertEqual(macro['balanced_accuracy'],0)
        self.assertAlmostEqual(macro['log_loss'],15*math.log(10))
        self.assertEqual(macro['brier_sum_over_classes'],2)
        self.assertEqual(macro['ece_10_equal_width'],1)

    def test_participant_weighting_not_trial_pooling(self):
        self.onehot(1)
        for truth,row in zip(self.m['trials'][:148],self.r[:148]):
            index = ['PG','UG','WH'].index(truth['label'])
            row['probabilities'] = [int(i==index) for i in range(3)]
            row['prediction'] = truth['label']
        result = self.result()
        self.assertAlmostEqual(result['participant_macro']['balanced_accuracy'],1/14)
        self.assertAlmostEqual(result['pooled_accuracy_diagnostic_only'],148/1558)
        self.assertNotAlmostEqual(result['participant_macro']['balanced_accuracy'],148/1558)

    def test_class_balancing_before_person_mean(self):
        self.onehot(1)
        self.r[0]['probabilities'] = [1,0,0]
        self.r[0]['prediction'] = 'PG'
        result = self.result()
        self.assertAlmostEqual(result['participant_macro']['balanced_accuracy'],1/42)
        self.assertAlmostEqual(result['pooled_accuracy_diagnostic_only'],1/1558)

    def test_logloss_participant_weighting(self):
        for truth,row in zip(self.m['trials'],self.r):
            index = ['PG','UG','WH'].index(truth['label'])
            ptrue = 0.5 if truth['participant_id']=='person_01' else 0.25
            row['probabilities'] = [(1-ptrue)/2]*3
            row['probabilities'][index] = ptrue
            row['prediction'] = ['PG','UG','WH'][row['probabilities'].index(max(row['probabilities']))]
        observed = self.result()['participant_macro']['log_loss']
        self.assertAlmostEqual(observed,(math.log(2)+13*math.log(4))/14)
        self.assertNotAlmostEqual(observed,(148*math.log(2)+1410*math.log(4))/1558)

    def test_probability_ties_in_declared_order(self):
        self.r[0].update(probabilities=[0,0.5,0.5],prediction='UG')
        self.result()
        self.r[0]['prediction']='WH'
        with self.assertRaisesRegex(s.Invalid,'argmax'):
            self.result()

    def test_probabilities_are_not_renormalized(self):
        self.onehot()
        self.r[0]['probabilities'] = [0.9999995,0,0]
        result = self.result()
        self.assertAlmostEqual(result['participants']['person_01']['log_loss'],-math.log(0.9999995)/148)

    def test_record_order_irrelevant(self):
        expected=self.result()
        self.r.reverse()
        self.assertEqual(self.result(),expected)

    def test_invalid_probability_vectors(self):
        bad = [[float('nan'),0,1],[float('inf'),0,0],[float('-inf'),1,0],
               [-0.1,0.6,0.5],[1.1,0,0],[0.2,0.2,0.2],[0,0,0],
               [1,0],[1,0,0,0],[True,0,0],['1',0,0],None,[10**1000,0,0]]
        for probabilities in bad:
            with self.subTest(probabilities=str(probabilities)[:80]):
                self.r[0]['probabilities'] = probabilities
                with self.assertRaises(s.Invalid):
                    self.result()

    def test_wrong_class_order(self):
        self.reject(lambda:self.h.update(class_order=['UG','PG','WH']), 'class order')

    def test_wrong_declared_prediction(self):
        self.reject(lambda:self.r[0].update(prediction='WH'), 'argmax')

    def test_missing_prediction(self):
        self.reject(lambda:self.r.pop(), 'prediction row count')

    def test_extra_prediction(self):
        self.reject(lambda:self.r.append(copy.deepcopy(self.r[0])), 'prediction row count')

    def test_unknown_query(self):
        self.reject(lambda:self.r[0].update(query_id='q_'+'f'*32), 'unknown query')

    def test_duplicate_query(self):
        self.reject(lambda:self.r.__setitem__(1,copy.deepcopy(self.r[0])), 'duplicate prediction')

    def test_wrong_query_fold(self):
        self.reject(lambda:self.r[0].update(fold_id='fold_person_02'), 'held-out fold')

    def test_manifest_binding(self):
        self.reject(lambda:self.h.update(manifest_sha256='0'*64), 'manifest binding')

    def test_protocol_binding(self):
        self.reject(lambda:self.h.update(protocol_sha256='0'*64), 'protocol binding')

    def test_unresolved_native_semantics(self):
        self.reject(lambda:self.m['admission']['gates'].update(performed_label_mapping='unresolved'), 'semantic gate')

    def test_missing_participant(self):
        self.reject(lambda:self.m['participants'].pop(), 'fourteen people')

    def test_missing_participant_class(self):
        self.reject(lambda:self.m['trials'][0].update(label='WH'), 'all three classes')

    def test_duplicate_participant(self):
        self.reject(lambda:self.m['participants'][1].update(participant_id='person_01'), 'duplicate participant')

    def test_same_source_for_two_people(self):
        self.reject(lambda:self.m['participants'][1].update(source_sha256=self.m['participants'][0]['source_sha256']), 'original file identities')

    def test_wrong_cohort_index(self):
        self.reject(lambda:self.m['participants'][0].update(cohort_index=True), 'cohort index')

    def test_missing_primary_event_incomplete_rows(self):
        self.reject(lambda:self.m.update(trials=[r for r in self.m['trials'] if r['event_complete']]), '1558')

    def test_wrong_event_flag_count(self):
        self.reject(lambda:self.m['trials'][0].update(event_complete=False), 'event census')

    def test_wrong_event_flag_type(self):
        self.reject(lambda:self.m['trials'][0].update(event_complete=1), 'boolean')

    def test_wrong_per_person_census(self):
        self.reject(lambda:self.m['trials'][0].update(participant_id='person_02',block_id='person_02_block_0'), 'per-person trial count')

    def test_duplicate_original_row(self):
        self.reject(lambda:self.m['trials'][1].update(source_row_one_based=1), 'original rows')

    def test_missing_block(self):
        def change():
            for row in self.m['trials']:
                if row['block_id']=='person_01_block_4': row['block_id']='person_01_block_3'
        self.reject(change,'block count')

    def test_block_cross_person_leak(self):
        self.reject(lambda:self.m['trials'][148].update(block_id='person_01_block_0'), 'block crosses')

    def test_block_cross_session_leak(self):
        self.reject(lambda:self.m['trials'][0].update(session_id='session_other'), 'block crosses')

    def test_session_cross_person_leak(self):
        def change():
            for row in self.m['trials']:
                row['session_id']='shared_session'
        self.reject(change,'session crosses')

    def test_outer_training_leak(self):
        self.reject(lambda:self.m['folds'][0]['training_participant_ids'].__setitem__(0,'person_01'), 'outer training people')

    def test_outer_query_leak(self):
        self.reject(lambda:self.m['folds'][0]['test_query_ids'].__setitem__(0,self.m['folds'][1]['test_query_ids'][0]), 'outer test queries')

    def test_missing_outer_fold(self):
        self.reject(lambda:self.m['folds'].pop(), 'outer folds')

    def test_wrong_outer_identity(self):
        self.reject(lambda:self.m['folds'][0].update(held_out_participant_id='person_02'), 'outer training people')

    def test_inner_training_leak(self):
        self.reject(lambda:self.m['folds'][0]['inner_folds'][0]['training_participant_ids'].__setitem__(0,'person_01'), 'inner training people')

    def test_inner_validation_leak(self):
        self.reject(lambda:self.m['folds'][0]['inner_folds'][0].update(held_out_participant_id='person_01'), 'inner held-out identity')

    def test_missing_inner_fold(self):
        self.reject(lambda:self.m['folds'][0]['inner_folds'].pop(), 'thirteen inner')

    def test_duplicate_inner_fold(self):
        self.reject(lambda:self.m['folds'][0]['inner_folds'].__setitem__(1,copy.deepcopy(self.m['folds'][0]['inner_folds'][0])), 'inner held-out identity')

    def test_receipt_isolation_and_information_failures(self):
        bad=[('isolation_id','isolation_person_02'),('conversation_id','conversation_person_02'),
             ('input_modalities',['scalp_EEG','EMG']),('network_enabled',True),
             ('cross_fold_state_reused',True),('query_updates',True),
             ('held_out_participant_id','person_02')]
        for key,value in bad:
            with self.subTest(key=key):
                original=self.h['fold_receipts'][0][key]
                self.h['fold_receipts'][0][key]=value
                with self.assertRaises(s.Invalid): self.result()
                self.h['fold_receipts'][0][key]=original

    def fit(self,inner=False):
        return {'fit_id':'fit_1','stage':'inner' if inner else 'outer',
                'inner_held_out_participant_id':'person_02' if inner else None,
                'training_participant_ids':['person_%02d'%i for i in range(3 if inner else 2,15)],
                'artifact_id':'artifact_1','artifact_sha256':sha('invented fit'),
                'input_modalities':['scalp_EEG']}

    def test_fit_provenance_valid_outer_and_inner(self):
        fit=self.fit(); inner=self.fit(True)
        inner.update(fit_id='fit_2',artifact_id='artifact_2')
        self.h['fold_receipts'][0]['fit_records']=[fit,inner]
        self.result()

    def test_fit_provenance_held_person_leak(self):
        fit=self.fit(True);fit['training_participant_ids'][0]='person_01'
        self.h['fold_receipts'][0]['fit_records']=[fit]
        with self.assertRaisesRegex(s.Invalid,'fit training leakage'): self.result()

    def test_fit_provenance_inner_validation_leak(self):
        fit=self.fit(True);fit['training_participant_ids'][0]='person_02'
        self.h['fold_receipts'][0]['fit_records']=[fit]
        with self.assertRaisesRegex(s.Invalid,'fit training leakage'): self.result()

    def test_cross_fold_artifact_identity_reuse(self):
        self.h['fold_receipts'][0]['fit_records']=[self.fit()]
        other=self.fit(); other['training_participant_ids']=['person_01']+['person_%02d'%i for i in range(3,15)]
        self.h['fold_receipts'][1]['fit_records']=[other]
        with self.assertRaisesRegex(s.Invalid,'artifact identity'): self.result()

    def test_calibration_bins_boundary_and_sum(self):
        self.onehot()
        result=self.result()
        for person in result['participants'].values():
            self.assertEqual(sum(b['count'] for b in person['calibration_bins']),person['trials'])
            self.assertEqual(person['calibration_bins'][9]['count'],person['trials'])
        self.r[0].update(probabilities=[0.4,0.3,0.3],prediction='PG')
        bins=self.result()['participants']['person_01']['calibration_bins']
        self.assertEqual(bins[4]['count'],1)
        self.assertAlmostEqual(bins[4]['mean_confidence'],0.4)

    def test_paired_bootstrap_uniform_shift_oracle(self):
        uniform=(copy.deepcopy(self.h),copy.deepcopy(self.r))
        self.onehot()
        result=s.compare(self.m,(self.h,self.r),uniform,self.digest)
        ba=result['differences']['balanced_accuracy']
        loss=result['differences']['log_loss']
        self.assertEqual(len(ba['paired_values']),14)
        for value in [ba['mean'],ba['median']]+ba['percentile_95_interval']:
            self.assertAlmostEqual(value,2/3)
        for value in [loss['mean'],loss['median']]+loss['percentile_95_interval']:
            self.assertAlmostEqual(value,-math.log(3))

    def test_paired_bootstrap_identical_zero(self):
        result=s.compare(self.m,(self.h,self.r),(self.h,self.r),self.digest)
        for metric in result['differences'].values():
            self.assertEqual(metric['mean'],0)
            self.assertEqual(metric['percentile_95_interval'],[0,0])

    def test_json_strictness(self):
        for data in (b'{"x":1,"x":2}',b'{"x":NaN}',b'{"x":Infinity}',
                     b'{"x":1e999}',b'\xff',b'[] trailing',b'['*2000+b'0'+b']'*2000):
            with self.subTest(data=data[:32]):
                with self.assertRaises(s.Invalid):s.strict_json(data)

    def test_utf8_only_json_transport(self):
        text = '{"invented": 1}'
        self.assertEqual(s.strict_json(text.encode('utf-8')), {'invented':1})
        for encoding in ('utf-16','utf-32','utf-16-le','utf-16-be'):
            with self.subTest(encoding=encoding):
                with self.assertRaises(s.Invalid):s.strict_json(text.encode(encoding))

    def test_prediction_jsonl_complete_boundary(self):
        raw=('\n'.join(json.dumps(v) for v in [self.h]+self.r)+'\n').encode()
        h,r=s.load_prediction_bytes(raw)
        self.assertEqual(s.evaluate(self.m,h,r,self.digest),self.result())
        for bad in (raw+b'\n',raw.split(b'\n',1)[1],b' '* (s.PREDICTION_LIMIT+1)):
            with self.assertRaises(s.Invalid):s.load_prediction_bytes(bad)

    def test_cli_authenticates_manifest_and_outputs_no_partial_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); mp=root/'manifest.json'; pp=root/'predictions.jsonl'
            mp.write_bytes(self.raw)
            pp.write_text('\n'.join(json.dumps(v) for v in [self.h]+self.r)+'\n')
            argv=[sys.executable,'-B',str(Path(s.__file__).resolve()),'--manifest',str(mp),
                  '--manifest-sha256',self.digest,'--predictions',str(pp)]
            good=subprocess.run(argv,capture_output=True,text=True,timeout=10)
            self.assertEqual(good.returncode,0,good.stderr)
            self.assertEqual(json.loads(good.stdout)['coverage']['trials'],1558)
            mp.write_bytes(self.raw+b' ')
            bad=subprocess.run(argv,capture_output=True,text=True,timeout=10)
            self.assertEqual(bad.returncode,2,bad.stderr)
            result=json.loads(bad.stdout)
            self.assertFalse(result['valid'])
            self.assertNotIn('participant_macro',result)

    def test_bounded_ordinary_file_reader(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); regular=root/'regular'; regular.write_bytes(b'123')
            self.assertEqual(s.bounded_read(regular,3),b'123')
            with self.assertRaises(s.Invalid):s.bounded_read(regular,2)
            link=root/'link';link.symlink_to(regular)
            with self.assertRaises(s.Invalid):s.bounded_read(link,3)
            fifo=root/'fifo';os.mkfifo(fifo)
            with self.assertRaises(s.Invalid):s.bounded_read(fifo,3)


if __name__ == '__main__':
    unittest.main(verbosity=2)
