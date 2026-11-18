"""Operator-side direct numerical observations and probability capture for N059.

This is an in-process state machine, not a participant sandbox or provider.
Only its returned JSON bytes may cross a separately qualified boundary.
"""
from copy import deepcopy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
CONDITIONS = ("SH", "SHN", "SBH", "SBHN")
PINS = {
    "prepared-support-v2/support.py": "ec960cb594d829abfeca94d3decaa7736e66c1626a094ab5c7ab56959646abe8",
    "prepared-support-v2/_retained.py": "c0221ab1211df70e92f7cbdb6577e40c20761db5a0c2d2f6f098e2c25cf00a60",
    "registered-runtime/complete-process-v1/scientific/__init__.py": "bb5787781385927b7c93bda57d56888b18597a56b45f734350ad8ea0c95ca7ab",
    "registered-runtime/complete-process-v1/scientific/contracts.py": "bfac56e3f7c30fb6a9f8d263706dd7578ee58e383a40d88f626cfcea52098557",
    "registered-runtime/complete-process-v1/scientific/diagnostics.py": "1a3aeb8defa32d1fa5b339a2f2501b176d21e4fb7beb2791a639c436cff87054",
    "registered-runtime/complete-process-v1/scientific/evaluation.py": "40a02d51e8db4d9aee0a4c0f983431b96caa769da2513d5591dd34826799e09d",
    "registered-runtime/complete-process-v1/scientific/preparation.py": "ac261ceb483e3b9d8d1e7a15befb59a9dad9dc8ac41f632fe42058f9807c3827",
}


class DeliveryError(ValueError):
    """Stable code only; do not reflect protected operand values."""


def need(condition, code):
    if not condition:
        raise DeliveryError(code)


def bounded_json(value, maximum):
    """Canonical byte encoding, refused before exceeding a selected ceiling."""
    need(type(maximum) is int and maximum > 0, "positive_byte_ceiling")
    body = bytearray()
    try:
        for piece in json.JSONEncoder(sort_keys=True, separators=(",", ":"),
                                      ensure_ascii=True, allow_nan=False).iterencode(value):
            encoded = piece.encode("ascii")
            need(len(body) + len(encoded) + 1 <= maximum, "json_byte_ceiling")
            body.extend(encoded)
    except (TypeError, OverflowError, RecursionError, ValueError) as error:
        if isinstance(error, DeliveryError):
            raise
        raise DeliveryError("invalid_json_operand") from error
    return bytes(body) + b"\n"


def pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def _source_module(name, path, body):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    # Execute the bytes just authenticated, not a later reread or stale bytecode.
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


def dependencies():
    """Use the existing original-slot validator and feature projection unchanged.

    The legacy validator uses an unqualified `_retained` import. Bind that name
    only during its trusted import and restore the prior operator module after.
    This trusted bootstrap is not thread-safe or an untrusted-code boundary.
    """
    bodies = {}
    for relative, expected in PINS.items():
        body = (HERE.parent / relative).read_bytes()
        need(hashlib.sha256(body).hexdigest() == expected, "dependency_source_changed")
        bodies[relative] = body
    retained_path = HERE.parent / "prepared-support-v2/_retained.py"
    retained = _source_module("_neural059_direct_retained", retained_path,
                              bodies["prepared-support-v2/_retained.py"])
    missing = object()
    prior = sys.modules.get("_retained", missing)
    try:
        sys.modules["_retained"] = retained
        support = _source_module("_neural059_direct_support",
                                 HERE.parent / "prepared-support-v2/support.py",
                                 bodies["prepared-support-v2/support.py"])
    finally:
        if prior is missing:
            del sys.modules["_retained"]
        else:
            sys.modules["_retained"] = prior
    relative = "registered-runtime/complete-process-v1/scientific/preparation.py"
    preparation = _source_module("_neural059_direct_preparation",
                                 HERE.parent / relative, bodies[relative])
    return support, preparation


def parse_response(body, maximum):
    need(type(body) is bytes and len(body) <= maximum, "response_bytes")

    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, "duplicate_response_key")
            result[key] = value
        return result

    try:
        result = json.loads(body.decode("utf-8"), object_pairs_hook=pairs,
                            parse_constant=lambda _: (_ for _ in ()).throw(
                                DeliveryError("nonfinite_response")))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise DeliveryError("response_json") from error
    need(type(result) is dict and set(result) ==
         {"case_id", "observation_sha256", "p_left"}, "response_schema")
    probability = result["p_left"]
    try:
        valid = (type(probability) in (int, float) and math.isfinite(probability)
                 and 0 <= probability <= 1)
    except OverflowError:
        valid = False
    need(valid, "response_probability")
    return result


