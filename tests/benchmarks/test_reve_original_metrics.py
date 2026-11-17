"""Generated software controls; none are authentic REVE performance evidence."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "benchmarks/paper/PAPER-paper-method-003/implementations/original-physionet/metrics.py"
SPEC = importlib.util.spec_from_file_location("reve_original_metrics", PATH)
metrics = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(metrics)


def panel():
    targets = [{"event_id": f"S{person}-{label}", "participant": person, "label": label}
               for person in range(90, 110) for label in range(4)]
    predictions = [{"event_id": row["event_id"], "prediction": row["label"]} for row in targets]
    return predictions, targets


class ReveOriginalMetrics(unittest.TestCase):
    def test_class_metrics_hand_computed(self):
        # Repeat a known 4x4 confusion matrix across every required participant.
        # Truth/prediction rows: 00,01,11,22,23,33 => BA .75, acc 2/3,
        # expected chance2/9, kappa4/7, weightedF1=2/3.
        predictions, targets = [], []
        for person in range(90, 110):
            for index, (truth, prediction) in enumerate(((0, 0), (0, 1), (1, 1), (2, 2), (2, 3), (3, 3))):
                event_id = f"S{person}-{index}"
                predictions.append({"event_id": event_id, "prediction": prediction})
                targets.append({"event_id": event_id, "participant": person, "label": truth})
        result = metrics.score_predictions(reversed(predictions), targets)
        pooled = result["pooled"]
        self.assertAlmostEqual(pooled["balanced_accuracy"], .75)
        self.assertAlmostEqual(pooled["accuracy"], 2 / 3)
        self.assertAlmostEqual(pooled["cohen_kappa"], 4 / 7)
        self.assertAlmostEqual(pooled["weighted_f1"], 2 / 3)
        self.assertEqual(pooled["class_recall"], [.5, 1, .5, 1])
        self.assertEqual(pooled["class_support"], [40, 20, 40, 20])
        self.assertEqual(pooled["confusion_matrix"], [[20, 20, 0, 0], [0, 20, 0, 0], [0, 0, 20, 20], [0, 0, 0, 20]])
        self.assertFalse(result["historical_recipe_verified"])
        json.dumps(result, allow_nan=False)

    def test_missing_extra_and_duplicate_prediction_ids_fail(self):
        predictions, targets = panel()
        for bad in (predictions[:-1], predictions + [predictions[0]],
                    predictions + [{"event_id": "extra", "prediction": 0}]):
            with self.subTest(rows=len(bad)), self.assertRaises(metrics.MetricError):
                metrics.score_predictions(bad, targets)
        with self.assertRaises(metrics.MetricError):
            metrics.score_predictions(predictions, targets + [targets[0]])

    def test_weighted_f1_is_not_replaced_by_accuracy(self):
        predictions, targets = [], []
        for person in range(90, 110):
            for label in range(4):
                for repeat in range(2):
                    event_id = f"S{person}-{label}-{repeat}"
                    targets.append({"event_id": event_id, "participant": person, "label": label})
                    predictions.append({"event_id": event_id, "prediction": label if repeat else 0})
        pooled = metrics.score_predictions(predictions, targets)["pooled"]
        # Class F1s are4/7,2/3,2/3,2/3 with equal class support.
        self.assertAlmostEqual(pooled["weighted_f1"], 9 / 14)
        self.assertAlmostEqual(pooled["accuracy"], 5 / 8)
        self.assertAlmostEqual(pooled["cohen_kappa"], .5)

    def test_all_original_participants_required(self):
        predictions, targets = panel()
        with self.assertRaisesRegex(metrics.MetricError, "every original test participant"):
            metrics.score_predictions(predictions[4:], targets[4:])
        targets[0]["participant"] = 89
        with self.assertRaisesRegex(metrics.MetricError, "90..109"):
            metrics.score_predictions(predictions, targets)

    def test_score_vectors_are_finite_and_unambiguous(self):
        predictions, targets = panel()
        for scores in ([0, 0, float("nan"), 0], [0, float("inf"), 0, 0], [1, 2, 3],
                       [False, 0, 0, 0], ["1", 0, 0, 0]):
            predictions[0] = {"event_id": targets[0]["event_id"], "scores": scores}
            with self.subTest(scores=scores), self.assertRaises(metrics.MetricError):
                metrics.score_predictions(predictions, targets)
        predictions[0] = {"event_id": targets[0]["event_id"], "scores": [1, 1, 1, 1]}
        self.assertEqual(metrics.score_predictions(predictions, targets)["pooled"]["accuracy"], 1)
        predictions[0]["prediction"] = 0
        with self.assertRaisesRegex(metrics.MetricError, "exactly one"):
            metrics.score_predictions(predictions, targets)
        predictions[0] = {"event_id": targets[0]["event_id"], "prediction": True}
        with self.assertRaises(metrics.MetricError):
            metrics.score_predictions(predictions, targets)

    def test_pooled_primary_is_not_participant_mean(self):
        predictions, targets = panel()
        # Add 100 missed class0 events to S090, preserving all original people.
        for index in range(100):
            event_id = "extra-" + str(index)
            targets.append({"event_id": event_id, "participant": 90, "label": 0})
            predictions.append({"event_id": event_id, "prediction": 1})
        scored = metrics.score_predictions(predictions, targets)
        expected = (20 / 120 + 3) / 4
        self.assertAlmostEqual(scored["pooled"]["balanced_accuracy"], expected)
        participant_mean = sum(row["balanced_accuracy"] for row in scored["per_participant"].values()) / 20
        self.assertNotAlmostEqual(expected, participant_mean)

    def test_missing_participant_class_is_null_not_macro_subset(self):
        predictions, targets = panel()
        predictions.pop(0)
        targets.pop(0)
        result = metrics.score_predictions(predictions, targets)
        self.assertEqual(result["pooled"]["balanced_accuracy"], 1)
        self.assertIsNone(result["per_participant"]["90"]["balanced_accuracy"])
        self.assertIsNone(result["per_participant"]["90"]["class_recall"][0])
        json.dumps(result, allow_nan=False)

    def test_compare_requires_same_frozen_panel_and_keeps_published_separate(self):
        candidate, targets = panel()
        author = copy.deepcopy(candidate)
        for row in author:
            row["prediction"] = (row["prediction"] + 1) % 4
        kwargs = dict(panel_identity="a" * 64, candidate_panel_identity="a" * 64,
                      author_panel_identity="a" * 64, bootstrap_samples=100, bootstrap_seed=5)
        compared = metrics.compare_predictions(candidate, author, targets, **kwargs)
        self.assertEqual(compared["candidate_minus_author"]["balanced_accuracy"], 1)
        self.assertEqual(compared["published_baseline"]["balanced_accuracy_mean"], .648)
        self.assertIsNone(compared["paper_win"])
        self.assertFalse(compared["historical_recipe_verified"])
        interval = compared["uncertainty"]["intervals"]["balanced_accuracy"]
        self.assertEqual(interval, {"low": 1, "high": 1, "undefined_replicates": 0})
        self.assertEqual(compared, metrics.compare_predictions(candidate, author, targets, **kwargs))
        kwargs["author_panel_identity"] = "b" * 64
        with self.assertRaisesRegex(metrics.MetricError, "same frozen panel"):
            metrics.compare_predictions(candidate, author, targets, **kwargs)

    def test_run_summary_preserves_roster_and_both_sd_definitions(self):
        rows = [{"run_id": str(seed), "seed": seed,
                 **{metric: value for metric in metrics.METRICS}}
                for seed, value in enumerate((.5, .75, 1.0))]
        result = metrics.aggregate_runs(rows)
        summary = result["metrics"]["balanced_accuracy"]
        self.assertEqual(summary["mean"], .75)
        self.assertAlmostEqual(summary["sd_population_ddof0"], math.sqrt(1 / 24))
        self.assertAlmostEqual(summary["sd_sample_ddof1"], .25)
        self.assertEqual(result["historical_run_roster_and_sd_ddof"], "unresolved")
        self.assertIsNone(metrics.aggregate_runs(rows[:1])["metrics"]["balanced_accuracy"]["sd_sample_ddof1"])
        with self.assertRaises(metrics.MetricError):
            metrics.aggregate_runs(rows + [rows[0]])

    def test_cluster_bootstrap_keeps_methods_paired(self):
        predictions, targets = panel()
        # Person-level performance varies: half perfect, half entirely wrong.
        # Identical methods must have zero paired difference in every replicate.
        # Independently resampling people per method would violate this property.
        for prediction, target in zip(predictions, targets):
            if target["participant"] >= 100:
                prediction["prediction"] = (prediction["prediction"] + 1) % 4
        compared = metrics.compare_predictions(
            predictions, predictions, targets, panel_identity="a" * 64,
            candidate_panel_identity="a" * 64, author_panel_identity="a" * 64,
            bootstrap_samples=100, bootstrap_seed=9,
        )
        for interval in compared["uncertainty"]["intervals"].values():
            self.assertEqual(interval, {"low": 0, "high": 0, "undefined_replicates": 0})


if __name__ == "__main__":
    unittest.main()
