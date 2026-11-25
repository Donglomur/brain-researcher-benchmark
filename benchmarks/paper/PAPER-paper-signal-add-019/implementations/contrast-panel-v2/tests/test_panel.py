"""Generated analytic controls; no authentic observations or scientific fits."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("contrast_panel", PACKAGE / "panel.py")
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def fixture(ragged=True):
    rows = []
    for participant in ("0_epo", "1_epo"):
        for condition in ("accuracy", "speed"):
            for contrast in (5, 20, 80):
                if ragged and participant == "1_epo" and contrast == 5:
                    continue
                rows.append(dict(participant=participant, epoch=f"{condition}-{contrast}",
                    condition=condition, contrast_percent=contrast, side="left", response="right",
                    rt_ms=700 + contrast, model_end_ms=710 + contrast,
                    event_times_ms=[0, 100, 200, 400, 500]))
    inventory = [dict(participant=r["participant"], epoch=r["epoch"], disposition="retained") for r in rows]
    neural = dict(schema="decision-times-export-v1", purpose="engineering_control",
        sample_rate_hz=512, time_unit="ms", contrast_unit="percent", time_origin="stimulus_onset",
        point_time_method="explicit_point_estimates", expected_participants=["0_epo", "1_epo"],
        trial_inventory=inventory, trials=rows)
    behavior = dict(time_unit="ms", contrast_unit="percent", trial_inventory=copy.deepcopy(inventory),
        trials=[{k: v for k, v in r.items() if k not in ("model_end_ms", "event_times_ms")} for r in rows])
    return dict(schema="decision-times-panel-targets-v2", hmp=neural, behavior=behavior)


def method(targets, name):
    # Predictions here are deliberately generated constants, not fit results.
    records = {"held_out": [], "full_data": []}
    roster = targets["hmp"]["expected_participants"]
    for target in p.TARGETS:
        raw = targets["behavior"]["trials"] if target == "rt" else targets["hmp"]["trials"]
        for condition in p.CONDITIONS:
            selected = [r for r in raw if r["condition"] == condition]
            grid = sorted({r["contrast_percent"] for r in selected})
            for participant in roster:
                available = {r["contrast_percent"] for r in selected if r["participant"] == participant}
                for contrast in grid:
                    for mode in records:
                        records[mode].append(dict(target=target, condition=condition, participant=participant,
                            contrast_percent=contrast, fit_contrasts_percent=sorted(available - {contrast} if mode == "held_out" else available),
                            latency_ms=0, probability_correct=.5 if name == "fechner" else None))
    return dict(method_id=name, targets_sha256=p.target_digest(targets), latency_selection="all_responded",
                time_unit="ms", contrast_unit="percent", **records)


def submission(targets):
    return dict(schema="decision-times-panel-predictions-v2",
        access_condition="paper_data",
        references=[method(targets, name) for name in p.AUTHOR_MODELS], candidate=method(targets, "free_candidate"))


def first_cell(result):
    return result["candidate"]["cells"][0]


class SourcePanelControls(unittest.TestCase):
    def test_reproduction_is_separate_complete_outcome(self):
        target = fixture()
        bundle = submission(target)
        del bundle["candidate"]
        bundle["reproduction"] = copy.deepcopy(bundle["references"])
        out = p.evaluate(target, bundle)
        self.assertIsNone(out["candidate"])
        self.assertEqual(out["paired_differences"], [])
        self.assertEqual(len(out["reproduction"]["differences"]), 54)
        self.assertTrue(all(r["reproduced_minus_reference_source_rmse_ms"] == 0
                            for r in out["reproduction"]["differences"]))
        self.assertIsNone(out["reproduction"]["reproduction_pass"])
        bundle["reproduction"].pop()
        with self.assertRaisesRegex(ValueError, "all three source"):
            p.evaluate(target, bundle)

    def test_missing_observation_still_requires_participant_prediction(self):
        target = fixture()
        bundle = submission(target)
        for r in bundle["candidate"]["held_out"]:
            if r["target"] == p.TARGETS[0] and r["participant"] == "1_epo" and r["contrast_percent"] == 5:
                self.assertEqual(r["fit_contrasts_percent"], [20, 80])
                r["latency_ms"] = 100
        out = first_cell(p.evaluate(target, bundle))
        # Observed at contrast 5: only participant 0, at 0 ms.
        # Predictions: participants 0 and 1, at 0 and 100 ms.
        self.assertAlmostEqual(out["source_rmse_ms"], 50 / math.sqrt(3))
        self.assertEqual(out["folds"][0]["observed_participants"], 1)
        self.assertEqual(out["folds"][0]["predicted_participants"], 2)
        bundle["candidate"]["held_out"] = [r for r in bundle["candidate"]["held_out"]
            if not (r["participant"] == "1_epo" and r["contrast_percent"] == 5)]
        with self.assertRaisesRegex(ValueError, "global contrast grid"):
            p.evaluate(target, bundle)

    def test_source_pooled_observations_equal_participant_predictions(self):
        target = fixture(False)
        base = next(r for r in target["hmp"]["trials"] if r["participant"] == "0_epo"
                    and r["condition"] == "accuracy" and r["contrast_percent"] == 5)
        for i in range(8):
            new = copy.deepcopy(base)
            new["epoch"] += f"-extra{i}"
            target["hmp"]["trials"].append(new)
            inv = dict(participant=new["participant"], epoch=new["epoch"], disposition="retained")
            target["hmp"]["trial_inventory"].append(inv)
            target["behavior"]["trials"].append({k: v for k, v in new.items() if k not in ("event_times_ms", "model_end_ms")})
            target["behavior"]["trial_inventory"].append(copy.deepcopy(inv))
        for r in target["hmp"]["trials"]:
            if r["participant"] == "1_epo" and r["condition"] == "accuracy" and r["contrast_percent"] == 5:
                r["event_times_ms"][0] = 100
        bundle = submission(target)
        for r in bundle["candidate"]["held_out"]:
            if r["target"] == p.TARGETS[0] and r["participant"] == "1_epo" and r["contrast_percent"] == 5:
                r["latency_ms"] = 100
        out = first_cell(p.evaluate(target, bundle))
        self.assertAlmostEqual(out["source_rmse_ms"], 40 / math.sqrt(3))
        fold = out["folds"][0]
        self.assertEqual(fold["observed_pooled_ms"], 10)
        self.assertEqual(fold["observed_participant_equal_ms"], 50)
        self.assertEqual(fold["predicted_participant_equal_ms"], 50)

    def test_full_panel_and_free_candidate_name(self):
        target = fixture()
        out = p.evaluate(target, submission(target))
        self.assertEqual(len(out["references"]), 3)
        self.assertEqual(len(out["candidate"]["cells"]), 18)
        self.assertEqual(len(out["paired_differences"]), 54)
        self.assertEqual({r["target"] for r in out["candidate"]["cells"]}, set(p.TARGETS))
        self.assertTrue(all(r["candidate_minus_reference_rmse_ms"] == 0 for r in out["paired_differences"]))
        self.assertIsNone(out["binary_reward"])
        self.assertEqual(out["scientific_runs"], 0)

    def test_full_data_r2_does_not_use_held_out_predictions(self):
        target = fixture()
        bundle = submission(target)
        for row in bundle["candidate"]["full_data"]:
            if row["target"] == "rt":
                row["latency_ms"] = 700 + row["contrast_percent"]
        out = p.evaluate(target, bundle)
        rt = [r for r in out["candidate"]["cells"] if r["target"] == "rt"]
        self.assertTrue(all(r["full_data_latency_r2"] == 1 for r in rt))
        self.assertTrue(all(r["source_rmse_ms"] > 700 for r in rt))
        self.assertIsNone(first_cell(out)["full_data_latency_r2"])

    def test_accuracy_uses_all_responses_and_full_data_predictions(self):
        target = fixture()
        for rows in (target["hmp"]["trials"], target["behavior"]["trials"]):
            for row in rows:
                correct = row["contrast_percent"] == 80 or (row["contrast_percent"] == 20 and row["participant"] == "0_epo")
                row["response"] = "left" if correct else "right"
        bundle = submission(target)
        for row in bundle["references"][0]["full_data"]:
            row["probability_correct"] = {5: 0, 20: .5, 80: 1}[row["contrast_percent"]]
        out = p.evaluate(target, bundle)
        self.assertTrue(all(row["full_data_accuracy_r2"] == 1 for row in out["references"][0]["cells"]))
        self.assertTrue(all(row["full_data_accuracy_r2"] is None for row in out["candidate"]["cells"]))

    def test_distinct_behavior_population_is_preserved(self):
        target = fixture()
        extra = copy.deepcopy(target["behavior"]["trials"][0])
        extra.update(epoch="behavior-only", rt_ms=1000)
        target["behavior"]["trials"].append(extra)
        target["behavior"]["trial_inventory"].append(dict(participant=extra["participant"], epoch=extra["epoch"], disposition="retained"))
        out = p.evaluate(target, submission(target))
        self.assertEqual(out["behavioral_trial_count"], out["hmp_trial_count"] + 1)
        rt = next(r for r in out["candidate"]["cells"] if r["target"] == "rt" and r["condition"] == "accuracy")
        self.assertEqual(rt["folds"][0]["observed_pooled_ms"], 852.5)
        self.assertEqual(first_cell(out)["folds"][0]["observed_trials"], 1)

    def test_no_automatic_behavioral_substitution(self):
        target = fixture()
        del target["behavior"]
        with self.assertRaisesRegex(ValueError, "separate behavioral"):
            p.prepare(target)

    def test_changed_targets_rejected_for_both_reference_and_candidate(self):
        target = fixture()
        bundle = submission(target)
        target["hmp"]["trials"][0]["event_times_ms"][0] = 1
        with self.assertRaisesRegex(ValueError, "target identity"):
            p.evaluate(target, bundle)
        target = fixture()
        bundle = submission(target)
        bundle["candidate"]["targets_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "target identity"):
            p.evaluate(target, bundle)

    def test_leakage_partial_panels_and_wrong_selection_rejected(self):
        target = fixture()
        for mutate, pattern in [
            (lambda b: b["candidate"]["held_out"][0]["fit_contrasts_percent"].append(5), "leakage"),
            (lambda b: b["candidate"]["full_data"].pop(), "global contrast grid"),
            (lambda b: b["references"].pop(), "three author"),
            (lambda b: b["candidate"].update(latency_selection="correct_only"), "all responded"),
            (lambda b: b["candidate"].update(time_unit="s"), "units"),
            (lambda b: b["references"][0]["full_data"][0].pop("probability_correct"), "partial accuracy"),
        ]:
            bundle = submission(target)
            mutate(bundle)
            with self.subTest(pattern=pattern), self.assertRaisesRegex(ValueError, pattern):
                p.evaluate(target, bundle)

    def test_duplicate_nonfinite_mismatched_population_and_rate_rejected(self):
        target = fixture()
        bundle = submission(target)
        bundle["candidate"]["held_out"].append(bundle["candidate"]["held_out"][0])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            p.evaluate(target, bundle)
        for value in (float("nan"), True):
            bundle = submission(target)
            bundle["candidate"]["held_out"][0]["latency_ms"] = value
            with self.assertRaisesRegex(ValueError, "finite number"):
                p.evaluate(target, bundle)
        target["behavior"]["trials"][0]["rt_ms"] += 1
        with self.assertRaisesRegex(ValueError, "metadata mismatch"):
            p.prepare(target)
        target = fixture()
        target["hmp"]["sample_rate_hz"] = 100
        with self.assertRaisesRegex(ValueError, "512"):
            p.prepare(target)

    def test_keyed_order_independence_and_interval_identities(self):
        target = fixture()
        before = p.evaluate(target, submission(target))
        target["hmp"]["trials"].reverse()
        target["behavior"]["trials"].reverse()
        bundle = submission(target)
        bundle["candidate"]["held_out"].reverse()
        bundle["candidate"]["full_data"].reverse()
        after = p.evaluate(target, bundle)
        self.assertEqual(before["candidate"], after["candidate"])
        cells = after["candidate"]["cells"]
        self.assertEqual(next(r for r in cells if r["target"] == "encoding")["source_rmse_ms"], 200)
        self.assertEqual(next(r for r in cells if r["target"] == "decision")["source_rmse_ms"], 300)

    def test_cli_rejects_duplicate_json_fields_before_scoring(self):
        target = fixture()
        valid = [json.dumps(target), json.dumps(submission(target))]
        cases = [
            (0, '{"schema":"conflicting",' + valid[0][1:]),
            (1, '{"access_condition":"paper_data_author_code",' + valid[1][1:]),
            (1, valid[1].replace('"latency_ms": 0', '"latency_ms": 999, "latency_ms": 0', 1)),
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = [root / "targets.json", root / "predictions.json"]
            for path, body in zip(paths, valid):
                path.write_text(body)
            for index, body in cases:
                with self.subTest(input=index, nested='latency_ms' in body[:100]):
                    paths[index].write_text(body)
                    output = root / "result.json"
                    run = subprocess.run([sys.executable, "-I", "-S", "-B", str(PACKAGE / "panel.py"),
                        *map(str, paths), "--output", str(output)], capture_output=True, text=True)
                    self.assertNotEqual(run.returncode, 0)
                    self.assertIn("duplicate JSON object key", run.stderr)
                    self.assertFalse(output.exists())
                    paths[index].write_text(valid[index])

    def test_cli_and_file_pins(self):
        target = fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "targets.json").write_text(json.dumps(target))
            (root / "predictions.json").write_text(json.dumps(submission(target)))
            subprocess.run([sys.executable, "-B", str(PACKAGE / "panel.py"), str(root / "targets.json"),
                            str(root / "predictions.json"), "--output", str(root / "result.json")], check=True)
            output = json.loads((root / "result.json").read_text())
            self.assertEqual(output["qualification"], "software_component_only")
            self.assertEqual(len(output["input_file_sha256"]["targets"]), 64)


if __name__ == "__main__":
    unittest.main()
