"""NEURAL-030 candidate output contract and operator-private paired evaluation.

No candidate launcher, fitting routine, native loader, or identity verifier lives
here. The unchanged sibling score.py owns all count arithmetic and hierarchy.
"""
import copy
import json
import math
import re

from candidate_views import validate_plan, validate_view, query_packet
from score import score_predictions

ARMS = ("context_handle", "grc", "cf", "joint")


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _closed(value, fields, message):
    _require(type(value) is dict and set(value) == set(fields), message)


def _opaque(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{32}", value) is not None


def _counts(value, count):
    _require(type(value) is list and len(value) == count, "prediction bin membership")
    for item in value:
        _require(type(item) in (int, float), "prediction counts must be numbers, not booleans")
        try:
            okay = math.isfinite(item) and item >= 0
        except (OverflowError, ValueError):
            okay = False
        _require(okay, "prediction counts must be finite and nonnegative")


def parse_response(body, *, max_bytes):
    """Decode an already bounded response; caller supplies its resource limit.

    Syntax validation is separate from validate_response's exact case contract.
    This in-memory function does not impose a process or filesystem limit.
    """
    _require(type(max_bytes) is int and max_bytes > 0, "explicit positive response limit")
    _require(type(body) is bytes and len(body) <= max_bytes, "response byte extent")

    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, "duplicate JSON key")
            result[key] = value
        return result

    def constant(value):
        raise ValueError("nonfinite JSON constant: " + value)

    def floating(value):
        number = float(value)
        _require(math.isfinite(number), "nonfinite JSON number")
        return number

    try:
        result = json.loads(body.decode("utf-8"), object_pairs_hook=pairs,
                            parse_constant=constant, parse_float=floating)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("response must be finite UTF-8 JSON") from exc
    _require(type(result) is dict, "response must be an object")
    return result


def validate_response(response, case, arm):
    """Return predictions in frozen plan order, accepting keyed output order."""
    _require(arm in ARMS, "unknown arm")
    _closed(response, ("schema", "task_id", "session_id", "arm", "predictions"),
            "response fields")
    _require(response["schema"] == "neural030_prediction_v1"
             and response["task_id"] == "NEURAL-030"
             and response["session_id"] == case["session_id"]
             and response["arm"] == arm, "response case/arm binding")
    required = {row["trial_id"]: row["bin_count"] for row in case["required_predictions"]}
    _require(type(response["predictions"]) is list, "prediction rows")
    found = {}
    for row in response["predictions"]:
        _closed(row, ("trial_id", "counts"), "prediction row fields")
        tid = row["trial_id"]
        _require(type(tid) is str and tid in required and tid not in found,
                 "duplicate or foreign prediction trial")
        _counts(row["counts"], required[tid])
        found[tid] = row
    _require(set(found) == set(required), "missing prediction trial")
    return [copy.deepcopy(found[tid]) for tid in required]


def _panel_responses(plan, responses, arm):
    _require(type(responses) is list and len(responses) == 16, "complete response panel")
    required = {case["session_id"]: case for case in plan["cases"]}
    found = {}
    for response in responses:
        _require(type(response) is dict, "response object")
        sid = response.get("session_id")
        _require(type(sid) is str and sid in required and sid not in found,
                 "duplicate or foreign response session")
        found[sid] = validate_response(response, required[sid], arm)
    _require(set(found) == set(required), "missing response session")
    return [row for sid in required for row in found[sid]]


def _expected(plan, expected):
    required = {row["trial_id"]: (case["session_id"], row["bin_count"])
                for case in plan["cases"] for row in case["required_predictions"]}
    _require(type(expected) is list, "private expected rows")
    found = {}
    for row in expected:
        _closed(row, ("trial_id", "session_id", "bin_count", "counts"), "private target fields")
        tid = row["trial_id"]
        _require(type(tid) is str and tid in required and tid not in found,
                 "duplicate or foreign target trial")
        _require(type(row["bin_count"]) is int and
                 (row["session_id"], row["bin_count"]) == required[tid], "target plan binding")
        found[tid] = row
    _require(set(found) == set(required), "complete private target panel")
    # Exact integer target semantics are checked by the original scorer.
    return [found[tid] for tid in required]


