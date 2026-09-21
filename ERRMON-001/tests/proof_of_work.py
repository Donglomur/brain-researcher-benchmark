"""Reusable proof-of-work helpers for SOMATOERD-001 (see PROOF_OF_WORK_SPEC.md).

SOMATOERD-001 is a single-subject, single-value task (one beta-ERD percentage). A lone scalar
is guessable, so -- following the RESTCONN-001 / QSMDIPOLE-001 model -- a passing submission
must also carry the finest intermediate the analysis naturally produces: the contralateral
sensorimotor beta-band power time course (percent baseline), one value per epoch time sample.
This is a NEUTRAL deliverable both a correct and a naive pipeline produce; matched to the
held-out reference (tests/reference.npz, built from the oracle run, never shipped to the
agent) it closes fabrication AND the naive shortcut without cueing the honest method. The
grader validates the submitted time course against the reference, recomputes the window ERD
FROM the submitted curve, and grades the ERD as a number (a decrease of ~-17.7%). The naive
evoked-power curve is a large POSITIVE excursion (+444% in-window) essentially uncorrelated
with the induced reference, so it fails at the time-course level.
"""
import csv
import json
import math
import re
import statistics
from pathlib import Path

import numpy as np


def load_reference(path):
    z = np.load(path, allow_pickle=True)
    return {
        "times": np.asarray(z["ref_times"], float),
        "tc": np.asarray(z["ref_timecourse"], float),
        "stats": json.loads(str(z["ref_stats"])),
    }


def load_reference_errmon(path):
    z = np.load(path, allow_pickle=True)
    return {
        "times": np.asarray(z["ref_times"], float),
        "error": np.asarray(z["ref_error"], float),
        "correct": np.asarray(z["ref_correct"], float),
        "stats": json.loads(str(z["ref_stats"])),
    }


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def load_submitted_timecourse(path):
    """Return (times_s, values) parsed from the submitted time-course CSV. Tolerant column
    matching: a time/index column and a beta-power/percent value column. Times given in ms
    (|t|>10) are converted to seconds."""
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    if not rows:
        return None, None
    headers = list(rows[0].keys())
    norm_to_raw = {}
    for h in headers:
        norm_to_raw.setdefault(_norm(h), h)

    def pick(cands, avoid=()):
        for c in cands:
            if c in norm_to_raw:
                return norm_to_raw[c]
        for nrm, raw in norm_to_raw.items():
            if any(c in nrm for c in cands) and not any(a in nrm for a in avoid):
                return raw
        return None

    tc_col = pick(("times", "timesec", "timems", "time", "t", "latency", "sec", "ms"),
                  avoid=("power", "erd", "percent", "beta"))
    val_col = pick(("betapowerpct", "betapower", "power", "erd", "percent", "pct", "beta",
                    "desync", "value"), avoid=())
    if tc_col is None or val_col is None or tc_col == val_col:
        # fall back: first two numeric columns
        cols = headers[:2] if len(headers) >= 2 else []
        if len(cols) < 2:
            return None, None
        tc_col, val_col = cols[0], cols[1]
    t, v = [], []
    for r in rows:
        try:
            tt = float(r.get(tc_col)); vv = float(r.get(val_col))
        except (TypeError, ValueError):
            continue
        if math.isfinite(tt) and math.isfinite(vv):
            t.append(tt); v.append(vv)
    if not t:
        return None, None
    t = np.asarray(t, float); v = np.asarray(v, float)
    order = np.argsort(t)
    t, v = t[order], v[order]
    if np.nanmax(np.abs(t)) > 10:      # milliseconds -> seconds
        t = t / 1000.0
    return t, v


def load_submitted_waveforms(path):
    """Return (times_s, error_uv, correct_uv) from the submitted FCz waveform CSV. Tolerant
    column matching: a time column plus an error-average and a correct-average column. Times
    in ms (|t|>10) are converted to seconds."""
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    if not rows:
        return None, None, None
    headers = list(rows[0].keys())
    norm_to_raw = {}
    for h in headers:
        norm_to_raw.setdefault(_norm(h), h)

    def pick(cands, avoid=()):
        for c in cands:
            if c in norm_to_raw:
                return norm_to_raw[c]
        for nrm, raw in norm_to_raw.items():
            if any(c in nrm for c in cands) and not any(a in nrm for a in avoid):
                return raw
        return None

    tcol = pick(("times", "timems", "timesec", "time", "t", "latency", "ms", "sec"),
                avoid=("error", "correct", "uv", "amp"))
    ecol = pick(("erroruv", "error", "err", "incorrect", "erroraverage", "errortrials"),
                avoid=("correct",))
    ccol = pick(("correctuv", "correct", "cor", "correctaverage", "correcttrials"),
                avoid=("incorrect", "error"))
    if tcol is None or ecol is None or ccol is None:
        return None, None, None
    t, e, c = [], [], []
    for r in rows:
        try:
            tt = float(r.get(tcol)); ee = float(r.get(ecol)); cc = float(r.get(ccol))
        except (TypeError, ValueError):
            continue
        if all(math.isfinite(x) for x in (tt, ee, cc)):
            t.append(tt); e.append(ee); c.append(cc)
    if not t:
        return None, None, None
    t = np.asarray(t, float); e = np.asarray(e, float); c = np.asarray(c, float)
    order = np.argsort(t)
    t, e, c = t[order], e[order], c[order]
    if np.nanmax(np.abs(t)) > 10:
        t = t / 1000.0
    return t, e, c


def interp_series(sub_t, sub_v, ref_t):
    """Interpolate one submitted series onto ref_t over the overlap; return (rt, sv)."""
    lo = max(sub_t.min(), ref_t.min())
    hi = min(sub_t.max(), ref_t.max())
    m = (ref_t >= lo) & (ref_t <= hi)
    rt = ref_t[m]
    if len(rt) < 10:
        return rt, np.array([])
    return rt, np.interp(rt, sub_t, sub_v)


def interp_to_ref(sub_t, sub_v, ref_t):
    """Interpolate the submitted curve onto the reference time grid over their overlap.
    Returns (ref_t_overlap, ref_v_overlap, sub_v_interp)."""
    lo = max(sub_t.min(), ref_t.min())
    hi = min(sub_t.max(), ref_t.max())
    m = (ref_t >= lo) & (ref_t <= hi)
    rt = ref_t[m]
    if len(rt) < 10:
        return rt, np.array([]), np.array([])
    sv = np.interp(rt, sub_t, sub_v)
    return rt, rt, sv


def pearson(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    m = min(len(x), len(y))
    if m < 5 or np.std(x[:m]) == 0 or np.std(y[:m]) == 0:
        return float("nan")
    return float(np.corrcoef(x[:m], y[:m])[0, 1])


def window_mean(times, values, win):
    m = (times >= win[0]) & (times <= win[1])
    if m.sum() == 0:
        return float("nan")
    return float(np.asarray(values)[m].mean())


def find_number(obj, key_patterns, exclude=None):
    exc = [re.compile(e) for e in (exclude or [])]
    pats = [re.compile(p) for p in key_patterns]
    stack = [obj]
    while stack:
        cur = stack.pop(0)
        if isinstance(cur, dict):
            for k, val in cur.items():
                nk = _norm(k)
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    if any(p.search(nk) for p in pats) and not any(e.search(nk) for e in exc):
                        fv = float(val)
                        if math.isfinite(fv):
                            return fv
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    return None
