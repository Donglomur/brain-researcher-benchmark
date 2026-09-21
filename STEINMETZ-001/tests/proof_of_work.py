"""Reusable proof-of-work helpers for STEINMETZ-001 (see PROOF_OF_WORK_SPEC.md).

STEINMETZ-001 is a single-value reproduction task (one cross-validated decoding accuracy). A lone
scalar is guessable, so a passing submission must also carry the finest neutral intermediate the
analysis naturally produces -- the per-fold cross-validated accuracies -- and the headline must lie
in a held-out band that ONLY the honest pipeline reaches (QSMDIPOLE model). The per-fold table is
NEUTRAL: any 5-fold cross-validation (naive or honest) produces one accuracy per fold. The
held-out reference (tests/reference.npz, built from the oracle run, never shipped to the agent)
stores the honest per-fold accuracies + the discriminating statistics.

The honest quantity a naive run cannot produce: a strictly pre-movement window scored with
blocked (contiguous) cross-validation reaches ~0.72; a peri-movement window with random k-fold
reads out the movement already underway (plus CV leakage) and reports ~0.95. Only the honest
method lands the headline (and the per-fold mean) in the ~0.72 band.
"""
import csv, json, math, re, statistics
from pathlib import Path
import numpy as np


def load_reference(path):
    z = np.load(path, allow_pickle=True)
    return {
        "fold_idx": np.asarray(z["ref_fold_idx"], dtype=float),
        "fold_acc": np.asarray(z["ref_fold_acc"], dtype=float),
        "stats": json.loads(str(z["ref_stats"])),
    }


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def load_submitted_folds(path):
    """Return the per-fold accuracies ordered by fold index, parsed from folds.csv. Tolerant
    column matching. Accepts accuracies as fractions (0..1) or percentages (50..100)."""
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

    acc_c = pick(("accuracy", "acc", "score", "cvaccuracy", "testaccuracy", "foldaccuracy"),
                 avoid=("std", "chance", "train"))
    fold_c = pick(("fold", "foldindex", "foldid", "k", "split", "index", "foldnumber"))
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


def check_folds_match_reference(folds, ref, mean_band, per_fold_tol=0.12, min_frac=0.6,
                                fold_std_min=0.015, fold_std_max=0.16, eps=1e-6):
    """Pillar 1+2. The submitted per-fold accuracies must be a real cross-validation result whose
    mean lands in the held-out honest band, whose per-fold spread is realistic (a table clustered at
    the guessable headline is rejected), and whose sorted per-fold accuracies track the honest
    reference. A fabricated table that merely averages to the headline, a constant table, or a
    clustered near-constant table all fail.

    No held-out reference value (the honest mean, the naive inflated value, or the reference fold
    accuracies) is ever printed in an assertion message -- the grader must not leak the answer it
    checks against."""
    assert folds is not None and len(folds) >= 3, (
        "folds.csv could not be parsed into a per-fold accuracy table (one accuracy per CV fold)")
    ref_folds = ref["fold_acc"]
    assert abs(len(folds) - len(ref_folds)) <= 1, (
        f"submitted {len(folds)} folds; this analysis uses {len(ref_folds)}-fold cross-validation")
    m = float(np.mean(folds))
    lo, hi = mean_band
    assert lo <= m <= hi, (
        f"mean of the submitted per-fold accuracies ({m:.3f}) is outside the honest band "
        f"[{lo:.2f}, {hi:.2f}] that only a strictly pre-movement, non-leaky decoder reaches. A "
        f"peri-movement window scored with random k-fold decodes movement execution with "
        f"cross-validation leakage and lands well above this band.")
    sd = statistics.pstdev([float(x) for x in folds])
    assert sd > eps, (
        "submitted per-fold accuracies are constant across folds -- not a real cross-validation")
    assert fold_std_min <= sd <= fold_std_max, (
        f"the spread of the submitted per-fold accuracies (SD {sd:.3f}) is not that of a real "
        f"cross-validation on this many trials (expected roughly [{fold_std_min:.3f}, "
        f"{fold_std_max:.3f}]). A table clustered at the headline value, or one with implausible "
        f"scatter, is not the real per-fold cross-validation this task reproduces.")
    a = np.sort(np.asarray(folds, float))
    b = np.sort(ref_folds.astype(float))
    k = min(len(a), len(b))
    close = int(np.sum(np.abs(a[:k] - b[:k]) <= per_fold_tol))
    frac = close / k
    assert frac >= min_frac, (
        f"only {frac:.0%} of the submitted per-fold accuracies match the held-out reference "
        f"cross-validation within tolerance (need >= {min_frac:.0%}); the per-fold table is not the "
        f"real cross-validation this task reproduces.")
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
