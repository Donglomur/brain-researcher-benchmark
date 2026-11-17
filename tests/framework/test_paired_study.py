"""Invented engineering examples; no recorded benchmark outcomes are loaded."""
import copy
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location(
    "paired_report", Path(__file__).resolve().parents[1] / "report_neuroscience_paired_study.py")
REPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REPORT)


def plan():
    return {"schema_version": 1, "study_id": "INVENTED-study", "arms": list(REPORT.ARMS),
            "tasks": [{"task_id": "INVENTED-paper", "family_id": "INVENTED-family",
                       "contract_id": "contract-v1", "common_inputs_id": "inputs-v1",
                       "baseline_id": "matched-reference-v1", "budget_profile_id": "budget-v1",
                       "metric": "mse", "direction": "minimize", "replicates": ["seed1"]}]}


def attempt(task, arm, reproduction="success", candidate=None, baseline=5.0, replicate="seed1"):
    return {"task_id": task["task_id"], "replicate": replicate, "arm": arm,
            **{key: task[key] for key in REPORT.CONTEXT},
            "reproduction": reproduction, "operator_evidence_id": "INVENTED-operator-record",
            "improvement": {"status": "unavailable"} if candidate is None else
                {"status": "scored", "candidate": candidate, "baseline": baseline}}


def records(p, attempts):
    return {"schema_version": 1, "study_id": p["study_id"], "attempts": attempts}


