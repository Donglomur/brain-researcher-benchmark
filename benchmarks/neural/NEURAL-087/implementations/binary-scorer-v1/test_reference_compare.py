"""Generated fixed-reference controls; no authentic observations or fits."""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from contract import VIEWS
import reference_compare as rc


def prediction(rows, values):
    return {'schema_version': 1, 'predictions': [
        {'edge_id': row['edge_id'], 'probability': value}
        for row, value in zip(rows, values, strict=True)]}


def body_and_hash(value):
    body = json.dumps(value, separators=(',', ':'), allow_nan=False).encode()
    return body, hashlib.sha256(body).hexdigest()


class FixedReferenceTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {'edge_id': 'e0', 'pre_id': 1, 'post_id': 2, 'projection': 'V1->V1'},
            {'edge_id': 'e1', 'pre_id': 1, 'post_id': 3, 'projection': 'V1->HVA'},
            {'edge_id': 'e2', 'pre_id': 4, 'post_id': 5, 'projection': 'HVA->HVA'},
        ]
        self.target = {'schema_version': 1, 'targets': [
            {'edge_id': row['edge_id'], 'connected': y}
            for row, y in zip(self.rows, [1, 0, 1], strict=True)]}
        self.candidate = {
            VIEWS[0]: prediction(self.rows, [.6, .4, .6]),
            VIEWS[1]: prediction(self.rows, [.8, .2, .9]),
        }
        self.reference = {
            'schema': rc.REFERENCE_SCHEMA,
            'task_id': 'NEURAL-087',
            'query_roster_sha256': rc.roster_commitment(self.rows),
            'reference_protocol_sha256': 'a' * 64,
            'views': {VIEWS[0]: prediction(self.rows, [.5, .5, .5]),
                      VIEWS[1]: prediction(self.rows, [.7, .3, .7])},
        }
        self.calls = 0

    def private(self):
        self.calls += 1
        return self.target

    def run_compare(self):
        return rc.compare(self.rows, self.candidate, *body_and_hash(self.reference), self.private)

    def test_hand_calculated_equal_neuron_comparisons_and_one_private_load(self):
        result = self.run_compare()
        expected = (-math.log(.8) - math.log(.9)) / 2
        self.assertAlmostEqual(result['primary']['value'], expected)
        self.assertNotAlmostEqual(result['primary']['value'], (-2*math.log(.8)-math.log(.9))/3)
        self.assertAlmostEqual(result['fixed_anatomy_minus_fixed_joint']['value'], math.log(.7/.5))
        self.assertAlmostEqual(result['fixed_minus_candidate_same_information'][VIEWS[1]]['value'],
                               -math.log(.7)-expected)
        self.assertEqual(self.calls, 1)
        self.assertEqual(result['private_loader_calls'], 1)
        self.assertFalse(result['research_qualified'])
        self.assertIsNone(result['scientific_success'])
        json.dumps(result, allow_nan=False)

    def test_weakening_candidate_anatomy_cannot_change_primary_or_fixed_contrasts(self):
        before = self.run_compare()
        self.candidate[VIEWS[0]] = prediction(self.rows, [0, 1, 0])
        after = self.run_compare()
        for key in ('primary', 'fixed_anatomy_minus_fixed_joint'):
            self.assertEqual(before[key], after[key])
        self.assertEqual(before['fixed_minus_candidate_same_information'][VIEWS[1]],
                         after['fixed_minus_candidate_same_information'][VIEWS[1]])
        self.assertEqual(after['fixed_minus_candidate_same_information'][VIEWS[0]]['status'],
                         'negative_infinity')

    def test_signed_negative_fixed_information_effect_is_retained(self):
        self.reference['views'][VIEWS[0]] = prediction(self.rows, [.95, .05, .95])
        result = self.run_compare()
        self.assertLess(result['fixed_anatomy_minus_fixed_joint']['value'], 0)

    def test_invalid_candidate_each_view_rejected_before_private_load(self):
        original = copy.deepcopy(self.candidate)
        for view in VIEWS:
            for kind in ('missing', 'duplicate', 'extra_field', 'boolean', 'nan'):
                with self.subTest(view=view, kind=kind):
                    self.candidate = copy.deepcopy(original)
                    rows = self.candidate[view]['predictions']
                    if kind == 'missing': rows.pop()
                    elif kind == 'duplicate': rows[1] = rows[0]
                    elif kind == 'extra_field': rows[0]['connected'] = 1
                    elif kind == 'boolean': rows[0]['probability'] = True
                    else: rows[0]['probability'] = float('nan')
                    with self.assertRaises(ValueError): self.run_compare()
                    self.assertEqual(self.calls, 0)

    def test_invalid_fixed_predictions_each_view_rejected_before_private_load(self):
        original = copy.deepcopy(self.reference)
        for view in VIEWS:
            for kind in ('missing', 'duplicate', 'unknown_edge', 'out_of_range'):
                with self.subTest(view=view, kind=kind):
                    self.reference = copy.deepcopy(original)
                    rows = self.reference['views'][view]['predictions']
                    if kind == 'missing': rows.pop()
                    elif kind == 'duplicate': rows[1] = rows[0]
                    elif kind == 'unknown_edge': rows[0]['edge_id'] = 'e999'
                    else: rows[0]['probability'] = 1.01
                    with self.assertRaises(ValueError): self.run_compare()
                    self.assertEqual(self.calls, 0)

    def test_wrong_reference_task_schema_roster_and_protocol_rejected(self):
        original = copy.deepcopy(self.reference)
        changes = [('task_id', 'NEURAL-088'), ('schema', 'other'),
                   ('query_roster_sha256', 'b'*64), ('reference_protocol_sha256', None)]
        for key, value in changes:
            with self.subTest(key=key):
                self.reference = copy.deepcopy(original)
                self.reference[key] = value
                with self.assertRaises(ValueError): self.run_compare()
                self.assertEqual(self.calls, 0)

    def test_frozen_bytes_include_whitespace_and_predictions(self):
        body, expected = body_and_hash(self.reference)
        with self.assertRaises(ValueError):
            rc.compare(self.rows, self.candidate, body+b'\n', expected, self.private)
        self.reference['views'][VIEWS[1]]['predictions'][0]['probability'] = .8
        changed, _ = body_and_hash(self.reference)
        with self.assertRaises(ValueError):
            rc.compare(self.rows, self.candidate, changed, expected, self.private)
        self.assertEqual(self.calls, 0)

    def test_reference_roster_pin_binds_neuron_grouping_and_order(self):
        original = copy.deepcopy(self.rows)
        self.rows[0]['pre_id'] = 8
        with self.assertRaises(ValueError): self.run_compare()
        self.rows = list(reversed(original))
        with self.assertRaises(ValueError): self.run_compare()
        self.assertEqual(self.calls, 0)

    def test_prediction_row_order_does_not_change_comparison_arithmetic(self):
        before = self.run_compare()
        for view in VIEWS:
            self.reference['views'][view]['predictions'].reverse()
            self.candidate[view]['predictions'].reverse()
        after = self.run_compare()
        for key in ('primary', 'fixed_reference', 'fixed_anatomy_minus_fixed_joint',
                    'fixed_minus_candidate_same_information'):
            self.assertEqual(before[key], after[key])

    def test_infinite_and_indeterminate_contrasts_are_json_safe(self):
        wrong = prediction(self.rows, [0, 1, 0])
        self.candidate = {v: copy.deepcopy(wrong) for v in VIEWS}
        self.reference['views'] = copy.deepcopy(self.candidate)
        result = self.run_compare()
        self.assertEqual(result['primary']['status'], 'positive_infinity')
        self.assertEqual(result['fixed_anatomy_minus_fixed_joint']['status'], 'undefined_infinity_difference')
        for value in result['fixed_minus_candidate_same_information'].values():
            self.assertEqual(value['status'], 'undefined_infinity_difference')
        json.dumps(result, allow_nan=False)
        self.assertEqual(rc._contrast({1: math.inf, 2: 0.}, {1: 0., 2: math.inf})['status'],
                         'undefined_infinity_difference')

    def test_bad_private_target_is_rejected_after_exactly_one_read(self):
        self.target['targets'][0]['connected'] = True
        with self.assertRaises(ValueError): self.run_compare()
        self.assertEqual(self.calls, 1)

    def test_exact_6691_generated_support_kept_complete(self):
        rows = [{'edge_id': f'e{i}', 'pre_id': 100+i%21, 'post_id': 1000+i,
                 'projection': 'V1->V1'} for i in range(6691)]
        preds = {v: prediction(rows, [.5]*6691) for v in VIEWS}
        ref = {**self.reference, 'views': copy.deepcopy(preds),
               'query_roster_sha256': rc.roster_commitment(rows)}
        target = {'schema_version': 1, 'targets': [
            {'edge_id': row['edge_id'], 'connected': i%2} for i, row in enumerate(rows)]}
        calls = []
        result = rc.compare(rows, preds, *body_and_hash(ref), lambda: (calls.append(1), target)[1])
        self.assertEqual(calls, [1])
        self.assertEqual(result['candidate']['support']['pairs'], 6691)
        self.assertEqual(result['candidate']['support']['presynaptic_neurons'], 21)
        self.assertAlmostEqual(result['primary']['value'], math.log(2))
        self.assertEqual(result['fixed_minus_candidate_same_information'][VIEWS[1]]['value'], 0.)

    def test_reference_and_output_aliases_rejected_before_body_reader(self):
        with tempfile.TemporaryDirectory() as temp:
            names = ('binding', 'roster', 'anatomy', 'joint', 'reference', 'targets', 'output')
            original = {name: Path(temp)/name for name in names}
            for first, second in [('reference', 'targets'), ('output', 'reference')]:
                values = dict(original); values[first] = values[second]
                args = SimpleNamespace(**values, binding_sha256='0'*64, reference_sha256='a'*64)
                with mock.patch.object(rc, 'load_bound_roster', side_effect=AssertionError('body opened')):
                    with self.assertRaises(ValueError): rc.main(args)

    def test_duplicate_json_reference_field_rejected_before_private_read(self):
        body, _ = body_and_hash(self.reference)
        bad = b'{"task_id":"NEURAL-087",'+body[1:]
        with self.assertRaises(ValueError):
            rc.compare(self.rows, self.candidate, bad, hashlib.sha256(bad).hexdigest(), self.private)
        self.assertEqual(self.calls, 0)

    def test_reference_hardlink_alias_rejected_before_body_reader(self):
        with tempfile.TemporaryDirectory() as temp:
            names = ('binding', 'roster', 'anatomy', 'joint', 'reference', 'targets', 'output')
            values = {name: Path(temp)/name for name in names}
            values['targets'].write_bytes(b'generated-not-read')
            os.link(values['targets'], values['reference'])
            args = SimpleNamespace(**values, binding_sha256='0'*64, reference_sha256='a'*64)
            with mock.patch.object(rc, 'load_bound_roster', side_effect=AssertionError('body opened')):
                with self.assertRaises(ValueError): rc.main(args)


if __name__ == '__main__':
    unittest.main(verbosity=1)
