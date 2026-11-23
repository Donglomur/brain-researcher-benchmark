"""Export supplied original native index order into the private fold bridge.

No pandas ordering is reimplemented. Call this at the native training callsite
with the actual post-context-selection training index and held-fold query index.
The resulting metadata never proves source custody, native runtime parity or fit.
"""
from __future__ import annotations

import builtins
import copy
import hashlib
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import types

BRIDGE_SHA256 = "72001871a9372bf4480425e6a829ddf75b8a33b497544600fbb5cd03a535a564"
SCORER_SHA256 = "ef7146154f054e29f77a74757d0b82c4000692ca47ef2187d7629fda29cddfc9"
PRODUCER_SHA256 = "54b2530012aa298ea53689dc598eb1d466b376e478225c3e853561fdd47203d6"
TRAIN_NAMES = ("trial", "result", "time_bin")
QUERY_NAMES = ("trial", "type", "result", "time_bin")
CAPTURE_SCHEMA = "structured-original-native-order-export/v1"
JOIN_SCHEMA = "structured-original-native-order-join/v1"
TRAIN_ORIGIN = "y_train.xs(bound_source_context, level='type').index"
QUERY_ORIGIN = "y_test.index"

class _CapturedSourceLoader:
    """Execute the same immutable bytes already checked, ignoring bytecode caches."""
    def __init__(self, path, source):
        self.path = str(path)
        self.source = source

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        module.__file__ = self.path
        exec(compile(self.source, self.path, "exec"), module.__dict__)


def _load_dependencies(implementations):
    bridge_path = (implementations / "original-fold-bridge-v1/bridge.py").resolve()
    scorer_path = (implementations / "original-row-score-v1/scorer.py").resolve()
    bridge_source, scorer_source = bridge_path.read_bytes(), scorer_path.read_bytes()
    if hashlib.sha256(bridge_source).hexdigest() != BRIDGE_SHA256:
        raise RuntimeError("reviewed original fold bridge dependency changed")
    if hashlib.sha256(scorer_source).hexdigest() != SCORER_SHA256:
        raise RuntimeError("reviewed original row scorer dependency changed")

    def scorer_spec(name, location, *args, **kwargs):
        if (name != "structured_original_row_score" or Path(location).resolve() != scorer_path
                or args or kwargs):
            raise RuntimeError("unexpected dependency import requested by pinned bridge")
        return importlib.machinery.ModuleSpec(name, _CapturedSourceLoader(scorer_path, scorer_source))

    # Only this bridge's import statement receives the narrow facade. No sys.modules
    # or process-global import hook is changed. Its original source hash recheck can
    # still refuse a concurrent replacement, but its loader cannot execute it.
    facade = types.SimpleNamespace(util=types.SimpleNamespace(
        spec_from_file_location=scorer_spec, module_from_spec=importlib.util.module_from_spec))

    def bridge_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "importlib.util" and level == 0 and not fromlist:
            return facade
        return builtins.__import__(name, globals, locals, fromlist, level)

    module = types.ModuleType("structured_native_order_bridge")
    module.__file__ = str(bridge_path)
    module.__builtins__ = dict(vars(builtins), __import__=bridge_import)
    exec(compile(bridge_source, str(bridge_path), "exec"), module.__dict__)
    return module


bridge = _load_dependencies(Path(__file__).resolve().parent.parent)
scorer = bridge.SCORER


class NativeOrderError(ValueError):
    """An index export cannot be joined losslessly to original row membership."""


def _require(condition, message):
    if not condition:
        raise NativeOrderError(message)


def _canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    except (TypeError, ValueError) as exc:
        raise NativeOrderError("only finite JSON-compatible metadata is supported") from exc


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _freeze(value):
    return json.loads(_canonical(value))


def _fields(value, expected, name):
    _require(isinstance(value, dict) and set(value) == set(expected), name + " fields changed")


def _sha(value):
    try:
        return scorer._sha(value)
    except scorer.ScoreError as exc:
        raise NativeOrderError("expected SHA256 binding") from exc


def _declaration(value):
    _fields(value, ("source_commit", "producer_sha256", "runtime_manifest_sha256",
                    "source_run_receipt_sha256"), "source/runtime declaration")
    _require(value["source_commit"] == scorer.SOURCE_COMMIT and
             value["producer_sha256"] == PRODUCER_SHA256, "original source declaration changed")
    _sha(value["runtime_manifest_sha256"])
    _sha(value["source_run_receipt_sha256"])
    return _freeze(value)


def _row_key(row):
    # Existing scalar admission, followed by a type-sensitive serialization.
    # In particular Python's 1 == 1.0 must not silently equate native labels.
    try:
        scorer._row_key(row)
    except (scorer.ScoreError, TypeError, KeyError) as exc:
        raise NativeOrderError("unsupported original row identity") from exc
    return _canonical([row[name] for name in QUERY_NAMES])


