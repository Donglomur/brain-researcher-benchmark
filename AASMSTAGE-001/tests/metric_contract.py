"""Public arithmetic for complete source-keyed Welch LOSO outputs; no fitting."""
import csv
from decimal import Decimal, InvalidOperation
import json
import math
from pathlib import Path

import numpy as np

METHOD_SHA = "5a935b2a61676fafab304fd28343c9720d11e1b7f3c3f5c7f2b12b2744527793"
SOURCE_SHA = "241be998b50465f17431dba963499dbb34c355a2e17533a1dd0d659f4e837cbb"
PIPELINE = "sleepedf-welch256-loso-v2"
CLASSES = ("W", "N1", "N2", "N3", "REM")
FEATURES = tuple(f"{band}_{channel}" for band in ("delta", "theta", "alpha", "sigma", "beta")
                 for channel in ("fpz_cz", "pz_oz"))
PROBS = ("prob_w", "prob_n1", "prob_n2", "prob_n3", "prob_rem")
BIN_COUNTS = np.array([10, 10, 8, 10, 37], dtype=float)
ANNOTATION_STATUSES = ("outside_crop_or_recording", "unsupported_stage", "used", "no_complete_chunk")
EPOCH_STATUSES = ("unsupported_stage", "outside_recording", "overlap_bad_annotation", "retained")


def need(condition, message):
    assert condition, message


