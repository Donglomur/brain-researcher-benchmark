"""Released Majaj notebook algebra and labelled preparation, not a qualified study.

Source correspondence and unresolved final-paper differences are in SOURCE.md.
NumPy is imported only when a numerical function is called. No file/network I/O.
"""
from __future__ import annotations
import math

GROUPS = (("Tito", "V4"), ("Tito", "IT"), ("Chabo", "V4"), ("Chabo", "IT"))
PATTERNS = ("ijji", "iiii", "ijjj", "ijjl", "iijj", "iijl", "ijlm")
ESTIMATORS = ("naive", "row", "column", "both")
RECIPE = "released_Majaj_1000_draws_numpy_prospective_rng_v1"
RNG = "numpy_PCG64_SeedSequence_seed_group_axis_grid_draw_v1"


class MajajError(ValueError):
    """A declared input, support or recipe refusal; never scientific approval."""


def need(ok, reason):
    if not ok:
        raise MajajError(reason)


def integer(x, lo, hi, name):
    need(type(x) is int and lo <= x <= hi, name)
    return x


def _labels(values, count, name, unique=False):
    need(type(values) is list and len(values) == count, name + " length")
    need(all(type(x) is str and bool(x) for x in values), name + " string identities")
    if unique:
        need(len(set(values)) == count, name + " unique identities")


def prepare_assembly(responses, coordinates, provenance, group):
    """Get_DiCarlo C2: first duplicate, sorted common support, 28 repetitions.

    Coordinates are an operator-supplied explicit mapping of a labelled assembly.
    A provenance string is not authenticated acquisition or source qualification.
    No time averaging, centering, scaling or trial averaging is introduced.
    """
    import numpy as np
    need(tuple(group) in GROUPS, "one of the four released animal/region groups")
    need(set(coordinates) == {"dimensions", "repetition", "stimulus", "object_name",
         "neuroid_id", "animal", "region"}, "closed coordinate mapping")
    dims = coordinates["dimensions"]
    need(type(dims) is list and len(dims) == 3 and
         set(dims) == {"presentation", "neuroid", "time_bin"}, "explicit dimension identities")
    x = np.asarray(responses)
    need(x.ndim == 3 and x.dtype.kind in "iuf" and np.isfinite(x).all(), "finite numeric assembly")
    x = np.transpose(x, [dims.index(k) for k in ("presentation", "neuroid", "time_bin")])
    n, q, t = x.shape
    need(n > 0 and q > 0 and t == 1, "source requires singleton time_bin, no invented averaging")
    need(set(provenance) == {"dataset", "assembly_revision", "package_revision", "units",
                           "time_bin_description", "upstream_window_status"}, "explicit provenance operands")
    need(provenance["dataset"] == "MajajHong2015.public", "released dataset identity")
    need(all(type(v) is str and bool(v) for v in provenance.values()), "provenance strings")
    reps, stims = coordinates["repetition"], coordinates["stimulus"]
    need(type(reps) is list and len(reps) == n and all(type(v) is int and v >= 0 for v in reps), "repetition labels")
    need(type(stims) is list and len(stims) == n and all(type(v) is int and 0 <= v < 5000 for v in stims), "5000-stimulus domain")
    _labels(coordinates["object_name"], n, "object_name")
    _labels(coordinates["neuroid_id"], q, "neuroid_id", unique=True)
    _labels(coordinates["animal"], q, "animal")
    _labels(coordinates["region"], q, "region")
    columns = [i for i in range(q) if (coordinates["animal"][i], coordinates["region"][i]) == tuple(group)]
    need(bool(columns), "missing planned animal/region group")
    firsts, duplicates = [], []
    for rep in range(28):
        first, discarded = {}, []
        for i, r in enumerate(reps):
            if r != rep:
                continue
            if stims[i] in first:
                discarded.append({"stimulus": stims[i], "kept_presentation": first[stims[i]], "discarded_presentation": i})
            else:
                first[stims[i]] = i
        need(bool(first), "missing repetition " + str(rep))
        firsts.append(first)
        duplicates.append(discarded)
    common = sorted(set.intersection(*(set(x) for x in firsts)))
    need(bool(common), "empty 28-repetition intersection")
    positions = [[first[s] for s in common] for first in firsts]
    objects = [[coordinates["object_name"][i] for i in row] for row in positions]
    need(all(row == objects[0] for row in objects), "object identity changes across retained repetitions")
    # Advanced indexing returns owned tensors; input is never normalized or mutated.
    out = x[np.asarray(positions)[:, :, None], np.asarray(columns)[None, None, :], 0].copy()
    return {"trials": out, "stimulus_ids": np.asarray(common, dtype=np.int64),
            "presentation_indices": np.asarray(positions, dtype=np.int64),
            "support": {"group": list(group), "repetitions": list(range(28)),
                "source_stimulus_domain": 5000, "retained_stimuli": len(common),
                "neuroid_ids": [coordinates["neuroid_id"][i] for i in columns],
                "original_neuroid_indices": columns, "object_names": objects[0],
                "discarded_duplicates": duplicates,
                "dropped_from_common_by_repetition": [sorted(set(f) - set(common)) for f in firsts],
                "ignored_repetition_labels": sorted(set(reps) - set(range(28))),
                "provenance": dict(provenance), "normalization": "none_added",
                "window": "singleton supplied time_bin; upstream window remains unqualified"}}


