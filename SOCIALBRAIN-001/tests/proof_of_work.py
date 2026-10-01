"""Real-subject ROI validation for the publicly declared GSR sensitivity pipelines.

Measurements are joined by actual participant ID; named estimands are never reassigned
by value or age. No forced GSR-dependence or causal confounding conclusion is graded.
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
    assert len(ref["ids"])==len(set(ref["ids"])), "duplicate reference participant ID"
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
    wp_c = pick(("withinpain", "painwithin", "within_pain"))
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
                    "within_tom": g(wt_c), "within_pain": g(wp_c),
                    "across_by_col": {c: g(c) for c in across_cols}})
    assert len(out)==len({row["id"] for row in out}), "duplicate participant ID"
    return out, across_cols


def align_by_id(subrows, ref, key_ref, get_val):
    """Authenticate measurements by actual participant identity, never age/value matching."""
    ids=[row["id"] for row in subrows]
    assert len(ids)==len(set(ids)), "duplicate participant ID"
    assert len(ref["ids"])==len(set(ref["ids"])), "duplicate reference participant ID"
    lookup={sid:i for i,sid in enumerate(ref["ids"])}
    values=[];targets=[]
    for row in subrows:
        value=get_val(row)
        if row["id"] in lookup and value is not None:
            values.append(float(value));targets.append(float(ref[key_ref][lookup[row["id"]]]))
    return values,targets


def assign_across_columns(subrows, ref, cover):
    """The public no-GSR/GSR names bind estimands; do not reassign by best numerical match."""
    columns=set().union(*(set(row.get("across_by_col",{})) for row in subrows))
    assert {"across_network","across_network_gsr"}<=columns, "both declared pipelines required"
    return "across_network","across_network_gsr",{}

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
    """Coverage, non-constant and same-participant measurement agreement."""
    sub, refv = align_by_id(subrows, ref, key_ref, lambda r: r.get(key_sub))
    n_ref = len(ref[key_ref])
    coverage = len(sub) / max(1, n_ref)
    assert coverage >= cover, (
        f"[{key_sub}] network_connectivity.csv covers only {coverage:.1%} of the {n_ref} "
        f"real ds000228 subjects by participant ID (need >= {cover:.0%}). Fabricated or missing subjects.")
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
    sub, refv = align_by_id(subrows, ref, key_ref, lambda r: r.get(key_sub))
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
    """Child membership and ages are ground-truth metadata keyed by actual participant ID."""
    lookup={sid:i for i,sid in enumerate(ref["ids"])}
    xs=[];ys=[]
    for row in subrows:
        index=lookup.get(row["id"])
        if index is not None and ref["group"][index]=="child" and row.get(key_sub) is not None:
            xs.append(float(ref["age"][index]));ys.append(float(row[key_sub]))
    if len(xs)<20:return float("nan"),0
    return spearmanr_np(xs,ys),len(xs)

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
