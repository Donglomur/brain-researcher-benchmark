"""Reusable proof-of-work helpers for EYESTATE-001's grader (see PROOF_OF_WORK_SPEC.md).

EYESTATE is a single-headline task (one cross-validated balanced accuracy), so the finest
validated intermediate is the PER-FOLD (per-held-out-site) balanced accuracy. A passing
submission must reproduce the real per-site leave-one-site-out accuracies, whose mean is the
reported headline, and must report both the site-blocked and the leaky random-fold numbers.
Only numpy + stdlib.
"""
import csv
import json
import math
import re
import statistics
from pathlib import Path

import numpy as np


def canon_site(s):
    return re.sub(r"[^A-Z0-9]", "", str(s).upper())


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def load_reference(path):
    z = np.load(path, allow_pickle=True)
    ref = {
        "ids": [canon_site(x) for x in z["ref_ids"]],
        "bacc": np.asarray(z["ref_bacc"], float),
        "ntest": np.asarray(z["ref_ntest"], int),
        "stats": json.loads(str(z["ref_stats"])),
    }
    ref["by_id"] = dict(zip(ref["ids"], ref["bacc"]))
    return ref


def load_submitted(path):
    """{canon_site: balanced_accuracy} from per_fold.csv (tolerant columns)."""
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    if not rows:
        return {}
    headers = list(rows[0].keys())
    norm_to_raw = {}
    for h in headers:
        norm_to_raw.setdefault(_norm(h), h)

    def pick(cands, exclude=()):
        for cand in cands:
            if cand in norm_to_raw:
                return norm_to_raw[cand]
        for nrm, raw in norm_to_raw.items():
            if any(c in nrm for c in cands) and not any(e in nrm for e in exclude):
                return raw
        return None

    id_c = pick(("foldsite", "site", "heldoutsite", "testsite", "fold", "foldid", "group", "siteid"))
    ba_c = pick(("balancedaccuracy", "balancedacc", "bacc", "balacc"),
                exclude=("n", "count")) or pick(("accuracy", "score"), exclude=("n", "count"))
    out = {}
    if id_c is None or ba_c is None:
        return out
    for r in rows:
        sid = canon_site(r.get(id_c, ""))
        if not sid:
            continue
        try:
            v = float(r.get(ba_c))
        except (TypeError, ValueError):
            continue
        if math.isfinite(v):
            out[sid] = v
    return out


def pearson(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    if len(x) < 3 or np.std(x) == 0 or np.std(y) == 0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def check_folds_and_values(sub, ref, val_tol, corr_min, cover, match, eps):
    """Pillar 1. coverage of the real LOSO folds (sites) + non-constant + cross-fold correlation
    with the reference per-site accuracies + per-fold abs match. A random-fold submission whose
    folds are numbered (not sites) fails coverage; a fabricated per-site table fails the match."""
    ref_ids = set(ref["ids"])
    matched = [i for i in ref["ids"] if i in sub]
    coverage = len(matched) / max(1, len(ref_ids))
    assert coverage >= cover, (
        f"per_fold.csv covers only {coverage:.0%} of the {len(ref_ids)} real acquisition sites "
        f"(need >= {cover:.0%}). The required per-fold table is the leave-one-SITE-out folds; a "
        f"random-fold table (numbered folds) does not identify the sites.")
    vals = [sub[i] for i in matched]
    assert statistics.pstdev(vals) > eps, (
        "submitted per-fold balanced accuracy is constant across folds -- not a real evaluation")
    ref_vals = [ref["by_id"][i] for i in matched]
    if len(matched) >= 4:
        rc = pearson(vals, ref_vals)
        assert math.isfinite(rc) and rc >= corr_min, (
            f"submitted per-site balanced accuracies do not track the reference (cross-fold "
            f"r={rc:.3f} < {corr_min}); the per-fold values were not really computed.")
    close = sum(1 for a, b in zip(vals, ref_vals) if abs(a - b) <= val_tol)
    frac = close / max(1, len(matched))
    assert frac >= match, (
        f"only {frac:.0%} of matched sites have a per-fold balanced accuracy within {val_tol} of "
        f"the reference (need >= {match:.0%}); the per-fold rows are not the real analysis.")
    return matched


def find_number(obj, leaf_re, path_include=(), path_exclude=(), prefer=None):
    lre = re.compile(leaf_re)
    hits = []

    def walk(cur, path):
        if isinstance(cur, dict):
            for k, v in cur.items():
                walk(v, path + [_norm(k)])
        elif isinstance(cur, list):
            for v in cur:
                walk(v, path)
        elif isinstance(cur, (int, float)) and not isinstance(cur, bool):
            fv = float(cur)
            if not math.isfinite(fv):
                return
            leaf = path[-1] if path else ""
            p = ".".join(path)
            if lre.search(leaf) and all(t in p for t in path_include) and not any(e in p for e in path_exclude):
                hits.append((len(path), p, fv))

    walk(obj, [])
    if not hits:
        return None
    if prefer:
        pref = [h for h in hits if any(pt in h[1] for pt in prefer)]
        if pref:
            hits = pref
    hits.sort(key=lambda h: h[0])
    return hits[0][2]