def _five_mouse_binding(plan, binding):
    _closed(binding, ("verification_status", "binding_id", "evidence_sha256", "session_to_mouse"),
            "mouse binding fields")
    sessions = {case["session_id"] for case in plan["cases"]}
    mapping = binding["session_to_mouse"]
    _require(type(mapping) is dict and set(mapping) == sessions, "complete session binding")
    _require(all(_opaque(value) for value in mapping.values()) and len(set(mapping.values())) == 5,
             "exactly five declared opaque mouse IDs")
    # The scorer verifies the remaining attestation fields. None authenticate biology.


def mismatch_query_packet(view):
    """Cyclic +1 query-trial mismatch for an already fitted joint candidate.

    Return (candidate_packet, operator_only_donor_rows). Neural time and both
    arrays move together; recipient context and requested target IDs stay fixed.
    This deliberately returns no calibration data or refitting instruction.
    """
    validate_view(view)
    _require(view["arm"] == "joint", "mismatch requires joint view")
    _require(len(view["query"]) >= 2, "mismatch needs two query trials; do not prune cases")
    result = query_packet(view)
    donors = []
    for index, recipient in enumerate(result["query"]):
        donor = view["query"][(index + 1) % len(view["query"])]
        for key in ("neural_time", "grc", "cf"):
            recipient[key] = copy.deepcopy(donor[key])
        donors.append({"recipient_trial_id": recipient["trial_id"],
                       "donor_trial_id": donor["trial_id"]})
    return result, donors


def score_matched_panel(plan, expected, outputs, *, fixed_reference_predictions,
                        mouse_binding, mismatch_outputs=None):
    """Evaluate every case/arm using unchanged count arithmetic, privately.

    `outputs` is exactly four lists of sixteen per-case responses. The caller
    supplies the original context/handle ridge predictions as a mandatory fixed
    anchor. This function cannot prove their producer or matched candidate fits.
    All returned rows, including target-derived scores, are evaluator-private.
    """
    validate_plan(plan)
    _closed(outputs, ARMS, "all four candidate arms required")
    labels = _expected(plan, expected)
    _five_mouse_binding(plan, mouse_binding)
    _require(type(fixed_reference_predictions) is list, "complete fixed reference required")
    predictions = {arm: _panel_responses(plan, outputs[arm], arm) for arm in ARMS}
    if mismatch_outputs is not None:
        _require(all(len(case["required_predictions"]) >= 2 for case in plan["cases"]),
                 "mismatch needs two query trials in every case; do not prune cases")
    mismatch = None if mismatch_outputs is None else _panel_responses(plan, mismatch_outputs, "joint")
    fixed = {arm: score_predictions(labels, predictions[arm],
                    baseline_predictions=fixed_reference_predictions, mouse_binding=mouse_binding)
             for arm in ARMS}
    matched = {arm: score_predictions(labels, predictions[arm],
                      baseline_predictions=predictions["context_handle"], mouse_binding=mouse_binding)
               for arm in ("grc", "cf", "joint")}
    alignment = None if mismatch is None else score_predictions(labels, predictions["joint"],
                      baseline_predictions=mismatch, mouse_binding=mouse_binding)
    gains = [row["mse_gain"] for row in matched["joint"]["mouse_results"]]
    return {
        "schema": "neural030_matched_panel_evaluation_v1",
        "task_id": "NEURAL-030",
        "primary_preserved": "joint fixed-reference mouse-macro MSE gain",
        "fixed_reference_comparisons": fixed,
        "additive_matched_candidate_comparisons": matched,
        "matched_primary_condition": "joint",
        "mismatch_alignment_diagnostic": alignment,
        "mismatch_status": "not supplied; diagnostic unavailable" if alignment is None
                            else "descriptive only; frozen-fit execution not authenticated",
        "descriptive_mouse_gain_range": {"minimum": min(gains), "maximum": max(gains),
                                         "mouse_count": 5, "confidence_interval": None},
        "interpretation": {
            "fixed_anchor": "gain over a fixed ridge reference is not a neural attribution",
            "matched": "incremental predictive utility conditional on matched procedure, exposure and resources",
            "mismatch": "aligned-versus-mismatched neural bundles; no exchangeability or permutation inference",
            "scope": "retrospective within-session held-out complete trials; same five declared mice",
        },
        "unverified": ["native data and biological identities", "candidate source/fit matching",
                       "reference producer", "frozen-fit mismatch", "runtime isolation and resources",
                       "predeclared inferential uncertainty and empirical reference adequacy"],
        "scientific_qualification": False,
        "candidate_execution_performed_by_evaluator": False,
    }
