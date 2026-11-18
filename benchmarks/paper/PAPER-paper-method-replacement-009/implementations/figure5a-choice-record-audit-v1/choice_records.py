"""Complete, keyed Figure 5A choice-output audit over operator-supplied support.

Construction only: a supplied census is NOT authenticated original paper support.
This module neither selects a scalar panel aggregate nor establishes improvement.
"""
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
import re


TASK = "PAPER-paper-method-replacement-009"
REGIONS = frozenset(("PO", "LP", "DG", "CA1", "VISa"))
METRICS_SHA256 = "833da18fb4f0e7f792ffb032c1d50b4c7556064ab9419ebe5b2f24ee8f671435"
MAX_DOCUMENT_BYTES = 64 * 1024 * 1024


class AuditError(ValueError):
    pass


def _need(condition, message):
    if not condition:
        raise AuditError(message)


def _closed(value, keys, context):
    _need(type(value) is dict and set(value) == set(keys), context + ": exact fields required")


def _text(value):
    _need(type(value) is str and 0 < len(value) <= 512 and value == value.strip()
          and not any(ord(c) < 32 for c in value), "nonempty bounded literal identity required")
    return value


def _digest(value):
    _need(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
          "lowercase SHA256 required")
    return value


def _id(value):
    if type(value) is int:
        _need(0 <= value <= 2**53 - 1, "trial integer outside exact nonnegative range")
        return ("int", value)
    return ("str", _text(value))


def _ordered_ids(values):
    _need(type(values) is list and values, "nonempty ordered trial identifiers required")
    keys = [_id(value) for value in values]
    _need(len(keys) == len(set(keys)), "duplicate typed trial identifier")
    return keys


def _document(raw, context):
    _need(type(raw) is bytes and 0 < len(raw) <= MAX_DOCUMENT_BYTES,
          context + ": bounded captured bytes required")

    def pairs(rows):
        result = {}
        for key, value in rows:
            _need(key not in result, context + ": duplicate JSON field")
            result[key] = value
        return result

    def bad_constant(_):
        raise AuditError(context + ": nonfinite JSON token")

    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=bad_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise AuditError(context + ": malformed JSON") from exc


def _plan(raw, expected_sha256):
    _need(sha256(raw).hexdigest() == _digest(expected_sha256), "support commitment mismatch")
    plan = _document(raw, "support")
    _closed(plan, ("schema", "task_id", "positive_class", "source_protocol_sha256",
                   "sessions", "cases"), "support")
    _need(plan["schema"] == "figure5a-choice-support/v1" and plan["task_id"] == TASK,
          "wrong task or support schema")
    _text(plan["positive_class"])
    _digest(plan["source_protocol_sha256"])
    _need(type(plan["sessions"]) is list and len(plan["sessions"]) == 10,
          "selected Figure 5A scope requires ten declared sessions")
    animals = {}
    for session in plan["sessions"]:
        _closed(session, ("session", "animal"), "session")
        sid = _text(session["session"])
        _need(sid not in animals, "duplicate session")
        animals[sid] = _text(session["animal"])
    _need(type(plan["cases"]) is list and plan["cases"], "explicit nonempty case incidence required")
    cases, cells, covered_regions, covered_sessions = {}, set(), set(), set()
    expected_labels = {sid: set() for sid in animals}
    for case in plan["cases"]:
        _closed(case, ("case_id", "session", "region", "condition", "trial_ids"), "case")
        cid, sid = _text(case["case_id"]), _text(case["session"])
        region, condition = _text(case["region"]), _text(case["condition"])
        _need(cid not in cases, "duplicate case identity")
        _need(sid in animals and region in REGIONS, "case outside declared session/region support")
        cell = (sid, region, condition)
        _need(cell not in cells, "duplicate session/region/condition incidence")
        cells.add(cell)
        keys = _ordered_ids(case["trial_ids"])
        expected_labels[sid].update(keys)
        cases[cid] = (case, keys)
        covered_regions.add(region)
        covered_sessions.add(sid)
    _need(covered_regions == REGIONS and covered_sessions == set(animals),
          "declared original panel axes must all have explicit support")
    return plan, animals, cases, expected_labels


def _probability(value):
    _need(type(value) in (int, float), "probability must be a real number, excluding booleans")
    try:
        valid = isfinite(value) and 0 <= value <= 1
    except OverflowError:
        valid = False
    _need(valid, "probability outside finite [0,1]")
    return float(value)


