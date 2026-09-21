"""Reusable proof-of-work helpers for ALLENOSI-001 (see PROOF_OF_WORK_SPEC.md).

The neutral per-item intermediate is the per-unit OSI keyed by real unit id: BOTH a naive
(count every cluster) and an honest (quality-controlled) analysis compute an OSI for every VISp
unit, so requiring the per-unit table does not cue the quality-control lever. The held-out
reference (tests/reference.npz) stores every VISp unit's OSI plus its quality-control flags and
visual-responsiveness flag. The grader validates the submitted per-unit OSI against the reference
(proving real per-unit work) and then RECOMPUTES the honest quality-controlled selective fraction
from the submitted OSI using the held-out QC flags -- so the headline is only reachable by an
analysis whose OSI values are real and whose reported fraction is the QC-gated one (~0.24), not
the noise-inflated all-clusters fraction (~0.39).
"""
import csv, json, math, re, statistics
from pathlib import Path
import numpy as np


def load_reference(path):
    z = np.load(path, allow_pickle=True)
    ids = [str(int(x)) for x in z["ref_unit_ids"]]
    return {
        "ids": ids,
        "osi": {i: float(o) for i, o in zip(ids, z["ref_osi"])},
        "keep": {i: bool(k) for i, k in zip(ids, z["ref_keep"])},
        "qc_pass": {i: bool(k) for i, k in zip(ids, z["ref_qc_pass"])},
        "responsive": {i: bool(k) for i, k in zip(ids, z["ref_responsive"])},
        "stats": json.loads(str(z["ref_stats"])),
    }


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def canon_id(s):
    d = re.sub(r"\D", "", str(s))
    return d.lstrip("0") or ("0" if d else "")


def load_submitted_units(path):
    """Return {canon_unit_id: osi} parsed from units.csv. Tolerant column matching."""
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    if not rows:
        return {}
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

    id_c = pick(("unitid", "unit", "id", "clusterid", "cluster", "unitindex"), avoid=("osi", "rate"))
    osi_c = pick(("osi", "orientationselectivity", "orientationselectivityindex", "selectivity"),
                 avoid=("threshold", "dsi", "flag", "selective"))
    if id_c is None or osi_c is None:
        return {}
    out = {}
    for r in rows:
        cid = canon_id(r.get(id_c, ""))
        if not cid:
            continue
        try:
            o = float(r.get(osi_c))
        except (TypeError, ValueError):
            continue
        if math.isfinite(o):
            out[cid] = o
    return out


def _ref_by_canon(ref):
    """map canonical id -> (osi, keep) from the reference (ids are stored as plain ints)."""
    osi, keep = {}, {}
    for i in ref["ids"]:
        c = canon_id(i)
        osi[c] = ref["osi"][i]
        keep[c] = ref["keep"][i]
    return osi, keep


def check_units_and_osi(submitted, ref, osi_tol=0.08, cover=0.90, val_match=0.80,
                        corr_min=0.95, eps=1e-6):
    """Pillar 1. The submitted per-unit OSI must be the real per-unit values for the real VISp
    units: coverage of the reference unit ids, non-constant, high cross-unit correlation and
    per-unit agreement with the held-out reference OSI."""
    ref_osi, ref_keep = _ref_by_canon(ref)
    ref_ids = set(ref_osi)
    matched = [i for i in submitted if i in ref_ids]
    coverage = len(matched) / max(1, len(ref_ids))
    assert coverage >= cover, (
        f"submitted units.csv covers only {coverage:.1%} of the {len(ref_ids)} real VISp units by "
        f"id (need >= {cover:.0%}). Fabricated or missing unit ids.")
    sub = [submitted[i] for i in matched]
    rf = [ref_osi[i] for i in matched]
    assert statistics.pstdev(sub) > eps, "submitted OSI is constant across units -- not per-unit work"
    rc = float(np.corrcoef(sub, rf)[0, 1]) if np.std(sub) > 0 and np.std(rf) > 0 else float("nan")
    assert math.isfinite(rc) and rc >= corr_min, (
        f"submitted per-unit OSI does not track the reference (cross-unit r={rc:.3f} < {corr_min}); "
        f"the OSI values were not computed from the real drifting-grating responses.")
    close = sum(1 for a, b in zip(sub, rf) if abs(a - b) <= osi_tol)
    frac = close / max(1, len(matched))
    assert frac >= val_match, (
        f"only {frac:.1%} of matched units have OSI within {osi_tol} of the reference "
        f"(need >= {val_match:.0%}); the per-unit OSI values are not the real ones.")
    return matched


def recompute_fractions(submitted, ref, thr=0.5):
    """Recompute the honest (QC + responsive) and naive (all VISp) selective fractions FROM the
    submitted per-unit OSI, using the held-out QC/responsiveness flags. Returns (honest, naive)."""
    ref_osi, ref_keep = _ref_by_canon(ref)
    ref_ids = set(ref_osi)
    matched = [i for i in submitted if i in ref_ids]
    kept = [i for i in matched if ref_keep[i]]
    honest = (sum(1 for i in kept if submitted[i] > thr) / len(kept)) if kept else float("nan")
    naive = (sum(1 for i in matched if submitted[i] > thr) / len(matched)) if matched else float("nan")
    return honest, naive


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
