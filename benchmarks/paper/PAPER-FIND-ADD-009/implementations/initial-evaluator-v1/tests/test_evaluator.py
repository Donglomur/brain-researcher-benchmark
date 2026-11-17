import copy
import importlib.util
import json
import math
import subprocess
import sys
import tempfile
from unittest import mock
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("voice_evaluator", ROOT / "evaluator.py")
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


def frames(values):
    return [[v + b * 0.01 for b in range(40)] for v in values]


def acoustic_row(tid, values, cid=None, mask=None):
    row = {"trial_id": tid, "mel_db": frames(values), "speech_mask": mask if mask is not None else [True] * len(values)}
    if cid:
        row["condition_id"] = cid
    return row


def manifest():
    plan = {"schema_version": 1, "task_id": e.TASK_ID, "data_release": "441124",
            "official_code_revision": e.CODE_REVISION, "mode": "offline_retrained",
            "split_policy": "author_day195", "sentence_policy": "disjoint", "neural_condition_id": "brain",
            "acoustic_profile": {"representation": "mel_power_db", "bands": 40, "sample_rate_hz": 16000,
                                 "window_ms": 50, "window": "hann", "hop_ms": 40,
                                 "dtw_policy": e.DTW_POLICY, "mel_filterbank_id": "test-filter",
                                 "db_reference_id": "test-ref", "silence_policy_id": "fixed-test-masks"},
            "trials": [{"trial_id": tid, "original_trial_id": tid, "session_id": session,
                        "sentence_id": tid, "participant_id": "T15", "partition": part}
                       for tid, session, part in [("train", "t15_day193", "train"),
                                                  ("val", "t15_day193", "validation"),
                                                  ("a", "t15_day195", "test"), ("b", "t15_day195", "test")]],
            "conditions": [{"condition_id": cid, "signal": signal, "decoder_id": cid + "-frozen",
                            "vocoder_id": "same-vocoder", "training_provenance_id": "frozen-train-ledger",
                            "training_trial_ids": ["train"], "selection_trial_ids": ["val"],
                            "external_speech_resources": []}
                           for cid, signal in [("brain", "neural"), ("steth", "stethoscope")]]}

    for session in e.TRAIN_SESSIONS:
        if session == "t15_day193":
            continue
        tid = "train-" + session
        plan["trials"].append({"trial_id": tid, "original_trial_id": tid, "session_id": session,
                               "sentence_id": tid, "participant_id": "T15", "partition": "train"})
        for condition in plan["conditions"]:
            condition["training_trial_ids"].append(tid)
    return plan


def population():
    refs = [acoustic_row(t, [0, 1, 2]) for t in ("a", "b")]
    preds = [acoustic_row(t, [0, 1, 2], c) for t in ("a", "b") for c in ("brain", "steth")]
    return refs, preds