def _predictions(raw, support_sha256, positive_class, cases):
    doc = _document(raw, "prediction")
    _closed(doc, ("schema", "support_sha256", "positive_class", "cases"), "prediction")
    _need(doc["schema"] == "figure5a-choice-predictions/v1", "wrong prediction schema")
    _need(doc["support_sha256"] == support_sha256 and doc["positive_class"] == positive_class,
          "prediction support or class orientation mismatch")
    _need(type(doc["cases"]) is list and len(doc["cases"]) == len(cases),
          "complete case prediction support required")
    parsed = {}
    for result in doc["cases"]:
        _closed(result, ("case_id", "predictions"), "predicted case")
        cid = _text(result["case_id"])
        _need(cid in cases and cid not in parsed, "unexpected or duplicate predicted case")
        _need(type(result["predictions"]) is list, "ordered prediction records required")
        expected = cases[cid][1]
        _need(len(result["predictions"]) == len(expected), "complete trial prediction support required")
        values = {}
        for row in result["predictions"]:
            _closed(row, ("trial_id", "positive_probability"), "prediction row")
            key = _id(row["trial_id"])
            _need(key not in values, "duplicate trial prediction")
            values[key] = _probability(row["positive_probability"])
        _need(set(values) == set(expected), "prediction trial identity mismatch")
        parsed[cid] = [values[key] for key in expected]
    _need(set(parsed) == set(cases), "missing predicted case")
    return parsed


def _labels(raw, support_sha256, positive_class, expected):
    doc = _document(raw, "labels")
    _closed(doc, ("schema", "support_sha256", "positive_class", "sessions"), "labels")
    _need(doc["schema"] == "figure5a-choice-labels/v1", "wrong label schema")
    _need(doc["support_sha256"] == support_sha256 and doc["positive_class"] == positive_class,
          "label support or class orientation mismatch")
    _need(type(doc["sessions"]) is list and len(doc["sessions"]) == len(expected),
          "complete protected session support required")
    parsed = {}
    for session in doc["sessions"]:
        _closed(session, ("session", "labels"), "label session")
        sid = _text(session["session"])
        _need(sid in expected and sid not in parsed, "unexpected or duplicate label session")
        _need(type(session["labels"]) is list, "protected label records required")
        values = {}
        for row in session["labels"]:
            _closed(row, ("trial_id", "label"), "label row")
            key = _id(row["trial_id"])
            _need(key not in values, "duplicate protected trial label")
            _need(type(row["label"]) is int and row["label"] in (0, 1), "explicit integer 0/1 label required")
            values[key] = row["label"]
        _need(set(values) == expected[sid], "protected trial support mismatch")
        parsed[sid] = values
    return parsed


def _metric_function():
    path = Path(__file__).resolve().parent.parent / "figure5-metric-diagnostics-v1" / "metrics.py"
    raw = path.read_bytes()
    _need(sha256(raw).hexdigest() == METRICS_SHA256, "metric implementation pin mismatch")
    namespace = {"__name__": "figure5_choice_pinned_diagnostics", "__file__": str(path)}
    exec(compile(raw, str(path), "exec"), namespace)
    return namespace["score_case"]


def audit_choice_profile(support_bytes, prediction_bytes, load_protected_labels, *, expected_support_sha256):
    """Recompute one complete choice profile without choosing a panel winner.

    All prediction identities/probabilities are validated before the label callback
    is called once. This call ordering is not filesystem/process isolation. Callers
    separately own actual source qualification, precommit timing and target custody.
    Label/prediction bytes are already captured snapshots; no pathname is reopened.
    """
    _need(type(support_bytes) is bytes, "captured support bytes required")
    _need(callable(load_protected_labels), "operator-owned protected-label callback required")
    plan, animals, cases, expected_labels = _plan(support_bytes, expected_support_sha256)
    predictions = _predictions(prediction_bytes, expected_support_sha256, plan["positive_class"], cases)
    # Resolve the pinned numerical implementation before accessing protected labels.
    score_case = _metric_function()
    label_bytes = load_protected_labels()
    labels = _labels(label_bytes, expected_support_sha256, plan["positive_class"], expected_labels)
    rows = []
    for cid, (case, keys) in cases.items():
        score = score_case("choice", [labels[case["session"]][key] for key in keys], predictions[cid])
        auc = score["metrics"]["auc"]
        rows.append({"case_id": cid, "session": case["session"], "animal": animals[case["session"]],
                     "region": case["region"], "condition": case["condition"],
                     "trials": len(keys), "value": auc["value"],
                     "undefined_reason": auc["undefined_reason"]})
    return {"schema": "figure5a-choice-record-audit/v1", "task_id": TASK,
            "support_sha256": expected_support_sha256,
            "prediction_sha256": sha256(prediction_bytes).hexdigest(),
            "protected_label_sha256": sha256(label_bytes).hexdigest(),
            "metric_source_sha256": METRICS_SHA256,
            "source_protocol_sha256": plan["source_protocol_sha256"],
            "positive_class": plan["positive_class"], "expected_cases": len(cases),
            "expected_sessions": len(animals), "expected_animals": len(set(animals.values())),
            "prediction_records": sum(len(item[1]) for item in cases.values()),
            "complete_prediction_coverage": True, "all_case_auc_defined": all(row["value"] is not None for row in rows),
            "rows": rows, "panel_aggregate": None, "paper_win": None,
            "scientific_outcome": "unknown", "source_qualification": "not_established_by_supplied_support",
            "runtime_isolation": "not_established", "research_qualified": False}
