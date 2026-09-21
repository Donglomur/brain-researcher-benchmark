"""Reusable proof-of-work helpers for VISCAT-001's grader.

A passing submission must be IMPOSSIBLE to produce without running the real single-neuron analysis
on the real DANDI 000004 MTL units. These helpers validate the SUBMITTED per-neuron table -- a
NEUTRAL intermediate that BOTH a naive and an honest analysis produce (the pinned per-neuron
preferred-category-vs-rest ROC AUC + the category-selective flag) -- against a
reference built from the oracle run (tests/reference.npz; held out of the agent CONTAINER but
PUBLIC in this repo (burned) -- a real eval needs fresh tasks / a server-side reference), then
recomputes the proportion category-selective and the same-trials (naive) mean AUC FROM the submitted
rows and cross-checks them. It does NOT force the held-out judgement (that is graded separately, as
an OR-escape) -- it only proves the per-neuron work is real.
"""
import csv
import math
import re
import statistics

import numpy as np


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def canon_id(s):
    """Canonical neuron id = alphanumeric-lowercase of '<asset stem>__u<unit id>'.

    Robust to case / punctuation ('+', '-', '__') while still rejecting fabricated ids.
    """
    return _norm(s)


def load_reference(path):
    import json
    z = np.load(path, allow_pickle=True)
    ids = [canon_id(x) for x in z["ref_ids"]]
    ref = {
        "ids": ids,
        "auc": np.asarray(z["ref_auc"], dtype=float),
        "sel": np.asarray(z["ref_selective"], dtype=int),
        "ntrials": np.asarray(z["ref_ntrials"], dtype=float),
        "region": [str(x) for x in z["ref_region"]],
        "stats": json.loads(str(z["ref_stats"])),
    }
    ref["by_id"] = {i: (float(a), int(s)) for i, a, s in zip(ids, ref["auc"], ref["sel"])}
    return ref


def _to_bool(v):
    s = str(v).strip().lower()
    if s in ("1", "true", "t", "yes", "y", "sig", "selective", "significant"):
        return 1
    if s in ("0", "false", "f", "no", "n", "ns", "nonselective", "non-selective", ""):
        return 0
    try:
        return 1 if float(s) >= 0.5 else 0
    except ValueError:
        return None


def load_submitted(path, id_cols, auc_cols, sel_cols):
    """Return {canon_id: (auc, sel_or_None)} plus parallel lists. Tolerant column matching."""
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    if not rows:
        return {}, [], []
    headers = list(rows[0].keys())
    norm_to_raw = {}
    for h in headers:
        norm_to_raw.setdefault(_norm(h), h)

    def pick(cands, avoid=()):
        for c in cands:
            if c in norm_to_raw:
                return norm_to_raw[c]
        for nrm, raw in norm_to_raw.items():
            if any(a in nrm for a in avoid):
                continue
            if any(c in nrm for c in cands):
                return raw
        return None

    id_c = pick(id_cols)
    # keep the AUC column away from the selective/flag column
    auc_c = pick(auc_cols, avoid=("select", "flag", "sig"))
    sel_c = pick(sel_cols)
    submitted, auc_list, sel_list = {}, [], []
    if id_c is None or auc_c is None:
        return submitted, auc_list, sel_list
    for r in rows:
        cid = canon_id(r.get(id_c, ""))
        if not cid:
            continue
        try:
            a = float(r.get(auc_c))
        except (TypeError, ValueError):
            continue
        if not math.isfinite(a):
            continue
        s = _to_bool(r.get(sel_c)) if sel_c is not None else None
        submitted[cid] = (a, s)
        auc_list.append(a)
        sel_list.append(s)
    return submitted, auc_list, sel_list


def check_neurons_and_values(submitted, ref, auc_tol=0.03, cover=0.90, corr_min=0.90,
                             val_match=0.80, sel_match=0.80, eps=1e-4):
    """Pillar 1. Raise AssertionError unless the per-neuron table is real per-neuron work.

    (a) coverage: >= `cover` of the reference neurons present by real canonical id;
    (b) non-constant guard on the per-neuron AUC;
    (c) fabrication teeth: cross-neuron Pearson corr(submitted AUC, reference AUC) >= `corr_min`
        AND >= `val_match` of matched neurons within `auc_tol` (the pinned per-neuron new/old AUC is
        deterministic -- impossible to fake without the real firing rates);
    (d) if a selective flag is present, it must agree with the reference for >= `sel_match`.
    """
    ref_ids = set(ref["ids"])
    matched = [i for i in submitted if i in ref_ids]
    coverage = len(matched) / max(1, len(ref_ids))
    assert coverage >= cover, (
        f"submitted per-neuron table covers only {coverage:.1%} of the {len(ref_ids)} real MTL "
        f"neurons by id (need >= {cover:.0%}). Fabricated or missing neuron ids -- use the pinned "
        f"'<asset-stem>__u<unit id>' neuron_id.")

    sub_auc = [submitted[i][0] for i in matched]
    ref_auc = [ref["by_id"][i][0] for i in matched]
    assert statistics.pstdev(sub_auc) > eps, \
        "submitted per-neuron preferred-vs-rest AUC is constant across neurons -- not computed per neuron"

    rc = float(np.corrcoef(sub_auc, ref_auc)[0, 1])
    assert math.isfinite(rc) and rc >= corr_min, (
        f"submitted per-neuron preferred-vs-rest AUC does not track the reference (cross-neuron r={rc:.3f} "
        f"< {corr_min}). The values were not computed from the real recognition firing rates.")

    close = sum(1 for a, b in zip(sub_auc, ref_auc) if abs(a - b) <= auc_tol)
    frac = close / max(1, len(matched))
    assert frac >= val_match, (
        f"only {frac:.1%} of matched neurons have preferred-vs-rest AUC within {auc_tol} of the reference "
        f"(need >= {val_match:.0%}); the per-neuron values are not the real ones.")

    sub_sel = [submitted[i][1] for i in matched]
    if any(s is not None for s in sub_sel):
        agree = sum(1 for i, s in zip(matched, sub_sel)
                    if s is not None and s == ref["by_id"][i][1])
        graded = sum(1 for s in sub_sel if s is not None)
        afrac = agree / max(1, graded)
        assert afrac >= sel_match, (
            f"submitted category-selective flag agrees with the reference for only {afrac:.1%} of "
            f"neurons (need >= {sel_match:.0%}); the selection was not the real rank-sum test.")
    return matched


def recompute_naive_and_prop(submitted, matched, ref):
    """Recompute (proportion memory-selective, naive same-trials mean AUC over selective) FROM the
    submitted rows. Returns (prop, naive_mean, n_selective)."""
    sels = [(submitted[i][0], submitted[i][1]) for i in matched]
    have_flags = [s for _, s in sels if s is not None]
    prop = (sum(1 for s in have_flags if s == 1) / len(have_flags)) if have_flags else float("nan")
    sel_aucs = [a for a, s in sels if s == 1]
    naive = float(np.mean(sel_aucs)) if sel_aucs else float("nan")
    return prop, naive, len(sel_aucs)


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
