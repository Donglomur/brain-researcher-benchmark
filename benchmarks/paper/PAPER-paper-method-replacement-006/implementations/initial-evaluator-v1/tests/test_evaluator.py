import copy
import importlib.util
import json
import math
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
import evaluator as ev
from generated_control import make_plan, make_predictions

class Metrics(unittest.TestCase):
    def test_independent_pairwise_auc(self):
        rng = random.Random(18)
        for n in (3, 8, 40):
            y = [0, 1] + [rng.randrange(2) for _ in range(n - 2)]
            p = [rng.randrange(5) / 4 for _ in y]
            positive = [v for label, v in zip(y, p) if label]
            negative = [v for label, v in zip(y, p) if not label]
            expected = sum((a > b) + 0.5 * (a == b) for a in positive for b in negative) / (len(positive) * len(negative))
            self.assertAlmostEqual(ev.auc(y, p), expected)
    def test_ties_threshold_and_orientation(self):
        y, p = [0, 1, 0, 1], [.2, .5, .5, .8]
        m = ev._metrics(y, p, 1)
        self.assertEqual(m["roc_auc"], .875)
        self.assertAlmostEqual(m["f1_native_index1"], 2 / 3)
        flipped = ev._metrics(y, p, 0)
        self.assertEqual(flipped["roc_auc"], .875)
        self.assertEqual(flipped["f1_high_rms"], m["f1_high_rms"])
        self.assertAlmostEqual(ev.auc([1-z for z in y], [1-z for z in p]), .875)
    def test_source_class_f1_is_separate(self):
        y, p = [1, 1, 0, 0], [.5, .8, .2, .3]
        self.assertNotEqual(ev._metrics(y, p, 0)["f1_native_index1"], ev._metrics(y, p, 1)["f1_native_index1"])
    def test_one_class_auc_is_undefined(self):
        self.assertIsNone(ev.auc([1, 1], [.1, .2]))
    def test_quartile_integer_rounding(self):
        labels = ev.rms_quartile_labels([{"id": str(i), "rms": i} for i in range(7)])
        self.assertEqual([k for k, v in labels.items() if v == 0], ["0"])
        self.assertEqual([k for k, v in labels.items() if v == 1], ["5", "6"])
    def test_cutoff_tie_is_rejected(self):
        with self.assertRaisesRegex(ev.ContractError, "boundary tie"):
            ev.rms_quartile_labels([{"id": str(i), "rms": p} for i, p in enumerate([1, 1, 2, 3])])
    def test_blocks_merge_crossing_window_and_undefined_replicates(self):
        rows = [{"start_s": 58, "end_s": 63, "label_high_rms": 0},
                {"start_s": 65, "end_s": 70, "label_high_rms": 0},
                {"start_s": 121, "end_s": 126, "label_high_rms": 1}]
        result = ev._blocked_ci(rows, [.1, .2, .9], [.5, .5, .5], 100, 7)
        self.assertEqual(result["block_count"], 2)
        self.assertGreater(result["undefined_replicates"], 0)
        self.assertEqual(result["valid_replicates"] + result["undefined_replicates"], 100)
        self.assertEqual(result["paired_auc_delta_95"], [.5, .5])

