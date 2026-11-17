"""Invented full-support engineering controls; no authentic records or fitting."""
import copy
import importlib.util
import math
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("paired_sleep_contribution", Path(__file__).with_name("paired_sleep_contribution.py"))
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def independent_metrics(matrix):
    support = [sum(row) for row in matrix]
    f1 = [2 * matrix[i][i] / (support[i] + sum(row[i] for row in matrix))
          if support[i] + sum(row[i] for row in matrix) else 0.0 for i in range(5)]
    recall = [matrix[i][i] / support[i] if support[i] else None for i in range(5)]
    return {"confusion": matrix, "support": support, "eligible_epochs": sum(support),
            "class_f1": f1, "class_recall": recall, "fixed_five_macro_f1": sum(f1) / 5,
            "supported_balanced_accuracy": sum(x for x in recall if x is not None) /
            sum(x is not None for x in recall)}


def finish(grade):
    """Regenerate existing scalar reductions after an invented-panel mutation."""
    for panel in grade["panels"].values():
        panel["primary"] = math.fsum(m["fixed_five_macro_f1"] for m in panel["people"].values()) / 78
    grade["contrasts"] = {}
    for mode in c.MODES:
        profile = next(k.split("|")[1] for k in grade["panels"] if k.startswith(mode + "|"))
        for left, right, name in c.SIGNALS:
            a = grade["panels"][f"{mode}|{profile}|{left}|original"]["people"]
            b = grade["panels"][f"{mode}|{profile}|{right}|original"]["people"]
            delta = {p: a[p]["fixed_five_macro_f1"] - b[p]["fixed_five_macro_f1"] for p in a}
            grade["contrasts"][mode + "|" + name] = {"mean_delta": math.fsum(delta.values()) / 78,
                                                       "paired_person_deltas": delta}


