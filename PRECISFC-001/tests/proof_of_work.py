"""Reusable proof-of-work helpers for PRECISFC-001's grader (see PROOF_OF_WORK_SPEC.md).

A passing submission must be IMPOSSIBLE to produce without running the real cross-session
reliability analysis on the real MSC (ds000224) subjects. Frame-censoring is an accepted
refinement (not required), so the per-subject teeth accept EITHER the censored OR the
all-frames reliability for each subject. Only numpy + stdlib.
"""
import csv
import json
import math
import re
import statistics
from pathlib import Path

import numpy as np


def canon_id(s):
    m = re.search(r"MSC0*(\d+)", str(s).upper())
    return f"MSC{int(m.group(1)):02d}" if m else re.sub(r"[^A-Z0-9]", "", str(s).upper())


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def load_reference(path):
    z = np.load(path, allow_pickle=True)
    ref = {
        "ids": [canon_id(x) for x in z["ref_ids"]],
        "rel_censored": np.asarray(z["ref_rel_censored"], float),
        "rel_allframes": np.asarray(z["ref_rel_allframes"], float),
        "retention": np.asarray(z["ref_retention"], float),
        "stats": json.loads(str(z["ref_stats"])),
    }
    ref["cens_by_id"] = dict(zip(ref["ids"], ref["rel_censored"]))
    ref["all_by_id"] = dict(zip(ref["ids"], ref["rel_allframes"]))
    return ref


def load_submitted(path):
    """{canon_id: reliability} from reliability.csv (tolerant reliability-column match)."""
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    if not rows:
        return {}
    headers = list(rows[0].keys())
    norm_to_raw = {}
    for h in headers:
        norm_to_raw.setdefault(_norm(h), h)

    def pick_id():
        for cand in ("subjectid", "subject", "subid", "participant", "id"):
            if cand in norm_to_raw:
                return norm_to_raw[cand]
        for nrm, raw in norm_to_raw.items():
            if "subject" in nrm or "subid" in nrm:
                return raw
        return headers[0]

    def pick_rel():
        # prefer a plain reliability column (censored default); avoid frame/count/retention cols
        for nrm, raw in norm_to_raw.items():
            if ("reliab" in nrm or nrm in ("r", "similarity")) and \
               not any(x in nrm for x in ("frame", "retention", "session", "n")):
                return raw
        for nrm, raw in norm_to_raw.items():
            if "reliab" in nrm:
                return raw
        return None

    id_c, rel_c = pick_id(), pick_rel()
    out = {}
    if rel_c is None:
        return out
    for r in rows:
        cid = canon_id(r.get(id_c, ""))
        if not cid:
            continue
        try:
            v = float(r.get(rel_c))
        except (TypeError, ValueError):
            continue
        if math.isfinite(v):
            out[cid] = v
    return out


def check_subjects_and_values(sub, ref, val_tol, cover, match, eps):
    """Pillar 1. coverage + non-constant + per-subject match to EITHER the censored OR the
    all-frames reference reliability (frame-censoring is optional)."""
    ref_ids = set(ref["ids"])
    matched = [i for i in ref["ids"] if i in sub]
    coverage = len(matched) / max(1, len(ref_ids))
    assert coverage >= cover, (
        f"reliability.csv covers only {coverage:.0%} of the {len(ref_ids)} pinned MSC subjects "
        f"(need >= {cover:.0%}); the exact cohort must be analysed.")
    real = sum(1 for i in sub if i in ref_ids) / max(1, len(sub))
    assert real >= 0.6, f"only {real:.0%} of submitted ids are the pinned MSC subjects (padded?)"

    vals = [sub[i] for i in matched]
    assert statistics.pstdev(vals) > eps, (
        "submitted reliability is ~constant across subjects; a real per-subject computation is "
        "not constant (MSC08 in particular is far lower).")

    ok = 0
    for i in matched:
        if abs(sub[i] - ref["cens_by_id"][i]) <= val_tol or abs(sub[i] - ref["all_by_id"][i]) <= val_tol:
            ok += 1
    frac = ok / len(matched)
    assert frac >= match, (
        f"only {frac:.0%} of matched subjects have a reliability within {val_tol} of the real "
        f"per-subject value (censored or all-frames) -- the rows are not the real analysis.")
    return matched


def group_mean(sub, ids):
    v = [sub[i] for i in ids if i in sub]
    return sum(v) / len(v) if v else float("nan")


def find_path_number(obj, path_include=(), leaf_re=None, path_exclude=(), prefer=None):
    lre = re.compile(leaf_re) if leaf_re else None
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
            if all(t in p for t in path_include) and not any(e in p for e in path_exclude):
                if lre is None or lre.search(leaf):
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
