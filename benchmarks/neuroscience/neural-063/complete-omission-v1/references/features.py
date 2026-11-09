"""Primary exact L/Q feature construction and FIT-only standardization."""
from __future__ import annotations
import itertools
import math
from owner.io import ContractError
from owner.scoring import hierarchy
from .schema import CATEGORIES, row_numeric, row_categories, object_hash, finite_number


def layout(rows, view, basis):
    if view not in ("T", "N") or basis not in ("L", "Q") or any(r["split"] != "fit" for r in rows):
        raise ContractError("fixed FIT feature family required")
    levels = [sorted({row_categories(r)[j] for r in rows}, key=lambda x: x.encode("utf-8")) for j in range(9)]
    q = 4 if view == "T" else 15
    widths = [len(x) + 1 for x in levels]  # final level is explicit unknown
    terms = [["n", i] for i in range(q)]
    terms += [["c", a, b] for a, width in enumerate(widths) for b in range(width)]
    if basis == "Q":
        terms += [["nn", i, j] for i in range(q) for j in range(i, q)]
        terms += [["nc", i, a, b] for i in range(q) for a, width in enumerate(widths) for b in range(width)]
        terms += [["cc", a, b, c, d] for a in range(9) for c in range(a + 1, 9) for b in range(widths[a]) for d in range(widths[c])]
    return {"schema": "neural063_feature_layout_v1", "view": view, "basis": basis,
            "categories": list(CATEGORIES), "levels": levels, "unknown_indices": [len(x) for x in levels],
            "numeric_count": q, "terms": terms, "nonintercept_dimension": len(terms),
            "intercept_separate_unpenalized": True}


def raw_vector(row, spec):
    nums = row_numeric(row, spec["view"])
    cats = row_categories(row)
    positions = []
    for value, levels in zip(cats, spec["levels"]):
        try: positions.append(levels.index(value))
        except ValueError: positions.append(len(levels))
    result = []
    for term in spec["terms"]:
        kind, *idx = term
        if kind == "n": x = nums[idx[0]]
        elif kind == "c": x = float(positions[idx[0]] == idx[1])
        elif kind == "nn": x = nums[idx[0]] * nums[idx[1]]
        elif kind == "nc": x = nums[idx[0]] * (positions[idx[1]] == idx[2])
        elif kind == "cc": x = float(positions[idx[0]] == idx[1] and positions[idx[2]] == idx[3])
        else: raise ContractError("unknown constructed feature")
        if not math.isfinite(x): raise ContractError("nonfinite constructed feature; no clipping")
        result.append(x)
    return result


def fit_statistics(rows, spec):
    weights, _ = hierarchy(rows, 73)
    d = spec["nonintercept_dimension"]
    lo, hi = [math.inf] * d, [-math.inf] * d
    for row in rows:
        for j, x in enumerate(raw_vector(row, spec)):
            lo[j], hi[j] = min(lo[j], x), max(hi[j], x)
    anchors = [a / 2 + b / 2 for a, b in zip(lo, hi)]
    radii = [max(abs(a - c), abs(b - c)) for a, b, c in zip(lo, hi, anchors)]
    weight_sum = math.fsum(weights.values())
    sums, corrections = [0.0] * d, [0.0] * d
    def add(total, correction, j, value):
        adjusted = value - correction[j]
        updated = total[j] + adjusted
        correction[j] = (updated - total[j]) - adjusted
        total[j] = updated
    for row in rows:
        vector = raw_vector(row, spec)
        for j, value in enumerate(vector):
            if radii[j]:
                add(sums, corrections, j, weights[row["id"]] * (value - anchors[j]) / radii[j])
    means_z = [x / weight_sum for x in sums]
    variances, corrections = [0.0] * d, [0.0] * d
    for row in rows:
        vector = raw_vector(row, spec)
        for j, value in enumerate(vector):
            if radii[j]:
                residual = (value - anchors[j]) / radii[j] - means_z[j]
                add(variances, corrections, j, weights[row["id"]] * residual * residual)
    sd_z = [math.sqrt(x / weight_sum) for x in variances]
    if any(radii[j] and (not math.isfinite(sd_z[j]) or sd_z[j] <= 0) for j in range(d)):
        raise ContractError("undefined nonconstant FIT feature scale")
    means = [a + radius * mu for a, radius, mu in zip(anchors, radii, means_z)]
    sds = [radius * zsd for radius, zsd in zip(radii, sd_z)]
    if any(not math.isfinite(v) for v in means + sds):
        raise ContractError("nonrepresentable feature statistic")
    if any(radius != 0 and sd == 0 for radius, sd in zip(radii, sds)):
        raise ContractError("feature scale underflow is not a constant column")
    return {"schema": "neural063_feature_state_v1", "layout": spec, "layout_sha256": object_hash(spec),
            "anchors": anchors, "radii": radii, "mean_z": means_z, "sd_z": sd_z,
            "means": means, "sds": sds, "constant": [r == 0 for r in radii],
            "fit_ids_sha256": object_hash([r["id"] for r in rows]),
            "weights_sha256": object_hash([[r["id"], weights[r["id"]]] for r in rows]),
            "weight_sum_float64": weight_sum, "mice": 73}


def transform(row, state):
    vector = raw_vector(row, state["layout"])
    result = []
    for x, a, radius, mu, zsd, constant in zip(vector, state["anchors"], state["radii"], state["mean_z"], state["sd_z"], state["constant"]):
        if constant:
            result.append(0.0); continue
        residual = x - a
        z = residual / radius if math.isfinite(residual) else x / radius - a / radius
        value = (z - mu) / zsd
        if not math.isfinite(value): raise ContractError("nonfinite transformed feature")
        result.append(value)
    return result
