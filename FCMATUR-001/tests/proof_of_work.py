"""Reusable proof-of-work helpers for FCMATUR-001's grader.

A passing submission must be IMPOSSIBLE to produce without running the real connectivity analysis
on the real ABIDE subjects. These helpers validate the SUBMITTED per-subject table against a
held-out reference built from the oracle run (tests/reference.npz), then recompute the headline
statistic FROM the submitted rows and cross-check it against the agent's reported JSON.

Nothing here imports numpy/scipy at module import time beyond numpy (already a verifier dep).
"""
import csv
import json
import math
import re
import statistics
from pathlib import Path

import numpy as np


def canon_id(s):
    """Canonical ABIDE subject id = the digit run (SUB_ID), leading zeros stripped.

    'Pitt_0050037' -> '50037', 50037 -> '50037'. SUB_ID is globally unique in ABIDE, so this is
    robust to FILE_ID prefix/case/zero-padding while still rejecting fabricated/index ids.
    """
    d = re.sub(r"\D", "", str(s)).lstrip("0")
    return d


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def load_reference(path):
    z = np.load(path, allow_pickle=True)
    ref = {
        "ids": [canon_id(x) for x in z["ref_ids"]],
        "conn": np.asarray(z["ref_conn"], dtype=float),
        "age": np.asarray(z["ref_age"], dtype=float),
        "site": [str(x) for x in z["ref_site"]],
        "stats": json.loads(str(z["ref_stats"])),
    }
    ref["by_id"] = {i: (float(c), float(a)) for i, c, a in zip(ref["ids"], ref["conn"], ref["age"])}
    return ref


def load_submitted(path, id_cols, conn_cols, age_cols, site_cols=None):
    """Return {canon_id: (connectivity, age, site)} plus the raw column-parsed lists.

    Tolerant column matching: `id_cols`, `conn_cols`, `age_cols`, `site_cols` are tuples of
    normalised names (lowercase, alnum-only) that are accepted for each field. `site` is the raw
    (string) acquisition-site label, or None when no site column is present. The returned tuple is
    ``(submitted, conn_list, age_list, site_list)``.
    """
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    if not rows:
        return {}, [], [], []
    headers = list(rows[0].keys())
    norm_to_raw = {}
    for h in headers:
        norm_to_raw.setdefault(_norm(h), h)

    def pick(cands):
        if not cands:
            return None
        for c in cands:
            if c in norm_to_raw:
                return norm_to_raw[c]
        # substring fallback (e.g. "connectivity_strength" contains "connectivity")
        for nrm, raw in norm_to_raw.items():
            if any(c in nrm for c in cands):
                return raw
        return None

    id_c = pick(id_cols)
    conn_c = pick(conn_cols)
    age_c = pick(age_cols)
    site_c = pick(site_cols)
    submitted, conn_list, age_list, site_list = {}, [], [], []
    if id_c is None or conn_c is None or age_c is None:
        return submitted, conn_list, age_list, site_list
    for r in rows:
        cid = canon_id(r.get(id_c, ""))
        if not cid:
            continue
        try:
            c = float(r.get(conn_c))
            a = float(r.get(age_c))
        except (TypeError, ValueError):
            continue
        if not (math.isfinite(c) and math.isfinite(a)):
            continue
        s = None
        if site_c is not None:
            raw_s = r.get(site_c, "")
            s = str(raw_s).strip() if raw_s is not None and str(raw_s).strip() != "" else None
        submitted[cid] = (c, a, s)       # last wins on duplicate id
        conn_list.append(c)
        age_list.append(a)
        site_list.append(s)
    return submitted, conn_list, age_list, site_list


def check_subjects_and_values(submitted, ref, conn_tol=0.05, age_tol=0.5,
                              cover=0.90, val_match=0.80, corr_min=0.95, eps=1e-6):
    """Pillar 1. Raise AssertionError if the submitted table is not real per-subject work.

    (a) coverage: >= `cover` of the reference subjects are present by real canonical id;
    (b) non-constant guard on both connectivity and age;
    (c) fabrication teeth: cross-subject Pearson corr(submitted, reference) >= `corr_min`
        (impossible to fake without computing the real per-subject values), and >= `val_match`
        of matched subjects within `conn_tol`; and the real per-subject AGE matches within
        `age_tol` for >= `cover` of matched subjects.
    """
    ref_ids = set(ref["ids"])
    matched = [i for i in submitted if i in ref_ids]
    coverage = len(matched) / max(1, len(ref_ids))
    assert coverage >= cover, (
        f"submitted connectivity.csv covers only {coverage:.1%} of the {len(ref_ids)} real ABIDE "
        f"subjects by id (need >= {cover:.0%}). Fabricated or missing participant ids.")

    sub_conn = [submitted[i][0] for i in matched]
    sub_age = [submitted[i][1] for i in matched]
    assert statistics.pstdev(sub_conn) > eps, \
        "submitted connectivity is constant across participants -- not computed per subject"
    assert statistics.pstdev(sub_age) > eps, \
        "submitted age is constant across participants -- not the real per-subject ages"

    ref_conn = [ref["by_id"][i][0] for i in matched]
    ref_age = [ref["by_id"][i][1] for i in matched]

    # (c1) fabrication teeth: cross-subject correlation with the held-out reference connectivity.
    rc = float(np.corrcoef(sub_conn, ref_conn)[0, 1])
    assert math.isfinite(rc) and rc >= corr_min, (
        f"submitted per-subject connectivity does not track the reference (cross-subject r={rc:.3f} "
        f"< {corr_min}). The values were not computed from the real CC200 timeseries.")

    # (c2) absolute per-subject connectivity match (catches a rescaled fake that still correlates).
    close = sum(1 for a, b in zip(sub_conn, ref_conn) if abs(a - b) <= conn_tol)
    frac = close / max(1, len(matched))
    assert frac >= val_match, (
        f"only {frac:.1%} of matched subjects have connectivity within {conn_tol} of the reference "
        f"(need >= {val_match:.0%}); the per-subject values are not the real ones.")

    # (c3) the real per-subject ages must match (age is a hard phenotype fact).
    age_close = sum(1 for a, b in zip(sub_age, ref_age) if abs(a - b) <= age_tol)
    afrac = age_close / max(1, len(matched))
    assert afrac >= cover, (
        f"only {afrac:.1%} of matched subjects have age within {age_tol}yr of the real phenotype "
        f"(need >= {cover:.0%}); ages were not read from the real ABIDE subjects.")
    return matched


