"""Owner-only original-fold membership and complete prediction assembly.

This module neither prepares neural features nor runs or isolates a participant.
Its row positions and private plan must never enter a participant environment.
"""
from __future__ import annotations

import copy
import hashlib
import hmac
import importlib.util
import json
from pathlib import Path

SCORER_SHA256 = "ef7146154f054e29f77a74757d0b82c4000692ca47ef2187d7629fda29cddfc9"
PLAN_SCHEMA = "structured-original-fold-membership/v1"
RESPONSE_SCHEMA = "structured-original-unit-response/v1"


class BridgeError(ValueError):
    """A plan or response fails the frozen original-panel contract."""


def _load_scorer():
    path = Path(__file__).resolve().parent.parent / "original-row-score-v1/scorer.py"
    source = path.read_bytes()
    if hashlib.sha256(source).hexdigest() != SCORER_SHA256:
        raise BridgeError("original-row scorer differs from the reviewed dependency")
    spec = importlib.util.spec_from_file_location("structured_original_row_score", path)
    module = importlib.util.module_from_spec(spec)
    # Execute the verified snapshot, never a changed path or an accepted .pyc.
    module.__file__ = str(path)
    exec(compile(source, str(path), "exec"), module.__dict__)
    return module


SCORER = _load_scorer()


def _canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    except (TypeError, ValueError) as exc:
        raise BridgeError("expected finite JSON-compatible owner metadata") from exc


