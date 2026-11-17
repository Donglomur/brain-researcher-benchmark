"""Generated numerical and adversarial controls; no native animal data."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / "scorer.py"
spec = importlib.util.spec_from_file_location("neural048_frozen_comparator", MODULE)
scorer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scorer)


def fixture():
    reference = {
        "task_id": "NEURAL-048", "policy": copy.deepcopy(scorer.legacy.POLICY),
        "source_manifest_sha256": "a" * 64, "behavior_history_sha256": "b" * 64,
        "population_worm_ids": ["fit", "A", "B"], "evaluation_worm_ids": ["A", "B"],
        "folds": [{"id": "f", "train_worm_ids": ["fit"],
                   "validation_worm_ids": [], "test_worm_ids": ["A", "B"]}],
        "episode_inventory": [], "observations": [],
    }
    behavior, neural = [], []
    for worm, labels, bp, np in [("A", [1], [.8], [.9]),
                                  ("B", [1, 0, 0], [.5, .5, .5], [.5, .25, .25])]:
        ids = []
        for index, y in enumerate(labels):
            oid = f"{worm}-{index}"
            ids.append(oid)
            reference["observations"].append({
                "id": oid, "worm_id": worm, "session_id": "s", "episode_id": "e",
                "fold_id": "f", "cutoff_ns": 10 + index, "target_start_ns": 20 + index,
                "target_end_ns": 21 + index, "dorsal": y})
            behavior.append({"id": oid, "behavior": bp[index]})
            neural.append({"id": oid, "neural_history": np[index],
                           "shifted_neural_history": bp[index]})
        reference["episode_inventory"].append({"worm_id": worm, "session_id": "s",
                                                "episode_id": "e", "observation_ids": ids})
    receipt = {"split_sha256": scorer.digest(reference["folds"]),
               "behavior_history_sha256": "b" * 64, "frozen_recipe_sha256": "c" * 64,
               "cpu_seconds": .1, "peak_memory_bytes": 1000}
    comparator = scorer.freeze_behavior(reference, behavior, receipt, "d" * 64)
    pin = scorer.digest(comparator)
    candidate = {
        "schema": scorer.CANDIDATE_SCHEMA, "task_id": "NEURAL-048",
        "reference_sha256": scorer.digest(reference),
        "policy_sha256": scorer.digest(scorer.legacy.POLICY),
        "comparator_sha256": pin,
        "arm_receipts": {arm: copy.deepcopy(receipt) for arm in scorer.NEURAL_ARMS},
        "predictions": neural}
    return reference, comparator, candidate, pin


def run(reference, comparator, candidate, pin):
    return scorer.score(reference, comparator, candidate, expected_comparator_sha256=pin)


class FrozenComparatorTests(unittest.TestCase):
    def test_unequal_worm_sizes_have_independent_loss_and_interval_oracles(self):
        report = run(*fixture())
        a, b = math.log(9 / 8), (2 / 3) * math.log(3 / 2)
        self.assertAlmostEqual(report["primary"]["mean_nats_per_observation"], (a + b) / 2)
        self.assertAlmostEqual(report["primary"]["interval_95"][0], a + .075 * (b - a) / 2)
        self.assertAlmostEqual(report["primary"]["interval_95"][1], b - .075 * (b - a) / 2)
        self.assertAlmostEqual(report["absolute_equal_worm_log_loss_nats"]["behavior"],
                               (-math.log(.8) - math.log(.5)) / 2)
        self.assertAlmostEqual(report["absolute_equal_worm_log_loss_nats"]["neural_history"],
                               (-math.log(.9) + (-math.log(.5) - 2 * math.log(.75)) / 3) / 2)
        self.assertNotAlmostEqual(report["primary"]["mean_nats_per_observation"], (a + 3 * b) / 4)
        self.assertEqual(report["contrasts"]["behavior_minus_shifted"]["mean_nats_per_observation"], 0)

    def test_bad_submitted_behavior_cannot_inflate_fixed_contrast(self):
        reference, baseline, candidate, pin = fixture()
        expected = run(reference, baseline, candidate, pin)["primary"]
        candidate["predictions"][0]["behavior"] = .00001
        with self.assertRaisesRegex(scorer.ContractError, "exact fields"):
            run(reference, baseline, candidate, pin)
        del candidate["predictions"][0]["behavior"]
        self.assertEqual(run(reference, baseline, candidate, pin)["primary"], expected)

    def test_changed_baseline_even_with_candidate_rebound_fails_operator_pin(self):
        reference, baseline, candidate, pin = fixture()
        baseline["predictions"][0]["behavior"] = .00001
        candidate["comparator_sha256"] = scorer.digest(baseline)
        with self.assertRaisesRegex(scorer.ContractError, "operator comparator pin"):
            run(reference, baseline, candidate, pin)

    def test_baseline_provenance_and_receipt_are_inside_external_pin(self):
        for field in ("execution_manifest_sha256", "receipt"):
            reference, baseline, candidate, pin = fixture()
            if field == "receipt":
                baseline[field]["frozen_recipe_sha256"] = "e" * 64
            else:
                baseline[field] = "e" * 64
            with self.subTest(field=field), self.assertRaisesRegex(scorer.ContractError, "operator comparator pin"):
                run(reference, baseline, candidate, pin)

    def test_explicit_operator_pin_is_required(self):
        reference, baseline, candidate, _ = fixture()
        with self.assertRaises(TypeError):
            scorer.score(reference, baseline, candidate)

    def test_complete_matched_ids_required_in_both_sources(self):
        for source in ("comparator", "candidate"):
            for mutation in ("missing", "duplicate", "unknown", "label"):
                reference, baseline, candidate, pin = fixture()
                rows = (baseline if source == "comparator" else candidate)["predictions"]
                if mutation == "missing":
                    rows.pop()
                elif mutation == "duplicate":
                    rows.append(copy.deepcopy(rows[0]))
                elif mutation == "unknown":
                    rows[0]["id"] = "unscored"
                else:
                    rows[0]["dorsal"] = 1
                if source == "comparator":
                    pin = scorer.digest(baseline)
                    candidate["comparator_sha256"] = pin
                with self.subTest(source=source, mutation=mutation), self.assertRaises(scorer.ContractError):
                    run(reference, baseline, candidate, pin)

    def test_behavior_freeze_rejects_invalid_probabilities(self):
        for value in (0, 1, -1, True, "0.5", float("nan"), float("inf")):
            reference, baseline, _, _ = fixture()
            baseline["predictions"][0]["behavior"] = value
            with self.subTest(value=value), self.assertRaises(scorer.ContractError):
                scorer.freeze_behavior(reference, baseline["predictions"], baseline["receipt"], "d" * 64)

    def test_both_candidate_arms_reject_invalid_probabilities(self):
        for arm in scorer.NEURAL_ARMS:
            for value in (0, 1, -1, True, "0.5", float("nan"), float("inf")):
                reference, baseline, candidate, pin = fixture()
                candidate["predictions"][0][arm] = value
                with self.subTest(arm=arm, value=value), self.assertRaises(scorer.ContractError):
                    run(reference, baseline, candidate, pin)

    def test_null_and_negative_neural_contrasts_are_valid(self):
        reference, baseline, candidate, pin = fixture()
        fixed = {row["id"]: row["behavior"] for row in baseline["predictions"]}
        for row in candidate["predictions"]:
            row["neural_history"] = fixed[row["id"]]
        self.assertEqual(run(reference, baseline, candidate, pin)["primary"]["interval_95"], [0, 0])
        labels = {row["id"]: row["dorsal"] for row in reference["observations"]}
        for row in candidate["predictions"]:
            row["neural_history"] = .1 if labels[row["id"]] else .9
        self.assertLess(run(reference, baseline, candidate, pin)["primary"]["interval_95"][1], 0)

    def test_candidate_row_order_does_not_change_any_loss(self):
        reference, baseline, candidate, pin = fixture()
        original = run(reference, baseline, candidate, pin)
        candidate["predictions"].reverse()
        actual = run(reference, baseline, candidate, pin)
        for key in ("primary", "contrasts", "worms", "episodes", "absolute_equal_worm_log_loss_nats"):
            self.assertEqual(original[key], actual[key])

    def test_reference_and_recipe_bindings_cannot_be_replaced(self):
        for change in ("reference", "policy", "comparator", "split", "history", "behavior_receipt"):
            reference, baseline, candidate, pin = fixture()
            if change in ("reference", "policy", "comparator"):
                candidate[change + "_sha256"] = "f" * 64
            elif change == "behavior_receipt":
                candidate["arm_receipts"]["behavior"] = copy.deepcopy(baseline["receipt"])
            else:
                key = "split_sha256" if change == "split" else "behavior_history_sha256"
                candidate["arm_receipts"]["neural_history"][key] = "f" * 64
            with self.subTest(change=change), self.assertRaises(scorer.ContractError):
                run(reference, baseline, candidate, pin)

    def test_inputs_and_frozen_outputs_do_not_alias(self):
        inputs = fixture()
        before = copy.deepcopy(inputs)
        report = run(*inputs)
        self.assertEqual(inputs, before)
        report["resource_receipts"]["behavior"]["cpu_seconds"] = 99
        self.assertEqual(inputs, before)
        reference, baseline, _, _ = inputs
        receipt = copy.deepcopy(baseline["receipt"])
        frozen = scorer.freeze_behavior(reference, baseline["predictions"], receipt, "d" * 64)
        receipt["cpu_seconds"] = 88
        self.assertEqual(frozen["receipt"]["cpu_seconds"], .1)

    def test_original_scientific_limits_remain_explicit(self):
        report = run(*fixture())
        self.assertFalse(report["admission"]["research_qualified"])
        self.assertFalse(report["admission"]["runnable_native"])
        self.assertIn("competence of the frozen behavior decoder", report["comparison_scope"]["not_established"])

    def test_cli_runs_real_scoring_and_rejects_pin_mismatch(self):
        reference, baseline, candidate, pin = fixture()
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            for name, value in (("reference", reference), ("baseline", baseline), ("candidate", candidate)):
                (folder / name).write_text(json.dumps(value))
            command = [sys.executable, str(MODULE), str(folder / "reference"), str(folder / "baseline"),
                       str(folder / "candidate"), "--expected-comparator-sha256", pin,
                       "--output", str(folder / "report")]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads((folder / "report").read_text())
            self.assertEqual(report["primary"], run(reference, baseline, candidate, pin)["primary"])
            command[6] = "e" * 64
            command[-1] = str(folder / "rejected")
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("operator comparator pin mismatch", result.stderr)
            self.assertFalse((folder / "rejected").exists())

    def test_cli_strict_json_rejects_duplicate_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.json"
            path.write_text('{"schema": "one", "schema": "two"}')
            with self.assertRaises(scorer.ContractError):
                scorer.legacy._load(path)


if __name__ == "__main__":
    unittest.main()