class AcousticTests(unittest.TestCase):
    def test_independent_silence_removal_and_repeated_time(self):
        # These silence samples differ and occur at different times; padding must
        # never score as speech or be copied from the reference mask.
        reference = acoustic_row("a", [900, 0, 1, 2], mask=[False, True, True, True])
        prediction = acoustic_row("a", [0, -900, 0, 1, 2], "brain", [True, False, True, True, True])
        score = e.score_trial(reference, prediction)
        self.assertAlmostEqual(score["mean_band_pearson_r"], 1)
        self.assertEqual(score["reference_speech_frames"], 3)
        self.assertEqual(score["prediction_speech_frames"], 4)
        self.assertEqual(score["dtw_path_length"], 4)
        self.assertEqual(score["dtw_total_squared_cost"], 0)

    def test_manual_path_and_cost(self):
        path, cost = e.dtw_path(frames([0, 1, 2]), frames([0, 0, 1, 2]))
        self.assertEqual(path, [(0, 0), (0, 1), (1, 2), (2, 3)])
        self.assertEqual(cost, 0)
        # Every local cost ties at zero: diagonal predecessor has priority.
        path, cost = e.dtw_path(frames([0, 0]), frames([0, 0, 0]))
        self.assertEqual(path, [(0, 0), (0, 1), (1, 2)])

    def test_signed_correlation_and_not_flattened(self):
        self.assertAlmostEqual(e.pearson([0, 1, 2], [2, 1, 0]), -1)
        reference = acoustic_row("a", [0, 1, 2])
        prediction = copy.deepcopy(reference)
        # The shared path is constrained by 39 intact bands; one reverses.
        for i, frame in enumerate(prediction["mel_db"]):
            frame[0] = 2 - i
        result = e.score_trial(reference, prediction)
        self.assertAlmostEqual(result["band_pearson_r"][0], -1)
        self.assertAlmostEqual(result["mean_band_pearson_r"], 0.95)

    def test_independent_bandwise_oracle_and_exhaustive_path_cost(self):
        reference = [[float(i)] * 20 + [100.0 + i] * 20 for i in range(3)]
        prediction = [[float(v)] * 20 + [100.0 + i] * 20 for i, v in enumerate([0, 2, 1])]
        def all_costs(i, j, total):
            total += sum((a - b) ** 2 for a, b in zip(reference[i], prediction[j]))
            if (i, j) == (2, 2):
                return [total]
            results = []
            for di, dj in ((1, 1), (1, 0), (0, 1)):
                if i + di <= 2 and j + dj <= 2:
                    results += all_costs(i + di, j + dj, total)
            return results
        path, cost = e.dtw_path(reference, prediction)
        self.assertEqual(cost, min(all_costs(0, 0, 0)))
        self.assertEqual(path, [(0, 0), (1, 1), (2, 2)])
        score = e.score_trial({"mel_db": reference, "speech_mask": [True] * 3},
                              {"mel_db": prediction, "speech_mask": [True] * 3})
        self.assertAlmostEqual(score["mean_band_pearson_r"], .75)

    def test_full_population_and_paired_conditions(self):
        refs, preds = population()
        result = e.evaluate_acoustic(manifest(), refs, preds)
        self.assertEqual(result["declared_test_trials"], 2)
        self.assertEqual(len(result["trials"]), 4)
        self.assertEqual(result["paired_neural_minus_condition_r"]["steth"]["mean"], 0)
        self.assertFalse(result["authentic_population_verified"])
        self.assertEqual(result["scientific_qualification"], "unknown")

    def test_reject_missing_extra_duplicate_trial_condition(self):
        refs, preds = population()
        for bad in (preds[:-1], preds + [preds[0]], preds + [acoustic_row("unknown", [0, 1, 2], "brain")]):
            with self.subTest(bad=bad), self.assertRaises(e.ContractError):
                e.evaluate_acoustic(manifest(), refs, bad)
        with self.assertRaises(e.ContractError):
            e.evaluate_acoustic(manifest(), refs[:-1], preds)

    def test_train_selection_original_trial_and_session_leakage(self):
        for mutation in ("original", "session", "sentence", "selection"):
            plan = manifest()
            if mutation == "original":
                plan["trials"][2]["original_trial_id"] = "train"
            elif mutation == "session":
                plan["trials"][0]["session_id"] = "t15_day195"
            elif mutation == "sentence":
                plan["trials"][2]["sentence_id"] = "train"
            else:
                plan["conditions"][0]["selection_trial_ids"].append("a")
            with self.subTest(mutation=mutation), self.assertRaises(e.ContractError):
                e.validate_manifest(plan)

    def test_source_session_roster_cannot_be_subsetted(self):
        plan = manifest()
        removed = plan["trials"].pop()
        for condition in plan["conditions"]:
            condition["training_trial_ids"].remove(removed["trial_id"])
        with self.assertRaises(e.ContractError):
            e.validate_manifest(plan)

    def test_pretrained_cannot_omit_training_provenance(self):
        plan = manifest()
        plan["mode"] = "pretrained_inference"
        plan["conditions"][0]["training_trial_ids"] = []
        with self.assertRaises(e.ContractError):
            e.validate_manifest(plan)

    def test_matched_resource_exposure(self):
        plan = manifest()
        plan["conditions"][1]["vocoder_id"] = "different"
        with self.assertRaises(e.ContractError):
            e.validate_manifest(plan)

    def test_undefined_and_nonfinite_bands_are_not_omitted(self):
        for values in ([0, 0, 0], [0, math.nan, 2], [0, math.inf, 2]):
            with self.subTest(values=values), self.assertRaises(e.ContractError):
                e.score_trial(acoustic_row("a", [0, 1, 2]), acoustic_row("a", values))
        for mask in ([1, 1, 1], [True, False, False], [True]):
            with self.subTest(mask=mask), self.assertRaises(e.ContractError):
                e.score_trial(acoustic_row("a", [0, 1, 2]), acoustic_row("a", [0, 1, 2], mask=mask))

    def test_reviewer_duplicate_physical_trials_and_invalid_profile(self):
        plan = manifest()
        plan["trials"][3]["original_trial_id"] = "a"
        with self.assertRaises(e.ContractError):
            e.validate_manifest(plan)
        for profile in (None, [], True):
            plan = manifest()
            plan["acoustic_profile"] = profile
            with self.subTest(profile=profile), self.assertRaises(e.ContractError):
                e.validate_manifest(plan)
        with self.assertRaises(e.ContractError):
            e.score_trial(acoustic_row("a", [0, 1, 2]), acoustic_row("a", [1e308, 1, 2]))

    def test_explicit_resource_budget(self):
        with self.assertRaises(e.ContractError):
            e.score_trial(acoustic_row("a", [0, 1, 2]), acoustic_row("a", [0, 1, 2]), max_cells=8)

    def test_sessions_are_not_weighted_by_frame_or_trial_count(self):
        plan = manifest()
        plan["split_policy"] = "prospective_session_holdout"
        extra = dict(plan["trials"][3], trial_id="c", original_trial_id="c", sentence_id="c", session_id="t15_day196")
        plan["trials"].append(extra)
        refs = [acoustic_row(t, [0, 1, 2]) for t in ("a", "b", "c")]
        preds = [acoustic_row(t, [0, 1, 2], cid) for t in ("a", "b", "c") for cid in ("brain", "steth")]
        for row in preds:
            if row["trial_id"] == "c" and row["condition_id"] == "brain":
                for i, frame in enumerate(row["mel_db"]):
                    frame[0] = 2 - i
        result = e.evaluate_acoustic(plan, refs, preds)["condition_summaries"]["brain"]
        self.assertAlmostEqual(result["sentence_weighted"]["mean"], (1 + 1 + .95) / 3)
        self.assertAlmostEqual(result["session_equal_weighted"]["mean"], .975)


