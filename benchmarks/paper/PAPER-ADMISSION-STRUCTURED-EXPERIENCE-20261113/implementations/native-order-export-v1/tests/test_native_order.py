"""Generated index-protocol controls, not pandas/source-runtime qualification."""
import copy
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location("native_order", Path(__file__).parents[1] / "native_order.py")
n = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(n)
KEY = b"generated owner secret for native index export controls"
DECLARATION = {"source_commit": n.scorer.SOURCE_COMMIT,
               "producer_sha256": n.PRODUCER_SHA256,
               "runtime_manifest_sha256": "a" * 64,
               "source_run_receipt_sha256": "b" * 64}


class GeneratedLevel:
    def __init__(self, dtype):
        self.dtype = dtype


class GeneratedIndex:
    """Minimal supplied-index protocol; never presented as a pandas object."""
    def __init__(self, names, rows):
        self.names = list(names)
        self.rows = list(rows)
        self.levels = [GeneratedLevel("generated-string" if name in ("type", "result")
                                      else "generated-int") for name in names]

    def tolist(self):
        return list(self.rows)


class GeneratedScalar:
    def __init__(self, value):
        self.value = value

    def item(self):
        return self.value


def panel():
    trials = (42, 3, 100, 8, 9, 10, 11, 12, 13, 14, 15, 16)
    sessions = []
    for group in n.scorer.SESSIONS.values():
        for sid in group:
            rows = []
            for ordinal, trial in enumerate(trials):
                context = "LS" if ordinal < 6 else "SL" if ordinal < 9 else "SS"
                for time_bin in range(40):
                    rows.append({"trial": trial, "type": context, "result": "correct", "time_bin": time_bin})
            sessions.append({"session_id": sid, "feature_sha256": "1" * 64, "rows": rows})
    return {"schema": "structured-original-index/v1", "source_commit": n.scorer.SOURCE_COMMIT,
            "evidence_kind": "generated_engineering_control", "sessions": sessions}


def supplied_indexes(owner, unit):
    rows = next(session["rows"] for session in owner["sessions"] if session["session_id"] == unit["session_id"])
    # Intentional non-source/non-sorted permutations. The exporter must preserve
    # the supplied sequences rather than infer a pandas native ordering policy.
    train_positions = list(reversed(unit["calibration_row_membership"]))
    query_positions = sorted(q["row_position"] for q in unit["query_rows"])
    query_positions = query_positions[1:] + query_positions[:1]
    train = GeneratedIndex(n.TRAIN_NAMES, [tuple(rows[i][key] for key in n.TRAIN_NAMES) for i in train_positions])
    query = GeneratedIndex(n.QUERY_NAMES, [tuple(rows[i][key] for key in n.QUERY_NAMES) for i in query_positions])
    return train, query, train_positions, query_positions


class NativeOrderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.owner = panel()
        cls.plan = n.bridge.build_plan(cls.owner, KEY)
        recorder = n.NativeOrderRecorder(cls.owner, cls.plan, KEY, DECLARATION)
        for unit in cls.plan["units"]:
            train, query, _, _ = supplied_indexes(cls.owner, unit)
            recorder.record(unit["unit_id"], source_context=unit["source_context"],
                            training_index=train, query_index=query)
        cls.capture = recorder.finish()

    def recorder(self):
        return n.NativeOrderRecorder(self.owner, self.plan, KEY, DECLARATION)

    def test_all390_units_preserve_supplied_sequences_without_sorting(self):
        joined = n.join_native_order(self.owner, self.plan, KEY, self.capture)
        self.assertEqual(len(joined["units"]), 390)
        self.assertEqual({u["unit_id"] for u in joined["units"]}, {u["unit_id"] for u in self.plan["units"]})
        for unit, exported in zip(self.plan["units"], joined["units"]):
            _, _, train_positions, query_positions = supplied_indexes(self.owner, unit)
            self.assertEqual(exported["calibration_row_order"], train_positions)
            self.assertEqual(exported["query_row_order"], query_positions)
            ids = {q["row_position"]: q["query_id"] for q in unit["query_rows"]}
            self.assertEqual(exported["query_ids_in_native_order"], [ids[i] for i in query_positions])
        self.assertIsNone(joined["paper_win"])
        self.assertFalse(joined["source_native_parity_established"])
        self.assertFalse(joined["execution_admitted"])

    def test_native_query_order_joins_existing117_cell_scorer(self):
        joined = n.join_native_order(self.owner, self.plan, KEY, self.capture)
        by_session = {s["session_id"]: s["rows"] for s in self.owner["sessions"]}
        units = {u["unit_id"]: u for u in self.plan["units"]}
        responses = []
        for exported in joined["units"]:
            unit = units[exported["unit_id"]]
            rows = by_session[unit["session_id"]]
            values = []
            for pos, qid in zip(exported["query_row_order"], exported["query_ids_in_native_order"]):
                shift = 2 if rows[pos]["type"] == unit["source_context"] else 4
                values.append({"query_id": qid, "time_bin": (rows[pos]["time_bin"] + shift) % 40})
            responses.append({"schema": n.bridge.RESPONSE_SCHEMA,
                              "plan_sha256": self.plan["plan_sha256"],
                              "unit_id": unit["unit_id"], "predictions": values})
        predictions = n.bridge.assemble_predictions(self.owner, self.plan, KEY, responses, "c" * 64)
        scored = n.scorer.score(self.owner, predictions)
        self.assertEqual(sum(len(row) for matrix in scored["context_pair_mse_seconds2"].values()
                             for row in matrix.values()), 117)
        for matrix in scored["context_pair_mse_seconds2"].values():
            for source, row in matrix.items():
                for context, error in row.items():
                    self.assertEqual(error, 1 if context == source else 4)

    def test_training_shape_is_only_exact_context_dropped_native_index(self):
        unit = self.plan["units"][0]
        train, query, _, _ = supplied_indexes(self.owner, unit)
        for names in (("result", "trial", "time_bin"), n.QUERY_NAMES, ("trial", "result")):
            bad = copy.deepcopy(train)
            bad.names = list(names)
            with self.subTest(names=names), self.assertRaises(n.NativeOrderError):
                self.recorder().record(unit["unit_id"], source_context=unit["source_context"],
                                       training_index=bad, query_index=query)
        with self.assertRaises(n.NativeOrderError):
            self.recorder().record(unit["unit_id"], source_context="SS",
                                   training_index=train, query_index=query)

    def test_missing_duplicate_wrong_membership_and_unknown_shapes_refuse(self):
        unit = self.plan["units"][0]
        for kind in ("missing_train", "duplicate_train", "held_in_train", "missing_query",
                     "duplicate_query", "wrong_query_context", "short_tuple", "unknown_names"):
            train, query, _, _ = supplied_indexes(self.owner, unit)
            if kind == "missing_train": train.rows.pop()
            elif kind == "duplicate_train": train.rows[-1] = train.rows[0]
            elif kind == "held_in_train":
                t, _, result, time_bin = query.rows[0]
                train.rows[-1] = (t, result, time_bin)
            elif kind == "missing_query": query.rows.pop()
            elif kind == "duplicate_query": query.rows[-1] = query.rows[0]
            elif kind == "wrong_query_context":
                t, _, result, time_bin = query.rows[0]
                query.rows[0] = (t, "SS", result, time_bin)
            elif kind == "short_tuple": train.rows[0] = train.rows[0][:-1]
            else: query.names = ["trial", "type", "result", "time"]
            with self.subTest(kind=kind), self.assertRaises(n.NativeOrderError):
                self.recorder().record(unit["unit_id"], source_context=unit["source_context"],
                                       training_index=train, query_index=query)

    def test_scalar_export_is_lossless_and_type_sensitive(self):
        unit = self.plan["units"][0]
        train, query, _, _ = supplied_indexes(self.owner, unit)
        train.rows = [tuple(GeneratedScalar(v) for v in row) for row in train.rows]
        recorder = self.recorder()
        recorder.record(unit["unit_id"], source_context=unit["source_context"], training_index=train, query_index=query)
        for replacement in (float(query.rows[0][0]), str(query.rows[0][0]), True, float("nan")):
            train, query, _, _ = supplied_indexes(self.owner, unit)
            query.rows[0] = (replacement,) + query.rows[0][1:]
            with self.subTest(replacement=repr(replacement)), self.assertRaises(n.NativeOrderError):
                self.recorder().record(unit["unit_id"], source_context=unit["source_context"],
                                       training_index=train, query_index=query)

    def test_complete_capture_and_one_record_per_unit_required(self):
        recorder = self.recorder()
        unit = self.plan["units"][0]
        train, query, _, _ = supplied_indexes(self.owner, unit)
        recorder.record(unit["unit_id"], source_context=unit["source_context"], training_index=train, query_index=query)
        with self.assertRaises(n.NativeOrderError): recorder.finish()
        with self.assertRaises(n.NativeOrderError):
            recorder.record(unit["unit_id"], source_context=unit["source_context"], training_index=train, query_index=query)

    def test_rehashed_capture_cannot_change_membership_or_promote_qualification(self):
        for kind in ("missing_unit", "duplicate_unit", "duplicate_position", "float_position",
                     "wrong_query", "changed_order_digest", "source", "promotion"):
            capture = copy.deepcopy(self.capture)
            if kind == "missing_unit": capture["units"].pop()
            elif kind == "duplicate_unit": capture["units"][-1] = copy.deepcopy(capture["units"][0])
            elif kind == "duplicate_position":
                order = capture["units"][0]["calibration_row_order"]; order[-1] = order[0]
            elif kind == "float_position": capture["units"][0]["query_row_order"][0] += 0.0
            elif kind == "wrong_query": capture["units"][0]["query_row_order"][0] = 479
            elif kind == "changed_order_digest": capture["units"][0]["query_row_order"].reverse()
            elif kind == "source": capture["source_runtime_declaration"]["source_commit"] = "x" * 40
            else: capture["source_native_parity_established"] = True
            capture.pop("capture_sha256"); capture["capture_sha256"] = n._digest(capture)
            with self.subTest(kind=kind), self.assertRaises(n.NativeOrderError):
                n.join_native_order(self.owner, self.plan, KEY, capture)

    def test_source_runtime_and_frozen_owner_bindings_required(self):
        for kind in ("runtime", "producer", "extra"):
            declaration = copy.deepcopy(DECLARATION)
            if kind == "runtime": declaration["runtime_manifest_sha256"] = "unknown"
            elif kind == "producer": declaration["producer_sha256"] = "0" * 64
            else: declaration["pandas_parity"] = True
            with self.subTest(kind=kind), self.assertRaises(n.NativeOrderError):
                n.NativeOrderRecorder(self.owner, self.plan, KEY, declaration)
        changed = copy.deepcopy(self.owner); changed["sessions"][0]["feature_sha256"] = "2" * 64
        with self.assertRaises(n.NativeOrderError):
            n.join_native_order(changed, self.plan, KEY, self.capture)


if __name__ == "__main__":
    unittest.main(verbosity=2)
