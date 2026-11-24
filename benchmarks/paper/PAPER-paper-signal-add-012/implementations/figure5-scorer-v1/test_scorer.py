"""Generated controls only; these labels are not participant data."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

MODULE_PATH = Path(__file__).with_name("scorer.py")
spec = importlib.util.spec_from_file_location("figure5_scorer", MODULE_PATH)
scorer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scorer)


def encoded(document):
    return json.dumps(document, allow_nan=False).encode()


def fixture():
    roster = [f"generated-{index:02}" for index in range(19)]
    targets = {"schema_version": 1, "task_id": scorer.TASK_ID, "panel": scorer.PANEL,
               "participant_ids": roster, "source_binding_sha256": "a" * 64,
               "observations": []}
    rows = []
    for participant in roster:
        for label in (0, 1):
            count = 4 if participant == roster[-1] else 1
            for index in range(count):
                window = f"generated-{label}-{index}"
                targets["observations"].append({"participant_id": participant,
                                                 "window_id": window, "awake": label})
                rows.append({"participant_id": participant, "window_id": window,
                             "held_out_participant_id": participant,
                             "predicted_awake": label, "score_awake": float(label)})
    predictions = {"schema_version": 1, "access_condition": "author_reference",
                   "target_manifest_sha256": hashlib.sha256(encoded(targets)).hexdigest(),
                   "observations": rows}
    return targets, predictions


def run_score(targets, author, candidate=None):
    blob = encoded(targets)
    candidate = copy.deepcopy(author if candidate is None else candidate)
    candidate["access_condition"] = "paper_data"
    return scorer.score_panel(blob, encoded(author), encoded(candidate),
                              expected_target_sha256=hashlib.sha256(blob).hexdigest())


class MetricsTests(unittest.TestCase):
    def test_hand_derived_ties_and_balanced_accuracy(self):
        result = scorer.binary_metrics([0, 0, 1, 1], [0, 1, 1, 1], [.1, .5, .5, .9])
        self.assertEqual(result["balanced_accuracy"], .75)
        self.assertEqual(result["roc_auc"], .875)
        self.assertEqual((result["true_awake"], result["true_lor"]), (2, 1))
        self.assertEqual(scorer.binary_metrics([0, 1], [0, 1], [0, 0])["roc_auc"], .5)
        self.assertEqual(scorer.binary_metrics([0, 1], [0, 1], [1, 0])["roc_auc"], 0)

    def test_auc_matches_independent_pairwise_oracle(self):
        rng = random.Random(472)
        for _ in range(200):
            labels = [0, 1] + [rng.randrange(2) for _ in range(rng.randrange(12))]
            scores = [rng.randrange(-3, 4) for _ in labels]
            positives = [s for s, label in zip(scores, labels) if label == 1]
            negatives = [s for s, label in zip(scores, labels) if label == 0]
            expected = sum((p > n) + .5 * (p == n) for p in positives for n in negatives) / (len(positives) * len(negatives))
            result = scorer.binary_metrics(labels, [1] * len(labels), scores)
            self.assertAlmostEqual(result["roc_auc"], expected, places=14)
            self.assertEqual(result["balanced_accuracy"], .5)

    def test_roc_curve_exact_threshold_groups(self):
        result = scorer.binary_metrics([0, 0, 1, 1], [0, 1, 1, 1], [.1, .5, .5, .9])
        self.assertEqual(result["roc_curve"], [
            {"threshold": None, "false_positive_rate": 0., "true_positive_rate": 0.},
            {"threshold": .9, "false_positive_rate": 0., "true_positive_rate": .5},
            {"threshold": .5, "false_positive_rate": .5, "true_positive_rate": 1.},
            {"threshold": .1, "false_positive_rate": 1., "true_positive_rate": 1.}])
        tied = scorer.binary_metrics([0, 1], [0, 1], [0, 0])["roc_curve"]
        self.assertEqual(len(tied), 2)
        self.assertEqual(tied[-1], {"threshold": 0, "false_positive_rate": 1., "true_positive_rate": 1.})
        # The sentinel must stay strict-JSON-safe even when the largest score
        # cannot be increased to another finite floating-point value.
        extreme = scorer.binary_metrics([0, 1], [0, 1], [-sys.float_info.max, sys.float_info.max])
        json.dumps(extreme, allow_nan=False)
        self.assertIsNone(extreme["roc_curve"][0]["threshold"])

    def test_roc_curve_matches_threshold_oracle_and_auc(self):
        rng = random.Random(968)
        for _ in range(100):
            labels = [0, 1] + [rng.randrange(2) for _ in range(rng.randrange(20))]
            scores = [rng.randrange(-5, 6) for _ in labels]
            result = scorer.binary_metrics(labels, [0] * len(labels), scores)
            curve = result["roc_curve"]
            self.assertEqual([point["threshold"] for point in curve[1:]],
                             sorted(set(scores), reverse=True))
            for point in curve[1:]:
                selected = [score >= point["threshold"] for score in scores]
                self.assertEqual(point["true_positive_rate"],
                                 sum(hit and label == 1 for hit, label in zip(selected, labels)) / sum(labels))
                self.assertEqual(point["false_positive_rate"],
                                 sum(hit and label == 0 for hit, label in zip(selected, labels)) / labels.count(0))
            area = sum((right["false_positive_rate"] - left["false_positive_rate"]) *
                       (right["true_positive_rate"] + left["true_positive_rate"]) / 2
                       for left, right in zip(curve, curve[1:]))
            self.assertAlmostEqual(area, result["roc_auc"], places=14)

    def test_scores_and_hard_decisions_remain_separate(self):
        result = scorer.binary_metrics([0, 1], [1, 1], [-1000, 1000])
        self.assertEqual((result["balanced_accuracy"], result["roc_auc"]), (.5, 1))

    def test_complete_roster_macro_mean_and_pairing(self):
        targets, author = fixture()
        candidate = copy.deepcopy(author)
        for row in candidate["observations"]:
            if row["participant_id"] == targets["participant_ids"][-1]:
                row["predicted_awake"] = 1 - row["predicted_awake"]
                row["score_awake"] = 1 - row["score_awake"]
        report = run_score(targets, author, candidate)
        self.assertEqual(report["observation_count"], 44)
        for metric in ("balanced_accuracy", "roc_auc"):
            self.assertEqual(report["arms"]["candidate"]["summary"][metric]["mean"], 18 / 19)
            self.assertNotAlmostEqual(report["arms"]["candidate"]["summary"][metric]["mean"], 36 / 44)
            self.assertEqual(report["mean_paired_difference"][metric], -1 / 19)
            self.assertEqual(report["paired_candidate_minus_author"][-1][metric], -1)
            self.assertAlmostEqual(report["arms"]["candidate"]["summary"][metric]["descriptive_subject_sem"], 1 / 19)

    def test_order_invariant_alignment(self):
        targets, author = fixture()
        candidate = copy.deepcopy(author)
        candidate["observations"].reverse()
        report = run_score(targets, author, candidate)
        self.assertEqual(report["arms"]["author"], report["arms"]["candidate"])

    def test_missing_duplicate_extra_windows_and_wrong_fold(self):
        targets, author = fixture()
        for mutation in ("missing", "duplicate", "extra", "fold", "binding"):
            with self.subTest(mutation=mutation):
                candidate = copy.deepcopy(author)
                if mutation == "missing":
                    candidate["observations"].pop()
                elif mutation == "duplicate":
                    candidate["observations"].append(candidate["observations"][0])
                elif mutation == "extra":
                    candidate["observations"][0]["window_id"] = "unfrozen-window"
                elif mutation == "fold":
                    candidate["observations"][0]["held_out_participant_id"] = "generated-01"
                else:
                    candidate["target_manifest_sha256"] = "b" * 64
                with self.assertRaises(ValueError):
                    run_score(targets, author, candidate)

    def test_target_roster_and_class_failures(self):
        for mutation in ("18", "20", "duplicate", "missing_class", "unknown", "duplicate_window", "panel"):
            with self.subTest(mutation=mutation):
                targets, author = fixture()
                if mutation == "18":
                    targets["participant_ids"].pop()
                elif mutation == "20":
                    targets["participant_ids"].append("generated-extra")
                elif mutation == "duplicate":
                    targets["participant_ids"][-1] = targets["participant_ids"][0]
                elif mutation == "missing_class":
                    targets["observations"][0]["awake"] = 1
                elif mutation == "unknown":
                    targets["observations"][0]["participant_id"] = "unknown"
                elif mutation == "duplicate_window":
                    targets["observations"].append(targets["observations"][0])
                else:
                    targets["panel"] = "dataset3_static_contrast"
                author["target_manifest_sha256"] = hashlib.sha256(encoded(targets)).hexdigest()
                with self.assertRaises(ValueError):
                    run_score(targets, author)

    def test_invalid_values_and_json(self):
        for labels, predictions, scores in (([True, 0], [1, 0], [1, 0]),
                                            ([0, 1], [False, 1], [0, 1]),
                                            ([0, 1], [0, 1], [float("inf"), 1]),
                                            ([0, 1], [0, 1], [True, 1]),
                                            ([1, 1], [1, 1], [0, 1]),
                                            ([0, 1], [0], [0, 1])):
            with self.assertRaises(ValueError):
                scorer.binary_metrics(labels, predictions, scores)
        for blob in (b'{"schema_version":1,"schema_version":1}',
                     b'{"schema_version":true}', b'{"schema_version":1,"x":NaN}'):
            with self.assertRaises(ValueError):
                scorer._decode(blob)
        targets, author = fixture()
        with self.assertRaises(ValueError):
            scorer.score_panel(encoded(targets), encoded(author), encoded(author), expected_target_sha256="0" * 64)

    def test_cli_reports_private_summary_and_preserves_inputs(self):
        targets, author = fixture()
        candidate = copy.deepcopy(author)
        candidate["access_condition"] = "paper_data_author_code"
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            paths = [folder / name for name in ("targets.json", "author.json", "candidate.json")]
            for path, doc in zip(paths, (targets, author, candidate)):
                path.write_bytes(encoded(doc))
            output = folder / "operator-report.json"
            command = [sys.executable, "-I", "-B", str(MODULE_PATH), "--targets", str(paths[0]),
                       "--expected-target-sha256", hashlib.sha256(encoded(targets)).hexdigest(),
                       "--author", str(paths[1]), "--candidate", str(paths[2]), "--output", str(output)]
            result = subprocess.run(command, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(output.read_text())
            self.assertEqual(report["arms"]["author"]["summary"]["balanced_accuracy"]["mean"], 1)
            self.assertNotIn("paper_win", report)
            self.assertEqual(report["declared_access_conditions"]["candidate"], "paper_data_author_code")
            for arm in ("author", "candidate"):
                records = report["arms"][arm]["participants"]
                self.assertEqual(len(records), 19)
                self.assertTrue(all(len(record["roc_curve"]) == 3 for record in records))
                self.assertTrue(all(record["roc_curve"][0]["threshold"] is None for record in records))
            self.assertNotIn("source_roc_summary", report)
            self.assertAlmostEqual(report["reproduction_offsets_from_rounded_source"]["candidate"]["balanced_accuracy"], .07)
            command[-1] = str(paths[0])
            result = subprocess.run(command, capture_output=True, text=True, timeout=20)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(paths[0].read_bytes(), encoded(targets))


if __name__ == "__main__":
    unittest.main(verbosity=2)
