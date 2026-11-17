"""Generated engineering controls; no authentic data or learned model results."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / "aasd_evaluator.py"
spec = importlib.util.spec_from_file_location("aasd_evaluator", MODULE_PATH)
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


def inventory(complete=False):
    people = [f"synthetic-person-{i:02}" for i in range(18)]
    result = {"schema": "aasd-inventory-v1", "participants": people, "mixture_folds": {"f0": 0, "f1": 1, "f2": 2}, "mixture_map_provenance": "GENERATED engineering control; not native identity evidence", "trials": []}
    for person in people:
        for block in range(7):
            for j in range(10):
                row = {"trial_id": f"{person}-b{block}-t{j}", "participant": person, "block_id": f"b{block}", "trial_in_block": j+1, "order": block*10+j+1, "condition": "active" if block < 6 else "passive", "status": "available" if complete or j == 0 and block in (0, 1, 2, 6) else "missing", "reason": "GENERATED missing-trial control", "mixture_family": f"f{block%3}", "duration_ns": 60*a.NS}
                if row["status"] == "available":
                    row.update({"sample_count": 7680, "sample_origin_ns": 0, "valid_spans": [[0, 7680]], "initial_state": 0, "key_events": [{"time_ns": 30*a.NS, "state": 1}], "state_mapping_provenance": "GENERATED state mapping"})
                result["trials"].append(row)
    return result


def row(cid, person, label):
    return {"case_id": cid, "participant": person, "label": label}


class StateAndContext(unittest.TestCase):
    def setUp(self):
        self.trial = inventory()["trials"][0]

    def test_exact_duration_majority_and_tie(self):
        t = self.trial
        t["key_events"] = [{"time_ns": 1_400_000_000, "state": 1}, {"time_ns": 1_600_000_000, "state": 0}]
        self.assertEqual(a.state_label(t, a.NS, 2*a.NS), (0, None))
        t["key_events"] = [{"time_ns": 1_500_000_000, "state": 1}]
        self.assertEqual(a.state_label(t, a.NS, 2*a.NS), (None, "majority_tie"))

    def test_half_open_events_and_no_retroactive_initialization(self):
        t = self.trial
        t["initial_state"] = None
        t["key_events"] = [{"time_ns": 1_100_000_000, "state": 1}]
        self.assertEqual(a.state_label(t, a.NS, 2*a.NS), (None, "uninitialized_state"))
        self.assertEqual(a.state_label(t, 2*a.NS, 3*a.NS), (1, None))
        t["key_events"] = [{"time_ns": a.NS, "state": 0}, {"time_ns": 2*a.NS, "state": 1}]
        self.assertEqual(a.state_label(t, a.NS, 2*a.NS), (0, None))
        self.assertEqual(a.state_label(t, 2*a.NS, 3*a.NS), (1, None))

    def test_complete_trial_has_exactly_58_common_context_windows(self):
        spans = [a.context_span(self.trial, k*a.NS)[0] for k in range(60)]
        self.assertEqual(sum(s is not None for s in spans), 58)
        self.assertEqual(spans[1], [64, 320])
        self.assertEqual(spans[58], [7360, 7616])
        self.assertTrue(all(s[1]-s[0] == 256 for s in spans if s))

    def test_missing_invalid_and_unaligned_context(self):
        t = self.trial
        t["sample_count"] = 300
        t["valid_spans"] = [[0, 300]]
        self.assertEqual(a.context_span(t, a.NS)[1], "missing_context")
        t["sample_count"] = 7680
        t["valid_spans"] = [[0, 100], [101, 7680]]
        self.assertEqual(a.context_span(t, a.NS)[1], "invalid_context")
        t["valid_spans"] = [[0, 100], [100, 7680]]
        self.assertEqual(a.context_span(t, a.NS), ([64, 320], None))
        t["sample_origin_ns"] = 1
        self.assertEqual(a.context_span(t, a.NS)[1], "unaligned_context")


class PopulationAndSplits(unittest.TestCase):
    def test_inventory_rejects_silent_census_narrowing(self):
        data = inventory()
        a.validate_inventory(data)
        for change in (lambda d: d["participants"].pop(), lambda d: d["trials"].pop(), lambda d: d["trials"][0].update(order=2), lambda d: d["trials"][0].update(condition="passive"), lambda d: d["trials"][1].pop("reason"), lambda d: d["mixture_folds"].update(f2=1)):
            bad = copy.deepcopy(data)
            change(bad)
            with self.assertRaises(a.ContractError):
                a.validate_inventory(bad)

    def test_events_and_states_fail_closed(self):
        data = inventory()
        for change in (lambda t: t.update(initial_state=True), lambda t: t.pop("initial_state"), lambda t: t.update(key_events=[{"time_ns": 1, "state": 0}, {"time_ns": 1, "state": 1}]), lambda t: t.update(key_events=[{"time_ns": -1, "state": 0}]), lambda t: t.update(valid_spans=[[0, 400], [300, 7680]])):
            bad = copy.deepcopy(data)
            change(bad["trials"][0])
            with self.assertRaises(a.ContractError):
                a.validate_inventory(bad)

    def test_full_cohort_grid_and_motor_guard(self):
        data = inventory(complete=True)
        first = data["trials"][0]
        first["key_events"] = [{"time_ns": 3_500_000_000, "state": 0}]
        prepared = a.prepare(data)
        active = [c for c in prepared["cases"] if c["condition"] == "active"]
        passive = [c for c in prepared["cases"] if c["condition"] == "passive"]
        self.assertEqual((len(active), len(passive), len(prepared["exclusions"])), (62640, 10440, 2520))
        cases = {c["start_ns"]: c for c in active if c["trial_id"] == first["trial_id"]}
        self.assertFalse(cases[a.NS]["guard_2s"])
        self.assertEqual(cases[a.NS]["keypress_distance_ns"], 1_500_000_000)
        self.assertTrue(cases[6*a.NS]["guard_2s"])
        self.assertEqual(cases[3*a.NS]["switches_in_target"], 0)
        self.assertIsNone(cases[3*a.NS]["transition_distance_ns"])
        self.assertEqual(sum(t["grid_windows"] for t in prepared["trials"]), 75600)

    def test_double_holdout_excludes_whole_person_and_family_fold(self):
        data = inventory()
        cells = a.split_plan(data)
        self.assertEqual(len(cells), 54)
        lookup = {t["trial_id"]: t for t in data["trials"]}
        cases = {c["case_id"]: c for c in a.prepare(data)["cases"]}
        test_ids, passive_ids = [], []
        for cell in cells:
            for tid in cell["train_trial_ids"]:
                t = lookup[tid]
                self.assertNotEqual(t["participant"], cell["participant"])
                self.assertNotEqual(data["mixture_folds"][t["mixture_family"]], cell["held_mixture_fold"])
                self.assertEqual(t["condition"], "active")
            for cid in cell["passive_diagnostic_case_ids"]:
                self.assertEqual(cases[cid]["condition"], "passive")
                self.assertEqual(cases[cid]["participant"], cell["participant"])
                self.assertEqual(cases[cid]["fold"], cell["held_mixture_fold"])
                passive_ids.append(cid)
            for cid in cell["test_case_ids"]:
                self.assertEqual(cases[cid]["participant"], cell["participant"])
                self.assertEqual(cases[cid]["fold"], cell["held_mixture_fold"])
                test_ids.append(cid)
        self.assertEqual(len(passive_ids), len(set(passive_ids)))
        self.assertEqual(set(passive_ids), {c["case_id"] for c in cases.values() if c["condition"] == "passive"})
        self.assertEqual(len(test_ids), len(set(test_ids)))
        self.assertEqual(set(test_ids), {c["case_id"] for c in cases.values() if c["condition"] == "active"})


class MetricOracles(unittest.TestCase):
    def test_counts_pool_before_balanced_accuracy(self):
        # Independent source worker oracle: fold sizes differ sharply.
        rows, predictions, folded = [], {}, []
        for f, counts in enumerate(((90, 0, 1, 0), (0, 1, 0, 10), (9, 0, 0, 9))):
            local = []
            for y, guessed, count in ((0, 0, counts[0]), (0, 1, counts[1]), (1, 0, counts[2]), (1, 1, counts[3])):
                for _ in range(count):
                    cid = str(len(rows))
                    r = row(cid, "person", y)
                    rows.append(r)
                    local.append(r)
                    predictions[cid] = float(guessed)
            folded.append(a.metrics(local, predictions)["balanced_accuracy"])
        self.assertAlmostEqual(a.metrics(rows, predictions)["balanced_accuracy"], .97)
        self.assertAlmostEqual(sum(folded)/3, 2/3)

    def test_one_class_folds_and_participant_denominator(self):
        people = [str(i) for i in range(18)]
        rows = [row(f"{p}L", p, 0) for p in people] + [row(f"{p}R", p, 1) for p in people[:-1]]
        pred = {r["case_id"]: float(r["label"]) for r in rows}
        result = a.population_metrics(rows, people, pred)
        self.assertIsNone(result["macro"]["balanced_accuracy"]["all_18"])
        self.assertEqual(result["macro"]["balanced_accuracy"]["eligible_participants"], 17)
        self.assertEqual(result["macro"]["balanced_accuracy"]["eligible_participant_mean"], 1)
        self.assertEqual(result["macro"]["log_loss"]["eligible_participants"], 18)
        self.assertEqual(result["participants"][-1]["recall_left"], 1)
        self.assertIsNone(result["participants"][-1]["recall_right"])

    def test_logloss_calibration_and_fixed_tie_rule(self):
        rows = [row("a", "p", 0), row("b", "p", 1)]
        result = a.metrics(rows, {"a": .25, "b": .5})
        self.assertAlmostEqual(result["log_loss"], (-math.log(.75)-math.log(.5))/2)
        self.assertAlmostEqual(result["brier"], (.25**2+.5**2)/2)
        self.assertAlmostEqual(result["ece_10"], .375)
        self.assertEqual(result["balanced_accuracy"], 1)
        result = a.metrics(rows, {"a": 1., "b": 0.})
        self.assertTrue(math.isfinite(result["log_loss"]))

    def test_prediction_contract_cannot_shrink_scoring_denominator(self):
        cases = [row("a", "p", 0), row("b", "p", 1)]
        valid = [{"case_id": "a", "p_right": .2}, {"case_id": "b", "p_right": .8}]
        a.validate_predictions(cases, valid)
        for bad in (valid[:-1], valid+valid[:1], valid+[{"case_id": "c", "p_right": .2}], [{"case_id": "a", "p_right": float("nan")}, valid[1]], [{"case_id": "a", "p_right": True}, valid[1]], [{"case_id": "a", "p_right": 1.01}, valid[1]]):
            with self.assertRaises(a.ContractError):
                a.validate_predictions(cases, bad)

    def test_participant_bootstrap_and_exact_paired_null(self):
        people = [str(i) for i in range(18)]
        rows = [row(f"{p}{y}", p, y) for p in people for y in (0, 1)]
        perfect = {r["case_id"]: float(r["label"]) for r in rows}
        chance = {r["case_id"]: 0. for r in rows}
        result = a.paired_uncertainty(rows, people, perfect, chance, 100, 123)
        self.assertEqual(result["mean_difference"], .5)
        self.assertEqual(result["bootstrap_ci_95"], [.5, .5])
        self.assertEqual(result["exact_sign_flip_p_two_sided"], 2/(2**18))
        null = a.paired_uncertainty(rows, people, perfect, perfect, 100, 123)
        self.assertEqual(null["exact_sign_flip_p_two_sided"], 1)


class FullPath(unittest.TestCase):
    def test_score_retains_passive_and_all_trial_coverage(self):
        data = inventory()
        prepared = a.prepare(data)
        predictions = [{"case_id": c["case_id"], "p_right": .9 if c["label"] else .1} for c in prepared["cases"]]
        result = a.score(data, predictions)
        self.assertEqual(result["primary"]["macro"]["balanced_accuracy"]["all_18"], 1)
        self.assertEqual(result["passive_motor_report_diagnostic"]["macro"]["balanced_accuracy"]["all_18"], 1)
        self.assertEqual(len(result["per_mixture_fold"]), 54)
        self.assertEqual(len(result["coverage"]), 36)
        self.assertEqual(len(result["block_order_strata"]), 108)
        missing_block = next(b for b in result["block_order_strata"] if b["block_id"] == "b3")
        self.assertEqual(missing_block["n"], 0)
        self.assertEqual(missing_block["excluded_windows"], 600)
        self.assertEqual(missing_block["excluded_undefined_labels"], 600)
        self.assertEqual(len(result["trial_accounting"]), 1260)
        self.assertEqual(result["scientific_qualification"], "unknown")
        self.assertFalse(result["native_data_validated"])
        self.assertTrue(result["holds"])
        with self.assertRaises(a.ContractError):
            active_ids = {c["case_id"] for c in prepared["cases"] if c["condition"] == "active"}
            a.score(data, [p for p in predictions if p["case_id"] in active_ids])

    def test_cli_and_duplicate_json_rejection(self):
        data = inventory()
        with tempfile.TemporaryDirectory() as td:
            source, output = Path(td)/"inventory.json", Path(td)/"out.json"
            source.write_text(json.dumps(data))
            process = subprocess.run([sys.executable, str(MODULE_PATH), "prepare", str(source), "--output", str(output)], capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(json.loads(output.read_text())["schema"], "aasd-prepared-evaluator-only-v1")
            source.write_text('{"schema": "x", "schema": "aasd-inventory-v1"}')
            process = subprocess.run([sys.executable, str(MODULE_PATH), "prepare", str(source), "--output", str(output)], capture_output=True, text=True)
            self.assertEqual(process.returncode, 2)
            self.assertIn("duplicate JSON key", process.stderr)


if __name__ == "__main__":
    unittest.main()
