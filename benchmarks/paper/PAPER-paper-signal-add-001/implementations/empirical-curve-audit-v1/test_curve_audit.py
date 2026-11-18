"""Generated engineering controls; these are not patient data or source results."""
import copy
import unittest

from curve_audit import AuditError, TASK_ID, SCHEMA, audit_curve, canonical_sha256, compare_on_frozen_curve


def support():
    cats = [f"category{i}" for i in range(5)]
    training = [{"trial": f"train-{c}-{j}", "category": c} for c in cats for j in range(4)]
    testing = [{"trial": f"test-{c}", "category": c} for c in cats]
    return {
        "schema": SCHEMA, "task_id": TASK_ID, "patient": "fixture-patient",
        "session": "fixture-session", "region": "hippocampus",
        "noise_condition": "intact", "ablation": "all_units", "removal_draw": 0,
        "categories": cats, "unit_ids": ["u1", "u2", "u3"],
        "ensemble_by_step": [["u1"], ["u1", "u2"], ["u1", "u2", "u3"]],
        "source_bindings": {key: "0" * 64 for key in (
            "observations_sha256", "correct_load1_selection_sha256",
            "trial_partition_policy_sha256", "ensemble_producer_sha256", "condition_transform_sha256")},
        "repetitions": [{"repeat": i, "training": copy.deepcopy(training), "testing": copy.deepcopy(testing)}
                        for i in range(1, 501)],
    }


def predictions(m, right=(2, 4, 3)):
    for rep in m["repetitions"]:
        for step in range(1, len(m["unit_ids"]) + 1):
            for j, row in enumerate(rep["testing"]):
                category = row["category"] if j < right[step - 1] else m["categories"][(j + 1) % 5]
                yield {"repeat": rep["repeat"], "step": step, "trial": row["trial"], "category": category}


