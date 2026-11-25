"""Generated pairing controls; no authentic inputs or scientific fits."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("decision_times_pair", PACKAGE / "pair.py")
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def fixture(people=2):
    roster = [f"{i}_epo" for i in range(people)]
    rows = []
    for i, person in enumerate(roster):
        for condition in p.panel.CONDITIONS:
            for contrast in (5, 20, 80):
                if i == 1 and contrast == 5:
                    continue
                rows.append(dict(participant=person, epoch=f"{condition}-{contrast}",
                    condition=condition, contrast_percent=contrast, side="left",
                    response="left" if contrast == 80 else "right", rt_ms=700 + contrast,
                    model_end_ms=710 + contrast, event_times_ms=[0, 100, 200, 400, 500]))
    inventory = [dict(participant=r["participant"], epoch=r["epoch"], disposition="retained") for r in rows]
    hmp = dict(schema="decision-times-export-v1", purpose="engineering_control", sample_rate_hz=512,
        time_unit="ms", contrast_unit="percent", time_origin="stimulus_onset",
        point_time_method="explicit_point_estimates", expected_participants=roster,
        trial_inventory=inventory, trials=rows)
    behavior = dict(time_unit="ms", contrast_unit="percent", trial_inventory=copy.deepcopy(inventory),
        trials=[{k: v for k, v in r.items() if k not in ("event_times_ms", "model_end_ms")} for r in rows])
    extra = copy.deepcopy(behavior["trials"][0])
    extra.update(epoch="behavior-only", rt_ms=1000)
    behavior["trials"].append(extra)
    behavior["trial_inventory"].append(dict(participant=extra["participant"], epoch=extra["epoch"], disposition="retained"))
    targets = dict(schema="decision-times-panel-targets-v2", hmp=hmp, behavior=behavior)
    prepared = p.panel.prepare(targets)
    def method(name):
        rows = {"held_out": [], "full_data": []}
        for (target, condition), item in prepared.items():
            for person in item["participants"]:
                for x in item["contrasts"]:
                    for mode in rows:
                        row = dict(target=target, condition=condition, participant=person, contrast_percent=x,
                            fit_contrasts_percent=[v for v in item["support"][person] if mode == "full_data" or v != x],
                            latency_ms=0)
                        if name == "fechner" and mode == "full_data":
                            row["probability_correct"] = .5
                        rows[mode].append(row)
        return dict(method_id=name, targets_sha256=p.panel.target_digest(targets),
                    latency_selection="all_responded", time_unit="ms", contrast_unit="percent", **rows)
    left = dict(schema="decision-times-panel-predictions-v2", access_condition="paper_data",
                references=[method(name) for name in p.panel.AUTHOR_MODELS], candidate=method("free-left"))
    left["reproduction"] = copy.deepcopy(left["references"])
    right = copy.deepcopy(left)
    right["access_condition"] = "paper_data_author_code"
    right["candidate"]["method_id"] = "free-right"
    return targets, left, right


class PairedControls(unittest.TestCase):
    def test_cli_rejects_duplicate_fields_in_every_input(self):
        valid = [json.dumps(value) for value in fixture(1)]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = [root / name for name in ("targets.json", "left.json", "right.json")]
            for path, body in zip(paths, valid):
                path.write_text(body)
            for index in range(3):
                with self.subTest(input=index):
                    field = "schema" if index == 0 else "access_condition"
                    paths[index].write_text('{"' + field + '":"conflicting",' + valid[index][1:])
                    output = root / "result.json"
                    run = subprocess.run([sys.executable, "-I", "-S", "-B", str(PACKAGE / "pair.py"),
                        *map(str, paths), "--output", str(output)], capture_output=True, text=True)
                    self.assertNotEqual(run.returncode, 0)
                    self.assertIn("duplicate JSON object key", run.stderr)
                    self.assertFalse(output.exists())
                    paths[index].write_text(valid[index])

    def test_complete_26_person_panel_preserves_all_outcomes(self):
        targets, left, right = fixture(26)
        out = p.evaluate_pair(targets, left, right)
        self.assertEqual(len(out["candidate"]["cells"]), 18)
        self.assertEqual(len(out["reproduction"]["findings"]), 126)
        self.assertEqual({r["model"] for r in out["reproduction"]["findings"] if r["metric"] == "full_data_accuracy_r2"}, {"fechner"})
        for arm in out["arms"].values():
            self.assertEqual(arm["behavioral_trial_count"], arm["hmp_trial_count"] + 1)
            self.assertEqual(arm["candidate"]["cells"][0]["folds"][0]["predicted_participants"], 26)
        self.assertIsNone(out["paper_win"])
        self.assertIsNone(out["reproduction_pass"])
        self.assertFalse(out["scientific_qualification"])

    def test_signed_differences_and_undefined_companions_remain(self):
        targets, left, right = fixture()
        for row in right["candidate"]["held_out"]:
            row["latency_ms"] = 12
        for row in right["candidate"]["full_data"]:
            row["probability_correct"] = .5
        out = p.evaluate_pair(targets, left, right)
        cell = out["candidate"]["cells"][0]
        self.assertEqual(cell["source_rmse_ms"]["author_code_minus_paper_data"], 12)
        self.assertEqual(cell["full_data_latency_r2"]["undefined_in"], list(p.ACCESS))
        self.assertEqual(cell["full_data_accuracy_r2"]["undefined_in"], ["paper_data"])
        self.assertIsNone(cell["full_data_accuracy_r2"]["author_code_minus_paper_data"])

    def test_references_with_same_aggregate_scores_but_different_people_fail(self):
        targets, left, right = fixture()
        changed = [r for r in right["references"][0]["held_out"]
                   if r["target"] == p.panel.TARGETS[0] and r["condition"] == "accuracy" and r["contrast_percent"] == 5]
        changed[0]["latency_ms"], changed[1]["latency_ms"] = 100, -100
        self.assertEqual(p.panel.evaluate(targets, left)["references"], p.panel.evaluate(targets, right)["references"])
        with self.assertRaisesRegex(ValueError, "identical complete reference"):
            p.evaluate_pair(targets, left, right)

    def test_keyed_reference_and_reproduction_order_do_not_change_pair(self):
        targets, left, right = fixture()
        expected = p.evaluate_pair(targets, left, right)
        right["references"].reverse()
        right["reproduction"].reverse()
        for method in right["references"] + right["reproduction"]:
            for mode in ("held_out", "full_data"):
                method[mode].reverse()
                for row in method[mode]:
                    row["fit_contrasts_percent"].reverse()
        actual = p.evaluate_pair(targets, left, right)
        for field in ("references_sha256", "candidate", "reproduction"):
            self.assertEqual(actual[field], expected[field])

    def test_wrong_arm_and_unmatched_outcome_fail(self):
        targets, left, right = fixture()
        with self.assertRaisesRegex(ValueError, "exact access condition"):
            p.evaluate_pair(targets, right, left)
        del right["reproduction"]
        with self.assertRaisesRegex(ValueError, "same nonempty outcome"):
            p.evaluate_pair(targets, left, right)

    def test_original_coverage_and_fixed_target_checks_apply_to_both_arms(self):
        for arm_index in (1, 2):
            args = fixture()
            args[arm_index]["candidate"]["held_out"].pop()
            with self.subTest(arm=arm_index), self.assertRaisesRegex(ValueError, "global contrast grid"):
                p.evaluate_pair(*args)
        targets, left, right = fixture()
        right["candidate"]["targets_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "fixed target identity"):
            p.evaluate_pair(targets, left, right)

    def test_each_outcome_can_be_paired_independently(self):
        for omitted, present in (("candidate", "reproduction"), ("reproduction", "candidate")):
            targets, left, right = fixture()
            del left[omitted], right[omitted]
            result = p.evaluate_pair(targets, left, right)
            self.assertIsNone(result[omitted])
            self.assertIsNotNone(result[present])

    def test_cli_pins_all_inputs_and_preserves_existing_output(self):
        args = fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = [root / (key + ".json") for key in ("targets",) + p.ACCESS]
            for path, value in zip(paths, args):
                path.write_text(json.dumps(value))
            output = root / "result.json"
            command = [sys.executable, "-I", "-S", "-B", str(PACKAGE / "pair.py"), *map(str, paths), "--output", str(output)]
            subprocess.run(command, check=True, capture_output=True)
            before = output.read_bytes()
            result = json.loads(before)
            self.assertEqual(result["input_file_sha256"], {path.stem: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths})
            retry = subprocess.run(command, capture_output=True)
            self.assertNotEqual(retry.returncode, 0)
            self.assertEqual(output.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
