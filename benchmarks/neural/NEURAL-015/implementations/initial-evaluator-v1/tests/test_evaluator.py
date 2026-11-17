"""Generated controls only; no native data or fitted scientific baseline."""
import copy
import importlib.util
import itertools
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[1] / "evaluator.py"
spec = importlib.util.spec_from_file_location("boundary_evaluator", PATH)
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


def fixture():
    """Full 26-ID generated corpus, five joint person/movie connected folds."""
    p = {"profile": e.PROFILE, "sample_rate_hz": 2048, "grid_step_samples": 2,
         "tolerance_samples": 0, "feature_lags_samples": [-2, 0], "guard_samples": 2,
         "latency_shift_samples": 4, "probability_clip": 1e-12, "bootstrap_draws": 40,
         "bootstrap_seed": 7, "fitting_recipe_sha256": "a" * 64, "acoustic_visual_recipe_sha256": "b" * 64}
    # Fixed participant groups independently derived from the immutable movie map.
    person_groups = [{"1", "5"}, {"2"}, {"3", "4", "6", "7", "10"}, {"8"}, {"9"}]
    folds = []
    for i, people in enumerate(person_groups):
        test = sorted(rid for rid, v in e.IDENTITIES.items() if v["participant_id"] in people)
        train = sorted(set(e.IDENTITIES) - set(test))
        folds.append({"fold_id": f"joint-{i}", "train": train, "test": test, "unused": []})
    recs = [{"recording_id": rid, "sample_count": 20, "word_onset_samples": [4, 10],
             "neural_sha256": "c" * 64, "alignment_sha256": "d" * 64, "transcript_sha256": "e" * 64,
             "acoustic_visual_probabilities": [.5] * 8} for rid in sorted(e.IDENTITIES)]
    ref = {"task_id": e.TASK, "protocol": p, "folds": folds, "recordings": recs}
    fold_for = {rid: f["fold_id"] for f in folds for rid in f["test"]}
    # Grid [2,4,6,8,10,12,14,16], known target bins 1 and 4.
    predictions = [{"recording_id": r["recording_id"], "fold_id": fold_for[r["recording_id"]],
                    "neural": [.1, .9, .1, .1, .9, .1, .1, .1]} for r in recs]
    sub = {"task_id": e.TASK, "query_sha256": e.digest(e.public_query(ref)), "predictions": predictions}
    return ref, sub


class MetricControls(unittest.TestCase):
    def test_independent_tie_reference_and_permutation(self):
        y, s = [1, 0, 1, 0], [.8, .8, .4, .1]
        for permutation in itertools.permutations(range(4)):
            self.assertAlmostEqual(e.average_precision([y[i] for i in permutation], [s[i] for i in permutation]), 7 / 12)

    def test_constant_null_is_prevalence(self):
        result = e.metrics([1, 0, 0, 0], [.6] * 4, 1e-12)
        self.assertEqual(result["average_precision"], .25)
        self.assertTrue(result["constant_output"])

    def test_incremental_loss_sign_and_exact_value(self):
        p = fixture()[0]["protocol"]
        result = e.compare([1, 0], [.8, .2], [.5, .5], p)
        self.assertAlmostEqual(result["incremental_log_loss_nats"], math.log(1.6))
        inverse = e.compare([1, 0], [.5, .5], [.8, .2], p)
        self.assertAlmostEqual(inverse["incremental_log_loss_nats"], -math.log(1.6))

    def test_macro_is_not_pooled_or_session_average(self):
        p = fixture()[0]["protocol"]
        first = e.compare([1, 0], [.9, .1], [.5] * 2, p)
        second = e.compare([1, 1, 0, 0], [.1, .2, .8, .9], [.5] * 4, p)
        self.assertAlmostEqual(e.summarize([first, second], p)["participant_macro"]["neural_average_precision"], 17 / 24)
        self.assertAlmostEqual(e.average_precision([1, 0, 1, 1, 0, 0], [.9, .1, .1, .2, .8, .9]), .5)

    def test_undefined_ap_preserved_not_dropped(self):
        p = fixture()[0]["protocol"]
        rows = [e.compare([0, 0], [.1, .2], [.2, .3], p), e.compare([1, 0], [.9, .1], [.5, .5], p)]
        out = e.summarize(rows, p)
        self.assertIsNone(out["participant_macro"]["neural_average_precision"])
        self.assertIsNotNone(out["participant_macro"]["incremental_log_loss_nats"])

    def test_clipping_is_explicit_and_counted(self):
        result = e.metrics([1, 0], [0, 1], 1e-6)
        self.assertEqual(result["clipped_probabilities"], 2)
        self.assertAlmostEqual(result["log_loss_nats"], -math.log(1e-6), places=8)
        tiny = e.metrics([1, 0], [0, 1], 1e-20)
        self.assertEqual(tiny["clipped_probabilities"], 2)
        self.assertAlmostEqual(tiny["log_loss_nats"], -math.log(1e-20))

    def test_balanced_diagnostic_has_half_prevalence_null(self):
        self.assertAlmostEqual(e.metrics([1, 0, 0, 0], [.4] * 4, 1e-12, balanced=True)["average_precision"], .5)


