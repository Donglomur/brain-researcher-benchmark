"""Reusable proof-of-work helpers for CLINCONN-001's grader (see PROOF_OF_WORK_SPEC.md).

A passing submission must be IMPOSSIBLE to produce without running the real resting-state
connectivity analysis on the real ds000030 fMRIPrep subjects. These helpers validate the
SUBMITTED per-subject table against a held-out reference built from the oracle run
(tests/reference.npz), recompute the naive group contrast FROM the submitted rows, and expose
the discriminating post-control statistic for the numeric judgement.

Only numpy + stdlib (the verifier installs numpy; nothing else).
"""
import csv
import json
import math
import re
import statistics
from pathlib import Path

import numpy as np


def canon_id(s):
    """Canonical ds000030 subject id = the digit run, leading zeros stripped.
    'sub-10159' -> '10159'."""
    return re.sub(r"\D", "", str(s)).lstrip("0")


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def load_reference(path):
    z = np.load(path, allow_pickle=True)
    ref = {
        "ids": [canon_id(x) for x in z["ref_ids"]],
        "group": [str(x).lower() for x in z["ref_group"]],
        "mean": np.asarray(z["ref_mean"], float),
        "short": np.asarray(z["ref_short"], float),
        "long": np.asarray(z["ref_long"], float),
        "stats": json.loads(str(z["ref_stats"])),
    }
    ref["by_id"] = {i: {"group": g, "mean": m, "short": s, "long": l}
                    for i, g, m, s, l in zip(ref["ids"], ref["group"], ref["mean"],
                                             ref["short"], ref["long"])}
    return ref


def _canon_group(s):
    s = _norm(s)
    if "schz" in s or "schiz" in s or s == "sz" or "patient" in s:
        return "schz"
    if "control" in s or s in ("hc", "con", "ctrl", "td"):
        return "control"
    return s


def load_submitted(path):
    """Return {canon_id: {group, mean, short, long}} from the submitted connectivity.csv.

    Tolerant column matching: subject id, group, mean_fc, short_range_fc, long_range_fc."""
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    if not rows:
        return {}
    headers = list(rows[0].keys())
    norm_to_raw = {}
    for h in headers:
        norm_to_raw.setdefault(_norm(h), h)

    def pick(cands, exclude=()):
        for c in cands:
            if c in norm_to_raw:
                return norm_to_raw[c]
        for nrm, raw in norm_to_raw.items():
            if any(c in nrm for c in cands) and not any(e in nrm for e in exclude):
                return raw
        return None

    id_c = pick(("subjectid", "subject", "participantid", "participant", "subid", "id"))
    grp_c = pick(("group", "diagnosis", "dx"))
    mean_c = pick(("meanfc", "meanconn", "meanconnectivity"), exclude=("short", "long"))
    short_c = pick(("shortrangefc", "shortrange", "shortfc", "short"))
    long_c = pick(("longrangefc", "longrange", "longfc", "long"))
    out = {}
    if id_c is None or short_c is None:
        return out
    for r in rows:
        cid = canon_id(r.get(id_c, ""))
        if not cid:
            continue
        try:
            short = float(r.get(short_c))
        except (TypeError, ValueError):
            continue
        if not math.isfinite(short):
            continue

        def gf(col):
            if col is None:
                return None
            try:
                v = float(r.get(col))
                return v if math.isfinite(v) else None
            except (TypeError, ValueError):
                return None
        out[cid] = {
            "group": _canon_group(r.get(grp_c, "")) if grp_c else "",
            "mean": gf(mean_c), "short": short, "long": gf(long_c)}
    return out


