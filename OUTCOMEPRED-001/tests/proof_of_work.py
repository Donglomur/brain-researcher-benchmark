"""Reusable proof-of-work helpers for OUTCOMEPRED-001 (see PROOF_OF_WORK_SPEC.md).

Single-value task whose honest headline is a NULL (upcoming outcome not decodable above chance in
a pre-feedback window). A null is guessable, so the grader (a) validates the neutral per-fold
accuracy table (both a naive and an honest run produce one accuracy per CV fold), (b) requires the
headline to sit in the at-chance band, and (c) requires the discriminating POSITIVE CONTROL the
honest analysis volunteers -- a window that reads the delivered feedback decodes the outcome
near-perfectly (~0.99). The positive control both proves the pipeline works (so the null is not a
broken decoder) and shows the near-perfect number comes from reading feedback, not prediction.
This scopes the null to the pre-feedback window (R2 hedge), not a general claim about encoding.
"""
import csv, json, math, re, statistics
from pathlib import Path
import numpy as np


def load_reference(path):
    z = np.load(path, allow_pickle=True)
    out = {
        "fold_acc": np.asarray(z["ref_fold_acc"], dtype=float),
        "fold_acc_post": np.asarray(z["ref_fold_acc_post"], dtype=float),
        "stats": json.loads(str(z["ref_stats"])),
    }
    if "ref_window_acc" in z.files:
        out["window_acc"] = np.asarray(z["ref_window_acc"], dtype=float)
        out["window_starts"] = np.asarray(z["ref_window_starts"], dtype=float)
    return out


def load_window_curve(path):
    """Return (starts, accuracy) from decoding_vs_window.csv (the time-resolved decoding profile:
    accuracy for a fixed-width spike-count window at successive latencies relative to feedback)."""
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    if not rows:
        return None
    headers = list(rows[0].keys())
    norm = {}
    for h in headers:
        norm.setdefault(_norm(h), h)

    def pick(cands, avoid=()):
        for c in cands:
            if c in norm:
                return norm[c]
        for nrm, raw in norm.items():
            if any(c in nrm for c in cands) and not any(x in nrm for x in avoid):
                return raw
        return None

    s_col = pick(("windowstarts", "windowstart", "start", "latency", "windowcenter", "center",
                  "time", "windowonset", "onset"), avoid=("end", "acc"))
    a_col = pick(("accuracy", "acc", "score"), avoid=("std", "chance", "start", "end", "time"))
    if s_col is None or a_col is None:
        return None
    ss, aa = [], []
    for r in rows:
        try:
            s = float(r[s_col]); a = float(r[a_col])
        except (TypeError, ValueError):
            continue
        if not (math.isfinite(s) and math.isfinite(a)):
            continue
        ss.append(s); aa.append(a / 100.0 if a > 1.5 else a)
    if len(ss) < 3:
        return None
    order = np.argsort(ss)
    return np.asarray(ss, float)[order], np.asarray(aa, float)[order]


def window_shape_corr(sub_s, sub_a, ref_s, ref_a):
    """Pearson corr of the submitted profile vs the reference on the reference latency grid
    (magnitude-invariant, so it proves a real decoder ran without matching absolute levels)."""
    lo = max(sub_s.min(), ref_s.min()); hi = min(sub_s.max(), ref_s.max())
    grid = ref_s[(ref_s >= lo - 1e-9) & (ref_s <= hi + 1e-9)]
    if len(grid) < 3:
        return float("nan"), 0
    so = np.interp(grid, sub_s, sub_a); ro = np.interp(grid, ref_s, ref_a)
    if np.std(so) < 1e-9 or np.std(ro) < 1e-9:
        return float("nan"), len(grid)
    return float(np.corrcoef(so, ro)[0, 1]), len(grid)


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def load_submitted_folds(path):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    if not rows:
        return None
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

    acc_c = pick(("accuracy", "acc", "score", "cvaccuracy", "foldaccuracy"),
                 avoid=("std", "chance", "train", "post", "control"))
    fold_c = pick(("fold", "foldindex", "foldid", "split", "index", "foldnumber"))
    if acc_c is None:
        return None
    out = []
    for r in rows:
        try:
            a = float(r.get(acc_c))
        except (TypeError, ValueError):
            continue
        if not math.isfinite(a):
            continue
        a = a / 100.0 if a > 1.5 else a
        key = None
        if fold_c is not None:
            try:
                key = float(r.get(fold_c))
            except (TypeError, ValueError):
                key = None
        out.append((key, a))
    if not out:
        return None
    if all(k is not None for k, _ in out):
        out.sort(key=lambda kv: kv[0])
    return [a for _, a in out]


def check_null_folds(folds, null_band, n_folds_ref, eps=1e-9):
    """The submitted per-fold table must be a real cross-validation whose mean lands at chance."""
    assert folds is not None and len(folds) >= 3, (
        "folds.csv could not be parsed into a per-fold accuracy table (one accuracy per CV fold)")
    assert abs(len(folds) - n_folds_ref) <= 1, (
        f"submitted {len(folds)} folds; the analysis uses {n_folds_ref}-fold CV")
    m = float(np.mean(folds))
    lo, hi = null_band
    assert lo <= m <= hi, (
        f"mean of the submitted per-fold accuracies ({m:.3f}) is outside the at-chance band "
        f"[{lo:.2f}, {hi:.2f}]. A value near 0.99 comes from a window that spans/follows feedback "
        f"and reads the delivered outcome, not from predicting the upcoming outcome.")
    assert statistics.pstdev([float(x) for x in folds]) > eps, (
        "submitted per-fold accuracies are constant across folds -- not a real cross-validation")
    for a in folds:
        assert 0.15 <= a <= 0.75, (
            f"a submitted per-fold accuracy ({a:.3f}) is implausible for an at-chance pre-feedback "
            f"decoder; the folds are not the real cross-validation")
    return m


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
                            return fv / 100.0 if fv > 1.5 and fv <= 100 else fv
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    return None


def find_number_raw(obj, key_patterns, exclude=None):
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


def find_max_accuracy(obj):
    """The largest accuracy-like number anywhere in the reported JSON (a volunteered positive
    control is typically reported as a second, near-perfect accuracy)."""
    best = None
    stack = [obj]
    while stack:
        cur = stack.pop(0)
        if isinstance(cur, dict):
            for k, v in cur.items():
                nk = _norm(k)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    if re.search(r"acc|decod|score|control|revealed|post|feedback", nk) and \
                       not re.search(r"chance|std|window|seed|nfold|ntrial|nunit", nk):
                        fv = float(v)
                        fv = fv / 100.0 if fv > 1.5 and fv <= 100 else fv
                        if math.isfinite(fv) and (best is None or fv > best):
                            best = fv
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    return best
