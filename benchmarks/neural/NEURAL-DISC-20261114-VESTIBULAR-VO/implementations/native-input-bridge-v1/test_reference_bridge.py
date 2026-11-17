"""Generated reference joins only; no scientific results or prior fitting."""
import copy
import unittest
from unittest.mock import patch

import packet_projection as p
import reference_bridge as r
from test_packet_projection import generated_panel,admission_for,KEY


class ReferenceBridgeControls(unittest.TestCase):
    def setUp(self):
        self.prepared=generated_panel()
        self.admission=admission_for(self.prepared)
        projected=p.project(self.prepared,self.admission,accepted_admission_sha256=p.canonical_sha256(self.admission),id_key=KEY)
        self.prior={'schema':'vestibular_supplied_prior_v1','task_id':p.TASK,
                    'prepared_sha256':self.admission['prepared_sha256'],
                    'public_evidence_id':p.canonical_sha256(projected['public']),
                    'information_condition':'full-repeat-v1',
                    'selection':{'id':'generated independently supplied prior','selection_split':'training_only',
                                 'selection_protocol_sha256':'6'*64,
                                 'source_record_ids':[row['id'] for row in self.prepared['records'] if row['partition']=='train']},
                    'cases':[{'id':case['id'],'sample_ticks':case['sample_ticks'],
                              'prediction':[0.25]*len(case['sample_ticks'])} for case in projected['protected']['cases']]}

    def assemble(self):
        return r.assemble(self.prepared,self.admission,self.prior,
                          accepted_admission_sha256=p.canonical_sha256(self.admission),
                          accepted_prior_sha256=p.canonical_sha256(self.prior),id_key=KEY,
                          evaluation_id='generated-evaluation',access_condition='generated-full-repeat')

    def test_complete_reference_uses_unchanged_v2_without_candidate_score_or_prior_synthesis(self):
        evaluator=p.load_evaluator()
        with patch.object(evaluator,'evaluate',side_effect=AssertionError('no candidate scoring')), \
             patch.object(evaluator,'compare',side_effect=AssertionError('no candidate comparison')), \
             patch.object(r.p,'load_evaluator',return_value=evaluator):
            result=self.assemble()
        plan=evaluator.validate_reference(result['reference'])
        self.assertEqual(len(plan['cases']),380)
        self.assertEqual(len(plan['pairs']),35);self.assertEqual(len(plan['neurons']),49)
        self.assertEqual(len(plan['coverage']),60)
        self.assertEqual(result['reference']['cases'][0]['prior'],[0.25]*4)
        self.assertFalse(result['operator_provenance']['reference_competence_established'])
        self.assertEqual(result['reference']['binding']['kind'],'generated_control')

    def test_missing_prior_repeat_or_changed_grid_refused(self):
        for change in ('missing','clock','vector','mask'):
            old=copy.deepcopy(self.prior)
            if change=='missing':self.prior['cases'].pop()
            elif change=='clock':self.prior['cases'][0]['sample_ticks'][0]+=1
            elif change=='vector':self.prior['cases'][0]['prediction'].pop()
            else:self.prior['cases'][0]['valid_mask']=[True]*4
            with self.subTest(change=change),self.assertRaises(ValueError):self.assemble()
            self.prior=old

    def test_prior_cannot_select_a_held_or_excluded_record(self):
        for partition in ('query','excluded'):
            self.prior['selection']['source_record_ids']=[next(row['id'] for row in self.prepared['records'] if row['partition']==partition)]
            with self.subTest(partition=partition),self.assertRaisesRegex(ValueError,'permitted training'):
                self.assemble()

    def test_changed_prior_identity_or_access_support_refused(self):
        with self.assertRaisesRegex(ValueError,'prior identity'):
            r.assemble(self.prepared,self.admission,self.prior,
                       accepted_admission_sha256=p.canonical_sha256(self.admission),accepted_prior_sha256='0'*64,
                       id_key=KEY,evaluation_id='generated',access_condition='generated')
        self.prior['information_condition']='bounded-single-core-v1'
        with self.assertRaisesRegex(ValueError,'full-repeat'):
            self.assemble()

    def test_different_native_units_refused_without_silent_conversion(self):
        self.prepared['records'][0]['clock']['target_unit']='another-velocity-unit'
        self.admission=admission_for(self.prepared)
        projected=p.project(self.prepared,self.admission,accepted_admission_sha256=p.canonical_sha256(self.admission),id_key=KEY)
        self.prior['prepared_sha256']=self.admission['prepared_sha256']
        self.prior['public_evidence_id']=p.canonical_sha256(projected['public'])
        with self.assertRaisesRegex(ValueError,'no implicit conversion'):
            self.assemble()

    def test_nonfinite_prior_cannot_become_an_admitted_reference(self):
        self.prior['cases'][0]['prediction'][0]=True
        with self.assertRaises(ValueError):self.assemble()


if __name__=='__main__':
    unittest.main()