def pearson(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    if len(x) < 3 or np.std(x) == 0 or np.std(y) == 0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def check_subjects_and_values(sub, ref, val_tol, corr_min, cover, match, eps):
    """Pillar 1. Raise AssertionError unless the submitted table is real per-subject work.

    (a) coverage of the reference subjects by real id; (b) non-constant short_range_fc;
    (c) cross-subject corr(submitted short, reference short) >= corr_min AND per-subject abs
    match for >= `match` of matched subjects; (d) the real group label matches for the
    matched subjects (a hard phenotype fact)."""
    ref_ids = set(ref["ids"])
    matched = [i for i in sub if i in ref_ids]
    coverage = len(matched) / max(1, len(ref_ids))
    assert coverage >= cover, (
        f"connectivity.csv covers only {coverage:.1%} of the {len(ref_ids)} real ds000030 "
        f"subjects by id (need >= {cover:.0%}). Fabricated or missing participant ids.")

    sub_short = [sub[i]["short"] for i in matched]
    ref_short = [ref["by_id"][i]["short"] for i in matched]
    assert statistics.pstdev(sub_short) > eps, \
        "submitted short_range_fc is constant across subjects -- not computed per subject"

    rc = pearson(sub_short, ref_short)
    assert math.isfinite(rc) and rc >= corr_min, (
        f"submitted per-subject short-range connectivity does not track the reference "
        f"(cross-subject r={rc:.3f} < {corr_min}). Values were not computed from the real "
        f"fMRIPrep rest timeseries.")
    close = sum(1 for a, b in zip(sub_short, ref_short) if abs(a - b) <= val_tol)
    frac = close / max(1, len(matched))
    assert frac >= match, (
        f"only {frac:.1%} of matched subjects have short_range_fc within {val_tol} of the "
        f"reference (need >= {match:.0%}); the per-subject values are not the real ones.")

    # mean_fc, if present, must also track the reference (second independent per-subject column)
    if all(sub[i]["mean"] is not None for i in matched) and matched:
        sub_mean = [sub[i]["mean"] for i in matched]
        ref_mean = [ref["by_id"][i]["mean"] for i in matched]
        rm = pearson(sub_mean, ref_mean)
        assert math.isfinite(rm) and rm >= corr_min, (
            f"submitted per-subject mean_fc does not track the reference "
            f"(cross-subject r={rm:.3f} < {corr_min}).")

    # group label must match the real phenotype for the matched subjects
    have_grp = [i for i in matched if sub[i]["group"] in ("schz", "control")]
    if have_grp:
        gmatch = sum(1 for i in have_grp if sub[i]["group"] == ref["by_id"][i]["group"])
        gfrac = gmatch / len(have_grp)
        assert gfrac >= cover, (
            f"only {gfrac:.1%} of subjects carry the real diagnosis label (need >= {cover:.0%}); "
            f"the group column is not the real ds000030 phenotype.")
    return matched


def welch_t(a, b):
    """Welch two-sample t (a vs b), NaN if degenerate. Matches scipy.ttest_ind(equal_var=False)."""
    a = np.asarray(a, float); b = np.asarray(b, float)
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return float("nan")
    va, vb = a.var(ddof=1), b.var(ddof=1)
    denom = math.sqrt(va / na + vb / nb)
    if denom == 0:
        return float("nan")
    return float((a.mean() - b.mean()) / denom)


def recompute_naive_short_t(sub, matched, ref):
    """Pillar 2. Recompute the naive short-range Welch t (SCHZ vs CONTROL) FROM the submitted
    rows using the submitted group labels."""
    schz = [sub[i]["short"] for i in matched if sub[i]["group"] == "schz"]
    ctrl = [sub[i]["short"] for i in matched if sub[i]["group"] == "control"]
    return welch_t(schz, ctrl), len(schz), len(ctrl)


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
                        fv = float(v)
                        if math.isfinite(fv):
                            return fv
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    return None


def find_path_number(obj, path_include=(), leaf_re=None, path_exclude=(), prefer=None):
    """Return a finite float leaf value chosen by path + leaf-key matching. Robust to nesting.

    - `path_include`: every token must appear in the joined normalised ancestor path.
    - `leaf_re`: if given, the LEAF key (normalised) must match this regex (identifies the
      quantity, e.g. the t-statistic vs its p-value).
    - `path_exclude`: none of these tokens may appear in the joined path (branch exclusion).
    - `prefer`: among matches, prefer one whose path contains a prefer token; else shallowest.
    """
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


def find_scoped(obj, scope_patterns, key_patterns, exclude=None):
    """Find a number under a sub-object whose key matches a scope pattern (e.g. the
    'short_range_fc' block) then the value key (e.g. 't'). Falls back to a global scoped search
    where the key name itself carries both meanings."""
    exc = [re.compile(e) for e in (exclude or [])]
    scopes = [re.compile(p) for p in scope_patterns]
    keys = [re.compile(p) for p in key_patterns]

    def walk(cur, in_scope):
        if isinstance(cur, dict):
            for k, v in cur.items():
                nk = _norm(k)
                now = in_scope or any(s.search(nk) for s in scopes)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    if now and any(kp.search(nk) for kp in keys) and not any(e.search(nk) for e in exc):
                        fv = float(v)
                        if math.isfinite(fv):
                            return fv
                r = walk(v, now)
                if r is not None:
                    return r
        elif isinstance(cur, list):
            for v in cur:
                r = walk(v, in_scope)
                if r is not None:
                    return r
        return None
    return walk(obj, False)
