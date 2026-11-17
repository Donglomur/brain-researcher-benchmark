"""Independent feature/statistic/SVD reconstruction.

This file never imports primary.py, features.py or their fitter/transform code.
The shared schema constants describe the estimand, not the numerical algorithm.
"""
from __future__ import annotations
import json
import math
from collections import Counter, defaultdict
from owner.io import ContractError, canonical
import hashlib
from .schema import CATEGORIES


def _hash(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _levels(row):
    c = row["context"]
    tuples = [(c[name],) for name in CATEGORIES[:6]]
    tuples += [(item["image"], item["omitted"]) for item in row["previous"]]
    return [json.dumps(list(x), ensure_ascii=False, separators=(",", ":"), allow_nan=False) for x in tuples]


def describe(rows, view, basis):
    if view not in ("T", "N") or basis not in ("L", "Q"):
        raise ContractError("unknown independent feature family")
    vocabulary = [set() for _ in range(9)]
    for row in rows:
        if row["split"] != "fit": raise ContractError("independent dictionaries are FIT only")
        for i, value in enumerate(_levels(row)): vocabulary[i].add(value)
    levels = [sorted(x, key=lambda s: s.encode("utf-8")) for x in vocabulary]
    q = 4 if view == "T" else 15
    widths = [len(x) + 1 for x in levels]
    labels = []
    for i in range(q): labels.append(["n", i])
    for a in range(9):
        for b in range(widths[a]): labels.append(["c", a, b])
    if basis == "Q":
        for a in range(q):
            for b in range(a, q): labels.append(["nn", a, b])
        for i in range(q):
            for a in range(9):
                for b in range(widths[a]): labels.append(["nc", i, a, b])
        for a in range(9):
            for c in range(a + 1, 9):
                for b in range(widths[a]):
                    for d in range(widths[c]): labels.append(["cc", a, b, c, d])
    return {"schema": "neural063_feature_layout_v1", "view": view, "basis": basis,
            "categories": list(CATEGORIES), "levels": levels, "unknown_indices": [len(x) for x in levels],
            "numeric_count": q, "terms": labels, "nonintercept_dimension": len(labels),
            "intercept_separate_unpenalized": True}


def _vector(row, descriptor):
    previous = row["previous"]
    starts = [float(item["start_relative_seconds"]) for item in previous]
    numeric = [starts[1] - starts[0], starts[2] - starts[1], -starts[2], float(row["context"]["imaging_depth"])]
    if descriptor["view"] == "N": numeric += [float(row["history"][i]) for i in range(11)]
    tokens = _levels(row)
    bits = [[float(value == token) for value in levels] + [float(token not in levels)]
            for token, levels in zip(tokens, descriptor["levels"])]
    values = list(numeric)
    for column in bits: values.extend(column)
    if descriptor["basis"] == "Q":
        for i, a in enumerate(numeric):
            values.extend(a * numeric[j] for j in range(i, len(numeric)))
        for a in numeric:
            for one_hot in bits: values.extend(a * b for b in one_hot)
        for a in range(len(bits)):
            for c in range(a + 1, len(bits)):
                for b in bits[a]: values.extend(b * d for d in bits[c])
    if len(values) != descriptor["nonintercept_dimension"] or not all(math.isfinite(v) for v in values):
        raise ContractError("independent feature construction failed")
    return values


def _weights(rows):
    sessions = defaultdict(set); experiments = defaultdict(set); counts = Counter()
    for row in rows:
        m, s, e = row["mouse"], row["session"], row["experiment"]
        sessions[m].add(s); experiments[(m, s)].add(e); counts[(m, s, e)] += 1
    if len(sessions) != 73: raise ContractError("independent full FIT panel required")
    return [1 / 73 / len(sessions[r["mouse"]]) / len(experiments[(r["mouse"], r["session"])]) / counts[(r["mouse"], r["session"], r["experiment"])] for r in rows]


def fit(rows, view, basis, target_sd, lam):
    import numpy as np
    if any(r["split"] != "fit" for r in rows): raise ContractError("independent fit is FIT only")
    if not math.isfinite(target_sd) or target_sd <= 0 or lam not in (0.0001, 0.001, 0.01, 0.1, 1., 10., 100.):
        raise ContractError("frozen scale/lambda required")
    descriptor = describe(rows, view, basis)
    raw = np.array([_vector(row, descriptor) for row in rows], dtype=np.float64)
    weights = np.asarray(_weights(rows), dtype=np.float64)
    weight_sum = math.fsum(weights.tolist())
    low, high = raw.min(axis=0), raw.max(axis=0)
    anchor = low / 2 + high / 2
    radius = np.maximum(np.abs(low - anchor), np.abs(high - anchor))
    constant = radius == 0
    safe_radius = radius.copy(); safe_radius[constant] = 1.0
    z = (raw - anchor) / safe_radius
    mean_z = np.array([math.fsum((weights * z[:, j]).tolist()) / weight_sum for j in range(raw.shape[1])])
    var_z = np.array([math.fsum((weights * ((z[:, j] - mean_z[j]) ** 2)).tolist()) / weight_sum for j in range(raw.shape[1])])
    sd_z = np.sqrt(var_z)
    if np.any((~constant) & ((sd_z <= 0) | (~np.isfinite(sd_z)))):
        raise ContractError("independent scale undefined")
    safe_zsd = sd_z.copy(); safe_zsd[constant] = 1.0
    x = (z - mean_z) / safe_zsd; x[:, constant] = 0.0
    sd = radius * sd_z
    if not np.isfinite(x).all() or not np.isfinite(sd).all() or np.any((~constant) & (sd == 0)):
        raise ContractError("independent standardization overflow/underflow")
    active = np.flatnonzero(~constant)
    design = x[:, active]
    response = np.asarray([r["target"] for r in rows], dtype=np.float64) / target_sd
    if not np.isfinite(response).all(): raise ContractError("independent normalized response overflow")
    xbar = np.array([math.fsum((weights * design[:, j]).tolist()) / weight_sum for j in range(design.shape[1])])
    ybar = np.array([math.fsum((weights * response[:, j]).tolist()) / weight_sum for j in range(3)])
    weighted_x = (design - xbar) * np.sqrt(weights)[:, None]
    weighted_y = (response - ybar) * np.sqrt(weights)[:, None]
    if len(active):
        u, singular, vt = np.linalg.svd(weighted_x, full_matrices=False)
        shrink = singular / (singular * singular + lam)
        beta = (vt.T * shrink) @ (u.T @ weighted_y)
        intercept = ybar - xbar @ beta
    else:
        beta = np.empty((0, 3), dtype=np.float64); intercept = ybar
    full = np.zeros((raw.shape[1], 3), dtype=np.float64); full[active] = beta
    if not np.isfinite(full).all() or not np.isfinite(intercept).all():
        raise ContractError("independent nonfinite coefficients")
    state = {"schema": "neural063_independent_feature_state_v1", "layout": descriptor,
             "layout_sha256": _hash(descriptor), "anchors": anchor.tolist(), "radii": radius.tolist(),
             "mean_z": mean_z.tolist(), "sd_z": sd_z.tolist(), "constant": constant.tolist(),
             "fit_ids_sha256": _hash([r["id"] for r in rows]),
             "weights_sha256": _hash([[r["id"], w] for r, w in zip(rows, weights.tolist())])}
    return {"schema": "neural063_independent_svd_v1", "implementation": "independent_weighted_design_svd",
            "view": view, "basis": basis, "lambda": lam, "target_sd": target_sd,
            "feature_state": state, "coefficients": full.tolist(), "intercept": intercept.tolist(),
            "fit_rows": len(rows), "fit_mice": 73, "outputs": 3, "active_columns": len(active)}


def predict(rows, model, *, normalized=False):
    if model.get("schema") != "neural063_independent_svd_v1": raise ContractError("wrong independent model")
    state = model["feature_state"]; result = []
    for row in rows:
        raw = _vector(row, state["layout"]); standardized = []
        for j, value in enumerate(raw):
            if state["constant"][j]: standardized.append(0.0); continue
            residual = value - state["anchors"][j]
            z = residual / state["radii"][j] if math.isfinite(residual) else value / state["radii"][j] - state["anchors"][j] / state["radii"][j]
            standardized.append((z - state["mean_z"][j]) / state["sd_z"][j])
        values = [math.fsum([model["intercept"][k]] + [a * b[k] for a, b in zip(standardized, model["coefficients"])]) for k in range(3)]
        if not normalized: values = [x * model["target_sd"] for x in values]
        if not all(math.isfinite(v) for v in values): raise ContractError("independent prediction nonfinite")
        result.append({"id": row["id"], "values": values})
    return result
