"""Reusable proof-of-work helpers for EMOMATCH-001's grader (see PROOF_OF_WORK_SPEC.md).

A passing submission must be IMPOSSIBLE to produce without running the real first-level GLM on
the real ds002790 (AOMIC PIOP2) emomatching subjects. These helpers validate the SUBMITTED
per-subject contrast table against a held-out reference (tests/reference.npz), recompute the
group one-sample t FROM the submitted rows, and expose the discriminating reaction-time-
controlled statistics for the numeric judgement.

Only numpy + stdlib.
"""
import csv
import json
import math
import re
import statistics
from pathlib import Path

import numpy as np


def canon_id(s):
    return re.sub(r"\D", "", str(s)).lstrip("0")


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


REGIONS = ("amygdala", "fusiform", "control")


def load_reference(path):
    z = np.load(path, allow_pickle=True)
    ref = {
        "ids": [canon_id(x) for x in z["ref_ids"]],
        "amygdala": np.asarray(z["ref_amygdala"], float),
        "fusiform": np.asarray(z["ref_fusiform"], float),
        "control": np.asarray(z["ref_control"], float),
        # per-subject contrasts under the alternative (variable-epoch) model
        "amygdala_rt": np.asarray(z["ref_amygdala_rt"], float),
        "fusiform_rt": np.asarray(z["ref_fusiform_rt"], float),
        "control_rt": np.asarray(z["ref_control_rt"], float),
        "stats": json.loads(str(z["ref_stats"])),
    }
    ref["by_id"] = {i: {k: ref[k][j] for k in
                        ("amygdala", "fusiform", "control", "amygdala_rt", "fusiform_rt", "control_rt")}
                    for j, i in enumerate(ref["ids"])}
    return ref


# region -> substrings that identify a column as belonging to that region
_REGION_MATCH = {
    "amygdala": (("amygdala", "amyg"), ()),
    "fusiform": (("fusiform", "ffa"), ("control", "amyg")),
    "control": (("controlrois", "control", "ctrl", "cognitivecontrol", "cogcontrol", "domaingeneral",
                 "salience", "frontoparietal", "dorsalattention", "dorsattn"),
                ("amyg", "fusiform", "face")),
}


def load_submitted(path):
    """Return {canon_id: {region: {colname: value}}} from activation.csv.

    The emotion>control contrast may be reported under SEVERAL first-level modelling choices, one
    column per choice per region. We collect EVERY column per region (amygdala / fusiform /
    control) and let the grader assign, by VALUE, which column is the standard (constant-epoch)
    estimate and which is the alternative-model estimate. The grader never keys off a column NAME,
    so the required schema does not name the modelling lever that separates them."""
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    if not rows:
        return {}, {r: [] for r in REGIONS}
    headers = list(rows[0].keys())
    norm = {h: _norm(h) for h in headers}

    id_c = None
    for h, n in norm.items():
        if any(c in n for c in ("subjectid", "subject", "participant", "subid", "id")):
            id_c = h; break

    region_cols = {}
    for region, (inc, exc) in _REGION_MATCH.items():
        region_cols[region] = [h for h, n in norm.items()
                               if any(c in n for c in inc) and not any(e in n for e in exc)]
    out = {}
    if id_c is None:
        return out, region_cols
    for r in rows:
        cid = canon_id(r.get(id_c, ""))
        if not cid:
            continue

        def gf(col):
            try:
                v = float(r.get(col))
                return v if math.isfinite(v) else None
            except (TypeError, ValueError):
                return None
        rowd = {}
        for region in REGIONS:
            rowd[region] = {c: gf(c) for c in region_cols[region]}
        out[cid] = rowd
    return out, region_cols


