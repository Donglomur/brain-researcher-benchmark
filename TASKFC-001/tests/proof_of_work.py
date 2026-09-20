"""Reusable proof-of-work helpers for TASKFC-001 (see PROOF_OF_WORK_SPEC.md).

A passing submission must be impossible to produce without running the real analysis on the
real 10 language-localizer subjects: the per-subject RAW task-state FC AND the per-subject
BACKGROUND FC (residuals after regressing the task-evoked response) must be the REAL values
for the pinned subjects; the group summaries must recompute from those rows; and the
discriminating raw>background inflation must match the held-out reference. Background FC is
off the naive path -- an agent that only correlated the raw time series cannot produce that
column or the ~0.46 background mean.
"""
import csv
import json
import math
import re
import statistics
from pathlib import Path

import numpy as np


def canon_id(s):
    """sub-01 / sub01 / 01 / 1 -> '1' (the digit run, leading zeros stripped)."""
    d = re.sub(r"\D", "", str(s)).lstrip("0")
    return d


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def load_reference(path):
    z = np.load(path, allow_pickle=True)
    ref = {
        "ids": [canon_id(x) for x in z["ref_ids"]],
        "raw": np.asarray(z["ref_raw"], float),
        "bg": np.asarray(z["ref_bg"], float),
        "stats": json.loads(str(z["ref_stats"])),
    }
    ref["raw_by_id"] = {i: float(v) for i, v in zip(ref["ids"], ref["raw"])}
    ref["bg_by_id"] = {i: float(v) for i, v in zip(ref["ids"], ref["bg"])}
    return ref


def _pick(headers, cands, avoid=()):
    norm_to_raw = {}
    for h in headers:
        norm_to_raw.setdefault(_norm(h), h)
    for c in cands:
        if c in norm_to_raw:
            return norm_to_raw[c]
    for nrm, raw in norm_to_raw.items():
        if any(c in nrm for c in cands) and not any(x in nrm for x in avoid):
            return raw
    return None


def load_submitted(path):
    """Return {canon_id: (raw, background_or_None)} from the submitted connectivity.csv."""
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    if not rows:
        return {}, None, None
    headers = list(rows[0].keys())
    id_c = _pick(headers, ("subject", "subjectid", "subid", "participant", "id"))
    # background column first (more specific), so the raw column doesn't swallow it
    bg_c = _pick(headers, ("backgroundconnectivity", "background", "backgroundfc",
                           "residualconnectivity", "residualfc", "taskregressed",
                           "intrinsicconnectivity", "backgroundr", "bgconnectivity", "bgfc"))
    raw_c = _pick(headers, ("connectivity", "rawconnectivity", "taskstateconnectivity",
                            "rawfc", "fc", "correlation", "coupling", "connectivityraw"),
                  avoid=("background", "residual", "intrinsic", "taskregressed"))
    out = {}
    for r in rows:
        cid = canon_id(r.get(id_c, "")) if id_c else ""
        if not cid:
            continue
        try:
            rawv = float(r.get(raw_c)) if raw_c else float("nan")
        except (TypeError, ValueError):
            rawv = float("nan")
        try:
            bgv = float(r.get(bg_c)) if bg_c else None
        except (TypeError, ValueError):
            bgv = None
        out[cid] = (rawv, bgv)
    return out, raw_c, bg_c


def fisher_mean(vals):
    v = np.clip(np.asarray([x for x in vals if x is not None and math.isfinite(x)], float),
                -0.999, 0.999)
    if v.size == 0:
        return float("nan")
    return float(np.tanh(np.mean(np.arctanh(v))))


def coverage(sub_ids, ref_ids):
    return sum(1 for i in ref_ids if i in sub_ids) / max(1, len(ref_ids))


def per_subject_match(sub_map, ref_by_id, ref_ids, idx, val_tol):
    matched = [i for i in ref_ids if i in sub_map]
    if not matched:
        return 0.0, 0
    ok = 0
    for i in matched:
        v = sub_map[i][idx]
        if v is not None and math.isfinite(v) and abs(v - ref_by_id[i]) <= val_tol:
            ok += 1
    return ok / len(matched), len(matched)


def cross_corr(sub_map, ref_by_id, ref_ids, idx):
    matched = [i for i in ref_ids if i in sub_map and sub_map[i][idx] is not None
               and math.isfinite(sub_map[i][idx])]
    if len(matched) < 3:
        return float("nan")
    a = [sub_map[i][idx] for i in matched]
    b = [ref_by_id[i] for i in matched]
    if np.std(a) == 0 or np.std(b) == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def nonconstant(sub_map, idx, eps=1e-6):
    vals = [sub_map[i][idx] for i in sub_map
            if sub_map[i][idx] is not None and math.isfinite(sub_map[i][idx])]
    return len(vals) >= 3 and statistics.pstdev(vals) > eps


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
