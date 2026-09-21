"""Reusable proof-of-work helpers for NETINTEG-001's grader.

A passing submission must be IMPOSSIBLE to produce without running the real density-matched
global-efficiency analysis on the real ADHD-200 participants. These helpers validate the
submitted per-participant efficiency.csv against a reference built from the oracle
(tests/reference.npz; held out of the agent CONTAINER but PUBLIC in this repo (burned) -- a real
eval needs fresh tasks / a server-side reference), recompute the efficiency<->overall-strength
confound correlation FROM
the submitted rows, and expose the discriminating absolute-vs-density-matched contrast.
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


def load_reference(path):
    z = np.load(path, allow_pickle=True)
    # conn_pos = a GSR-robust positive/absolute strength proxy (mean over positive edges).
    # Signed mean FC is centred to ~0 under global-signal regression, so the density confound
    # must be measured against a positive-strength proxy to be pipeline-robust.
    conn_pos = z["ref_conn_pos"] if "ref_conn_pos" in z.files else z["ref_conn"]
    ref = {
        "ids": [canon_id(x) for x in z["ref_ids"]],
        "eff": np.asarray(z["ref_eff"], dtype=float),
        "conn": np.asarray(z["ref_conn"], dtype=float),
        "conn_pos": np.asarray(conn_pos, dtype=float),
        "eff_abs": np.asarray(z["ref_eff_abs"], dtype=float),
        "stats": json.loads(str(z["ref_stats"])),
    }
    ref["by_id"] = {i: (float(e), float(c)) for i, e, c in zip(ref["ids"], ref["eff"], ref["conn"])}
    return ref


def load_submitted(path, id_cols, eff_cols, conn_cols):
    """Return {canon_id: (efficiency, mean_connectivity_or_nan)}."""
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    if not rows:
        return {}
    headers = list(rows[0].keys())
    norm_to_raw = {}
    for h in headers:
        norm_to_raw.setdefault(_norm(h), h)

    def pick(cands, exclude=()):
        for c in cands:
            if c in norm_to_raw and not any(e in c for e in exclude):
                return norm_to_raw[c]
        for nrm, raw in norm_to_raw.items():
            if any(c in nrm for c in cands) and not any(e in nrm for e in exclude):
                return raw
        return None

    id_c = pick(id_cols)
    eff_c = pick(eff_cols)
    conn_c = pick(conn_cols, exclude=("efficiency",))
    submitted = {}
    if id_c is None or eff_c is None:
        return submitted
    for r in rows:
        cid = canon_id(r.get(id_c, ""))
        if not cid:
            continue
        try:
            e = float(r.get(eff_c))
        except (TypeError, ValueError):
            continue
        c = float("nan")
        if conn_c is not None:
            try:
                c = float(r.get(conn_c))
            except (TypeError, ValueError):
                c = float("nan")
        if not math.isfinite(e):
            continue
        submitted[cid] = (e, c)
    return submitted


def pearson(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    if len(x) < 3 or np.std(x) == 0 or np.std(y) == 0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def check_subjects_and_values(submitted, ref, eff_tol, corr_min, cover, match, eps=1e-4):
    """Pillar 1. Raise AssertionError unless the submitted per-participant efficiency is the
    real DENSITY-MATCHED per-subject work: coverage of the real ids, non-constant, and -- the
    PRIMARY teeth -- cross-subject corr(submitted, reference density-matched efficiency) >=
    corr_min (submitting the confounded ABSOLUTE-threshold efficiency instead fails here, the
    two rankings are near-disjoint at r~-0.28; a fabrication gives ~0). The absolute band
    (`eff_tol`) is a secondary sanity check, set wide enough to admit a defensible density-range
    choice (a wider proportional-density sweep shifts efficiency by ~0.05-0.06)."""
    ref_ids = set(ref["ids"])
    matched = [i for i in submitted if i in ref_ids]
    coverage = len(matched) / max(1, len(ref_ids))
    assert coverage >= cover, (
        f"efficiency.csv covers only {coverage:.1%} of the {len(ref_ids)} real ADHD-200 "
        f"participants by id (need >= {cover:.0%}). Fabricated or missing participant ids.")
    sub_eff = [submitted[i][0] for i in matched]
    assert statistics.pstdev(sub_eff) > eps, (
        "submitted global efficiency is constant across participants -- not computed per subject")
    ref_eff = [ref["by_id"][i][0] for i in matched]
    rc = pearson(sub_eff, ref_eff)
    assert math.isfinite(rc) and rc >= corr_min, (
        f"submitted per-participant efficiency does not track the density-matched reference "
        f"(cross-subject r={rc:.3f} < {corr_min}). Either the values were fabricated, or the "
        f"CONFOUNDED absolute-threshold efficiency (which is near-disjoint from the "
        f"density-matched ranking) was submitted as the answer.")
    close = sum(1 for a, b in zip(sub_eff, ref_eff) if abs(a - b) <= eff_tol)
    frac = close / max(1, len(matched))
    assert frac >= match, (
        f"only {frac:.1%} of matched participants have efficiency within {eff_tol} of the "
        f"density-matched reference (need >= {match:.0%}); the per-subject values are not real.")
    return matched


def reference_abs_cross_corr(submitted, ref):
    """Diagnostic: cross-subject corr of the submitted efficiency with the ABSOLUTE reference."""
    ref_ids = set(ref["ids"])
    matched = [i for i in submitted if i in ref_ids]
    by_abs = {i: float(a) for i, a in zip(ref["ids"], ref["eff_abs"])}
    return pearson([submitted[i][0] for i in matched], [by_abs[i] for i in matched])


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


def collect_confound_corrs(objs):
    """Return (abs_corrs, dm_corrs): reported efficiency<->overall-strength correlations tagged
    by convention. Used for the discriminating pillar-3 contrast."""
    abs_corrs, dm_corrs = [], []

    def walk(obj, path=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                walk(v, path + "/" + str(k).lower())
        elif isinstance(obj, list):
            for x in obj:
                walk(x, path)
        elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
            v = float(obj)
            if -1.01 <= v <= 1.01 and re.search(r"corr|strength|confound|_r\b|pearson", path):
                if re.search(r"absolute|abs\b|_abs|fixed|cutoff", path):
                    abs_corrs.append(v)
                elif re.search(r"proportion|densit|match", path):
                    dm_corrs.append(v)
    for o in objs:
        if o is not None:
            walk(o)
    return abs_corrs, dm_corrs
