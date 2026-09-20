"""Reusable proof-of-work helpers for FCVAR-001 (see PROOF_OF_WORK_SPEC.md).

A passing submission must be impossible to produce without running the real sliding-window
analysis on the real 30 ADHD-200 subjects: the per-subject observed mean edge-SD at each
window length must be the REAL values for the pinned cohort (validated against a held-out
reference by cross-subject correlation, robust to the preprocessing the task leaves to the
analyst), the group means must recompute from those rows, and the volunteered discriminating
quantity -- the observed/stationary-null ratio (~1.0) and the low fraction of surrogate-
significant subjects -- must be reported. An agent that only ran the naive sliding-window SD
(and concluded 'strong dynamics') has no stationary-null ratio to report.
"""
import csv
import json
import math
import re
import statistics
from pathlib import Path

import numpy as np


def canon_id(s):
    d = re.sub(r"\D", "", str(s))
    return d.lstrip("0") or "0"


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def load_reference(path):
    z = np.load(path, allow_pickle=True)
    ids = [canon_id(x) for x in z["ref_ids"]]
    ref = {"ids": ids, "stats": json.loads(str(z["ref_stats"]))}
    for w in ("20", "30", "44"):
        ref[w] = {i: float(v) for i, v in zip(ids, np.asarray(z[f"ref_w{w}"], float))}
    return ref


def _pick(headers, cands):
    norm_to_raw = {}
    for h in headers:
        norm_to_raw.setdefault(_norm(h), h)
    for c in cands:
        if c in norm_to_raw:
            return norm_to_raw[c]
    for nrm, raw in norm_to_raw.items():
        if any(c in nrm for c in cands):
            return raw
    return None


def load_submitted(path):
    """Return {canon_id: {'20':v,'30':v,'44':v}} from variability.csv (tolerant columns)."""
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    if not rows:
        return {}
    headers = list(rows[0].keys())
    id_c = _pick(headers, ("subjectindex", "subject", "subid", "index", "id"))
    cols = {w: _pick(headers, (f"meanedgesdw{w}", f"edgesdw{w}", f"meanedgesd{w}",
                               f"sdw{w}", f"w{w}")) for w in ("20", "30", "44")}
    out = {}
    for r in rows:
        cid = canon_id(r.get(id_c, "")) if id_c else ""
        if cid == "":
            continue
        rec = {}
        for w, c in cols.items():
            if c is None:
                continue
            try:
                rec[w] = float(r.get(c))
            except (TypeError, ValueError):
                pass
        out[cid] = rec
    return out


def coverage(sub, ref_ids):
    return sum(1 for i in ref_ids if i in sub) / max(1, len(ref_ids))


def cross_corr(sub, ref_w, ref_ids, w):
    matched = [i for i in ref_ids if i in sub and w in sub[i]
               and math.isfinite(sub[i].get(w, float("nan")))]
    if len(matched) < 3:
        return float("nan"), 0
    a = [sub[i][w] for i in matched]
    b = [ref_w[i] for i in matched]
    if np.std(a) == 0 or np.std(b) == 0:
        return float("nan"), len(matched)
    return float(np.corrcoef(a, b)[0, 1]), len(matched)


def per_subject_match(sub, ref_w, ref_ids, w, tol):
    matched = [i for i in ref_ids if i in sub and w in sub[i]]
    if not matched:
        return 0.0, 0
    ok = sum(1 for i in matched
             if math.isfinite(sub[i][w]) and abs(sub[i][w] - ref_w[i]) <= tol)
    return ok / len(matched), len(matched)


def nonconstant(sub, w, eps=1e-6):
    vals = [sub[i][w] for i in sub if w in sub[i] and math.isfinite(sub[i][w])]
    return len(vals) >= 3 and statistics.pstdev(vals) > eps


def group_mean(sub, w):
    vals = [sub[i][w] for i in sub if w in sub[i] and math.isfinite(sub[i][w])]
    return sum(vals) / len(vals) if vals else float("nan")


def collect_numbers_by_key(obj, key_re, exclude_re=None):
    """All numeric leaves reachable under a key matching key_re. Ancestor-aware: once any
    ancestor key matches, descendant leaves are collected even when keyed only by a window
    number (e.g. {"observed_over_null_ratio_mean": {"20": 1.02}}). A leaf is dropped if the
    matching key (ancestor or its own) also matches exclude_re at that level."""
    out = []
    exc = re.compile(exclude_re) if exclude_re else None
    pat = re.compile(key_re)

    def walk(o, matched=False, excluded=False):
        if isinstance(o, dict):
            for k, v in o.items():
                nk = _norm(k)
                m = matched or bool(pat.search(nk))
                x = excluded or bool(exc and exc.search(nk))
                walk(v, m, x)
        elif isinstance(o, list):
            for v in o:
                walk(v, matched, excluded)
        elif isinstance(o, (int, float)) and not isinstance(o, bool):
            if matched and not excluded:
                out.append(float(o))
    walk(obj)
    return out


def find_ratio_values(obj):
    """observed/null ratio numbers, keyed under a ratio/excess concept."""
    return collect_numbers_by_key(
        obj, r"ratio|observedovernull|obsovernull|excess|overnull|relativeto",
        exclude_re=r"pval|pvalue")


def find_frac_sig_values(obj):
    return collect_numbers_by_key(
        obj, r"fractionsubjects|fracsig|fractionsig|propsig|proportionsig|fractionplt|fracplt")
