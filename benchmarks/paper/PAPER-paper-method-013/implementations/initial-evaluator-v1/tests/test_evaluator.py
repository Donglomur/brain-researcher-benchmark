"""Analytical controls, no biological data or model execution."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest

import numpy as np

MODULE = Path(__file__).resolve().parents[1] / 'evaluator.py'
spec = importlib.util.spec_from_file_location('deepcaimx_evaluator', MODULE)
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


def mask(indices, width=6):
    out = np.zeros((1, 1, width), dtype=bool)
    out[0, 0, indices] = True
    return out


class MetricsTests(unittest.TestCase):
    def test_strict_threshold_and_analytical_counts(self):
        r = mask([0, 1])
        p = mask([0])
        self.assertEqual(e.pairwise_iou(r, p)[0, 0], .5)
        self.assertEqual(e.match_iou(e.pairwise_iou(r, p)), [])
        r = mask([0, 1, 2])
        p = np.concatenate((mask([0, 1]), mask([4])))
        score = e.score_recording(r, p, [[1, 2, 3]], [[3, 2, 1], [0, 1, 2]])
        self.assertEqual((score['true_positive'], score['false_positive'], score['false_negative']), (1, 1, 0))
        self.assertEqual(score['precision'], .5)
        self.assertEqual(score['recall'], 1)
        self.assertAlmostEqual(score['f1'], 2 / 3)
        self.assertAlmostEqual(score['trace_mean_pearson_r'], -1)

    def test_best_overlap_and_ambiguity_fail_closed(self):
        self.assertEqual(e.match_iou([[.6, .9]]), [(0, 1, .9)])
        self.assertEqual(e.match_iou([[1., 1.]]), [(0, 0, 1.)])
        duplicate = e.score_recording(mask([0]), np.concatenate((mask([0]), mask([0]))), [[1, 2]], [[1, 2], [2, 1]])
        self.assertEqual(duplicate['false_positive'], 1)
        self.assertAlmostEqual(duplicate['f1'], 2 / 3)
        with self.assertRaisesRegex(ValueError, 'multiple reference'):
            e.match_iou([[.8, .7], [.9, .2]])

    def test_empty_prediction_preserves_false_negatives(self):
        result = e.score_recording(mask([0]), np.zeros((0, 1, 6)), [[1, 2]], np.zeros((0, 2)))
        self.assertEqual(result['f1'], 0)
        self.assertEqual(result['false_negative'], 1)
        self.assertIsNone(result['trace_mean_pearson_r'])

    def test_constant_trace_is_undefined(self):
        result = e.score_recording(mask([0]), mask([0]), [[1, 1, 1]], [[1, 2, 3]])
        self.assertIsNone(result['trace_mean_pearson_r'])
        self.assertEqual(result['trace_undefined_count'], 1)
        self.assertEqual(result['trace_evaluable_reference_fraction'], 0)

    def test_scale_offset_and_large_values(self):
        self.assertAlmostEqual(e._pearson(np.array([0., 1., 2.]), np.array([7., 10., 13.])), 1)
        self.assertAlmostEqual(e._pearson(np.array([0., 1e300, 2e300]), np.array([0., 1., 2.])), 1)
        self.assertAlmostEqual(e._pearson(np.array([0., 1e-300, 2e-300]), np.array([0., 1., 2.])), 1)

    def test_bad_arrays_fail(self):
        for value in (np.full((1, 1, 6), np.nan), np.full((1, 1, 6), .5), np.zeros((1, 1, 6))):
            with self.assertRaises(ValueError):
                e.validate_masks(value, 'bad')
        with self.assertRaises(ValueError):
            e.score_recording(mask([0]), mask([0]), [[1, 2]], [[1, np.inf]])

    def test_tile_layout_has_exact_padding_and_order(self):
        tiles = e.tile_layout()
        self.assertEqual(len(tiles), 1053)
        self.assertEqual(tiles[1]['start_zero_based'], [53, 0, 0])
        self.assertEqual(tiles[9]['start_zero_based'], [0, 53, 0])
        self.assertEqual(tiles[81]['start_zero_based'], [0, 0, 400])
        self.assertEqual(tiles[-1]['stop_exclusive'], [488, 488, 5200])
        self.assertEqual(tiles[-1]['valid_stop_exclusive'], [488, 488, 5000])


class CohortTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        masks = np.zeros((2, 488, 488), bool)
        masks[0, 0, :3] = 1
        masks[1, 1, :3] = 1
        traces = np.stack((np.arange(5000), -np.arange(5000)))
        self.rpin = self.arrays('ref.npz', masks, traces)
        self.cpin = self.arrays('candidate.npz', masks[:1], traces[:1])
        self.bpin = self.arrays('baseline.npz', masks, -traces)
        common = dict(schema_version=1, task_id=e.TASK_ID, frame_labels_inclusive=[18501, 23500], frame_count=5000, image_shape=[488, 488], coordinate_system='zero_based_row_column')
        self.ref = dict(common, reference_kind='author_constructed_fluorescence', source_transformation_receipt='generated engineering fixture; no authentic admission', recordings=self.rows('ref.npz', self.rpin))
        self.ref_path = self.root / 'reference.json'
        self.ref_path.write_text(json.dumps(self.ref))
        candidate = dict(common, method_id='candidate', role='candidate', implementation_identity='generated identity control', recordings=self.rows('candidate.npz', self.cpin, 2))
        baseline = dict(common, method_id='baseline', role='baseline', implementation_identity='generated sign inversion', recordings=self.rows('baseline.npz', self.bpin, 4))
        self.sub = dict(policy_id=e.POLICY_ID, reference_manifest_sha256=e._sha256(self.ref_path), methods=[candidate, baseline])
        self.sub_path = self.root / 'submission.json'

    def tearDown(self):
        self.temp.cleanup()

    def arrays(self, name, masks, traces):
        path = self.root / name
        np.savez_compressed(path, masks=masks, traces=traces)
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def rows(self, name, pin, seconds=None):
        result = []
        for rid, depth in e.RECORDINGS.items():
            row = dict(recording_id=rid, depth_um=depth, array_file=name, array_sha256=pin)
            if seconds:
                row['runtime'] = dict(wall_seconds=seconds, hardware_id='generated-fixture-cpu', environment_id='same-fixture', scope='processing_excluding_data_loading_and_writing')
            result.append(row)
        return result

    def run_score(self):
        self.sub_path.write_text(json.dumps(self.sub))
        return e.evaluate(self.ref_path, self.sub_path)

    def test_full_cohort_common_trace_endpoint_and_runtime(self):
        result = self.run_score()
        self.assertEqual(result['scientific_qualification'], 'unknown')
        candidate = result['methods'][0]
        self.assertEqual(candidate['pooled_roi_counts']['false_negative'], 10)
        self.assertAlmostEqual(candidate['pooled_roi_counts']['f1'], 2 / 3)
        self.assertEqual(set(candidate['by_depth_um']), {'175', '275', '375', '550', '625'})
        common = result['all_method_common_reference_trace_endpoint']
        self.assertTrue(all(r['common_detected_reference_indices'] == [0] for r in common))
        paired = result['paired_comparisons'][0]
        self.assertEqual(paired['baseline_over_candidate_total_runtime'], 2)
        self.assertAlmostEqual(paired['paired_recordings'][0]['common_reference_mean_pearson_r_delta'], 2)

    def test_no_cohort_subsetting_or_wrong_depth(self):
        self.sub['methods'][0]['recordings'].pop()
        with self.assertRaisesRegex(ValueError, 'ten-recording'):
            self.run_score()

    def test_duplicate_recording_and_wrong_frame_window(self):
        self.sub['methods'][0]['recordings'][1] = self.sub['methods'][0]['recordings'][0]
        with self.assertRaisesRegex(ValueError, 'duplicate recording'):
            self.run_score()
        self.sub['methods'][0]['frame_labels_inclusive'] = [0, 4999]
        with self.assertRaisesRegex(ValueError, 'frame window'):
            self.run_score()

    def test_sha_integrity_and_reference_identity(self):
        self.sub['reference_manifest_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'different reference'):
            self.run_score()
        self.sub['reference_manifest_sha256'] = e._sha256(self.ref_path)
        self.sub['methods'][0]['recordings'][0]['array_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'SHA256'):
            self.run_score()

    def test_runtime_scope_and_hardware_are_paired(self):
        self.sub['methods'][1]['recordings'][0]['runtime']['hardware_id'] = 'other'
        with self.assertRaisesRegex(ValueError, 'identical hardware'):
            self.run_score()

    def test_cli_refuses_existing_payload_output(self):
        self.sub_path.write_text(json.dumps(self.sub))
        target = self.root / 'candidate.npz'
        before = target.read_bytes()
        result = subprocess.run([sys.executable, str(MODULE), 'score', '--reference', str(self.ref_path), '--submission', str(self.sub_path), '--output', str(target)], capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(target.read_bytes(), before)

    def test_common_trace_endpoint_excludes_extra_detected_reference(self):
        result = self.run_score()
        self.assertEqual(result['methods'][1]['recordings'][0]['trace_defined_count'], 2)
        self.assertEqual(result['all_method_common_reference_trace_endpoint'][0]['methods']['baseline']['defined_count'], 1)

    def test_malformed_method_is_rejected_cleanly(self):
        self.sub['methods'][0] = 'not-an-object'
        with self.assertRaisesRegex(ValueError, 'method must be an object'):
            self.run_score()

    def test_runtime_overflow_is_rejected(self):
        for row in self.sub['methods'][0]['recordings']:
            row['runtime']['wall_seconds'] = 1e308
        with self.assertRaisesRegex(ValueError, 'total runtime'):
            self.run_score()
        with self.assertRaisesRegex(ValueError, 'finite wall_seconds'):
            e._runtime_seconds(10 ** 1000)

    def test_runtime_ratio_overflow_and_underflow_rejected(self):
        for numerator, denominator in [(1e300, 1e-300), (1e-300, 1e300)]:
            with self.assertRaisesRegex(ValueError, 'runtime ratio'):
                e._runtime_ratio(numerator, denominator)

    def test_json_duplicate_key_rejected(self):
        self.sub_path.write_text('{"a":1,"a":2}')
        with self.assertRaisesRegex(ValueError, 'duplicate JSON key'):
            e._read_json(self.sub_path)


if __name__ == '__main__':
    unittest.main()
