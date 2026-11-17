"""Continuous empirical-core reconstruction metrics; no model fitting or thresholds.

The exponent diagnostic reproduces the author's weighted algebra, not a new
model-selection exercise. DMD assignment is invariant to complex mode ordering.
"""
import math
from collections import defaultdict


def error(a, b):
    if len(a) != len(b) or not a:
        raise ValueError("Exact nonempty metric support")
    residuals = [abs(x - y) for x, y in zip(a, b)]
    if not all(math.isfinite(x) for x in residuals):
        raise ValueError("Residual overflow")
    return {"mean_absolute_error": math.fsum(residuals) / len(residuals),
            "max_absolute_error": max(residuals), "count": len(residuals)}


def flatten(rows):
    return [x for row in rows for x in row]


def exponent(spectrum):
    # Literal weighted regression: y=log(abs(value)), x=-log(rank), w=1/rank.
    if any(x == 0 for x in spectrum[10:500]):
        return {"status": "undefined_zero_in_fit_window", "value": None}
    points = [(1.0 / k, -math.log(k), math.log(abs(spectrum[k - 1]))) for k in range(11, 501)]
    sw = math.fsum(w for w, _, _ in points)
    sx = math.fsum(w * x for w, x, _ in points)
    sy = math.fsum(w * y for w, _, y in points)
    sxx = math.fsum(w * x * x for w, x, _ in points)
    sxy = math.fsum(w * x * y for w, x, y in points)
    value = (sw * sxy - sx * sy) / (sw * sxx - sx * sx)
    if not math.isfinite(value):
        raise ValueError("Exponent diagnostic overflow")
    return {"status": "defined", "value": value}


def quantile(values, p):
    s = sorted(values)
    z = (len(s) - 1) * p
    i = int(z)
    return s[i] + (z - i) * (s[min(i + 1, len(s) - 1)] - s[i])


def rotations(pairs):
    # Literal Fig3 convention: |e|>.25, imaginary>=0, without |e|<1 filter.
    values, singular, unstable = [], 0, 0
    for real, imag in pairs:
        magnitude = math.hypot(real, imag)
        if not math.isfinite(magnitude):
            raise ValueError("Complex magnitude overflow")
        if magnitude <= .25 or imag < 0:
            continue
        if magnitude == 1:
            singular += 1
            continue
        unstable += magnitude > 1
        value = (math.atan2(imag, real) / (2 * math.pi)) / -math.log10(magnitude)
        if not math.isfinite(value):
            raise ValueError("Rotation diagnostic overflow")
        values.append(value)
    return {"finite_count": len(values), "unit_magnitude_undefined_count": singular,
            "unstable_retained_count": unstable,
            "mean": math.fsum(values) / len(values) if values else None,
            "quantiles_5_25_50_75_95": [quantile(values, p) for p in (.05, .25, .5, .75, .95)] if values else None}


def complex_assignment(a, b):
    # Lazy dependencies; never invoked by packaging/import. Preserves multiplicity.
    import numpy as np
    from scipy.optimize import linear_sum_assignment
    x, y = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    distances = np.hypot(x[:, None, 0] - y[None, :, 0], x[:, None, 1] - y[None, :, 1])
    if not np.isfinite(distances).all():
        raise ValueError("DMD distance overflow")
    rows, cols = linear_sum_assignment(distances)
    ds = distances[rows, cols].tolist()
    return {"mean_absolute_error": math.fsum(ds) / len(ds), "max_absolute_error": max(ds), "count": len(ds)}


def compare(candidate, reference, sessions, match=complex_assignment):
    records, primary, strata = [], [], defaultdict(list)
    for a, b, session in zip(candidate["records"], reference["records"], sessions):
        fields = {k: error(a[k], b[k]) for k in ("covariance", "svca2", "svca", "svca_variance")}
        fields["pc_acg"] = error(flatten(a["pc_acg"]), flatten(b["pc_acg"]))
        fields["dmd"] = match(a["dmd"], b["dmd"])
        sa, sb = math.fsum(a["svca2"]), math.fsum(b["svca2"])
        shape = error([x / sa for x in a["svca2"]], [x / sb for x in b["svca2"]])
        primary.append(shape["mean_absolute_error"])
        strata[session["region"]].append(primary[-1])
        exponents = {}
        for k in ("covariance", "svca2", "svca"):
            x, y = exponent(a[k]), exponent(b[k])
            exponents[k] = {"candidate": x, "reference": y,
                            "absolute_error": abs(x["value"] - y["value"]) if x["value"] is not None and y["value"] is not None else None}
        records.append({"session_id": session["session_id"], "raw_field_errors": fields,
                        "svca2_shape_error": shape, "exponents": exponents,
                        "candidate_rotation": rotations(a["dmd"]), "reference_rotation": rotations(b["dmd"])})
    return {"schema": "critical_init_score_v1", "primary_equal_session_svca2_shape_mae": math.fsum(primary) / len(primary),
            "direction": "lower", "sessions": len(primary),
            "region_mean_shape_errors": {k: math.fsum(v) / len(v) for k, v in sorted(strata.items())},
            "records": records, "binary_scientific_pass": None,
            "interpretation": "Source-anchored empirical-core numerical reconstruction only; session average is not an independent-animal significance test.",
            "runtime_verified": False, "research_qualified": False}
