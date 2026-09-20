"""Reusable proof-of-work helpers for RESTCONN-001 (see PROOF_OF_WORK_SPEC.md).

RESTCONN-001 is a SINGLE-SUBJECT, single-value task (one correlation r and its
significance verdict). A single scalar can be guessed, so — following the QSMDIPOLE-001
model — a passing submission must also carry the finest validated intermediate the analysis
naturally produces: the two extracted ROI mean BOLD time series (R DMN and Cereb). These are
held-out-referenced (tests/reference.npz, built from the oracle run and never shipped to the
agent). The grader validates the submitted time series against the reference, recomputes the
correlation AND the temporal-autocorrelation-corrected effective degrees of freedom FROM the
submitted rows, and grades the significance verdict as numbers. The honest quantity a naive
run cannot produce: the near-0.87 lag-1 autocorrelation collapses the effective sample size
from 176 to ~25, so the correlation is NOT significant — a value that can only be obtained by
extracting the real autocorrelated series, not by reporting scipy's df=n-2 p-value.
"""
import csv
import json
import math
import re
import statistics
from pathlib import Path

import numpy as np
from scipy import stats


def load_reference(path):
    z = np.load(path, allow_pickle=True)
    return {
        "a": np.asarray(z["ref_ts_a"], dtype=float),
        "b": np.asarray(z["ref_ts_b"], dtype=float),
        "region_a": str(z["ref_region_a"]),
        "region_b": str(z["ref_region_b"]),
        "stats": json.loads(str(z["ref_stats"])),
    }


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def load_submitted_timeseries(path, a_cands, b_cands):
    """Return (a, b) numpy arrays parsed from the submitted timeseries.csv, ordered by the
    time/index column if present. Tolerant column matching on normalised names."""
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
            if any(c in nrm for c in cands) and not any(x in nrm for x in avoid):
                return raw
        return None

    ac = pick(a_cands, avoid=("cereb", "cerebell"))
    bc = pick(b_cands)
    tc = pick(("t", "time", "tr", "volume", "index", "frame", "timepoint"))
    if ac is None or bc is None or ac == bc:
        return None, None

    def order_key(r):
        if tc is None:
            return 0
        try:
            return float(r.get(tc))
        except (TypeError, ValueError):
            return 0

    srows = sorted(rows, key=order_key) if tc is not None else rows
    a, b = [], []
    for r in srows:
        try:
            av = float(r.get(ac)); bv = float(r.get(bc))
        except (TypeError, ValueError):
            continue
        if math.isfinite(av) and math.isfinite(bv):
            a.append(av); b.append(bv)
    return np.asarray(a, float), np.asarray(b, float)


def _abscorr(x, y):
    m = min(len(x), len(y))
    if m < 3 or np.std(x[:m]) == 0 or np.std(y[:m]) == 0:
        return float("nan")
    return abs(float(np.corrcoef(x[:m], y[:m])[0, 1]))


def check_timeseries_matches_reference(a, b, ref, ts_corr=0.90, len_tol=8):
    """Pillar 1. The submitted ROI time series must BE the real extracted series (they
    correlate with the held-out reference across time), not a fabricated or constant column."""
    assert a is not None and b is not None and len(a) >= 3 and len(b) >= 3, (
        "timeseries.csv could not be parsed into two ROI mean time series (columns for "
        f"'{ref['region_a']}' and '{ref['region_b']}')")
    n_ref = int(ref["stats"]["n"])
    assert abs(len(a) - n_ref) <= len_tol and abs(len(b) - n_ref) <= len_tol, (
        f"submitted time series length ({len(a)}) does not match the {n_ref} real volumes")
    assert statistics.pstdev(a.tolist()) > 1e-9 and statistics.pstdev(b.tolist()) > 1e-9, (
        "a submitted ROI time series is constant across volumes -- not a real BOLD extraction")
    ca = _abscorr(a, ref["a"]); cb = _abscorr(b, ref["b"])
    assert math.isfinite(ca) and ca >= ts_corr, (
        f"the submitted '{ref['region_a']}' time series does not track the held-out reference "
        f"(|r|={ca:.3f} < {ts_corr}); it was not extracted from the real MSDL/ADHD-200 data.")
    assert math.isfinite(cb) and cb >= ts_corr, (
        f"the submitted '{ref['region_b']}' time series does not track the held-out reference "
        f"(|r|={cb:.3f} < {ts_corr}); it was not extracted from the real MSDL/ADHD-200 data.")
    # guard against a swapped/duplicated pair: each column must match its OWN reference better
    # than the other reference column.
    assert ca >= _abscorr(a, ref["b"]) and cb >= _abscorr(b, ref["a"]), (
        "the two submitted time series appear swapped or duplicated relative to the reference "
        "R DMN / Cereb columns")
    return ca, cb


def _acf(x, k):
    x = np.asarray(x, float); x = x - x.mean()
    d = np.dot(x, x)
    return float(np.dot(x[:len(x) - k], x[k:]) / d) if d > 0 else 0.0


def eff_df_ar1(x, y):
    rx, ry = _acf(x, 1), _acf(y, 1)
    n = min(len(x), len(y))
    denom = (1 + rx * ry)
    return (n * (1 - rx * ry) / denom if denom != 0 else float(n)), rx, ry


def eff_df_bartlett(x, y):
    n = min(len(x), len(y))
    s = sum(_acf(x, k) * _acf(y, k) for k in range(1, n // 4 + 1))
    return n / (1 + 2 * s)


def p_from_neff(r, neff):
    df = neff - 2
    if df <= 1:
        return 1.0
    t = r * math.sqrt(df / max(1 - r ** 2, 1e-12))
    return float(2 * stats.t.sf(abs(t), df))


def pearson(x, y):
    m = min(len(x), len(y))
    if m < 3 or np.std(x[:m]) == 0 or np.std(y[:m]) == 0:
        return float("nan")
    return float(np.corrcoef(x[:m], y[:m])[0, 1])


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


def find_significant_flag(obj):
    stack = [(None, obj)]
    out = []
    while stack:
        k, v = stack.pop()
        if isinstance(v, dict):
            stack.extend(v.items())
        elif isinstance(v, list):
            stack.extend((k, x) for x in v)
        elif k and "signif" in _norm(k):
            if isinstance(v, bool):
                out.append(v)
            elif isinstance(v, str):
                s = v.strip().lower()
                if s in ("true", "yes", "significant", "sig"):
                    out.append(True)
                elif s in ("false", "no", "not significant", "ns", "n.s.", "nonsignificant",
                           "non-significant", "not_significant"):
                    out.append(False)
    return out
