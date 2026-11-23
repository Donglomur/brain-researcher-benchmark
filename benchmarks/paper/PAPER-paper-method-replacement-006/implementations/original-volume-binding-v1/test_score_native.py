"""Small generated controls: no real labels, neural arrays, or model execution."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import score_native as s

b = s.b


def generated_panel():
    """Build structural test metadata, never historical source authenticity."""
    binding = {"task_id": b.TASK, "profile": b.PROFILE,
               "source_revision": b.REVISION, "endpoint": "rms",
               "clean_laplacian_sha256": b.CLEAN_SHA256,
               "word_onset_is_neural_support": False, "subjects": {}}
    for ordinal, (subject, trial) in enumerate(b.TRIALS.items()):
        # Unequal per-subject row counts discriminate macro from pooled scores.
        n = 40 + 20 * ordinal
        order = [f"generated-E{i}" for i in range(90)]
        binding["subjects"][subject] = {
            "subject": subject, "trial": trial,
            "rows": [{"manifest_index": i, "row_id": f"{subject}/{trial}/{n-i-1}.npy",
                      "label_high_rms": i % 2, "word_onset_s": i / 100} for i in range(n)],
            "splits": {"train": list(range(n * 8 // 10)),
                       "val": list(range(n * 8 // 10, n * 9 // 10)),
                       "test": list(reversed(range(n * 9 // 10, n)))},
            "feature_channel_order": order,
            "ensembles": {str(c): {"channels": order[:c], "feature_indices": list(range(c))}
                          for c in b.COUNTS}}
    binding["binding_sha256"] = b.canonical_sha(binding)
    native = {"binding_sha256": binding["binding_sha256"], "runs": {}}
    for ordinal, subject in enumerate(b.TRIALS):
        data = binding["subjects"][subject]
        for count in b.COUNTS:
            high = (ordinal + count) % 2
            indices = data["splits"]["test"]
            labels = [high if data["rows"][i]["label_high_rms"] else 1 - high for i in indices]
            native["runs"][f"{subject}/{count}"] = {
                "label2idx": {"True": high, "False": 1-high},
                "channels": data["ensembles"][str(count)]["channels"],
                "manifest_indices": indices, "labels": labels,
                "predicts": [0.9 if y else 0.1 for y in labels]}
    return binding, native


class NativeScoringControls(unittest.TestCase):
    def test_rank_ties_and_native_half_threshold(self):
        # Four cross-class pairs: one win and two half-credit ties => AUC 0.5.
        metrics = s.binary_metrics([0, 1, 0, 1], [0.1, 0.1, 0.9, 0.9])
        self.assertEqual(metrics["roc_auc"], 0.5)
        self.assertEqual(metrics["f1_native_index1"], 0.5)
        self.assertEqual(s.binary_metrics([0, 1], [0.5, 0.5])["f1_native_index1"], 0)
        self.assertEqual(s.binary_metrics([0, 1], [0, 1])["roc_auc"], 1)

    def test_auc_against_pairwise_oracle_and_both_orientations(self):
        import itertools
        labels = [0, 1, 0, 1]
        for scores in itertools.product((0.0, 0.5, 1.0), repeat=4):
            expected = sum((scores[i] > scores[j]) + 0.5 * (scores[i] == scores[j])
                           for i in (1, 3) for j in (0, 2)) / 4
            self.assertEqual(s.binary_metrics(labels, list(scores))["roc_auc"], expected)
            inverse = s.binary_metrics([1-y for y in labels], [1-p for p in scores])
            self.assertEqual(inverse["roc_auc"], expected)

    def test_full_original_panel_and_tiny_probabilities(self):
        binding, native = generated_panel()
        run = native["runs"]["sub_1/10"]
        tiny = 2.0 ** -60
        self.assertEqual(run["label2idx"]["True"], 0)
        run["predicts"] = [2*tiny if y else tiny for y in run["labels"]]
        report = s.score_native(binding, native)
        self.assertEqual(len(report["per_subject_count"]), 49)
        self.assertEqual([r["electrode_count"] for r in report["by_electrode_count"]], list(b.COUNTS))
        self.assertTrue(all(r["roc_auc"] == 1 for r in report["per_subject_count"]))
        self.assertTrue(all(r["subject_mean_roc_auc"] == 1 for r in report["by_electrode_count"]))
        self.assertEqual(report["primary_electrode_count"], 90)
        self.assertFalse(report["historical_sem_estimator_verified"])
        self.assertEqual(report["native_content_sha256"], b.canonical_sha(native))

    def test_equal_subject_mean_and_explicit_sample_sem(self):
        binding, native = generated_panel()
        for count in b.COUNTS:
            run = native["runs"][f"sub_1/{count}"]
            run["predicts"] = [1-p for p in run["predicts"]]
        report = s.score_native(binding, native)
        for row in report["by_electrode_count"]:
            self.assertAlmostEqual(row["subject_mean_roc_auc"], 6/7)
            self.assertAlmostEqual(row["subject_sem_ddof1_roc_auc"], 1/7)

    def test_original_binding_rejections_reach_scorer(self):
        binding, native = generated_panel()
        for key, value in (("labels", [1, 1, 1, 1]),
                           ("manifest_indices", [36, 37, 38, 39]),
                           ("channels", ["different"]), ("predicts", [float("nan")] * 4)):
            bad = copy.deepcopy(native)
            bad["runs"]["sub_1/1"][key] = value
            with self.assertRaises(b.BindingError, msg=key):
                s.score_native(binding, bad)
        bad = copy.deepcopy(native)
        bad["runs"].pop("sub_10/20")
        with self.assertRaisesRegex(b.BindingError, "49"):
            s.score_native(binding, bad)
        binding["subjects"]["sub_1"]["rows"][0]["word_onset_s"] = 7
        with self.assertRaisesRegex(b.BindingError, "changed"):
            s.score_native(binding, native)

    def test_invalid_binary_inputs(self):
        for labels, probabilities in (([], []), ([0, 1], [0.1]), ([0, 0], [0, 1]),
                                      ([False, 1], [0, 1]), ([0, 1], [0, float("inf")]),
                                      ([0, 1], [0, 1.01])):
            with self.assertRaises(b.BindingError):
                s.binary_metrics(labels, probabilities)

    def test_cli_roundtrip_and_duplicate_json_rejection(self):
        binding, native = generated_panel()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "binding.json").write_text(json.dumps(binding))
            (root / "native.json").write_text(json.dumps(native))
            command = [sys.executable, "-B", str(Path(s.__file__)),
                       str(root / "binding.json"), str(root / "native.json"), str(root / "report.json")]
            completed = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads((root / "report.json").read_text())
            self.assertEqual(report, s.score_native(binding, native))
            (root / "native.json").write_text('{"runs": {}, "runs": {}}')
            completed = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("duplicate JSON key", completed.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
