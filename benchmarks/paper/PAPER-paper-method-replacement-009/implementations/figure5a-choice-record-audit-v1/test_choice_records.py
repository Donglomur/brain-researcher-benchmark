"""Generated support/ordering controls only; no recordings or model execution."""
from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("choice_records_under_test", Path(__file__).with_name("choice_records.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def fixture():
    regions = ("PO", "LP", "DG", "CA1", "VISa")
    sessions = [{"session": "s" + str(i), "animal": "a" + str(i // 2)} for i in range(10)]
    cases = [{"case_id": "c" + str(i), "session": "s" + str(i),
              "region": regions[i % 5], "condition": "single", "trial_ids": [0, "0", 2, 3]}
             for i in range(10)]
    # Explicitly nonrectangular: three additional incidences, not 10 x 5 x 2.
    cases += [{"case_id": "extra" + str(i), "session": "s" + str(i),
               "region": regions[(i + 1) % 5], "condition": "combined", "trial_ids": [0, "0", 2]}
              for i in (0, 3, 6)]
    plan = {"schema": "figure5a-choice-support/v1", "task_id": m.TASK,
            "positive_class": "source-declared-right-choice", "source_protocol_sha256": "a" * 64,
            "sessions": sessions, "cases": cases}
    commitment = sha256(encoded(plan)).hexdigest()
    predictions = {"schema": "figure5a-choice-predictions/v1", "support_sha256": commitment,
                   "positive_class": plan["positive_class"], "cases": []}
    probabilities = {("int", 0): .1, ("str", "0"): .2, ("int", 2): .3, ("int", 3): .4}
    for case in cases:
        predictions["cases"].append({"case_id": case["case_id"], "predictions": [
            {"trial_id": tid, "positive_probability": probabilities[(type(tid).__name__, tid)]}
            for tid in case["trial_ids"]]})
    labels = {"schema": "figure5a-choice-labels/v1", "support_sha256": commitment,
              "positive_class": plan["positive_class"], "sessions": [
                  {"session": item["session"], "labels": [
                      {"trial_id": tid, "label": label} for tid, label in ((0, 0), ("0", 1), (2, 0), (3, 1))]}
                  for item in sessions]}
    return plan, predictions, labels


class ChoiceRecordControls(unittest.TestCase):
    def setUp(self):
        self.plan, self.predictions, self.labels = fixture()
        self.calls = 0

    def load_labels(self):
        self.calls += 1
        return encoded(self.labels)

    def audit(self, raw_prediction=None):
        plan = encoded(self.plan)
        return m.audit_choice_profile(plan, encoded(self.predictions) if raw_prediction is None else raw_prediction,
                                      self.load_labels, expected_support_sha256=sha256(plan).hexdigest())

    def test_full_nonrectangular_profile_uses_continuous_scores(self):
        report = self.audit()
        self.assertEqual(self.calls, 1)
        self.assertEqual(report["expected_cases"], 13)
        self.assertEqual(report["expected_sessions"], 10)
        self.assertEqual(report["expected_animals"], 5)
        self.assertEqual(report["prediction_records"], 49)
        self.assertEqual(report["rows"][0]["value"], .75)
        self.assertEqual(report["rows"][10]["value"], .5)
        self.assertTrue(report["complete_prediction_coverage"])
        self.assertIsNone(report["panel_aggregate"])
        self.assertIsNone(report["paper_win"])
        self.assertFalse(report["research_qualified"])
        self.assertEqual(report["scientific_outcome"], "unknown")
        self.assertEqual(report["source_qualification"], "not_established_by_supplied_support")

    def test_case_and_trial_reordering_joins_by_typed_identity(self):
        expected = self.audit()["rows"]
        self.predictions["cases"].reverse()
        for case in self.predictions["cases"]:
            case["predictions"].reverse()
        for session in self.labels["sessions"]:
            session["labels"].reverse()
        self.labels["sessions"].reverse()
        self.assertEqual(self.audit()["rows"], expected)
        self.assertEqual(self.calls, 2)

    def test_last_case_invalid_probability_precedes_any_label_access(self):
        self.predictions["cases"][-1]["predictions"][-1]["positive_probability"] = 1.01
        with self.assertRaises(m.AuditError):
            self.audit()
        self.assertEqual(self.calls, 0)

    def test_missing_extra_and_duplicate_cases_are_rejected_before_labels(self):
        base = deepcopy(self.predictions)
        mutations = [base["cases"][:-1], base["cases"] + [base["cases"][0]],
                     base["cases"][:-1] + [base["cases"][0]],
                     base["cases"][:-1] + [dict(base["cases"][-1], case_id="foreign")]]
        for cases in mutations:
            with self.subTest(cases=len(cases)):
                self.predictions = dict(base, cases=cases)
                with self.assertRaises(m.AuditError):
                    self.audit()
                self.assertEqual(self.calls, 0)

    def test_missing_extra_duplicate_and_bool_trial_ids_are_rejected(self):
        original = deepcopy(self.predictions)
        for mode in ("missing", "extra", "duplicate", "wrong", "bool", "int_string_collision"):
            self.predictions = deepcopy(original)
            rows = self.predictions["cases"][-1]["predictions"]
            if mode == "missing": rows.pop()
            elif mode == "extra": rows.append(dict(rows[0], trial_id=900))
            elif mode == "duplicate": rows[-1] = deepcopy(rows[0])
            elif mode == "wrong": rows[-1]["trial_id"] = 900
            elif mode == "bool": rows[-1]["trial_id"] = True
            else: rows[1]["trial_id"] = 0  # "0" is not integer0.
            with self.subTest(mode=mode), self.assertRaises(m.AuditError): self.audit()
            self.assertEqual(self.calls, 0)

    def test_nonfinite_bool_and_huge_probability_rejection(self):
        original = deepcopy(self.predictions)
        for value in (True, -0.01, 10**400, "0.3"):
            self.predictions = deepcopy(original)
            self.predictions["cases"][-1]["predictions"][-1]["positive_probability"] = value
            with self.subTest(value_type=type(value).__name__), self.assertRaises(m.AuditError): self.audit()
        self.predictions = deepcopy(original)
        raw = encoded(self.predictions).replace(b'"positive_probability":0.1', b'"positive_probability":NaN', 1)
        with self.assertRaises(m.AuditError): self.audit(raw)
        self.assertEqual(self.calls, 0)

    def test_prediction_orientation_and_commitment_must_match(self):
        for field, value in (("positive_class", "source-declared-left-choice"), ("support_sha256", "b" * 64)):
            self.predictions = fixture()[1]
            self.predictions[field] = value
            with self.subTest(field=field), self.assertRaises(m.AuditError): self.audit()
            self.assertEqual(self.calls, 0)

    def test_no_target_bearing_extra_prediction_fields(self):
        self.predictions["cases"][0]["predictions"][0]["label"] = 0
        with self.assertRaises(m.AuditError): self.audit()
        self.assertEqual(self.calls, 0)

    def test_uncommitted_support_and_wrong_task_fail_before_labels(self):
        raw = encoded(self.plan)
        with self.assertRaises(m.AuditError):
            m.audit_choice_profile(raw, encoded(self.predictions), self.load_labels, expected_support_sha256="0" * 64)
        self.plan["task_id"] = "NEURAL-009"
        with self.assertRaises(m.AuditError): self.audit()
        self.assertEqual(self.calls, 0)

    def test_duplicate_incidence_and_dropped_panel_axes_fail(self):
        original = deepcopy(self.plan)
        mutations = []
        bad = deepcopy(original); bad["cases"].append(dict(bad["cases"][0], case_id="duplicated-cell")); mutations.append(bad)
        bad = deepcopy(original); bad["sessions"].pop(); mutations.append(bad)
        bad = deepcopy(original); bad["cases"] = [x for x in bad["cases"] if x["session"] != "s9"]; mutations.append(bad)
        bad = deepcopy(original); bad["cases"] = [x for x in bad["cases"] if x["region"] != "VISa"]; mutations.append(bad)
        for plan in mutations:
            self.plan = plan
            with self.assertRaises(m.AuditError): self.audit()
            self.assertEqual(self.calls, 0)

    def test_metric_pin_is_checked_before_label_access(self):
        with patch.object(m, "METRICS_SHA256", "0" * 64), self.assertRaises(m.AuditError): self.audit()
        self.assertEqual(self.calls, 0)

    def test_single_class_case_stays_in_complete_profile(self):
        for row in self.labels["sessions"][-1]["labels"]: row["label"] = 1
        report = self.audit()
        self.assertEqual(len(report["rows"]), 13)
        self.assertTrue(report["complete_prediction_coverage"])
        self.assertFalse(report["all_case_auc_defined"])
        self.assertEqual(report["rows"][9]["undefined_reason"], "single_class")
        self.assertIsNone(report["rows"][9]["value"])
        self.assertIsNone(report["panel_aggregate"])

    def test_label_missing_extra_duplicate_and_orientation_fail(self):
        original = deepcopy(self.labels)
        for mode in ("missing", "extra", "duplicate", "orientation", "bool"):
            self.labels = deepcopy(original)
            rows = self.labels["sessions"][-1]["labels"]
            if mode == "missing": rows.pop()
            elif mode == "extra": rows.append({"trial_id": 800, "label": 1})
            elif mode == "duplicate": rows[-1] = deepcopy(rows[0])
            elif mode == "orientation": self.labels["positive_class"] = "opposite"
            else: rows[-1]["label"] = True
            with self.subTest(mode=mode), self.assertRaises(m.AuditError): self.audit()
        self.assertEqual(self.calls, 5)

    def test_duplicate_json_key_and_document_bounds_fail_before_labels(self):
        raw = encoded(self.predictions).replace(b'"schema":', b'"schema":"duplicate","schema":', 1)
        with self.assertRaises(m.AuditError): self.audit(raw)
        with patch.object(m, "MAX_DOCUMENT_BYTES", 10), self.assertRaises(m.AuditError): self.audit()
        self.assertEqual(self.calls, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
