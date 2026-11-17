"""Independent algebraic references and adversarial complete-grid controls."""
import copy
import math
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import evaluator as ev
from example_control import make_control


class Mathematics(unittest.TestCase):
    def test_pooled_r2_not_fold_average(self):
        self.assertAlmostEqual(ev.pooled_r2([0, .1, .9, 1], [0, 0, .9, .9]), 40 / 41)
        self.assertAlmostEqual(ev.pooled_r2([0, 1, 2, 3], [0, 0, 2, 4]), .6)
        with self.assertRaises(ev.EvaluationError):
            ev.pooled_r2([.5, .5], [.5, .5])

    def test_pseudo_run_means_ties_and_plus_one(self):
        result = ev.session_statistics([0, 1], [[.6, .6], [.4, .4], [.5, .5]])
        self.assertEqual(result["score"], .5)
        self.assertEqual(result["median_null"], .5)
        self.assertEqual(result["p_value"], .75)
        self.assertEqual(ev.session_statistics([.2, .2], [[x, x] for x in [.1, .2, .2, .3]])["p_value"], .8)

    def test_fisher_and_bh_independent_values(self):
        self.assertAlmostEqual(ev.fisher_combined([.2, .5]), .1 * (1 + math.log(10)))
        self.assertEqual(ev.fisher_combined([1, 1]), 1)
        self.assertAlmostEqual(ev.fisher_combined([.1, .2]), .09824046010856292)
        for actual, expected in zip(ev.benjamini_hochberg([.04, .001, .02, .9]), [.0533333333333, .004, .04, .9]):
            self.assertAlmostEqual(actual, expected)

    def test_region_difference_of_medians_and_coverage(self):
        rows = [{"subject": f"m{i}", "eid": f"s{i}", "region": "VISp", "score": score,
                 "median_null": null, "p_value": p, "n_units": 10, "n_trials": 250}
                for i, (score, null, p) in enumerate(zip([0, .1, .9], [0, .8, .8], [.2, .5, .9]))]
        result = ev.region_statistics(rows)[0]
        self.assertAlmostEqual(result["valuesminusnull_median"], -.7)
        self.assertAlmostEqual(result["combined_p"], .567634197218831)
        self.assertIsNone(result["values_median_significant"])
        rows[1]["n_trials"] = 249
        rows[2]["n_units"] = 4
        result = ev.region_statistics(rows)[0]
        self.assertEqual(result["status"], "insufficient_sessions")
        self.assertEqual(len(result["excluded_sessions"]), 2)


class NativeAdapter(unittest.TestCase):
    def setUp(self):
        target = [[i % 2 * .6 + .2] for i in range(100)]
        tests = [[i for i in range(100) if i % 50 == f] for f in range(50)]
        self.fit = {"target": target, "predictions_test": target, "scores_test_full": 1,
                    "idxes_test": tests, "idxes_train": [[i for i in range(100) if i not in t] for t in tests],
                    "n_folds": 5, "pseudo_id": -1, "run_id": 0}

    def test_uses_actual_partitions_not_misleading_scalar(self):
        target, run = ev.export_native_run(self.fit)
        self.assertEqual(len(target), 100)
        self.assertEqual(set(run["test_fold"]), set(range(50)))

    def test_rejects_leakage_and_score_mismatch(self):
        self.fit["idxes_train"][0].append(0)
        with self.assertRaisesRegex(ev.EvaluationError, "complement"):
            ev.export_native_run(self.fit)
        self.fit["scores_test_full"] = .8
        with self.assertRaisesRegex(ev.EvaluationError, "reported score"):
            ev.export_native_run(self.fit)

    def test_full_native_adapter_and_variable_mask_rejection(self):
        class NativeInt:
            def __init__(self, value):
                self.value = value

            def item(self):
                return self.value

        ids = [f"t{i}" for i in range(100)]
        mapping = {str(p): ids for p in [-1, *range(1, 201)]}
        native = {"subject": "mouse", "eid": "session", "region": ["VISp"], "N_units": NativeInt(10),
                  "fit": [{**self.fit, "pseudo_id": NativeInt(p), "run_id": NativeInt(r)}
                          for p in [-1, *range(1, 201)] for r in range(10)]}
        cell = ev.export_native_ephys(native, mapping, input_objects_sha256="1" * 64,
                                      target_generator_sha256="2" * 64)
        self.assertEqual(len(cell["runs"]), 2010)
        self.assertIs(type(cell["n_units"]), int)
        self.assertEqual(len(ev.digest(cell)), 64)
        with self.assertRaises(ev.EvaluationError):
            ev.native_integer(NativeInt(True), "N_units")
        with self.assertRaises(ev.EvaluationError):
            ev.native_integer(NativeInt(1.5), "N_units")
        mapping["1"] = list(reversed(ids))
        with self.assertRaisesRegex(ev.EvaluationError, "varying"):
            ev.export_native_ephys(native, mapping, input_objects_sha256="1" * 64,
                                   target_generator_sha256="2" * 64)


