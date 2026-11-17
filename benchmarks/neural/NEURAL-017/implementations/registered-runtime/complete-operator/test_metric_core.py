"""Generated numerical controls only; no files, models or native campaign.

Run directly with Python and NumPy. The grade controls exercise its real fixed
support admission using broadcast arrays and stop before any prediction work.
"""
import importlib.util
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import numpy as np


PACKAGE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "_nlb_numeric_control", PACKAGE / "nlb" / "__init__.py",
    submodule_search_locations=[str(PACKAGE / "nlb")])
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
from _nlb_numeric_control import arrays, contracts, metric_core, programme, scoring


class MetricCoreTests(unittest.TestCase):
    def score(self, values, expected=None, mask=None):
        values = np.asarray(values)
        if expected is None:
            expected = np.ones(values.shape, dtype=np.float64)
        return metric_core.poisson_bits_per_spike(values, expected, mask)

    def test_uint64_regression_rejects_original_value_above_boundary(self):
        value = np.array([[[2**53 + 1]]], dtype=np.uint64)
        self.assertEqual(float(value.item()), float(2**53))
        with self.assertRaisesRegex(ValueError, "Observed targets"):
            self.score(value, np.array([[[float(2**53)]]]))

    def test_signed_unsigned_boundary_and_extrema(self):
        for dtype in (np.int64, np.uint64, np.dtype('>i8'), np.dtype('>u8')):
            for value in (2**53 - 1, 2**53):
                with self.subTest(dtype=dtype, value=value):
                    result = self.score(np.array([[[value]]], dtype=dtype),
                                        np.array([[[float(value)]]]))
                    self.assertEqual(result['status'], 'scored')
                    self.assertEqual(result['target_spikes'], value)
                    self.assertEqual(result['co_bps'], 0.0)
            for value in (2**53 + 1, 2**53 + 2, np.iinfo(dtype).max):
                with self.subTest(dtype=dtype, value=value):
                    with self.assertRaisesRegex(ValueError, "Observed targets"):
                        self.score(np.array([[[value]]], dtype=dtype))

    def test_small_integer_dtypes_and_python_integer_lists(self):
        for dtype in (np.int8, np.int16, np.int32, np.int64,
                      np.uint8, np.uint16, np.uint32, np.uint64):
            with self.subTest(dtype=dtype):
                target = np.array([[[0], [1]], [[2], [3]]], dtype=dtype)
                expected = np.array([[[0.5], [1.0]], [[2.0], [4.0]]])
                self.assertEqual(self.score(target, expected),
                                 self.score(target.astype(np.float64), expected))
        self.assertEqual(self.score([[[1]]])['target_spikes'], 1.0)

    def test_real_array_default_conversion_and_preserved_dtype(self):
        original = np.array([2**53 + 1], dtype=np.uint64)
        preserved = metric_core.real_array(original, 'targets', preserve_dtype=True)
        self.assertIs(preserved, original)
        self.assertEqual(int(preserved[0]), 2**53 + 1)
        self.assertEqual(metric_core.real_array(original, 'predictions').dtype,
                         np.dtype('float64'))

    def test_floating_dtypes_and_next_representable_bound(self):
        for dtype in (np.float16, np.float32, np.float64, np.longdouble):
            with self.subTest(dtype=dtype):
                self.assertEqual(self.score(np.array([[[2]]], dtype=dtype))['target_spikes'], 2.0)
                with self.assertRaisesRegex(ValueError, "Observed targets"):
                    self.score(np.array([[[1.5]]], dtype=dtype))
        for dtype in (np.float32, np.float64, np.longdouble):
            boundary = np.array([[[2**53]]], dtype=dtype)
            with self.subTest(dtype=dtype):
                self.assertEqual(self.score(boundary)['target_spikes'], 2**53)
                with self.assertRaisesRegex(ValueError, "Observed targets"):
                    self.score(np.nextafter(boundary, np.array(np.inf, dtype=dtype)))

    @unittest.skipUnless(np.finfo(np.longdouble).nmant > 52,
                         'platform longdouble has no extra precision')
    def test_extended_precision_fraction_cannot_round_into_domain(self):
        fractional = np.nextafter(np.longdouble(1), np.longdouble(2))
        self.assertEqual(float(fractional), 1.0)
        for value in (fractional, np.longdouble(2**53) + 1):
            with self.subTest(value=str(value)):
                with self.assertRaisesRegex(ValueError, "Observed targets"):
                    self.score(np.array([[[value]]], dtype=np.longdouble))

    def test_original_invalid_types_and_count_values(self):
        for value in (True, 1 + 0j, '1', np.datetime64('2026-01-01')):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "must be real numeric"):
                    self.score(np.array([[[value]]]))
        with self.assertRaisesRegex(ValueError, "must be real numeric"):
            self.score(np.array([[[1]]], dtype=object))
        for value in (-1, -0.5, np.inf, -np.inf, np.nan):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "Observed targets"):
                    self.score(np.array([[[value]]]))

    def test_only_observed_counts_are_admitted(self):
        mask = np.array([[[True], [False]]])
        for dtype, invalid in ((np.uint64, 2**64 - 1), (np.int64, -1),
                               (np.float64, np.nan), (np.float64, np.inf),
                               (np.float64, 1.5)):
            with self.subTest(dtype=dtype, invalid=invalid):
                target = np.array([[[1], [invalid]]], dtype=dtype)
                result = self.score(target, mask=mask)
                self.assertEqual(result['co_bps'], 0.0)
                self.assertEqual(result['valid_cells'], 1)
                self.assertEqual(result['target_spikes'], 1.0)

    def test_noncontiguous_and_readonly_inputs_are_not_modified(self):
        original = np.array([[[0], [99], [1], [99]],
                             [[2], [99], [3], [99]]], dtype=np.uint64)
        target = original[:, ::2, :]
        target.setflags(write=False)
        saved = original.copy()
        self.assertFalse(target.flags.c_contiguous)
        self.assertEqual(self.score(target), self.score(target.copy()))
        np.testing.assert_array_equal(original, saved)

    def test_predictions_keep_positive_finite_domain_without_count_cap(self):
        target = np.array([[[1]]], dtype=np.uint64)
        for value in (2**53 + 2, 2**64 - 1, 1e100):
            with self.subTest(value=value):
                result = self.score(target, np.array([[[value]]]))
                self.assertEqual(result['status'], 'scored')
                self.assertTrue(math.isfinite(result['co_bps']))
        for value in (0, -1, np.inf, np.nan):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, 'Predictions must'):
                    self.score(np.array([[[1], [1]]]),
                               np.array([[[1.0], [value]]]),
                               np.array([[[True], [False]]]))

    def test_zero_total_null_neurons_and_independent_poisson_equation(self):
        zero = self.score(np.zeros((2, 2, 2), dtype=np.uint64))
        self.assertEqual(zero['status'], 'undefined_zero_target_spikes')
        self.assertIsNone(zero['co_bps'])
        self.assertEqual(zero['target_spikes'], 0.0)
        target = np.array([[[0, 0], [1, 0]], [[2, 0], [3, 0]]], dtype=np.uint64)
        expected = np.array([[[0.5, 0.1], [1.0, 0.2]], [[2.5, 0.3], [4.0, 0.4]]])
        mask = np.array([[[True, True], [True, False]], [[False, True], [True, True]]])
        score = self.score(target, expected, mask)
        improvement = 0.0
        total = 0
        for unit in range(target.shape[2]):
            cells = [(trial, time) for trial in range(target.shape[0])
                     for time in range(target.shape[1]) if mask[trial, time, unit]]
            mean = sum(int(target[t, b, unit]) for t, b in cells) / len(cells)
            if mean == 0:
                mean = 1e-9
            for trial, time in cells:
                y = int(target[trial, time, unit])
                rate = float(expected[trial, time, unit])
                prediction_ll = y * math.log(rate) - rate - math.lgamma(y + 1)
                null_ll = y * math.log(mean) - mean - math.lgamma(y + 1)
                improvement += prediction_ll - null_ll
                total += y
        self.assertEqual(score['target_spikes'], total)
        self.assertEqual(score['valid_cells'], int(mask.sum()))
        self.assertEqual(score['null_policy'], 'evaluation_per_neuron_mean')
        self.assertAlmostEqual(score['log_likelihood_improvement_nats'], improvement, places=13)
        self.assertAlmostEqual(score['co_bps'], improvement / (total * math.log(2)), places=13)

    def test_shape_mask_and_per_neuron_support_remain_strict(self):
        for target in (np.ones((1, 1)), np.ones((1, 0, 1))):
            with self.assertRaisesRegex(ValueError, 'matching nonempty'):
                self.score(target)
        target = np.ones((1, 2, 2))
        for mask in (np.ones(target.shape, dtype=np.uint8), np.ones((1, 1, 1), dtype=bool)):
            with self.assertRaisesRegex(ValueError, 'Mask must'):
                self.score(target, mask=mask)
        with self.assertRaisesRegex(ValueError, 'No valid targets'):
            self.score(target, mask=np.array([[[True, False], [True, False]]]))

    def test_score_submission_alignment_and_target_boundary(self):
        target = np.array([[[1, 2]], [[3, 4]]], dtype=np.uint64)
        expected = np.array([[[1.5, 2.5]], [[2.5, 3.5]]])
        gold = {'trial_ids': np.array(['t1', 't2']), 'heldout_unit_ids': np.array(['u1', 'u2']),
                'bin_left_edges_ms': np.array([0]), 'panel_fingerprint': 'generated',
                'target_counts': target, 'valid_mask': np.ones(target.shape, dtype=bool)}
        submission = {'trial_ids': np.array(['t2', 't1']), 'heldout_unit_ids': np.array(['u2', 'u1']),
                      'bin_left_edges_ms': np.array([0]), 'panel_fingerprint': 'generated',
                      'prediction_units': 'expected_spikes_per_bin',
                      'expected_counts': expected[::-1, :, ::-1]}
        self.assertEqual(metric_core.score_submission(submission, gold), self.score(target, expected))
        target[0, 0, 0] = 2**53 + 1
        with self.assertRaisesRegex(ValueError, 'Observed targets'):
            metric_core.score_submission(submission, gold)