class DirectCollection:
    """Trusted owner of the full 29-session collection and protected preparation.

    Four independent participant contexts must answer a trial before any of them
    can see the next trial's lawful history. This class does not create or
    authenticate those contexts. It neither grades nor invokes any model/tool.
    """

    def __init__(self, prepared_sessions, *, max_input_bytes, max_packet_bytes,
                 max_response_bytes, max_total_response_bytes):
        for limit in (max_input_bytes, max_packet_bytes, max_response_bytes,
                      max_total_response_bytes):
            need(type(limit) is int and limit > 0, "positive_byte_ceiling")
        encoded = bounded_json(prepared_sessions, max_input_bytes)
        self._input_pin = pin(encoded)
        support, self._preparation = dependencies()
        support.validate_prepared(prepared_sessions)
        self._sessions = deepcopy(prepared_sessions)
        self._queries = [[c for c in s["cases"] if c["split"] == "test"]
                         for s in self._sessions]
        need(all(self._queries), "empty_required_session_support")
        self._positions = [0] * len(self._sessions)
        self._pending = [set() for _ in self._sessions]
        self._seen = {}
        self._records = []
        self._failed = False
        self._sealed = False
        self._packet_limit = max_packet_bytes
        self._response_limit = max_response_bytes
        self._response_total_limit = max_total_response_bytes
        self._response_total = 0

    def _live(self):
        need(not self._failed, "collection_failed")
        need(not self._sealed, "collection_sealed")

    def channel(self, session_index, condition):
        """Operator-only binding: never give the collection itself to a model."""
        self._live()
        need(type(session_index) is int and 0 <= session_index < len(self._sessions),
             "session_index")
        need(type(condition) is str and condition in CONDITIONS, "condition")
        return DirectChannel(self, session_index, condition)

    def finish(self):
        """Return an operator artifact only after every required response exists."""
        self._live()
        need(all(position == len(cases) for position, cases in
                 zip(self._positions, self._queries)), "incomplete_full_support")
        need(all(not pending for pending in self._pending), "incomplete_panel")
        self._sealed = True
        return {
            "schema": "neural059-direct-probability-collection/v1",
            "status": "complete_capture_source_only_unqualified",
            "scientific_qualification": False,
            "participant_isolation_qualified": False,
            "model_execution_proved": False,
            "prepared_input": deepcopy(self._input_pin),
            "sessions": len(self._sessions),
            "conditions": list(CONDITIONS),
            "expected_responses": 4 * sum(map(len, self._queries)),
            "captured_response_bytes": self._response_total,
            "predictions": deepcopy(self._records),
            "score": None,
        }


class DirectChannel:
    """Trusted adapter handle bound to one session and information condition."""

    def __init__(self, owner, session_index, condition):
        self._owner, self._session, self._condition = owner, session_index, condition

    def calibration(self, split, index):
        owner = self._owner
        owner._live()
        need(type(split) is str and split in ("train", "val"), "calibration_split")
        cases = [c for c in owner._sessions[self._session]["cases"] if c["split"] == split]
        need(type(index) is int and 0 <= index < len(cases), "calibration_index")
        view = owner._preparation.project_case(cases[index], self._condition, include_label=True)
        return bounded_json({"role": "calibration", "split": split, "observation": view},
                            owner._packet_limit)

    def calibration_counts(self):
        owner = self._owner
        owner._live()
        cases = owner._sessions[self._session]["cases"]
        return {split: sum(c["split"] == split for c in cases) for split in ("train", "val")}

    def observation(self):
        owner = self._owner
        owner._live()
        index = owner._positions[self._session]
        cases = owner._queries[self._session]
        need(index < len(cases), "session_complete")
        need(self._condition not in owner._pending[self._session], "panel_barrier")
        view = owner._preparation.project_case(cases[index], self._condition, include_label=False)
        body = bounded_json({"role": "query", "observation": view}, owner._packet_limit)
        owner._seen[(self._session, self._condition, index)] = pin(body)
        return body

    def answer(self, body):
        """Capture once. Any invalid submission poisons the entire collection."""
        owner = self._owner
        owner._live()
        try:
            need(type(body) is bytes, "response_bytes")
            owner._response_total += len(body)
            need(owner._response_total <= owner._response_total_limit, "response_total_ceiling")
            response = parse_response(body, owner._response_limit)
            index = owner._positions[self._session]
            cases = owner._queries[self._session]
            need(index < len(cases), "session_complete")
            need(self._condition not in owner._pending[self._session], "duplicate_response")
            observed = owner._seen.get((self._session, self._condition, index))
            need(observed is not None, "observation_not_delivered")
            need(response["case_id"] == cases[index]["case_id"] and
                 response["observation_sha256"] == observed["sha256"], "response_identity")
            owner._records.append({
                "session_index": self._session, "condition": self._condition,
                "case_id": response["case_id"], "p_left": response["p_left"],
                "observation": deepcopy(observed), "response": pin(body),
                "response_utf8": body.decode("utf-8"),
            })
            owner._pending[self._session].add(self._condition)
            if owner._pending[self._session] == set(CONDITIONS):
                owner._positions[self._session] += 1
                owner._pending[self._session].clear()
        except BaseException:
            owner._failed = True
            raise
        return {"accepted": True}
