"""Generated comparisons only; no authentic observations, model fitting or scores."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

MODULE_PATH = Path(__file__).with_name("candidate_comparison.py")
spec = importlib.util.spec_from_file_location("icnet_candidate_comparison", MODULE_PATH)
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


def manifest():
    scorer = comparison._scorer()
    arrays = {name: {"path": "counts.npy", "sha256": "a"*64}
              for name in scorer.ARRAY_NAMES}
    panel = {
        "schema": "icnet-source-equations-input/v1", "variance_ddof": 0,
        "preparation": {
            "source_mask_sha256": "1"*64, "alignment_protocol_sha256": "2"*64,
            "prediction_freeze_sha256": "3"*64, "measurement_times_sha256": "4"*64,
            "mask_origin": "source_broadband_noise_reliability",
            "split": "original_four_sounds_held_out_from_training"},
        "animals": {str(a): {"unit_ids": [f"column_{i}" for i in range(512)],
                              "eligible_mask": [i < (500 if a == 9 else 496)
                                                for i in range(512)]}
                    for a in scorer.ANIMALS},
        "cases": [{"animal": a, "sound": s, "time_bins": 4,
                   "measurement_times_seconds": [1.0, 2.0], "arrays": copy.deepcopy(arrays)}
                  for a in scorer.ANIMALS for s in scorer.SOUNDS]}
    model = {"panel": panel, "provenance": {
        "model_sha256": "5"*64, "prediction_protocol_sha256": "6"*64,
        "stochastic_policy": "generated deterministic count fixture; no model run"}}
    return {"schema": "icnet-candidate-comparison-input/v1",
            "baseline": copy.deepcopy(model), "candidate": copy.deepcopy(model)}


class MatchedSupportTests(unittest.TestCase):
    def reject_before_array_access(self, value):
        scorer = comparison._scorer()
        with patch.object(scorer, "score_panel", side_effect=AssertionError("array access")) as mocked:
            with patch.object(comparison, "_scorer", return_value=scorer):
                with self.assertRaises(ValueError):
                    comparison.compare_panel(value, "/nonexistent-generated-root")
                mocked.assert_not_called()

    def test_recorded_trials_must_match_even_in_last_sound(self):
        for trial in ("recorded_trial1", "recorded_trial2"):
            value = manifest()
            value["candidate"]["panel"]["cases"][-1]["arrays"][trial]["sha256"] = "b"*64
            self.reject_before_array_access(value)

    def test_masks_and_ordered_original_unit_identities_must_match(self):
        for field in ("eligible_mask", "unit_ids"):
            value = manifest()
            row = value["candidate"]["panel"]["animals"]["3"]
            row[field][0], row[field][-1] = row[field][-1], row[field][0]
            self.reject_before_array_access(value)

    def test_original_panel_and_temporal_support_required(self):
        mutations = (
            lambda panel: panel["cases"].pop(),
            lambda panel: panel["cases"].__setitem__(-1, copy.deepcopy(panel["cases"][0])),
            lambda panel: panel["cases"][-1].update(animal=True),
            lambda panel: panel["cases"][-1].update(time_bins=3),
            lambda panel: panel["cases"][-1].update(measurement_times_seconds=[1, 3]),
            lambda panel: panel["cases"][-1].update(measurement_times_seconds=[1, float("nan")]),
        )
        for mutate in mutations:
            value = manifest(); mutate(value["candidate"]["panel"])
            self.reject_before_array_access(value)

    def test_shared_preparation_and_variance_convention(self):
        for field in comparison.SHARED_PREPARATION:
            value = manifest()
            value["candidate"]["panel"]["preparation"][field] = "f"*64
            self.reject_before_array_access(value)
        value = manifest(); value["candidate"]["panel"]["variance_ddof"] = 1
        self.reject_before_array_access(value)

    def test_different_prediction_freezes_and_independent_policies_allowed(self):
        value = manifest()
        value["candidate"]["panel"]["preparation"]["prediction_freeze_sha256"] = "7"*64
        value["candidate"]["provenance"]["model_sha256"] = "8"*64
        value["candidate"]["provenance"]["stochastic_policy"] = "different declared sampling schedule"
        value["candidate"]["panel"]["cases"].reverse()
        panels = comparison._matched_panels(value, comparison._scorer())
        self.assertEqual(set(panels), {"baseline", "candidate"})
        # Equal freezes are also valid for an identity control.
        comparison._matched_panels(manifest(), comparison._scorer())
        value["candidate"]["provenance"]["stochastic_policy"] = "  "
        self.reject_before_array_access(value)


class NumericalComparisonTests(unittest.TestCase):
    def test_complete_vector_signed_difference_nulls_and_byte_authentication(self):
        parent = Path(os.environ["ICNET_CONTROL_FIXTURE_ROOT"])
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as directory:
            root = Path(directory)
            counts = (np.arange(512)[None, :] % 8 + np.array([[0], [1], [3], [2]])).astype(np.int16)
            counts[:, 0] = 0
            expected = counts.astype(np.float64)
            worse = expected + 1
            descriptors = {}
            for name, array in (("counts", counts), ("expected", expected), ("worse", worse)):
                path = root/(name+".npy"); np.save(path, array)
                descriptors[name] = {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            value = manifest()
            for role in comparison.ROLES:
                for case in value[role]["panel"]["cases"]:
                    case["arrays"] = {
                        name: descriptors[("worse" if role == "candidate" else "expected")
                                          if name.startswith("expected_") else "counts"]
                        for name in comparison._scorer().ARRAY_NAMES}
            report = comparison.compare_panel(value, root)
            self.assertEqual(len(report["cases"]), 28)
            self.assertEqual(sum(len(case["fig4d_time_only_unit_vector"]) for case in report["cases"]), 4*3476)
            for case in report["cases"]:
                unit0, unit1 = case["fig4d_time_only_unit_vector"][:2]
                self.assertIsNone(unit0["candidate_minus_baseline_percentage_points"]["variance_explained_percent"])
                self.assertIn("zero_explainable_variance", unit0["candidate"]["diagnostics"])
                delta = unit1["candidate_minus_baseline_percentage_points"]
                self.assertAlmostEqual(delta["correlation_explained_percent"], 0)
                # Population variance of [0,1,3,2] is1.25; adding1 givesMSE1.
                self.assertAlmostEqual(delta["variance_explained_percent"], -80)
                flat = case["fig4b_flattened_companion"]
                self.assertAlmostEqual(flat["candidate_minus_baseline_percentage_points"]["variance_explained_percent"],
                                       flat["candidate"]["variance_explained_percent"] - flat["baseline"]["variance_explained_percent"])
            for flag in ("model_provenance_authenticated", "native_author_baseline_reproduced",
                         "reproduction_evaluated", "improvement_evaluated", "paper_win_evaluated"):
                self.assertFalse(report[flag])
            self.assertIn("ICNet", report["reference_role"])
            self.assertEqual(report["models"]["candidate"]["provenance"], value["candidate"]["provenance"])
            # A declared shared hash cannot conceal changed array bytes.
            with (root/"counts.npy").open("ab") as handle:
                handle.write(b"corrupt")
            with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
                comparison.compare_panel(value, root)

    def test_identity_difference_and_undefined_values(self):
        same = dict(zip(comparison.METRICS, (121.5, -35)))
        self.assertEqual(comparison._difference(same, same), dict.fromkeys(comparison.METRICS, 0))
        missing = dict.fromkeys(comparison.METRICS)
        self.assertEqual(comparison._difference(missing, same), missing)

    def test_cli_rejects_duplicate_fields_before_output(self):
        parent = Path(os.environ["ICNET_CONTROL_FIXTURE_ROOT"])
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as directory:
            root = Path(directory)
            source = root/"manifest.json"; output = root/"output.json"
            source.write_text('{"schema":"first","schema":"second"}')
            result = subprocess.run([sys.executable, "-I", "-B", str(MODULE_PATH),
                                     "--manifest", str(source), "--input-root", str(root),
                                     "--output", str(output)], capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("duplicate JSON field", result.stderr)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
