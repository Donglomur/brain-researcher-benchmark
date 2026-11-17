"""Generated report controls only; no authentic data or PAC computation."""
import copy
import importlib.util
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
PROGRAM = HERE.parent / "programme-source" / "implementation-v1" / "program"
sys.path.insert(0, str(PROGRAM))
spec = importlib.util.spec_from_file_location("neural042_comparison_v2", HERE / "comparison.py")
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)
from contracts import CLAIM, CONTRASTS, DESIGNS, METRICS, report
from core import Refusal
import grade as predecessor


ROSTER = [f"{i:024x}" for i in range(36)]


def generated_report(support=None):
    """Four report axes, with independently specified supported person counts."""
    support = [36] * 4 if support is None else support
    rows = []
    for i, person in enumerate(ROSTER):
        for j, (design, contrast) in enumerate((d, c) for d in DESIGNS for c in CONTRASTS):
            supported = i < support[j]
            rows.append({"patient": person, "design": design, "contrast": contrast,
                         "n_sessions": int(supported), "n_channels": int(supported),
                         "metrics": dict.fromkeys(METRICS, 0.0) if supported else None})
    groups = []
    for j, (design, contrast) in enumerate((d, c) for d in DESIGNS for c in CONTRASTS):
        n = support[j]
        groups.append({"design": design, "contrast": contrast, "n_patients": n,
                       "mean": 0.0 if n >= 2 else None,
                       "ci95": [0.0, 0.0] if n >= 2 else None,
                       "sign_flip_p": 1.0 if n >= 2 else None})
    return {"schema": "neural042_report_v1", "claim_scope": CLAIM,
            "patients": rows, "groups": groups}


def refresh_means(value):
    for j, group in enumerate(value["groups"]):
        supported = [r["metrics"]["corrected_mi"] for r in value["patients"][j::4]
                     if r["metrics"] is not None]
        group["n_patients"] = len(supported)
        group["mean"] = sum(supported) / len(supported) if len(supported) >= 2 else None
        if len(supported) < 2:
            group["ci95"] = group["sign_flip_p"] = None


