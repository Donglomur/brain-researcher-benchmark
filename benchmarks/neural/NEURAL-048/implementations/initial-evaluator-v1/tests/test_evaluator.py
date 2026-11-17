"""Generated engineering controls, never authentic scientific benchmark results."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / "evaluator.py"
spec = importlib.util.spec_from_file_location("neural048_initial", MODULE)
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)


def fixture():
    # Different episode counts make row pooling disagree with equal-worm mean.
    reference = {
        "task_id": ev.TASK_ID, "policy": copy.deepcopy(ev.POLICY),
        "source_manifest_sha256": "a" * 64, "behavior_history_sha256": "b" * 64,
        "population_worm_ids": ["train", "A", "B"], "evaluation_worm_ids": ["A", "B"],
        "folds": [{"id": "f0", "train_worm_ids": ["train"],
                   "validation_worm_ids": [], "test_worm_ids": ["A", "B"]}],
        "episode_inventory": [], "observations": [],
    }
    predictions = []
    for worm, labels, behavior, neural in [
            ("A", [1, 0], [.5, .5], [.8, .2]),
            ("B", [1, 1, 0, 0], [.8, .8, .2, .2], [.5, .5, .5, .5])]:
        ids = []
        for i, label in enumerate(labels):
            oid = f"{worm}-{i}"
            ids.append(oid)
            reference["observations"].append({
                "id": oid, "worm_id": worm, "session_id": "session", "episode_id": "episode",
                "fold_id": "f0", "dorsal": label, "cutoff_ns": 10 + i,
                "target_start_ns": 20 + i, "target_end_ns": 21 + i,
            })
            predictions.append({"id": oid, "behavior": behavior[i],
                                "neural_history": neural[i], "shifted_neural_history": behavior[i]})
        reference["episode_inventory"].append({"worm_id": worm, "session_id": "session",
                                                "episode_id": "episode", "observation_ids": ids})
    submission = {"task_id": ev.TASK_ID, "reference_sha256": ev.digest(reference),
                  "policy_sha256": ev.digest(ev.POLICY), "predictions": predictions,
                  "arm_receipts": {arm: {"split_sha256": ev.digest(reference["folds"]),
                                        "behavior_history_sha256": "b" * 64,
                                        "frozen_recipe_sha256": "c" * 64,
                                        "cpu_seconds": .001, "peak_memory_bytes": 1024}
                                   for arm in ev.ARMS}}
    return reference, submission


def rebind(reference, submission):
    submission["reference_sha256"] = ev.digest(reference)
    for receipt in submission["arm_receipts"].values():
        receipt["split_sha256"] = ev.digest(reference["folds"])


class ScoreTests(unittest.TestCase):
    def test_independently_derived_worm_oracle_and_exhaustive_ci(self):
        reference, submission = fixture()
        report = ev.score(reference, submission)
        d = math.log(1.6)
        self.assertAlmostEqual(report["worms"][0]["behavior_minus_neural"], d)
        self.assertAlmostEqual(report["worms"][1]["behavior_minus_neural"], -d)
        self.assertAlmostEqual(report["primary"]["mean_nats_per_observation"], 0)
        self.assertAlmostEqual(report["primary"]["interval_95"][0], -.4347533570523054)
        self.assertAlmostEqual(report["primary"]["interval_95"][1], .4347533570523054)
        self.assertEqual(report["primary"]["resamples"], 4)
        pooled_wrong = -d / 3
        self.assertGreater(abs(pooled_wrong - report["primary"]["mean_nats_per_observation"]), .15)
        self.assertFalse(report["admission"]["research_qualified"])

    def test_row_order_and_class_complement_invariance(self):
        reference, submission = fixture()
        expected = ev.score(reference, submission)["primary"]
        submission["predictions"].reverse()
        self.assertEqual(ev.score(reference, submission)["primary"], expected)
        for row in reference["observations"]:
            row["dorsal"] = 1 - row["dorsal"]
        for row in submission["predictions"]:
            for arm in ev.ARMS:
                row[arm] = 1 - row[arm]
        rebind(reference, submission)
        actual = ev.score(reference, submission)["primary"]
        self.assertAlmostEqual(actual["mean_nats_per_observation"], expected["mean_nats_per_observation"])

    def test_identical_arms_is_null_and_constants_are_diagnosed(self):
        reference, submission = fixture()
        for row in submission["predictions"]:
            for arm in ev.ARMS:
                row[arm] = .5
        report = ev.score(reference, submission)
        self.assertEqual(report["primary"]["interval_95"], [0, 0])
        self.assertEqual(report["constant_probability_arms"], list(ev.ARMS))
        self.assertAlmostEqual(report["worms"][0]["log_loss_nats"]["behavior"], math.log(2))

    def test_swapping_arms_reverses_sign(self):
        reference, submission = fixture()
        labels = {row["id"]: row["dorsal"] for row in reference["observations"]}
        for row in submission["predictions"]:
            row["neural_history"] = .9 if labels[row["id"]] else .1
        original = ev.score(reference, submission)["primary"]
        for row in submission["predictions"]:
            row["behavior"], row["neural_history"] = row["neural_history"], row["behavior"]
        swapped = ev.score(reference, submission)["primary"]
        self.assertAlmostEqual(swapped["mean_nats_per_observation"], -original["mean_nats_per_observation"])
        self.assertAlmostEqual(swapped["interval_95"][0], -original["interval_95"][1])

    def test_single_worm_has_no_population_interval(self):
        result = ev.paired_interval([.2])
        self.assertIsNone(result["interval_95"])
        self.assertEqual(result["method"], "single_worm_descriptive_only")

    def test_large_sample_rng_is_local_reproducible(self):
        import random
        state = random.getstate()
        one = ev.paired_interval([-.2, -.1, 0, .1, .2, .3])
        self.assertEqual(random.getstate(), state)
        self.assertEqual(one, ev.paired_interval([-.2, -.1, 0, .1, .2, .3]))
        self.assertEqual(one["resamples"], 10000)

    def test_invalid_probabilities_rejected_without_clipping(self):
        for value in (0, 1, -.1, 1.1, float("nan"), float("inf"), True, "0.5"):
            with self.subTest(value=value):
                reference, submission = fixture()
                submission["predictions"][0]["neural_history"] = value
                with self.assertRaises(ev.ContractError):
                    ev.score(reference, submission)

    def test_missing_extra_duplicate_and_label_bearing_rows_rejected(self):
        for mutation in ("missing", "extra", "duplicate", "label"):
            reference, submission = fixture()
            if mutation == "missing":
                submission["predictions"].pop()
            elif mutation == "extra":
                submission["predictions"].append({"id": "unknown", **{arm: .5 for arm in ev.ARMS}})
            elif mutation == "duplicate":
                submission["predictions"].append(copy.deepcopy(submission["predictions"][0]))
            else:
                submission["predictions"][0]["dorsal"] = 1
            with self.subTest(mutation=mutation), self.assertRaises(ev.ContractError):
                ev.score(reference, submission)

    def test_worm_split_leakage_rejected(self):
        reference, submission = fixture()
        reference["folds"][0]["train_worm_ids"].append("A")
        rebind(reference, submission)
        with self.assertRaisesRegex(ev.ContractError, "whole-worm"):
            ev.score(reference, submission)

    def test_repeated_test_worm_rejected(self):
        reference, submission = fixture()
        repeat = copy.deepcopy(reference["folds"][0])
        repeat["id"] = "f1"
        reference["folds"].append(repeat)
        rebind(reference, submission)
        with self.assertRaisesRegex(ev.ContractError, "more than once"):
            ev.score(reference, submission)

    def test_complete_episode_missingness_rejected(self):
        reference, submission = fixture()
        reference["observations"].pop()
        rebind(reference, submission)
        with self.assertRaisesRegex(ev.ContractError, "coverage"):
            ev.score(reference, submission)

    def test_duplicate_physical_observation_rejected(self):
        reference, submission = fixture()
        reference["observations"][1]["cutoff_ns"] = reference["observations"][0]["cutoff_ns"]
        rebind(reference, submission)
        with self.assertRaisesRegex(ev.ContractError, "physical"):
            ev.score(reference, submission)

    def test_episode_alias_cannot_hide_duplicate_physical_observation(self):
        reference, submission = fixture()
        duplicate = copy.deepcopy(reference["observations"][0])
        duplicate.update(id="aliased", episode_id="alias_episode")
        reference["observations"].append(duplicate)
        reference["episode_inventory"].append({"worm_id": "A", "session_id": "session",
                                                "episode_id": "alias_episode", "observation_ids": ["aliased"]})
        submission["predictions"].append({"id": "aliased", **{arm: .5 for arm in ev.ARMS}})
        rebind(reference, submission)
        with self.assertRaisesRegex(ev.ContractError, "physical"):
            ev.score(reference, submission)

    def test_target_and_clock_leakage_rejected(self):
        for change in ("future", "float", "bool_label"):
            reference, submission = fixture()
            if change == "future":
                reference["observations"][0]["cutoff_ns"] = 20
            elif change == "float":
                reference["observations"][0]["cutoff_ns"] = 10.0
            else:
                reference["observations"][0]["dorsal"] = True
            rebind(reference, submission)
            with self.subTest(change=change), self.assertRaises(ev.ContractError):
                ev.score(reference, submission)

    def test_binding_and_behavior_mismatch_rejected(self):
        for change in ("reference", "policy", "behavior", "split", "missing_control"):
            reference, submission = fixture()
            if change == "reference":
                submission["reference_sha256"] = "d" * 64
            elif change == "policy":
                reference["policy"]["target"] = "turn_occurrence"
                rebind(reference, submission)
            elif change == "missing_control":
                del submission["arm_receipts"]["shifted_neural_history"]
            else:
                field = "behavior_history_sha256" if change == "behavior" else "split_sha256"
                submission["arm_receipts"]["neural_history"][field] = "d" * 64
            with self.subTest(change=change), self.assertRaises(ev.ContractError):
                ev.score(reference, submission)

    def test_cli_executes_same_scoring_path(self):
        reference, submission = fixture()
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            for name, value in (("ref", reference), ("sub", submission)):
                (folder / name).write_text(json.dumps(value))
            result = subprocess.run([sys.executable, str(MODULE), str(folder / "ref"),
                                     str(folder / "sub"), "--output", str(folder / "out")],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads((folder / "out").read_text())["primary"],
                             ev.score(reference, submission)["primary"])

    def test_strict_json_parser_rejects_duplicate_keys_and_nonfinite(self):
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / "input.json"
            for text in ('{"id":1,"id":2}', '{"x": NaN}'):
                file.write_text(text)
                with self.assertRaises(ev.ContractError):
                    ev._load(file)

    def test_malformed_objects_raise_contract_error(self):
        for mutation in ("reference", "submission", "fold", "episode", "observation", "receipt", "prediction", "id"):
            reference, submission = fixture()
            if mutation == "reference":
                reference = []
            elif mutation == "submission":
                submission = []
            elif mutation in ("fold", "episode", "observation"):
                field = {"fold": "folds", "episode": "episode_inventory", "observation": "observations"}[mutation]
                reference[field][0] = None
                submission["reference_sha256"] = ev.digest(reference)
            elif mutation == "receipt":
                submission["arm_receipts"]["behavior"] = []
            elif mutation == "prediction":
                submission["predictions"][0] = "invalid"
            else:
                submission["predictions"][0]["id"] = []
            with self.subTest(mutation=mutation), self.assertRaises(ev.ContractError):
                ev.score(reference, submission)


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.samples = [{"worm_id": "A", "session_id": "s", "time_ns": t,
                         "available_ns": t, "support_end_ns": t,
                         "curvature": t * .1, "velocity": 1, "odor_encounter": t % 2,
                         "neural": [t, t * 2]} for t in range(1, 31)]
        self.events = [{"id": "e", "worm_id": "A", "session_id": "s", "cutoff_ns": 20}]

    def build(self):
        return ev.causal_histories(self.samples, self.events, [1, 2, 3], 6, 0)[0]

    def test_exact_past_only_history_and_matched_time_translation(self):
        row = self.build()
        self.assertEqual(row["neural_sample_times_ns"], [19, 18, 17])
        self.assertEqual(row["shifted_neural_sample_times_ns"], [13, 12, 11])
        self.assertEqual(row["neural_history"][:9], row["behavior"])
        self.assertEqual(row["shifted_neural_history"][:9], row["behavior"])
        self.assertEqual(row["neural_history"][9:], [19, 38, 18, 36, 17, 34])
        self.assertNotIn("dorsal", row)

    def test_future_mutation_cannot_change_history(self):
        expected = self.build()
        for sample in self.samples:
            if sample["time_ns"] >= 20:
                sample["neural"] = [999999, -999999]
                sample["curvature"] = 999999
        self.assertEqual(self.build(), expected)

    def test_nan_future_support_and_missing_context_rejected(self):
        for mutation in ("nan", "support", "context"):
            old = copy.deepcopy(self.samples)
            if mutation == "nan":
                self.samples[18]["neural"][0] = float("nan")
            elif mutation == "support":
                self.samples[18]["support_end_ns"] = 20
                self.samples[18]["available_ns"] = 20
            else:
                del self.samples[18]["odor_encounter"]
            with self.subTest(mutation=mutation), self.assertRaises(ev.ContractError):
                self.build()
            self.samples = old

    def test_no_wrap_drop_cross_worm_or_cross_session_history(self):
        for mutation in ("early", "session", "worm", "gap"):
            old_events, old_samples = copy.deepcopy(self.events), copy.deepcopy(self.samples)
            if mutation == "early":
                self.events[0]["cutoff_ns"] = 5
            elif mutation == "session":
                self.events[0]["session_id"] = "other"
            elif mutation == "worm":
                self.events[0]["worm_id"] = "B"
            else:
                self.samples.pop(18)
            with self.subTest(mutation=mutation), self.assertRaises(ev.ContractError):
                self.build()
            self.events, self.samples = old_events, old_samples

    def test_clocks_above_float_precision_remain_exact(self):
        offset = 2 ** 60
        expected = self.build()
        for sample in self.samples:
            for field in ("time_ns", "available_ns", "support_end_ns"):
                sample[field] += offset
        self.events[0]["cutoff_ns"] += offset
        actual = self.build()
        self.assertEqual(actual["neural_history"], expected["neural_history"])
        self.assertEqual(actual["neural_sample_times_ns"], [offset + 19, offset + 18, offset + 17])

    def test_irregular_shift_cannot_claim_exact_translation(self):
        self.samples = [row for row in self.samples if row["time_ns"] != 13]
        with self.assertRaisesRegex(ev.ContractError, "translation"):
            ev.causal_histories(self.samples, self.events, [1, 2, 3], 6, 1)


if __name__ == "__main__":
    unittest.main()
