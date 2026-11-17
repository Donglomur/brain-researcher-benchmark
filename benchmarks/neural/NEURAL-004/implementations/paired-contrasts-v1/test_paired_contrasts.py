"""Generated software controls only; no authentic data, model, or solver runs."""
import copy
import importlib.util
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paired_contrasts import InvalidGrade, PEOPLE, POLICIES, UNIT, paired_contrasts


def panel(losses, label):
    rows = []
    for i, person in enumerate(PEOPLE):
        # Unequal person sizes and different opaque IDs in each view matter.
        n = i + 1
        rows.append({"person": person, "mse": losses[i], "n": n,
                     "trial_errors": [{"id": f"{label}-opaque-{person}-{j}", "squared_error": losses[i]} for j in range(n)]})
    return {"status": "complete", "person_results": rows, "failures": [],
            "macro_mse": math.fsum(losses) / 26, "unit": UNIT}


def grade():
    result = {"schema": "neural004_prediction_grade_v1", "actors": {}, "references": {}, "whole_prediction_complete": True,
              "release_pin": {"bytes": 1, "sha256": "0" * 64}}
    for key in POLICIES:
        result["actors"][key] = panel([0.25] * 26, key)
    result["references"] = {key: panel([0.25] * 26, key) for key in ("B", "N")}
    return result


def lookup(report, identifier):
    return next(c for c in report["comparisons"] if c["id"] == identifier)


def fail_person(value, person, status="failed"):
    value["person_results"] = [row for row in value["person_results"] if row["person"] != person]
    value.update(status="incomplete", failures=[{"person": person, "status": status}], macro_mse=None)


