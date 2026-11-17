"""Full-cohort generated controls for the retained NEURAL-083 scorers.

Standard library only. No authentic data, acquisition, model fit, or solver call.
Run this file through the shared bounded test pool during the parallel build.
"""
import hashlib
import math
from pathlib import Path
import sys
import types
import unittest


ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ("target20", "transfer0", "target100", "other_session20")
ARMS = ("EEG", "CONTEXT", "PERMUTED_EEG")
GENERATION = "a" * 64


def load_source(relative, name, pin):
    path = ROOT / relative
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != pin:
        raise AssertionError("Selected predecessor source changed: " + relative)
    module = types.ModuleType(name)
    module.__file__ = str(path)
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


def load_scorers():
    """Restore legacy import state; all numerical operands are invented below."""
    old_path = sys.path[:]
    sentinel = object()
    previous = sys.modules.get("protocol", sentinel)
    try:
        protocol = load_source(
            "case-adaptive/bindings/scoring_sources/protocol.py", "protocol",
            "90898be76b4193e7b26e2765b2ab80b040bb519c91245ac09c252e92e4de7699")
        sys.modules["protocol"] = protocol
        scorer = load_source(
            "case-adaptive/bindings/scoring_sources/scorer_core.py", "scorer_controls",
            "31a37f8df65dd0d760cf42cb7575914b97a5ec7207354822e789107e00ca7483")
        if scorer.p is not protocol:
            raise AssertionError("Scorer did not use captured protocol")
        paired = load_source(
            "case-adaptive/successor/paired_report.py", "paired_controls",
            "e3482c46fe9ac274e7725d79bd5df0498bbf6f244f6320251f874be2d06612d0")
        return scorer, paired
    finally:
        sys.path[:] = old_path
        if previous is sentinel:
            sys.modules.pop("protocol", None)
        else:
            sys.modules["protocol"] = previous


def token(kind, number):
    return kind + "_" + format(number, "024x")


def fixture(correct=None, probability=None):
    """Exactly 54 people, two sessions, 100 queries, and 12 conditions each.

    ``correct`` declares how many of EACH class receive the correct side of
    0.5. The rest receive the wrong side; probabilities are 0.8 or 0.2. Thus
    expected balanced accuracy is known by construction, independently of
    the scorer's metric calculation. This is not a scientific observation.
    """
    panel = dict(schema="neural083_panel_v1", generation=GENERATION,
                 settings=list(SETTINGS), arms=list(ARMS), cases=[])
    truth = dict(schema="neural083_targets_v1", generation=GENERATION, cases=[])
    submission = dict(schema="neural083_predictions_v1", generation=GENERATION, outcomes=[])
    for person in range(54):
        for session in (1, 2):
            ordinal = 2 * person + session - 1
            case = token("case", ordinal)
            queries = [token("trial", ordinal * 100 + i) for i in range(100)]
            panel["cases"].append(dict(case=case, person=token("person", person),
                                        session=session, query=queries))
            truth["cases"].append(dict(case=case, labels=[0] * 50 + [1] * 50))
            for si, setting in enumerate(SETTINGS):
                for ai, arm in enumerate(ARMS):
                    k = correct(person, session, si, ai) if correct else 0
                    rows = []
                    for i, trial in enumerate(queries):
                        value = (0.2 if i < 50 else 0.8)
                        if i % 50 >= k:
                            value = 1.0 - value
                        if probability is not None:
                            value = probability(i)
                        rows.append(dict(trial=trial, p_right=value))
                    submission["outcomes"].append(dict(
                        schema="neural083_case_prediction_v1", generation=GENERATION,
                        case=case, setting=setting, arm=arm, status="complete", predictions=rows))
    return panel, truth, submission


class TargetCounter:
    def __init__(self, truth):
        self.truth, self.calls = truth, 0

    def __call__(self):
        self.calls += 1
        return self.truth


def change_outcome(submission, index, **updates):
    changed = dict(submission, outcomes=list(submission["outcomes"]))
    changed["outcomes"][index] = dict(changed["outcomes"][index], **updates)
    return changed


class ScientificScoringControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scorer, cls.paired = load_scorers()
        cls.panel, cls.truth, cls.submission = fixture(
            correct=lambda person, session, setting, arm: (person + 7 * session + 5 * setting + 11 * arm) % 51)

    def test_all_person_session_metrics_and_five_paired_contrasts(self):
        loader = TargetCounter(self.truth)
        result = self.scorer.score(self.panel, self.submission, loader)
        self.assertEqual((loader.calls, result["private_callbacks"], result["biological_n"]), (1, 1, 54))
        expected = {}
        for si, setting in enumerate(SETTINGS):
            for ai, arm in enumerate(ARMS):
                key = setting + "/" + arm
                # Independent, closed-form expectations from per-class counts.
                accuracy = [sum((person + 7 * session + 5 * si + 11 * ai) % 51
                                for session in (1, 2)) / 100 for person in range(54)]
                expected[key] = accuracy
                for person, row in enumerate(result["per_person"][key]):
                    self.assertEqual(row["person"], token("person", person))
                    self.assertAlmostEqual(row["balanced_accuracy"], accuracy[person], places=13)
                    loss = -accuracy[person] * math.log(0.8) - (1 - accuracy[person]) * math.log(0.2)
                    self.assertAlmostEqual(row["log_loss"], loss, places=13)
                self.assertAlmostEqual(result["macro"][key]["balanced_accuracy"], sum(accuracy) / 54, places=13)
        self.assertAlmostEqual(result["primary_score"], sum(expected["target20/EEG"]) / 54, places=13)
        contrasts = (
            ("eeg_minus_context", "target20/EEG", "target20/CONTEXT"),
            ("eeg_minus_permuted", "target20/EEG", "target20/PERMUTED_EEG"),
            ("calibration20_minus_zero", "target20/EEG", "transfer0/EEG"),
            ("calibration100_minus20", "target100/EEG", "target20/EEG"),
            ("same_minus_other_session20", "target20/EEG", "other_session20/EEG"))
        for name, active, control in contrasts:
            differences = [a - b for a, b in zip(expected[active], expected[control])]
            actual = result["paired_balanced_accuracy_differences"][name]
            mean = sum(differences) / 54
            se = math.sqrt(sum((value - mean) ** 2 for value in differences) / (53 * 54))
            self.assertAlmostEqual(actual["mean"], mean, places=13)
            self.assertAlmostEqual(actual["descriptive_se"], se, places=13)
            for got, wanted in zip(actual["per_person"], differences):
                self.assertAlmostEqual(got, wanted, places=13)

    def test_probability_threshold_and_log_loss_floor(self):
        for probability, accuracy, loss in (
                (lambda i: 0.5, 0.5, math.log(2)),
                # All-0.5 on balanced classes cannot distinguish >= from >.
                # Left below threshold and right exactly on it must be perfect.
                (lambda i: 0.2 if i < 50 else 0.5, 1.0,
                 -(math.log(0.8) + math.log(0.5)) / 2),
                (lambda i: int(i >= 50), 1.0, 0.0),
                (lambda i: int(i < 50), 0.0, -math.log(1e-15))):
            panel, truth, submission = fixture(probability=probability)
            result = self.scorer.score(panel, submission, lambda: truth)
            self.assertEqual(result["primary_score"], accuracy)
            self.assertAlmostEqual(result["macro"]["target20/EEG"]["log_loss"], loss, places=12)

    def test_case_and_outcome_order_do_not_change_identity_join(self):
        # Query order is fixed, but whole-case/outcome ordering is immaterial.
        panel = dict(self.panel, cases=list(reversed(self.panel["cases"])))
        truth = dict(self.truth, cases=list(reversed(self.truth["cases"])))
        submission = dict(self.submission, outcomes=list(reversed(self.submission["outcomes"])))
        first = self.scorer.score(self.panel, self.submission, lambda: self.truth)
        second = self.scorer.score(panel, submission, lambda: truth)
        self.assertEqual(first, second)

    def test_malformed_outputs_never_open_targets(self):
        variants = [
            dict(self.submission, generation="b" * 64),
            dict(self.submission, outcomes=self.submission["outcomes"][:-1]),
            dict(self.submission, outcomes=self.submission["outcomes"][:-1] + [self.submission["outcomes"][0]])]
        for value in (True, float("nan"), float("inf"), -0.1, 1.1):
            rows = list(self.submission["outcomes"][-1]["predictions"])
            rows[-1] = dict(rows[-1], p_right=value)
            variants.append(change_outcome(self.submission, -1, predictions=rows))
        rows = list(reversed(self.submission["outcomes"][-1]["predictions"]))
        variants.append(change_outcome(self.submission, -1, predictions=rows))
        for variant in variants:
            loader = TargetCounter(self.truth)
            with self.assertRaises(ValueError):
                self.scorer.score(self.panel, variant, loader)
            self.assertEqual(loader.calls, 0)

    def abstaining(self):
        submission = change_outcome(self.submission, 0, status="abstain", reason="generated numerical failure")
        del submission["outcomes"][0]["predictions"]
        return submission

    def test_abstention_keeps_entire_panel_unscored(self):
        loader = TargetCounter(self.truth)
        result = self.scorer.score(self.panel, self.abstaining(), loader)
        self.assertEqual((result["status"], result["primary_score"], loader.calls), ("abstained", None, 0))
        invalid = change_outcome(self.abstaining(), -1, predictions=[])
        with self.assertRaises(ValueError):
            self.scorer.score(self.panel, invalid, loader)
        self.assertEqual(loader.calls, 0)

    def test_wrong_protected_join_or_class_support_fails(self):
        for field, value in (("case", token("case", 999)), ("labels", [0] * 49 + [1] * 51)):
            truth = dict(self.truth, cases=list(self.truth["cases"]))
            truth["cases"][0] = dict(truth["cases"][0], **{field: value})
            loader = TargetCounter(truth)
            with self.assertRaises(ValueError):
                self.scorer.score(self.panel, self.submission, loader)
            self.assertEqual(loader.calls, 1)

    def test_three_panel_paired_metric_direction_and_person_join(self):
        _, _, frozen = fixture(correct=lambda p, s, setting, arm: 30)
        _, _, adaptive = fixture(correct=lambda p, s, setting, arm: 40 if arm == 0 else 35)
        _, _, reference = fixture(correct=lambda p, s, setting, arm: 20)
        loader = TargetCounter(self.truth)
        result = self.paired.compare(self.panel, dict(frozen_program=frozen, case_adaptive=adaptive,
                                     reference=reference), loader, self.scorer, external_admission=True)
        self.assertEqual(loader.calls, 1)
        for setting in SETTINGS:
            self.assertAlmostEqual(result["mode_advantage"][setting + "/EEG"]["balanced_accuracy_mean"], 0.2)
            self.assertAlmostEqual(result["mode_advantage"][setting + "/EEG"]["log_loss_improvement_mean"], 0.2 * math.log(4))
            self.assertAlmostEqual(result["mode_by_representation"][setting]["balanced_accuracy_mean"], 0.1)
        self.assertIs(result["scientific_qualified"], False)
        self.assertIs(result["population_inference"], False)

    def test_all_three_panels_admitted_even_when_first_abstains(self):
        bundles = dict(frozen_program=self.abstaining(), case_adaptive=self.submission,
                       reference=change_outcome(self.submission, -1, predictions=[]))
        loader = TargetCounter(self.truth)
        with self.assertRaises(ValueError):
            self.paired.compare(self.panel, bundles, loader, self.scorer, external_admission=True)
        self.assertEqual(loader.calls, 0)
        bundles["reference"] = self.submission
        result = self.paired.compare(self.panel, bundles, loader, self.scorer, external_admission=True)
        self.assertEqual((result["status"], loader.calls), ("abstained", 0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