class ListeningTests(unittest.TestCase):
    def sample(self):
        plan = {"schema_version": 1, "task_id": e.TASK_ID, "trial_ids": ["a", "b"], "condition_ids": ["brain"], "cohort_label": "prospective",
                "tokenization_policy_id": "fixed-words", "phonemization_policy_id": "fixed-phonemes", "pairing_policy_id": "frozen-pairs",
                "pairs": [{"pair_id": "pair1", "trial_ids": ["a", "b"], "listener_ids": [str(i) for i in range(7)]}]}
        refs = [{"trial_id": t, "words": ["a", "b"], "phonemes": ["A", "B"]} for t in ("a", "b")]
        predictions = [{"trial_id": t, "condition_id": "brain", "listener_id": str(i), "words": ["a", "b"], "phonemes": ["A", "B"]}
                       for i in range(7) for t in ("a", "b")]
        return plan, refs, predictions

    def test_sentence_pair_then_seven_listener_median(self):
        plan, refs, pred = self.sample()
        for row in pred:
            if int(row["listener_id"]) >= 3 and row["trial_id"] == "a":
                row["words"] = ["a", "x"]
                row["phonemes"] = ["A", "X"]
        result = e.evaluate_transcriptions(plan, refs, pred)
        self.assertEqual(result["pairs"][0]["median_wer"], .25)
        self.assertEqual(result["pairs"][0]["median_per"], .25)
        self.assertNotEqual(result["pairs"][0]["median_wer"], 4 / 28)

    def test_named_listening_cohort_count_is_not_relabeled(self):
        plan, refs, pred = self.sample()
        plan["cohort_label"] = "paper_main_90"
        with self.assertRaises(e.ContractError):
            e.evaluate_transcriptions(plan, refs, pred)

    def test_token_edit_insertions_unbounded_empty_response(self):
        self.assertEqual(e.edit_distance(["a"], []), 1)
        self.assertEqual(e.edit_distance(["a"], ["a", "b", "c", "d"]), 3)
        self.assertEqual(e.edit_distance(["a", "b"], ["b", "a"]), 2)
        plan, refs, pred = self.sample()
        for row in pred:
            row["words"] = []
        self.assertEqual(e.evaluate_transcriptions(plan, refs, pred)["pairs"][0]["median_wer"], 1)

    def test_missing_listener_and_reused_pair_rejected(self):
        plan, refs, pred = self.sample()
        with self.assertRaises(e.ContractError):
            e.evaluate_transcriptions(plan, refs, pred[:-1])
        plan["pairs"].append(dict(plan["pairs"][0], pair_id="pair2"))
        with self.assertRaises(e.ContractError):
            e.evaluate_transcriptions(plan, refs, pred)


