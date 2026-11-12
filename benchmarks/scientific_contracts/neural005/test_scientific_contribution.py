"""Invented scalar/full-roster checks only; no datasets, fitting, or scientific runs."""
import copy
import importlib.util
import math
from pathlib import Path
import unittest

PATH = Path(__file__).with_name("scientific_contribution.py")
SPEC = importlib.util.spec_from_file_location("scientific_contribution", PATH)
c = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(c)

PEOPLE = [str(i) for i in range(1, 8)]  # Deliberately invented identities.
COUNTS = [144, 144, 144, 144, 144, 48, 48]


def fixture(history=None, all_erp=None):
    """Generate analytic constant-probability metrics and target-free identities."""
    history = history or [0.2, 0.7, 0.6, 0.8, 0.5, 0.5, 0.8]
    all_erp = all_erp or [0.1, 0.5, 0.5, 0.5, 0.7, 0.8, 0.6]
    cases = [{"participant": p, "case_id": f"{p}:{j // 4 + 1}:{j % 4 + 1}"}
             for p, n in zip(PEOPLE, COUNTS) for j in range(n)]
    schedule = {"participants": list(PEOPLE), "cases": cases}
    receipt = {"status": "three_view_projection_complete", "error": None,
               "training_rows": 3254, "training_people": 26, "development_people": 7,
               "queries_per_view": 816, "total_view_queries": 2448, "fits": 0,
               "reserved_person_inputs": 0, "views": list(c.VIEWS),
               "widths": {"history": 50, "prestimulus": 53, "all_erp": 57},
               "canonical_support_checked_before_mask": True}
    people = []
    prior = 0.5
    for index, (p, n) in enumerate(zip(PEOPLE, COUNTS)):
        positive = 0 if index == 0 else n // 2
        f = positive / n
        probabilities = {"history": history[index], "prestimulus": 0.6,
                         "all_erp": all_erp[index], c.PRIOR: prior}
        arms = {}
        for arm, probability in probabilities.items():
            q = min(1 - c.EPSILON, max(c.EPSILON, probability))
            arms[arm] = {"log_loss": -f * math.log(q) - (1 - f) * math.log1p(-q),
                         "brier": f * (1 - probability) ** 2 + (1 - f) * probability ** 2,
                         "auc": None if positive in (0, n) else 0.5,
                         "mean_probability": probability, "observed_frequency": f,
                         "calibration_mean_error": probability - f}
        people.append({"participant": p, "n": n, "positive_n": positive, "arms": arms})
    macro = {}
    for arm in c.ARMS:
        macro[arm] = {m: math.fsum(row["arms"][arm][m] for row in people) / 7 for m in c.MEASURES}
        defined = [row["arms"][arm]["auc"] for row in people if row["arms"][arm]["auc"] is not None]
        macro[arm].update(auc_mean_defined_only=math.fsum(defined) / len(defined),
                          auc_defined_participant_n=len(defined), auc_undefined_participant_n=7 - len(defined))
    contrasts = {}
    for left, right in c.PAIRS:
        rows = [{"participant": row["participant"],
                 **{m: row["arms"][left][m] - row["arms"][right][m] for m in ("log_loss", "brier")}}
                for row in people]
        contrasts[left + "_minus_" + right] = {
            "left_arm": left, "right_arm": right,
            "direction": "left-minus-right loss; positive means lower right-arm loss",
            "per_participant": rows,
            "equal_participant_mean": {m: math.fsum(row[m] for row in rows) / 7 for m in ("log_loss", "brier")}}
    report = {"status": "matched_scored", "public_validation_passed": True, "participant_n": 7,
              "record_n_per_view": 816, "prediction_n": 2448, "complete_process_n": 21,
              "primary_metric": "equal_participant_all_erp_log_loss", "direction": "lower",
              "primary_unit": "participant", "log_loss_clip_epsilon": c.EPSILON,
              "unchanged_metric_audit_crosscheck": True, "independent_scalar_crosscheck": True,
              "full_contract_qualified": False, "bootstrap_or_significance_test": False,
              "independent_ERP_trial_identity_verified": False,
              "training_participant_macro_prior": prior, "per_participant": people,
              "equal_participant_arms": macro, "signed_comparisons": contrasts,
              "score": macro["all_erp"]["log_loss"]}
    return report, receipt, schedule