def seven_terms(A, B):
    """C1 gett_all exactly: all free row indices, and excluded equal columns.

    In particular ijji contains trace((A B.T)^2), not ||A B.T||_F^2.
    NumPy float64 algebra is a new backend; literal JAX parity is not asserted.
    """
    import numpy as np
    a, b = np.asarray(A, dtype=np.float64), np.asarray(B, dtype=np.float64)
    need(a.ndim == 2 and a.shape == b.shape and a.shape[0] >= 4 and a.shape[1] >= 2,
         "paired P>=4 Q>=2 matrices")
    need(np.isfinite(a).all() and np.isfinite(b).all(), "finite paired matrices")
    p, q = a.shape
    nf = np.sqrt(p) * np.sqrt(q)
    a, b = a / nf, b / nf
    terms = []
    with np.errstate(over="ignore", invalid="ignore", under="ignore"):
        for i, j, l, m in PATTERNS:
            same_row = np.einsum(f"{i}a,{j}a,{l}b,{m}b->", a, b, a, b, optimize=True)
            same_col = np.einsum(f"{i}a,{j}a,{l}a,{m}a->", a, b, a, b, optimize=True)
            terms.append((float(same_row), float(same_row - same_col)))
    return terms


def _scalar(value):
    v = float(value)
    return v if math.isfinite(v) else None


def estimate_pair(A, B):
    """C1 getest_all; four literal parts and their distinct failure dispositions."""
    import numpy as np
    terms = seven_terms(A, B)
    p, q = np.shape(A)
    (t1, d1), (t2, d2), (t3, d3), (t5, d5), (t6, d6), (t7, d7), (t9, d9) = terms
    f1, f2, f3 = p / (p - 2), 2 / (p - 2), 1 / ((p - 1) * (p - 2))
    def corrected(t1, t2, t3, t5, t6, t7, t9):
        den = p / (p - 3) * (t1 - f1*t2 + f2*(2*t3-t5) + f3*(t6-2*t7+t9))
        num = p / (p - 3) * (t6 - 2/(p-1)*t7 + 1/(p-2)*(4*t3-p*t2) + f3*(t9-4*t5+2*t1-t6))
        return num, den
    row = corrected(t1, t2, t3, t5, t6, t7, t9)
    both = tuple(v * q/(q-1) for v in corrected(d1, d2, d3, d5, d6, d7, d9))
    parts = ((t6-2/p*t7+t9/p**2, t1-2/p*t5+t9/p**2), row,
             (d6-2/p*d7+d9/p**2, d1-2/p*d5+d9/p**2), both)
    result = {}
    for name, (num, den) in zip(ESTIMATORS, parts):
        with np.errstate(all="ignore"):
            ratio = float(np.divide(num, den))
        status = "nonfinite_moment" if not (math.isfinite(num) and math.isfinite(den)) else (
            "undefined_denominator" if den == 0 else "ok" if math.isfinite(ratio) else "nonfinite_ratio")
        result[name] = {"A": _scalar(num), "B": _scalar(den), "gamma": _scalar(ratio), "status": status,
            "nonfinite_kinds": {k: str(v) for k, v in (("A", num), ("B", den), ("gamma", ratio)) if not math.isfinite(v)},
            "positive_ratio": bool(math.isfinite(ratio) and ratio > 0)}
    return result