class CohortControls(unittest.TestCase):
    def test_full_path_population_macro_and_shift(self):
        ref, sub = fixture()
        out = e.evaluate(ref, sub)
        self.assertEqual(out["population"], {"participants": 10, "recordings": 26, "unique_movies": 21})
        self.assertEqual(out["primary_uniform_grid"]["participant_macro"]["neural_average_precision"], 1)
        self.assertEqual(out["primary_uniform_grid"]["participant_macro"]["control_average_precision"], .25)
        self.assertAlmostEqual(out["primary_uniform_grid"]["participant_macro"]["incremental_log_loss_nats"], math.log(1.8))
        self.assertTrue(all(r["n_latency_control_bins"] == 6 for r in out["recordings"]))
        # Positive shift uses earlier predictions; at remaining bins target has one
        # positive and shifted high scores are two negatives: AP = 1/6.
        self.assertAlmostEqual(out["latency_shift_common_interior_diagnostic"]["participant_macro"]["control_average_precision"], 1 / 6)
        self.assertFalse(out["admitted"])

    def test_target_free_allowlist(self):
        ref, _ = fixture()
        q = e.public_query(ref)
        self.assertEqual(set(q), {"task_id", "profile", "protocol_sha256", "recordings"})
        self.assertEqual(set(q["recordings"][0]), {"recording_id", "fold_id", "grid_start_sample", "grid_stop_sample_exclusive", "grid_step_samples", "n_grid_points"})
        ref["recordings"][0]["word_onset_samples"] = [6, 12]
        self.assertEqual(e.public_query(ref), q)

    def test_submission_rejects_missing_duplicate_unknown_ids(self):
        for mutation in ("missing", "duplicate", "unknown"):
            ref, sub = fixture()
            if mutation == "missing":
                sub["predictions"].pop()
            elif mutation == "duplicate":
                sub["predictions"].append(sub["predictions"][0])
            else:
                sub["predictions"][0]["recording_id"] = "unknown"
            with self.assertRaises(e.ContractError):
                e.evaluate(ref, sub)

    def test_prediction_validation(self):
        for bad in (float("nan"), float("inf"), -.01, 1.01, True, "0.9"):
            ref, sub = fixture()
            sub["predictions"][0]["neural"][0] = bad
            with self.assertRaises(e.ContractError):
                e.evaluate(ref, sub)
        ref, sub = fixture()
        sub["predictions"][0]["neural"].pop()
        with self.assertRaises(e.ContractError):
            e.evaluate(ref, sub)

    def test_movie_and_person_leakage_rejected(self):
        for train_rid in ("sub_1_trial000", "sub_5_trial000"):
            ref, _ = fixture()
            fold = ref["folds"][0]
            fold["test"].remove(train_rid)
            fold["train"].append(train_rid)
            with self.assertRaisesRegex(e.ContractError, "leakage"):
                e.validate_reference(ref)

    def test_reference_and_test_coverage_cannot_be_reduced(self):
        ref, _ = fixture()
        ref["recordings"].pop()
        with self.assertRaises(e.ContractError):
            e.validate_reference(ref)
        ref, _ = fixture()
        fold = ref["folds"][0]
        fold["unused"].append(fold["test"].pop())
        with self.assertRaises(e.ContractError):
            e.validate_reference(ref)

    def test_guard_shift_and_query_binding(self):
        for key, bad in (("guard_samples", 1), ("latency_shift_samples", 3), ("latency_shift_samples", 2)):
            ref, _ = fixture()
            ref["protocol"][key] = bad
            with self.assertRaises(e.ContractError):
                e.validate_reference(ref)
        ref, sub = fixture()
        sub["query_sha256"] = "0" * 64
        with self.assertRaises(e.ContractError):
            e.evaluate(ref, sub)

    def test_no_label_bearing_unknown_fields(self):
        ref, _ = fixture()
        ref["recordings"][0]["transcript"] = "secret"
        with self.assertRaises(e.ContractError):
            e.public_query(ref)

    def test_entrant_cannot_supply_control_or_future_context(self):
        ref, sub = fixture()
        sub["predictions"][0]["acoustic_visual"] = [0] * 8
        with self.assertRaises(e.ContractError):
            e.evaluate(ref, sub)
        ref["protocol"]["feature_lags_samples"] = [0, 1]
        with self.assertRaises(e.ContractError):
            e.validate_reference(ref)

    def test_sign_reversed_shift_has_no_wrap(self):
        ref, sub = fixture()
        ref["protocol"]["latency_shift_samples"] = -4
        with self.assertRaises(e.ContractError):
            e.evaluate(ref, sub)
        sub["query_sha256"] = e.digest(e.public_query(ref))
        out = e.evaluate(ref, sub)
        self.assertTrue(all(r["n_latency_control_bins"] == 6 for r in out["recordings"]))
        self.assertAlmostEqual(out["latency_shift_common_interior_diagnostic"]["participant_macro"]["control_average_precision"], 1 / 3)


