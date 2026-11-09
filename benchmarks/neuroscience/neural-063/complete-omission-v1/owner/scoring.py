"""Hierarchy-preserving finite/extended-real arithmetic for NEURAL-063.

No I/O, native source access or fitting occurs at import. Scientific entrypoints
are guarded by the owning stage; pure arithmetic is usable on selected invented
engineering cases only under a separate control reservation.
"""
from __future__ import annotations

from collections import defaultdict
import math
from .io import ContractError


def finite(value):
    if type(value) not in (float, int):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def number(value):
    if not finite(value):
        raise ContractError("finite numeric scalar required")
    return float(value)


def typed(value):
    if not math.isfinite(value):
        if value == math.inf:
            return {"value": None, "status": "positive_infinity"}
        raise ContractError("negative/nonfinite absolute score")
    if value < 0:
        raise ContractError("negative absolute score")
    return {"value": value, "status": "finite"}


def unavailable(reason, *, arithmetic_class=None, **details):
    out = {"value": None, "status": "unavailable", "reason": reason, **details}
    if arithmetic_class:
        out["arithmetic_class"] = arithmetic_class
    return out


def validate_absolute(x):
    if not isinstance(x, dict) or x.get("status") not in ("finite", "positive_infinity"):
        raise ContractError("typed absolute score required")
    if x["status"] == "finite":
        v = number(x.get("value"))
        if v < 0:
            raise ContractError("negative absolute score")
        return v
    if x.get("value") is not None:
        raise ContractError("infinity must have null JSON value")
    return math.inf


def stable_mean(values):
    if not values or any(not finite(v) for v in values):
        raise ContractError("nonempty finite mean operands required")
    scale = max(abs(float(v)) for v in values)
    if scale == 0:
        return 0.0
    return math.fsum(float(v) / scale / len(values) for v in values) * scale


def hierarchy(rows, expected_mice):
    """Equal mouse/session/experiment/event weights over supported observations."""
    groups = {}
    identities = set()
    session_parent, experiment_parent = {}, {}
    for row in rows:
        ident = row["id"]
        if not isinstance(ident, str) or not ident or ident in identities:
            raise ContractError("duplicate/invalid event identity")
        identities.add(ident)
        m, s, e = row["mouse"], row["session"], row["experiment"]
        if any(not isinstance(v, str) or not v for v in (m, s, e)):
            raise ContractError("invalid opaque hierarchy token")
        if session_parent.setdefault(s, m) != m or experiment_parent.setdefault(e, (m, s)) != (m, s):
            raise ContractError("hierarchy token has inconsistent parent")
        groups.setdefault(m, {}).setdefault(s, {}).setdefault(e, []).append(ident)
    if len(groups) != expected_mice:
        raise ContractError("complete fixed mouse panel required")
    weights = {}
    for m, sessions in groups.items():
        for s, experiments in sessions.items():
            for e, ids in experiments.items():
                for ident in ids:
                    weights[ident] = 1 / expected_mice / len(sessions) / len(experiments) / len(ids)
    return weights, groups


def target(row):
    y = row.get("target")
    if not isinstance(y, list) or len(y) != 3:
        raise ContractError("three target bins required")
    return [number(v) for v in y]


def training_scale(rows):
    if any(r.get("split") != "fit" for r in rows):
        raise ContractError("FIT-only target scaling required")
    weights, _ = hierarchy(rows, 73)
    yy = [target(r) for r in rows]
    lo, hi = min(min(y) for y in yy), max(max(y) for y in yy)
    if lo == hi:
        raise ContractError("exactly constant FIT support; no epsilon permitted")
    anchor = lo / 2 + hi / 2
    residuals = [[v - anchor for v in y] for y in yy]
    radius = max(abs(v) for y in residuals for v in y)
    if not math.isfinite(radius) or radius <= 0:
        raise ContractError("undefined FIT scale radius")
    z = [[v / radius for v in y] for y in residuals]
    mean = math.fsum(weights[r["id"]] * math.fsum(y) / 3 for r, y in zip(rows, z))
    variance = math.fsum(weights[r["id"]] * math.fsum((v - mean) ** 2 for v in y) / 3
                         for r, y in zip(rows, z))
    sd = radius * math.sqrt(variance)
    if not math.isfinite(sd) or sd <= 0:
        raise ContractError("undefined FIT target SD")
    return sd


