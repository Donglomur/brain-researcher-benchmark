"""Reusable proof-of-work helpers (see PROOF_OF_WORK_SPEC).

The grade is carried by NUMBERS, not prose: the submitted per-subject table must contain the
REAL per-subject measurements for the exact pinned analysis sample, they must recompute the
reported group result, and the reported conclusion numbers must match the held-out reference.
None of this is producible without actually computing the measures on the real per-subject
data. This module is copied verbatim into each task's tests/ directory.
"""
import csv
import re

import numpy as np


def canon_id(s):
    """Canonicalise a subject id: digits only, leading zeros stripped."""
    d = re.sub(r"\D", "", str(s)).lstrip("0")
    return d or "0"


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def load_submitted(path, colmap, id_cands=None):
    """Load a submitted per-subject CSV.

    colmap: {out_key: [candidate column-name substrings]}.
    Returns (rows_by_id, order): rows_by_id maps canon_id -> {out_key: float|None}.
    Column matching is tolerant (case/punctuation-insensitive substring).
    """
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return {}, []
    headers = list(rows[0].keys())

    def find_col(cands, exclude=()):
        for h in headers:
            hn = _norm(h)
            if any(_norm(c) in hn for c in cands) and not any(_norm(e) in hn for e in exclude):
                return h
        return None

    idc = id_cands or ["subject_id", "subject", "participant", "subj", "sub", "fold", "id"]
    idcol = find_col(idc)
    if idcol is None:
        idcol = headers[0]
    cols = {}
    for k, cands in colmap.items():
        c = find_col(cands, exclude=("subject", "participant"))
        if c == idcol:
            c = None
        cols[k] = c

    out, order = {}, []
    for r in rows:
        cid = canon_id(r.get(idcol, ""))
        if not cid:
            continue
        d = {}
        for k, c in cols.items():
            v = None
            if c is not None:
                raw = r.get(c, "")
                if raw not in (None, ""):
                    try:
                        v = float(raw)
                    except (TypeError, ValueError):
                        v = None
            d[k] = v
        out[cid] = d
        order.append(cid)
    return out, order


def check_subjects_and_values(sub, ref_ids, ref_vals, key, val_tol,
                              cover=0.90, match=0.90, eps=1e-4, signed=True, rel_tol=0.0):
    """Pillar 1: exact subjects + per-subject value match (SIGNED by default).

    (a) coverage of the reference ids; (b) no fabricated-id padding; (c) non-constant guard;
    (d) per-subject |submitted - ref| <= max(val_tol, rel_tol*|ref|) for >= `match` of matched
    subjects. With signed=True an abs()-ed or sign-flipped table fails. `rel_tol` widens the
    tolerance proportionally for measures with a large dynamic range (e.g. power ratios).
    Returns the list of matched ids.
    """
    ref = {canon_id(i): float(v) for i, v in zip(ref_ids, ref_vals)}
    present = [i for i in ref if i in sub and sub[i].get(key) is not None]
    coverage = len(present) / len(ref)
    assert coverage >= cover, (
        f"[{key}] per-subject table covers only {len(present)}/{len(ref)} reference subjects "
        f"({coverage:.2f} < {cover}); the exact pinned analysis sample must be reported")

    extra = [i for i in sub if i not in ref and sub[i].get(key) is not None]
    assert len(extra) <= 0.10 * len(ref) + 1e-9, (
        f"[{key}] submitted table contains {len(extra)} subject ids that are not in the "
        f"analysis sample -- fabricated/padded rows")

    vals = np.array([sub[i][key] for i in present], float)
    assert np.isfinite(vals).all(), f"[{key}] non-numeric per-subject values"
    assert float(vals.std()) > eps, (
        f"[{key}] submitted per-subject values are ~constant (std {vals.std():.2g}); a real "
        f"per-subject computation is not constant -- the table was not actually computed")

    def tol(rv):
        return max(val_tol, rel_tol * abs(rv))
    if signed:
        good = [i for i in present if abs(sub[i][key] - ref[i]) <= tol(ref[i])]
    else:
        good = [i for i in present if abs(abs(sub[i][key]) - abs(ref[i])) <= tol(ref[i])]
    frac = len(good) / len(present)
    assert frac >= match, (
        f"[{key}] only {len(good)}/{len(present)} ({frac:.2f} < {match}) per-subject values are "
        f"within {val_tol} of the held-out reference{' (SIGNED)' if signed else ''}. The "
        f"submitted per-subject numbers are not the real measurements (fabricated, abs()-ed, "
        f"or sign-flipped).")
    return present


def recompute_mean(sub, present, key):
    return float(np.nanmean(np.array([sub[i][key] for i in present], float)))


def recompute_weighted_mean(sub, present, key, weight_key):
    v = np.array([sub[i][key] for i in present], float)
    w = np.array([sub[i][weight_key] for i in present], float)
    return float(np.sum(v * w) / np.sum(w))


def check_recompute(sub, present, key, ref_mean, reported, tol_ref, tol_report,
                    weight_key=None):
    """Pillar 2: the group aggregate recomputed FROM the submitted rows must match BOTH the
    held-out reference AND the agent's reported headline number. If weight_key is given the
    aggregate is the weighted mean (e.g. epoch-weighted overall accuracy)."""
    if weight_key is not None:
        got = recompute_weighted_mean(sub, present, key, weight_key)
    else:
        got = recompute_mean(sub, present, key)
    assert abs(got - ref_mean) <= tol_ref, (
        f"[{key}] group aggregate recomputed from the submitted rows ({got:.4f}) does not "
        f"match the held-out reference ({ref_mean:.4f}, tol {tol_ref}) -- the rows do not "
        f"reproduce the real group result")
    assert reported is not None and abs(got - reported) <= tol_report, (
        f"[{key}] the reported headline value ({reported}) is not the aggregate of the "
        f"submitted per-subject rows ({got:.4f}, tol {tol_report}) -- reported number and "
        f"table disagree")
    return got