class CompleteGrid(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest, cls.payload = make_control(50)

    def resign(self, manifest, payload):
        manifest["prediction_payload_sha256"] = ev.digest(payload)

    def test_complete_native_shape_is_not_scientific_qualification(self):
        result = ev.evaluate(self.manifest, self.payload)
        self.assertEqual(result["sessions"][0]["p_value"], 1 / 201)
        self.assertAlmostEqual(result["movement_comparisons"][0]["neural_minus_motor_r2"], .25)
        self.assertFalse(result["scientific_qualification"])
        self.assertEqual(result["neural_regions"][0]["status"], "insufficient_sessions")

    def test_missing_run_or_null_is_rejected(self):
        payload, manifest = copy.deepcopy(self.payload), copy.deepcopy(self.manifest)
        payload["cells"][0]["runs"].pop()
        self.resign(manifest, payload)
        with self.assertRaisesRegex(ev.EvaluationError, "incomplete"):
            ev.evaluate(manifest, payload)

    def test_missing_cell_and_exposed_subject(self):
        payload, manifest = copy.deepcopy(self.payload), copy.deepcopy(self.manifest)
        payload["cells"].pop()
        self.resign(manifest, payload)
        with self.assertRaisesRegex(ev.EvaluationError, "population"):
            ev.evaluate(manifest, payload)
        manifest = copy.deepcopy(self.manifest)
        manifest["excluded_exposed_subjects"] = ["generated-mouse"]
        with self.assertRaisesRegex(ev.EvaluationError, "exposed"):
            ev.evaluate(manifest, self.payload)

    def test_invalid_protocol_and_payload_pin(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["protocol"]["model"] = "oracle"
        with self.assertRaisesRegex(ev.EvaluationError, "protocol"):
            ev.evaluate(manifest, self.payload)
        manifest = copy.deepcopy(self.manifest)
        manifest["prediction_payload_sha256"] = "0" * 64
        with self.assertRaisesRegex(ev.EvaluationError, "digest"):
            ev.evaluate(manifest, self.payload)

    def test_duplicate_run_and_missing_fold(self):
        payload, manifest = copy.deepcopy(self.payload), copy.deepcopy(self.manifest)
        payload["cells"][0]["runs"][1] = payload["cells"][0]["runs"][0]
        self.resign(manifest, payload)
        with self.assertRaisesRegex(ev.EvaluationError, "duplicate"):
            ev.evaluate(manifest, payload)
        with self.assertRaisesRegex(ev.EvaluationError, "50 balanced"):
            ev.check_folds([0] * 50, 50)

    def test_malformed_objects_duplicate_keys_and_nonfinite_json(self):
        with self.assertRaisesRegex(ev.EvaluationError, "objects"):
            ev.evaluate([], {})
        with self.assertRaisesRegex(ev.EvaluationError, "object"):
            ev.cell_key(None)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            path.write_text('{"subject":"first", "subject":"second"}')
            with self.assertRaisesRegex(ev.EvaluationError, "duplicate JSON"):
                ev.read_json(path)
            path.write_text('{"target": NaN}')
            with self.assertRaisesRegex(ev.EvaluationError, "nonfinite JSON"):
                ev.read_json(path)

    def test_motor_trial_reordering_rejected_even_when_repinned(self):
        payload, manifest = copy.deepcopy(self.payload), copy.deepcopy(self.manifest)
        # Replace (rather than mutate) the shared generated ID list.
        payload["cells"][1]["trial_ids"] = list(reversed(payload["cells"][1]["trial_ids"]))
        manifest["expected_cells"][1]["trial_ids"] = payload["cells"][1]["trial_ids"]
        self.resign(manifest, payload)
        with self.assertRaisesRegex(ev.EvaluationError, "histories"):
            ev.evaluate(manifest, payload)


if __name__ == "__main__":
    unittest.main()
