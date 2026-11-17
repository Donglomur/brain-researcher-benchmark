"""Generated controls only: no Allen observations or source-native model runs."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

PACKAGE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("method018_evaluator", PACKAGE / "evaluator.py")
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + "\n")


def save_npz(root, name, **arrays):
    path = root / name
    np.savez(path, **arrays)
    return {"path": name, "sha256": e.file_sha256(path)}


def control_artifacts(root):
    """All ten identifiers, tiny independently generated counts; never real data."""
    recipe = {
        "inference_policy": e.INFERENCE_POLICY, "include_stimulus": True,
        "include_self_history": True, "use_self_coupling": False,
        "beta": 1.0, "latent_dimension": 2, "bin_width_seconds": 0.002,
        "history_padding_bins": 50, "model_capacity_sha256": "a" * 64,
        "training_recipe_sha256": "b" * 64, "preprocessing_sha256": "c" * 64,
        "split_policy": "operator_frozen_condition_stratified_code_route",
        "split_frozen_after_final_batch_size": True,
    }
    ref = {"schema_version": 1, "task_id": e.TASK_ID,
           "contract_sha256": e.CONTRACT_SHA256, "source_commit": e.SOURCE_COMMIT,
           "inventory_status": "operator_frozen_not_independently_native_validated",
           "recipe": recipe, "sessions": []}
    arm_sessions = {arm: [] for arm in e.ARMS}
    for index, sid in enumerate(e.SESSION_IDS):
        neurons = [f"synthetic-neuron-{n}" for n in range(1 + index % 3)]
        trials = [f"synthetic-trial-{n}" for n in range(10)]
        bins = [50, 51, 52]
        counts = np.full((3, len(neurons), 2), 2, dtype=np.int64)
        ref["sessions"].append({
            "session_id": sid, "neuron_ids": neurons,
            "eligible_trial_ids": trials, "train_trial_ids": trials[:7],
            "validation_trial_ids": trials[7:8], "test_trial_ids": trials[8:], "test_batches": [trials[8:]],
            "trial_conditions": {t: {"stimulus_name": "drifting_gratings", "stimulus_condition_id": "0"} for t in trials},
            "time_bin_indices": bins,
            "counts": save_npz(root, f"counts-{sid}.npz", counts=counts),
            "eligibility_receipt_sha256": "d" * 64,
        })
        for arm in e.ARMS:
            eta = np.full(counts.shape, 0.0 if arm == "history_only" else math.log(2))
            artifact = save_npz(root, f"{arm}-{sid}.npz", log_rate=eta,
                                posterior_mu=np.zeros((2, 2)), posterior_logvar=np.zeros((2, 2)))
            arm_sessions[arm].append({"session_id": sid, "neuron_ids": neurons,
                                      "test_trial_ids": trials[8:], "test_batches": [trials[8:]], "time_bin_indices": bins,
                                      "predictions": artifact})
    write_json(root / "reference.json", ref)
    sub = {"schema_version": 1, "task_id": e.TASK_ID,
           "reference_sha256": e.file_sha256(root / "reference.json"), "arms": {}}
    for arm in e.ARMS:
        sub["arms"][arm] = {"recipe": copy.deepcopy(recipe),
                            "include_coupling": arm == "interaction_enabled",
                            "checkpoint_sha256": ("e" if arm == "history_only" else "f") * 64,
                            "fit_training_partition_sha256": e.partition_digest(ref),
                            "sessions": arm_sessions[arm]}
    write_json(root / "submission.json", sub)
    return ref, sub


class AnalyticLossTests(unittest.TestCase):
    def test_independent_count_rate_factorial_kl_oracle(self):
        counts = np.array([[[0], [1]], [[2], [3]]])
        eta = np.full(counts.shape, math.log(2))
        result = e.loss_components(counts, eta, np.array([[1., 2.]]), np.zeros((1, 2)), beta=.2)
        self.assertAlmostEqual(result["poisson_nll_without_constant_mean"], 2 - 1.5 * math.log(2), places=13)
        self.assertAlmostEqual(result["poisson_nll_with_constant_mean"], 2 - 1.5 * math.log(2) + math.log(12)/4, places=13)
        self.assertAlmostEqual(result["scaled_latent_kl"], .625, places=13)
        self.assertAlmostEqual(result["source_variational_loss_mean"], 2 - 1.5 * math.log(2) + .125, places=13)

    def test_independent_three_count_oracle(self):
        y = np.array([0, 1, 2]).reshape(3, 1, 1)
        h = e.loss_components(y, np.zeros(y.shape), np.zeros((1, 1)), np.zeros((1, 1)))
        i = e.loss_components(y, np.full(y.shape, math.log(2)), np.zeros((1, 1)), np.zeros((1, 1)))
        self.assertAlmostEqual(h["poisson_nll_without_constant_mean"], 1)
        self.assertAlmostEqual(h["poisson_nll_without_constant_mean"] - i["poisson_nll_without_constant_mean"], math.log(2) - 1)

    def test_invalid_counts_and_overflow_fail_without_clipping(self):
        for bad in (-1, .5, float("nan"), float("inf"), 2**54, True):
            with self.subTest(bad=bad), self.assertRaises(e.EvaluationError):
                e.loss_components(np.full((1, 1, 1), bad), np.zeros((1, 1, 1)), np.zeros((1, 1)), np.zeros((1, 1)))
        for bad in (710, float("nan"), float("inf")):
            with self.subTest(eta=bad), self.assertRaises(e.EvaluationError):
                e.loss_components(np.zeros((1, 1, 1)), np.full((1, 1, 1), bad), np.zeros((1, 1)), np.zeros((1, 1)))
        with self.assertRaises(e.EvaluationError):
            e.loss_components(np.ones((1, 1, 1)), np.zeros((1, 1, 1)), np.ones((1, 1)), np.full((1, 1), 710))

    def test_full_tensor_shape_required(self):
        with self.assertRaises(e.EvaluationError):
            e.loss_components(np.ones((1, 1, 1)), np.zeros((1, 1, 2)), np.zeros((1, 1)), np.zeros((1, 1)))
        with self.assertRaises(e.EvaluationError):
            e.loss_components(np.ones((1, 1, 1)), np.zeros((1, 1, 1)), np.zeros((2, 1)), np.zeros((2, 1)))

    def test_sign_flip_exact_null_and_uniform_controls(self):
        self.assertEqual(e.exact_session_sign_flip([0] * 10), 1)
        self.assertEqual(e.exact_session_sign_flip([1] * 10), 2/1024)
        self.assertEqual(e.exact_session_sign_flip([1e-20] * 10), 2/1024)
        self.assertEqual(e.exact_session_sign_flip([1e308] * 10), 2/1024)
        self.assertEqual(e._weighted_mean([1e308] * 10), 1e308)
        self.assertEqual(e._weighted_mean([1e308, -1e308]), 0)
        self.assertEqual(e.exact_session_sign_flip([1, -1] * 5), 1)


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.ref, self.sub = control_artifacts(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def evaluate(self):
        return e.evaluate(self.root / "reference.json", self.root / "submission.json")

    def rewrite_submission(self):
        write_json(self.root / "submission.json", self.sub)

    def rewrite_both(self):
        write_json(self.root / "reference.json", self.ref)
        self.sub["reference_sha256"] = e.file_sha256(self.root / "reference.json")
        for arm in e.ARMS:
            self.sub["arms"][arm]["fit_training_partition_sha256"] = e.partition_digest(self.ref)
        self.rewrite_submission()

    def test_all_ten_sessions_complete_score_and_no_qualification(self):
        result = self.evaluate()
        self.assertEqual([r["session_id"] for r in result["sessions"]], list(e.SESSION_IDS))
        self.assertAlmostEqual(result["primary_value"], 2 * math.log(2) - 1)
        self.assertEqual(result["secondary_exact_session_sign_flip_two_sided_p"], 2/1024)
        self.assertFalse(result["scientifically_qualified"])
        self.assertFalse(result["full_contract_complete"])
        self.assertEqual(result["inference_policy"], e.INFERENCE_POLICY)

    def test_missing_extra_or_duplicate_session_rejected(self):
        sessions = self.sub["arms"]["history_only"]["sessions"]
        for bad in (sessions[:-1], sessions + [sessions[0]], sessions[:-1] + [sessions[0]]):
            self.sub["arms"]["history_only"]["sessions"] = bad
            self.rewrite_submission()
            with self.subTest(length=len(bad)), self.assertRaises(e.EvaluationError):
                self.evaluate()

    def test_neuron_trial_and_time_order_mismatch_rejected(self):
        row = self.sub["arms"]["history_only"]["sessions"][1]
        for key in ("neuron_ids", "test_trial_ids", "time_bin_indices"):
            original = row[key]
            row[key] = original[::-1]
            self.rewrite_submission()
            with self.subTest(key=key), self.assertRaises(e.EvaluationError):
                self.evaluate()
            row[key] = original

    def test_native_test_batch_regrouping_rejected(self):
        row = self.sub["arms"]["history_only"]["sessions"][0]
        row["test_batches"] = [[trial] for trial in row["test_trial_ids"]]
        self.rewrite_submission()
        with self.assertRaises(e.EvaluationError):
            self.evaluate()

    def test_huge_json_number_fails_with_explicit_error(self):
        self.ref["recipe"]["beta"] = 10**400
        self.rewrite_both()
        with self.assertRaises(e.EvaluationError):
            self.evaluate()

    def test_train_test_overlap_rejected(self):
        self.ref["sessions"][0]["train_trial_ids"][0] = self.ref["sessions"][0]["test_trial_ids"][0]
        self.rewrite_both()
        with self.assertRaises(e.EvaluationError):
            self.evaluate()

    def test_condition_stratification_not_just_total_sizes(self):
        row = self.ref["sessions"][0]
        for index, trial in enumerate(row["eligible_trial_ids"]):
            row["trial_conditions"][trial]["stimulus_condition_id"] = str(index % 2)
        self.rewrite_both()
        with self.assertRaises(e.EvaluationError):
            self.evaluate()

    def test_small_condition_and_special_fifteen_source_split(self):
        row = self.ref["sessions"][0]
        trials = [f"trial-{i}" for i in range(16)]
        row.update(eligible_trial_ids=trials, train_trial_ids=trials[:9],
                   validation_trial_ids=trials[9:11], test_trial_ids=trials[11:])
        row["test_batches"] = [trials[11:]]
        row["trial_conditions"] = {t: {"stimulus_name": "flashes", "stimulus_condition_id": str(i)}
                                   for i, t in enumerate(trials[:15])}
        row["trial_conditions"][trials[-1]] = {"stimulus_name": "spontaneous", "stimulus_condition_id": None}
        # Non-drifting conditions group by stimulus name only; n15->9/2/4, n1->0/0/1.
        e._validate_reference(self.ref, self.root)
        row["validation_trial_ids"] = trials[9:10]
        row["test_trial_ids"] = trials[10:]
        row["test_batches"] = [trials[10:]]
        with self.assertRaises(e.EvaluationError):
            e._validate_reference(self.ref, self.root)

    def test_mutated_reference_or_array_digest_rejected(self):
        path = self.root / "reference.json"
        path.write_text(path.read_text() + " ")
        with self.assertRaises(e.EvaluationError):
            self.evaluate()
        self.rewrite_both()
        path = self.root / self.ref["sessions"][0]["counts"]["path"]
        with path.open("ab") as handle:
            handle.write(b"tampering")
        with self.assertRaises(e.EvaluationError):
            self.evaluate()

    def test_unmatched_recipe_or_partition_rejected(self):
        row = self.sub["arms"]["history_only"]
        row["recipe"]["model_capacity_sha256"] = "0" * 64
        self.rewrite_submission()
        with self.assertRaises(e.EvaluationError):
            self.evaluate()
        row["recipe"] = copy.deepcopy(self.ref["recipe"])
        row["fit_training_partition_sha256"] = "0" * 64
        self.rewrite_submission()
        with self.assertRaises(e.EvaluationError):
            self.evaluate()

    def test_same_checkpoint_masking_not_separately_fitted_ablation(self):
        self.sub["arms"]["interaction_enabled"]["checkpoint_sha256"] = self.sub["arms"]["history_only"]["checkpoint_sha256"]
        self.rewrite_submission()
        with self.assertRaises(e.EvaluationError):
            self.evaluate()

    def test_claimed_blind_forecast_rejected(self):
        self.ref["recipe"]["inference_policy"] = "blind_causal_forecast"
        self.rewrite_both()
        with self.assertRaises(e.EvaluationError):
            self.evaluate()

    def test_object_arrays_and_truncated_arrays_rejected(self):
        record = self.sub["arms"]["history_only"]["sessions"][0]
        for eta in (np.array([object()], dtype=object), np.zeros((1, 1, 1))):
            record["predictions"] = save_npz(self.root, "bad.npz", log_rate=eta,
                                            posterior_mu=np.zeros((2, 2)), posterior_logvar=np.zeros((2, 2)))
            self.rewrite_submission()
            with self.assertRaises(e.EvaluationError):
                self.evaluate()

    def test_path_escape_and_symlink_escape_rejected(self):
        record = self.sub["arms"]["history_only"]["sessions"][0]["predictions"]
        original = record["path"]
        for path in ("../outside.npz", str(self.root / original)):
            record["path"] = path
            self.rewrite_submission()
            with self.assertRaises(e.EvaluationError):
                self.evaluate()
        with tempfile.TemporaryDirectory() as other:
            outside = Path(other) / "outside.npz"
            outside.write_bytes((self.root / original).read_bytes())
            (self.root / "link.npz").symlink_to(outside)
            record["path"] = "link.npz"
            self.rewrite_submission()
            with self.assertRaises(e.EvaluationError):
                self.evaluate()

    def test_zero_spikes_leave_bits_per_spike_undefined(self):
        row = self.ref["sessions"][0]
        row["counts"] = save_npz(self.root, "zero.npz", counts=np.zeros((3, 1, 2), dtype=int))
        self.rewrite_both()
        result = self.evaluate()
        self.assertIsNone(result["sessions"][0]["interaction_gain_bits_per_spike"])

    def test_nonuniform_session_weighting_is_explicit(self):
        for index, row in enumerate(self.sub["arms"]["history_only"]["sessions"]):
            n = len(row["neuron_ids"])
            rate = index + 1
            row["predictions"] = save_npz(self.root, f"weight-{index}.npz",
                log_rate=np.full((3, n, 2), math.log(rate)),
                posterior_mu=np.zeros((2, 2)), posterior_logvar=np.zeros((2, 2)))
        self.rewrite_submission()
        result = self.evaluate()["aggregate"]["history_only"]
        values = [i + 1 - 2*math.log(i + 1) for i in range(10)]
        self.assertAlmostEqual(result["equal_session_poisson_nll_without_constant"], sum(values)/10)
        weights = [1+i%3 for i in range(10)]
        self.assertAlmostEqual(result["pooled_observation_poisson_nll_without_constant"], sum(v*w for v,w in zip(values,weights))/sum(weights))
        self.assertNotAlmostEqual(result["equal_session_poisson_nll_without_constant"], result["pooled_observation_poisson_nll_without_constant"])

    def test_duplicate_json_keys_rejected(self):
        (self.root / "submission.json").write_text('{"task_id":"a","task_id":"b"}')
        with self.assertRaises(e.EvaluationError):
            self.evaluate()

    def test_cli_and_existing_output_protection(self):
        output = self.root / "report.json"
        command = [sys.executable, str(PACKAGE / "evaluator.py"), "--reference", str(self.root / "reference.json"),
                   "--submission", str(self.root / "submission.json"), "--output", str(output)]
        completed = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertFalse(json.loads(output.read_text())["scientifically_qualified"])
        again = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(again.returncode, 2)


if __name__ == "__main__":
    unittest.main()
