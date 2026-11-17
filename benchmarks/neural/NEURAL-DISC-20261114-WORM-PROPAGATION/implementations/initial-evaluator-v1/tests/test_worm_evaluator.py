"""Bounded generated engineering controls; no biological reference results."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("worm_evaluator", ROOT / "worm_evaluator.py")
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)


def fixture():
    cases = []
    for role, worm, target in [("train", "train-a", [0., 2., 4.]),
                               ("train", "train-b", [2., 4., 6.]),
                               ("development", "dev-a", [1., 3., 5.]),
                               ("held", "held-a", [1., 3., 5.]),
                               ("held", "held-b", [2., 4., 6.])]:
        cases.append({"case_id": worm + ":0:R", "worm_id": worm, "acquisition_id": worm + ":acq",
                      "trial_id": "trial-0", "source_id": "S", "receiver_id": "R", "condition": "WT",
                      "role": role, "quality_flags": ["generated_control_only"],
                      "stimulus_parameters": {"duration_s": .5, "power_mw": 1.2},
                      "stimulus_onset_acquisition_s": 100.,
                      "provenance": {"asset_id": "generated:" + worm, "asset_sha256": "0" * 64,
                                     "source_index": 0, "receiver_index": 1, "stimulus_index": 0},
                      "source": {"times_s": [-4., -2., -1., 0., 1., 2., 4.],
                                 "values": [0., 0., 0., 1., 2., 3., 4.]},
                      "receiver_pre": {"times_s": [-2., -1.], "values": [0., 0.]},
                      "target": {"times_s": [0., 1., 2.], "values": target}})
    return {"task_id": w.TASK_ID, "schema_version": 1, "release_id": w.RELEASE,
            "inventory_sha256": "a" * 64, "identity_audit_sha256": "b" * 64,
            "mask_policy_sha256": "c" * 64, "identity_authenticated": True,
            "mask_policy": "acquisition_missingness_only", "units": "generated-fluorescence-unit",
            "horizon_s": 30, "max_interpolation_gap_s": 2.,
            "expected_case_ids": [c["case_id"] for c in cases], "cases": cases}


def predictions(data, offset=0.):
    return {"units": data["units"], "cases": [{"case_id": c["case_id"],
            "times_s": c["target"]["times_s"],
            "values": [(y if y is not None else 0.) + offset for y in c["target"]["values"]]}
            for c in data["cases"] if c["role"] == "held"]}


class EvaluatorTests(unittest.TestCase):
    def test_independent_mse_area_and_variance(self):
        data = fixture()
        result = w.evaluate(data, predictions(data, 1.), draws=100)
        rows = result["case_rows"]
        self.assertEqual([r["mse"] for r in rows], [1., 1.])
        self.assertEqual([r["pair_mean_mse"] for r in rows], [0., 1.])
        self.assertEqual([r["paired_mse_difference"] for r in rows], [1., 0.])
        self.assertAlmostEqual(rows[0]["training_variance"], 11 / 3)
        self.assertAlmostEqual(rows[0]["normalized_mse"], 3 / 11)
        self.assertAlmostEqual(rows[1]["normalized_pair_mean_mse"], 3 / 11)
        self.assertAlmostEqual(rows[0]["normalized_paired_mse_difference"], 3 / 11)
        self.assertEqual(rows[0]["area_error"], 2.)
        self.assertEqual(rows[0]["correlation"], 1.)
        self.assertEqual(result["complete_roster_primary_mean_difference"], .5)
        self.assertEqual(rows[0]["target_tail_unobserved_s"], 28.)
        self.assertEqual(result["scientific_qualification"], "unknown")

    def test_independent_hierarchical_weighting(self):
        rows = [dict(worm_id="a", condition="WT", source_id="S", receiver_id=receiver,
                     valid_samples=10, mse=value)
                for receiver, value in [("r1", 0.), ("r1", 4.), ("r2", 16.)]]
        rows.append(dict(worm_id="b", condition="WT", source_id="S", receiver_id="r1",
                         valid_samples=2, mse=1.))
        self.assertEqual(w.aggregate(rows, "mse"), {"a": 9., "b": 1.})

    def test_missingness_no_interpolation_or_area_bridge(self):
        trace = {"times_s": [0., 1., 2.], "values": [0., None, 2.]}
        self.assertIsNone(w.interpolate(trace, .5, 10.))
        self.assertIsNone(w.interpolate(trace, 1.5, 10.))
        self.assertIsNone(w.interpolate(trace, -1., 10.))
        result = w.trace_metrics(trace, [1., 10., 3.], 10.)
        self.assertEqual(result["mse"], 1.)
        self.assertIsNone(result["area_error"])
        self.assertEqual(result["area_supported_duration_s"], 0.)

    def test_no_large_gap_bridge(self):
        trace = {"times_s": [0., 20.], "values": [0., 20.]}
        self.assertIsNone(w.interpolate(trace, 10., 2.))
        self.assertIsNone(w.trace_metrics(trace, [1., 21.], 2.)["area_error"])

    def test_original_irregular_time_area(self):
        result = w.trace_metrics({"times_s": [0., .25, 2.], "values": [0., 0., 0.]},
                                 [2., 2., 2.], 2.)
        self.assertEqual(result["area_error"], 4.)
        self.assertEqual(result["correlation_status"], "zero_target_variance")

    def test_worm_split_and_acquisition_alias_rejected(self):
        data = fixture()
        data["cases"][-1]["worm_id"] = data["cases"][0]["worm_id"]
        with self.assertRaisesRegex(ValueError, "worm crosses roles"):
            w.validate_dataset(data)
        data = fixture()
        data["cases"][-1]["acquisition_id"] = data["cases"][0]["acquisition_id"]
        with self.assertRaisesRegex(ValueError, "acquisition maps"):
            w.validate_dataset(data)

    def test_roster_cannot_drop_failure_case(self):
        data = fixture()
        data["cases"][-1]["quality_flags"] += ["failed_self_response", "weak_response"]
        result = w.evaluate(data, predictions(data), draws=100)
        self.assertEqual(result["coverage"]["held_cases"], 2)
        self.assertEqual(result["coverage"]["quality_flag_counts"]["failed_self_response"], 1)
        data["cases"].pop()
        with self.assertRaisesRegex(ValueError, "roster"):
            w.validate_dataset(data)

    def test_unsupported_pair_not_silently_dropped_or_filled(self):
        data = fixture()
        data["cases"][-1]["receiver_id"] = "UNSEEN"
        result = w.evaluate(data, predictions(data), draws=100)
        self.assertEqual(result["coverage"]["held_cases"], 2)
        self.assertIsNone(result["case_rows"][-1]["pair_mean_mse"])
        self.assertIsNone(result["complete_roster_primary_mean_difference"])
        self.assertFalse(result["coverage"]["all_held_worms_paired_supported"])
        self.assertIsNone(result["paired_worm_interval"]["ci95"])
        self.assertEqual(result["paired_worm_interval"]["status"], "incomplete_held_worm_support")

    def test_zero_training_variance_and_all_missing_targets_retained(self):
        data = fixture()
        for c in data["cases"]:
            if c["role"] == "train":
                c["target"]["values"] = [2., 2., 2.]
        data["cases"][-1]["target"]["values"] = [None, None, None]
        result = w.evaluate(data, predictions(data), draws=100)
        self.assertEqual(result["case_rows"][0]["training_variance"], 0.)
        self.assertIsNone(result["case_rows"][0]["normalized_mse"])
        self.assertEqual(result["coverage"]["held_cases_no_valid_target"], 1)
        self.assertIsNone(result["complete_roster_primary_mean_difference"])

    def test_prediction_validation_even_when_target_missing(self):
        data = fixture()
        data["cases"][-1]["target"]["values"][0] = None
        pred = predictions(data)
        pred["cases"][-1]["values"][0] = math.nan
        with self.assertRaisesRegex(ValueError, "finite"):
            w.evaluate(data, pred, draws=100)
        pred = predictions(data)
        pred["cases"][-1]["times_s"] = [0., 1., 2.00001]
        with self.assertRaisesRegex(ValueError, "grid"):
            w.evaluate(data, pred, draws=100)
        with self.assertRaisesRegex(ValueError, "complete held roster"):
            w.evaluate(data, {"units": data["units"], "cases": []}, draws=100)

    def test_public_packets_hide_all_response_and_arbitrary_evaluator_fields(self):
        data = fixture()
        data["secret"] = "SECRET"
        data["cases"][-1]["private_target_normalizer"] = "SECRET"
        data["cases"][-1]["quality_flags"].append("SECRET")
        held = w.public_packet(data, "held")
        self.assertNotIn("SECRET", json.dumps(held))
        self.assertNotIn("target", held["cases"][0])
        self.assertNotIn("quality_flags", held["cases"][0])
        self.assertNotIn("training_response", held["cases"][0])
        self.assertIn("training_response", w.public_packet(data, "train")["cases"][0])
        self.assertNotIn("training_response", w.public_packet(data, "development")["cases"][0])

    def test_target_zero_not_receiver_prehistory(self):
        data = fixture()
        data["cases"][-1]["receiver_pre"]["times_s"][-1] = 0.
        with self.assertRaisesRegex(ValueError, "time window"):
            w.validate_dataset(data)

    def test_nested_stimulus_target_leakage_rejected(self):
        data = fixture()
        data["cases"][-1]["stimulus_parameters"]["receiver_response"] = {"secret": [1, 2, 3]}
        with self.assertRaisesRegex(ValueError, "stimulus parameters"):
            w.public_packet(data, "held")
        data = fixture()
        data["cases"][-1]["stimulus_parameters"]["duration_s"] = {"target": [1, 2, 3]}
        with self.assertRaisesRegex(ValueError, "stimulus parameters"):
            w.public_packet(data, "held")

    def test_training_reference_and_kernel_never_read_held_targets(self):
        data = fixture()
        first = w.evaluate(data, predictions(data), draws=100)
        data["cases"][-1]["target"]["values"] = [100., 200., 300.]
        second = w.evaluate(data, predictions(data), draws=100)
        self.assertEqual(first["kernel_selection"], second["kernel_selection"])
        self.assertEqual(first["case_rows"][0], second["case_rows"][0])
        self.assertEqual(first["case_rows"][-1]["training_variance"], second["case_rows"][-1]["training_variance"])
        with self.assertRaisesRegex(ValueError, "training only"):
            w.PairMean(data["cases"], 2.)

    def test_convolution_numeric_ridge_solution(self):
        data = fixture()
        c = data["cases"][0]
        c["source"] = {"times_s": [-1., 0., 1.], "values": [0., 1., 2.]}
        c["target"] = {"times_s": [0., 1.], "values": [1., 2.]}
        kernel = w.Convolution([c], [0., 1.], 1., 2.)
        # X=[[.5,0],[1,.5]], normalized by sqrt(2); solve
        # [[1.625,.25],[.25,1.125]] beta=[1.25,.5].
        determinant = 1.625 * 1.125 - .25 ** 2
        expected = [(1.25 * 1.125 - .25 * .5) / determinant,
                    (1.625 * .5 - .25 * 1.25) / determinant]
        for actual, value in zip(kernel.weights[w.pair_key(c)], expected):
            self.assertAlmostEqual(actual, value)

    def test_paired_worm_bootstrap(self):
        result = w.paired_interval([-3., -3., -3.], seed=8, draws=100)
        self.assertEqual(result["ci95"], [-3., -3.])
        self.assertIsNone(w.paired_interval([-3.], draws=100)["ci95"])

    def test_whole_trace_reassignment_preserves_nulls_and_shared_stimulation(self):
        data = fixture()
        c = copy.deepcopy(data["cases"][-1])
        c["case_id"] += ":second"
        c["trial_id"] = "trial-1"
        c["stimulus_onset_acquisition_s"] = 200.
        c["source"]["values"] = [None, 3., 2., 1., None, 5., 4.]
        data["cases"].append(c)
        data["expected_case_ids"].append(c["case_id"])
        out, log = w.source_reassignment(data, 0)
        self.assertEqual(out["cases"][-2]["source"], data["cases"][-1]["source"])
        self.assertEqual(out["cases"][-1]["source"], data["cases"][-2]["source"])
        self.assertEqual(sum(a["status"] == "reassigned" for a in log["assignments"]), 2)
        self.assertEqual(data["cases"][-2]["source"]["values"][0], 0.)

    def test_physical_export_and_score_cli(self):
        data = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            dataset, pred = tmp / "data.json", tmp / "prediction.json"
            dataset.write_text(json.dumps(data))
            pred.write_text(json.dumps(predictions(data)))
            subprocess.run([sys.executable, str(ROOT / "worm_evaluator.py"), "export", str(dataset), str(tmp / "packets")], check=True)
            self.assertEqual((tmp / "packets/evaluator-only/protected.json").stat().st_mode & 0o777, 0o600)
            subprocess.run([sys.executable, str(ROOT / "worm_evaluator.py"), "score", str(dataset), str(pred), str(tmp / "score.json")], check=True)
            self.assertEqual(json.loads((tmp / "score.json").read_text())["coverage"]["held_worms"], 2)


if __name__ == "__main__":
    unittest.main()
