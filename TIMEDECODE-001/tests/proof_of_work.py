"""Reusable proof-of-work helpers for TIMEDECODE-001 (single-trial MEG modality decoding).

A passing submission must be impossible to produce without running the real trial-grouped
cross-validation on the real pooled (trial x time) MEG samples: the reported accuracy must be
the honest trial-grouped value (materially below the leaky random-k-fold value), it must
recompute from the submitted per-fold rows, and the per-fold accuracies must themselves sit in
the trial-grouped (leakage-free) band, not the inflated random-k-fold band.
"""
import csv
import json
import math
import os
import re
import statistics
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
REF_PATH = Path(os.environ.get("TIMEDECODE_REFERENCE",
                               str(Path(__file__).resolve().parent / "reference.npz")))


def load_reference():
    d = np.load(REF_PATH, allow_pickle=False)
    out = {"fold_acc": np.asarray(d["ref_fold_acc"], float),
           "stats": json.loads(str(d["ref_stats"]))}
    if "ref_timecourse" in d.files:
        out["timecourse"] = np.asarray(d["ref_timecourse"], float)
        out["time_s"] = np.asarray(d["ref_time_s"], float)
    return out


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def load_results():
    for name in ("decoding_results.json", "results.json"):
        p = OUT / name
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
    return {}


def headline_accuracy(res):
    """The single reported cross-validated accuracy (never a labelled leaky/random one)."""
    if not isinstance(res, dict):
        return None
    for k, v in res.items():
        if k.lower() == "accuracy" and isinstance(v, (int, float)) and not isinstance(v, bool):
            return float(v)
    for k, v in res.items():
        kl = _norm(k)
        if (isinstance(v, (int, float)) and not isinstance(v, bool) and "acc" in kl
                and not any(t in kl for t in ("random", "kfold", "leak", "reference", "chance",
                                              "naive", "perfold", "fold"))):
            return float(v)
    return None


def reported_leaky(res):
    out = []
    if isinstance(res, dict):
        for k, v in res.items():
            kl = _norm(k)
            if (isinstance(v, (int, float)) and not isinstance(v, bool)
                    and any(t in kl for t in ("random", "kfold", "leaky"))
                    and "acc" in kl and "chance" not in kl):
                out.append(float(v))
    return out


def load_per_fold():
    """Return (accuracies, n_test_samples_list, n_test_trials_list_or_None)."""
    p = OUT / "per_fold.csv"
    assert p.exists(), "missing required output per_fold.csv"
    rows = list(csv.DictReader(open(p, encoding="utf-8")))
    assert rows, "per_fold.csv has no data rows"
    hdr = list(rows[0].keys())
    acc_col = next((h for h in hdr if ("acc" in _norm(h) or "score" in _norm(h))
                    and "sample" not in _norm(h)), None)
    assert acc_col, f"per_fold.csv has no accuracy column (columns: {hdr})"
    ns_col = next((h for h in hdr if "sample" in _norm(h) or _norm(h) in ("ntest", "n")), None)
    nt_col = next((h for h in hdr if "trial" in _norm(h)), None)
    accs, nss, nts = [], [], []
    for r in rows:
        try:
            a = float(r[acc_col])
        except (TypeError, ValueError):
            continue
        if not math.isfinite(a):
            continue
        accs.append(a / 100.0 if a > 1.5 else a)
        if ns_col:
            try:
                nss.append(float(r[ns_col]))
            except (TypeError, ValueError):
                nss.append(float("nan"))
        if nt_col:
            try:
                nts.append(float(r[nt_col]))
            except (TypeError, ValueError):
                nts.append(float("nan"))
    return np.asarray(accs, float), (nss if ns_col else None), (nts if nt_col else None)


def load_timecourse():
    """Return (time_s, accuracy) arrays from the required decoding_timecourse.csv.

    The per-time-sample decoding accuracy in the 0.05-0.45 s window: at a single time
    sample every trial contributes one example, so this profile is the same whatever the
    pooled-sample fold scheme is -- a neutral record that a real decoder was actually run.
    """
    p = OUT / "decoding_timecourse.csv"
    assert p.exists(), "missing required output decoding_timecourse.csv"
    rows = list(csv.DictReader(open(p, encoding="utf-8")))
    assert rows, "decoding_timecourse.csv has no data rows"
    hdr = list(rows[0].keys())
    t_col = next((h for h in hdr if "time" in _norm(h) or _norm(h) in ("t", "ts", "sample")), None)
    a_col = next((h for h in hdr if ("acc" in _norm(h) or "score" in _norm(h))
                  and "time" not in _norm(h)), None)
    assert t_col and a_col, f"decoding_timecourse.csv needs time and accuracy columns (columns: {hdr})"
    ts, accs = [], []
    for r in rows:
        try:
            t = float(r[t_col])
            a = float(r[a_col])
        except (TypeError, ValueError):
            continue
        if not (math.isfinite(t) and math.isfinite(a)):
            continue
        ts.append(t)
        accs.append(a / 100.0 if a > 1.5 else a)
    order = np.argsort(ts)
    return np.asarray(ts, float)[order], np.asarray(accs, float)[order]


def timecourse_shape_corr(sub_t, sub_a, ref_t, ref_a):
    """Pearson corr of the submitted profile against the reference on the reference time grid
    (magnitude-invariant, so it proves a real decoder ran without discriminating the fold scheme)."""
    lo = max(sub_t.min(), ref_t.min())
    hi = min(sub_t.max(), ref_t.max())
    grid = ref_t[(ref_t >= lo - 1e-9) & (ref_t <= hi + 1e-9)]
    if len(grid) < 3:
        return float("nan"), 0
    sub_on = np.interp(grid, sub_t, sub_a)
    ref_on = np.interp(grid, ref_t, ref_a)
    if np.std(sub_on) < 1e-9 or np.std(ref_on) < 1e-9:
        return float("nan"), len(grid)
    return float(np.corrcoef(sub_on, ref_on)[0, 1]), len(grid)


def nonconstant(accs, eps):
    return len(accs) >= 3 and statistics.pstdev(accs.tolist()) > eps


def findings_text():
    p = OUT / "findings.md"
    return p.read_text(encoding="utf-8").lower() if p.exists() else ""