class PairedReportTests(unittest.TestCase):
    def test_missing_attempts_keep_full_assignment_and_unknown_bounds(self):
        p = plan()
        out = REPORT.summarize(p, records(p, []))
        self.assertEqual(out["assigned_pairs"], 1)
        self.assertEqual(out["records_present"], 0)
        self.assertEqual(out["equal_task_success_effect_bounds"], [-1, 1])
        self.assertIsNone(out["tasks"][0]["code_minus_no_code_success_point"])
        self.assertEqual(out["tasks"][0]["improvement_pairs_scored"], 0)

    def test_infrastructure_error_is_not_scientific_failure(self):
        p = plan(); task = p["tasks"][0]
        rows = [attempt(task, REPORT.ARMS[0], "success"),
                attempt(task, REPORT.ARMS[1], "infrastructure_error")]
        out = REPORT.summarize(p, records(p, rows))
        self.assertEqual(out["equal_task_success_effect_bounds"], [-1, 0])
        self.assertEqual(out["tasks"][0]["reproduction_status_counts"][REPORT.ARMS[1]]["failure"], 0)

    def test_failure_and_abstention_remain_in_denominator(self):
        p = plan(); task = p["tasks"][0]; task["replicates"] = ["seed1", "seed2"]
        rows = [attempt(task, REPORT.ARMS[0], "failure", replicate="seed1"),
                attempt(task, REPORT.ARMS[1], "success", replicate="seed1"),
                attempt(task, REPORT.ARMS[0], "success", replicate="seed2"),
                attempt(task, REPORT.ARMS[1], "abstained", replicate="seed2")]
        out = REPORT.summarize(p, records(p, rows))
        self.assertEqual(out["equal_task_success_effect_bounds"], [0, 0])

    def test_improvement_scoring_does_not_filter_reproduction_failures(self):
        p = plan(); task = p["tasks"][0]
        rows = [attempt(task, REPORT.ARMS[0], "failure", 4),
                attempt(task, REPORT.ARMS[1], "success", 3)]
        out = REPORT.summarize(p, records(p, rows))["tasks"][0]
        self.assertEqual(out["improvement_pairs_scored"], 1)
        self.assertEqual(out["improvement_pairs"][0]["paper_and_data_gain"], 1)
        self.assertEqual(out["conditional_mean_code_minus_no_code_gain"], 1)

    def test_metric_direction_and_negative_gain_preserved(self):
        p = plan(); task = p["tasks"][0]; task["direction"] = "maximize"; task["metric"] = "r2"
        rows = [attempt(task, REPORT.ARMS[0], candidate=.4, baseline=.5),
                attempt(task, REPORT.ARMS[1], candidate=.2, baseline=.5)]
        out = REPORT.summarize(p, records(p, rows))["tasks"][0]
        self.assertAlmostEqual(out["conditional_mean_code_minus_no_code_gain"], -.2)
        self.assertAlmostEqual(out["improvement_pairs"][0]["paper_data_official_code_gain"], -.3)

    def test_family_and_task_weighting_do_not_count_extra_replicates_as_papers(self):
        p = plan(); first = p["tasks"][0]
        second, third = copy.deepcopy(first), copy.deepcopy(first)
        second["task_id"] = "INVENTED-paper2"
        third.update(task_id="INVENTED-paper3", family_id="INVENTED-family2", replicates=["seed1", "seed2"])
        p["tasks"] += [second, third]
        rows = []
        for task in p["tasks"]:
            for rep in task["replicates"]:
                better = task["family_id"] == "INVENTED-family"
                rows += [attempt(task, REPORT.ARMS[0], "failure" if better else "success", replicate=rep),
                         attempt(task, REPORT.ARMS[1], "success" if better else "failure", replicate=rep)]
        out = REPORT.summarize(p, records(p, rows))
        self.assertEqual(out["assigned_pairs"], 4)
        self.assertAlmostEqual(out["equal_task_success_effect_bounds"][0], 1/3)
        self.assertEqual(out["equal_declared_family_success_effect_bounds"], [0, 0])

    def test_no_raw_improvement_average_across_tasks(self):
        p = plan(); first = p["tasks"][0]
        second = copy.deepcopy(first); second.update(task_id="INVENTED-paper2", metric="accuracy", direction="maximize")
        p["tasks"].append(second)
        rows = [attempt(t, arm, candidate=value) for t in p["tasks"]
                for arm, value in zip(REPORT.ARMS, (4, 3))]
        out = REPORT.summarize(p, records(p, rows))
        self.assertEqual([t["conditional_mean_code_minus_no_code_gain"] for t in out["tasks"]], [1, -1])
        self.assertNotIn("mean_improvement", out)

    def test_unpaired_improvement_does_not_create_zero_partner(self):
        p = plan(); task = p["tasks"][0]
        out = REPORT.summarize(p, records(p, [attempt(task, REPORT.ARMS[0], candidate=4)]))
        self.assertEqual(out["tasks"][0]["improvement_pairs_scored"], 0)
        self.assertIsNone(out["tasks"][0]["conditional_mean_code_minus_no_code_gain"])

    def test_duplicate_retries_rejected(self):
        p = plan(); row = attempt(p["tasks"][0], REPORT.ARMS[0])
        with self.assertRaises(ValueError):
            REPORT.summarize(p, records(p, [row, row]))

    def test_mismatched_baseline_context_or_budget_rejected(self):
        for field in REPORT.CONTEXT:
            with self.subTest(field=field):
                p = plan(); row = attempt(p["tasks"][0], REPORT.ARMS[0]); row[field] = "different"
                with self.assertRaises(ValueError): REPORT.summarize(p, records(p, [row]))
        p = plan(); task = p["tasks"][0]
        with self.assertRaises(ValueError):
            REPORT.summarize(p, records(p, [attempt(task, REPORT.ARMS[0], candidate=1, baseline=2),
                                           attempt(task, REPORT.ARMS[1], candidate=1, baseline=3)]))

    def test_unassigned_attempt_rejected(self):
        for field in ("task_id", "arm", "replicate"):
            with self.subTest(field=field):
                p = plan(); row = attempt(p["tasks"][0], REPORT.ARMS[0]); row[field] = "unassigned"
                with self.assertRaises(ValueError): REPORT.summarize(p, records(p, [row]))

    def test_invalid_and_overflow_arithmetic_rejected(self):
        for value in (True, float("nan"), float("inf"), 10**1000, "1.0"):
            with self.subTest(value_type=type(value).__name__):
                p = plan(); row = attempt(p["tasks"][0], REPORT.ARMS[0], candidate=value)
                with self.assertRaises(ValueError): REPORT.summarize(p, records(p, [row]))
        p = plan(); row = attempt(p["tasks"][0], REPORT.ARMS[0], candidate=1e308, baseline=-1e308)
        with self.assertRaises(ValueError): REPORT.summarize(p, records(p, [row]))

    def test_json_duplicate_and_nonfinite_literals_rejected(self):
        for body in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}'):
            with self.assertRaises(ValueError): REPORT.parse_json(body)

    def test_integer_precision_cannot_hide_baseline_mismatch_or_gain(self):
        p = plan(); task = p["tasks"][0]
        rows = [attempt(task, REPORT.ARMS[0], candidate=0, baseline=2**53),
                attempt(task, REPORT.ARMS[1], candidate=0, baseline=2**53+1)]
        with self.assertRaises(ValueError): REPORT.summarize(p, records(p, rows))
        row = attempt(task, REPORT.ARMS[0], candidate=2**53+1, baseline=2**53)
        with self.assertRaises(ValueError): REPORT.summarize(p, records(p, [row]))
        self.assertEqual(REPORT.number(2**53), 2**53)
        self.assertEqual(REPORT.number(2**53+2), 2**53+2)

    def test_records_order_does_not_select_favorable_outcome(self):
        p = plan(); task = p["tasks"][0]
        rows = [attempt(task, REPORT.ARMS[0], candidate=5), attempt(task, REPORT.ARMS[1], candidate=3)]
        self.assertEqual(REPORT.summarize(p, records(p, rows)), REPORT.summarize(p, records(p, rows[::-1])))

    def test_extra_score_on_unavailable_record_rejected(self):
        p = plan(); row = attempt(p["tasks"][0], REPORT.ARMS[0]); row["improvement"]["candidate"] = 0
        with self.assertRaises(ValueError): REPORT.summarize(p, records(p, [row]))

    def test_empty_or_duplicate_roster_rejected(self):
        p = plan(); p["tasks"] = []
        with self.assertRaises(ValueError): REPORT.summarize(p, records(p, []))
        p = plan(); p["tasks"] *= 2
        with self.assertRaises(ValueError): REPORT.summarize(p, records(p, []))


if __name__ == "__main__":
    unittest.main()