class CurveAuditTests(unittest.TestCase):
    def setUp(self):
        self.m = support()
        self.pin = canonical_sha256(self.m)

    def audit(self, rows=None, manifest=None, pin=None):
        return audit_curve(manifest or self.m, predictions(self.m) if rows is None else rows,
                           expected_manifest_sha256=pin or self.pin)

    def test_complete_curves_and_interior_peak(self):
        result = self.audit()
        self.assertEqual(result["prediction_records"], 7500)
        self.assertEqual([r["mean_repeat_accuracy"] for r in result["curve"]], [0.4, 0.8, 0.6])
        self.assertEqual(result["maximizing_steps_without_tie_resolution"], [2])
        self.assertTrue(all(len(r["repetitions"]) == 500 for r in result["curve"]))
        self.assertIsNone(result["paper_win"])
        self.assertFalse(result["source_authentication_established"])

    def test_record_order_does_not_change_result(self):
        self.assertEqual(self.audit(), self.audit(list(reversed(list(predictions(self.m))))))

    def test_full_ensemble_only_is_rejected(self):
        with self.assertRaisesRegex(AuditError, "incomplete"):
            self.audit(r for r in predictions(self.m) if r["step"] == 3)

    def test_missing_repeat_and_duplicate_record_are_rejected(self):
        with self.assertRaisesRegex(AuditError, "incomplete"):
            self.audit(r for r in predictions(self.m) if r["repeat"] != 500)
        rows = list(predictions(self.m))
        rows.append(rows[0])
        with self.assertRaisesRegex(AuditError, "duplicate prediction"):
            self.audit(rows)

    def test_manifest_has_exact_500_repetitions(self):
        m = copy.deepcopy(self.m)
        m["repetitions"].pop()
        with self.assertRaisesRegex(AuditError, "500"):
            self.audit(manifest=m, pin=canonical_sha256(m))
        m["repetitions"].append(copy.deepcopy(m["repetitions"][0]))
        with self.assertRaisesRegex(AuditError, "repeat IDs"):
            self.audit(manifest=m, pin=canonical_sha256(m))

    def test_training_target_cannot_be_submitted_as_query(self):
        rows = list(predictions(self.m))
        rows[0]["trial"] = self.m["repetitions"][0]["training"][0]["trial"]
        with self.assertRaisesRegex(AuditError, "not held out"):
            self.audit(rows)

    def test_overlap_and_unbalanced_source_selection_fail(self):
        m = copy.deepcopy(self.m)
        m["repetitions"][0]["training"][0]["trial"] = m["repetitions"][0]["testing"][0]["trial"]
        with self.assertRaisesRegex(AuditError, "overlap"):
            self.audit(manifest=m, pin=canonical_sha256(m))
        m = copy.deepcopy(self.m)
        m["repetitions"][0]["training"].pop()
        with self.assertRaisesRegex(AuditError, "equal pooled support"):
            self.audit(manifest=m, pin=canonical_sha256(m))

    def test_complete_nested_ensemble_identity_is_required(self):
        m = copy.deepcopy(self.m)
        m["ensemble_by_step"][1] = ["u2", "u3"]
        with self.assertRaisesRegex(AuditError, "retain prior units"):
            self.audit(manifest=m, pin=canonical_sha256(m))
        m["ensemble_by_step"][1] = ["u1", "alien"]
        with self.assertRaisesRegex(AuditError, "undeclared"):
            self.audit(manifest=m, pin=canonical_sha256(m))

    def test_frozen_identity_prevents_support_replacement(self):
        m = copy.deepcopy(self.m)
        m["session"] = "other-session"
        with self.assertRaisesRegex(AuditError, "frozen identity"):
            self.audit(manifest=m)
        m = copy.deepcopy(self.m)
        m["source_bindings"]["condition_transform_sha256"] = "a" * 64
        with self.assertRaisesRegex(AuditError, "frozen identity"):
            self.audit(manifest=m)

    def test_bool_coordinates_unknown_labels_and_extra_fields_fail(self):
        for field, value in (("repeat", True), ("step", False), ("category", "unknown"), ("category", float("nan"))):
            rows = list(predictions(self.m))
            rows[0][field] = value
            with self.assertRaises(AuditError):
                self.audit(rows)
        rows = list(predictions(self.m)); rows[0]["gold"] = "injected"
        with self.assertRaisesRegex(AuditError, "fields"):
            self.audit(rows)

    def test_ties_are_retained_without_arbitrary_selection(self):
        result = self.audit(predictions(self.m, (4, 4, 3)))
        self.assertEqual(result["maximizing_steps_without_tie_resolution"], [1, 2])

    def test_pairing_returns_every_step_and_repeat_but_no_win(self):
        result = compare_on_frozen_curve(self.m, predictions(self.m), predictions(self.m, (2, 4, 5)),
                                         expected_manifest_sha256=self.pin)
        self.assertEqual([r["candidate_minus_author_mean_repeat_accuracy"] for r in result["differences_by_step"]], [0., 0., .4])
        self.assertTrue(all(len(r["paired_repeat_differences"]) == 500 for r in result["differences_by_step"]))
        self.assertIsNone(result["paper_win"])
        self.assertEqual(result["current_sota"], "not_assessed")
        with self.assertRaisesRegex(AuditError, "incomplete"):
            compare_on_frozen_curve(self.m, predictions(self.m),
                                    (r for r in predictions(self.m) if r["step"] < 3),
                                    expected_manifest_sha256=self.pin)

    def test_ablation_draw_axis_is_distinct_from_decoding_repeat(self):
        m = copy.deepcopy(self.m); m["ablation"] = "nonpac_removed"; m["removal_draw"] = 500
        result = self.audit(manifest=m, pin=canonical_sha256(m))
        self.assertEqual(result["removal_draw"], 500)
        self.assertEqual(len(result["curve"][0]["repetitions"]), 500)
        m["removal_draw"] = 501
        with self.assertRaisesRegex(AuditError, "selection"):
            self.audit(manifest=m, pin=canonical_sha256(m))

    def test_balanced_cross_repeat_target_relabeling_is_rejected(self):
        m = copy.deepcopy(self.m)
        a, b = m["repetitions"][1]["testing"][:2]
        a["category"], b["category"] = b["category"], a["category"]
        # All five pooled counts remain equal, but a source observation's
        # category cannot change when it reappears in another random draw.
        with self.assertRaisesRegex(AuditError, "category changed"):
            audit_curve(m, predictions(m), expected_manifest_sha256=canonical_sha256(m))

    def test_fixed_label_trial_can_move_between_training_and_testing(self):
        m = copy.deepcopy(self.m)
        training = m["repetitions"][1]["training"][0]
        testing = m["repetitions"][1]["testing"][0]
        self.assertEqual(training["category"], testing["category"])
        training["trial"], testing["trial"] = testing["trial"], training["trial"]
        result = audit_curve(m, predictions(m), expected_manifest_sha256=canonical_sha256(m))
        self.assertEqual(result["prediction_records"], 7500)
        self.assertEqual([r["mean_repeat_accuracy"] for r in result["curve"]], [0.4, 0.8, 0.6])


if __name__ == "__main__":
    unittest.main()
