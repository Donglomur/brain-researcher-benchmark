"""Tiny generated software controls. No recording, fitting or model is opened."""
import contextlib
import hashlib
import io
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

# Supports the pool's isolated Python (-I) invocation.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import support
import score


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


class SupportTests(unittest.TestCase):
    def setUp(self):
        self.sessions = fixture()

    def refusal(self, code):
        with self.assertRaises(support.SupportError) as caught:
            support.validate_prepared(self.sessions)
        self.assertEqual(caught.exception.code, code)

    def test_complete_generated_support_and_primary_math(self):
        counts = support.validate_prepared(self.sessions)
        self.assertEqual(len(counts), 29)
        rows, methods = predictions(self.sessions)
        result = support.score_panel(self.sessions, rows, expected_methods=methods)
        self.assertFalse(result["scientific_qualification"])
        for condition in result["methods"][0]["conditions"]:
            self.assertAlmostEqual(condition["equal_animal_primary"]["scores"]["log_loss"], math.log(2))
            self.assertEqual(condition["equal_animal_primary"]["scores"]["brier"], .25)

    def test_deleted_eligible_case_was_not_detected_by_retained_scorer(self):
        self.sessions[0]["cases"].pop()
        previous, global_failures = support.evaluation._preparation(self.sessions)
        self.assertEqual(global_failures, [])
        self.assertEqual(previous[self.sessions[0]["session_id"]]["failures"], [])
        self.refusal("eligible_slot_case_bijection")

    def test_renamed_case_and_slot_does_not_change_original_identity(self):
        self.sessions[0]["cases"][-1]["case_id"] = "reassigned"
        self.sessions[0]["slots"][-1]["case_id"] = "reassigned"
        self.refusal("eligible_slot_identity")

    def test_retained_row_history_must_not_skip_no_response_original(self):
        self.sessions[0]["cases"][2]["H"] = one(4, 7)
        self.refusal("original_predecessor_history")

    def test_excluded_original_predecessor_has_no_retained_case_id(self):
        self.sessions[0]["cases"][2]["prior_case_id"] = self.sessions[0]["cases"][1]["case_id"]
        self.refusal("original_predecessor_case_join")

    def test_feedback_at_cutoff_is_unavailable(self):
        prior = self.sessions[0]["slots"][2]["normalized"]
        prior["feedback_time"] = prior["raw"]["feedback_times"] = 48.
        case = self.sessions[0]["cases"][2]
        self.refusal("original_predecessor_history")
        case.update(H=one(0, 7), history_available=False,
                    history_reason="prior_feedback_or_behavior_unavailable")
        support.validate_prepared(self.sessions)

    def test_relabelled_truth(self):
        self.sessions[0]["cases"][-1]["y"] = 1
        self.refusal("case_source_choice")

    def test_window_crossing_split(self):
        self.sessions[0]["derived_splits"]["test"][0][0] = 47.5
        self.refusal("case_whole_window_split")

    def test_wrong_count_transformation(self):
        self.sessions[0]["cases"][-1]["N"] = [4.]
        self.refusal("case_log_count_join")

    def test_raw_index_inverse(self):
        self.sessions[0]["raw_to_sorted"] = list(range(5))
        self.refusal("raw_sorted_inverse")

    def test_counter_cannot_hide_case_loss(self):
        self.sessions[0]["counts"]["eligible_by_split"]["test"] = 1
        self.refusal("census_join:eligible_by_split")

    def test_full_cohort_and_order(self):
        self.sessions.reverse()
        self.refusal("complete_ordered_roster_join")

    def test_boolean_identity(self):
        self.sessions[0]["cases"][0]["ordinal"] = False
        self.refusal("case_ordinal_type")

    def test_source_stimulus_and_block(self):
        self.sessions[0]["cases"][-1]["S"] = one(8, 9)
        self.refusal("case_stimulus_join")
        self.sessions = fixture()
        self.sessions[0]["cases"][-1]["B"] = one(0, 3)
        self.refusal("case_block_join")

    def test_protected_json_reader_rejects_duplicate_keys_and_nonfinite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            for body in (b'{"a":1,"a":2}', b'[NaN]', b'[Infinity]'):
                path.write_bytes(body)
                with self.assertRaises(ValueError):
                    score.strict_json(path, 100)
            path.write_bytes(b'{}')
            with self.assertRaises(ValueError):
                score.strict_json(path, 1)

    def test_operator_entrypoint_receipt_and_fresh_output(self):
        rows, methods = predictions(self.sessions)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            argv = []
            for role, value in (("prepared", self.sessions), ("predictions", rows), ("methods", methods)):
                path = root / (role + ".json")
                path.write_text(json.dumps(value))
                argv += ["--" + role, str(path)]
            output = root / "score.json"
            argv += ["--output", str(output), "--max-input-bytes", "2000000", "--max-output-bytes", "2000000"]
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(score.main(argv), 0)
            receipt = json.loads(stdout.getvalue())
            self.assertEqual(set(receipt), {"status", "bytes", "sha256"})
            self.assertEqual(receipt["sha256"], hashlib.sha256(output.read_bytes()).hexdigest())
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(score.main(argv), 2)
            self.assertEqual(receipt["sha256"], hashlib.sha256(output.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main(verbosity=2)