def axis_plan(M, F, group, axis, seed):
    """Ten literal integer grid ordinals, never unique/deduplicated/full-support substituted."""
    import numpy as np
    integer(M, 4, 5000, "aligned stimulus count")
    integer(F, 2, 2**31-1, "selected neuroid count")
    need(tuple(group) in GROUPS and axis in ("P", "Q"), "released group/axis")
    integer(seed, 0, 2**64-1, "explicit prospective RNG seed")
    counts = np.power(10, np.linspace(np.log10(200 if axis == "P" else 10),
                       np.log10(M if axis == "P" else F), 10)).astype(int).tolist()
    return {"recipe": RECIPE, "group": list(group), "axis": axis, "M": M, "F": F,
            "rng_protocol": RNG, "seed": seed, "draws_per_grid": 1000,
            "historical_seed_recovered": False, "paper_recipe_resolved": False,
            "grid": [{"ordinal": i, "P": int(c) if axis == "P" else M,
                      "Q": int(c) if axis == "Q" else F,
                      "sampleable": bool(4 <= (c if axis == "P" else M) <= M and
                                         2 <= (c if axis == "Q" else F) <= F)} for i, c in enumerate(counts)]}


def validate_plan(plan):
    need(type(plan) is dict, "axis plan mapping")
    expected = axis_plan(plan["M"], plan["F"], plan["group"], plan["axis"], plan["seed"])
    # Type-sensitive JSON comparison prevents bool/int identity substitutions.
    import json
    need(json.dumps(plan, sort_keys=True, allow_nan=False) == json.dumps(expected, sort_keys=True, allow_nan=False),
         "exact source recipe; caller cannot change grid, draw count or RNG")
    return expected


def draw(trials, plan, grid_ordinal, draw_ordinal):
    import numpy as np
    plan = validate_plan(plan)
    integer(grid_ordinal, 0, 9, "grid ordinal")
    integer(draw_ordinal, 0, 999, "draw ordinal")
    x = np.asarray(trials)
    need(x.shape == (28, plan["M"], plan["F"]) and x.dtype.kind in "iuf" and np.isfinite(x).all(), "full prepared 28-repeat panel")
    cell = plan["grid"][grid_ordinal]
    identity = {"group": plan["group"], "axis": plan["axis"], "grid_ordinal": grid_ordinal,
                "draw_ordinal": draw_ordinal, "seed": plan["seed"], "rng_protocol": RNG}
    if not cell["sampleable"]:
        return {**identity, "status": "insufficient_support", "selection": None,
                "estimates": {k: {"status": "insufficient_support", "A": None, "B": None, "gamma": None,
                                     "nonfinite_kinds": {}, "positive_ratio": False} for k in ESTIMATORS}}
    # Counter-addressed per-draw RNG is explicitly prospective. NumPy/JAX historical
    # process state is unrecoverable; this does not claim the original realizations.
    rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence(
        [plan["seed"], GROUPS.index(tuple(plan["group"])), ("P", "Q").index(plan["axis"]), grid_ordinal, draw_ordinal])))
    reps = rng.choice(28, size=2, replace=False)
    rows = rng.choice(plan["M"], size=cell["P"], replace=False)
    cols = rng.choice(plan["F"], size=cell["Q"], replace=False)
    one, two = (x[t][np.ix_(rows, cols)] for t in reps)
    return {**identity, "status": "drawn", "selection": {"repetitions": reps.tolist(),
            "row_indices": rows.tolist(), "column_indices": cols.tolist()}, "estimates": estimate_pair(one, two)}


def _literal_array(records, key):
    import numpy as np
    vals = []
    for r in records:
        value = r[key]
        if value is None:
            kind = r.get("nonfinite_kinds", {}).get(key)
            vals.append(float(kind) if kind in ("nan", "inf", "-inf") else float("nan"))
        else:
            need(type(value) in (int, float) and math.isfinite(value), "finite encoded scalar")
            vals.append(float(value))
    return np.asarray(vals)


def _check_estimate(row):
    import numpy as np
    need(type(row) is dict and set(row) == {"A", "B", "gamma", "status", "nonfinite_kinds", "positive_ratio"}, "closed estimator record")
    need(type(row["nonfinite_kinds"]) is dict and set(row["nonfinite_kinds"]) <= {"A", "B", "gamma"}, "nonfinite scalar map")
    if row["status"] == "insufficient_support":
        need(all(row[k] is None for k in ("A", "B", "gamma")) and row["nonfinite_kinds"] == {} and row["positive_ratio"] is False, "support failure cannot carry a numeric success")
        return
    aa, bb = (float(_literal_array([row], k)[0]) for k in ("A", "B"))
    with np.errstate(all="ignore"):
        ratio = float(np.divide(aa, bb))
    status = "nonfinite_moment" if not (math.isfinite(aa) and math.isfinite(bb)) else ("undefined_denominator" if bb == 0 else "ok" if math.isfinite(ratio) else "nonfinite_ratio")
    need(row["status"] == status and type(row["positive_ratio"]) is bool and row["positive_ratio"] == bool(math.isfinite(ratio) and ratio > 0), "numeric status consistency")
    need(row["gamma"] == _scalar(ratio) and (row["gamma"] is None or type(row["gamma"]) in (int, float)), "ratio must equal the retained A/B")
    expected = {k: str(v) for k, v in (("A", aa), ("B", bb), ("gamma", ratio)) if not math.isfinite(v)}
    need(row["nonfinite_kinds"] == expected, "exact nonfinite disposition")


