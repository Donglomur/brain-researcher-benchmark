"""Full-panel generated controls; no authentic recordings or model execution."""
import copy
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location("fold_bridge", Path(__file__).parents[1] / "bridge.py")
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)
KEY = b"generated owner secret for software controls only"


def panel():
    trials = (42, 3, 100, 8, 9, 10, 11, 12, 13, 14, 15, 16)
    sessions = []
    for group in bridge.SCORER.SESSIONS.values():
        for sid in group:
            rows = []
            for ordinal, trial in enumerate(trials):
                context = "LS" if ordinal < 6 else "SL" if ordinal < 9 else "SS"
                for time_bin in range(40):
                    rows.append({"trial": trial, "type": context,
                                 "result": "correct", "time_bin": time_bin})
            sessions.append({"session_id": sid, "feature_sha256": "1" * 64, "rows": rows})
    return {"schema": "structured-original-index/v1",
            "source_commit": bridge.SCORER.SOURCE_COMMIT,
            "evidence_kind": "generated_engineering_control", "sessions": sessions}


def responses_for(index, plan):
    sessions = {session["session_id"]: session for session in index["sessions"]}
    responses = []
    for unit in plan["units"]:
        rows = sessions[unit["session_id"]]["rows"]
        predictions = []
        for query in unit["query_rows"]:
            row = rows[query["row_position"]]
            shift = 2 if row["type"] == unit["source_context"] else 4
            predictions.append({"query_id": query["query_id"],
                                "time_bin": (row["time_bin"] + shift) % 40})
        responses.append({"schema": bridge.RESPONSE_SCHEMA,
                          "plan_sha256": plan["plan_sha256"],
                          "unit_id": unit["unit_id"], "predictions": predictions})
    return responses


class OriginalFoldBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = panel()
        cls.plan = bridge.build_plan(cls.index, KEY)
        cls.responses = responses_for(cls.index, cls.plan)

    def test_original_membership_all_390_units_not_held_mouse(self):
        self.assertEqual(len(self.plan["units"]), 390)
        self.assertEqual(len({unit["unit_id"] for unit in self.plan["units"]}), 390)
        sessions = {session["session_id"]: session for session in self.index["sessions"]}
        # Independent source-order tenfold expectation: first two folds have two trials.
        fold_trials = ({42, 3}, {100, 8}, {9}, {10}, {11}, {12}, {13}, {14}, {15}, {16})
        query_count = 0
        for unit in self.plan["units"]:
            rows = sessions[unit["session_id"]]["rows"]
            query_positions = {query["row_position"] for query in unit["query_rows"]}
            expected_query = {i for i, row in enumerate(rows) if row["trial"] in fold_trials[unit["split"]]}
            expected_train = {i for i, row in enumerate(rows)
                              if row["trial"] not in fold_trials[unit["split"]]
                              and row["type"] == unit["source_context"]}
            self.assertEqual(query_positions, expected_query)
            self.assertEqual(set(unit["calibration_row_membership"]), expected_train)
            self.assertFalse(query_positions & expected_train)
            query_count += len(query_positions)
        self.assertEqual(query_count, 13 * 12 * 40 * 3)
        self.assertIsNone(self.plan["paper_win"])
        self.assertFalse(self.plan["execution_admitted"])

    def test_full_response_bridge_preserves_all_117_error_cells(self):
        artifact = bridge.assemble_predictions(self.index, self.plan, KEY, self.responses, "2" * 64)
        result = bridge.SCORER.score(self.index, artifact)
        cells = result["context_pair_mse_seconds2"]
        self.assertEqual(sum(len(row) for matrix in cells.values() for row in matrix.values()), 117)
        for matrix in cells.values():
            for source, row in matrix.items():
                for context, error in row.items():
                    self.assertEqual(error, 1 if context == source else 4)
        self.assertIsNone(result["paper_win"])

    def test_response_order_is_irrelevant_to_original_row_assembly(self):
        responses = copy.deepcopy(self.responses)
        responses.reverse()
        for response in responses:
            response["predictions"].reverse()
        result = bridge.assemble_predictions(self.index, self.plan, KEY, responses, "2" * 64)
        expected = bridge.assemble_predictions(self.index, self.plan, KEY, self.responses, "2" * 64)
        self.assertEqual(result, expected)

    def test_owner_plan_reconstruction_rejects_rehashed_truncation_or_leakage(self):
        for kind in ("missing_unit", "query_removed", "query_in_train", "source_context", "numeric_type"):
            plan = copy.deepcopy(self.plan)
            if kind == "missing_unit":
                plan["units"].pop()
            elif kind == "query_removed":
                plan["units"][0]["query_rows"].pop()
            elif kind == "query_in_train":
                plan["units"][0]["calibration_row_membership"].append(0)
            elif kind == "source_context":
                plan["units"][0]["source_context"] = "SS"
            else:
                plan["units"][0]["split"] = 0.0
            plan.pop("plan_sha256")
            plan["plan_sha256"] = bridge._hash(plan)
            with self.subTest(kind=kind), self.assertRaises(bridge.BridgeError):
                bridge.validate_plan(self.index, plan, KEY)

    def test_missing_replayed_cross_unit_and_invalid_response_refuse(self):
        for kind in ("missing_unit", "duplicate_unit", "missing_row", "duplicate_row",
                     "cross_unit", "wrong_plan", "bool_bin", "float_bin", "out_of_range", "extra_field"):
            responses = copy.deepcopy(self.responses)
            row = responses[0]["predictions"][0]
            if kind == "missing_unit":
                responses.pop()
            elif kind == "duplicate_unit":
                responses[-1] = copy.deepcopy(responses[0])
            elif kind == "missing_row":
                responses[0]["predictions"].pop()
            elif kind == "duplicate_row":
                responses[0]["predictions"][-1] = copy.deepcopy(row)
            elif kind == "cross_unit":
                row["query_id"] = responses[1]["predictions"][0]["query_id"]
            elif kind == "wrong_plan":
                responses[0]["plan_sha256"] = "0" * 64
            elif kind == "extra_field":
                row["trial"] = 42
            else:
                row["time_bin"] = {"bool_bin": True, "float_bin": 2.0, "out_of_range": 40}[kind]
            with self.subTest(kind=kind), self.assertRaises(bridge.BridgeError):
                bridge.assemble_predictions(self.index, self.plan, KEY, responses, "2" * 64)

    def test_tokens_are_unit_specific_and_template_hides_owner_lineage(self):
        left, right = self.plan["units"][:2]
        self.assertTrue({q["row_position"] for q in left["query_rows"]} ==
                        {q["row_position"] for q in right["query_rows"]})
        self.assertFalse({q["query_id"] for q in left["query_rows"]} &
                         {q["query_id"] for q in right["query_rows"]})
        template = bridge.response_template(self.plan, left["unit_id"])
        self.assertEqual(set(template), {"schema", "plan_sha256", "unit_id", "query_ids"})
        self.assertEqual(template["query_ids"], sorted(template["query_ids"]))
        self.assertNotIn("session_id", template)

    def test_changed_owner_or_secret_cannot_reuse_plan(self):
        changed = copy.deepcopy(self.index)
        changed["sessions"][0]["feature_sha256"] = "3" * 64
        for index, key in ((changed, KEY), (self.index, b"x" * 32)):
            with self.assertRaises(bridge.BridgeError):
                bridge.validate_plan(index, self.plan, key)
        for key in (b"short", "not bytes"):
            with self.assertRaises(bridge.BridgeError):
                bridge.build_plan(self.index, key)

    def test_no_mutation_of_frozen_owner_metadata(self):
        before = bridge.SCORER.digest(self.index)
        artifact = bridge.assemble_predictions(self.index, self.plan, KEY, self.responses, "2" * 64)
        artifact["sessions"][0]["rows"][0]["predictions"]["LS"] = 17
        self.assertEqual(before, bridge.SCORER.digest(self.index))
        self.assertNotIn("predictions", self.index["sessions"][0]["rows"][0])


if __name__ == "__main__":
    unittest.main()
