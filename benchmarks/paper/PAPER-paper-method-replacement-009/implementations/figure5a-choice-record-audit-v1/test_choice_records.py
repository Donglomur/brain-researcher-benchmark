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


class ChoiceLogitSubmissionControls(unittest.TestCase):
    def setUp(self):
        self.plan, _, self.labels = fixture()
        self.support = encoded(self.plan)
        self.commitment = sha256(self.support).hexdigest()
        self.logits = {"schema": "figure5a-choice-logits/v1", "support_sha256": self.commitment,
                       "cases": []}
        for case in self.plan["cases"]:
            rows = [[0, i - 4] for i in range(len(case["trial_ids"]))]
            self.logits["cases"].append({
                "case_id": case["case_id"], "class_order": ["other-choice", self.plan["positive_class"]],
                "batches": [{"trial_ids": case["trial_ids"][:-1], "logits": rows[:-1]},
                            {"trial_ids": case["trial_ids"][-1:], "logits": rows[-1:]}]})

    def build(self, raw=None):
        return m.build_choice_predictions(self.support, encoded(self.logits) if raw is None else raw,
                                          expected_support_sha256=self.commitment)

    def audit(self, raw):
        return m.audit_choice_profile(self.support, raw, lambda: encoded(self.labels),
                                      expected_support_sha256=self.commitment)

    def test_preserves_auc_lost_by_argmax_and_retains_partial_batches(self):
        raw = self.build()
        report = self.audit(raw)
        self.assertEqual(report["prediction_records"], 49)
        self.assertEqual(report["rows"][0]["value"], .75)
        self.assertEqual(report["rows"][-1]["value"], .5)
        hard = json.loads(raw)
        for case in hard["cases"]:
            for row in case["predictions"]:
                self.assertLess(row["positive_probability"], .5)
                row["positive_probability"] = 0
        self.assertEqual(self.audit(encoded(hard))["rows"][0]["value"], .5)
        self.assertFalse(report["research_qualified"])
        self.assertIsNone(report["paper_win"])

    def test_reorders_batches_cases_and_typed_trials_to_support_order(self):
        expected = self.build()
        self.logits["cases"].reverse()
        for case in self.logits["cases"]:
            case["batches"].reverse()
            for batch in case["batches"]:
                batch["trial_ids"].reverse()
                batch["logits"].reverse()
        self.assertEqual(self.build(), expected)

    def test_explicit_reversed_class_order_selects_the_same_probability(self):
        expected = self.build()
        for case in self.logits["cases"]:
            case["class_order"].reverse()
            for batch in case["batches"]:
                for row in batch["logits"]:
                    row.reverse()
        self.assertEqual(self.build(), expected)

    def test_stable_softmax_handles_extreme_finite_logits_and_ties(self):
        rows = self.logits["cases"][0]["batches"][0]["logits"]
        rows[:] = [[-1e308, 1e308], [1e308, -1e308], [1e308, 1e308]]
        predictions = json.loads(self.build())["cases"][0]["predictions"]
        self.assertEqual([row["positive_probability"] for row in predictions[:3]], [1., 0., .5])

    def test_missing_extra_duplicate_foreign_cases_and_dropped_tail_fail(self):
        original = deepcopy(self.logits)
        for mode in ("missing", "extra", "duplicate", "foreign", "dropped_tail"):
            self.logits = deepcopy(original)
            cases = self.logits["cases"]
            if mode == "missing": cases.pop()
            elif mode == "extra": cases.append(deepcopy(cases[0]))
            elif mode == "duplicate": cases[-1] = deepcopy(cases[0])
            elif mode == "foreign": cases[-1]["case_id"] = "not-in-support"
            else: cases[-1]["batches"].pop()
            with self.subTest(mode=mode), self.assertRaises(m.AuditError): self.build()

    def test_trial_identity_and_batch_alignment_fail_closed(self):
        original = deepcopy(self.logits)
        for mode in ("duplicate", "foreign", "bool", "string_integer", "misaligned", "empty"):
            self.logits = deepcopy(original)
            batch = self.logits["cases"][0]["batches"][-1]
            if mode == "duplicate": batch["trial_ids"][0] = 0
            elif mode == "foreign": batch["trial_ids"][0] = 999
            elif mode == "bool": batch["trial_ids"][0] = True
            elif mode == "string_integer": batch["trial_ids"][0] = "3"
            elif mode == "misaligned": batch["logits"].append([0, 1])
            else: batch.update(trial_ids=[], logits=[])
            with self.subTest(mode=mode), self.assertRaises(m.AuditError): self.build()

    def test_hard_labels_wrong_width_and_invalid_logit_values_are_rejected(self):
        original = deepcopy(self.logits)
        for logits in (1, [0], [0, 1, 2], [True, 1], ["0", 1], [10**400, 0]):
            self.logits = deepcopy(original)
            self.logits["cases"][-1]["batches"][-1]["logits"][0] = logits
            with self.subTest(logits_type=type(logits).__name__), self.assertRaises(m.AuditError): self.build()
        raw = encoded(original).replace(b'"logits":[[0,-4]', b'"logits":[[0,1e309]', 1)
        with self.assertRaises(m.AuditError): self.build(raw)

    def test_class_orientation_is_required_not_inferred(self):
        original = deepcopy(self.logits)
        for classes in (["left", "right"], [self.plan["positive_class"]] * 2,
                        [0, 1], [self.plan["positive_class"]]):
            self.logits = deepcopy(original)
            self.logits["cases"][-1]["class_order"] = classes
            with self.subTest(classes=classes), self.assertRaises(m.AuditError): self.build()

    def test_changed_commitment_and_target_bearing_documents_fail(self):
        original = deepcopy(self.logits)
        self.logits["support_sha256"] = "b" * 64
        with self.assertRaises(m.AuditError): self.build()
        self.logits = deepcopy(original)
        self.logits["cases"][-1]["batches"][-1]["labels"] = [1]
        with self.assertRaises(m.AuditError): self.build()
        self.logits = original
        raw = encoded(self.logits).replace(b'"schema":', b'"schema":"duplicate","schema":', 1)
        with self.assertRaises(m.AuditError): self.build(raw)


if __name__ == "__main__":
    unittest.main(verbosity=2)
