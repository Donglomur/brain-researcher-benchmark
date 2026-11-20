"""Focused probability-admission controls; no recordings or models are opened."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import support

def one(index, width):
    return [float(i == index) for i in range(width)]


def fixture():
    sessions = []
    for eid, subject, lab in support.evaluation.ROSTER:
        source = {"repository": "brainbench-org/ibl-bwb",
                  "revision": "6fbd666fe8170a2165f5198c1f490911424a654d",
                  "pipeline_sha256": "931002bcf87e2ff88a8eb2e270d963b2479971a0a7dabc3659c5098a2bec0c29",
                  "source_sha256": None}
        # A genuine intervening original no-response slot must supply history.
        movements, choices, rewards = [5., 25., 43., 48., 54.], [-1, 1, 0, 1, -1], [1, 1, -1, 1, 1]
        raw_order = [2, 4, 1, 0, 3]
        inverse = [raw_order.index(i) for i in range(5)]
        slots, cases = [], []
        for ordinal in range(5):
            valid = ordinal != 2
            movement, choice, reward = movements[ordinal], choices[ordinal], rewards[ordinal]
            raw = {"raw_index": raw_order[ordinal], "stored_ordinal": ordinal,
                   "intervals_0": movement - 2., "intervals_1": movement + 2.,
                   "stimOn_times": movement - .5, "firstMovement_times": movement,
                   "feedback_times": movement + .5, "choice": choice, "feedbackType": reward,
                   "probabilityLeft": .5, "contrastLeft": 1. if choice == 1 else None,
                   "contrastRight": None if choice == 1 else 1.}
            normalized = {"ordinal": ordinal, "raw_index": raw_order[ordinal], "source_valid": valid,
                          "raw": raw, "movement_onset_time": movement, "stim_on_time": movement - .5,
                          "feedback_time": movement + .5, "choice": {-1: 0, 1: 1, 0: 2}[choice],
                          "reward": int(reward == 1)}
            split = "train" if ordinal == 0 else "val" if ordinal == 1 else "test" if valid else None
            # Independent canonical identity calculation, matching the task formula.
            token = json.dumps([eid, source, ordinal], sort_keys=True, separators=(",", ":"))
            cid = "case_" + hashlib.sha256(token.encode()).hexdigest() if valid else None
            slots.append({"ordinal": ordinal, "raw_index": raw_order[ordinal],
                          "prior_ordinal": ordinal - 1 if ordinal else None,
                          "source_valid": valid, "normalized": normalized,
                          "disposition": "eligible" if valid else "source_invalid",
                          "reasons": [] if valid else ["raw_no_response"], "case_id": cid, "split": split})
            if not valid:
                continue
            # Prior H: unavailable; prior right rewarded; prior no-response unrewarded;
            # prior left rewarded. Never use the previous *retained* case at ordinal 3.
            h = {0: 0, 1: 2, 3: 5, 4: 4}[ordinal]
            prior = cases[-1]["case_id"] if ordinal in (1, 4) else None
            cases.append({"case_id": cid, "ordinal": ordinal, "split": split,
                          "prior_case_id": prior, "y": int(choice == 1),
                          "unit_ids": ["synthetic-unit"], "count_row": [ordinal], "N": [math.log1p(ordinal)],
                          "S": one(8 if choice == 1 else 0, 9), "B": one(1, 3), "H": one(h, 7),
                          "history_available": ordinal > 0,
                          "history_reason": "feedback_strictly_before_cutoff" if ordinal else "no_preceding_original_trial",
                          "window_start": movement - 1., "window_end": movement})
        sessions.append({"session_id": eid, "subject_id": subject, "lab": lab,
                         "source_identity": source, "source_profile": "reviewed_6fbd_structured_v1",
                         "status": "source_only_unqualified", "structural_holds": [],
                         "slots": slots, "cases": cases, "unit_ids": ["synthetic-unit"],
                         "sorted_to_raw": raw_order, "raw_to_sorted": inverse,
                         "derived_splits": {"train": [[0., 12.]], "val": [[20., 32.]], "test": [[40., 60.]]},
                         "counts": {"original_trials": 5, "source_valid_trials": 4,
                                    "eligible_by_split": {"train": 1, "val": 1, "test": 2},
                                    "excluded_by_reason": {"raw_no_response": 1}, "unit_count": 1,
                                    "matrix": [[0], [1], [3], [4]], "case_ids": [c["case_id"] for c in cases]}})
    return sessions


def predictions(sessions):
    method = {"method_id": "synthetic-constant", "arm": "F", "kind": "actor",
              "method_source_identity": "generated-no-model", "commitments": []}
    for session in sessions:
        for condition in support.evaluation.CONDITIONS:
            method["commitments"].append({"session_id": session["session_id"], "condition": condition,
                                          "config_identity": "generated-config", "parameter_identity": "generated-state"})
    rows = [support.evaluation.build_prediction(session, case, method, condition, .5)
            for session in sessions for case in session["cases"] if case["split"] == "test"
            for condition in support.evaluation.CONDITIONS]
    return rows, [method]


class ProbabilityValidationTests(unittest.TestCase):
    def test_predecessor_overflow_and_total_probability_predicate(self):
        root = HERE.parent / "registered-runtime" / "complete-process-v1" / "scientific"
        name = "_neural059_probability_predecessor_control"
        spec = importlib.util.spec_from_file_location(name, root / "__init__.py", submodule_search_locations=[str(root)])
        package = importlib.util.module_from_spec(spec)
        sys.modules[name] = package
        spec.loader.exec_module(package)
        predecessor = __import__(name + ".evaluation", fromlist=["evaluation"])
        self.assertEqual(hashlib.sha256((root / "evaluation.py").read_bytes()).hexdigest(),
                         "40a02d51e8db4d9aee0a4c0f983431b96caa769da2513d5591dd34826799e09d")
        for value in (10**400, -(10**400)):
            with self.assertRaises(OverflowError):
                predecessor._probability(value)
            self.assertFalse(support.evaluation._probability(value))
            with self.assertRaisesRegex(ValueError, "probability_not_finite_in_unit_interval"):
                support.evaluation.trial_score(0, value)
        for value in (None, True, False, "0.5", [], {}, -1, 2, float("inf"), float("-inf"), float("nan")):
            self.assertFalse(support.evaluation._probability(value))
        for value in (0, 1, 0.0, 0.5, 1.0):
            self.assertTrue(support.evaluation._probability(value))
            for truth in (0, 1):
                self.assertEqual(support.evaluation.trial_score(truth, value), predecessor.trial_score(truth, value))

    def test_oversized_json_integer_retains_trial_and_panel_dispositions(self):
        for invalid in (10**400, -(10**400)):
            sessions = fixture()
            rows, methods = predictions(sessions)
            # This is an ordinary JSON value, not a custom numerical object.
            rows[0]["p"] = json.loads(json.dumps(invalid))
            report = support.score_panel(sessions, rows, expected_methods=methods)
            self.assertFalse(report["scientific_qualification"])
            conditions = report["methods"][0]["conditions"]
            self.assertEqual(len(conditions), 4)
            first = conditions[0]
            self.assertEqual(len(first["sessions"]), 29)
            bad = first["sessions"][0]
            self.assertEqual(bad["status"], "unavailable")
            self.assertEqual((bad["expected_n"], bad["accepted_n"]), (2, 1))
            self.assertIsNone(bad["scores"]["log_loss"])
            self.assertEqual(len(bad["trials"]), 2)
            self.assertIn("invalid_probability", bad["trials"][0]["failures"])
            self.assertEqual(bad["trials"][0]["captured_rows"][0]["p"], invalid)
            self.assertEqual(bad["trials"][1]["status"], "arithmetically_valid_unqualified")
            self.assertIsNone(first["equal_animal_primary"]["scores"]["log_loss"])
            for unaffected in conditions[1:]:
                self.assertAlmostEqual(unaffected["equal_animal_primary"]["scores"]["log_loss"], math.log(2))
                self.assertEqual(unaffected["equal_animal_primary"]["scores"]["brier"], 0.25)
                self.assertTrue(all(row["status"] == "complete_arithmetic_unqualified" for row in unaffected["sessions"]))


if __name__ == "__main__":
    unittest.main()
