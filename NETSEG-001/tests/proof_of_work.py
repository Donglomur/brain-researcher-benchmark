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
    # seg_clip = a second defensible positive-edge convention (negatives clipped to 0 then
    # averaged) alongside seg_pos (negatives excluded from the mean). Both are legitimate
    # positive-edge system segregation; they differ by ~0.10 in magnitude (cross-subject
    # r~0.96), so the grader accepts a per-subject match to EITHER.
    seg_clip = z["ref_seg_clip"] if "ref_seg_clip" in z.files else z["ref_seg_pos"]
    ref = {
        "ids": [canon_id(x) for x in z["ref_ids"]],
        "seg_pos": np.asarray(z["ref_seg_pos"], dtype=float),
        "seg_clip": np.asarray(seg_clip, dtype=float),
        "seg_all": np.asarray(z["ref_seg_all"], dtype=float),
        "group": [str(x) for x in z["ref_group"]],
        "age": np.asarray(z["ref_age"], dtype=float),
        "stats": json.loads(str(z["ref_stats"])),
    }
    ref["by_id"] = {i: float(s) for i, s in zip(ref["ids"], ref["seg_pos"])}
    ref["by_id_clip"] = {i: float(s) for i, s in zip(ref["ids"], ref["seg_clip"])}
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
    """Pillar 1: coverage, non-constant, and per-subject positive-edge segregation that tracks
    the reference. The PRIMARY authenticity teeth is the cross-subject correlation with the
    reference (a fabricated / shuffled / random column gives r~0); the absolute match is graded
    against EITHER of the two defensible positive-edge conventions (negatives-excluded ~0.37 or
    negatives-clipped-to-0 ~0.47), so a correct solve is not failed for a legitimate convention
    choice while a fabrication still fails the correlation."""
    ref_ids = set(ref["ids"])
    matched = [i for i in seg if i in ref_ids]
    coverage = len(matched) / max(1, len(ref_ids))
    assert coverage >= cover, (
        f"segregation.csv covers only {coverage:.1%} of the {len(ref_ids)} real participants "
        f"(need >= {cover:.0%}). Fabricated or missing participant ids.")
    sub = [seg[i] for i in matched]
    assert statistics.pstdev(sub) > eps, (
        "submitted segregation is constant across participants -- not computed per subject")
    refv = [ref["by_id"][i] for i in matched]           # negatives-excluded convention
    refc = [ref["by_id_clip"][i] for i in matched]      # negatives-clipped-to-0 convention
    # cross-subject correlation is the real teeth (both conventions correlate ~1 with a real
    # per-subject solve; a fabrication does not)
    rc = max(pearson(sub, refv), pearson(sub, refc))
    assert math.isfinite(rc) and rc >= corr_min, (
        f"submitted per-participant segregation does not track the reference (cross-subject "
        f"r={rc:.3f} < {corr_min}); the values were not computed from the real connectomes "
        f"(a shuffled or random column fails here).")
    # absolute match against EITHER defensible positive-edge convention
    close = sum(1 for a, b, c in zip(sub, refv, refc)
                if min(abs(a - b), abs(a - c)) <= val_tol)
    frac = close / max(1, len(matched))
    assert frac >= match, (
        f"only {frac:.1%} of matched participants have system segregation within {val_tol} of "
        f"either positive-edge reference convention (need >= {match:.0%}). The per-subject "
        f"values are not the real positive-edge quantities.")
    return matched


def find_number(obj, key_patterns, exclude=None):
    got = collect_numbers(obj, key_patterns, exclude)
    return got[0] if got else None


def collect_numbers(obj, key_patterns, exclude=None):
    """Collect ALL finite numbers whose (normalised) key matches any pattern and no exclusion.

    Used where a submission may legitimately report several related numbers (e.g. a signed
    cohort mean AND a positive-edge cohort mean): the caller picks the one consistent with the
    quantity being graded rather than being trapped by whichever appears first.
    """
    exc = [re.compile(e) for e in (exclude or [])]
    pats = [re.compile(p) for p in key_patterns]
    out = []
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
                                out.append(fv)
                        except Exception:
                            pass
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    return out