def scaled_ratio(a, b, denominator):
    if a == 0 or b == 0:
        return (0.0, 0)
    am, ae = math.frexp(a); bm, be = math.frexp(b); dm, de = math.frexp(denominator)
    m, e = math.frexp(am * bm / dm)
    return m, ae + be - de + e


def materialize(pair):
    try:
        return math.ldexp(*pair)
    except OverflowError:
        return math.inf


def admit_predictions(rows, expected_ids):
    if not isinstance(rows, list) or len(rows) != len(expected_ids):
        raise ContractError("complete prediction list required")
    result = {}
    for row, ident in zip(rows, expected_ids):
        if not isinstance(row, dict) or set(row) != {"id", "values"} or row["id"] != ident:
            raise ContractError("prediction identity/order/fields mismatch")
        if ident in result or not isinstance(row["values"], list) or len(row["values"]) != 3:
            raise ContractError("exactly one three-bin prediction per identity required")
        result[ident] = [number(v) for v in row["values"]]
    return result


def absolute(predictions, rows, sd, expected_mice):
    sd = number(sd)
    if sd <= 0:
        raise ContractError("strictly positive fixed FIT scale required")
    weights, groups = hierarchy(rows, expected_mice)
    if set(predictions) != {r["id"] for r in rows}:
        raise ContractError("no missing or extra prediction allowed")
    by_mouse = defaultdict(list)
    for row in rows:
        p = predictions[row["id"]]
        if not isinstance(p, list) or len(p) != 3:
            raise ContractError("three prediction bins required")
        by_mouse[row["mouse"]].append((row, [number(v) for v in p], target(row)))
    parts, raw_parts, per_bin, bin_parts = {}, {}, {}, {}
    for mouse, records in by_mouse.items():
        differences = [p[k] - y[k] for _, p, y in records for k in range(3)]
        if all(math.isfinite(v) for v in differences):
            scale = max(abs(v) for v in differences)
        else:
            scale = max(abs(v) for _, p, y in records for v in p + y)
        if scale == 0:
            parts[mouse] = raw_parts[mouse] = (0.0, 0)
            per_bin[mouse] = [typed(0.0)] * 3
            bin_parts[mouse] = [(0.0, 0)] * 3
            continue
        sums = [[], [], []]
        for row, p, y in records:
            for k in range(3):
                d = p[k] - y[k]
                z = d / scale if math.isfinite(d) else p[k] / scale - y[k] / scale
                sums[k].append(weights[row["id"]] * expected_mice * z * z)
        sq = [math.fsum(x) for x in sums]
        rms = math.sqrt(math.fsum(sq) / 3)
        parts[mouse] = scaled_ratio(rms, scale, sd)
        raw_parts[mouse] = scaled_ratio(rms, scale, 1.0)
        bin_parts[mouse] = [scaled_ratio(math.sqrt(v), scale, sd) for v in sq]
        per_bin[mouse] = [typed(materialize(v)) for v in bin_parts[mouse]]
    def average_pairs(values):
        exponent = max(e for _, e in values.values())
        m = math.fsum(math.ldexp(a, e - exponent) / expected_mice for a, e in values.values())
        return typed(materialize((m, exponent)))
    return {"primary": average_pairs(parts), "raw_rmse": average_pairs(raw_parts),
            "per_mouse": {m: typed(materialize(parts[m])) for m in sorted(parts)},
            "per_mouse_bin_nrmse": {m: per_bin[m] for m in sorted(parts)},
            "per_bin_nrmse": [average_pairs({m: bin_parts[m][k] for m in bin_parts}) for k in range(3)],
            "mice": expected_mice, "events": len(rows),
            "sessions_supported": sum(len(s) for s in groups.values()),
            "experiments_supported": sum(len(e) for s in groups.values() for e in s.values())}


