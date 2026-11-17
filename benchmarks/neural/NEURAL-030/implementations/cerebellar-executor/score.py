"""Strict count scorer; all labels and biological bindings are operator-private.

This original implementation scores declared arrays; it does not authenticate
source data, establish a biological identity join, or sandbox participant code.
"""
import re
import numpy as np

POISSON_EPSILON = 1e-12


def _id(value, name):
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ValueError(f"{name} must be a nonempty opaque string")
    return value


def _vector(value, length, name, *, integer=False):
    if isinstance(value, (list, tuple)) and any(isinstance(v, (bool, np.bool_)) for v in value):
        raise ValueError(f"{name} cannot contain booleans")
    raw = np.asarray(value)
    if raw.dtype.kind not in "iuf" or raw.shape != (length,):
        raise ValueError(f"{name} must be a numeric vector of length {length}")
    result = raw.astype(np.float64, copy=True)
    if not np.isfinite(result).all() or (result < 0).any():
        raise ValueError(f"{name} must contain finite nonnegative values")
    if integer and ((result > 2**53 - 1).any() or (result != np.floor(result)).any()):
        raise ValueError(f"{name} must contain exact integer counts")
    return result


def _expected_rows(expected):
    if not isinstance(expected, (list, tuple)) or not expected:
        raise ValueError("expected must be a nonempty frozen sequence")
    result = {}
    for row in expected:
        if not isinstance(row, dict) or set(row) != {"trial_id", "session_id", "bin_count", "counts"}:
            raise ValueError("unexpected expected-record schema")
        trial = _id(row["trial_id"], "trial_id")
        session = _id(row["session_id"], "session_id")
        size = row["bin_count"]
        if isinstance(size, (bool, np.bool_)) or not isinstance(size, (int, np.integer)) or size <= 0:
            raise ValueError("bin_count must be a positive integer")
        if trial in result:
            raise ValueError("duplicate expected trial_id")
        result[trial] = (session, _vector(row["counts"], size, "expected counts", integer=True))
    return result


def _prediction_rows(predictions, expected, name):
    if not isinstance(predictions, (list, tuple)):
        raise ValueError(f"{name} must be a sequence")
    result = {}
    for row in predictions:
        if not isinstance(row, dict) or set(row) != {"trial_id", "counts"}:
            raise ValueError(f"unexpected {name} record schema")
        trial = _id(row["trial_id"], "trial_id")
        if trial in result or trial not in expected:
            raise ValueError(f"duplicate or unlisted {name} trial_id")
        result[trial] = _vector(row["counts"], len(expected[trial][1]), name)
    if set(result) != set(expected):
        raise ValueError(f"missing {name} trial_id")
    return result


def _metrics(y, prediction):
    # The floor applies to the entire Poisson mean, including the +mu term.
    # Consequently y=0, prediction=0 has deviance 2*epsilon, not exactly zero.
    mu = np.maximum(prediction, POISSON_EPSILON)
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            mse = float(np.mean((y - prediction) ** 2))
            terms = mu - y
            positive = y > 0
            terms[positive] += y[positive] * (np.log(y[positive]) - np.log(mu[positive]))
            deviance = float(np.mean(np.maximum(0.0, 2 * terms)))
    except FloatingPointError as exc:
        raise ValueError("score arithmetic is not finite") from exc
    if not np.isfinite([mse, deviance]).all():
        raise ValueError("score arithmetic is not finite")
    return {"mse": mse, "poisson_deviance": deviance}


def _mean_metrics(records, keys):
    try:
        with np.errstate(over="raise", invalid="raise"):
            result = {key: float(np.sum(np.asarray([row[key] for row in records]) / len(records))) for key in keys}
    except FloatingPointError as exc:
        raise ValueError("aggregation arithmetic is not finite") from exc
    if not np.isfinite(list(result.values())).all():
        raise ValueError("aggregation arithmetic is not finite")
    return result