def assign_model_columns(sub, ref, region, cover):
    """For one region, assign by VALUE which submitted column is the standard (constant-epoch)
    estimate (best per-subject match to ref[region]) and which is the alternative-model estimate
    (best per-subject match to ref[region+'_rt']). Returns (std_col, alt_col, diag)."""
    ref_ids = set(ref["ids"])
    std_key, alt_key = region, region + "_rt"
    cols = set()
    for cid in sub:
        cols |= set(sub[cid].get(region, {}).keys())
    cols = sorted(cols)
    best_std = (None, -2.0); best_alt = (None, -2.0); diag = {}
    for c in cols:
        xs, ys_std, ys_alt = [], [], []
        for cid in sub:
            if cid not in ref_ids:
                continue
            v = sub[cid].get(region, {}).get(c)
            if v is None:
                continue
            xs.append(v)
            ys_std.append(ref["by_id"][cid][std_key])
            ys_alt.append(ref["by_id"][cid][alt_key])
        coverage = len(xs) / max(1, len(ref_ids))
        r_std = pearson(xs, ys_std) if len(xs) >= 8 else float("nan")
        r_alt = pearson(xs, ys_alt) if len(xs) >= 8 else float("nan")
        diag[c] = {"coverage": coverage, "r_std": r_std, "r_alt": r_alt}
        if coverage < cover:
            continue
        if math.isfinite(r_std) and r_std > best_std[1]:
            best_std = (c, r_std)
        if math.isfinite(r_alt) and r_alt > best_alt[1]:
            best_alt = (c, r_alt)
    return best_std[0], best_alt[0], diag


def column_values(sub, ref, region, col):
    """Ordered (submitted, reference-std, reference-alt) triples over matched subjects for a chosen
    column; and the raw per-subject submitted values keyed by id."""
    ref_ids = set(ref["ids"])
    matched = [cid for cid in sub if cid in ref_ids and sub[cid].get(region, {}).get(col) is not None]
    return matched


def pearson(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    if len(x) < 3 or np.std(x) == 0 or np.std(y) == 0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def one_sample_t(vals):
    v = np.asarray([x for x in vals if x is not None and math.isfinite(x)], float)
    if len(v) < 2 or v.std(ddof=1) == 0:
        return float("nan")
    return float(v.mean() / (v.std(ddof=1) / math.sqrt(len(v))))


def check_region_column(sub, ref, region, col, ref_key, val_tol, corr_min, cover, match, eps,
                        label):
    """Validate one submitted per-subject column (region, col) against a reference vector
    (ref_key): coverage, non-constant, cross-subject correlation, per-subject absolute match."""
    ref_ids = set(ref["ids"])
    matched = [cid for cid in sub if cid in ref_ids and sub[cid].get(region, {}).get(col) is not None]
    coverage = len(matched) / max(1, len(ref_ids))
    assert coverage >= cover, (
        f"[{label}] covers only {coverage:.1%} of the {len(ref_ids)} real ds002790 emomatching "
        f"subjects by id (need >= {cover:.0%}). Fabricated or missing participant ids.")
    s = [sub[cid][region][col] for cid in matched]
    r = [ref["by_id"][cid][ref_key] for cid in matched]
    assert statistics.pstdev(s) > eps, \
        f"[{label}] {region} emotion>control is constant across subjects -- not computed per subject"
    rc = pearson(s, r)
    assert math.isfinite(rc) and rc >= corr_min, (
        f"[{label}] submitted per-subject {region} emotion>control does not track the reference "
        f"(cross-subject r={rc:.3f} < {corr_min}). Values were not computed from the real GLM.")
    close = sum(1 for a, b in zip(s, r) if abs(a - b) <= val_tol)
    frac = close / max(1, len(matched))
    assert frac >= match, (
        f"[{label}] only {frac:.1%} of matched subjects have {region} within {val_tol} of the "
        f"reference (need >= {match:.0%}); the per-subject values are not the real ones.")
    return matched


def group_t_from_column(sub, region, col, matched):
    return one_sample_t([sub[cid][region][col] for cid in matched])


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
