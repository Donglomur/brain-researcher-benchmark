"""Reusable proof-of-work helpers for MOVIESYNC-001 (see PROOF_OF_WORK_SPEC.md).

A clean reproduction task: the deliverable is one headline inter-subject correlation (ISC). A
lone scalar is guessable, so (QSMDIPOLE-001 model) the grader also validates the finest
intermediate the analysis produces -- the per-subject ISC (both the pairwise and the
leave-one-out estimator) -- against a held-out reference. Both estimators are legitimate; the
grader validates the per-subject values, recomputes the headline as the mean of the per-subject
column, and requires the reported value to match the reference for the DECLARED estimator. A
fabricated ISC, or a value inconsistent with the per-subject rows or the declared estimator,
fails.
"""
import csv
import json
import math
import re
from pathlib import Path

import numpy as np


def canon_id(s):
    d = re.sub(r"\D", "", str(s))
    return d.lstrip("0") or (d if d else "")


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def load_reference(path):
    z = np.load(path, allow_pickle=True)
    ids = [canon_id(x) for x in z["ref_ids"]]
    ref = {
        "ids": ids,
        "pairwise": {i: float(v) for i, v in zip(ids, np.asarray(z["ref_pairwise"], float))},
        "loo": {i: float(v) for i, v in zip(ids, np.asarray(z["ref_loo"], float))},
        "stats": json.loads(str(z["ref_stats"])),
    }
    return ref


def _pick(headers, cands):
    norm_to_raw = {}
    for h in headers:
        norm_to_raw.setdefault(_norm(h), h)
    for c in cands:
        if c in norm_to_raw:
            return norm_to_raw[c]
    for nrm, raw in norm_to_raw.items():
        if any(c in nrm for c in cands):
            return raw
    return None


def load_submitted(path):
    """Return {canon_id: (pairwise_or_None, loo_or_None)} from isc_per_subject.csv."""
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    if not rows:
        return {}
    headers = list(rows[0].keys())
    id_c = _pick(headers, ("subject", "subjectid", "participant", "participantid", "subid", "id"))
    pw_c = _pick(headers, ("iscpairwise", "pairwiseisc", "pairwise", "iscpw", "pw"))
    loo_c = _pick(headers, ("iscloo", "looisc", "loo", "leaveoneout", "leaveoneoutisc",
                            "iscleaveoneout"))
    out = {}
    for r in rows:
        cid = canon_id(r.get(id_c, "")) if id_c else ""
        if not cid:
            continue

        def num(c):
            if c is None:
                return None
            try:
                v = float(r.get(c))
                return v if math.isfinite(v) else None
            except (TypeError, ValueError):
                return None
        out[cid] = (num(pw_c), num(loo_c))
    return out, pw_c is not None, loo_c is not None


def coverage(sub, ref_ids):
    return sum(1 for i in ref_ids if i in sub) / max(1, len(ref_ids))


def _corr(a, b):
    if len(a) < 3 or np.std(a) == 0 or np.std(b) == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def cross_corr(sub, ref_map, ref_ids, idx):
    matched = [i for i in ref_ids if i in sub and sub[i][idx] is not None]
    a = [sub[i][idx] for i in matched]
    b = [ref_map[i] for i in matched]
    return _corr(a, b), len(matched)


def per_subject_match(sub, ref_map, ref_ids, idx, tol):
    matched = [i for i in ref_ids if i in sub and sub[i][idx] is not None]
    if not matched:
        return 0.0, 0
    ok = sum(1 for i in matched if abs(sub[i][idx] - ref_map[i]) <= tol)
    return ok / len(matched), len(matched)


def nonconstant(sub, idx, eps=1e-6):
    vals = [sub[i][idx] for i in sub if sub[i][idx] is not None]
    return len(vals) >= 3 and float(np.std(vals)) > eps


def mean_of(sub, ref_ids, idx):
    vals = [sub[i][idx] for i in ref_ids if i in sub and sub[i][idx] is not None]
    return sum(vals) / len(vals) if vals else float("nan")


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


def declared_estimator(meta):
    """Return 'pairwise', 'loo', or None from the reported estimator string(s)."""
    blob = _norm(json.dumps(meta))
    is_loo = bool(re.search(r"leaveoneout|leave1out|loo|oneout|meanofthe?others|"
                            r"vsthemean|againstthemean|templatebased", blob))
    is_pw = "pairwise" in blob or "everypair" in blob or "betweeneverypair" in blob or \
            "meanpearson" in blob and "pair" in blob
    if is_loo and not is_pw:
        return "loo"
    if is_pw and not is_loo:
        return "pairwise"
    return None