class ProtectedGradeAdmissionTests(unittest.TestCase):
    """Actual grade() admission, generated broadcast support; no prediction work."""
    def inputs(self, value, dtype):
        shape = (574, 140, 45)
        targets = {'counts_heldout': np.broadcast_to(np.array(value, dtype=dtype), shape),
                   'valid_mask': np.broadcast_to(np.array(True), shape),
                   'trial_ids': np.array(['generated-axis']), 'unit_ids': np.array(['generated-unit']),
                   'panel_fingerprint': np.array('generated')}
        keys = {programme.group_id(g) for g in programme.expected_groups()}
        keys |= {programme.bank_id(c, r) for c in programme.CONDITIONS
                 for r in programme.allowed_references(c)}
        keys |= {'TOOL_ONLY_BATCH', 'TOOL_ONLY_CASE'}
        predictions = dict.fromkeys(keys, b'')
        support = {'eval_trial_ids': targets['trial_ids'], 'heldout_unit_ids': targets['unit_ids'],
                   'panel_fingerprint': 'generated'}
        return predictions, targets, support, {'contrasts': [None] * 65}

    def test_grade_rejects_original_out_of_domain_before_candidate_work(self):
        for dtype, value in ((np.uint64, 2**53 + 1), (np.int64, 2**53 + 1),
                             (np.uint64, 2**64 - 1), (np.int64, -1),
                             (np.float64, 0.5), (np.float64, np.nan), (np.bool_, True)):
            with self.subTest(dtype=dtype, value=value):
                args = self.inputs(value, dtype)
                owners = []
                with patch.object(arrays, 'prediction') as prediction:
                    with self.assertRaisesRegex(contracts.Refusal, 'valid original count targets'):
                        scoring.grade(*args, owners)
                    prediction.assert_not_called()
                self.assertEqual(owners, [])

    def test_grade_exact_boundary_and_small_integers_reach_prediction_gate(self):
        class PredictionGateReached(Exception):
            pass
        for dtype, value in ((np.uint64, 2**53), (np.int64, 2**53), (np.uint8, 1)):
            with self.subTest(dtype=dtype, value=value):
                args = self.inputs(value, dtype)
                owners = []
                with patch.object(arrays, 'prediction', side_effect=PredictionGateReached) as prediction:
                    with self.assertRaises(PredictionGateReached):
                        scoring.grade(*args, owners)
                    prediction.assert_called_once()
                self.assertEqual(owners, [])

    def test_grade_fixed_support_is_not_weakened(self):
        args = self.inputs(1, np.uint64)
        args[1]['valid_mask'] = np.broadcast_to(np.array(False), (574, 140, 45))
        with patch.object(arrays, 'prediction') as prediction:
            with self.assertRaisesRegex(contracts.Refusal, 'complete fixed target support'):
                scoring.grade(*args, [])
            prediction.assert_not_called()


if __name__ == '__main__':
    unittest.main()