def _snapshot(native_index, expected_names, expected_count, source_context=None):
    """Read metadata only, preserving the supplied .tolist() sequence exactly."""
    try:
        names = list(native_index.names)
        values = native_index.tolist()
        levels = list(native_index.levels)
    except (AttributeError, TypeError) as exc:
        raise NativeOrderError("native index must expose names, levels and tolist") from exc
    _require(names == list(expected_names), "native index level names/order unsupported")
    _require(isinstance(values, list) and len(values) == expected_count,
             "native index must cover exact original membership")
    _require(len(levels) == len(expected_names), "native level metadata does not match index")
    try:
        dtypes = [str(level.dtype) for level in levels]
    except AttributeError as exc:
        raise NativeOrderError("native level dtype declarations required") from exc
    _require(all(0 < len(dtype) <= 128 for dtype in dtypes), "invalid dtype declaration")
    exported, full_rows = [], []
    for values_row in values:
        _require(isinstance(values_row, (tuple, list)) and len(values_row) == len(expected_names),
                 "native index tuple shape changed")
        # Same NumPy-scalar item() convention used by the existing source exporter.
        converted = [scorer._native_scalar(value) for value in values_row]
        row = dict(zip(expected_names, converted))
        if source_context is not None:
            row["type"] = source_context
        _row_key(row)
        exported.append(converted)
        full_rows.append(row)
    descriptor = {"names": names,
                  "index_class": type(native_index).__module__ + "." + type(native_index).__qualname__,
                  "level_dtype_strings": dtypes,
                  "exported_rows_sha256": _digest(exported)}
    return full_rows, descriptor


def _positions(rows, original_positions, membership, name):
    result = []
    for row in rows:
        key = _row_key(row)
        _require(key in original_positions, name + " index contains changed source row identity")
        result.append(original_positions[key])
    _require(len(result) == len(membership) and len(set(result)) == len(result)
             and set(result) == set(membership), name + " index is not a complete one-to-one membership")
    return result


def _expected(owner_index, plan, secret_key):
    try:
        validated = bridge.validate_plan(owner_index, plan, secret_key)
    except (bridge.BridgeError, scorer.ScoreError) as exc:
        raise NativeOrderError("original owner index/fold plan invalid") from exc
    sessions = {session["session_id"]: session for session in owner_index["sessions"]}
    positions = {sid: {_row_key(row): i for i, row in enumerate(session["rows"])}
                 for sid, session in sessions.items()}
    return validated, sessions, positions


class NativeOrderRecorder:
    """Private one-record-per-unit export, with no model or feature operations.

    Restoring the dropped type field relies on the bound source-context callsite.
    Matching row labels cannot independently prove which native frame was used.
    """
    def __init__(self, owner_index, plan, secret_key, source_runtime_declaration):
        self.owner_index = _freeze(owner_index)
        self.plan, self.sessions, self.positions = _expected(self.owner_index, plan, secret_key)
        self.units = {unit["unit_id"]: unit for unit in self.plan["units"]}
        self.declaration = _declaration(source_runtime_declaration)
        self.records = {}
        self.closed = False

    def record(self, unit_id, *, source_context, training_index, query_index):
        _require(not self.closed, "native-order recorder already closed")
        _require(type(unit_id) is str and unit_id in self.units and unit_id not in self.records,
                 "unknown or already recorded original fit unit")
        unit = self.units[unit_id]
        _require(source_context == unit["source_context"], "native source-context binding changed")
        calibration = unit["calibration_row_membership"]
        query_membership = [query["row_position"] for query in unit["query_rows"]]
        train_rows, train_meta = _snapshot(training_index, TRAIN_NAMES, len(calibration), source_context)
        query_rows, query_meta = _snapshot(query_index, QUERY_NAMES, len(query_membership))
        original = self.positions[unit["session_id"]]
        training_order = _positions(train_rows, original, calibration, "training")
        query_order = _positions(query_rows, original, query_membership, "query")
        self.records[unit_id] = {"unit_id": unit_id,
                                 "calibration_row_order": training_order,
                                 "query_row_order": query_order,
                                 "training_index": train_meta, "query_index": query_meta}

    def finish(self):
        _require(not self.closed, "native-order recorder already closed")
        _require(set(self.records) == set(self.units), "all390 original fit index exports required")
        result = {"schema": CAPTURE_SCHEMA, "task_id": scorer.TASK_ID,
                  "owner_index_sha256": self.plan["owner_index_sha256"],
                  "membership_plan_sha256": self.plan["plan_sha256"],
                  "evidence_kind": self.owner_index["evidence_kind"],
                  "source_runtime_declaration": self.declaration,
                  "training_index_origin": TRAIN_ORIGIN, "query_index_origin": QUERY_ORIGIN,
                  "units": [self.records[unit["unit_id"]] for unit in self.plan["units"]],
                  "qualification": "structurally_validated_supplied_index_exports_only",
                  "source_native_parity_established": False, "execution_admitted": False,
                  "paper_win": None}
        result["capture_sha256"] = _digest(result)
        self.closed = True
        return _freeze(result)