def difference(a, b):
    aa, bb = validate_absolute(a), validate_absolute(b)
    if not math.isfinite(aa) or not math.isfinite(bb):
        if aa == bb:
            return unavailable("indeterminate_infinity_minus_infinity", arithmetic_class="undefined")
        return unavailable("absolute_positive_infinity_operand",
                           arithmetic_class="positive_infinity" if aa == math.inf else "negative_infinity")
    delta = aa - bb
    if not math.isfinite(delta):
        return unavailable("derived_arithmetic_overflow",
                           arithmetic_class="positive_infinity" if delta > 0 else "negative_infinity")
    return {"value": delta, "status": "finite"}


def paired(a, b, expected_mice):
    if set(a) != set(b) or len(a) != expected_mice:
        raise ContractError("complete paired mouse set required; no finite subset")
    per_mouse = {m: difference(a[m], b[m]) for m in sorted(a)}
    failed = {m: v for m, v in per_mouse.items() if v["status"] != "finite"}
    if failed:
        return {"contrast": unavailable("required_comparison_unavailable", affected_mice=failed),
                "per_mouse": per_mouse}
    value = stable_mean([v["value"] for v in per_mouse.values()])
    contrast = ({"value": value, "status": "finite"} if math.isfinite(value)
                else unavailable("derived_arithmetic_overflow"))
    return {"contrast": contrast, "per_mouse": per_mouse}


def gain(candidate, reference, *, qualified):
    if qualified is not True:
        return unavailable("reference_unqualified")
    c, r = validate_absolute(candidate), validate_absolute(reference)
    if not math.isfinite(c) or not math.isfinite(r):
        return unavailable("absolute_positive_infinity_operand")
    if r == 0:
        return unavailable("undefined_zero_reference", arithmetic_class="undefined")
    ratio = c / r
    value = 1 - ratio
    if not math.isfinite(value):
        return unavailable("derived_arithmetic_overflow", arithmetic_class="negative_infinity")
    return {"value": value, "status": "finite"}


def bootstrap(contrast, *, seed, draws=10000):
    if draws != 10000 or seed not in (63015, 63019):
        raise ContractError("frozen bootstrap draw count/seed required")
    result = {"seed": seed, "planned_resamples": draws, "resamples_executed": 0,
              "draw_indices": None}
    if contrast["contrast"]["status"] != "finite":
        return {**result, "interval": unavailable("required_comparison_unavailable")}
    items = list(contrast["per_mouse"].values())
    if not items or any(x["status"] != "finite" for x in items):
        return {**result, "interval": unavailable("required_comparison_unavailable")}
    # Imported only inside an explicitly invoked numerical operation.
    import numpy as np
    rng = np.random.Generator(np.random.PCG64(seed))
    indices, means = [], []
    for _ in range(draws):
        idx = rng.integers(0, len(items), size=len(items)).tolist()
        indices.append(idx)
        try:
            value = stable_mean([items[i]["value"] for i in idx])
        except (OverflowError, ValueError):
            return {**result, "resamples_executed": len(indices), "draw_indices": indices,
                    "interval": unavailable("derived_arithmetic_overflow", operation="resample_mean")}
        if not math.isfinite(value):
            return {**result, "resamples_executed": len(indices), "draw_indices": indices,
                    "interval": unavailable("derived_arithmetic_overflow", operation="resample_mean")}
        means.append(value)
    means.sort()
    endpoints = []
    for q in (0.025, 0.975):
        z = (draws - 1) * q
        low, high = math.floor(z), math.ceil(z)
        fraction = z - low
        # Convex interpolation avoids overflowing high-low for opposite signs.
        try:
            value = math.fsum([(1 - fraction) * means[low], fraction * means[high]])
        except (OverflowError, ValueError):
            return {**result, "resamples_executed": draws, "draw_indices": indices,
                    "interval": unavailable("derived_arithmetic_overflow", operation="percentile_endpoint")}
        if not math.isfinite(value):
            return {**result, "resamples_executed": draws, "draw_indices": indices,
                    "interval": unavailable("derived_arithmetic_overflow", operation="percentile_endpoint")}
        endpoints.append(value)
    return {**result, "resamples_executed": draws, "draw_indices": indices,
            "interval": {"status": "finite", "lower": endpoints[0], "upper": endpoints[1]}}
