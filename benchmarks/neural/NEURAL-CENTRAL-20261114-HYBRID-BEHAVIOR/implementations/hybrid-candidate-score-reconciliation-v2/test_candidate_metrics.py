"""Generated score controls; no authentic data, predictions, fits, or models."""
from copy import deepcopy
import hashlib
import math
from pathlib import Path
import sys
import types
import unittest


ROOT = Path(__file__).resolve().parent
OLD = ROOT.parent / "hybrid-frozen-model-candidate"


def load(name, path, expected=None):
    raw = path.read_bytes()
    if expected is not None and hashlib.sha256(raw).hexdigest() != expected:
        raise RuntimeError("predecessor source changed: " + path.name)
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


metrics = load("candidate_metrics", ROOT / "candidate_metrics.py")
load("source_binding", OLD / "source_binding.py",
     "1079a68cb275a35543f02dff2ad973ef2ae2e89b85c72fab9263d00eee89c3ce")
legacy = load("legacy_result_contract", ROOT / "historical/result_contract.pre-integration.py",
              "f23846ae3825f05caff9e8ec7d268db9690b4cb67fcfa9ae66380f4b9b5129ed")
consumer = load("consumer", OLD / "runner/consumer.py",
                "c5876452457f05c3f9fe69015f7e6cff565dcfa43b6a7b9e8921b096cdd1d00b")
scoring = load("scoring", OLD / "runner/scoring.py",
               "c2b90aff66015aa33aaa3f73660a628d2b4b4ac021026a3d8129e2ee15f745db")


def fixture():
    # Analytic full-population uniform predictor. A tie predicts action 1.
    # Counts are invented: two sampling rows and two terminal rows, with the
    # terminal supports adding to exactly the full number of completed trials.
    supports = [79125, 79126, 2442, 2442]
    loss = -math.log(0.25)
    return {
        "schema": "hybrid-protected-main-score-v1",
        "primary_subject_session_mean_nll": loss,
        "subject_mean_nll": {str(s): loss for s in range(1, 21)},
        "session_mean_nll": {str(s) + ":" + str(k): loss for s in range(1, 21) for k in range(1, 5)},
        "trial_balanced_nll": loss, "decision_weighted_nll": loss,
        "accuracy": 79125 / 163135,
        "per_action_recall": [1.0, 0.0, 0.0, 0.0], "macro_action_recall": 0.25,
        "stop_brier": 0.25,
        "confusion": [[n, 0, 0, 0] for n in supports],
        "participants": 20, "sessions": 80, "trials": 4884, "decisions": 163135,
        "scoring_unit_for_uncertainty": "participant, not row/fold/coding",
        "claim": "conditional next-action prediction on selected completed two-option trials",
        "benchmark_ready": False, "scientific_count_delta": 0,
    }


def derive_confusion_metrics(score):
    matrix = score["confusion"]
    score["per_action_recall"] = [row[i] / sum(row) if sum(row) else None for i, row in enumerate(matrix)]
    defined = [x for x in score["per_action_recall"] if x is not None]
    score["macro_action_recall"] = math.fsum(defined) / len(defined)
    score["accuracy"] = sum(row[i] for i, row in enumerate(matrix)) / 163135