def _hash(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _key(key):
    if type(key) is not bytes or len(key) < 32:
        raise BridgeError("operator must retain a secret key of at least 32 bytes")
    return key


def _token(key, domain, *parts):
    return hmac.new(key, _canonical([domain, *parts]), hashlib.sha256).hexdigest()


def _fields(value, expected):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise BridgeError("missing or unexpected response fields")


def _validated_index(owner_index):
    try:
        return SCORER.validate_index(owner_index)
    except (SCORER.ScoreError, TypeError, KeyError) as exc:
        raise BridgeError("invalid original owner index: " + str(exc)) from exc


def build_plan(owner_index, secret_key):
    """Construct all 390 original fit memberships, without feature values.

    The training list denotes membership in owner-index order. The native
    producer's pandas Index.difference/reindex ordering remains to be exported
    and independently checked before any source-concordance fit. This is not
    an assertion of native training-row-order parity.
    """
    key = _key(secret_key)
    validated = _validated_index(owner_index)
    owner_hash = SCORER.digest(owner_index)
    by_session = {session["session_id"]: session for session in owner_index["sessions"]}
    units = []
    for session_ids in SCORER.SESSIONS.values():
        for sid in session_ids:
            session = by_session[sid]
            folds = validated[sid]["folds"]
            for fold in range(10):
                queries = [position for position, row in enumerate(session["rows"])
                           if folds[row["trial"]] == fold]
                for source in SCORER.CONTEXTS:
                    unit_id = _token(key, "structured-unit-v1", owner_hash, sid, fold, source)
                    calibration = [position for position, row in enumerate(session["rows"])
                                   if folds[row["trial"]] != fold and row["type"] == source]
                    # Sorting opaque tokens prevents this view encoding original row order.
                    query_rows = sorted(
                        ({"query_id": _token(key, "structured-query-v1", owner_hash,
                                             unit_id, position), "row_position": position}
                         for position in queries), key=lambda row: row["query_id"])
                    units.append({"unit_id": unit_id, "session_id": sid,
                                  "source_context": source, "split": fold,
                                  "feature_sha256": session["feature_sha256"],
                                  "calibration_row_membership": calibration,
                                  "query_rows": query_rows})
    plan = {"schema": PLAN_SCHEMA, "task_id": SCORER.TASK_ID,
            "source_commit": SCORER.SOURCE_COMMIT,
            "owner_index_sha256": owner_hash,
            "evidence_kind": owner_index["evidence_kind"],
            "units": units,
            "calibration_order": "membership_only_native_training_order_unresolved",
            "delivery_qualification": "owner_metadata_component_only",
            "execution_admitted": False, "paper_win": None}
    plan["plan_sha256"] = _hash(plan)
    return plan


def validate_plan(owner_index, plan, secret_key):
    """Reconstruct the full expected plan, rather than trusting a rehashed subset."""
    expected = build_plan(owner_index, secret_key)
    if not hmac.compare_digest(_canonical(plan), _canonical(expected)):
        raise BridgeError("plan differs from complete frozen original fold membership")
    return expected


def response_template(plan, unit_id):
    """Return only a unit's opaque query IDs; never row positions or targets.

    Caller must first validate the private plan. This shape alone is not a
    participant input packet: neural feature projection is not implemented here.
    """
    if type(unit_id) is not str:
        raise BridgeError("unit identity must be a string")
    matches = [unit for unit in plan["units"] if unit["unit_id"] == unit_id]
    if len(matches) != 1:
        raise BridgeError("unknown or duplicate unit identity")
    return {"schema": RESPONSE_SCHEMA, "plan_sha256": plan["plan_sha256"],
            "unit_id": unit_id,
            "query_ids": [row["query_id"] for row in matches[0]["query_rows"]]}


def assemble_predictions(owner_index, plan, secret_key, responses, run_receipt_sha256):
    """Join exactly one complete response per fit to the existing scorer format.

    External runtime receipts are opaque provenance bindings, not evidence of
    fresh fitting, chronology, per-fit state isolation or resource enforcement.
    The caller must freeze/authenticate the owner index before any actor output.
    """
    expected = validate_plan(owner_index, plan, secret_key)
    try:
        SCORER._sha(run_receipt_sha256)
    except SCORER.ScoreError as exc:
        raise BridgeError("a run receipt SHA256 binding is required") from exc
    if not isinstance(responses, list) or len(responses) != len(expected["units"]):
        raise BridgeError("exactly 390 complete original fit responses are required")
    units = {unit["unit_id"]: unit for unit in expected["units"]}
    by_session = {session["session_id"]: session for session in owner_index["sessions"]}
    assembled = {sid: [dict(copy.deepcopy(row), split=None, predictions={})
                       for row in session["rows"]] for sid, session in by_session.items()}
    seen = set()
    for response in responses:
        _fields(response, ("schema", "plan_sha256", "unit_id", "predictions"))
        unit_id = response["unit_id"]
        if (response["schema"] != RESPONSE_SCHEMA or
                response["plan_sha256"] != expected["plan_sha256"] or
                type(unit_id) is not str or unit_id not in units or unit_id in seen):
            raise BridgeError("unexpected, replayed or differently bound fit response")
        unit = units[unit_id]
        query_map = {row["query_id"]: row["row_position"] for row in unit["query_rows"]}
        predictions = response["predictions"]
        if not isinstance(predictions, list) or len(predictions) != len(query_map):
            raise BridgeError("fit response does not cover every original query row")
        answered = set()
        for item in predictions:
            _fields(item, ("query_id", "time_bin"))
            query_id = item["query_id"]
            if type(query_id) is not str or query_id not in query_map or query_id in answered:
                raise BridgeError("unexpected, duplicated or cross-unit query identity")
            if type(item["time_bin"]) is not int or not 0 <= item["time_bin"] < 40:
                raise BridgeError("prediction must be an integer time bin in 0..39")
            row = assembled[unit["session_id"]][query_map[query_id]]
            row["split"] = unit["split"]
            row["predictions"][unit["source_context"]] = item["time_bin"]
            answered.add(query_id)
        seen.add(unit_id)
    artifact = {"schema": "structured-original-predictions/v1",
                "owner_index_sha256": expected["owner_index_sha256"],
                "run_receipt_sha256": run_receipt_sha256,
                "sessions": [{"session_id": sid, "rows": assembled[sid]}
                             for ids in SCORER.SESSIONS.values() for sid in ids]}
    # The independent existing scorer is the final coverage/fold/class authority.
    SCORER.score(owner_index, artifact)
    return artifact
