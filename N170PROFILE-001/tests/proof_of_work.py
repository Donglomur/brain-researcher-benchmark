"""Reusable proof-of-work helpers for N170PROFILE-001 (see PROOF_OF_WORK_SPEC).

The grade is carried by NUMBERS, not prose: the submitted per-subject table must contain the
REAL signed per-subject measurements for the exact ERP CORE N170 analysis sample, they must
recompute the reported group results, and the reported conclusion numbers must match the
held-out reference. None of this is producible without actually computing the measures on the
real per-subject data.
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


def load_submitted(path, colmap):
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

    idcol = find_col(["subject_id", "subject", "participant", "subj", "sub", "id"])
    if idcol is None:
        idcol = headers[0]
    # resolve value columns; make sure a value column is not the id column
    cols = {}
    for k, cands in colmap.items():
        c = find_col(cands, exclude=("subject", "participant"))
        if c == idcol:
            c = None
        cols[k] = c

    out, order = {}, []
    for r in rows:
        cid = canon_id(r.get(idcol, ""))
        if not cid or cid == "0":
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
                              cover=0.90, match=0.90, eps=1e-4, signed=True):
    """Pillar 1: exact subjects + per-subject SIGNED value match.

    (a) coverage of the reference ids; (b) no fabricated-id padding; (c) non-constant guard;
    (d) per-subject |submitted - ref| <= val_tol for >= `match` of matched subjects (SIGNED,
    so an abs()-ed or sign-flipped table fails). Returns the list of matched ids.
    """
    ref = {canon_id(i): float(v) for i, v in zip(ref_ids, ref_vals)}
    present = [i for i in ref if i in sub and sub[i].get(key) is not None]
    coverage = len(present) / len(ref)
    assert coverage >= cover, (
        f"[{key}] per-subject table covers only {len(present)}/{len(ref)} reference subjects "
        f"({coverage:.2f} < {cover}); the exact ERP CORE N170 analysis sample must be reported")

    extra = [i for i in sub if i not in ref and sub[i].get(key) is not None]
    assert len(extra) <= 0.10 * len(ref), (
        f"[{key}] submitted table contains {len(extra)} subject ids that are not in the "
        f"analysis sample -- fabricated/padded rows")

    vals = np.array([sub[i][key] for i in present], float)
    assert np.isfinite(vals).all(), f"[{key}] non-numeric per-subject values"
    assert float(vals.std()) > eps, (
        f"[{key}] submitted per-subject values are ~constant (std {vals.std():.2g}); a real "
        f"per-subject computation is not constant -- the table was not actually computed")

    if signed:
        good = [i for i in present if abs(sub[i][key] - ref[i]) <= val_tol]
    else:
        good = [i for i in present if abs(abs(sub[i][key]) - abs(ref[i])) <= val_tol]
    frac = len(good) / len(present)
    assert frac >= match, (
        f"[{key}] only {len(good)}/{len(present)} ({frac:.2f} < {match}) per-subject values are "
        f"within {val_tol} of the held-out reference (SIGNED). The submitted per-subject numbers "
        f"are not the real measurements (fabricated, abs()-ed, or sign-flipped).")
    return present


def recompute_mean(sub, present, key):
    return float(np.nanmean(np.array([sub[i][key] for i in present], float)))


def check_recompute(sub, present, key, ref_mean, reported, tol_ref, tol_report):
    """Pillar 2: the group mean recomputed FROM the submitted rows must match BOTH the
    held-out reference mean AND the agent's reported headline number."""
    got = recompute_mean(sub, present, key)
    assert abs(got - ref_mean) <= tol_ref, (
        f"[{key}] group mean recomputed from the submitted rows ({got:.3f}) does not match the "
        f"held-out reference ({ref_mean:.3f}, tol {tol_ref}) -- the rows do not reproduce the "
        f"real group result")
    assert reported is not None and abs(got - reported) <= tol_report, (
        f"[{key}] the reported headline value ({reported}) is not the mean of the submitted "
        f"per-subject rows ({got:.3f}, tol {tol_report}) -- reported number and table disagree")
    return got
