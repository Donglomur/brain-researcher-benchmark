"""Generated selector and continuous-effect controls; no native/model execution."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import sys
import unittest

import numpy as np

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import improvement as m


def packet(role):
    return {'schema':'language-original-figure3b-scores/v1','role':role,
            'selection_sha256':hashlib.sha256(m.encoded(m.selection())).hexdigest(),
            'source_support_sha256':'1'*64,'prediction_run_sha256':('2' if role=='candidate' else '3')*64,
            'scores':[{'context':c,'pearson_r':0.0} for c in m.contexts()], 'execution_qualified':False}


class ImprovementControls(unittest.TestCase):
    def test_selector_finds_exact42_from_all58926_source_coordinates(self):
        path=HERE.parent/'original-protected-layout-v1/layout.py'
        spec=importlib.util.spec_from_file_location('_improvement_source_layout',path)
        source=importlib.util.module_from_spec(spec);spec.loader.exec_module(source)
        def rows():
            for r in source.iter_source_contexts():
                field,family,_,_,_,_=source.specs()[r['field_index']]
                yield {'context':{'session':source.SESSIONS[r['session_index']], 'field':field,'family':family,
                    'layer':r['layer'],'lag_index':r['lag_index'],'lag_bins':r['lag_bins']}}
        selected=list(m.select_stream(rows()))
        self.assertEqual([r['context'] for r in selected],list(m.contexts()))
        self.assertEqual(len(selected),42)
        self.assertEqual(len({r['context']['session'] for r in selected}),14)
        self.assertEqual(m.selection()['held_sentence_software_callbacks'],5685)
        self.assertFalse(m.selection()['callbacks_are_native_process_or_API_requirements'])

    def test_equal_session_effect_is_not_replaced_by_equal_person_weighting(self):
        c,r=packet('candidate'),packet('provided_author_reference')
        for row in c['scores']:
            row['pearson_r']=.24 if row['context']['session'].startswith('p1_') else .1
        result=m.compare(c,r)
        self.assertAlmostEqual(result['equal_session_paired_mean_delta'],.12)
        self.assertNotAlmostEqual(result['equal_session_paired_mean_delta'],.1175)
        self.assertAlmostEqual(sum(p['contribution_to_equal_session_delta'] for p in result['participants']),.12)
        self.assertEqual(len(result['sessions']),14);self.assertEqual(len(result['participants']),8)
        p1=result['participants'][0]
        self.assertAlmostEqual(p1['leave_one_person_out_equal_remaining_session_delta'],.1)
        self.assertEqual(p1['remaining_session_count'],12)
        self.assertIsNone(result['binary_win']);self.assertIsNone(result['uncertainty_method'])

    def test_fixed_three_lag_means_and_signed_negative_delta(self):
        c,r=packet('candidate'),packet('provided_author_reference')
        for i,row in enumerate(c['scores']): row['pearson_r']=(.1,.2,.3)[i%3]
        for i,row in enumerate(r['scores']): row['pearson_r']=(.3,.2,.4)[i%3]
        result=m.compare(c,r)
        self.assertAlmostEqual(result['candidate_equal_session_mean'],.2)
        self.assertAlmostEqual(result['equal_session_paired_mean_delta'],-.1)
        self.assertFalse(result['scientific_qualification'])

    def test_undefined_correlation_propagates_without_favorable_session_drop(self):
        c,r=packet('candidate'),packet('provided_author_reference')
        c['scores'][0]['pearson_r']=None
        result=m.compare(c,r)
        self.assertIsNone(result['equal_session_paired_mean_delta'])
        self.assertEqual(result['defined_session_pairs'],13)
        self.assertEqual(len(result['sessions']),14)
        self.assertIsNone(result['participants'][0]['contribution_to_equal_session_delta'])
        self.assertEqual(result['participants'][0]['leave_one_person_out_equal_remaining_session_delta'],0.0)

    def test_missing_reordered_wrong_layer_or_wrong_support_refused(self):
        for fault in ('missing','reordered','layer','support'):
            with self.subTest(fault=fault):
                c,r=packet('candidate'),packet('provided_author_reference')
                if fault=='missing':c['scores'].pop()
                if fault=='reordered':c['scores'][0],c['scores'][1]=c['scores'][1],c['scores'][0]
                if fault=='layer':c['scores'][0]['context']['layer']=6
                if fault=='support':c['source_support_sha256']='4'*64
                with self.assertRaises(ValueError):m.compare(c,r)

    def test_partial_selector_cannot_masquerade_as_complete_endpoint(self):
        with self.assertRaisesRegex(ValueError,'All14sessions'):
            list(m.select_stream({'context':c} for c in m.contexts()[:-1]))
        with self.assertRaisesRegex(ValueError,'repeat/reordering'):
            list(m.select_stream({'context':c} for c in reversed(m.contexts())))

    def test_nonfinite_boolean_and_out_of_range_correlations_refused(self):
        for value in (float('nan'),float('inf'),True,1.001,-1.001):
            c,r=packet('candidate'),packet('provided_author_reference');c['scores'][0]['pearson_r']=value
            with self.assertRaises(ValueError):m.compare(c,r)

    def test_asserted_execution_flags_never_promote_continuous_effect_to_win(self):
        c,r=packet('candidate'),packet('provided_author_reference')
        c['execution_qualified']=r['execution_qualified']=True
        for row in c['scores']:row['pearson_r']=.9
        result=m.compare(c,r)
        self.assertGreater(result['equal_session_paired_mean_delta'],.8)
        self.assertFalse(result['execution_qualification_independently_verified'])
        self.assertFalse(result['scientific_qualification']);self.assertIsNone(result['binary_win'])


if __name__=='__main__':unittest.main()
