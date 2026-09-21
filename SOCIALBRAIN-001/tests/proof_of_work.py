"""Reusable proof-of-work helpers for SOCIALBRAIN-001's grader.

A passing submission must be IMPOSSIBLE to produce without running the real ToM/pain ROI
connectivity analysis on the real ds000228 subjects under BOTH pipelines. These helpers
validate the submitted per-subject network_connectivity.csv against a held-out reference
(tests/reference.npz), recompute the children's Spearman(age, across-network) FROM the
submitted rows, and expose the GSR-dependence for numeric grading.
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
    """Spearman rho = Pearson correlation of the average ranks."""
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
        "within_tom": np.asarray(z["ref_within_tom"], float),
        "within_pain": np.asarray(z["ref_within_pain"], float),
        "across": np.asarray(z["ref_across"], float),
        "across_gsr": np.asarray(z["ref_across_gsr"], float),
        "age": np.asarray(z["ref_age"], float),
        "group": [str(x) for x in z["ref_group"]],
        "stats": json.loads(str(z["ref_stats"])),
    }
    ref["idx"] = {i: k for k, i in enumerate(ref["ids"])}
    return ref


def load_submitted(path):
    """Return a list of dict rows with canon id + resolved columns.

    The across-network correlation may be reported under SEVERAL preprocessing choices, as
    several columns. We collect EVERY across-network candidate column (`across_by_col`) and let
    the grader assign, by value, which submitted column is the standard-clean quantity and which
    is the alternative-preprocessing quantity -- the grader never keys off a column NAME (so the
    specific preprocessing lever is not cued by the required schema)."""
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
    wt_c = pick(("withintom", "tomwithin", "within_tom"))
    # every across-network column (any preprocessing choice), regardless of its name
    across_cols = [h for h, n in norm.items()
                   if any(c in n for c in ("acrossnetwork", "across", "tompain", "betweennetwork"))
                   and not any(e in n for e in ("within",))]
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
        out.append({"id": cid, "age": g(age_c), "group": (str(r.get(grp_c, "")).strip().lower()
                                                          if grp_c else ""),
                    "within_tom": g(wt_c),
                    "across_by_col": {c: g(c) for c in across_cols}})
    return out, across_cols


def _age_key(a):
    """Round an age to a stable bucket key (or None if unparseable)."""
    try:
        return round(float(a), 2)
    except (TypeError, ValueError):
        return None


def align_by_age(subrows, ref_age, ref_vals, get_val):
    """Align submitted rows to reference subjects BY AGE -- a stable per-subject phenotype that is
    identical across fetch orders -- NOT by row id/index.

    `subject_index` is a fetch-ORDER label: a valid re-run (a different nilearn version / cache
    path) may enumerate ds000228 in a different order, so an id/index join compares mismatched
    subjects and a correct solve fails spuriously (its per-subject values look uncorrelated with the
    reference even though the sorted multisets are identical). Age is the real phenotype (identical
    across runs). Bucket the reference values by age; assign each submitted row to an unused
    reference subject of the same age. ~4/5 of ds000228 ages are unique, so those joins are forced
    and value-independent; age ties (a handful of buckets of 2-5) are broken by nearest
    submitted-vs-reference value, which only recovers the within-bucket pairing for a genuine solve
    and cannot rescue a fabricated column (the >120 forced singleton joins dominate every
    cross-subject correlation guard). Returns aligned (sub, refv) lists."""
    from collections import defaultdict
    buckets = defaultdict(list)
    for a, v in zip(ref_age, ref_vals):
        k = _age_key(a)
        if k is not None:
            buckets[k].append(float(v))
    for k in buckets:
        buckets[k].sort()
    sub, refv = [], []
    for r in subrows:
        v = get_val(r)
        k = _age_key(r.get("age"))
        if v is None or k is None:
            continue
        cand = buckets.get(k)
        if not cand:
            continue
        j = min(range(len(cand)), key=lambda i: abs(cand[i] - float(v)))  # nearest ref value at age
        refv.append(cand.pop(j)); sub.append(float(v))
    return sub, refv


def assign_across_columns(subrows, ref, cover):
    """Assign, BY VALUE, which submitted across-network column is the standard-clean quantity and
    which is the alternative-preprocessing quantity. For each candidate column, compute the
    cross-subject Pearson correlation against both held-out references (ref['across'] = standard
    clean, ref['across_gsr'] = alternative preprocessing) over the subjects joined BY AGE (see
    `align_by_age`; not by fetch-order id). The standard column is the one that best tracks
    ref['across']; the alternative column is the one that best tracks ref['across_gsr']. Returns
    (std_col, alt_col, diag) with either name possibly None if no candidate covers enough subjects.

    Nothing keys off the column NAME, so the grader does not tell the agent which preprocessing
    lever separates the two -- only that the across-network value under each choice they consider
    must be reported per subject."""
    n_ref = len(ref["across"])
    cols = set()
    for r in subrows:
        cols |= set(r.get("across_by_col", {}).keys())
    cols = sorted(cols)  # deterministic iteration (stable column assignment)
    best_std = (None, -2.0)
    best_alt = (None, -2.0)
    diag = {}
    for c in cols:
        getv = (lambda r, c=c: r.get("across_by_col", {}).get(c))
        xs_std, ys_std = align_by_age(subrows, ref["age"], ref["across"], getv)
        xs_alt, ys_alt = align_by_age(subrows, ref["age"], ref["across_gsr"], getv)
        coverage = len(xs_std) / max(1, n_ref)
        r_std = pearson(xs_std, ys_std) if len(xs_std) >= 20 else float("nan")
        r_alt = pearson(xs_alt, ys_alt) if len(xs_alt) >= 20 else float("nan")
        diag[c] = {"coverage": coverage, "r_std": r_std, "r_alt": r_alt}
        if coverage < cover:
            continue
        if math.isfinite(r_std) and r_std > best_std[1]:
            best_std = (c, r_std)
        if math.isfinite(r_alt) and r_alt > best_alt[1]:
            best_alt = (c, r_alt)
    return best_std[0], best_alt[0], diag


def bind_column(subrows, col, key):
    """Copy the chosen across-network column's per-subject value onto each row under `key`."""
    for r in subrows:
        r[key] = r.get("across_by_col", {}).get(col) if col is not None else None