class AlignmentControls(unittest.TestCase):
    def setUp(self):
        self.triggers = [{"movie_time_seconds": 0, "neural_sample_index": 100}, {"movie_time_seconds": 1, "neural_sample_index": 2148}]

    def test_nearest_trigger_rounding_and_endpoints(self):
        out = e.align_onsets([0, .25, .5, 1], self.triggers, 0)
        self.assertEqual(out["word_onset_samples"], [100, 612, 1124, 2148])
        self.assertFalse(out["native_alignment_validated"])

    def test_clock_failures_and_no_extrapolation(self):
        for times in ([-.001], [1.001], [float("nan")], [1, 0], [.0001, .00009]):
            with self.assertRaises(e.ContractError):
                e.align_onsets(times, self.triggers, 0)
        self.triggers[1]["neural_sample_index"] += 2
        with self.assertRaises(e.ContractError):
            e.align_onsets([.5], self.triggers, 1)

    def test_pause_clock_must_be_segmented_before_alignment(self):
        paused = self.triggers + [{"movie_time_seconds": 1, "neural_sample_index": 4196}]
        with self.assertRaises(e.ContractError):
            e.align_onsets([.5], paused, 0)

    def test_inclusive_tolerance_union_and_no_event_matching(self):
        self.assertEqual(e.onset_labels([0, 2, 4, 6, 8], [3, 3, 5], 1), [0, 1, 1, 1, 0])

    def test_json_duplicate_keys_and_nonfinite_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "bad.json"
            for value in ('{"a":1,"a":2}', '{"a":NaN}'):
                path.write_text(value)
                with self.assertRaises(e.ContractError):
                    e.load_json(path)

    def test_cli_roundtrip_and_nonzero_rejection(self):
        ref, sub = fixture()
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "reference.json").write_text(json.dumps(ref))
            (d / "submission.json").write_text(json.dumps(sub))
            cmd = [sys.executable, str(PATH), "score", str(d / "reference.json"), "--submission", str(d / "submission.json"), "--output", str(d / "result.json")]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads((d / "result.json").read_text())["population"]["recordings"], 26)
            sub["predictions"].pop()
            (d / "submission.json").write_text(json.dumps(sub))
            self.assertEqual(subprocess.run(cmd, capture_output=True).returncode, 2)


if __name__ == "__main__":
    unittest.main()