class PairedContrastControls(unittest.TestCase):
    def test_exact_fixed_comparison_roster_and_null(self):
        result = paired_contrasts(grade())
        expected = {f"{mode}/{a}_vs_{b}" for mode in ("P", "I")
                    for b, a in (("B", "E"), ("B", "H"), ("B", "EH"), ("E", "EH"), ("H", "EH"))}
        expected |= {f"I_vs_P/{v}" for v in ("B", "E", "H", "EH")} | {"reference/N_vs_B"}
        self.assertEqual({c["id"] for c in result["comparisons"]}, expected)
        self.assertTrue(result["all_comparisons_complete"])
        self.assertTrue(all(c["person_macro_difference"] == 0 for c in result["comparisons"]))
        self.assertFalse(result["whole_study_qualified"])

    def test_participant_macro_not_trial_weighted_and_direction(self):
        source = grade()
        source["actors"]["P/E"] = panel([0.0] + [0.5] * 25, "different-context")
        result = lookup(paired_contrasts(source), "P/E_vs_B")
        self.assertAlmostEqual(result["person_macro_difference"], -3 / 13)
        trial_pooled = (0.25 * sum(range(1, 27)) - 0.5 * sum(range(2, 27))) / sum(range(1, 27))
        self.assertNotAlmostEqual(result["person_macro_difference"], trial_pooled)
        self.assertEqual(result["median_person_difference"], -0.25)
        self.assertEqual(result["minimum_person_difference"], -0.25)
        self.assertEqual(result["maximum_person_difference"], 0.25)
        sensitivity = result["descriptive_delete_one_person_macro"]
        self.assertEqual(sensitivity[0], {"omitted_person": "0", "difference": -0.25})
        self.assertAlmostEqual(sensitivity[1]["difference"], -0.23)
        self.assertIsNone(result["population_confidence_interval"])

    def test_mode_and_information_are_separate(self):
        source = grade()
        source["actors"]["I/E"] = panel([0.125] * 26, "I-E")
        result = paired_contrasts(source)
        self.assertEqual(lookup(result, "I_vs_P/E")["person_macro_difference"], 0.125)
        self.assertEqual(lookup(result, "I/E_vs_B")["person_macro_difference"], 0.125)
        self.assertEqual(lookup(result, "P/E_vs_B")["person_macro_difference"], 0)
        self.assertEqual(lookup(result, "I/EH_vs_E")["person_macro_difference"], -0.125)

    def test_failed_person_invalidates_only_dependent_comparisons(self):
        source = grade()
        fail_person(source["actors"]["P/E"], "4", "blocked")
        source["whole_prediction_complete"] = False
        result = paired_contrasts(source)
        impacted = lookup(result, "P/E_vs_B")
        self.assertEqual(len(impacted["people"]), 25)
        self.assertEqual(impacted["failures"], [{"person": "4", "baseline_status": "complete", "alternative_status": "blocked"}])
        for field in ("person_macro_difference", "median_person_difference", "minimum_person_difference",
                      "maximum_person_difference", "descriptive_delete_one_person_macro"):
            self.assertIsNone(impacted[field])
        self.assertEqual(lookup(result, "P/H_vs_B")["status"], "complete")
        self.assertFalse(result["all_comparisons_complete"])

    def test_rejects_silent_missing_and_duplicate_people(self):
        for edit in (lambda p: p["person_results"].pop(),
                     lambda p: p["person_results"].__setitem__(25, copy.deepcopy(p["person_results"][0]))):
            source = grade()
            edit(source["actors"]["P/B"])
            with self.assertRaises(InvalidGrade):
                paired_contrasts(source)

    def test_rejects_inconsistent_trial_support_or_arithmetic(self):
        for mutation in ("support", "trial", "macro", "nonfinite", "units"):
            source = grade()
            target = source["actors"]["P/E"]
            if mutation == "support":
                target["person_results"][0]["trial_errors"].append({"id": "extra", "squared_error": .25})
                target["person_results"][0]["n"] = 2
            elif mutation == "trial":
                target["person_results"][0]["trial_errors"][0]["squared_error"] = .1
            elif mutation == "macro":
                target["macro_mse"] = .1
            elif mutation == "nonfinite":
                target["person_results"][0]["mse"] = float("nan")
            else:
                target["unit"] = "percentage points squared"
            with self.subTest(mutation=mutation), self.assertRaises(InvalidGrade):
                paired_contrasts(source)

    def test_rejects_complete_case_macro_and_claimed_complete(self):
        source = grade()
        fail_person(source["references"]["N"], "25")
        with self.assertRaises(InvalidGrade):
            paired_contrasts(source)
        source["whole_prediction_complete"] = False
        source["references"]["N"]["macro_mse"] = .25
        with self.assertRaises(InvalidGrade):
            paired_contrasts(source)

    def test_compatible_with_actual_person_loss_and_context_specific_ids(self):
        # Execute the actual retained grader's person-loss path on generated
        # forecasts and targets; no fake target barrier or authority admission.
        root = Path(__file__).resolve().parents[1] / "programme-source/implementation-v1/central-integration/successor-v3/effective-parent"
        spec = importlib.util.spec_from_file_location("neural004_paired_test_source", root / "__init__.py", submodule_search_locations=[str(root)])
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        original = importlib.import_module(spec.name + ".grading")
        source = grade()
        for policy in POLICIES:
            rows = []
            for i, person in enumerate(PEOPLE):
                ids = [f"{policy}-opaque-{person}-{j}" for j in range(i + 1)]
                forecasts = [{"id": ident, "prediction": .5} for ident in ids]
                answers = [{"id": ident, "value": .25} for ident in ids]
                rows.append({"person": person, **original.person_loss(forecasts, answers)})
            source["actors"][policy].update(person_results=rows, macro_mse=.0625)
        result = paired_contrasts(source)
        self.assertEqual(lookup(result, "P/E_vs_B")["person_macro_difference"], 0)
        self.assertEqual(lookup(result, "reference/N_vs_B")["person_macro_difference"], 0)


if __name__ == "__main__":
    unittest.main()
