"""Small generated controls; no authentic recordings or scientific qualification."""
import copy
import importlib.util
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


old = load("predecessor_tests", HERE.parent / "frozen-grid-evaluator" / "test_evaluator.py")
ev = load("protected_evaluator", HERE / "evaluator.py")


def fixture():
    design, predictions, targets = old.fixture()
    design["schema"] = "poyo_protected_grid_v2"
    return design, predictions, targets


def run(module, design, predictions, targets, calls):
    body = old.encode(design)
    return module.evaluate(body, old.pin(body), old.encode(predictions),
                           lambda: calls.append("target-read") or old.encode(targets))


def predecessor(design, predictions, targets):
    previous = copy.deepcopy(design)
    previous["schema"] = "poyo_frozen_grid_v1"
    return run(old.ev, previous, predictions, targets, [])


class ProtectionTests(unittest.TestCase):
    def public_refusal(self, design, predictions, targets, message):
        # Establish the actual counterexample, rather than only asserting refusal.
        self.assertEqual(len(predecessor(design, predictions, targets)["results"]), 16)
        calls = []
        with self.assertRaisesRegex(ValueError, message):
            run(ev, design, predictions, targets, calls)
        self.assertEqual(calls, [])

    def test_valid_grid_preserves_all_numerical_results(self):
        d, p, t = fixture()
        calls = []
        result = run(ev, d, p, t, calls)
        previous = predecessor(d, p, t)
        self.assertEqual(calls, ["target-read"])
        self.assertEqual(result.pop("support_policy"), ev.PROTECTION)
        self.assertEqual(result.pop("schema"), "poyo_protected_grid_scores_v2")
        previous.pop("schema")
        self.assertEqual(result, previous)

    def test_test_trial_cannot_be_adaptation_in_another_budget(self):
        d, p, t = fixture()
        case = d["cases"][2]
        case["adaptation_trials"][0] = "test"
        for row in case["rows"]:
            row["trial_id"] = "other-test"
            row["timestamp"] += 100
        self.public_refusal(d, p, t, "cross-budget adaptation")

    def test_test_trial_cannot_be_development_in_another_budget(self):
        d, p, t = fixture()
        case = d["cases"][2]
        case["development_trials"] = ["test"]
        for row in case["rows"]:
            row["trial_id"] = "other-test"
            row["timestamp"] += 100
        self.public_refusal(d, p, t, "cross-budget adaptation")

    def test_relabeling_same_clock_as_another_trial_is_refused(self):
        d, p, t = fixture()
        for row in d["cases"][2]["rows"]:
            row["trial_id"] = "other-test"
        self.public_refusal(d, p, t, "conflicting trial identities")
        d, p, t = fixture()
        d["cases"][0]["rows"][2]["trial_id"] = "other-test"
        self.public_refusal(d, p, t, "conflicting trial identities")

    def test_changed_target_across_budgets_is_refused_after_one_read(self):
        d, p, t = fixture()
        t["cases"][2]["rows"][0]["values"][0] += 1
        self.assertEqual(len(predecessor(d, p, t)["results"]), 16)
        calls = []
        with self.assertRaisesRegex(ValueError, "stitched target mismatch"):
            run(ev, d, p, t, calls)
        self.assertEqual(calls, ["target-read"])

    def test_target_consistency_uses_pooled_values_not_window_order(self):
        d, p, t = fixture()
        # Same physical target after pooling, represented by different occurrences.
        t["cases"][2]["rows"][1]["values"] = [-2, -20]
        t["cases"][2]["rows"][2]["values"] = [2, 20]
        result = run(ev, d, p, t, [])
        self.assertEqual(result["results"], predecessor(d, p, t)["results"])

    def test_session_scope_and_large_integer_clock_remain_exact(self):
        d, p, t = fixture()
        # Identical local clocks/trial names across animals are expected, not aliases.
        for case in d["cases"]:
            for row in case["rows"]:
                row["timestamp"] += 2**60
        # A different target in another session must remain admissible.
        for case in t["cases"]:
            if case["session_id"] == "s157":
                for row in case["rows"]:
                    row["values"][0] += 10
        result = run(ev, d, p, t, [])
        self.assertEqual(result["results"][0]["stitched_samples"], 3)
        self.assertEqual(result["results"], predecessor(d, p, t)["results"])

    def test_all_public_predictions_are_checked_before_targets(self):
        d, p, t = fixture()
        p["results"][-1]["rows"][-1]["values"] = [True, 0]
        calls = []
        with self.assertRaisesRegex(ValueError, "numeric type"):
            run(ev, d, p, t, calls)
        self.assertEqual(calls, [])

    def test_versioned_design_does_not_silently_relabel_legacy_input(self):
        d, p, t = old.fixture()
        calls = []
        with self.assertRaisesRegex(ValueError, "design task/schema"):
            run(ev, d, p, t, calls)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
