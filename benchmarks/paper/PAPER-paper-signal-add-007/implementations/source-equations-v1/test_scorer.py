"""Small generated controls. No authentic observations or model inference."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import statistics
import tempfile
import unittest

import numpy as np

spec = importlib.util.spec_from_file_location("icnet_equations", Path(__file__).with_name("scorer.py"))
scorer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scorer)


def oracle(arrays, ddof):
    # Independent literal equation implementation using Python's statistics;
    # no scorer moments, covariance identity or block machinery is reused.
    a, b, p, q, e, f = [list(map(float, x.ravel())) for x in arrays]
    var = statistics.pvariance if ddof == 0 else statistics.variance
    noise = var([x-y for x, y in zip(a, b)]) / 2
    mse = (sum((x-y)**2 for x, y in zip(a, e))
           + sum((x-y)**2 for x, y in zip(b, f))) / (2*len(a))
    corr = 50 * (statistics.correlation(a, p) + statistics.correlation(b, q)) / statistics.correlation(a, b)
    explained = 100 * (1 - (mse-noise) / ((var(a)+var(b))/2 - noise))
    return corr, explained, noise


class EquationsTests(unittest.TestCase):
    def setUp(self):
        self.a = np.array([[0, 8, 2], [1, 9, 3], [4, 8, 1], [2, 11, 3],
                           [5, 10, 4], [3, 14, 5], [6, 12, 3], [2, 9, 1]])
        self.b = self.a + np.array([[0], [1], [0], [2], [1], [0], [1], [0]])
        self.p = self.a + np.array([1, 2, 0])
        self.q = self.b + np.array([0, 1, 2])
        self.arrays = (self.a, self.b, self.p, self.q, self.a*0.8+0.5, self.b*0.9+0.1)

    def score(self, arrays=None, mask=None, ddof=0, block=2):
        return scorer.score_case(*(self.arrays if arrays is None else arrays),
                                 eligible_mask=[True]*3 if mask is None else mask,
                                 unit_ids=["a", "b", "c"], variance_ddof=ddof,
                                 block_units=block)

    def test_equations_match_independent_oracle_both_variance_conventions(self):
        for ddof in (0, 1):
            result = self.score(ddof=ddof)
            expected = oracle(self.arrays, ddof)
            for key, value in zip(("correlation_explained_percent", "variance_explained_percent", "noise_variance"), expected):
                self.assertAlmostEqual(result["flattened"][key], value, places=10)
            for index, unit in enumerate(result["by_unit"]):
                expected = oracle([x[:, index] for x in self.arrays], ddof)
                self.assertAlmostEqual(unit["correlation_explained_percent"], expected[0], places=10)
                self.assertAlmostEqual(unit["variance_explained_percent"], expected[1], places=10)

    def test_flattening_is_not_average_unit_score(self):
        result = self.score()
        unit_average = statistics.mean(x["correlation_explained_percent"] for x in result["by_unit"])
        self.assertGreater(abs(result["flattened"]["correlation_explained_percent"] - unit_average), 1)

    def test_column_blocking_does_not_change_score(self):
        for block in (1, 3, 32):
            self.assertEqual(self.score(block=block), self.score(block=2))

    def test_source_mask_is_applied_identically_to_every_array(self):
        result = self.score(mask=[True, False, True])
        expected = oracle([x[:, [0, 2]] for x in self.arrays], 0)
        self.assertAlmostEqual(result["flattened"]["correlation_explained_percent"], expected[0])
        self.assertEqual([x["unit_id"] for x in result["by_unit"]], ["a", "c"])

    def test_over_100_and_negative_variance_are_not_clipped(self):
        result = self.score(arrays=(self.a, self.b, self.a, self.b, self.a, self.b))
        self.assertGreater(result["flattened"]["correlation_explained_percent"], 100)
        bad_means = self.score(arrays=(*self.arrays[:4], self.a+100, self.b+100))
        self.assertLess(bad_means["flattened"]["variance_explained_percent"], 0)

    def test_expected_counts_do_not_replace_sampled_counts(self):
        result = self.score()
        changed = self.score(arrays=(*self.arrays[:4], self.a*0.0, self.b*0.0))
        self.assertEqual(result["flattened"]["correlation_explained_percent"], changed["flattened"]["correlation_explained_percent"])
        self.assertNotEqual(result["flattened"]["variance_explained_percent"], changed["flattened"]["variance_explained_percent"])

    def test_time_shift_and_unit_identity_mismatch_change_result(self):
        perfect = self.score(arrays=(self.a, self.b, self.a, self.b, self.a, self.b))
        for a, b in ((np.roll(self.a, 3, axis=0), np.roll(self.b, 3, axis=0)),
                     (self.a[:, ::-1], self.b[:, ::-1])):
            wrong = self.score(arrays=(self.a, self.b, a, b, a, b))
            self.assertLess(wrong["flattened"]["correlation_explained_percent"], perfect["flattened"]["correlation_explained_percent"])

    def test_undefined_metrics_are_explicit_not_zero(self):
        zeros = np.zeros_like(self.a)
        result = self.score(arrays=(zeros, zeros, zeros, zeros, zeros, zeros))
        self.assertIsNone(result["flattened"]["correlation_explained_percent"])
        self.assertIsNone(result["flattened"]["variance_explained_percent"])
        self.assertIn("undefined_trial_reliability", result["flattened"]["diagnostics"])
        json.dumps(result, allow_nan=False)

    def test_invalid_values_and_ambiguous_shapes_fail(self):
        for bad in (self.a.astype(float)+0.1, self.a.astype(float)*float("nan"),
                    self.a-20, self.a[:, :2], self.a.astype(complex)):
            with self.assertRaises(ValueError):
                self.score(arrays=(bad, *self.arrays[1:]))
        corrupt = self.a.astype(float)
        corrupt[:, 1] = np.nan
        with self.assertRaises(ValueError):
            self.score(arrays=(corrupt, *self.arrays[1:]), mask=[True, False, True])
        for mask in ([1, 0, 1], [False]*3, [True, False]):
            with self.assertRaises(ValueError):
                self.score(mask=mask)
        with self.assertRaises(ValueError):
            self.score(ddof=True)


class CompletePanelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        a = (np.arange(512)[None, :] % 8 + np.arange(6)[:, None]).astype(np.int16)
        arrays = (a, a+1, a, a+1, a+0.25, a+0.75)
        descriptors = {}
        for name, array in zip(scorer.ARRAY_NAMES, arrays):
            path = self.root / (name+".npy")
            np.save(path, array)
            descriptors[name] = {"path": path.name, "sha256": scorer.sha256_file(path)}
        self.manifest = {
            "schema": "icnet-source-equations-input/v1", "variance_ddof": 0,
            "preparation": {"source_mask_sha256": "1"*64, "alignment_protocol_sha256": "2"*64,
                            "prediction_freeze_sha256": "3"*64, "measurement_times_sha256": "4"*64,
                            "mask_origin": "source_broadband_noise_reliability",
                            "split": "original_four_sounds_held_out_from_training"},
            "animals": {str(animal): {"unit_ids": [f"column_{i}" for i in range(512)],
                                      "eligible_mask": [i < (500 if animal == 9 else 496) for i in range(512)]}
                        for animal in scorer.ANIMALS},
            "cases": [{"animal": animal, "sound": sound, "time_bins": 6,
                       "measurement_times_seconds": [1, 2], "arrays": copy.deepcopy(descriptors)}
                      for animal in scorer.ANIMALS for sound in scorer.SOUNDS],
        }

    def test_complete_generated_panel_retains_all_animals_units_and_sounds(self):
        result = scorer.score_panel(self.manifest, self.root)
        self.assertEqual(len(result["cases"]), 28)
        self.assertEqual(sum(len(c["by_unit"]) for c in result["cases"]), 4*3476)
        self.assertFalse(result["native_author_baseline_reproduced"])
        self.assertFalse(result["reproduction_evaluated"])
        self.assertFalse(result["improvement_evaluated"])
        self.assertFalse(result["paper_win_evaluated"])
        self.assertEqual(result["cases"][0]["measurement_times_seconds"], [1, 2])
        json.dumps(result, allow_nan=False)

    def test_incomplete_or_changed_panel_rejected(self):
        invalid = []
        m = copy.deepcopy(self.manifest); m["cases"].pop(); invalid.append(m)
        m = copy.deepcopy(self.manifest); m["cases"][0] = m["cases"][1]; invalid.append(m)
        m = copy.deepcopy(self.manifest); del m["animals"]["3"]; invalid.append(m)
        m = copy.deepcopy(self.manifest); m["animals"]["3"]["eligible_mask"][0] = False; invalid.append(m)
        m = copy.deepcopy(self.manifest); m["animals"]["3"]["unit_ids"][0] = "column_1"; invalid.append(m)
        m = copy.deepcopy(self.manifest); m["preparation"]["split"] = "trial1_calibration"; invalid.append(m)
        m = copy.deepcopy(self.manifest); m["preparation"]["mask_origin"] = "evaluation_reliability"; invalid.append(m)
        m = copy.deepcopy(self.manifest); m["cases"][0]["measurement_times_seconds"] = [1]; invalid.append(m)
        m = copy.deepcopy(self.manifest); del m["cases"][0]["arrays"]["sampled_trial2"]; invalid.append(m)
        for manifest in invalid:
            with self.assertRaises(ValueError):
                scorer.score_panel(manifest, self.root)

    def test_payload_integrity_and_path_escape_fail(self):
        case = self.manifest["cases"][0]
        case["arrays"]["recorded_trial1"]["sha256"] = "0"*64
        with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
            scorer.score_panel(self.manifest, self.root)
        case["arrays"]["recorded_trial1"]["path"] = "../outside.npy"
        with self.assertRaisesRegex(ValueError, "escapes"):
            scorer.score_panel(self.manifest, self.root)


if __name__ == "__main__":
    print(f"Generated fixtures only; NumPy {np.__version__}")
    unittest.main(verbosity=2)
