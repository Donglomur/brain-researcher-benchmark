"""Literal control-flow translation of the released Hungarian.m assignment.

The original min_line_cover stops at an augmenting path; do not replace its
result with a maximum-cardinality algorithm and call that faithful replay.
No claim of qualified native MATLAB floating-point parity is made.
"""
import time
import numpy as np
from scipy.optimize import linear_sum_assignment

class Refused(ValueError):
    pass

def need(ok, message):
    if not ok:
        raise Refused(message)

def tick(deadline):
    need(time.monotonic() < deadline, "assignment deadline")

def star_zeros(cost, deadline):
    n = len(cost)
    mask = np.zeros((n, n), dtype=np.uint8)
    covered_cols = np.zeros(n, dtype=bool)
    for r in range(n):
        tick(deadline)
        candidates = np.flatnonzero((cost[r] == 0) & ~covered_cols)
        if len(candidates):
            c = int(candidates[0])
            mask[r, c] = 1
            covered_cols[c] = True
    return mask

def step4(cost, rows, cols, mask, deadline):
    while True:
        tick(deadline)
        uncovered = (cost == 0) & ~rows[:, None] & ~cols[None, :]
        available = np.flatnonzero(uncovered)
        if not len(available):
            return None
        r, c = divmod(int(available[0]), len(cost))
        mask[r, c] = 2
        starred = np.flatnonzero(mask[r] == 1)
        if len(starred):
            need(len(starred) == 1, "invalid source assignment row state")
            rows[r] = True
            cols[int(starred[0])] = False
        else:
            return r, c

def min_line_cover_source(edge, deadline):
    mask = star_zeros(edge, deadline)
    rows = np.zeros(len(edge), dtype=bool)
    cols = np.any(mask == 1, axis=0)
    step4(edge, rows, cols, mask, deadline)
    # Exactly the released early-stop control flow, not a true minimum cover.
    return int(len(edge) - rows.sum() - cols.sum())

def matlab_hungarian_control_flow(performance, deadline):
    perf = np.asarray(performance, dtype=np.float64)
    need(perf.ndim == 2 and max(perf.shape, default=0) <= 512, "assignment shape cap")
    need(not np.isnan(perf).any() and not np.isneginf(perf).any() and np.all(perf[np.isfinite(perf)] >= 0), "invalid source costs")
    result = np.zeros(perf.shape, dtype=bool)
    x = np.flatnonzero(np.any(np.isfinite(perf), axis=1))
    y = np.flatnonzero(np.any(np.isfinite(perf), axis=0))
    n = max(len(x), len(y))
    if n == 0:
        return result, {"condensed_size": 0, "source_cnum": 0, "padded_size": 0}
    condensed = np.zeros((n, n), dtype=np.float64)
    condensed[:len(x), :len(y)] = perf[np.ix_(x, y)]
    edge = np.where(np.isfinite(condensed), 0.0, np.inf)
    cnum = min_line_cover_source(edge, deadline)
    need(0 <= cnum <= n, "invalid original cnum")
    pmax = float(condensed[np.isfinite(condensed)].max())
    total = n + cnum
    cost = np.full((total, total), pmax, dtype=np.float64)
    cost[:len(x), :len(y)] = perf[np.ix_(x, y)]
    minima = cost.min(axis=1)
    need(np.isfinite(minima).all(), "source padded matrix has infeasible row")
    cost -= minima[:, None]
    mask = star_zeros(cost, deadline)
    rows = np.zeros(total, dtype=bool)
    cols = np.any(mask == 1, axis=0)
    steps = 0
    while not np.all(cols):
        tick(deadline)
        steps += 1
        need(steps <= 100000, "source assignment iteration cap")
        endpoint = step4(cost, rows, cols, mask, deadline)
        if endpoint is None:
            sub = cost[np.ix_(~rows, ~cols)]
            need(sub.size > 0, "empty uncovered source assignment matrix")
            minimum = float(sub.min())
            need(np.isfinite(minimum) and minimum > 0, "invalid source uncovered minimum")
            cost[rows, :] += minimum
            cost[:, ~cols] -= minimum
            continue
        path = [endpoint]
        while True:
            tick(deadline)
            r, c = path[-1]
            star = np.flatnonzero(mask[:, c] == 1)
            if not len(star):
                break
            need(len(star) == 1, "invalid source assignment column state")
            r2 = int(star[0])
            path.append((r2, c))
            prime = np.flatnonzero(mask[r2] == 2)
            need(len(prime) == 1, "invalid source prime state")
            path.append((r2, int(prime[0])))
        for r, c in path:
            mask[r, c] = 0 if mask[r, c] == 1 else 1
        rows[:] = False
        cols[:] = False
        mask[mask == 2] = 0
        cols = np.any(mask == 1, axis=0)
    real = mask[:len(x), :len(y)] == 1
    need(np.isfinite(perf[np.ix_(x, y)])[real].all(), "source selected forbidden edge")
    result[np.ix_(x, y)] = real
    return result, {"condensed_size": n, "source_cnum": cnum, "padded_size": total, "main_steps": steps}

