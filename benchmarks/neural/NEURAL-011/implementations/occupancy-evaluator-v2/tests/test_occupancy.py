"""Generated software controls only; no authentic Siena samples or outcomes."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import siena_occupancy as so


def manifest(patients=("PN01",), n=200, fs=1, events=None):
    rows = [dict(row, n_samples=n, sample_rate=fs, channels=["FP1"],
                 reference_events=copy.deepcopy(events if events is not None else [[100, 120]]))
            for row in so.native.inventory().values() if row["patient_id"] in patients]
    return dict(schema_version=1, task_id="NEURAL-011", role="test", patients=list(patients), recordings=rows)


def predictions(m, value=0):
    return {row["recording_id"]: np.full(row["n_samples"], value, dtype=float) for row in m["recordings"]}


def generated_frozen(threshold=0.5):
    # A generated metadata fixture; no trained scientific model is represented.
    obj = dict(schema_version=1, task_id="NEURAL-011", method="timing_only_v1",
               training_patients=["PN07"], training_manifest_sha256="0" * 64,
               threshold=threshold, channels=["FP1"], parameters={},
               scoring_parameters=so.native.SCORING_PARAMETERS)
    obj["artifact_sha256"] = so.native.digest(obj)
    return obj


class OccupancyTests(unittest.TestCase):
    def assert_preserved(self, original, extended):
        if isinstance(original, dict):
            for key, value in original.items():
                self.assertIn(key, extended)
                self.assert_preserved(value, extended[key])
        elif isinstance(original, list):
            self.assertEqual(len(original), len(extended))
            for left, right in zip(original, extended):
                self.assert_preserved(left, right)
        else:
            self.assertEqual(original, extended)

    def test_same_perfect_event_score_distinct_time_burden(self):
        m = manifest()
        sparse, sustained = predictions(m), predictions(m, 1)
        next(iter(sparse.values()))[100] = 1
        brief = so.score_manifest(m, sparse, 0.5)
        long = so.score_manifest(m, sustained, 0.5)
        self.assertEqual(brief["patient_macro_event_f1"], 1)
        self.assertEqual(long["patient_macro_event_f1"], 1)
        self.assertEqual(brief["patient_macro_predicted_positive_time_fraction"], 1 / 200)
        self.assertEqual(long["patient_macro_predicted_positive_time_fraction"], 1)

    def test_occupancy_ignores_gap_fill_and_tolerance(self):
        m = manifest()
        p = predictions(m)
        vector = next(iter(p.values()))
        vector[[20, 100]] = 1
        result = so.score_manifest(m, p, 0.5)
        row = result["recordings"][0]
        self.assertEqual(row["processed_prediction_events"], [(20, 101)])
        self.assertEqual(row["predicted_positive_samples"], 2)
        self.assertEqual(row["predicted_positive_seconds"], 2)
        self.assertEqual(row["predicted_positive_time_fraction"], 0.01)

    def test_exact_support_not_rounded_native_denominator(self):
        m = manifest(n=7, fs=3, events=[])
        result = so.score_manifest(m, predictions(m, 1), 0.5)
        row = result["recordings"][0]
        self.assertEqual(row["duration_seconds"], 2.3)
        self.assertEqual(row["observed_duration_seconds"], 7 / 3)
        self.assertEqual(row["predicted_positive_time_fraction"], 1)
        self.assertEqual(result["pooled_predicted_positive_time_fraction"], 1)

    def test_duration_weighted_within_patient_then_equal_patient_macro(self):
        m = manifest(("PN00", "PN11"), events=[])
        pn00 = [r for r in m["recordings"] if r["patient_id"] == "PN00"]
        for row, duration, fs in zip(pn00, [10, 20, 30, 40, 50], [2, 3, 4, 5, 6]):
            row.update(n_samples=duration * fs, sample_rate=fs)
        pn11 = next(r for r in m["recordings"] if r["patient_id"] == "PN11")
        pn11.update(n_samples=100, sample_rate=2)
        p = predictions(m)
        p[pn00[0]["recording_id"]][:] = 1
        p[pn11["recording_id"]][:50] = 1
        result = so.score_manifest(m, p, 0.5)
        self.assertAlmostEqual(result["patients"]["PN00"]["predicted_positive_time_fraction"], 1 / 15)
        self.assertEqual(result["patients"]["PN11"]["predicted_positive_time_fraction"], 0.5)
        self.assertAlmostEqual(result["patient_macro_predicted_positive_time_fraction"], 17 / 60)
        self.assertAlmostEqual(result["pooled_predicted_positive_time_fraction"], 35 / 200)
        self.assertEqual(result["observed_duration_seconds"], 200)
        self.assertEqual(result["predicted_positive_seconds"], 35)

    def test_undefined_f1_does_not_exclude_background_patient(self):
        m = manifest(("PN01", "PN11"), events=[])
        p = predictions(m)
        p[m["recordings"][1]["recording_id"]][:] = 1
        result = so.score_manifest(m, p, 0.5)
        self.assertEqual(result["f1_undefined_patients"], ["PN01"])
        self.assertEqual(result["occupancy_patients"], ["PN01", "PN11"])
        self.assertEqual(result["occupancy_undefined_patients"], [])
        self.assertEqual(result["patient_macro_predicted_positive_time_fraction"], 0.5)

    def test_threshold_equality_and_recording_end_are_included(self):
        m = manifest(n=4, fs=2, events=[])
        p = {m["recordings"][0]["recording_id"]: np.array([0.5, 0.49, 0.1, 0.5])}
        row = so.score_manifest(m, p, 0.5)["recordings"][0]
        self.assertEqual(row["raw_prediction_events"], [(0, 0.5), (1.5, 2)])
        self.assertEqual(row["predicted_positive_seconds"], 1)
        self.assertEqual(row["predicted_positive_time_fraction"], 0.5)

    def test_large_integer_threshold_uses_native_float_normalization(self):
        m = manifest()
        p = {r["recording_id"]: np.full(r["n_samples"], 9007199254740992, dtype=np.uint64)
             for r in m["recordings"]}
        threshold = 9007199254740993
        for result in (so.score_manifest(m, p, threshold),
                       so.evaluate(m, p, generated_frozen(threshold))):
            with self.subTest(route="full_evaluate" if "constant_controls" in result else "score"):
                self.assertEqual(result["recordings"][0]["raw_prediction_events"], [(0, 200)])
                self.assertEqual(result["recordings"][0]["predicted_positive_samples"], 200)
                self.assertEqual(result["patient_macro_predicted_positive_time_fraction"], 1)

    def test_evaluation_retains_native_outputs_and_adds_constant_controls(self):
        m = manifest(("PN01", "PN11"))
        p, frozen = predictions(m), generated_frozen()
        before_m, before_p, before_frozen = copy.deepcopy(m), copy.deepcopy(p), copy.deepcopy(frozen)
        original = so.native.evaluate(m, p, frozen)
        result = so.evaluate(m, p, frozen)
        self.assert_preserved(original, result)
        for name, fraction in (("always_negative", 0), ("always_positive", 1)):
            control = result["constant_controls"][name]
            self.assertEqual(control["patient_macro_predicted_positive_time_fraction"], fraction)
            self.assertEqual(control["occupancy_patients"], result["occupancy_patients"])
            self.assertEqual(control["observed_duration_seconds"], result["observed_duration_seconds"])
        self.assertEqual(result["constant_controls"]["always_positive"]["patient_macro_event_f1"], 1)
        self.assertEqual(result["scientific_qualification"], "unknown")
        self.assertEqual(m, before_m)
        self.assertEqual(frozen, before_frozen)
        for rid in p:
            np.testing.assert_array_equal(p[rid], before_p[rid])

    def test_paired_occupancy_uses_all_patients_and_each_frozen_threshold(self):
        m = manifest(("PN01", "PN11"), events=[])
        p, q = predictions(m, 0.5), predictions(m, 0.5)
        first, second = generated_frozen(0.5), generated_frozen(0.6)
        result = so.evaluate(m, p, first, (q, second))
        self.assertEqual(result["paired_comparison"]["status"], "insufficient_independent_patients")
        self.assertEqual(result["paired_comparison"]["excluded"], ["PN01", "PN11"])
        paired = result["paired_predicted_positive_time_fraction"]
        self.assertEqual(paired["patients"], ["PN01", "PN11"])
        self.assertEqual(paired["excluded"], [])
        self.assertEqual(paired["patient_macro_difference"], 1)
        self.assertEqual(paired["candidate_minus_comparator_by_patient"], {"PN01": 1, "PN11": 1})

    def test_native_rejections_remain_enforced(self):
        m = manifest()
        rid = m["recordings"][0]["recording_id"]
        for p in ({}, {rid: np.zeros(199)}, {rid: np.full(200, np.nan)},
                  {rid: np.ones(200, dtype=bool)}, {rid: np.zeros(200), "extra": np.zeros(200)}):
            with self.subTest(prediction_keys=list(p)), self.assertRaises(ValueError):
                so.evaluate(m, p, generated_frozen())
        missing = manifest(("PN00",))
        missing["recordings"].pop()
        with self.assertRaisesRegex(ValueError, "missing complete"):
            so.constant_controls(missing)
        leaked = generated_frozen()
        leaked["training_patients"] = ["PN01"]
        leaked["artifact_sha256"] = so.native.digest({k: v for k, v in leaked.items() if k != "artifact_sha256"})
        with self.assertRaisesRegex(ValueError, "leakage"):
            so.evaluate(m, predictions(m), leaked)

    def test_cli_emits_companions_in_strict_json(self):
        m, frozen = manifest(), generated_frozen()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "manifest.json").write_text(json.dumps(m))
            (root / "frozen.json").write_text(json.dumps(frozen))
            np.savez(root / "predictions.npz", **predictions(m))
            args = [str(root / name) for name in ["manifest.json", "predictions.npz", "frozen.json", "report.json"]]
            self.assertEqual(so.main(args), 0)
            result = json.loads((root / "report.json").read_text())
            self.assertIn("constant_controls", result)
            self.assertEqual(result["patient_macro_predicted_positive_time_fraction"], 0)
            json.dumps(result, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
