import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

PATH = Path(__file__).resolve().parents[1] / "assess_panel.py"
spec = importlib.util.spec_from_file_location("biosignal_panel", PATH)
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def fixture():
    trial_ids = ["trial-%03d" % i for i in range(240)]
    folds = [{"fold_id": "fold-%d" % f, "test_trial_ids": trial_ids[f::10],
              "training_trial_ids": [t for i, t in enumerate(trial_ids) if i % 10 != f]}
             for f in range(10)]
    profile = {"representation": "mel_power_db", "bands": 40, "sample_rate_hz": 16000,
               "window_ms": 50, "window": "hann", "dtw_policy": p.acoustic.DTW_POLICY,
               "hop_ms": 10, "mel_filterbank_id": "generated", "db_reference_id": "generated",
               "silence_policy_id": "generated"}
    systems = {s: {"vocoder_sha256": "a" * 64, "external_speech_resources": [], "models": [
        {"fold_id": f["fold_id"], "signal": signal,
         "decoder_sha256": hashlib.sha256((s + signal + f["fold_id"]).encode()).hexdigest(),
         "training_trial_ids": f["training_trial_ids"][:], "selection_trial_ids": []}
        for f in folds for signal in p.SIGNALS]} for s in p.SYSTEMS}
    plan = {"schema_version": "voice-biosignal-panel/v1", "task_id": p.acoustic.TASK_ID,
            "data_release": "441124", "source_panel": "extended_data_5c_240",
            "original_support_sha256": "b" * 64, "source_input_features": p.FEATURES,
            "source_feature_bin_ms": 10, "source_context_ms": 600,
            "vocabulary": ["word-%d" % i for i in range(50)], "acoustic_profile": profile,
            "trials": [{"trial_id": t, "original_trial_id": "physical-" + t, "participant_id": "T15",
                        "session_id": "session-%d" % (i % 3), "sentence_id": "sentence-" + t}
                       for i, t in enumerate(trial_ids)], "folds": folds, "systems": systems}
    references = [{"trial_id": t, "mel_db": [[float(j)] * 40 for j in range(3)],
                   "speech_mask": [True] * 3} for t in trial_ids]
    predictions = {}
    for s in p.SYSTEMS:
        models = {(m["signal"], m["fold_id"]): m for m in systems[s]["models"]}
        predictions[s] = [{**copy.deepcopy(ref), "signal": signal, "fold_id": "fold-%d" % (i % 10),
                           "decoder_sha256": models[signal, "fold-%d" % (i % 10)]["decoder_sha256"]}
                          for i, ref in enumerate(references) for signal in p.SIGNALS]
    return plan, references, predictions


class AssessmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan, cls.refs, cls.pred = fixture()

    def test_complete_panel_math_and_paired_trial_identity(self):
        pred = copy.deepcopy(self.pred)
        row = pred["paper_data_author_code"][0]
        for i, frame in enumerate(row["mel_db"]):
            frame[0] = 2 - i
        result = p.assess(self.plan, self.refs, pred)
        self.assertEqual(len(result["trials"]), 3600)
        self.assertEqual(result["declared_trials"], 240)
        self.assertEqual(result["declared_folds"], 10)
        self.assertAlmostEqual(result["summaries"]["author_baseline"]["neural"]["trial_weighted"]["mean"], 1)
        self.assertAlmostEqual(result["summaries"]["paper_data_author_code"]["neural"]["trial_weighted"]["mean"],
                               1 - .05 / 240)
        delta = result["descriptive_paired_contrasts"]["paper_data_author_code_minus_paper_data"]["neural"]
        self.assertAlmostEqual(delta["trial_weighted"]["mean"], -.05 / 240)
        self.assertAlmostEqual(delta["trials"][0]["delta_r"], -.05)
        self.assertEqual(delta["trials"][0]["fold_id"], "fold-0")
        self.assertEqual(delta["trials"][0]["session_id"], "session-0")
        self.assertEqual(delta["per_fold"]["fold-1"]["mean"], 0)
        self.assertFalse(result["authentic_population_verified"])
        self.assertEqual(result["scientific_qualification"], "unknown")
        self.assertNotIn("reward", result)

    def test_prediction_coverage_and_fold_model_routing(self):
        for change in ("missing", "duplicate", "unknown", "fold", "model", "arm"):
            pred = copy.deepcopy(self.pred)
            rows = pred["paper_data"]
            if change == "missing": rows.pop()
            elif change == "duplicate": rows.append(rows[0])
            elif change == "unknown": rows[0]["trial_id"] = "unlisted"
            elif change == "fold": rows[0]["fold_id"] = "fold-1"
            elif change == "model": rows[0]["decoder_sha256"] = "0" * 64
            else: del pred["author_baseline"]
            with self.subTest(change=change), self.assertRaises(p.ContractError):
                p.assess(self.plan, self.refs, pred)

    def test_original_trial_fold_and_training_completeness(self):
        for change in ("subset", "physical", "fold_count", "fold_repeat", "training", "model_train", "selection", "modality"):
            plan = copy.deepcopy(self.plan)
            if change == "subset": plan["trials"].pop()
            elif change == "physical": plan["trials"][0]["original_trial_id"] = plan["trials"][1]["original_trial_id"]
            elif change == "fold_count": plan["folds"].pop()
            elif change == "fold_repeat":
                plan["folds"][1]["test_trial_ids"] = plan["folds"][0]["test_trial_ids"][:]
                plan["folds"][1]["training_trial_ids"] = plan["folds"][0]["training_trial_ids"][:]
            elif change == "training": plan["folds"][0]["training_trial_ids"].append("trial-000")
            elif change == "model_train": plan["systems"]["paper_data"]["models"][0]["training_trial_ids"].pop()
            elif change == "selection": plan["systems"]["paper_data"]["models"][0]["selection_trial_ids"] = ["trial-000"]
            else: plan["systems"]["paper_data"]["models"][0]["signal"] = "microphone"
            with self.subTest(change=change), self.assertRaises(p.ContractError):
                p.validate_plan(plan)

    def test_support_does_not_assume_equal_folds_or_session_holdout(self):
        plan = copy.deepcopy(self.plan)
        plan["folds"][0]["test_trial_ids"].append("trial-001")
        plan["folds"][1]["test_trial_ids"].remove("trial-001")
        trial_ids = {r["trial_id"] for r in plan["trials"]}
        for fold in plan["folds"]:
            fold["training_trial_ids"] = sorted(trial_ids - set(fold["test_trial_ids"]))
        for system in plan["systems"].values():
            for model in system["models"]:
                model["training_trial_ids"] = next(f["training_trial_ids"][:] for f in plan["folds"] if f["fold_id"] == model["fold_id"])
        _, folds, held, _ = p.validate_plan(plan)
        self.assertEqual(len(folds["fold-0"]["test_trial_ids"]), 25)
        self.assertEqual(held["trial-001"], "fold-0")

    def test_resource_profile_and_target_coverage(self):
        for change in ("vocoder", "features", "words", "frontend"):
            plan = copy.deepcopy(self.plan)
            if change == "vocoder": plan["systems"]["paper_data"]["vocoder_sha256"] = "c" * 64
            elif change == "features": plan["source_input_features"]["neural"] = 40
            elif change == "words": plan["vocabulary"].pop()
            else: plan["acoustic_profile"]["bands"] = 25
            with self.subTest(change=change), self.assertRaises(p.ContractError):
                p.validate_plan(plan)
        for refs in (self.refs[:-1], self.refs + [self.refs[0]]):
            with self.assertRaises(p.ContractError): p.assess(self.plan, refs, self.pred)

    def test_undefined_features_rejected_without_dropping_trial(self):
        pred = copy.deepcopy(self.pred)
        pred["author_baseline"][0]["mel_db"] = [[0.0] * 40] * 3
        with self.assertRaises(p.ContractError): p.assess(self.plan, self.refs, pred)


class CliTests(unittest.TestCase):
    def test_receipts_use_loaded_bytes_and_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("plan", "reference", "prediction"):
                (root / name).write_text("{}")
            command = [item for name in ("plan", "reference", "prediction", "output")
                       for item in ("--" + name, str(root / name))]
            def mutate(*args):
                (root / "prediction").write_text("[]")
                return {"generated_cli_receipt_control": True}
            with mock.patch.object(p, "assess", side_effect=mutate): p.main(command)
            raw = (root / "output").read_bytes()
            self.assertEqual(json.loads(raw)["input_sha256"]["prediction"], hashlib.sha256(b"{}").hexdigest())
            with mock.patch.object(p, "assess", return_value={}), self.assertRaises(SystemExit): p.main(command)
            self.assertEqual((root / "output").read_bytes(), raw)

    def test_real_cli_rejects_bad_plan_before_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("plan", "reference", "prediction"): (root / name).write_text("{}")
            command = [item for name in ("plan", "reference", "prediction", "output")
                       for item in ("--" + name, str(root / name))]
            with self.assertRaises(SystemExit): p.main(command)
            self.assertFalse((root / "output").exists())


if __name__ == "__main__":
    unittest.main()
