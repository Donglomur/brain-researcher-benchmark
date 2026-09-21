"""Reusable proof-of-work helpers for NETSEG-001's grader.

A passing submission must be IMPOSSIBLE to produce without running the real POSITIVE-EDGE
system-segregation analysis on the real developmental cohort. These helpers validate the
submitted per-participant segregation.csv against a reference (tests/reference.npz; held out of
the agent CONTAINER but PUBLIC in this repo (burned) -- a real eval needs fresh tasks / a
server-side reference), and recompute the cohort mean FROM the submitted rows. An all-edges run (which keeps the
anti-correlations and inflates segregation to ~0.55) has the WRONG per-subject values and the
WRONG recomputed mean, so it fails.
"""
import csv
import json
import math
import re
import statistics
from pathlib import Path

import numpy as np


def canon_id(s):
    return re.sub(r"\D", "", str(s)).lstrip("0")


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def load_reference(path):
    z = np.load(path, allow_pickle=True)
    ref = {
        "ids": [canon_id(x) for x in z["ref_ids"]],
        "seg_pos": np.asarray(z["ref_seg_pos"], dtype=float),
        "seg_all": np.asarray(z["ref_seg_all"], dtype=float),
        "group": [str(x) for x in z["ref_group"]],
        "age": np.asarray(z["ref_age"], dtype=float),
        "stats": json.loads(str(z["ref_stats"])),
    }
    ref["by_id"] = {i: float(s) for i, s in zip(ref["ids"], ref["seg_pos"])}
    ref["grp_by_id"] = {i: g for i, g in zip(ref["ids"], ref["group"])}
    return ref


def load_submitted(path, id_cols, seg_cols, group_cols):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    if not rows:
        return {}, {}
    headers = list(rows[0].keys())
    norm_to_raw = {}
    for h in headers:
        norm_to_raw.setdefault(_norm(h), h)

    def pick(cands, exclude=()):
        for c in cands:
            if c in norm_to_raw and not any(e in c for e in exclude):
                return norm_to_raw[c]
        for nrm, raw in norm_to_raw.items():
            if any(c in nrm for c in cands) and not any(e in nrm for e in exclude):
                return raw
        return None

    id_c = pick(id_cols)
    seg_c = pick(seg_cols)
    grp_c = pick(group_cols)
    seg, grp = {}, {}
    if id_c is None or seg_c is None:
        return seg, grp
    for r in rows:
        cid = canon_id(r.get(id_c, ""))
        if not cid:
            continue
        try:
            s = float(r.get(seg_c))
        except (TypeError, ValueError):
            continue
        if not math.isfinite(s):
            continue
        seg[cid] = s
        if grp_c is not None:
            grp[cid] = str(r.get(grp_c, "")).strip().lower()
    return seg, grp


def pearson(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    if len(x) < 3 or np.std(x) == 0 or np.std(y) == 0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def check_subjects_and_values(seg, ref, val_tol, corr_min, cover, match, eps=1e-3):
    """Pillar 1: coverage, non-constant, per-subject positive-edge segregation matches the
    reference. An all-edges submission (~0.55 per subject vs ~0.37) fails the absolute match."""
    ref_ids = set(ref["ids"])
    matched = [i for i in seg if i in ref_ids]
    coverage = len(matched) / max(1, len(ref_ids))
    assert coverage >= cover, (
        f"segregation.csv covers only {coverage:.1%} of the {len(ref_ids)} real participants "
        f"(need >= {cover:.0%}). Fabricated or missing participant ids.")
    sub = [seg[i] for i in matched]
    assert statistics.pstdev(sub) > eps, (
        "submitted segregation is constant across participants -- not computed per subject")
    refv = [ref["by_id"][i] for i in matched]
    close = sum(1 for a, b in zip(sub, refv) if abs(a - b) <= val_tol)
    frac = close / max(1, len(matched))
    assert frac >= match, (
        f"only {frac:.1%} of matched participants have system segregation within {val_tol} of "
        f"the positive-edge reference (need >= {match:.0%}). The per-subject values are not the "
        f"real positive-edge quantities -- an all-edges run inflates each subject to ~0.55.")
    rc = pearson(sub, refv)
    assert not math.isfinite(rc) or rc >= corr_min, (
        f"submitted per-participant segregation does not track the reference (cross-subject "
        f"r={rc:.3f} < {corr_min}); the values were not computed from the real connectomes.")
    return matched


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
