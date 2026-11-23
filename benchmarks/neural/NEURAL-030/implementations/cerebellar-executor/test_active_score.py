"""Generated full-panel controls for captured stable count-scoring adoption.

No candidate process, authentic observation, or protected target is used.
"""
import copy
from decimal import Decimal, localcontext
import importlib.util
import math
from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parent


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def panel(value=0, prediction=0.0, reference=0.0):
    """Invented complete 5/5/6 sessions, four arms and five declared mice."""
    plan = {"schema": "neural030_candidate_plan_v1", "task_id": "NEURAL-030",
            "availability": "full_planned_window_retrospective", "cases": []}
    labels, fixed = [], []
    outputs = {arm: [] for arm in ("context_handle", "grc", "cf", "joint")}
    binding = {"verification_status": "operator_attested", "binding_id": "generated-only",
               "evidence_sha256": "0" * 64, "session_to_mouse": {}}
    sid_number = 0
    for condition, delay, sessions in (("one_second_expert", 1.0, 5),
                                       ("two_second_novice", 2.0, 5),
                                       ("two_second_expert", 2.0, 6)):
        for _ in range(sessions):
            sid_number += 1
            sid, count = f"{sid_number:032x}", int(delay * 10)
            required, predicted = [], []
            for trial_index in (1, 2):
                tid = f"{1000 + 2 * sid_number + trial_index:032x}"
                required.append({"trial_id": tid, "bin_count": count})
                labels.append({"trial_id": tid, "session_id": sid,
                               "bin_count": count, "counts": [value] * count})
                predicted.append({"trial_id": tid, "counts": [prediction] * count})
                fixed.append({"trial_id": tid, "counts": [reference] * count})
            plan["cases"].append({"session_id": sid, "condition": condition,
                                  "delay_s": delay, "required_predictions": required})
            binding["session_to_mouse"][sid] = f"{200 + (sid_number - 1) % 5:032x}"
            for arm in outputs:
                outputs[arm].append({"schema": "neural030_prediction_v1",
                                     "task_id": "NEURAL-030", "session_id": sid,
                                     "arm": arm, "predictions": copy.deepcopy(predicted)})
    return plan, labels, outputs, fixed, binding


def evaluate(contract, values):
    plan, labels, outputs, fixed, binding = values
    return contract.score_matched_panel(plan, labels, outputs,
                                       fixed_reference_predictions=fixed,
                                       mouse_binding=binding)


class ActiveCountScoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entry = load(HERE / "entry.py", "_active_count_entry")
        cls.context = cls.entry.context()
        cls.contract = cls.context.module("candidate_contract")
        cls.legacy = load(HERE.parent / "registered-runtime" / "score.py", "_legacy_count_score")

    @classmethod
    def tearDownClass(cls):
        cls.context.close()

    def test_active_panel_keeps_near_exact_positive_deviance(self):
        target, prediction = 10, 10.0 + 2.0 ** -26
        values = panel(target, prediction, target)
        result = evaluate(self.contract, values)
        with localcontext() as context:
            context.prec = 90
            y, mu = Decimal(target), Decimal.from_float(prediction)
            oracle = float(2 * (mu - y + y * (y.ln() - mu.ln())))
        old = self.legacy.score_predictions(values[1],
                    [row for response in values[2]["joint"] for row in response["predictions"]])
        self.assertGreater(abs(old["trial_results"][0]["poisson_deviance"] - oracle), oracle * .01)
        for arm in values[2]:
            current = result["fixed_reference_comparisons"][arm]
            self.assertEqual(len(current["trial_results"]), 32)
            self.assertEqual(len(current["session_results"]), 16)
            self.assertEqual(len(current["mouse_results"]), 5)
            observed = current["mouse_macro"]["poisson_deviance"]
            self.assertGreater(observed, 0)
            self.assertLessEqual(abs(observed - oracle), oracle * 5e-15)
            self.assertEqual(current["mouse_macro"]["mse_gain"], -(2.0 ** -52))
        self.assertFalse(result["scientific_qualification"])

    def test_active_panel_refuses_unrepresentable_candidate_and_reference(self):
        for candidate, reference in ((1e-200, 0.0), (0.0, 1e-200)):
            with self.subTest(candidate=candidate, reference=reference):
                with self.assertRaisesRegex(ValueError, "nonzero MSE.*representability"):
                    evaluate(self.contract, panel(0, candidate, reference))

    def test_active_panel_preserves_subnormal_hierarchy(self):
        result = evaluate(self.contract, panel(0, 2.0 ** -537, 0.0))
        minimum = math.ldexp(1.0, -1074)
        for arm_result in result["fixed_reference_comparisons"].values():
            for level in ("trial_results", "session_results", "mouse_results"):
                self.assertTrue(all(row["mse"] == minimum for row in arm_result[level]))
            self.assertEqual(arm_result["mouse_macro"]["mse"], minimum)
            self.assertEqual(arm_result["mouse_macro"]["mse_gain"], -minimum)

    def test_original_ordinary_losses_and_mouse_hierarchy_are_preserved(self):
        values = panel(0, 0.0, 5.0)
        plan, labels, outputs, fixed, binding = values
        # Trial means (1 + 9)/2=5 for one session, then sessions 2,3,4.
        # The first mouse owns four sessions; every other mouse owns three.
        # Each mouse's squared-error means are computed independently below.
        expected_mice = [[] for _ in range(5)]
        for index, case in enumerate(plan["cases"]):
            first, second = (1.0, 3.0) if index == 0 else (float(index % 4),) * 2
            expected_mice[index % 5].append((first ** 2 + second ** 2) / 2)
            for arm in outputs:
                outputs[arm][index]["predictions"][0]["counts"] = [first] * case["required_predictions"][0]["bin_count"]
                outputs[arm][index]["predictions"][1]["counts"] = [second] * case["required_predictions"][1]["bin_count"]
        result = evaluate(self.contract, values)
        expected = sum(sum(rows) / len(rows) for rows in expected_mice) / 5
        for arm, report in result["fixed_reference_comparisons"].items():
            self.assertAlmostEqual(report["mouse_macro"]["mse"], expected)
            old = self.legacy.score_predictions(labels,
                    [row for response in outputs[arm] for row in response["predictions"]],
                    baseline_predictions=fixed, mouse_binding=binding)
            for key in ("mse", "mse_gain", "poisson_deviance", "poisson_deviance_gain"):
                self.assertAlmostEqual(report["mouse_macro"][key], old["mouse_macro"][key])

    def test_active_panel_retains_complete_support_and_count_refusals(self):
        values = panel()
        values[2]["joint"].pop()
        with self.assertRaisesRegex(ValueError, "complete response panel"):
            evaluate(self.contract, values)
        values = panel()
        values[2]["joint"][0]["predictions"][0]["counts"][0] = True
        with self.assertRaisesRegex(ValueError, "numbers, not booleans"):
            evaluate(self.contract, values)


if __name__ == "__main__":
    unittest.main(verbosity=2)