class CliTests(unittest.TestCase):
    def test_cli_input_pins_and_rejected_output_preservation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            refs, preds = population()
            for name, value in (("plan", manifest()), ("reference", refs), ("prediction", preds)):
                (root / (name + ".json")).write_text(json.dumps(value))
            command = [sys.executable, str(ROOT / "evaluator.py"), "acoustic", "--plan", str(root / "plan.json"),
                       "--reference", str(root / "reference.json"), "--prediction", str(root / "prediction.json"),
                       "--output", str(root / "output.json")]
            run = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            result = json.loads((root / "output.json").read_text())
            self.assertEqual(set(result["input_sha256"]), {"plan", "reference", "prediction"})
            prior = (root / "output.json").read_bytes()
            (root / "prediction.json").write_text(json.dumps(preds[:-1]))
            run = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(run.returncode, 2)
            self.assertEqual((root / "output.json").read_bytes(), prior)

    def test_receipts_bind_bytes_read_before_evaluation(self):
        import hashlib
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            refs, preds = population()
            for name, value in (("plan", manifest()), ("reference", refs), ("prediction", preds)):
                (root / (name + ".json")).write_text(json.dumps(value))
            original = (root / "prediction.json").read_bytes()
            real_evaluate = e.evaluate_acoustic
            def evaluate_then_mutate(*args):
                result = real_evaluate(*args)
                (root / "prediction.json").write_text("[]")
                return result
            with mock.patch.object(e, "evaluate_acoustic", side_effect=evaluate_then_mutate):
                e.main(["acoustic", "--plan", str(root / "plan.json"), "--reference", str(root / "reference.json"),
                        "--prediction", str(root / "prediction.json"), "--output", str(root / "output.json")])
            result = json.loads((root / "output.json").read_text())
            self.assertEqual(result["input_sha256"]["prediction"], hashlib.sha256(original).hexdigest())

    def test_duplicate_json_keys_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.json"
            path.write_text('{"a": 1, "a": 2}')
            with self.assertRaises(e.ContractError):
                e.load_json(path)


if __name__ == "__main__":
    unittest.main()
