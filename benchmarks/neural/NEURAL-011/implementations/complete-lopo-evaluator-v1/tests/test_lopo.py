"""Generated complete-roster controls; no authentic EEG or clinical outcomes."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import numpy as np


path = Path(__file__).resolve().parents[1] / "siena_lopo.py"
spec = importlib.util.spec_from_file_location("siena_lopo_under_test", path)
sl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sl)
FIXTURE_WRITES = 0


def freeze(held, roster, threshold=0.5):
    artifact = {
        "schema_version": 1, "task_id": "NEURAL-011", "method": "timing_only_v1",
        "training_patients": [p for p in roster if p != held],
        "training_manifest_sha256": "0" * 64, "threshold": threshold,
        "channels": ["FP1"], "scoring_parameters": sl.native.SCORING_PARAMETERS,
        "parameters": {"bin_seconds": 60.0, "unobserved_bin_score": 0.0,
                       "rates": [0.0, 0.5, 0.0, 0.0],
                       "threshold_selection": {"rule": "generated training rule",
                                               "training_summary": {}}},
    }
    repin(artifact)
    return artifact


def repin(artifact):
    artifact["artifact_sha256"] = sl.native.digest({k: v for k, v in artifact.items()
                                                    if k != "artifact_sha256"})


def folds(paired=False):
    source = sl.native.inventory()
    roster = sorted({r["patient_id"] for r in source.values()})
    result = []
    for patient in roster:
        recordings = [dict(row, n_samples=200, sample_rate=1, channels=["FP1"],
                           reference_events=[[100, 120]])
                      for row in source.values() if row["patient_id"] == patient]
        manifest = dict(schema_version=1, task_id="NEURAL-011", role="test",
                        patients=[patient], recordings=recordings)
        predictions = {row["recording_id"]: np.zeros(200) for row in recordings}
        for vector in predictions.values():
            vector[100] = 1
        fold = dict(manifest=manifest, predictions=predictions, frozen=freeze(patient, roster))
        if paired:
            fold["comparator_predictions"] = {key: np.zeros(200) for key in predictions}
            fold["comparator_frozen"] = freeze(patient, roster)
        result.append(fold)
    return result


def write_text(path, content):
    global FIXTURE_WRITES
    path.write_text(content)
    FIXTURE_WRITES += len(content.encode())


class LopoTests(unittest.TestCase):
    def test_complete_roster_preserves_native_metrics_and_exact_occupancy(self):
        inputs = folds()
        result = sl.evaluate_folds(inputs)
        self.assertEqual((result["fold_count"], len(result["patients"]), len(result["recordings"])), (14, 14, 41))
        self.assertEqual(result["patient_macro_event_f1"], 1)
        self.assertEqual(result["patient_macro_sensitivity"], 1)
        self.assertEqual(result["patient_macro_false_alarms_per_24h"], 0)
        self.assertAlmostEqual(result["patient_macro_predicted_positive_time_fraction"], 1 / 200)
        self.assertEqual(result["observed_duration_seconds"], 41 * 200)
        self.assertEqual(result["predicted_positive_seconds"], 41)
        self.assertTrue(result["complete_declared_outer_coverage"])
        self.assertTrue(result["full_cohort_event_f1_defined"])
        self.assertEqual(result["scientific_qualification"], "unknown")
        self.assertFalse(result["source_authentication_established"])
        self.assertFalse(result["fitting_provenance_established"])
        for fold in inputs:
            native = sl.native.score_manifest(fold["manifest"], fold["predictions"], 0.5)
            patient = fold["manifest"]["patients"][0]
            for key, value in native["patients"][patient].items():
                self.assertEqual(result["patients"][patient][key], value)
        self.assertEqual(result["constant_controls"]["always_negative"]["patient_macro_predicted_positive_time_fraction"], 0)
        self.assertEqual(result["constant_controls"]["always_positive"]["patient_macro_predicted_positive_time_fraction"], 1)

    def test_missing_duplicate_or_multi_patient_fold_refused_before_scoring(self):
        inputs = folds()
        variants = [inputs[:-1], inputs + [inputs[0]], copy.deepcopy(inputs), copy.deepcopy(inputs)]
        variants[2][-1] = copy.deepcopy(variants[2][0])
        variants[3][0]["manifest"]["patients"].append("PN01")
        with mock.patch.object(sl.occupancy, "evaluate", side_effect=AssertionError("must not score")) as scorer:
            for variant in variants:
                with self.subTest(length=len(variant)), self.assertRaises(ValueError):
                    sl.evaluate_folds(variant)
            scorer.assert_not_called()

    def test_heterogeneous_patients_preserve_macro_and_both_time_denominators(self):
        inputs = folds()
        first = next(f for f in inputs if f["manifest"]["patients"] == ["PN00"])
        self.assertEqual(len(first["manifest"]["recordings"]), 5)
        for vector in first["predictions"].values():
            vector[:] = 0
        second = next(f for f in inputs if f["manifest"]["patients"] == ["PN01"])
        self.assertEqual(len(second["manifest"]["recordings"]), 1)
        row = second["manifest"]["recordings"][0]
        row.update(n_samples=7, sample_rate=3, reference_events=[])
        second["predictions"][row["recording_id"]] = np.ones(7)
        result = sl.evaluate_folds(inputs)
        self.assertAlmostEqual(result["patient_macro_event_f1"], 12 / 14)
        self.assertAlmostEqual(result["patient_macro_sensitivity"], 12 / 13)
        self.assertEqual(result["sensitivity_undefined_patients"], ["PN01"])
        self.assertAlmostEqual(result["patient_macro_false_alarms_per_24h"], 86400 / 2.3 / 14)
        self.assertAlmostEqual(result["pooled_false_alarms_per_24h"], 86400 / (40 * 200 + 2.3))
        self.assertAlmostEqual(result["duration_seconds"], 40 * 200 + 2.3)
        self.assertAlmostEqual(result["observed_duration_seconds"], 40 * 200 + 7 / 3)
        self.assertAlmostEqual(result["patient_macro_predicted_positive_time_fraction"], (1 + 12 / 200) / 14)
        self.assertAlmostEqual(result["pooled_predicted_positive_time_fraction"], (35 + 7 / 3) / (40 * 200 + 7 / 3))
        self.assertNotAlmostEqual(result["patient_macro_predicted_positive_time_fraction"],
                                  result["pooled_predicted_positive_time_fraction"])

    def test_every_recording_for_each_held_person_is_mandatory(self):
        inputs = folds()
        inputs[0]["manifest"]["recordings"].pop()
        with self.assertRaisesRegex(ValueError, "missing complete"):
            sl.evaluate_folds(inputs)

    def test_other_thirteen_training_patients_required(self):
        for kind in ("missing", "held_leak"):
            inputs = folds()
            artifact = inputs[0]["frozen"]
            artifact["training_patients"].pop()
            if kind == "held_leak":
                artifact["training_patients"].append(inputs[0]["manifest"]["patients"][0])
            repin(artifact)
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, "other13"):
                sl.evaluate_folds(inputs)

    def test_fixed_recipe_and_channels_match_across_folds(self):
        for kind in ("rule", "channels", "method", "incomplete"):
            inputs = folds()
            artifact = inputs[0]["frozen"]
            if kind == "rule":
                artifact["parameters"]["threshold_selection"]["rule"] = "different tuning procedure"
            elif kind == "channels":
                artifact["channels"] = ["FP2"]
                for row in inputs[0]["manifest"]["recordings"]:
                    row["channels"] = ["FP2"]
            elif kind == "method":
                artifact["method"] = "line_length_v1"
                artifact["parameters"] = {"window_seconds": 1.0, "scale_floor": 1e-12,
                    "signal_unit": "microvolts", "scales": [1.0],
                    "threshold_selection": {"rule": "generated training rule", "training_summary": {}}}
            else:
                artifact["parameters"] = {}
            repin(artifact)
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, "recipe"):
                sl.evaluate_folds(inputs)

    def test_fold_specific_fitted_values_and_thresholds_allowed(self):
        inputs = folds()
        for i, fold in enumerate(inputs):
            artifact = fold["frozen"]
            artifact["threshold"] = (i + 1) / 100
            artifact["parameters"]["rates"] = [i / 14]
            artifact["parameters"]["threshold_selection"]["training_summary"] = {"fixture": i}
            artifact["training_manifest_sha256"] = f"{i:064x}"
            repin(artifact)
        result = sl.evaluate_folds(inputs)
        self.assertEqual(result["patient_macro_event_f1"], 1)
        self.assertEqual(len({row["frozen_artifact_sha256"] for row in result["folds"]}), 14)

    def test_undefined_f1_retained_without_full_cohort_endpoint_claim(self):
        inputs = folds(paired=True)
        missing = inputs[0]
        patient = missing["manifest"]["patients"][0]
        for row in missing["manifest"]["recordings"]:
            row["reference_events"] = []
            missing["predictions"][row["recording_id"]][:] = 0
        result = sl.evaluate_folds(inputs)
        self.assertEqual(result["f1_undefined_patients"], [patient])
        self.assertEqual(len(result["f1_defined_patients"]), 13)
        self.assertFalse(result["full_cohort_event_f1_defined"])
        self.assertFalse(result["full_cohort_paired_event_f1_defined"])
        self.assertEqual(result["paired_comparison"]["excluded"], [patient])
        self.assertEqual(len(result["occupancy_patients"]), 14)
        self.assertEqual(result["paired_predicted_positive_time_fraction"]["excluded"], [])

    def test_paired_complete_support_and_training_compatibility_required(self):
        for kind in ("one_missing", "one_half", "hash", "training_order", "recipe"):
            inputs = folds(paired=True)
            fold = inputs[0]
            if kind == "one_missing":
                del fold["comparator_predictions"], fold["comparator_frozen"]
            elif kind == "one_half":
                del fold["comparator_frozen"]
            else:
                artifact = fold["comparator_frozen"]
                if kind == "hash":
                    artifact["training_manifest_sha256"] = "1" * 64
                elif kind == "training_order":
                    artifact["training_patients"].reverse()
                else:
                    artifact["parameters"]["threshold_selection"]["rule"] = "different procedure"
                repin(artifact)
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                sl.evaluate_folds(inputs)

    def test_pairing_has_same_complete_patients_and_original_f1_delta(self):
        result = sl.evaluate_folds(folds(paired=True))
        self.assertEqual(result["patient_macro_event_f1"], 1)
        self.assertEqual(result["comparator"]["patient_macro_event_f1"], 0)
        self.assertEqual(result["paired_comparison"]["difference"], 1)
        self.assertEqual(result["paired_comparison"]["percentile_95_interval"], [1, 1])
        self.assertEqual(len(result["paired_comparison"]["patients"]), 14)
        self.assertTrue(result["full_cohort_paired_event_f1_defined"])
        self.assertAlmostEqual(result["paired_predicted_positive_time_fraction"]["patient_macro_difference"], 1 / 200)

    def test_incomplete_vectors_and_nonfinite_predictions_still_refused(self):
        for kind in ("missing", "short", "nan"):
            inputs = folds()
            predictions = inputs[-1]["predictions"]
            key = next(iter(predictions))
            if kind == "missing":
                del predictions[key]
            elif kind == "short":
                predictions[key] = predictions[key][:-1]
            else:
                predictions[key][0] = np.nan
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                sl.evaluate_folds(inputs)

    def test_cli_resolves_input_paths_relative_to_study(self):
        global FIXTURE_WRITES
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            rows = []
            for i, fold in enumerate(folds()):
                row = {}
                for key, value in fold.items():
                    path = root / (f"{i}-{key}" + (".npz" if key == "predictions" else ".json"))
                    if key == "predictions":
                        np.savez(path, **value)
                        FIXTURE_WRITES += path.stat().st_size
                    else:
                        write_text(path, json.dumps(value))
                    row[key] = path.name
                rows.append(row)
            study = root / "study.json"
            write_text(study, json.dumps(dict(schema_version=1, task_id="NEURAL-011", folds=rows)))
            output = root / "report.json"
            self.assertEqual(sl.main([str(study), str(output)]), 0)
            FIXTURE_WRITES += output.stat().st_size
            report = json.loads(output.read_text())
            self.assertEqual(len(report["recordings"]), 41)
            self.assertEqual(report["protocol"], "prospective_complete_leave_one_patient_out_v1")
            self.assertEqual(report["scientific_qualification"], "unknown")
            json.dumps(report, allow_nan=False)


if __name__ == "__main__":
    try:
        unittest.main()
    finally:
        print(f"generated_fixture_bytes_written={FIXTURE_WRITES}")
