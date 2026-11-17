"""Bounded generated controls; never authentic neuroscience evidence."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("rr_eval", Path(__file__).parents[1] / "evaluator.py")
e = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(e)


def fixture(post_laps=4):
    animals = list(e.SWITCH_ANIMALS)
    sessions = []
    for animal in animals:
        for day in e.SWITCH_DAYS:
            sid = f"{animal}-day-{day}"
            laps = []
            for lap in range(post_laps + 1):
                laps.append({"lap_id": f"lap-{lap}", "phase": "pre" if lap == 0 else "post", "complete": True,
                    "samples": [{"sample_id": f"{sid}-{lap}", "time_seconds": 1000.0 + lap,
                                  "neural": [0.25, None], "theta_rr": 0.0}]})
            sessions.append({"session_id": sid, "animal_id": animal, "day": day, "cell_ids": ["c1", "c2"],
                             "feature_evidence": {"kind": "causal_neural", "evidence_sha256": "1" * 64, "fitted_sample_ids": []}, "laps": laps})
    return {"schema": "rr-owner-input-v1", "animals": animals,
            "coordinate_evidence": {"admission": "engineering_control", "units": "radians", "source_commit": e.CODE_COMMIT,
                "transform_evidence_sha256": "2" * 64, "data_identity_sha256": "3" * 64}, "sessions": sessions}


def prediction(owner, angle=0.0):
    return {"schema": "rr-predictions-v1", "task_id": e.TASK_ID,
            "candidate_input_sha256": owner["candidate_input_sha256"], "sessions": [
            {"session_id": s["session_id"], "predictions": [{"sample_id": t["sample_id"], "theta_rr": angle} for t in s["targets"]],
             "fit_receipt": {"calibration_sample_ids": s["calibration_sample_ids"][:], "selection_session_ids": [], "artifact_sha256": "4" * 64}}
            for s in owner["sessions"]]}


class EvaluationControls(unittest.TestCase):
    def setUp(self):
        self.bundle = fixture()
        self.public, self.owner = e.prepare(self.bundle, b"s" * 32)

    def test_chronological_partition_guard_and_projection(self):
        trace = self.owner["sessions"][0]["trace"]
        self.assertEqual(trace["calibration"]["lap_ids"], ["lap-0", "lap-1", "lap-2"])
        self.assertEqual(trace["guard"]["lap_ids"], ["lap-3"])
        self.assertEqual(trace["evaluation"]["lap_ids"], ["lap-4"])
        visible = self.public["sessions"][0]
        self.assertEqual(set(visible["query"][0]), {"sample_id", "trial_id", "time_seconds", "neural", "missing"})
        self.assertEqual(visible["query"][0]["missing"], [False, True])
        self.assertEqual(visible["query"][0]["neural"], [0.25, 0.0])
        self.assertEqual(visible["query"][0]["time_seconds"], 0)
        text = json.dumps(self.public)
        for secret in ("GCAMP", "day-", "lap-", "cell_ids", "source_session_id", "evidence_sha256", "1000.0"):
            self.assertNotIn(secret, text)
        self.assertEqual(len(self.public["outer_folds"]), 11)
        for fold in self.public["outer_folds"]:
            self.assertEqual(len(fold["held_session_ids"]), 7)
            self.assertEqual(len(fold["selection_session_ids"]), 70)
            self.assertFalse(set(fold["held_session_ids"]) & set(fold["selection_session_ids"]))

    def test_odd_floor_and_incomplete_lap_trace(self):
        session = fixture(post_laps=5)["sessions"][0]
        session["laps"][2]["complete"] = False
        split = e.split_session(session)
        self.assertEqual(split["complete_post_laps"], 4)
        self.assertEqual(split["incomplete_post"][0]["lap_id"], "lap-2")
        self.assertEqual(split["guard"][0]["lap_id"], "lap-4")
        odd = e.split_session(fixture(post_laps=5)["sessions"][0])
        self.assertTrue(odd["odd_count_floor_used"])
        self.assertEqual(odd["calibration_post_laps"], 2)
        self.assertEqual(len(odd["evaluation"]), 2)
        minimum = e.split_session(fixture(post_laps=3)["sessions"][0])
        self.assertEqual([len(minimum[k]) for k in ("calibration", "guard", "evaluation")], [2, 1, 1])

    def test_opaque_order_and_secret_rotation(self):
        self.assertEqual([s["session_id"] for s in self.public["sessions"]],
                         sorted(s["session_id"] for s in self.public["sessions"]))
        self.assertEqual([f["fold_id"] for f in self.public["outer_folds"]],
                         sorted(f["fold_id"] for f in self.public["outer_folds"]))
        other, _ = e.prepare(self.bundle, b"t" * 32)
        self.assertFalse({s["session_id"] for s in other["sessions"]} & {s["session_id"] for s in self.public["sessions"]})

    def test_evaluation_target_changes_cannot_change_candidate_query(self):
        changed = copy.deepcopy(self.bundle)
        for s in changed["sessions"]:
            s["laps"][-1]["samples"][0]["theta_rr"] = 2.0
        public, owner = e.prepare(changed, b"s" * 32)
        self.assertEqual(public, self.public)
        self.assertEqual(owner["candidate_input_sha256"], self.owner["candidate_input_sha256"])
        self.assertNotEqual(owner["plan_sha256"], self.owner["plan_sha256"])

    def test_all_missing_eval_and_malformed_receipts_rejected(self):
        for lap in self.bundle["sessions"][0]["laps"]:
            for sample in lap["samples"]: sample["neural"] = [None, None]
        with self.assertRaises(e.ContractError): e.prepare(self.bundle, b"s" * 32)
        pred = prediction(self.owner)
        pred["sessions"][0]["fit_receipt"]["calibration_sample_ids"] = [{}]
        with self.assertRaises(e.ContractError): e.score(self.owner, pred, prediction(self.owner), bootstrap_repeats=5)

    def test_complete_cohort_required_before_export(self):
        for mutation in (lambda x: x["sessions"].pop(),
                         lambda x: x["sessions"].__setitem__(1, copy.deepcopy(x["sessions"][0])),
                         lambda x: x["animals"].__setitem__(0, "unknown")):
            broken = copy.deepcopy(self.bundle)
            mutation(broken)
            with self.assertRaises(e.ContractError): e.prepare(broken, b"s" * 32)

    def test_insufficient_and_disordered_laps_rejected(self):
        broken = fixture(post_laps=2)
        with self.assertRaises(e.ContractError): e.prepare(broken, b"s" * 32)
        session = self.bundle["sessions"][0]
        session["laps"][2]["samples"][0]["time_seconds"] = 999.0
        with self.assertRaises(e.ContractError): e.prepare(self.bundle, b"s" * 32)

    def test_evaluation_fitted_transform_and_extra_metadata_rejected(self):
        s = self.bundle["sessions"][0]
        s["feature_evidence"]["fitted_sample_ids"] = [s["laps"][-1]["samples"][0]["sample_id"]]
        with self.assertRaises(e.ContractError): e.prepare(self.bundle, b"s" * 32)
        self.bundle = fixture()
        self.bundle["sessions"][0]["laps"][-1]["samples"][0]["position"] = 120
        with self.assertRaises(e.ContractError): e.prepare(self.bundle, b"s" * 32)

    def test_perfect_antipodal_and_paired_bootstrap(self):
        out = e.score(self.owner, prediction(self.owner), prediction(self.owner, math.pi), bootstrap_repeats=50, seed=6)
        self.assertEqual(out["candidate"], 1)
        self.assertEqual(out["comparator"], -1)
        self.assertEqual(out["paired_gain"], 2)
        self.assertEqual(out["uncertainty"]["gain_interval"], [2, 2])
        self.assertFalse(out["scientifically_qualified"])
        self.assertEqual(out["uncertainty"]["unit"], "mouse")

    def test_wrap_seam_equivalence(self):
        for s in self.bundle["sessions"]:
            for lap in s["laps"]:
                for sample in lap["samples"]: sample["theta_rr"] = math.pi
        _, owner = e.prepare(self.bundle, b"s" * 32)
        out = e.score(owner, prediction(owner, -math.pi), prediction(owner, math.pi), bootstrap_repeats=5)
        self.assertEqual(out["candidate"], 1)
        self.assertEqual(out["paired_gain"], 0)

    def test_session_then_animal_aggregation_not_sample_pooling(self):
        # One mouse/day has 100 query samples, all its other days have one.
        s = self.bundle["sessions"][0]
        s["laps"][-1]["samples"] = [dict(sample_id=f"many-{j}", time_seconds=1004+j/1000, neural=[1, None], theta_rr=0) for j in range(100)]
        _, owner = e.prepare(self.bundle, b"s" * 32)
        cand, base = prediction(owner), prediction(owner)
        target_sid = next(x["session_id"] for x in owner["sessions"] if x["source_session_id"] == s["session_id"])
        for row in cand["sessions"]:
            if row["session_id"] == target_sid:
                for sample in row["predictions"]: sample["theta_rr"] = math.pi
        out = e.score(owner, cand, base, bootstrap_repeats=31, seed=7)
        self.assertAlmostEqual(out["candidate"], 1 - 2/77)
        self.assertAlmostEqual(out["paired_gain"], -2/77)
        self.assertAlmostEqual(next(x for x in out["animal_effects"] if x["animal_id"] == s["animal_id"])["gain"], -2/7)
        self.assertEqual(out, e.score(owner, cand, base, bootstrap_repeats=31, seed=7))

    def test_predictions_and_baseline_require_exact_support(self):
        mutations = [lambda p: p["sessions"].pop(),
                     lambda p: p["sessions"][0]["predictions"].clear(),
                     lambda p: p["sessions"][0]["predictions"].append(p["sessions"][0]["predictions"][0]),
                     lambda p: p["sessions"][0]["predictions"][0].__setitem__("theta_rr", float("nan")),
                     lambda p: p["sessions"][0]["fit_receipt"]["calibration_sample_ids"].pop(),
                     lambda p: p.__setitem__("candidate_input_sha256", "0" * 64)]
        for mutation in mutations:
            bad = prediction(self.owner)
            mutation(bad)
            with self.assertRaises(e.ContractError): e.score(self.owner, prediction(self.owner), bad, bootstrap_repeats=5)

    def test_outer_held_mouse_cannot_select_algorithm(self):
        pred = prediction(self.owner)
        held = self.owner["sessions"][0]
        sibling = next(s for s in self.owner["sessions"] if s["animal_id"] == held["animal_id"] and s["day"] != held["day"])
        pred["sessions"][0]["fit_receipt"]["selection_session_ids"] = [sibling["session_id"]]
        with self.assertRaises(e.ContractError): e.score(self.owner, pred, prediction(self.owner), bootstrap_repeats=5)

    def test_plan_tampering_and_json_duplicate_keys(self):
        owner = copy.deepcopy(self.owner)
        owner["sessions"][0]["targets"][0]["theta_rr"] = 1
        with self.assertRaises(e.ContractError): e.score(owner, prediction(self.owner), prediction(self.owner), bootstrap_repeats=5)
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "input.json"
            for raw in ('{"a":1,"a":2}', '{"a":NaN}'):
                p.write_text(raw)
                with self.assertRaises(e.ContractError): e.read_json(p)


if __name__ == "__main__":
    unittest.main()
