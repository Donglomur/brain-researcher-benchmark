"""Generated analytic controls only; no authentic recording or native model fitting."""
import copy
import hashlib
import importlib.util
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("latentcircuit_evaluator", PACKAGE / "evaluator.py")
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)
PROGRAM = b"generated engineering control artifact; not an executed scientific program\n"


def bind_census(owner):
    # Independent canonical representation, not an invocation of audit().
    census = {"units": sorted([[r["monkey"], r["unit_id"]] for r in owner["units"]]),
              "trials": sorted([[r[k] for k in ("monkey", "unit_id", "recording_id", "trial_id")]
                                for r in owner["trials"]]),
              "conditions": sorted(r["condition_id"] for r in owner["conditions"])}
    raw = json.dumps(census, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    owner["data_provenance"]["owner_census_sha256"] = hashlib.sha256(raw).hexdigest()


def fixture():
    conditions = [{"condition_id": f"{context}-{m}-{c}", "context": context,
                   "motion_level": m, "color_level": c}
                  for context in ("motion", "color") for m in (-3, -2, -1, 1, 2, 3)
                  for c in (-3, -2, -1, 1, 2, 3)]
    units = [{"monkey": m, "unit_id": u, "original_exclusion_reason": None}
             for m, u in (("A", "a1"), ("F", "f1"), ("F", "f2"))]
    rows = []
    for unit in units:
        for condition in conditions:
            cid = condition["condition_id"]
            for i, (split, value) in enumerate((("train", -1), ("train", 1),
                                                ("validation", 99), ("assessment", 3))):
                rows.append({"monkey": unit["monkey"], "unit_id": unit["unit_id"],
                             "recording_id": unit["unit_id"], "trial_id": f"{cid}/{i}",
                             "condition_id": cid, "correct": True, "split": split,
                             "values": [value] * 15})
    owner = {"schema": ev.SCHEMA, "task_id": ev.TASK, "policy": ev.POLICY,
             "data_provenance": {"dataset_id": "generated-control-not-authentic-Mante2013",
                                 "owner_census_sha256": "0" * 64,
                                 "origin": "generated_engineering_controls",
                                 "preprocessing_description": "Analytic constants; no native preprocessing."},
             "time_axis": {"sample_centers_ms": list(range(15)), "reference_event": "control_origin",
                           "alignment_policy": "Generated grid only; no empirical timing claim.",
                           "native_join": "unresolved"},
             "frozen_program_sha256": hashlib.sha256(PROGRAM).hexdigest(), "units": units,
             "conditions": conditions, "trials": rows}
    bind_census(owner)
    return owner


def prediction(owner, offsets=None):
    offsets = offsets or {"A": 0, "F": 0}
    # Derive required identity list from metadata-only preparation, not targets returned by scorer.
    _, packet = ev.prepare(owner)
    rows = [{**r, "values": [3 + offsets[r["monkey"]]] * 15} for r in packet["trials"]]
    return {"schema": "latentcircuit.predictions.v1", "task_id": ev.TASK,
            "coordinate_system": "original_neuron", "packet_sha256": packet["packet_sha256"],
            "frozen_program_sha256": owner["frozen_program_sha256"], "predictions": rows}


class AnalyticControls(unittest.TestCase):
    def setUp(self):
        self.owner = fixture()

    def test_perfect_predictions_and_analytic_baseline(self):
        result = ev.score(self.owner, prediction(self.owner), PROGRAM)
        self.assertEqual(result["equal_monkey_neural_nse"], 0)
        self.assertEqual(result["equal_monkey_condition_mean_nse"], 9)
        self.assertEqual(result["equal_monkey_candidate_minus_condition_mean"], -9)
        self.assertEqual(result["native_behavior_guard"], "unresolved_not_scored")
        self.assertEqual(result["scientific_qualification"], "unknown")
        self.assertEqual(result["improvement_decision"], "withheld")

    def test_one_training_sd_error_is_one(self):
        result = ev.score(self.owner, prediction(self.owner, {"A": 1, "F": 1}), PROGRAM)
        self.assertEqual(result["equal_monkey_neural_nse"], 1)
        self.assertEqual([r["training_variance"] for r in result["per_original_unit"]], [1, 1, 1])

    def test_equal_animals_despite_units_and_trial_imbalance(self):
        for row in list(self.owner["trials"]):
            if row["monkey"] == "F" and row["split"] == "assessment":
                for i in range(3):
                    self.owner["trials"].append({**row, "trial_id": row["trial_id"] + f"/extra{i}"})
        bind_census(self.owner)
        result = ev.score(self.owner, prediction(self.owner, {"A": 1, "F": 0}), PROGRAM)
        self.assertEqual(result["equal_monkey_neural_nse"], .5)
        self.assertEqual(result["per_monkey"]["F"]["assessment_trial_rows"], 576)

    def test_training_scale_and_baseline_never_use_validation_or_outer_values(self):
        before = ev.fit_training(self.owner)
        baseline = ev.baseline_submission(self.owner)
        _, packet_before = ev.prepare(self.owner)
        for row in self.owner["trials"]:
            if row["split"] == "assessment":
                row["values"] = [1000] * 15
        self.assertEqual(ev.fit_training(self.owner), before)
        self.assertEqual(ev.baseline_submission(self.owner), baseline)
        self.assertEqual(ev.prepare(self.owner)[1], packet_before)
        for row in self.owner["trials"]:
            if row["split"] == "validation":
                row["values"] = [-10000] * 15
        self.assertEqual(ev.fit_training(self.owner), before)
        changed = ev.baseline_submission(self.owner)
        self.assertEqual(changed["predictions"], baseline["predictions"])

    def test_equal_condition_weight_not_trial_weight(self):
        cid = self.owner["conditions"][0]["condition_id"]
        for row in list(self.owner["trials"]):
            if row["unit_id"] == "a1" and row["condition_id"] == cid and row["split"] == "train":
                for i in range(4):
                    self.owner["trials"].append({**row, "trial_id": row["trial_id"] + f"/rep{i}"})
        bind_census(self.owner)
        self.assertEqual(ev.fit_training(self.owner)[("A", "a1")]["variance"], 1)
        pred = prediction(self.owner)
        for row in pred["predictions"]:
            if row["unit_id"] == "a1" and row["condition_id"] == cid:
                row["values"] = [3 + math.sqrt(72)] * 15
        result = ev.score(self.owner, pred, PROGRAM)
        self.assertAlmostEqual(result["equal_monkey_neural_nse"], .5)

    def test_metadata_only_assessment_packet(self):
        dev, outer = ev.prepare(self.owner)
        self.assertEqual({r["split"] for r in dev["trials"]}, {"train", "validation"})
        for row in outer["trials"]:
            self.assertEqual(set(row), {"monkey", "unit_id", "recording_id", "trial_id", "condition_id"})
        self.assertNotIn("owner_census_sha256", json.dumps(outer))
        self.assertNotIn("values", json.dumps(outer))
        self.assertNotIn("correct", json.dumps(outer))

    def test_retains_excluded_unit_and_original_reason(self):
        self.owner["units"].append({"monkey": "A", "unit_id": "excluded",
                                    "original_exclusion_reason": "Only one correct trial in released ledger."})
        self.owner["trials"].append({**self.owner["trials"][0], "unit_id": "excluded",
                                      "recording_id": "excluded", "values": None})
        bind_census(self.owner)
        checked = ev.audit(self.owner)
        ledger = next(r for r in checked["ledger"] if r["unit_id"] == "excluded")
        self.assertFalse(ledger["eligible"])
        self.assertEqual(len(ledger["under_four_conditions"]), 72)
        self.assertEqual(ledger["original_exclusion_reason"], self.owner["units"][-1]["original_exclusion_reason"])

    def test_outer_packet_not_directly_filtered_by_correctness(self):
        self.owner["trials"].append({**self.owner["trials"][3], "trial_id": "incorrect-outer-trial",
                                      "correct": False, "values": [1000] * 15})
        bind_census(self.owner)
        packets = ev.prepare(self.owner)
        self.owner["trials"][-1]["correct"] = True
        self.assertEqual(ev.prepare(self.owner), packets)
        self.owner["trials"][-1]["correct"] = False
        self.owner["trials"][-1]["values"] = None
        pred = prediction(self.owner)
        row = next(r for r in pred["predictions"] if r["trial_id"] == "incorrect-outer-trial")
        row["values"] = [1e50] * 15  # Ignored by the correct-trial endpoint.
        result = ev.score(self.owner, pred, PROGRAM)
        self.assertEqual(result["equal_monkey_neural_nse"], 0)
        self.assertEqual(result["per_monkey"]["A"]["assessment_prediction_rows"], 73)
        self.assertEqual(result["per_monkey"]["A"]["assessment_trial_rows"], 72)
        pred["predictions"].remove(row)
        with self.assertRaises(ev.ContractError): ev.score(self.owner, pred, PROGRAM)

    def test_owner_condition_mean_control_is_exactly_recomputed(self):
        result = ev.score(self.owner, ev.baseline_submission(self.owner), PROGRAM)
        self.assertEqual(result["equal_monkey_neural_nse"], 9)
        self.assertEqual(result["equal_monkey_candidate_minus_condition_mean"], 0)


class RejectionControls(unittest.TestCase):
    def setUp(self):
        self.owner = fixture()

    def test_missing_duplicate_unknown_or_projected_coordinates(self):
        for attack in ("missing", "duplicate", "unknown", "projected", "condition", "time"):
            with self.subTest(attack=attack):
                pred = prediction(self.owner)
                if attack == "missing": pred["predictions"].pop()
                elif attack == "duplicate": pred["predictions"].append(copy.deepcopy(pred["predictions"][0]))
                elif attack == "unknown": pred["predictions"][0]["unit_id"] = "latent-node-1"
                elif attack == "projected": pred["coordinate_system"] = "learned_projection"
                elif attack == "condition": pred["predictions"][0]["condition_id"] = "different"
                else: pred["predictions"][0]["values"].pop()
                with self.assertRaises(ev.ContractError): ev.score(self.owner, pred, PROGRAM)

    def test_wrong_artifact_bytes_are_not_silently_accepted(self):
        with self.assertRaises(ev.ContractError):
            ev.score(self.owner, prediction(self.owner), b"different program")

    def test_candidate_supplied_scale_is_forbidden(self):
        pred = prediction(self.owner)
        pred["variance"] = 1e30
        with self.assertRaises(ev.ContractError): ev.score(self.owner, pred, PROGRAM)

    def test_missing_monkey_or_condition_or_unit_rows(self):
        for attack in ("monkey", "condition", "unit_rows"):
            with self.subTest(attack=attack):
                owner = copy.deepcopy(self.owner)
                if attack == "monkey":
                    owner["units"] = [r for r in owner["units"] if r["monkey"] == "A"]
                    owner["trials"] = [r for r in owner["trials"] if r["monkey"] == "A"]
                elif attack == "condition": owner["conditions"].pop()
                else: owner["trials"] = [r for r in owner["trials"] if r["unit_id"] != "a1"]
                bind_census(owner)
                with self.assertRaises(ev.ContractError): ev.audit(owner)

    def test_census_binding_cannot_be_silently_mutated(self):
        self.owner["trials"][0]["trial_id"] = "altered"
        with self.assertRaisesRegex(ev.ContractError, "census SHA256"):
            ev.audit(self.owner)

    def test_all_eligible_rows_need_nested_train_validation_outer_support(self):
        self.owner["trials"][3]["split"] = "train"
        with self.assertRaisesRegex(ev.ContractError, "incomplete nested"):
            ev.audit(self.owner)

    def test_original_exclusion_note_cannot_drop_eligible_unit(self):
        self.owner["units"][0]["original_exclusion_reason"] = "candidate wants to drop difficult unit"
        self.assertIn(("A", "a1"), ev.audit(self.owner)["eligible"])

    def test_shared_physical_trial_cannot_cross_partitions(self):
        for row in self.owner["trials"]:
            if row["monkey"] == "F": row["recording_id"] = "shared-session"
        bind_census(self.owner)
        ev.audit(self.owner)  # Simultaneously recorded units may share a trial identity.
        row = next(r for r in self.owner["trials"] if r["unit_id"] == "f2" and r["split"] == "assessment")
        row["split"] = "train"
        with self.assertRaisesRegex(ev.ContractError, "shared physical trial"):
            ev.audit(self.owner)

    def test_zero_scale_cannot_drop_unit_or_borrow_held_scale(self):
        for row in self.owner["trials"]:
            if row["split"] == "train": row["values"] = [1] * 15
        with self.assertRaisesRegex(ev.ContractError, "zero training variance"):
            ev.fit_training(self.owner)

    def test_nonfinite_boolean_and_extreme_numbers_rejected(self):
        for invalid in (True, float("nan"), float("inf"), 10 ** 400):
            with self.subTest(invalid=str(invalid)[:20]):
                pred = prediction(self.owner)
                pred["predictions"][0]["values"][0] = invalid
                with self.assertRaises(ev.ContractError): ev.score(self.owner, pred, PROGRAM)

    def test_native_clock_cannot_be_self_certified(self):
        self.owner["time_axis"]["native_join"] = "resolved"
        with self.assertRaises(ev.ContractError): ev.audit(self.owner)

    def test_cli_pin_duplicate_json_and_overwrite_guards(self):
        with tempfile.TemporaryDirectory() as tmp:
            owner_path = Path(tmp) / "owner.json"
            output = Path(tmp) / "audit.json"
            owner_path.write_text(json.dumps(self.owner))
            pin = hashlib.sha256(owner_path.read_bytes()).hexdigest()
            base = [sys.executable, str(PACKAGE / "evaluator.py"), "audit", "--owner", str(owner_path)]
            valid = subprocess.run(base + ["--expected-owner-sha256", pin, "--output", str(output)],
                                   capture_output=True, text=True)
            self.assertEqual(valid.returncode, 0, valid.stderr)
            bad = subprocess.run(base + ["--expected-owner-sha256", "0" * 64, "--output", str(output)],
                                 capture_output=True, text=True)
            self.assertEqual(bad.returncode, 2)
            overwrite = subprocess.run(base + ["--expected-owner-sha256", pin, "--output", str(owner_path)],
                                       capture_output=True, text=True)
            self.assertEqual(overwrite.returncode, 2)
            owner_path.write_text('{"a": 1, "a": 2}')
            with self.assertRaisesRegex(ev.ContractError, "duplicate JSON"):
                ev._load_json(owner_path)

    def test_cli_complete_owner_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            owner_path = tmp / "owner.json"
            program_path = tmp / "frozen-program.txt"
            owner_path.write_text(json.dumps(self.owner))
            program_path.write_bytes(PROGRAM)
            pin = hashlib.sha256(owner_path.read_bytes()).hexdigest()
            def run(command, output, *extra):
                result = subprocess.run([sys.executable, str(PACKAGE / "evaluator.py"), command,
                                         "--owner", str(owner_path), "--expected-owner-sha256", pin,
                                         "--output", str(output), *map(str, extra)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
            run("prepare", tmp / "development.json", "--assessment-output", tmp / "inputs.json")
            run("baseline", tmp / "predictions.json")
            run("score", tmp / "score.json", "--predictions", tmp / "predictions.json",
                "--candidate-program", program_path)
            result = json.loads((tmp / "score.json").read_text())
            self.assertEqual(result["owner_file_sha256"], pin)
            self.assertEqual(result["equal_monkey_candidate_minus_condition_mean"], 0)
            outer = json.loads((tmp / "inputs.json").read_text())
            self.assertEqual(len(outer["trials"]), 216)


if __name__ == "__main__":
    unittest.main()