def mask_columns(mask, allow_empty=False):
    a = np.asarray(mask)
    need(a.ndim == 3 and a.shape[:2] == (50, 50) and a.shape[2] <= 512, "mask shape")
    need(allow_empty or a.shape[2] > 0, "empty ground truth")
    need(a.dtype.kind in "buif" and np.isfinite(a).all() and np.all((a == 0) | (a == 1)), "mask must be finite binary numeric/logical")
    # MATLAB reshape(Masks,Lx*Ly,[]) uses first spatial index fastest.
    columns = a.reshape((2500, a.shape[2]), order="F").astype(np.uint32, copy=False)
    need(np.all(columns.sum(axis=0) > 0), "empty individual neuron mask")
    return columns

def score_masks(gt, prediction, deadline):
    g = mask_columns(gt)
    p = mask_columns(prediction, allow_empty=True)
    ng, npred = g.shape[1], p.shape[1]
    if npred == 0:
        return {"ground_truth_neurons": ng, "predicted_neurons": 0,
                "matlab_control_flow": {"matches": 0, "recall": 0.0, "precision": 0.0, "f1": 0.0, "status": "source_empty_set_zero"},
                "suns_python_finite2": {"matches": 0, "recall": 0.0, "precision": 0.0, "f1": 0.0}, "counts_agree": True}
    tick(deadline)
    intersection = g.T @ p
    union = g.sum(axis=0)[:, None] + p.sum(axis=0)[None, :] - intersection
    need(np.all(union > 0), "undefined Jaccard union")
    distance = 1 - intersection / union
    forbidden = distance > 0.5
    matlab_cost = np.where(forbidden, np.inf, distance)
    matching, details = matlab_hungarian_control_flow(matlab_cost, deadline)
    matched = int(matching.sum())
    recall, precision = matched / ng, matched / npred
    # Preserve released MATLAB's nonempty zero-match 0/0 result as JSON null.
    f1 = 2 * recall * precision / (recall + precision) if matched else None
    finite2 = np.where(forbidden, 2.0, distance)
    rows, cols = linear_sum_assignment(finite2)
    py_matches = int((finite2[rows, cols] < 1).sum())
    py_rec, py_prec = py_matches / ng, py_matches / npred
    py_f1 = 2 * py_rec * py_prec / (py_rec + py_prec) if py_matches else 0.0
    return {"ground_truth_neurons": ng, "predicted_neurons": npred,
            "matlab_control_flow": {"matches": matched, "recall": recall, "precision": precision, "f1": f1,
                                    "status": "finite" if matched else "source_nonempty_zero_match_NaN", "assignment": details},
            "suns_python_finite2": {"matches": py_matches, "recall": py_rec, "precision": py_prec, "f1": py_f1},
            "counts_agree": matched == py_matches}