class ContributionTests(unittest.TestCase):
    def test_full_scope_and_existing_rank_retained(self):
        report, receipt, schedule = fixture()
        result = c.assess(report, receipt, schedule)
        self.assertEqual(result["scope"]["predictions"], 2448)
        self.assertEqual(result["scope"]["training_examples"], 3254)
        self.assertEqual(result["ranking"]["score"], report["score"])
        self.assertEqual(result["all_six_signed_contrasts"], report["signed_comparisons"])
        self.assertFalse(result["research_qualified"])

    def test_equal_person_gain_is_not_trial_weighted(self):
        report, receipt, schedule = fixture()
        result = c.assess(report, receipt, schedule)
        deltas = [p["arms"]["history"]["log_loss"] - p["arms"]["all_erp"]["log_loss"]
                  for p in report["per_participant"]]
        self.assertAlmostEqual(result["predictive_contribution"]["mean_log_loss_gain"], math.fsum(deltas) / 7)
        self.assertNotAlmostEqual(math.fsum(n * d for n, d in zip(COUNTS, deltas)) / 816, math.fsum(deltas) / 7)

    def test_sensitivity_keeps_primary_full_panel(self):
        report, receipt, schedule = fixture()
        result = c.assess(report, receipt, schedule)
        contribution = result["predictive_contribution"]
        self.assertEqual(len(contribution["leave_one_person_out_sensitivity"]), 7)
        for row in contribution["leave_one_person_out_sensitivity"]:
            expected = [p["log_loss_gain"] for p in contribution["per_person"]
                        if p["participant"] != row["omitted_for_sensitivity_only"]]
            self.assertAlmostEqual(row["mean_log_loss_gain"], math.fsum(expected) / 6)
        self.assertEqual(result["scope"]["development_people"], 7)
        self.assertEqual(result["ranking"]["score"], report["score"])

    def test_adverse_and_zero_contribution_remain_valid(self):
        for history, all_erp, sign in [([0.1]+[0.5]*6, [0.9]*7, "negative"),
                                      ([0.5]*7, [0.5]*7, "zero")]:
            with self.subTest(sign=sign):
                self.assertEqual(c.assess(*fixture(history, all_erp))["predictive_contribution"]["observed_sign"], sign)

    def test_weakening_history_cannot_improve_rank(self):
        a = c.assess(*fixture([0.1]+[0.5]*6, [0.5]*7))
        b = c.assess(*fixture([0.9]*7, [0.5]*7))
        self.assertEqual(a["ranking"], b["ranking"])
        self.assertGreater(b["predictive_contribution"]["mean_log_loss_gain"],
                           a["predictive_contribution"]["mean_log_loss_gain"])
        self.assertFalse(b["scientific_neural_contribution_claim_admitted"])

    def test_infeasible_control_is_not_a_permutation_test(self):
        result = c.assess(*fixture())
        control = result["matched_history_ERP_control"]
        self.assertEqual(control["development_singleton_strata"], 816)
        self.assertEqual(control["movable_development_cases"], 0)
        self.assertEqual(control["ERP_randomizations_performed"], 0)
        self.assertIsNone(control["p_value"])
        self.assertIsNone(control["seed"])
        self.assertIsNone(control["randomization_repetitions_selected"])
        self.assertFalse(result["conditional_independence_test_performed"])
        self.assertFalse(result["full_contract_complete"])

    def test_one_class_person_remains_in_gain(self):
        result = c.assess(*fixture())
        self.assertEqual(result["absolute_arms"]["all_erp"]["auc_undefined_participant_n"], 1)
        self.assertEqual(len(result["predictive_contribution"]["per_person"]), 7)

    def test_no_input_mutation_or_output_aliasing(self):
        args = fixture()
        before = copy.deepcopy(args)
        result = c.assess(*args)
        self.assertEqual(args, before)
        result["absolute_arms"]["history"]["log_loss"] = 99
        self.assertEqual(args, before)

    def test_refuses_wrong_scope_or_incomplete_barrier(self):
        for key, value in [("participant_n", 6), ("record_n_per_view", 815),
                           ("prediction_n", 2447), ("complete_process_n", 20),
                           ("complete_process_n", True)]:
            with self.subTest(key=key, value=value):
                args = fixture(); args[0][key] = value
                with self.assertRaises(ValueError): c.assess(*args)

    def test_refuses_projection_scope_or_mask_drift(self):
        for key, value in [("training_people", 25), ("training_rows", 3253),
                           ("development_people", 6), ("queries_per_view", 815),
                           ("canonical_support_checked_before_mask", False),
                           ("fits", 1), ("reserved_person_inputs", 1)]:
            with self.subTest(key=key):
                args = fixture(); args[1][key] = value
                with self.assertRaises(ValueError): c.assess(*args)

    def test_refuses_duplicate_missing_or_outside_schedule(self):
        for mutation in ("duplicate", "missing", "episode", "round", "identity", "leading_zero"):
            with self.subTest(mutation=mutation):
                args = fixture(); cases = args[2]["cases"]
                if mutation == "duplicate": cases[-1] = dict(cases[0])
                elif mutation == "missing": cases.pop()
                elif mutation == "episode": cases[0]["case_id"] = "1:37:1"
                elif mutation == "round": cases[0]["case_id"] = "1:1:5"
                elif mutation == "identity": cases[0]["participant"] = "99"
                else: cases[0]["case_id"] = "1:01:1"
                with self.assertRaises(ValueError): c.assess(*args)

    def test_refuses_fabricated_positive_contrast(self):
        args = fixture()
        args[0]["signed_comparisons"]["history_minus_all_erp"]["equal_participant_mean"]["log_loss"] = 100
        with self.assertRaises(ValueError): c.assess(*args)

    def test_refuses_dropped_person_prior_or_contrast(self):
        for mutation in ("person", "prior", "contrast", "count"):
            with self.subTest(mutation=mutation):
                args = fixture(); r = args[0]
                if mutation == "person": r["per_participant"].pop()
                elif mutation == "prior": del r["equal_participant_arms"][c.PRIOR]
                elif mutation == "contrast": del r["signed_comparisons"]["history_minus_prestimulus"]
                else: r["per_participant"][0]["n"] -= 1
                with self.assertRaises(ValueError): c.assess(*args)

    def test_refuses_nonfinite_boolean_or_gain_primary(self):
        for value in (float("nan"), float("inf"), True):
            with self.subTest(value=value):
                args = fixture(); args[0]["score"] = value
                with self.assertRaises(ValueError): c.assess(*args)
        args = fixture(); args[0]["primary_metric"] = "history_minus_all_erp"
        with self.assertRaises(ValueError): c.assess(*args)

    def test_refuses_unvalidated_nested_payload_fields(self):
        args = fixture(); args[0]["per_participant"][0]["unrequested_records"] = ["not allowed"]
        with self.assertRaises(ValueError): c.assess(*args)

    def test_refuses_significance_or_qualification_promotion(self):
        for key in ("full_contract_qualified", "bootstrap_or_significance_test",
                    "independent_ERP_trial_identity_verified"):
            with self.subTest(key=key):
                args = fixture(); args[0][key] = True
                with self.assertRaises(ValueError): c.assess(*args)

    def test_keyed_person_order_is_not_an_alignment_shuffle(self):
        args = fixture()
        original = c.assess(*args)
        args[0]["per_participant"].reverse()
        for value in args[0]["signed_comparisons"].values():
            value["per_participant"].reverse()
        result = c.assess(*args)
        self.assertEqual(result["predictive_contribution"], original["predictive_contribution"])
        self.assertEqual(result["matched_history_ERP_control"], original["matched_history_ERP_control"])


if __name__ == "__main__":
    unittest.main()
