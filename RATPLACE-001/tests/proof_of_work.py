"""Reusable proof-of-work helpers for RATPLACE-001's grader.

A passing submission must be IMPOSSIBLE to produce without running the real Skaggs analysis on the
real DANDI 001754 Rat-1 baseline-track CA1 units. These helpers validate the SUBMITTED per-unit
table -- a NEUTRAL intermediate BOTH a naive (raw-only) and an honest (bias-corrected) analysis
produce: the pinned per-unit RAW Skaggs spatial information -- against a reference
(tests/reference.npz, held out of the agent CONTAINER but PUBLIC in this repo (burned) -- a real
eval needs fresh tasks / a server-side reference), then recompute the raw population mean FROM the
rows and cross-check it. The bias correction itself is NOT required by the table (that would cue the
lever); it is graded separately as an un-cued OR-escape.
"""
import csv
import math
import re
import statistics

import numpy as np


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def canon_id(s):
    """Canonical unit id = the integer unit_index as a string (leading zeros stripped)."""
    d = re.sub(r"\D", "", str(s)).lstrip("0")
    return d if d != "" else "0"


def load_reference(path):
    import json
    z = np.load(path, allow_pickle=True)
    ids = [canon_id(x) for x in z["ref_ids"]]
    ref = {
        "ids": ids,
        "raw": np.asarray(z["ref_raw"], dtype=float),
        "null": np.asarray(z["ref_null"], dtype=float),
        "corr": np.asarray(z["ref_corr"], dtype=float),
        "nspikes": np.asarray(z["ref_nspikes"], dtype=float),
        "stats": json.loads(str(z["ref_stats"])),
    }
    ref["by_id"] = {i: float(r) for i, r in zip(ids, ref["raw"])}
    return ref


def load_submitted(path, id_cols, raw_cols):
    """Return {canon_id: raw_skaggs} plus the raw list. Tolerant column matching; the RAW column is
    kept away from any 'corrected'/'shuffle'/'null' column."""
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    if not rows:
        return {}, []
    headers = list(rows[0].keys())
    norm_to_raw = {}
    for h in headers:
        norm_to_raw.setdefault(_norm(h), h)

    def pick(cands, avoid=()):
        # exact-ish first, avoiding disallowed substrings
        for c in cands:
            if c in norm_to_raw and not any(a in c for a in avoid):
                return norm_to_raw[c]
        for nrm, raw in norm_to_raw.items():
            if any(a in nrm for a in avoid):
                continue
            if any(c in nrm for c in cands):
                return raw
        return None

    id_c = pick(id_cols)
    raw_c = pick(raw_cols, avoid=("correct", "debias", "shuffle", "null", "adjust", "z", "p95", "sig"))
    submitted, raw_list = {}, []
    if id_c is None or raw_c is None:
        return submitted, raw_list
    for r in rows:
        cid = canon_id(r.get(id_c, ""))
        try:
            v = float(r.get(raw_c))
        except (TypeError, ValueError):
            continue
        if not math.isfinite(v):
            continue
        submitted[cid] = v
        raw_list.append(v)
    return submitted, raw_list


def check_units_and_values(submitted, ref, raw_tol=0.06, cover=0.90, corr_min=0.95,
                           val_match=0.80, eps=1e-4):
    """Pillar 1. Raise AssertionError unless the per-unit raw Skaggs table is real per-unit work.

    (a) coverage of the reference units by real unit id; (b) non-constant guard;
    (c) fabrication teeth: cross-unit Pearson corr(submitted raw, reference raw) >= `corr_min`
        AND >= `val_match` of matched units within `raw_tol` (raw Skaggs is deterministic given the
        real occupancy + spikes -- impossible to fake).
    """
    ref_ids = set(ref["ids"])
    matched = [i for i in submitted if i in ref_ids]
    coverage = len(matched) / max(1, len(ref_ids))
    assert coverage >= cover, (
        f"submitted spatial_information.csv covers only {coverage:.1%} of the {len(ref_ids)} real "
        f"CA1 units by unit_index (need >= {cover:.0%}). Fabricated or missing units.")

    sub = [submitted[i] for i in matched]
    ref_raw = [ref["by_id"][i] for i in matched]
    assert statistics.pstdev(sub) > eps, \
        "submitted per-unit spatial information is constant across units -- not computed per unit"

    rc = float(np.corrcoef(sub, ref_raw)[0, 1])
    assert math.isfinite(rc) and rc >= corr_min, (
        f"submitted per-unit raw Skaggs information does not track the reference (cross-unit "
        f"r={rc:.3f} < {corr_min}). The values were not computed from the real occupancy + spikes.")

    close = sum(1 for a, b in zip(sub, ref_raw) if abs(a - b) <= raw_tol)
    frac = close / max(1, len(matched))
    assert frac >= val_match, (
        f"only {frac:.1%} of matched units have raw Skaggs within {raw_tol} of the reference "
        f"(need >= {val_match:.0%}); the per-unit values are not the real ones.")
    return matched


def recompute_raw_mean(submitted, matched):
    vals = [submitted[i] for i in matched]
    return float(np.mean(vals)) if vals else float("nan")


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
                        fv = float(v)
                        if math.isfinite(fv):
                            return fv
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    return None