def _binding(binding, sessions):
    required = {"verification_status", "binding_id", "evidence_sha256", "session_to_mouse"}
    if not isinstance(binding, dict) or set(binding) != required:
        raise ValueError("unexpected mouse binding schema")
    if binding["verification_status"] != "operator_attested":
        raise ValueError("mouse binding must be explicitly operator-attested")
    _id(binding["binding_id"], "binding_id")
    if not isinstance(binding["evidence_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", binding["evidence_sha256"]):
        raise ValueError("binding requires a lowercase SHA-256 evidence pin")
    mapping = binding["session_to_mouse"]
    if not isinstance(mapping, dict) or set(mapping) != set(sessions):
        raise ValueError("mouse binding must cover exactly the scored sessions")
    for session, mouse in mapping.items():
        _id(session, "binding session")
        _id(mouse, "mouse_id")
    return mapping


def score_predictions(expected, predictions, *, baseline_predictions=None, mouse_binding=None):
    """Score every frozen trial/bin and optionally a paired fixed comparator.

    expected: sequence of {trial_id,session_id,bin_count,counts}, private labels.
    predictions and optional baseline: {trial_id,counts}, complete unique IDs.
    Positive *_gain means baseline loss minus candidate loss. Sessions average
    complete-trial means equally. Optional mouse means average sessions equally,
    then macro averages mice equally. No trial/animal independence is asserted.
    A declared evidence pin enables computation, not identity authentication.
    """
    rows = _expected_rows(expected)
    pred = _prediction_rows(predictions, rows, "predictions")
    baseline = None if baseline_predictions is None else _prediction_rows(baseline_predictions, rows, "baseline predictions")
    trial_results = []
    for trial, (session, y) in rows.items():
        metrics = _metrics(y, pred[trial])
        if baseline is not None:
            base_metrics = _metrics(y, baseline[trial])
            metrics.update({f"baseline_{key}": value for key, value in base_metrics.items()})
            metrics.update({f"{key}_gain": value - metrics[key] for key, value in base_metrics.items()})
        trial_results.append({"trial_id": trial, "session_id": session, "bin_count": len(y), **metrics})
    metric_keys = ["mse", "poisson_deviance"]
    if baseline is not None:
        metric_keys += ["baseline_mse", "baseline_poisson_deviance", "mse_gain", "poisson_deviance_gain"]
    session_results = []
    for session in sorted({row["session_id"] for row in trial_results}):
        selected = [row for row in trial_results if row["session_id"] == session]
        session_results.append({"session_id": session, "trial_count": len(selected),
                                "bin_count": sum(row["bin_count"] for row in selected),
                                **_mean_metrics(selected, metric_keys)})
    result = {
        "metrics": {"primary": "mse_gain" if baseline is not None else "mse",
                    "secondary": "poisson_deviance_gain" if baseline is not None else "poisson_deviance",
                    "poisson_mean_floor": POISSON_EPSILON,
                    "aggregation": "equal trials/session; equal sessions/mouse; equal mice",
                    "prediction_regime": "within-session held-out complete trials"},
        "trial_results": trial_results, "session_results": session_results,
        "mouse_results": None, "mouse_macro": None,
        "identity_status": "no operator binding supplied; biological aggregation unavailable",
        "scientific_qualification": False,
    }
    if mouse_binding is not None:
        mapping = _binding(mouse_binding, [row["session_id"] for row in session_results])
        mouse_results = []
        for mouse in sorted(set(mapping.values())):
            selected = [row for row in session_results if mapping[row["session_id"]] == mouse]
            mouse_results.append({"mouse_id": mouse, "session_count": len(selected), **_mean_metrics(selected, metric_keys)})
        result.update(mouse_results=mouse_results, mouse_macro=_mean_metrics(mouse_results, metric_keys),
                      identity_status="operator-attested mapping; authenticity not established by scorer",
                      binding_id=mouse_binding["binding_id"], evidence_sha256=mouse_binding["evidence_sha256"])
    return result