def fixture(profile="generic_current_person", missing_rem=False):
    support = {"schema": "sleep_full153_support_v1", "people": [
        {"person": str(100000 + i), "fold": i // 13 + 1, "nights": 1 if i < 3 else 2} for i in range(78)]}
    # These consecutive large identities and all counts/probabilities are invented.
    panels, night_matrices = {}, {}
    for key in c.panel_keys(profile):
        mode, _, view, control = key.split("|")
        base = {c.FROZEN: 40, c.ADAPTIVE: 46, "R0": 30, "R1": 38, "R2": 49}[mode]
        offset = {"C": 0, "EC": 13, "OC": 7, "EOC": 21}[view]
        shift = {"original": 0, "shifted": -11, "association": -19}[control]
        people = {}
        for i, row in enumerate(support["people"]):
            person = row["person"]
            matrices = []
            for night in range(row["nights"]):
                true = [30 + i % 3, 12, 21, 14, 0 if missing_rem and i == 0 else 10]
                true = [v * (3 if night else 1) for v in true]
                rate = base + offset + shift + i % 5 - 9 * night
                matrix = [[0] * 5 for _ in range(5)]
                for stage, total in enumerate(true):
                    correct = total * rate // 100
                    matrix[stage][stage] = correct
                    matrix[stage][(stage + 1) % 5] = total - correct
                matrices.append(matrix)
            combined = [[sum(m[a][b] for m in matrices) for b in range(5)] for a in range(5)]
            people[person] = independent_metrics(combined)
            night_matrices[key, person] = matrices
        panels[key] = {"primary": 0.0, "people": people, "independent_people": 78,
                       "metric": "equal_person_fixed_five_class_macro_f1"}
    grade = {"schema": "neural007_full153_grade_v1", "panels": panels, "contrasts": {},
             "people": 78, "nights": 153, "predictions": {"bytes": 123, "sha256": "a" * 64},
             "raw_native_LLM_understanding_tested": False, "scientific_content_admitted": False,
             "research_qualified": False, "submission_ready": False, "independent_tasks": 1}
    finish(grade)
    return grade, support, profile, night_matrices


class SleepComparisonTests(unittest.TestCase):
    def test_complete_scope_all_panels_and_contrasts(self):
        grade, support, profile, _ = fixture()
        r = c.assess(grade, support, profile)
        self.assertEqual(len(r["all_27_absolute_panels"]), 27)
        self.assertEqual(len(r["comparisons"]), 52)
        self.assertEqual(r["scope"]["candidate_inferences_required_upstream"], 936)
        self.assertEqual(r["scope"]["reference_inferences_required_upstream"], 1170)
        self.assertEqual(sum(x["nights"] for x in support["people"]), 153)
        self.assertEqual(r["original_six_signal_contrasts"], grade["contrasts"])
        self.assertEqual(r["primary_mode_comparison"], "mode:EOC")

    def test_mode_pairing_and_interaction_independent_arithmetic(self):
        grade, support, profile, _ = fixture()
        r = c.assess(grade, support, profile)
        expected = []
        for row in support["people"]:
            p = row["person"]
            def f(mode, view):
                selected = profile if mode == c.FROZEN else "current_person"
                return grade["panels"][f"{mode}|{selected}|{view}|original"]["people"][p]["fixed_five_macro_f1"]
            value = (f(c.ADAPTIVE, "EC") - f(c.ADAPTIVE, "C")) - (f(c.FROZEN, "EC") - f(c.FROZEN, "C"))
            expected.append(value)
            self.assertAlmostEqual(r["comparisons"]["mode_interaction:EEG_over_clock"]["per_person"][p], value)
        self.assertAlmostEqual(r["comparisons"]["mode_interaction:EEG_over_clock"]["mean"], sum(expected) / 78)

    def test_nights_combined_before_f1_not_night_mean(self):
        grade, support, profile, nights = fixture()
        r = c.assess(grade, support, profile)
        key = f"{c.FROZEN}|{profile}|EOC|original"
        person = support["people"][10]["person"]
        naive = sum(independent_metrics(m)["fixed_five_macro_f1"] for m in nights[key, person]) / 2
        observed = r["all_27_absolute_panels"][key]["people"][person]["fixed_five_macro_f1"]
        self.assertNotAlmostEqual(observed, naive)

    def test_person_weighting_not_epoch_weighting(self):
        grade, support, profile, _ = fixture()
        r = c.assess(grade, support, profile)
        values = r["comparisons"]["mode:EOC"]["per_person"]
        key = f"{c.FROZEN}|{profile}|EOC|original"
        counts = {p: m["eligible_epochs"] for p, m in grade["panels"][key]["people"].items()}
        weighted = sum(counts[p] * values[p] for p in values) / sum(counts.values())
        self.assertAlmostEqual(r["comparisons"]["mode:EOC"]["mean"], sum(values.values()) / 78)
        self.assertNotAlmostEqual(r["comparisons"]["mode:EOC"]["mean"], weighted)

    def test_fold_sensitivity_retains_primary_all_people(self):
        grade, support, profile, _ = fixture()
        r = c.assess(grade, support, profile)
        item = r["comparisons"]["mode:EOC"]
        for fold in range(1, 7):
            included = [row["person"] for row in support["people"] if row["fold"] != fold]
            x = item["leave_one_fold_out_sensitivity"][str(fold)]
            self.assertEqual(x["required_people"], 65)
            self.assertAlmostEqual(x["mean"], sum(item["per_person"][p] for p in included) / 65)
            self.assertEqual(item["folds"][str(fold)]["required_people"], 13)
        self.assertEqual(item["required_people"], 78)
        self.assertFalse(r["uncertainty"]["bootstrap_performed"])
        self.assertIsNone(r["uncertainty"]["confidence_interval"])

    def test_strict_rem_undefined_never_supported_only_mean(self):
        grade, support, profile, _ = fixture(missing_rem=True)
        r = c.assess(grade, support, profile)
        item = r["comparisons"][c.ADAPTIVE + ":EOG_given_EEG:rem_recall"]
        self.assertEqual(item["defined_people"], 77)
        self.assertIsNone(item["mean"])
        self.assertEqual(len(item["per_person"]), 78)
        self.assertIsNone(item["folds"]["1"]["mean"])
        self.assertIsNotNone(item["leave_one_fold_out_sensitivity"]["1"]["mean"])
        self.assertIsNone(r["neural008_numeric_claim_targets"][c.ADAPTIVE + ":eog_gain:rem_recall"]["aggregate"])
        self.assertIsNotNone(r["comparisons"]["mode:EOC"]["mean"])

    def test_reuse_profile_is_explicitly_different_treatment(self):
        grade, support, profile, _ = fixture("training_only_reuse")
        r = c.assess(grade, support, profile)
        self.assertEqual(r["comparison_policy"]["declared_fixed_final_fits"], 24)
        self.assertEqual(r["comparison_policy"]["kind"], "different_query_selection_and_fit_reuse_treatments")
        self.assertFalse(r["comparison_policy"]["equal_actual_compute_established"])
        with self.assertRaises(ValueError): c.assess(grade, support, "generic_current_person")

    def test_negative_and_zero_results_are_valid(self):
        grade, support, profile, _ = fixture()
        for view in c.VIEWS:
            f = grade["panels"][f"{c.FROZEN}|{profile}|{view}|original"]
            a = grade["panels"][f"{c.ADAPTIVE}|current_person|{view}|original"]
            f["people"], a["people"] = a["people"], f["people"]
        finish(grade)
        self.assertLess(c.assess(grade, support, profile)["comparisons"]["mode:EOC"]["mean"], 0)
        for view in c.VIEWS:
            grade["panels"][f"{c.ADAPTIVE}|current_person|{view}|original"]["people"] = copy.deepcopy(
                grade["panels"][f"{c.FROZEN}|{profile}|{view}|original"]["people"])
        finish(grade)
        r = c.assess(grade, support, profile)
        self.assertEqual(r["comparisons"]["mode:EOC"]["mean"], 0)
        self.assertFalse(r["research_qualified"])

    def test_weakened_context_cannot_improve_absolute_ranking(self):
        grade, support, profile, _ = fixture()
        before = c.assess(grade, support, profile)
        key = f"{c.ADAPTIVE}|current_person|EC|original"
        for value in grade["panels"][key]["people"].values():
            m = value["confusion"]
            for i in range(5):
                m[i][(i + 1) % 5] += m[i][i]
                m[i][i] = 0
            value.update(independent_metrics(m))
        finish(grade)
        after = c.assess(grade, support, profile)
        self.assertEqual(before["absolute_eoc_rankings"], after["absolute_eoc_rankings"])
        self.assertGreater(after["comparisons"][c.ADAPTIVE + ":EOG_given_EEG"]["mean"],
                           before["comparisons"][c.ADAPTIVE + ":EOG_given_EEG"]["mean"])
        self.assertIsNone(after["scientific_reasoning_credit"])

    def test_refuses_missing_panel_person_or_reference_control(self):
        for mode in ("panel", "person", "association"):
            with self.subTest(mode=mode):
                grade, support, profile, _ = fixture()
                if mode == "panel": grade["panels"].pop(next(iter(grade["panels"])))
                elif mode == "person": next(iter(grade["panels"].values()))["people"].pop(support["people"][0]["person"])
                else: grade["panels"].pop("R2|independent_reference|C|association")
                with self.assertRaises(ValueError): c.assess(grade, support, profile)

    def test_refuses_support_drift_folds_and_nights(self):
        for kind in ("duplicate", "fold", "night", "count", "bool"):
            with self.subTest(kind=kind):
                grade, support, profile, _ = fixture()
                if kind == "duplicate": support["people"][1]["person"] = support["people"][0]["person"]
                elif kind == "fold": support["people"][0]["fold"] = 2
                elif kind == "night": support["people"][0]["nights"] = 2
                elif kind == "count": support["people"].pop()
                else: support["people"][0]["fold"] = True
                with self.assertRaises(ValueError): c.assess(grade, support, profile)

    def test_refuses_inconsistent_truth_macro_and_contrast(self):
        for kind in ("truth", "macro", "contrast", "rem"):
            with self.subTest(kind=kind):
                grade, support, profile, _ = fixture()
                panel = next(iter(grade["panels"].values()))
                person = support["people"][0]["person"]
                if kind == "truth":
                    m = panel["people"][person]["confusion"]
                    m[0][0] += 1
                    panel["people"][person] = independent_metrics(m)
                    finish(grade)
                elif kind == "macro": panel["primary"] += .01
                elif kind == "contrast": next(iter(grade["contrasts"].values()))["mean_delta"] += .01
                else: panel["people"][person]["class_recall"][4] = None
                with self.assertRaises(ValueError): c.assess(grade, support, profile)

    def test_refuses_nonfinite_boolean_count_and_qualification(self):
        for bad in (True, float("nan"), float("inf"), 10**1000):
            with self.subTest(bad_type=type(bad).__name__):
                grade, support, profile, _ = fixture()
                next(iter(grade["panels"].values()))["primary"] = bad
                with self.assertRaises(ValueError): c.assess(grade, support, profile)
        grade, support, profile, _ = fixture()
        next(iter(next(iter(grade["panels"].values()))["people"].values()))["confusion"][0][0] = True
        with self.assertRaises(ValueError): c.assess(grade, support, profile)
        grade, support, profile, _ = fixture(); grade["research_qualified"] = True
        with self.assertRaises(ValueError): c.assess(grade, support, profile)

    def test_order_invariance_and_no_mutation(self):
        grade, support, profile, _ = fixture()
        before = copy.deepcopy((grade, support))
        a = c.assess(grade, support, profile)
        self.assertEqual((grade, support), before)
        support["people"].reverse()
        grade["panels"] = dict(reversed(list(grade["panels"].items())))
        for panel in grade["panels"].values(): panel["people"] = dict(reversed(list(panel["people"].items())))
        b = c.assess(grade, support, profile)
        self.assertEqual(a["comparisons"], b["comparisons"])
        a["all_27_absolute_panels"][next(iter(a["all_27_absolute_panels"]))]["primary"] = 999
        self.assertNotEqual(a["all_27_absolute_panels"], grade["panels"])

    def test_no_calibration_or_reasoning_invented_from_confusions(self):
        grade, support, profile, _ = fixture()
        r = c.assess(grade, support, profile)
        self.assertEqual(r["calibration"]["status"], "not_inferable_from_confusion_counts")
        self.assertIsNone(r["calibration"]["diagnostics"])
        self.assertFalse(r["internal_LLM_understanding_established"])
        self.assertFalse(r["causal_effect_established"])
        self.assertEqual(len(r["neural008_numeric_claim_targets"]), 6)


if __name__ == "__main__":
    unittest.main()
