"""Independent integer-count statistics for the public VISCAT recipe.

Counter ranks and pairwise wins are distinct from the oracle's SciPy rankdata.
The exact rational KW definition and NumPy PCG64 are deliberately shared public
mathematics. No oracle implementation, source result or historical bank input.
"""
from __future__ import annotations

from collections import Counter
from fractions import Fraction
import math

import numpy as np


CATEGORIES = (1, 2, 3, 4, 5)
N_REPEATS = 50


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def integers(values, name, nonnegative=False):
    a = np.asarray(values)
    require(a.ndim == 1 and a.dtype.kind in "iu", f"{name}: integer vector required")
    if a.size:
        require(int(a.max()) <= np.iinfo(np.int64).max and
                int(a.min()) >= np.iinfo(np.int64).min, f"{name}: integer overflow")
        if nonnegative:
            require(int(a.min()) >= 0, f"{name}: negative values")
    return a.astype(np.int64)


def validate_inputs(counts, categories):
    counts = integers(counts, "counts", True)
    categories = integers(categories, "categories")
    require(counts.shape == categories.shape, "Count/category shape mismatch")
    require(set(map(int, categories)) <= set(CATEGORIES), "Unknown category")
    return counts, categories


def auc_twice(counts, categories, preferred):
    counts, categories = validate_inputs(counts, categories)
    require(type(preferred) is int and preferred in CATEGORIES, "Invalid preferred category")
    positive = Counter(map(int, counts[categories == preferred]))
    negative = Counter(map(int, counts[categories != preferred]))
    n_positive, n_negative = sum(positive.values()), sum(negative.values())
    if not n_positive or not n_negative:
        return {"n_preferred": n_positive, "n_rest": n_negative, "u_preferred_twice": None, "auc": None}
    lower, twice = 0, 0
    for value in sorted(set(positive) | set(negative)):
        twice += positive[value] * (2 * lower + negative[value])
        lower += negative[value]
    require(0 <= twice <= 2*n_positive*n_negative, "Invalid doubled U")
    return {"n_preferred": n_positive, "n_rest": n_negative,
            "u_preferred_twice": twice, "auc": twice/(2*n_positive*n_negative)}


def is_selected(status, probability):
    return status == "ok" and probability < 0.05


def category_test(counts, categories):
    counts, categories = validate_inputs(counts, categories)
    supports = [int(np.count_nonzero(categories == c)) for c in CATEGORIES]
    sums = [sum(map(int, counts[categories == c])) for c in CATEGORIES]
    pooled = Counter(map(int, counts))
    before, rank2 = 0, {}
    for value, multiplicity in sorted(pooled.items()):
        rank2[value] = 2*before + multiplicity + 1
        before += multiplicity
    ranks = [sum(rank2[int(v)] for v in counts[categories == c]) for c in CATEGORIES]
    tie_sum = sum(n*n*n-n for n in pooled.values())
    result = {"n": len(counts), "supports": supports, "sums": sums,
              "means": [s/(1.5*n) if n else None for s, n in zip(sums, supports)],
              "rank_sum_twice": ranks, "tie_sum": tie_sum,
              "small_group_warning": any(0 < n < 5 for n in supports)}
    if not all(supports):
        result.update(status="insufficient_category_support", H=None, p=None,
                      preferred=None, preferred_tied=None, selected=False,
                      n_preferred=None, n_rest=None, u_preferred_twice=None, auc=None)
        return result
    means = [Fraction(s, n) for s, n in zip(sums, supports)]
    highest = max(means)
    winners = [c for c, mean in zip(CATEGORIES, means) if mean == highest]
    preferred = min(winners)
    n = len(counts)
    if len(pooled) == 1:
        status, H, probability = "all_tied", 0.0, 1.0
    else:
        H0 = Fraction(12, n*(n+1))*sum(Fraction(r*r, 4*k) for r, k in zip(ranks, supports))-3*(n+1)
        correction = 1-Fraction(tie_sum, n*n*n-n)
        require(H0 >= 0 and correction > 0, "Invalid exact KW arithmetic")
        H = float(H0/correction)
        probability = math.exp(-H/2)*(1+H/2)
        require(math.isfinite(H) and 0 <= probability <= 1, "Nonfinite KW arithmetic")
        status = "ok"
    result.update(status=status, H=H, p=probability, preferred=preferred,
                  preferred_tied=len(winners) > 1, selected=is_selected(status, probability))
    result.update(auc_twice(counts, categories, preferred))
    return result


def make_membership(categories_by_unit, repeats=N_REPEATS):
    """Caller supplies canonical asset-path/unit-row order and trial-row order."""
    require(type(repeats) is int and repeats >= 0, "Invalid repeat count")
    categories = [integers(c, "categories") for c in categories_by_unit]
    for c in categories:
        require(set(map(int, c)) <= set(CATEGORIES), "Unknown category")
    starts = np.cumsum([0]+[len(c) for c in categories], dtype=np.int64)
    masks = np.zeros((repeats, int(starts[-1])), dtype=bool)
    groups = [[np.flatnonzero(c == code) for code in CATEGORIES] for c in categories]
    supported = [all(len(g) >= 2 for g in unit) for unit in groups]
    rng = np.random.Generator(np.random.PCG64(0))
    for repeat in range(repeats):
        for unit, category_groups in enumerate(groups):
            if not supported[unit]:
                continue
            for original_indices in category_groups:
                shuffled = original_indices.copy()
                rng.shuffle(shuffled)
                chosen = shuffled[:len(shuffled)//2] + starts[unit]
                masks[repeat, chosen] = True
    return masks, starts, supported


def split_test(counts, categories, train):
    counts, categories = validate_inputs(counts, categories)
    train = np.asarray(train)
    require(train.dtype.kind == "b" and train.shape == counts.shape, "Invalid membership")
    supports = [int(np.count_nonzero(categories == c)) for c in CATEGORIES]
    if any(n < 2 for n in supports):
        require(not train.any(), "Unsupported membership must be false")
        return None
    require(all(int(np.count_nonzero(train & (categories == c))) == n//2
                for c, n in zip(CATEGORIES, supports)), "Invalid stratified support")
    fitted = category_test(counts[train], categories[train])
    heldout = auc_twice(counts[~train], categories[~train], fitted["preferred"])
    fitted["test_supports"] = [int(np.count_nonzero((~train) & (categories == c))) for c in CATEGORIES]
    fitted["test"] = heldout
    return fitted


def conditional_summary(splits):
    usable = [s for s in splits if s is not None]
    selected = [s["test"]["auc"] for s in usable if s["selected"]]
    require(all(x is not None and math.isfinite(x) and 0 <= x <= 1 for x in selected), "Invalid selected AUC")
    return {"n_usable_splits": len(usable), "n_selected_splits": len(selected),
            "conditional_auc": math.fsum(selected)/len(selected) if selected else None,
            "conditional_status": "defined" if selected else "no_selected_splits",
            "heldout_eligible": len(selected) >= 5}


def population(values):
    values = list(values)
    require(all(type(x) in (int, float) and math.isfinite(x) and 0 <= x <= 1 for x in values), "Invalid population AUC")
    return {"n_units": len(values), "mean_auc": math.fsum(values)/len(values) if values else None,
            "status": "defined" if values else "empty_population"}