def aggregate_axis(records, plan):
    """Complete 10x1000 source plotting computation; raw failures never disappear.

    Author source nanmean/nanmedian/std0 are diagnostic outputs. Protected all-draw
    summaries are supplied separately by the existing S3 scoring.curves caller.
    """
    import numpy as np
    plan = validate_plan(plan)
    need(type(records) is list and len(records) == 10000, "all 10 x 1000 draw records required")
    slots = {}
    for row in records:
        integer(row["grid_ordinal"], 0, 9, "record grid")
        integer(row["draw_ordinal"], 0, 999, "record draw")
        key = (row["grid_ordinal"], row["draw_ordinal"])
        need(key not in slots, "duplicate draw record")
        need(row["group"] == plan["group"] and row["axis"] == plan["axis"] and
             type(row["seed"]) is int and row["seed"] == plan["seed"] and row["rng_protocol"] == RNG,
             "record recipe identity")
        need(set(row["estimates"]) == set(ESTIMATORS), "all four estimator parts")
        cell = plan["grid"][key[0]]
        need(row["status"] == ("drawn" if cell["sampleable"] else "insufficient_support"), "planned draw support status")
        for estimate in row["estimates"].values():
            _check_estimate(estimate)
            need((estimate["status"] == "insufficient_support") == (not cell["sampleable"]), "no invented support failure or success")
        if cell["sampleable"]:
            selection = row["selection"]
            need(type(selection) is dict and set(selection) == {"repetitions", "row_indices", "column_indices"}, "paired selection mapping")
            for name, count, upper in (("repetitions", 2, 28), ("row_indices", cell["P"], plan["M"]), ("column_indices", cell["Q"], plan["F"])):
                values = selection[name]
                need(type(values) is list and len(values) == count and len(set(values)) == count and all(type(v) is int and 0 <= v < upper for v in values), "paired selection identity: " + name)
        else:
            need(row["selection"] is None, "unsupported draw has no selection")
        slots[key] = row
    need(len(slots) == 10000, "full ordinal census")
    grouped = [[slots[g, d] for d in range(1000)] for g in range(10)]
    last = [r["estimates"]["both"] for r in grouped[-1]]
    with np.errstate(all="ignore"):
        anchor = float(np.divide(_literal_array(last, "A").mean(), _literal_array(last, "B").mean()))
    curves = {}
    for name in ESTIMATORS:
        cells = []
        for g, rows in enumerate(grouped):
            raw = [r["estimates"][name] for r in rows]
            # Recompute A/B; never accept candidate-supplied ratios as numeric evidence.
            aa, bb = _literal_array(raw, "A"), _literal_array(raw, "B")
            with np.errstate(all="ignore"):
                ratios = aa / bb
                valid_nan = ratios[~np.isnan(ratios)]
                mean = float(valid_nan.mean()) if len(valid_nan) else float("nan")
                median = float(np.median(valid_nan)) if len(valid_nan) else float("nan")
                sd = float(ratios.std(ddof=0))
                mse = float(np.mean((anchor-ratios)**2)) if g < 9 else None
            cells.append({"ordinal": g, "planned_draws": 1000,
                "status_counts": {s: sum(r["status"] == s for r in raw) for s in sorted({r["status"] for r in raw})},
                "finite_ratios": int(np.isfinite(ratios).sum()), "nan_ratios": int(np.isnan(ratios).sum()),
                "infinite_ratios": int(np.isinf(ratios).sum()),
                "nanmean_ratio": _scalar(mean), "nanmedian_ratio": _scalar(median),
                "ordinary_std_ddof0": _scalar(sd), "ordinary_mse_to_last_grid": _scalar(mse) if mse is not None else None,
                "mse_plotted": g < 9, "raw_records": raw})
        curves[name] = cells
    return {"source_plot_curves": curves, "last_grid_both_ratio_of_means": _scalar(anchor),
            "anchor_nonfinite_kind": None if math.isfinite(anchor) else str(anchor),
            "reference_grid": plan["grid"][-1], "reference_is_full_support":
                plan["grid"][-1]["P"] == plan["M"] and plan["grid"][-1]["Q"] == plan["F"],
            "denominator": {"planned_draws": 10000, "retained_draws": len(records),
                            "estimator_records": 40000},
            "qualification": "source diagnostic; no final-paper or native-parity claim"}
