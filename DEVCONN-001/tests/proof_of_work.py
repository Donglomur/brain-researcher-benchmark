"""Reusable proof-of-work helpers for DEVCONN-001's grader.

A passing submission must be IMPOSSIBLE to produce without running the real Power-264
short/long-range connectivity analysis on the real ds000228 subjects AND performing the
head-motion control. These helpers validate the submitted per-subject connectivity.csv against
a held-out reference (tests/reference.npz), recompute the age~short-range Spearman FROM the
submitted rows, and locate the reported raw vs motion-controlled numbers for numeric grading.
"""
import csv
import json
import math
import re
import statistics
from pathlib import Path

import numpy as np


def _rankdata(a):
    """Average ranks (ties averaged), numpy-only (matches scipy.stats.rankdata)."""
    a = np.asarray(a, float)
    sorter = np.argsort(a, kind="mergesort")
    inv = np.empty(len(a), int)
    inv[sorter] = np.arange(len(a))
    a_sorted = a[sorter]
    obs = np.r_[True, a_sorted[1:] != a_sorted[:-1]]
    dense = obs.cumsum()[inv]
    count = np.r_[np.nonzero(obs)[0], len(a)]
    return 0.5 * (count[dense] + count[dense - 1] + 1)


def spearmanr_np(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    if len(x) < 3:
        return float("nan")
    rx, ry = _rankdata(x), _rankdata(y)
    if np.std(rx) == 0 or np.std(ry) == 0:
        return float("nan")
    return float(np.corrcoef(rx, ry)[0, 1])


def canon_id(s):
    return re.sub(r"\D", "", str(s)).lstrip("0")


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def load_reference(path):
    z = np.load(path, allow_pickle=True)
    ref = {
        "ids": [canon_id(x) for x in z["ref_ids"]],
        "short": np.asarray(z["ref_short"], float),
        "long": np.asarray(z["ref_long"], float),
        "seg": np.asarray(z["ref_seg"], float),
        "age": np.asarray(z["ref_age"], float),
        "group": [str(x) for x in z["ref_group"]],
        "stats": json.loads(str(z["ref_stats"])),
    }
    if "ref_fd" in z.files:
        ref["fd"] = np.asarray(z["ref_fd"], float)
    return ref


def load_submitted(path):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    if not rows:
        return []
    headers = list(rows[0].keys())
    norm = {h: _norm(h) for h in headers}

    def pick(cands, exclude=()):
        for h, n in norm.items():
            if any(c in n for c in cands) and not any(e in n for e in exclude):
                return h
        return None

    id_c = pick(("subjectindex", "subjectid", "subject", "participant", "subid", "id"))
    age_c = pick(("age",), exclude=("group", "range"))
    grp_c = pick(("group", "childadult", "cohort"))
    short_c = pick(("shortrange", "short"), exclude=("long",))
    long_c = pick(("longrange", "long"), exclude=("short",))
    fd_c = pick(("meanfd", "meanframewise", "framewisedisplacement", "fdmean", "meanmotion"),
                exclude=("mwu", "gt")) or pick(("fd",), exclude=("mwu", "gt"))
    out = []
    for r in rows:
        cid = canon_id(r.get(id_c, "")) if id_c else ""
        if not cid:
            continue
        def g(c):
            if c is None:
                return None
            try:
                return float(r.get(c))
            except (TypeError, ValueError):
                return None
        out.append({"id": cid, "age": g(age_c),
                    "group": (str(r.get(grp_c, "")).strip().lower() if grp_c else ""),
                    "short": g(short_c), "long": g(long_c), "fd": g(fd_c)})
    return out


def pearson(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    if len(x) < 3 or np.std(x) == 0 or np.std(y) == 0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def check_subjects_and_values(subrows, ref, key_ref, key_sub, val_tol, corr_min, cover, match,
                              eps=1e-4):
    refmap = {i: float(v) for i, v in zip(ref["ids"], ref[key_ref])}
    matched = [r for r in subrows if r["id"] in refmap and r.get(key_sub) is not None]
    coverage = len(matched) / max(1, len(refmap))
    assert coverage >= cover, (
        f"[{key_sub}] connectivity.csv covers only {coverage:.1%} of the {len(refmap)} real "
        f"ds000228 subjects (need >= {cover:.0%}). Fabricated or missing subject ids.")
    sub = [r[key_sub] for r in matched]
    refv = [refmap[r["id"]] for r in matched]
    assert statistics.pstdev(sub) > eps, f"[{key_sub}] constant across subjects -- not per-subject"
    rc = pearson(sub, refv)
    assert math.isfinite(rc) and rc >= corr_min, (
        f"[{key_sub}] submitted per-subject values do not track the reference (cross-subject "
        f"r={rc:.3f} < {corr_min}); not computed from the real Power-264 time series.")
    close = sum(1 for a, b in zip(sub, refv) if abs(a - b) <= val_tol)
    frac = close / max(1, len(matched))
    assert frac >= match, (
        f"[{key_sub}] only {frac:.1%} of matched subjects within {val_tol} of the reference "
        f"(need >= {match:.0%}); per-subject values are not the real ones.")
    return matched


def all_subjects_spearman(subrows, ref, key_sub):
    """Recompute Spearman(age, key) over ALL subjects from the submitted rows, using the
    reference age (ground-truth phenotype) keyed by id."""
    age = {i: float(a) for i, a in zip(ref["ids"], ref["age"])}
    xs, ys = [], []
    for r in subrows:
        if r.get(key_sub) is not None and r["id"] in age:
            xs.append(age[r["id"]]); ys.append(r[key_sub])
    if len(xs) < 40:
        return float("nan"), 0
    return spearmanr_np(xs, ys), len(xs)


def partial_spearman_np(y, x, cov):
    """Spearman partial correlation of y and x controlling `cov` (rank-residual method; numpy-only).
    Mirrors solution/compute.py's partial_spearman: rank y, x, cov; regress rank(y) and rank(x) on
    [1, rank(cov)]; Pearson-correlate the residuals."""
    x = np.asarray(x, float); y = np.asarray(y, float); cov = np.asarray(cov, float)
    if len(x) < 5:
        return float("nan")
    rx, ry, rc = _rankdata(x), _rankdata(y), _rankdata(cov)
    B = np.c_[np.ones(len(rc)), rc]

    def resid(rv):
        coef = np.linalg.lstsq(B, rv, rcond=None)[0]
        return rv - B @ coef
    ex, ey = resid(rx), resid(ry)
    if np.std(ex) == 0 or np.std(ey) == 0:
        return float("nan")
    return float(np.corrcoef(ex, ey)[0, 1])


def recompute_motion_collapse(subrows, ref, key_sub="short"):
    """Recompute, FROM the submitted rows, the raw all-subjects Spearman(age, short) and the
    mean-FD-partial Spearman(age, short | mean_fd), using the reference age (ground-truth
    phenotype) keyed by id and the SUBMITTED per-subject mean_fd. Returns
    {"raw", "partial", "collapse", "n"} where collapse = |raw| - |partial|. NaNs when the mean_fd
    column is absent/degenerate. This is the un-guessable gate: a guessed partial cannot help
    because the grader recomputes it from the real per-subject FD, and a fabricated FD column
    fails the pillar-1 match."""
    age = {i: float(a) for i, a in zip(ref["ids"], ref["age"])}
    ids, ys, fds = [], [], []
    for r in subrows:
        v = r.get(key_sub)
        fd = r.get("fd")
        if v is not None and fd is not None and r["id"] in age \
                and math.isfinite(v) and math.isfinite(fd):
            ids.append(age[r["id"]]); ys.append(v); fds.append(fd)
    out = {"raw": float("nan"), "partial": float("nan"), "collapse": float("nan"), "n": len(ys)}
    if len(ys) < 40:
        return out
    if float(np.std(fds)) == 0:
        return out
    out["raw"] = spearmanr_np(ids, ys)
    out["partial"] = partial_spearman_np(ys, ids, fds)
    if math.isfinite(out["raw"]) and math.isfinite(out["partial"]):
        out["collapse"] = abs(out["raw"]) - abs(out["partial"])
    return out


def find_by_path(obj, want, exclude=()):
    """First finite number in [-1.01,1.01] under a path matching all `want` tokens and none of
    `exclude` (tokens matched against the normalised '/'-joined key path). By default a p-value
    leaf (final key 'p'/'pval'/'pvalue') is skipped unless 'p' is explicitly wanted, so a
    correlation r is returned rather than its adjacent p-value regardless of dict ordering."""
    hit = [None]
    want_p = any(w in ("p", "pval", "pvalue") for w in want)

    def walk(o, path=""):
        if hit[0] is not None:
            return
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, path + "/" + str(k).lower())
        elif isinstance(o, list):
            for v in o:
                walk(v, path)
        elif isinstance(o, (int, float)) and not isinstance(o, bool):
            last = path.rsplit("/", 1)[-1]
            if not want_p and last in ("p", "pval", "pvalue", "pvalues"):
                return
            if all(w in path for w in want) and not any(e in path for e in exclude):
                hit[0] = float(o)
    walk(obj)
    return hit[0]