def pearson(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    if len(x) < 3 or np.std(x) == 0 or np.std(y) == 0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def check_subjects_and_values(subrows, ref, key_ref, key_sub, val_tol, corr_min, cover, match,
                              eps=1e-4):
    """Pillar 1 for one column: coverage, non-constant, per-subject match to reference. Subjects
    are joined BY AGE (stable phenotype), not by fetch-order id -- see `align_by_age`."""
    sub, refv = align_by_age(subrows, ref["age"], ref[key_ref], lambda r: r.get(key_sub))
    n_ref = len(ref[key_ref])
    coverage = len(sub) / max(1, n_ref)
    assert coverage >= cover, (
        f"[{key_sub}] network_connectivity.csv covers only {coverage:.1%} of the {n_ref} "
        f"real ds000228 subjects by age (need >= {cover:.0%}). Fabricated or missing subjects.")
    assert statistics.pstdev(sub) > eps, f"[{key_sub}] constant across subjects -- not per-subject"
    rc = pearson(sub, refv)
    assert math.isfinite(rc) and rc >= corr_min, (
        f"[{key_sub}] submitted per-subject values do not track the reference (cross-subject "
        f"r={rc:.3f} < {corr_min}); not computed from the real ROI time series.")
    close = sum(1 for a, b in zip(sub, refv) if abs(a - b) <= val_tol)
    frac = close / max(1, len(sub))
    assert frac >= match, (
        f"[{key_sub}] only {frac:.1%} of matched subjects within {val_tol} of the reference "
        f"(need >= {match:.0%}); per-subject values are not the real ones.")
    return sub


def check_real_extraction(subrows, ref, key_ref, key_sub, cover, corr_min, eps=1e-4):
    """Robust anti-fabrication guard for a pipeline-SENSITIVE per-subject quantity (the within-
    network connectivity). Require it to be a real, non-constant per-subject column that clearly
    tracks the reference's cross-subject structure (age-joined r >= corr_min), WITHOUT pinning
    per-subject magnitudes to one temporal-filter choice. A defensible band-pass within-network
    column shifts magnitudes relative to the reference's detrend pipeline (so it fails a tight
    VAL_TOL/MATCH per-subject pin: only ~0.63 within 0.08, r~0.74) yet is unmistakably a real
    extraction; a shuffled / constant / mislabelled (within-pain-in-the-tom-slot) column correlates
    <= ~0.3. The across-network pillars carry the discriminating teeth at the strict CORR_MIN/MATCH;
    this guard only certifies that a real within-network ROI extraction was performed."""
    sub, refv = align_by_age(subrows, ref["age"], ref[key_ref], lambda r: r.get(key_sub))
    n_ref = len(ref[key_ref])
    coverage = len(sub) / max(1, n_ref)
    assert coverage >= cover, (
        f"[{key_sub}] covers only {coverage:.1%} of the {n_ref} real ds000228 subjects by age "
        f"(need >= {cover:.0%}). Fabricated or missing subjects.")
    assert statistics.pstdev(sub) > eps, f"[{key_sub}] constant across subjects -- not per-subject"
    rc = pearson(sub, refv)
    assert math.isfinite(rc) and rc >= corr_min, (
        f"[{key_sub}] does not track the real per-subject within-network structure (cross-subject "
        f"r={rc:.3f} < {corr_min}); not a real ROI extraction (shuffled/constant/mislabelled).")
    return sub


def children_spearman(subrows, ref, key_sub):
    """Recompute Spearman(age, key) over the CHILDREN from the submitted rows. Group is derived
    from the reference BY AGE (ds000228 is a clean age->group phenotype: children <=~12.3y, adults
    >=~18y, no overlap), so a mislabelled/absent group column and the fetch-order id are both
    irrelevant. The age axis is the submitted row's own age (identical to the reference age)."""
    grp_by_age = {}
    for a, g in zip(ref["age"], ref["group"]):
        k = _age_key(a)
        if k is not None:
            grp_by_age[k] = g
    xs, ys = [], []
    for r in subrows:
        k = _age_key(r.get("age"))
        v = r.get(key_sub)
        if k is not None and grp_by_age.get(k) == "child" and v is not None:
            xs.append(float(r["age"])); ys.append(float(v))
    if len(xs) < 20:
        return float("nan"), 0
    return spearmanr_np(xs, ys), len(xs)


def find_number(obj, key_patterns, exclude=None):
    exc = [re.compile(e) for e in (exclude or [])]
    pats = [re.compile(p) for p in key_patterns]
    stack = [obj]
    while stack:
        cur = stack.pop(0)
        if isinstance(cur, dict):
            for k, v in cur.items():
                nk = _norm(k)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    if any(p.search(nk) for p in pats) and not any(e.search(nk) for e in exc):
                        try:
                            fv = float(v)
                            if math.isfinite(fv):
                                return fv
                        except Exception:
                            pass
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    return None


def find_across_r(obj, gsr):
    """Find a reported across-network vs age Spearman r. gsr=True -> the GSR variant; False ->
    the standard/no-GSR variant. Walks paths so the with/without-GSR variants are told apart."""
    best = None

    def walk(o, path=""):
        nonlocal best
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, path + "/" + str(k).lower())
        elif isinstance(o, list):
            for v in o:
                walk(v, path)
        elif isinstance(o, (int, float)) and not isinstance(o, bool):
            v = float(o)
            if not (-1.01 <= v <= 1.01):
                return
            has_across = re.search(r"across|tompain|betweennet", path)
            is_r = re.search(r"(^|/)r$|/r/|spearman|_r\b|rs\b|/r_", path) or path.endswith("/r")
            has_gsr = re.search(r"gsr|globalsignal", path)
            if has_across and is_r and (bool(has_gsr) == gsr):
                if best is None:
                    best = v
    walk(obj)
    return best