class MetricsControls(unittest.TestCase):
    def test_valid_uniform_score_and_original_bootstrap_are_unchanged(self):
        score = fixture()
        self.assertEqual(metrics.validate_score(score), (79125, 79126, 2442, 2442))
        comparison = scoring.paired_comparison(score, score)
        self.assertEqual(comparison["candidate_minus_reference_nll"], 0.0)
        self.assertEqual(comparison["paired_participant_percentile95"], [0.0, 0.0])
        self.assertEqual(metrics.reconcile_candidate(score, score, comparison, scoring), comparison)

    def test_predecessor_counterexamples_are_accepted_then_rejected(self):
        history = fixture()
        counterexamples = []
        for key, value in (("accuracy", 1.1), ("stop_brier", -0.25),
                           ("trial_balanced_nll", -1.0), ("decision_weighted_nll", -1.0),
                           ("macro_action_recall", 0.9), ("per_action_recall", [1.0] * 4)):
            value_score = deepcopy(history)
            value_score[key] = value
            counterexamples.append(value_score)
        extra = deepcopy(history)
        extra["confusion"][0][0] += 1
        counterexamples.append(extra)
        # This reproduces the old candidate test's impossible terminal support.
        terminal = deepcopy(history)
        terminal["confusion"] = [[40784 if i == j else 0 for j in range(4)] for i in range(4)]
        terminal["confusion"][3][3] -= 1
        derive_confusion_metrics(terminal)
        counterexamples.append(terminal)
        for bad in counterexamples:
            with self.subTest(score=bad):
                comparison = scoring.paired_comparison(bad, history)
                legacy.reconcile_candidate(bad, history, comparison, scoring)
                with self.assertRaises(metrics.ScoreError):
                    metrics.reconcile_candidate(bad, history, comparison, scoring)

    def test_candidate_reference_class_support_must_match(self):
        history, candidate = fixture(), fixture()
        candidate["confusion"][0][0] -= 1
        candidate["confusion"][1][0] += 1
        derive_confusion_metrics(candidate)
        metrics.validate_score(candidate)
        comparison = scoring.paired_comparison(candidate, history)
        legacy.reconcile_candidate(candidate, history, comparison, scoring)
        with self.assertRaisesRegex(metrics.ScoreError, "true-action support"):
            metrics.reconcile_candidate(candidate, history, comparison, scoring)

    def test_both_stopping_recalls_are_derived_not_optional(self):
        score = fixture()
        score["confusion"][2] = [1221, 0, 1221, 0]
        score["confusion"][3] = [0, 1221, 0, 1221]
        derive_confusion_metrics(score)
        metrics.validate_score(score)
        self.assertEqual(score["per_action_recall"][2:], [0.5, 0.5])
        for i in (2, 3):
            bad = deepcopy(score)
            bad["per_action_recall"][i] = 0.0
            with self.assertRaisesRegex(metrics.ScoreError, "recall disagrees"):
                metrics.validate_score(bad)

    def test_missing_actions_are_undefined_not_zero(self):
        score = fixture()
        score["confusion"][3] = [4884, 0, 0, 0]
        score["confusion"][2] = [0, 0, 0, 0]
        derive_confusion_metrics(score)
        metrics.validate_score(score)
        self.assertIsNone(score["per_action_recall"][2])
        score["per_action_recall"][2] = 0.0
        with self.assertRaisesRegex(metrics.ScoreError, "undefined"):
            metrics.validate_score(score)

    def test_full_population_and_explicit_types_are_required(self):
        mutations = [
            ("participants", 19), ("sessions", 79), ("trials", 4883), ("decisions", 163134),
            ("participants", 20.0), ("scientific_count_delta", False),
            ("benchmark_ready", 0), ("accuracy", True),
            ("stop_brier", float("nan")), ("stop_brier", float("inf")),
            ("confusion", [[True, 0, 0, 0]] * 4),
            ("per_action_recall", [1.0, 0.0, 0.0]),
            ("subject_mean_nll", []), ("session_mean_nll", {}),
        ]
        for key, value in mutations:
            with self.subTest(key=key, value=value):
                score = fixture()
                score[key] = value
                with self.assertRaises(metrics.ScoreError):
                    metrics.validate_score(score)

    def test_nested_aggregation_cannot_be_reweighted(self):
        score = fixture()
        score["session_mean_nll"]["20:4"] += 1.0
        with self.assertRaisesRegex(metrics.ScoreError, "four-session"):
            metrics.validate_score(score)
        score["subject_mean_nll"]["20"] = math.fsum(score["session_mean_nll"]["20:" + str(k)] for k in range(1, 5)) / 4
        with self.assertRaisesRegex(metrics.ScoreError, "20-participant"):
            metrics.validate_score(score)
        score["primary_subject_session_mean_nll"] = math.fsum(score["subject_mean_nll"].values()) / 20
        metrics.validate_score(score)

    def test_terminal_support_is_grounded_in_the_existing_consumer(self):
        decisions = []
        for subject in range(1, 21):
            for session in range(1, 5):
                for step in range(2):
                    observation = dict(nL=0, nR=0, nB=0, rL=0, rR=0,
                                       muL=0.5, muR=0.5, gL=True, gR=False,
                                       first_visit=True, after_first_visit=False, t=step)
                    decisions.append(consumer.Decision(
                        len(decisions) + 1, str(subject), session, 1,
                        tuple(observation[key] for key in consumer.FEATURES),
                        1 if step == 0 else (3 if subject % 2 else 4)))
        score = scoring.score_complete(decisions, [(d.source_row, [0.25] * 4) for d in decisions],
                                       expected_decisions=160, expected_trials=80)
        self.assertEqual(sum(score["confusion"][2]) + sum(score["confusion"][3]), score["trials"])
        self.assertEqual(score["per_action_recall"], [1.0, None, 0.0, 0.0])
        with self.assertRaisesRegex(metrics.ScoreError, "complete population"):
            metrics.validate_score(score)
        bad = list(decisions)
        first = bad[0]
        bad[0] = consumer.Decision(first.source_row, first.subject, first.session,
                                   first.trial, first.values, 3)
        with self.assertRaisesRegex(consumer.ContractError, "terminal target chronology"):
            scoring.score_complete(bad, [(d.source_row, [0.25] * 4) for d in bad],
                                   expected_decisions=160, expected_trials=80)

    def test_better_worse_and_heterogeneous_participant_contrasts_are_allowed(self):
        # These are algebraic aggregate controls, not new behavioral observations.
        history = fixture()
        for shift in (-0.125, 0.125):
            candidate = fixture()
            for s in range(1, 21):
                value = history["subject_mean_nll"][str(s)] + shift * s / 20
                candidate["subject_mean_nll"][str(s)] = value
                for k in range(1, 5):
                    candidate["session_mean_nll"][str(s) + ":" + str(k)] = value
            candidate["primary_subject_session_mean_nll"] = math.fsum(candidate["subject_mean_nll"].values()) / 20
            candidate["decision_weighted_nll"] = candidate["primary_subject_session_mean_nll"]
            candidate["trial_balanced_nll"] = candidate["primary_subject_session_mean_nll"]
            comparison = scoring.paired_comparison(candidate, history)
            self.assertEqual(metrics.reconcile_candidate(candidate, history, comparison, scoring), comparison)
            self.assertEqual(comparison["bootstrap_draws"], 10000)
            self.assertEqual(comparison["seed"], 20261114)
            self.assertAlmostEqual(comparison["candidate_minus_reference_nll"], shift * 10.5 / 20)
            forged = deepcopy(comparison)
            forged["candidate_minus_reference_nll"] += 0.01
            with self.assertRaises(metrics.ScoreError):
                metrics.reconcile_candidate(candidate, history, forged, scoring)

    def test_weighted_loss_cannot_exceed_every_session(self):
        score = fixture()
        score["decision_weighted_nll"] += 0.01
        with self.assertRaisesRegex(metrics.ScoreError, "session NLL range"):
            metrics.validate_score(score)

    def test_invalid_reference_is_not_used_as_schema_authority(self):
        history = fixture()
        history["stop_brier"] = -0.1
        candidate = fixture()
        with self.assertRaises(metrics.ScoreError):
            metrics.reconcile_candidate(candidate, history, {}, scoring)


if __name__ == "__main__":
    unittest.main(verbosity=2)
