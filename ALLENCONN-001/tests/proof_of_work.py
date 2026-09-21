"""Reusable proof-of-work helpers for ALLENCONN-001 (see PROOF_OF_WORK_SPEC.md).

The neutral per-item intermediate is the per-source-region "is the strongest projection target the
source's own structure?" indicator: BOTH the injection-included and the projection-only analyses
produce a source x target matrix and this per-source indicator, so requiring the per-source table
does not cue the injection-compartment lever. The held-out reference (tests/reference.npz) stores
the honest (projection-signal-only, is_injection=False) per-source indicators; a matrix that leaves
the saturated injection-site compartments in flips ~26% of sources to self-strongest and reports
~0.62 instead of the honest ~0.36, so matching the per-source indicators separates the two.
"""
import csv, json, math, re, statistics
from pathlib import Path
import numpy as np


def load_reference(path):
    z = np.load(path, allow_pickle=True)
    return {
        "src": [str(s) for s in z["ref_src"]],
        "self": np.asarray(z["ref_self"], dtype=bool),
        "strongest": [str(s) for s in z["ref_strongest"]],
        "naive_self": np.asarray(z["ref_naive_self"], dtype=bool),
        "stats": json.loads(str(z["ref_stats"])),
    }


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _truthy(v):
    s = str(v).strip().lower()
    if s in ("1", "true", "yes", "y", "self", "t"):
        return True
    if s in ("0", "false", "no", "n", "other", "f", ""):
        return False
    try:
        return float(s) != 0.0
    except ValueError:
        return None


def load_submitted_source_table(path):
    """Return {norm_source_acronym: is_self_strongest(bool)} from source_strongest.csv."""
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

    src_c = pick(("source", "sourceregion", "sourcestructure", "region", "src", "injectionstructure"),
                 avoid=("target", "strongest"))
    self_c = pick(("isselfstrongest", "selfstrongest", "isself", "self", "isdiagonal", "selfprojection",
                   "ownstructure", "isownstructure"), avoid=("fraction", "value", "strength"))
    strongest_c = pick(("strongesttarget", "strongest", "argmax", "target", "maxtarget", "peaktarget"),
                       avoid=("source", "self", "value", "strength"))
    if src_c is None:
        return {}
    out = {}
    for r in rows:
        s = _norm(r.get(src_c, ""))
        if not s:
            continue
        val = None
        if self_c is not None:
            val = _truthy(r.get(self_c, ""))
        if val is None and strongest_c is not None:
            val = (_norm(r.get(strongest_c, "")) == s)
        if val is None:
            continue
        out[s] = bool(val)
    return out


def check_per_source_indicators(submitted, ref, cover=0.85, match=0.85, eps=1e-6):
    """Pillar 1. The submitted per-source self-strongest indicators must be the real projection-only
    result: coverage of the reference sources, non-constant, and agreement with the held-out honest
    indicators for most sources (a matrix that leaves the injection-site compartments in disagrees
    on the ~26% of sources it flips to self-strongest)."""
    ref_by = {_norm(s): bool(b) for s, b in zip(ref["src"], ref["self"].tolist())}
    ref_ids = set(ref_by)
    matched = [s for s in submitted if s in ref_ids]
    coverage = len(matched) / max(1, len(ref_ids))
    assert coverage >= cover, (
        f"submitted source table covers only {coverage:.1%} of the {len(ref_ids)} real source "
        f"regions (need >= {cover:.0%}). Fabricated or missing source regions.")
    vals = [submitted[s] for s in matched]
    assert 0 < sum(vals) < len(vals), (
        "submitted per-source self-strongest indicator is constant (all-self or all-other) -- not "
        "a real per-source argmax over the projection matrix")
    agree = sum(1 for s in matched if submitted[s] == ref_by[s])
    frac = agree / max(1, len(matched))
    assert frac >= match, (
        f"only {frac:.0%} of source regions match the held-out projection-only self-strongest "
        f"indicators (need >= {match:.0%}). Leaving the saturated injection-site compartments in "
        f"flips ~26% of sources to self-strongest (reported fraction ~{ref['stats']['frac_naive']:.2f} "
        f"vs the honest ~{ref['stats']['frac_correct']:.2f}).")
    recomputed = sum(vals) / len(vals)
    return recomputed, matched


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
