"""Changed-seam generated controls only; no authentic observations or fits."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import statistics
import tempfile
import unittest

import numpy as np

spec = importlib.util.spec_from_file_location(
    "icnet_lnp_comparison", Path(__file__).with_name("lnp_comparison.py"))
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


class PoissonComparisonTests(unittest.TestCase):
    def test_unbounded_poisson_support_zero_mean_and_invalid_inputs(self):
        rates = np.array([[0.0, 200.0], [0.0, 200.0], [0.0, 200.0]])
        expected, samples = comparison.poisson_trials(rates, trial_seeds=[13, 29])
        self.assertTrue(np.array_equal(expected, rates))
        for sample in samples:
            self.assertEqual(sample.dtype, np.dtype("int64"))
            self.assertTrue(np.all(sample[:, 0] == 0))
            self.assertTrue(np.all(sample[:, 1] > 127))
        self.assertFalse(np.array_equal(samples[0], samples[1]))
        again = comparison.poisson_trials(rates, trial_seeds=[13, 29])[1]
        self.assertTrue(all(np.array_equal(a, b) for a, b in zip(samples, again)))
        for bad in (rates - 1, rates * np.nan, np.ones(3), rates.astype(complex)):
            with self.assertRaises(ValueError):
                comparison.poisson_trials(bad, trial_seeds=[13, 29])
        for seeds in (None, [1], [True, 2], [-1, 2], [1, 2**63]):
            with self.assertRaises(ValueError):
                comparison.poisson_trials(rates, trial_seeds=seeds)

    def test_variance_uses_rate_expectation_and_preserves_unit_vector(self):
        a = np.array([[0, 8], [1, 9], [4, 8], [2, 11],
                      [5, 10], [3, 14], [6, 12], [2, 9]])
        b = a + np.array([[0], [1], [0], [2], [1], [0], [1], [0]])
        rates = a * 0.7 + 0.2
        reports = [comparison.compare_case(
            a, b, a, b, a, b, rates, eligible_mask=[True, True],
            unit_ids=["left", "right"], variance_ddof=0,
            lnp_trial_seeds=seeds) for seeds in ([3, 17], [31, 71])]
        for i, unit_id in enumerate(("left", "right")):
            x, y, rate = [list(map(float, z[:, i])) for z in (a, b, rates)]
            noise = statistics.pvariance([v-w for v, w in zip(x, y)]) / 2
            error = sum((v-r)**2 + (w-r)**2 for v, w, r in zip(x, y, rate)) / (2*len(x))
            denominator = (statistics.pvariance(x) + statistics.pvariance(y))/2 - noise
            expected = 100 * (1 - (error-noise)/denominator)
            for report in reports:
                row = report["fig4d_time_only_unit_vector"][i]
                self.assertEqual((row["unit_id"], row["column_zero_based"]), (unit_id, i))
                self.assertAlmostEqual(row["lnp"]["variance_explained_percent"], expected)
                self.assertAlmostEqual(row["icnet_minus_lnp_percentage_points"]["variance_explained_percent"],
                                 row["icnet"]["variance_explained_percent"] - expected)
            self.assertEqual(reports[0]["fig4d_time_only_unit_vector"][i]["lnp"]["variance_explained_percent"],
                             reports[1]["fig4d_time_only_unit_vector"][i]["lnp"]["variance_explained_percent"])
        self.assertNotAlmostEqual(
            reports[0]["fig4b_flattened_companions"]["lnp"]["variance_explained_percent"],
            statistics.mean(row["lnp"]["variance_explained_percent"]
                            for row in reports[0]["fig4d_time_only_unit_vector"]))

    def test_undefined_and_signed_values_retained_without_claim(self):
        a = np.array([[0, 0, 2], [1, 0, 1], [3, 0, 0], [2, 0, 1]])
        b = a + np.array([[0, 0, 0], [1, 0, 0], [0, 0, 0], [2, 0, 0]])
        report = comparison.compare_case(
            a, b, a, b, a, b, np.ones_like(a)*100,
            eligible_mask=[True, True, False], unit_ids=["signal", "constant", "excluded"],
            variance_ddof=0, lnp_trial_seeds=[4, 5])
        rows = report["fig4d_time_only_unit_vector"]
        self.assertEqual([row["unit_id"] for row in rows], ["signal", "constant"])
        self.assertGreater(rows[0]["icnet"]["correlation_explained_percent"], 100)
        self.assertLess(rows[0]["lnp"]["variance_explained_percent"], 0)
        self.assertIsNone(rows[1]["icnet_minus_lnp_percentage_points"]["correlation_explained_percent"])
        self.assertIn("undefined_trial_reliability", rows[1]["icnet"]["diagnostics"])
        self.assertEqual(report["qualification"], "paired_case_equation_component_only")
        json.dumps(report, allow_nan=False)


class PanelBindingTests(unittest.TestCase):
    def test_full_panel_preserves_vector_and_live_scorer_dependency(self):
        fixture_root = Path(os.environ["ICNET_CONTROL_FIXTURE_ROOT"])
        fixture_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=fixture_root) as directory:
            root = Path(directory)
            counts = (np.arange(512)[None, :] % 8 + np.array([[0], [2]])).astype(np.int16)
            descriptors = {}
            for name, array in (("counts", counts), ("expected", counts.astype(float)),
                                ("rates", counts.astype(float)+0.5)):
                path = root/(name+".npy")
                np.save(path, array)
                descriptors[name] = {"path": path.name,
                                     "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            scorer = comparison._scorer()
            arrays = {name: descriptors["expected" if name.startswith("expected_") else "counts"]
                      for name in scorer.ARRAY_NAMES}
            panel = {
                "schema": "icnet-source-equations-input/v1", "variance_ddof": 0,
                "preparation": {"source_mask_sha256": "1"*64, "alignment_protocol_sha256": "2"*64,
                                "prediction_freeze_sha256": "3"*64, "measurement_times_sha256": "4"*64,
                                "mask_origin": "source_broadband_noise_reliability",
                                "split": "original_four_sounds_held_out_from_training"},
                "animals": {str(a): {"unit_ids": [f"column_{i}" for i in range(512)],
                                      "eligible_mask": [i < (500 if a == 9 else 496) for i in range(512)]}
                            for a in scorer.ANIMALS},
                "cases": [{"animal": a, "sound": s, "time_bins": 2,
                           "measurement_times_seconds": [1, 2], "arrays": arrays}
                          for a in scorer.ANIMALS for s in scorer.SOUNDS],
            }
            manifest = {
                "schema": "icnet-fig4-lnp-comparison-input/v1", "icnet_panel": panel,
                "lnp": {"model_sha256_by_animal": {str(a): "a"*64 for a in scorer.ANIMALS},
                        "training_split_evidence_sha256": "b"*64, "sampling": comparison.SAMPLING,
                        "cases": [{"animal": a, "sound": s, "time_bins": 2,
                                   "rates": descriptors["rates"], "trial_seeds": [a, a+100]}
                                  for a in scorer.ANIMALS for s in scorer.SOUNDS]},
            }
            result = comparison.score_comparison_panel(manifest, root)
            self.assertEqual(len(result["cases"]), 28)
            self.assertEqual(sum(len(c["fig4d_time_only_unit_vector"]) for c in result["cases"]), 4*3476)
            self.assertFalse(result["universal_scalar_required"])
            for flag in ("model_provenance_authenticated", "historical_sampling_parity",
                         "native_author_baseline_reproduced", "reproduction_evaluated", "improvement_evaluated"):
                self.assertFalse(result[flag])
            self.assertEqual(result["endpoint_binding"]["primary_comparison"]["panel"], "Fig4d")
            self.assertEqual(result["endpoint_binding"]["companion"]["panel"], "Fig4b")
            grade = Path(__file__).parent.parent/"original-inputs-v1"/"grade.py"
            self.assertIn('SCORER_SHA256 = "'+comparison.SCORER_SHA256+'"', grade.read_text())
            for mutate in (
                lambda m: m["lnp"]["cases"].pop(),
                lambda m: m["lnp"].update(sampling="categorical_0_to_4"),
                lambda m: m["lnp"]["model_sha256_by_animal"].pop("3"),
                lambda m: m["lnp"]["cases"][0].update(animal=100),
            ):
                invalid = copy.deepcopy(manifest); mutate(invalid)
                with self.assertRaises(ValueError):
                    comparison.score_comparison_panel(invalid, root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