def number(value):
    need(not isinstance(value, (bool, np.bool_)) and value is not None, "finite number required")
    try:
        value = float(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise AssertionError("finite number required") from exc
    need(math.isfinite(value), "finite number required")
    return value


def integer(value, minimum=0):
    need(not isinstance(value, (bool, np.bool_)) and value is not None, "integer required")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise AssertionError("integer required") from exc
    need(parsed.is_finite() and parsed == parsed.to_integral_value(), "integer required")
    value = int(parsed)
    need(value >= minimum, "integer below allowed minimum")
    return value


def flag(value):
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    need(isinstance(value, str) and value.lower() in ("0", "1", "true", "false"), "boolean required")
    return value.lower() in ("1", "true")


def finite_json(value):
    if isinstance(value, dict):
        for item in value.values():
            finite_json(item)
    elif isinstance(value, list):
        for item in value:
            finite_json(item)
    elif isinstance(value, float):
        need(math.isfinite(value), "nonfinite JSON number")


def json_loads(text):
    def pairs(items):
        out = {}
        for key, value in items:
            need(key not in out, "duplicate JSON key")
            out[key] = value
        return out
    value = json.loads(text, object_pairs_hook=pairs,
                       parse_constant=lambda x: (_ for _ in ()).throw(AssertionError("nonfinite JSON number")))
    finite_json(value)
    return value


def read_json(path):
    value = json_loads(Path(path).read_text(encoding="utf-8"))
    need(isinstance(value, dict), "JSON object required")
    return value


def close(actual, expected, atol=1e-6, rtol=0, field="numeric value"):
    actual, expected = number(actual), number(expected)
    need(abs(actual-expected) <= atol+rtol*abs(expected), f"{field} differs")


def match(actual, expected, field="metadata", closed=False):
    """Type-aware required fields; source/method objects explicitly closed."""
    if expected is None:
        need(actual is None, f"{field} must be null")
    elif isinstance(expected, bool):
        need(type(actual) is bool and actual is expected, f"{field} boolean differs")
    elif isinstance(expected, dict):
        need(isinstance(actual, dict) and set(expected) <= set(actual), f"{field} required fields missing")
        if closed:
            need(set(actual) == set(expected), f"{field} keys differ")
        for key, value in expected.items():
            match(actual[key], value, field+"."+key, closed)
    elif isinstance(expected, list):
        need(isinstance(actual, list) and len(actual) == len(expected), f"{field} array differs")
        for index, value in enumerate(expected):
            match(actual[index], value, f"{field}[{index}]", closed)
    elif isinstance(expected, int):
        need(type(actual) in (int, float), f"{field} integer type differs")
        parsed = Decimal(str(actual))
        need(parsed.is_finite() and parsed == Decimal(expected), f"{field} integer differs")
    elif isinstance(expected, float):
        need(type(actual) in (int, float), f"{field} numeric type differs")
        close(actual, expected, 0 if closed or field.rsplit(".", 1)[-1] == "sfreq_hz" else 1e-9, field=field)
    else:
        need(type(actual) is str and actual == expected, f"{field} differs")


def table(path, required, keys):
    with Path(path).open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        headers = reader.fieldnames or []
        need(len(headers) == len(set(headers)), "duplicate CSV header")
        need(set(required) <= set(headers), f"{Path(path).name}: required columns missing")
        out = {}
        for row in reader:
            need(None not in row and all(v is not None for v in row.values()), "malformed CSV row")
            key = tuple(integer(row[name]) for name in keys)
            need(key not in out, f"{Path(path).name}: duplicate scientific key")
            out[key] = row
    need(bool(out), f"{Path(path).name}: empty CSV")
    return out


def compare_csv_value(actual, expected, field):
    if expected is None:
        need(actual == "", f"{field} must be empty")
    elif isinstance(expected, bool):
        need(flag(actual) is expected, f"{field} flag differs")
    elif isinstance(expected, int):
        need(integer(actual) == expected, f"{field} source integer differs")
    elif isinstance(expected, float):
        close(actual, expected, 1e-9, field=field)
    else:
        need(actual == expected, f"{field} source string differs")


def confusion_metrics(matrix):
    arr = np.asarray(matrix)
    need(arr.shape == (5, 5) and arr.dtype.kind in "iu" and np.all(arr >= 0), "integer 5x5 confusion required")
    cells = [[int(x) for x in row] for row in arr]
    support = [sum(row) for row in cells]
    predicted = [sum(cells[a][b] for a in range(5)) for b in range(5)]
    n = sum(support)
    need(n > 0, "no epochs")
    correct = sum(cells[k][k] for k in range(5))
    recall = [cells[k][k]/support[k] if support[k] else None for k in range(5)]
    n_supported = sum(x > 0 for x in support)
    expectation = sum(a*b for a, b in zip(support, predicted))
    denominator = n*n-expectation
    return {"n": n, "overall": correct/n,
            "balanced": math.fsum(r for r in recall if r is not None)/n_supported,
            "kappa": (n*correct-expectation)/denominator if denominator else None,
            "kappa_status": "defined" if denominator else "undefined_degenerate_marginals",
            "n_supported": n_supported,
            "per_class": [{"stage_id": k+1, "n_true": support[k], "n_predicted": predicted[k],
                           "n_correct": cells[k][k], "recall": recall[k],
                           "recall_status": "defined" if support[k] else "undefined_no_true_epochs"}
                          for k in range(5)]}


def own_predictions(probabilities):
    p = np.asarray(probabilities, dtype=float)
    need(p.ndim == 2 and p.shape[1] == 5 and np.isfinite(p).all(), "finite five probabilities required")
    need(np.all((p >= 0) & (p <= 1)), "probability domain")
    need(np.all(np.abs(p.sum(axis=1)-1) <= 5.5e-9), "probability simplex")
    return np.argmax(p, axis=1)+1


def matrices(keys, truth, predicted):
    out = {s: np.zeros((5, 5), dtype=np.int64) for s in range(6)}
    for key, target, pred in zip(keys, truth, predicted):
        s = integer(key[0]); target = integer(target); pred = integer(pred)
        need(s in out and 1 <= target <= 5 and 1 <= pred <= 5, "invalid epoch class/subject")
        out[s][target-1, pred-1] += 1
    need(all(x.sum() > 0 for x in out.values()), "all six subjects required")
    return out


def results_from_matrices(mats):
    m = confusion_metrics(sum(mats.values()))
    return {"status": "ok", "task_id": "AASMSTAGE-001", "pipeline_id": PIPELINE,
            "cv_scheme": "leave-one-subject-out", "n_subjects": 6, "n_stages": 5,
            "stages": list(CLASSES), "n_epochs_total": m["n"], "n_supported_classes": m["n_supported"],
            "accuracy": m["balanced"], "balanced_accuracy": m["balanced"],
            "overall_accuracy_for_reference": m["overall"], "cohen_kappa": m["kappa"],
            "kappa_status": m["kappa_status"], "per_class": m["per_class"]}


def compare_metric(actual, expected, field, json_value=False, is_kappa=False):
    if expected is None:
        need(actual is None if json_value else actual == "", f"{field} undefined value required")
        return
    if json_value:
        need(type(actual) in (int, float), f"{field} numeric JSON required")
    val = number(actual)
    need((-1 if is_kappa else 0) <= val <= 1, f"{field} metric domain")
    close(val, expected, field=field)


def validate_results(actual, expected):
    need(set(expected) <= set(actual), "results fields missing")
    for key, value in expected.items():
        if key in ("accuracy", "balanced_accuracy", "overall_accuracy_for_reference", "cohen_kappa"):
            compare_metric(actual[key], value, key, True, key == "cohen_kappa")
        elif key != "per_class":
            match(actual[key], value, key)
    records = actual["per_class"]
    need(isinstance(records, list) and len(records) == 5, "five class metric records required")
    indexed = {}
    for row in records:
        need(isinstance(row, dict) and "stage_id" in row and type(row["stage_id"]) in (int, float), "class ID required")
        key = integer(row["stage_id"])
        need(key not in indexed, "duplicate class metric")
        indexed[key] = row
    need(set(indexed) == set(range(1, 6)), "class coverage")
    for row in expected["per_class"]:
        a = indexed[row["stage_id"]]
        need(set(row) <= set(a), "class metric fields missing")
        for key, value in row.items():
            if key == "recall":
                compare_metric(a[key], value, "class recall", True)
            else:
                match(a[key], value, "class "+key)
