"""Invented full-panel summary joins; no probability arrays or authentic inputs."""
import copy
import importlib.util
import math
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("probability_diagnostics_join", Path(__file__).with_name("probability_diagnostics_join.py"))
j = importlib.util.module_from_spec(spec)
spec.loader.exec_module(j)


def diagnostics_for(grade, support):
    """Analytic summaries for invented fixed-confidence argmax predictions.

    For every confusion-cell count, its predicted class receives s+(1-s)/5;
    others receive (1-s)/5. No epoch probability arrays are constructed.
    """
    roster = {r["person"]: r for r in support["people"]}
    panels = {}
    for index, (key, panel) in enumerate(grade["panels"].items()):
        people = {}
        for number, (person, metrics) in enumerate(panel["people"].items()):
            matrix = metrics["confusion"]
            truth = [sum(row) for row in matrix]
            eligible = sum(truth)
            s = .55 + .01 * (number % 5) + .002 * (index % 3)
            u = (1 - s) / 5
            correct = sum(matrix[k][k] for k in range(5)) / eligible
            predicted_counts = [sum(row[k] for row in matrix) for k in range(5)]
            predicted = [s * n / eligible + u for n in predicted_counts]
            observed = [n / eligible for n in truth]
            n = roster[person]["nights"]
            counts = [eligible] if n == 1 else [eligible // 3, eligible - eligible // 3]
            nights = {str(i + 1): {"clock": c + 1, "eligible": c, "masked": 1} for i, c in enumerate(counts)}
            people[person] = {
                "schema": "sleep_probability_diagnostics_person_v1", "classes": list(j.CLASSES),
                "clock_epochs": eligible + n, "eligible_epochs": eligible, "masked_epochs": n,
                "nights": nights, "truth_counts": truth,
                "mean_multiclass_brier": s * s + 2 * s * u + 5 * u * u - 2 * (u + s * correct) + 1,
                "mean_clipped_log_loss_nats": -correct * math.log(s + u) - (1 - correct) * math.log(u),
                "log_loss_floor": 1e-15, "log_loss_clipped_epochs": 0,
                "mean_predicted_probability": predicted, "observed_class_frequency": observed,
                "calibration_in_large_predicted_minus_observed": [p - f for p, f in zip(predicted, observed)], "defined": True}
        panels[key] = {"schema": "sleep_probability_diagnostics_panel_v1", "people": people,
            "required_people": 78, "undefined_people": [],
            "person_macro_brier": math.fsum(v["mean_multiclass_brier"] for v in people.values()) / 78,
            "person_macro_clipped_log_loss_nats": math.fsum(v["mean_clipped_log_loss_nats"] for v in people.values()) / 78,
            "person_macro_calibration_in_large_predicted_minus_observed": [math.fsum(v["calibration_in_large_predicted_minus_observed"][k] for v in people.values()) / 78 for k in range(5)],
            "aggregation": "eligible epochs pooled within person; equal people", "log_loss_floor": 1e-15,
            "interval": None, "p_value": None,
            "interpretation": "Prediction quality and marginal calibration diagnostics; no full calibration or inference guarantee"}
    return {"schema": "neural007_full153_probability_diagnostics_v1", "predictions": dict(grade["predictions"]),
            "people": 78, "nights": 153, "classes": list(j.CLASSES), "panels": panels}


def fixture():
    support = {"schema": "sleep_full153_support_v1", "people": [
        {"person": str(900000 + i), "fold": i // 13 + 1, "nights": 1 if i in (0, 13, 26) else 2} for i in range(78)]}
    profile = "generic_current_person"
    panels = {}
    for key in sorted(j.expected_panels(profile)):
        people = {}
        for i, row in enumerate(support["people"]):
            truth = [(i % 3 + 2) * row["nights"], 2, 4, 3, 1]
            matrix = [[truth[a] if a == b else 0 for b in range(5)] for a in range(5)]
            people[row["person"]] = {"confusion": matrix, "support": truth, "eligible_epochs": sum(truth),
                "class_f1": [1.] * 5, "class_recall": [1.] * 5, "fixed_five_macro_f1": 1., "supported_balanced_accuracy": 1.}
        panels[key] = {"primary": 1., "people": people, "independent_people": 78,
                       "metric": "equal_person_fixed_five_class_macro_f1"}
    grade = {"schema": "neural007_full153_grade_v1", "people": 78, "nights": 153, "independent_tasks": 1,
             "predictions": {"bytes": 123, "sha256": "b" * 64}, "panels": panels, "contrasts": {},
             "raw_native_LLM_understanding_tested": False, "scientific_content_admitted": False,
             "research_qualified": False, "submission_ready": False}
    # Only fields consumed by this post-admission join are needed by this invented
    # object. Separate composition checks use the actual accepted base assessor.
    report = {"schema": "sleep_scientific_comparison_v1", "status": "complete_descriptive_comparison",
              "source_grade_schema": grade["schema"], "prediction_panel": dict(grade["predictions"]),
              "all_27_absolute_panels": copy.deepcopy(panels), "support": support, "frozen_profile": profile,
              "scope": {"people": 78, "nights": 153, "folds": 6, "scored_panels": 27,
                        "candidate_inferences_required_upstream": 936, "reference_inferences_required_upstream": 1170, "new_assignments": 0},
              "calibration": {"status": "not_inferable_from_confusion_counts", "diagnostics": None},
              "internal_LLM_understanding_established": False, "causal_effect_established": False,
              "full_contract_complete": False, "research_qualified": False, "submission_ready": False}
    return grade, report, diagnostics_for(grade, support)


def first_person(diagnostics):
    return next(iter(next(iter(diagnostics["panels"].values()))["people"].values()))


class JoinTests(unittest.TestCase):
    def test_descriptor_types_cannot_exploit_bool_integer_equality(self):
        for side in ("diagnostics", "report"):
            grade, report, diagnostics = fixture()
            grade["predictions"]["bytes"] = 1
            report["prediction_panel"]["bytes"] = 1
            diagnostics["predictions"]["bytes"] = 1
            target = diagnostics["predictions"] if side == "diagnostics" else report["prediction_panel"]
            for value in (True, 1.0):
                target["bytes"] = value
                with self.assertRaises(ValueError):
                    j.join_probability_diagnostics(grade, report, diagnostics)

    def test_complete_join_is_detached_without_qualification(self):
        args = fixture(); original = copy.deepcopy(args)
        result = j.join_probability_diagnostics(*args)
        self.assertEqual(args, original)
        self.assertEqual(len(result["calibration"]["diagnostics"]["panels"]), 27)
        self.assertFalse(result["research_qualified"])
        self.assertFalse(result["calibration"]["raw_probability_metrics_authenticated_by_this_join"])
        first_person(result["calibration"]["diagnostics"])["truth_counts"][0] += 1
        self.assertEqual(args, original)

    def test_missing_diagnostics_preserves_unavailable_base_exactly(self):
        grade, report, _ = fixture()
        result = j.join_probability_diagnostics(grade, report)
        self.assertEqual(result, report)
        result["scope"]["people"] = 1
        self.assertEqual(report["scope"]["people"], 78)

    def test_recomputed_frequency_bias_and_macros(self):
        args = fixture(); result = j.join_probability_diagnostics(*args)
        panel = next(iter(result["calibration"]["diagnostics"]["panels"].values()))
        values = list(panel["people"].values())
        self.assertAlmostEqual(panel["person_macro_brier"], sum(v["mean_multiclass_brier"] for v in values) / 78)
        weighted = sum(v["eligible_epochs"] * v["mean_multiclass_brier"] for v in values) / sum(v["eligible_epochs"] for v in values)
        self.assertNotAlmostEqual(panel["person_macro_brier"], weighted)
        for v in values:
            self.assertAlmostEqual(v["observed_class_frequency"][0], v["truth_counts"][0] / v["eligible_epochs"])

    def test_refuses_prediction_panel_person_and_class_mismatch(self):
        for kind in ("prediction", "panel", "person", "classes", "schema"):
            with self.subTest(kind=kind):
                args = fixture(); d = args[2]
                if kind == "prediction": d["predictions"]["sha256"] = "c" * 64
                elif kind == "panel": d["panels"].pop(next(iter(d["panels"])))
                elif kind == "person": next(iter(d["panels"].values()))["people"].pop("900000")
                elif kind == "classes": d["classes"].reverse()
                else: d["schema"] = "unrelated"
                with self.assertRaises(ValueError): j.join_probability_diagnostics(*args)

    def test_refuses_truth_frequency_bias_and_macro_mutations(self):
        for kind in ("truth", "frequency", "bias", "macro", "macro_bias"):
            with self.subTest(kind=kind):
                args = fixture(); d = args[2]; person = first_person(d); panel = next(iter(d["panels"].values()))
                if kind == "truth": person["truth_counts"][0] += 1
                elif kind == "frequency": person["observed_class_frequency"][0] += .1
                elif kind == "bias": person["calibration_in_large_predicted_minus_observed"][0] += .1
                elif kind == "macro": panel["person_macro_brier"] += .1
                else: panel["person_macro_calibration_in_large_predicted_minus_observed"][0] += .1
                with self.assertRaises(ValueError): j.join_probability_diagnostics(*args)

    def test_refuses_clock_mask_and_cross_panel_night_drift(self):
        for kind in ("clock", "masked", "nights", "cross_panel"):
            with self.subTest(kind=kind):
                args = fixture(); person = first_person(args[2])
                if kind == "clock": person["clock_epochs"] += 1
                elif kind == "masked": person["masked_epochs"] += 1
                elif kind == "nights": person["nights"]["9"] = person["nights"].pop("1")
                else:
                    person["nights"]["1"]["clock"] += 1
                    person["nights"]["1"]["masked"] += 1
                    person["clock_epochs"] += 1; person["masked_epochs"] += 1
                with self.assertRaises(ValueError): j.join_probability_diagnostics(*args)

    def test_refuses_loss_clipping_floor_and_numeric_types(self):
        changes = [("mean_multiclass_brier", -1), ("mean_multiclass_brier", 2.01),
                   ("mean_clipped_log_loss_nats", float("nan")), ("mean_clipped_log_loss_nats", True),
                   ("mean_clipped_log_loss_nats", 10**1000), ("log_loss_floor", 1e-12),
                   ("log_loss_clipped_epochs", True), ("log_loss_clipped_epochs", 99999),
                   ("log_loss_clipped_epochs", 1), ("eligible_epochs", True)]
        for key, value in changes:
            with self.subTest(key=key, kind=type(value).__name__):
                args = fixture(); first_person(args[2])[key] = value
                with self.assertRaises(ValueError): j.join_probability_diagnostics(*args)

    def test_refuses_zero_eligible_integrated_person(self):
        args = fixture(); person = first_person(args[2])
        person["defined"] = False; person["eligible_epochs"] = 0
        with self.assertRaises(ValueError): j.join_probability_diagnostics(*args)

    def test_refuses_mean_simplex_or_undefined_panel(self):
        for kind in ("simplex", "undefined", "interval"):
            with self.subTest(kind=kind):
                args = fixture(); panel = next(iter(args[2]["panels"].values()))
                if kind == "simplex": first_person(args[2])["mean_predicted_probability"][0] += .1
                elif kind == "undefined": panel["undefined_people"] = ["900000"]
                else: panel["interval"] = [0, 1]
                with self.assertRaises(ValueError): j.join_probability_diagnostics(*args)

    def test_refuses_grade_report_rebinding_and_double_join(self):
        grade, report, d = fixture()
        report["prediction_panel"]["bytes"] += 1
        with self.assertRaises(ValueError): j.join_probability_diagnostics(grade, report, d)
        grade, report, d = fixture(); result = j.join_probability_diagnostics(grade, report, d)
        with self.assertRaises(ValueError): j.join_probability_diagnostics(grade, result, d)


if __name__ == "__main__":
    unittest.main()
