"""Reusable proof-of-work helpers for the single-subject Haxby decoding tasks
(VTDECODE-001 / OBJCAT-001). See PROOF_OF_WORK_SPEC.md.

A passing submission must be impossible to produce without running the real
cross-validated decoding on the real subject: the per-fold (leave-one-run-out)
held-out accuracies must be the REAL per-run numbers, the headline must recompute
from those rows, and the reported headline must be the honest run-blocked / nested
estimate -- not the leakage-inflated random-fold / select-once value.

The intermediate that makes the single headline non-guessable is the per-fold
accuracy breakdown: a leaky pipeline produces a different fold structure and
different per-fold numbers, so it cannot reproduce the reference per-run accuracies.
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
REF_PATH = Path(os.environ.get("DECODE_REFERENCE",
                               str(Path(__file__).resolve().parent / "reference.npz")))


def load_reference():
    d = np.load(REF_PATH, allow_pickle=False)
    stats = json.loads(str(d["ref_stats"]))
    return {
        "run_ids": [str(x) for x in d["ref_run_ids"]],
        "fold_acc": np.asarray(d["ref_fold_acc"], dtype=float),
        "stats": stats,
    }


def honest_naive(stats):
    """(honest_accuracy, naive_accuracy) tolerant to task-specific key names."""
    honest = next((stats[k] for k in ("honest_accuracy", "loro_accuracy", "nested_accuracy")
                   if k in stats), None)
    naive = next((stats[k] for k in ("naive_accuracy", "random_kfold_accuracy", "circular_accuracy")
                  if k in stats), None)
    return float(honest), float(naive)


# ---- submitted per-fold table ----------------------------------------------------------------
def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _find_perfold_csv():
    for name in ("per_fold.csv", "perfold.csv", "cv_folds.csv", "folds.csv"):
        p = OUT / name
        if p.exists():
            return p
    # any csv that has an accuracy-like column
    for p in sorted(OUT.glob("*.csv")):
        try:
            hdr = next(csv.reader(open(p, encoding="utf-8")))
        except Exception:
            continue
        if any("acc" in _norm(h) or "score" in _norm(h) for h in hdr):
            return p
    return None


def load_per_fold():
    """Return (run_ids_or_None, accuracies) parsed from the per-fold CSV.
    run id list is only returned when a run/group/fold-label column is present."""
    p = _find_perfold_csv()
    assert p is not None, "no per-fold CSV (per_fold.csv) with an accuracy column was produced"
    rows = list(csv.DictReader(open(p, encoding="utf-8")))
    assert rows, f"{p.name} has no data rows"
    hdr = list(rows[0].keys())
    acc_col = None
    for h in hdr:
        n = _norm(h)
        if ("acc" in n or "score" in n) and "samples" not in n and "n" != n:
            acc_col = h
            break
    assert acc_col, f"{p.name} has no accuracy column (columns: {hdr})"
    # optional held-out run / group id column
    id_col = None
    for h in hdr:
        n = _norm(h)
        if any(t in n for t in ("heldoutrun", "heldout", "run", "group", "chunk")) and "sample" not in n:
            id_col = h
            break
    accs, ids = [], []
    for r in rows:
        try:
            v = float(r[acc_col])
        except (TypeError, ValueError):
            continue
        if not math.isfinite(v):
            continue
        if v > 1.5:
            v = v / 100.0
        accs.append(v)
        if id_col is not None:
            ids.append(re.sub(r"\D", "", str(r[id_col])).lstrip("0") or "0")
    accs = np.asarray(accs, dtype=float)
    run_ids = ids if (id_col is not None and len(ids) == len(accs)) else None
    return run_ids, accs


def _canon_run(x):
    return re.sub(r"\D", "", str(x)).lstrip("0") or "0"


def per_fold_agreement(sub_ids, sub_accs, ref_ids, ref_accs, val_tol):
    """Return (best_match_fraction, correlation) between submitted and reference per-fold
    accuracies. Keyed by run id when available, else aligned by sorted value."""
    ref_canon = [_canon_run(r) for r in ref_ids]
    if sub_ids is not None and len(set(sub_ids) & set(ref_canon)) >= max(3, int(0.5 * len(ref_ids))):
        ref_map = {c: a for c, a in zip(ref_canon, ref_accs)}
        pairs = [(sub_accs[i], ref_map[sub_ids[i]]) for i in range(len(sub_ids)) if sub_ids[i] in ref_map]
    else:
        n = min(len(sub_accs), len(ref_accs))
        s = np.sort(sub_accs)[::-1][:n]
        r = np.sort(np.asarray(ref_accs))[::-1][:n]
        pairs = list(zip(s.tolist(), r.tolist()))
    if not pairs:
        return 0.0, 0.0
    a = np.array([p[0] for p in pairs]); b = np.array([p[1] for p in pairs])
    frac = float(np.mean(np.abs(a - b) <= val_tol))
    corr = _corr(a, b)
    return frac, corr


def _corr(a, b):
    a = np.asarray(a, float); b = np.asarray(b, float)
    if len(a) < 3 or np.std(a) < 1e-9 or np.std(b) < 1e-9:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def nonconstant(accs, eps):
    return len(accs) >= 3 and statistics.pstdev(accs.tolist()) > eps


# ---- reported headline / discriminating numbers ----------------------------------------------
_LEAKY_KEY = re.compile(r"leak|random|kfold|k_fold|circular|select.?once|naive|inflat|shuffl|chance", re.I)
_PERFOLD_KEY = re.compile(r"per.?run|per.?fold|fold|std|sem|sd\b|var|min|max|ci\b|lower|upper", re.I)


def _load_json(name):
    p = OUT / name
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def reported_headline():
    """The submission's reported cross-validated decoding accuracy (0-1). Prefers an explicit
    cv_accuracy/accuracy field; never returns a value the submission labelled leaky/naive/per-fold."""
    res = _load_json("decoding_results.json") or _load_json("results.json")
    if isinstance(res, dict):
        for key in ("cv_accuracy", "accuracy", "decoding_accuracy"):
            v = res.get(key)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                return float(v) / 100.0 if v > 1.5 else float(v)
        for k, v in res.items():
            if (isinstance(v, (int, float)) and not isinstance(v, bool)
                    and ("acc" in _norm(k) or "score" in _norm(k))
                    and not _LEAKY_KEY.search(k) and not _PERFOLD_KEY.search(k)):
                return float(v) / 100.0 if v > 1.5 else float(v)
    return None


def reported_leaky():
    """Any accuracy the submission itself labelled as the leaky/naive/random/circular contrast."""
    out = []
    for name in ("decoding_results.json", "results.json", "run_metadata.json"):
        res = _load_json(name)
        if isinstance(res, dict):
            for k, v in res.items():
                if (isinstance(v, (int, float)) and not isinstance(v, bool)
                        and _LEAKY_KEY.search(k) and ("acc" in _norm(k) or "score" in _norm(k))
                        and "chance" not in _norm(k)):
                    out.append(float(v) / 100.0 if v > 1.5 else float(v))
    return out