def pearson(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    if len(x) < 3 or np.std(x) == 0 or np.std(y) == 0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def check_recompute(submitted, matched, ref, reported_pooled, stat_tol=0.03):
    """Pillar 2. Recompute the pooled r FROM the submitted rows and require it to match BOTH the
    reference pooled r AND the agent's reported number. A CSV whose rows do not produce the
    reported statistic fails here."""
    conn = [submitted[i][0] for i in matched]
    age = [submitted[i][1] for i in matched]
    r_recompute = pearson(conn, age)
    ref_pool = float(ref["stats"]["pooled_r"])
    assert math.isfinite(r_recompute), "cannot recompute pooled r from submitted rows"
    assert abs(r_recompute - ref_pool) <= stat_tol, (
        f"pooled r recomputed from the submitted rows ({r_recompute:+.3f}) does not match the "
        f"reference ({ref_pool:+.3f}, tol {stat_tol}). The rows are not the real analysis.")
    assert reported_pooled is not None, "no pooled connectivity-age correlation reported in JSON"
    assert abs(r_recompute - float(reported_pooled)) <= stat_tol, (
        f"pooled r recomputed from the submitted rows ({r_recompute:+.3f}) does not match the "
        f"reported value ({float(reported_pooled):+.3f}, tol {stat_tol}). CSV and JSON disagree.")
    return r_recompute


def _partial_corr_resid(y, x, D):
    """Partial correlation of y and x after regressing both on the design matrix D (which must
    include an intercept column). numpy-only (the verifier ships no scipy)."""
    y = np.asarray(y, float); x = np.asarray(x, float); D = np.asarray(D, float)

    def resid(v):
        beta, *_ = np.linalg.lstsq(D, v, rcond=None)
        return v - D @ beta
    ry, rx = resid(y), resid(x)
    if np.std(ry) == 0 or np.std(rx) == 0:
        return float("nan")
    return float(np.corrcoef(ry, rx)[0, 1])


def recompute_site_levels(submitted, matched, min_per_site=5):
    """Recompute the WITHIN-site (site fixed effects) and BETWEEN-site (site-mean) connectivity–age
    correlations FROM the submitted rows {connectivity, age, site}. Mirrors the oracle exactly
    (drop sites with < `min_per_site` participants; site fixed effects via drop-first dummies).

    Returns ``{"within_site_r", "between_site_r", "pooled_r", "n_within", "n_sites"}`` with NaNs
    when the site column is absent/degenerate. This is the un-guessable teeth: a fabricated or
    shuffled site partition cannot reproduce the reference within-site attenuation.
    """
    conn = np.array([submitted[i][0] for i in matched], dtype=float)
    age = np.array([submitted[i][1] for i in matched], dtype=float)
    site = np.array([submitted[i][2] if submitted[i][2] is not None else "" for i in matched],
                    dtype=object)

    out = {"within_site_r": float("nan"), "between_site_r": float("nan"),
           "pooled_r": pearson(conn, age), "n_within": 0, "n_sites": 0}

    have_site = np.array([str(s) != "" for s in site])
    if have_site.sum() < 3:
        return out                       # no usable site column -> cannot recompute
    c, a, s = conn[have_site], age[have_site], site[have_site].astype(str)

    labels, counts = np.unique(s, return_counts=True)
    keep = set(labels[counts >= min_per_site])
    m = np.array([x in keep for x in s])
    if m.sum() < 10 or len(keep) < 2:
        return out
    cw, aw, sw = c[m], a[m], s[m]

    # within-site: site fixed effects (drop-first dummies + intercept)
    cats = sorted(set(sw))
    dummies = np.zeros((len(sw), len(cats) - 1), dtype=float)
    for j, cat in enumerate(cats[1:]):
        dummies[:, j] = (sw == cat).astype(float)
    D = np.column_stack([np.ones(len(sw)), dummies])
    out["within_site_r"] = _partial_corr_resid(aw, cw, D)
    out["n_within"] = int(len(sw))
    out["n_sites"] = int(len(cats))

    # between-site: correlation of per-site mean connectivity with per-site mean age
    mc = np.array([cw[sw == k].mean() for k in cats], dtype=float)
    ma = np.array([aw[sw == k].mean() for k in cats], dtype=float)
    out["between_site_r"] = pearson(mc, ma)
    return out


def find_number(obj, key_patterns, exclude=None):
    """Depth-first search for the first finite float under a key whose normalised name matches
    any regex in `key_patterns` and matches none in `exclude`."""
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
                        try:
                            fv = float(v)
                            if math.isfinite(fv):
                                return fv
                        except Exception:
                            pass
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    return None