def _validate_descriptor(descriptor, names, rows):
    _fields(descriptor, ("names", "index_class", "level_dtype_strings", "exported_rows_sha256"),
            "native index descriptor")
    _require(descriptor["names"] == list(names), "exported native names changed")
    _require(isinstance(descriptor["index_class"], str) and bool(descriptor["index_class"]),
             "native index class declaration missing")
    dtypes = descriptor["level_dtype_strings"]
    _require(isinstance(dtypes, list) and len(dtypes) == len(names)
             and all(isinstance(dtype, str) and 0 < len(dtype) <= 128 for dtype in dtypes),
             "native dtype declarations changed shape")
    _require(descriptor["exported_rows_sha256"] == _digest([[row[name] for name in names] for row in rows]),
             "native row order/value binding changed")


def join_native_order(owner_index, plan, secret_key, capture):
    """Join exported sequences to existing row positions and opaque query IDs.

    This is a private feature-selection recipe, not permission to run it or a
    certification that the supplied index originated in the declared source run.
    """
    validated, sessions, _ = _expected(owner_index, plan, secret_key)
    fields = ("schema", "task_id", "owner_index_sha256", "membership_plan_sha256", "evidence_kind",
              "source_runtime_declaration", "training_index_origin", "query_index_origin", "units",
              "qualification", "source_native_parity_established", "execution_admitted", "paper_win", "capture_sha256")
    _fields(capture, fields, "native-order capture")
    _require(capture["schema"] == CAPTURE_SCHEMA and capture["task_id"] == scorer.TASK_ID,
             "native-order capture identity changed")
    _require(capture["owner_index_sha256"] == validated["owner_index_sha256"]
             and capture["membership_plan_sha256"] == validated["plan_sha256"]
             and capture["evidence_kind"] == owner_index["evidence_kind"], "native-order capture changed owner inputs")
    _require(capture["capture_sha256"] == _digest({k: v for k, v in capture.items() if k != "capture_sha256"}),
             "native-order capture content changed")
    _require(capture["training_index_origin"] == TRAIN_ORIGIN and capture["query_index_origin"] == QUERY_ORIGIN,
             "native index origin declaration changed")
    _require(capture["qualification"] == "structurally_validated_supplied_index_exports_only"
             and capture["source_native_parity_established"] is False
             and capture["execution_admitted"] is False and capture["paper_win"] is None,
             "unsupported qualification promotion")
    declaration = _declaration(capture["source_runtime_declaration"])
    _require(isinstance(capture["units"], list) and len(capture["units"]) == len(validated["units"]),
             "complete390-unit capture required")
    expected_units = {unit["unit_id"]: unit for unit in validated["units"]}
    by_id = {}
    for record in capture["units"]:
        _fields(record, ("unit_id", "calibration_row_order", "query_row_order", "training_index", "query_index"),
                "native unit capture")
        uid = record["unit_id"]
        _require(type(uid) is str and uid in expected_units and uid not in by_id, "unknown or repeated native fit unit")
        unit = expected_units[uid]
        rows = sessions[unit["session_id"]]["rows"]
        for order_key, membership, descriptor_key, names in (
            ("calibration_row_order", unit["calibration_row_membership"], "training_index", TRAIN_NAMES),
            ("query_row_order", [q["row_position"] for q in unit["query_rows"]], "query_index", QUERY_NAMES),
        ):
            order = record[order_key]
            _require(isinstance(order, list) and all(type(position) is int for position in order)
                     and len(order) == len(membership) and len(set(order)) == len(order)
                     and set(order) == set(membership), "native row order changed original membership")
            _validate_descriptor(record[descriptor_key], names, [rows[position] for position in order])
        query_ids = {row["row_position"]: row["query_id"] for row in unit["query_rows"]}
        by_id[uid] = {"unit_id": uid, "feature_sha256": unit["feature_sha256"],
                      "calibration_row_order": list(record["calibration_row_order"]),
                      "query_row_order": list(record["query_row_order"]),
                      "query_ids_in_native_order": [query_ids[pos] for pos in record["query_row_order"]],
                      "training_index": copy.deepcopy(record["training_index"]),
                      "query_index": copy.deepcopy(record["query_index"])}
    return {"schema": JOIN_SCHEMA, "task_id": scorer.TASK_ID,
            "owner_index_sha256": validated["owner_index_sha256"],
            "membership_plan_sha256": validated["plan_sha256"],
            "capture_sha256": capture["capture_sha256"],
            "source_runtime_declaration": declaration,
            "units": [by_id[unit["unit_id"]] for unit in validated["units"]],
            "source_native_parity_established": False, "execution_admitted": False,
            "paper_win": None}