class Contract(unittest.TestCase):
    def setUp(self):
        self.plan = make_plan()
        self.ref = ev.freeze(self.plan)
        self.candidate = make_predictions(self.ref, "candidate")
        self.baseline = make_predictions(self.ref, "baseline")
    def score(self):
        return ev.evaluate(self.ref, self.candidate, self.baseline, replicates=20, seed=42)
    def test_complete_paired_control(self):
        result = self.score()
        self.assertEqual(len(result["per_subject"]), 28)
        for count in result["subject_macro"]:
            self.assertEqual(count["candidate_auc"]["mean"], 1)
            self.assertEqual(count["baseline_auc"]["mean"], .5)
            self.assertEqual(count["paired_auc_delta"]["mean"], .5)
            self.assertEqual(count["paired_auc_delta"]["n_subjects"], 7)
        self.assertFalse(result["full_contract_complete"])
        self.assertEqual(result["scientific_qualification"], "unknown")
    def test_reference_tamper_rejected_even_after_rehash(self):
        self.ref["words"][0]["label_high_rms"] = 1
        self.ref["reference_sha256"] = ev.canonical_sha({k: v for k, v in self.ref.items() if k != "reference_sha256"})
        with self.assertRaisesRegex(ev.ContractError, "canonical"):
            ev.validate_reference(self.ref)
    def test_missing_subject_rejected(self):
        self.plan["words"] = [r for r in self.plan["words"] if r["subject"] != "sub_10"]
        with self.assertRaisesRegex(ev.ContractError, "seven-subject"):
            ev.freeze(self.plan)
    def test_source_trial_and_movie_bound(self):
        for field, value in (("trial", "trial999"), ("movie", "a_new_movie")):
            plan = copy.deepcopy(self.plan)
            plan["words"][0][field] = value
            with self.assertRaises(ev.ContractError):
                ev.freeze(plan)
    def test_overlap_rejected_touching_allowed(self):
        a, b = self.plan["words"][:2]
        b["start_s"], b["end_s"] = a["end_s"] - .1, a["end_s"] + 5
        with self.assertRaisesRegex(ev.ContractError, "support overlap"):
            ev.freeze(self.plan)
        b["start_s"] = a["end_s"]
        ev.freeze(self.plan)
    def test_train_only_channel_rank_ids(self):
        ranking = self.plan["channel_rankings"]["sub_1"]
        ranking["fit_word_ids"].append("sub_1_word002")
        with self.assertRaisesRegex(ev.ContractError, "ranking fit"):
            ev.freeze(self.plan)
    def test_missing_duplicate_extra_and_wrong_ensemble_predictions(self):
        variants = []
        a = copy.deepcopy(self.candidate); a["predictions"].pop(); variants.append(a)
        a = copy.deepcopy(self.candidate); a["predictions"].append(a["predictions"][0]); variants.append(a)
        a = copy.deepcopy(self.candidate); a["predictions"][0]["word_id"] = "sub_1_word000"; variants.append(a)
        a = copy.deepcopy(self.candidate); a["predictions"][0]["channels"] = ["WRONG"]; variants.append(a)
        a = copy.deepcopy(self.candidate); a["predictions"][0]["electrode_count"] = True; variants.append(a)
        for a in variants:
            with self.assertRaises(ev.ContractError):
                ev.evaluate(self.ref, a, self.baseline, 20)
    def test_unmatched_resources_and_model_selection(self):
        for field, value in (("shared_resources", {}), ("saved_split_file_sha256", "0"*64),
                             ("selection_split", "test"), ("probability_semantics", "native_index1"),
                             ("native_high_rms_index", {}), ("method", "mean_pool")):
            a = copy.deepcopy(self.candidate); a[field] = value
            with self.assertRaises(ev.ContractError):
                ev.evaluate(self.ref, a, self.baseline, 20)
    def test_nonfinite_and_bounds(self):
        for value in (math.nan, math.inf, -.1, 1.1, True):
            a = copy.deepcopy(self.candidate); a["predictions"][0]["probability_high_rms"] = value
            with self.assertRaises(ev.ContractError):
                ev.evaluate(self.ref, a, self.baseline, 20)
    def test_reordering_predictions_does_not_change_result(self):
        expected = self.score()
        self.candidate["predictions"].reverse()
        self.baseline["predictions"].reverse()
        actual = self.score()
        self.assertEqual(expected["per_subject"], actual["per_subject"])
        self.assertNotEqual(expected["comparison_provenance"]["candidate"]["prediction_content_sha256"], actual["comparison_provenance"]["candidate"]["prediction_content_sha256"])
    def test_subject_macro_not_pooled_windows(self):
        # Give one subject reversed predictions and others perfect: mean AUC=6/7.
        for row in self.candidate["predictions"]:
            if row["word_id"].startswith("sub_1_"):
                row["probability_high_rms"] = 1 - row["probability_high_rms"]
        result = self.score()
        self.assertAlmostEqual(result["subject_macro"][0]["candidate_auc"]["mean"], 6/7)
        self.assertAlmostEqual(result["subject_macro"][0]["candidate_auc"]["sem_descriptive"], 1/7)
    def test_native_binding_canonicalizes_per_run_maps_and_rejects_wrong_order(self):
        binding = {k: self.candidate[k] for k in ("reference_sha256", "arm", "method", "shared_resources", "saved_split_file_sha256", "pretraining_exposure_manifest_sha256", "selection_split")}
        binding["runs"] = []
        outputs = {}
        for ensemble in self.ref["ensembles"]:
            subject, count = ensemble["subject"], ensemble["electrode_count"]
            rows = [r for r in self.ref["words"] if r["subject"] == subject and r["split"] == "test" and r["label_high_rms"] is not None]
            high_index = count % 2
            binding["runs"].append({"subject": subject, "electrode_count": count, "high_rms_index": high_index,
                "ordered_word_ids": [r["id"] for r in rows], "model_sha256": "1"*64, "order_evidence_sha256": "2"*64,
                "channels": ensemble["channels"],
                "channel_order_evidence_sha256": self.ref["channel_rankings"][subject]["channel_order_evidence_sha256"]})
            native_labels = [high_index if r["label_high_rms"] else 1-high_index for r in rows]
            outputs[f"{subject}/{count}"] = {"labels": native_labels, "predicts": [.9 if y else .1 for y in native_labels]}
        bound = ev.bind_native(self.ref, binding, outputs)
        result = ev.evaluate(self.ref, bound, self.baseline, 20)
        self.assertEqual(result["subject_macro"][0]["candidate_auc"]["mean"], 1)
        original_channels = binding["runs"][0]["channels"]
        binding["runs"][0]["channels"] = ["WRONG_NATIVE_CHANNEL"]
        with self.assertRaisesRegex(ev.ContractError, "native channel membership/order"):
            ev.bind_native(self.ref, binding, outputs)
        binding["runs"][0]["channels"] = original_channels
        loss_key = next(key for key in outputs if key.endswith("/10"))
        saved = copy.deepcopy(outputs[loss_key])
        outputs[loss_key]["predicts"][:2] = [0.0, 1e-20]
        with self.assertRaisesRegex(ev.ContractError, "collapses distinct scores"):
            ev.bind_native(self.ref, binding, outputs)
        outputs[loss_key] = saved
        binding["runs"][0]["ordered_word_ids"].reverse()
        with self.assertRaisesRegex(ev.ContractError, "truth/order/class map"):
            ev.bind_native(self.ref, binding, outputs)
    def test_submission_interface_does_not_export_targets_or_rank_fit_ids(self):
        public = ev.submission_interface(self.ref)
        self.assertEqual(public["reference_sha256"], self.ref["reference_sha256"])
        self.assertEqual(len(public["test_words"]), 56)
        for row in public["test_words"]:
            self.assertEqual(set(row), {"id", "subject", "trial", "movie", "start_s", "end_s"})
        self.assertNotIn("channel_rankings", public)
        self.assertNotIn("words", public)
    def test_selected_channels_preserve_feature_order_not_rank_order(self):
        self.plan["channel_rankings"]["sub_1"]["feature_channel_order"].reverse()
        ref = ev.freeze(self.plan)
        ensemble = next(e for e in ref["ensembles"] if e["subject"] == "sub_1" and e["electrode_count"] == 10)
        self.assertEqual(ensemble["channels"], [f"GENERATED_ELECTRODE_{i:03d}" for i in reversed(range(10))])
    def test_each_native_run_class_map_is_required(self):
        self.candidate["native_high_rms_index"]["sub_1"].pop("90")
        with self.assertRaisesRegex(ev.ContractError, "every subject/count"):
            self.score()
    def test_json_duplicate_and_cli(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)
            bad = path/"bad.json"; bad.write_text('{"x":1,"x":2}')
            with self.assertRaisesRegex(ev.ContractError, "duplicate JSON"):
                ev.read_json(bad)
            subprocess.run([sys.executable, str(PACKAGE/"generated_control.py"), td], check=True)
            subprocess.run([sys.executable, str(PACKAGE/"evaluator.py"), "freeze", str(path/"generated-plan.json"), str(path/"ref.json")], check=True)
            subprocess.run([sys.executable, str(PACKAGE/"evaluator.py"), "score", str(path/"ref.json"), str(path/"generated-candidate.json"), str(path/"generated-baseline.json"), str(path/"scores.json"), "--replicates", "20"], check=True)
            self.assertEqual(json.loads((path/"scores.json").read_text())["subject_macro"][0]["paired_auc_delta"]["mean"], .5)

if __name__ == "__main__":
    unittest.main()