class ReconstructionTests(unittest.TestCase):
    def test_counterexample_missing_group_comparison(self):
        target = generated_report()
        candidate = copy.deepcopy(target)
        candidate["groups"][2]["ci95"] = [-0.75, 0.5]
        candidate["groups"][2]["sign_flip_p"] = 0.001
        report(candidate, ROSTER)  # This is an admissible predecessor report.
        old = predecessor.compare(candidate, target)
        self.assertEqual(old["primary_equal_endpoint_mae"], 0.0)
        self.assertNotIn("groups", old)
        new = comparison.compare(candidate, target)
        self.assertEqual(new["primary_equal_endpoint_mae"], 0.0)
        self.assertFalse(new["full_numerical_agreement"])
        self.assertEqual(new["groups"][2]["absolute_error"]["ci95"], [0.75, 0.5])
        self.assertAlmostEqual(new["groups"][2]["absolute_error"]["sign_flip_p"], 0.999)

    def test_identical_full_report(self):
        target = generated_report()
        result = comparison.compare(target, copy.deepcopy(target))
        self.assertTrue(result["full_numerical_agreement"])
        self.assertTrue(comparison.reference_agreement(target, target))
        self.assertEqual(len(result["groups"]), 4)
        self.assertEqual(result["metric_units"]["gamma_power"], "volts_squared")
        self.assertEqual(result["metric_units"]["firing_rate"], "hertz")
        self.assertIsNone(result["neural_gain_scalar"])

    def test_equal_endpoint_weighting_not_pooled_people(self):
        target = generated_report([36, 36, 1, 3])
        candidate = copy.deepcopy(target)
        candidate["patients"][2]["metrics"]["corrected_mi"] = 0.2
        for i in range(3):
            candidate["patients"][4 * i + 3]["metrics"]["corrected_mi"] = 0.6
        refresh_means(candidate)
        result = comparison.compare(candidate, target)
        self.assertAlmostEqual(result["primary_equal_endpoint_mae"], 0.4)
        self.assertNotAlmostEqual(result["primary_equal_endpoint_mae"], 0.5)
        self.assertAlmostEqual(result["primary_equal_endpoint_mae"],
                               predecessor.compare(candidate, target)["primary_equal_endpoint_mae"])

    def test_support_mismatch_nulls_endpoint_and_group_errors(self):
        target = generated_report()
        candidate = copy.deepcopy(target)
        candidate["patients"][2]["n_channels"] = 2
        result = comparison.compare(candidate, target)
        self.assertIsNone(result["primary_equal_endpoint_mae"])
        self.assertEqual(result["groups"][2]["status"], "support_mismatch")
        self.assertIsNone(result["groups"][2]["absolute_error"]["sign_flip_p"])
        self.assertFalse(result["full_numerical_agreement"])

    def test_same_group_count_different_people_is_mismatch(self):
        target = generated_report([2, 2, 2, 2])
        candidate = copy.deepcopy(target)
        candidate["patients"][2].update(n_sessions=0, n_channels=0, metrics=None)
        candidate["patients"][10].update(n_sessions=1, n_channels=1, metrics=dict.fromkeys(METRICS, 0.0))
        result = comparison.compare(candidate, target)
        self.assertEqual(result["groups"][2]["target_supported_people"], 2)
        self.assertEqual(result["groups"][2]["status"], "support_mismatch")

    def test_all_unsupported_is_agreement_without_a_primary(self):
        target = generated_report([0, 0, 0, 0])
        result = comparison.compare(target, target)
        self.assertTrue(result["full_numerical_agreement"])
        self.assertIsNone(result["primary_equal_endpoint_mae"])
        self.assertTrue(all(g["status"] == "insufficient_group_support" for g in result["groups"]))
        self.assertTrue(all(g["absolute_error"]["mean"] is None for g in result["groups"]))

    def test_single_patient_has_primary_but_no_group_statistic(self):
        target = generated_report([1, 1, 1, 1])
        result = comparison.compare(target, target)
        self.assertEqual(result["primary_equal_endpoint_mae"], 0.0)
        self.assertTrue(result["full_numerical_agreement"])
        self.assertIsNone(result["groups"][3]["absolute_error"]["mean"])

    def test_secondary_patient_metric_is_part_of_full_agreement(self):
        target = generated_report()
        for metric in METRICS:
            with self.subTest(metric=metric):
                candidate = copy.deepcopy(target)
                candidate["patients"][0]["metrics"][metric] = 0.2
                refresh_means(candidate)
                result = comparison.compare(candidate, target)
                self.assertFalse(result["full_numerical_agreement"])
                self.assertEqual(result["primary_equal_endpoint_mae"], 0.0)

    def test_each_group_statistic_and_all_axes_are_compared(self):
        target = generated_report()
        for j in range(4):
            for field in ("ci95", "sign_flip_p"):
                with self.subTest(axis=j, field=field):
                    candidate = copy.deepcopy(target)
                    candidate["groups"][j][field] = [-0.1, 0.1] if field == "ci95" else 0.5
                    self.assertFalse(comparison.compare(candidate, target)["full_numerical_agreement"])
                    with self.assertRaises(Refusal):
                        comparison.reference_agreement(candidate, target)

    def test_group_tolerance_is_absolute(self):
        target = generated_report()
        candidate = copy.deepcopy(target)
        candidate["groups"][0]["ci95"] = [-0.9e-10, 0.9e-10]
        self.assertTrue(comparison.compare(candidate, target)["full_numerical_agreement"])
        candidate["groups"][0]["ci95"] = [-1.1e-10, 1.1e-10]
        self.assertFalse(comparison.compare(candidate, target)["full_numerical_agreement"])

    def test_malformed_reports_rejected_before_scoring(self):
        target = generated_report()
        mutations = [lambda r: r["patients"].pop(),
                     lambda r: r["patients"].reverse(),
                     lambda r: r["patients"][0].update(patient="f" * 24),
                     lambda r: r["patients"][0]["metrics"].update(mi=True),
                     lambda r: r["patients"][0]["metrics"].update(mi=float("nan")),
                     lambda r: r["groups"].pop(),
                     lambda r: r["groups"][0].update(ci95=[0.5, -0.5]),
                     lambda r: r["groups"][0].update(mean=0.2),
                     lambda r: r["groups"][0].update(sign_flip_p=1.1)]
        for mutate in mutations:
            with self.subTest(mutation=mutations.index(mutate)):
                candidate = copy.deepcopy(target)
                mutate(candidate)
                with self.assertRaises(Refusal):
                    comparison.compare(candidate, target)
                with self.assertRaises(Refusal):
                    comparison.compare(target, candidate)


if __name__ == "__main__":
    unittest.main()
