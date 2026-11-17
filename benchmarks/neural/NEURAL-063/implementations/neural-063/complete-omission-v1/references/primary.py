"""Compensated float64 weighted-ridge primary algorithm (never run at import)."""
from __future__ import annotations
import math
from owner.io import ContractError
from owner.scoring import hierarchy
from .schema import finite_number, object_hash
from .features import transform


def fit(rows, state, target_sd, lam):
    import numpy as np
    sd = finite_number(target_sd)
    if sd <= 0 or lam not in (0.0001, 0.001, 0.01, 0.1, 1.0, 10.0, 100.0):
        raise ContractError("frozen positive scale/lambda required")
    if any(r["split"] != "fit" for r in rows):
        raise ContractError("FIT-only regression")
    weights, _ = hierarchy(rows, 73)
    if state["fit_ids_sha256"] != object_hash([r["id"] for r in rows]):
        raise ContractError("feature state belongs to another FIT row set")
    if state["weights_sha256"] != object_hash([[r["id"], weights[r["id"]]] for r in rows]):
        raise ContractError("feature state hierarchy weights differ")
    d = state["layout"]["nonintercept_dimension"]
    active = [j for j, constant in enumerate(state["constant"]) if not constant]
    k = len(active)
    weight_sum = math.fsum(weights.values())
    # Means determine the unpenalized intercept even when floating centering
    # leaves a tiny residual mean in the standardized design.
    xm = np.zeros(k, dtype=np.float64); xc = np.zeros(k, dtype=np.float64)
    ym = np.zeros(3, dtype=np.float64); yc = np.zeros(3, dtype=np.float64)
    def accumulate(total, correction, addition):
        delta = addition - correction
        updated = total + delta
        correction[:] = (updated - total) - delta
        total[:] = updated
    for row in rows:
        x = np.asarray(transform(row, state), dtype=np.float64)[active]
        y = np.asarray(row["target"], dtype=np.float64) / sd
        if not np.isfinite(y).all(): raise ContractError("normalized FIT target overflow")
        w = weights[row["id"]]
        accumulate(xm, xc, w * x); accumulate(ym, yc, w * y)
    xm /= weight_sum; ym /= weight_sum
    gram = np.zeros((k, k), dtype=np.float64); gc = np.zeros_like(gram)
    cross = np.zeros((k, 3), dtype=np.float64); cc = np.zeros_like(cross)
    for row in rows:
        x = np.asarray(transform(row, state), dtype=np.float64)[active] - xm
        y = np.asarray(row["target"], dtype=np.float64) / sd - ym
        w = weights[row["id"]]
        accumulate(gram, gc, w * np.outer(x, x))
        accumulate(cross, cc, w * np.outer(x, y))
    if not np.isfinite(gram).all() or not np.isfinite(cross).all():
        raise ContractError("nonfinite normal equations")
    if k:
        system = gram + np.eye(k, dtype=np.float64) * lam
        chol = np.linalg.cholesky(system)
        beta = np.linalg.solve(chol.T, np.linalg.solve(chol, cross))
        residual = system @ beta - cross
        common_scale = max(float(np.max(np.abs(cross))), float(np.max(np.abs(residual))))
        if common_scale == 0:
            relative_residual = 0.0
        else:
            numerator = math.sqrt(math.fsum((float(v) / common_scale) ** 2 for v in residual.flat))
            denominator = math.sqrt(math.fsum((float(v) / common_scale) ** 2 for v in cross.flat))
            relative_residual = numerator / denominator if denominator else math.inf
        if not np.isfinite(beta).all() or not math.isfinite(relative_residual) or relative_residual > 1e-10:
            raise ContractError("ridge normal-equation residual failed")
        intercept = ym - xm @ beta
    else:
        beta = np.empty((0, 3), dtype=np.float64)
        intercept = ym
        relative_residual = 0.0
    if not np.isfinite(intercept).all(): raise ContractError("nonfinite output intercept")
    full = np.zeros((d, 3), dtype=np.float64)
    if k: full[active, :] = beta
    return {"schema": "neural063_primary_ridge_v1", "implementation": "compensated_cholesky",
            "view": state["layout"]["view"], "basis": state["layout"]["basis"], "lambda": lam,
            "target_sd": sd, "feature_state": state, "coefficients": full.tolist(),
            "intercept": intercept.tolist(), "fit_ids_sha256": state["fit_ids_sha256"],
            "weights_sha256": state["weights_sha256"], "relative_normal_equation_residual": relative_residual,
            "fit_rows": len(rows), "fit_mice": 73, "outputs": 3, "active_columns": k}


def predict(rows, model, *, normalized=False):
    if model.get("schema") != "neural063_primary_ridge_v1": raise ContractError("wrong primary model")
    state = model["feature_state"]
    coeff = model["coefficients"]
    if len(coeff) != state["layout"]["nonintercept_dimension"] or any(len(x) != 3 for x in coeff):
        raise ContractError("coefficient shape differs from feature state")
    result = []
    for row in rows:
        x = transform(row, state)
        values = [math.fsum([model["intercept"][j]] + [x[i] * coeff[i][j] for i in range(len(x))]) for j in range(3)]
        if not normalized: values = [v * model["target_sd"] for v in values]
        if any(not math.isfinite(v) for v in values): raise ContractError("nonfinite complete reference prediction")
        result.append({"id": row["id"], "values": values})
    return result
