"""Reusable proof-of-work helpers for MAPREL-001 (see PROOF_OF_WORK_SPEC.md).

A passing submission must be impossible to produce without actually parcellating the two real
neuromaps annotations (Margulies-2016 fcgradient02 and HCP-S1200 thickness) with the pinned
Schaefer-400 atlas: the per-parcel map values must be the REAL ones (validated against a
held-out reference by cross-parcel correlation), the observed correlation must recompute from
those rows, and the volunteered spatial-autocorrelation-preserving (spin) null result must be
reported -- the honest quantity a naive parametric test cannot produce.
"""
import csv
import json
import math
import re
from pathlib import Path

import numpy as np


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def load_reference(path):
    z = np.load(path, allow_pickle=True)
    pid = [str(x) for x in z["ref_pid"]]
    ref = {
        "pid": pid,
        "grad": {i: float(v) for i, v in zip(pid, np.asarray(z["ref_grad"], float))},
        "thick": {i: float(v) for i, v in zip(pid, np.asarray(z["ref_thick"], float))},
        "stats": json.loads(str(z["ref_stats"])),
    }
    return ref


def _pick(headers, cands):
    norm_to_raw = {}
    for h in headers:
        norm_to_raw.setdefault(_norm(h), h)
    for c in cands:
        if c in norm_to_raw:
            return norm_to_raw[c]
    for nrm, raw in norm_to_raw.items():
        if any(c in nrm for c in cands):
            return raw
    return None


def load_submitted(path):
    """Return {parcel_id: (gradient, thickness)} from parcels.csv (tolerant columns)."""
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    if not rows:
        return {}
    headers = list(rows[0].keys())
    id_c = _pick(headers, ("parcelid", "parcel", "roiid", "roi", "region", "id", "label"))
    g_c = _pick(headers, ("gradient2", "gradient", "grad", "fcgradient02", "fcgradient",
                          "mapa", "gradient02", "grad2"))
    t_c = _pick(headers, ("thickness", "corticalthickness", "thick", "mapb"))
    out = {}
    for r in rows:
        pid = str(r.get(id_c, "")).strip() if id_c else ""
        if not pid:
            continue
        try:
            g = float(r.get(g_c)); t = float(r.get(t_c))
        except (TypeError, ValueError):
            continue
        if math.isfinite(g) and math.isfinite(t):
            out[pid] = (g, t)
    return out


def matched_ids(sub, ref_pid):
    # match parcel ids robustly (tolerate '1' vs '1.0' vs 'Parcel_1' by digit run)
    def digits(s):
        d = re.sub(r"\D", "", str(s))
        return d.lstrip("0") or ("0" if d else "")
    sub_by_d = {}
    for k in sub:
        sub_by_d.setdefault(digits(k), k)
    out = []
    for p in ref_pid:
        d = digits(p)
        if d in sub_by_d:
            out.append((p, sub_by_d[d]))
    return out


def coverage(sub, ref_pid):
    return len(matched_ids(sub, ref_pid)) / max(1, len(ref_pid))


def _corr(a, b):
    if len(a) < 3 or np.std(a) == 0 or np.std(b) == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def cross_corr(sub, ref_map, ref_pid, idx):
    pairs = matched_ids(sub, ref_pid)
    a = [sub[sk][idx] for _, sk in pairs]
    b = [ref_map[rp] for rp, _ in pairs]
    return _corr(a, b), len(pairs)


def recompute_abs_r(sub, ref_pid):
    pairs = matched_ids(sub, ref_pid)
    g = [sub[sk][0] for _, sk in pairs]
    t = [sub[sk][1] for _, sk in pairs]
    return abs(_corr(g, t))


def nonconstant(sub, idx, eps=1e-6):
    vals = [sub[k][idx] for k in sub if math.isfinite(sub[k][idx])]
    return len(vals) >= 3 and float(np.std(vals)) > eps


def collect_numbers_by_key(obj, key_re, exclude_re=None):
    out = []
    exc = re.compile(exclude_re) if exclude_re else None
    pat = re.compile(key_re)

    def walk(o, matched=False, excluded=False):
        if isinstance(o, dict):
            for k, v in o.items():
                nk = _norm(k)
                walk(v, matched or bool(pat.search(nk)), excluded or bool(exc and exc.search(nk)))
        elif isinstance(o, list):
            for v in o:
                walk(v, matched, excluded)
        elif isinstance(o, (int, float)) and not isinstance(o, bool):
            if matched and not excluded:
                out.append(float(o))
    walk(obj)
    return out


def numbers_with_path(obj):
    """Yield (normalised_key_path, value) for every numeric leaf. The path is the '/'-joined
    normalised keys of all ancestors plus the leaf's own key, so a test can require several
    concepts to co-occur on the path (e.g. a spin-test p-value) without brittle key guessing."""
    out = []

    def walk(o, path=""):
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, path + "/" + _norm(k))
        elif isinstance(o, list):
            for idx, v in enumerate(o):
                walk(v, path + "/" + str(idx))
        elif isinstance(o, (int, float)) and not isinstance(o, bool):
            out.append((path, float(o)))
    walk(obj)
    return out


def spatial_null_p(blobs):
    """Reported spatial-autocorrelation-preserving (spin/surrogate) null p-value(s), in [0,1].
    Requires a spatial-null concept AND a p-value marker on the key path, excluding the null's
    mean/sd/count/rotation fields."""
    concept = re.compile(r"spin|spun|spatialnull|spatial|surrogate|surr|rotat|variogram|"
                         r"brainsmash|smash|moran|autocorr|geodesic|vasa|alexanderbloch")
    pmark = re.compile(r"(?:^|/)p(?:value|val|spin|spatial|surr\w*|perm|rot\w*)?$|pvalue|pval|"
                       r"/p[a-z]*$|significancep|_p$|(?<![a-z])p(?:spin|spatial|surr|perm|rot)")
    excl = re.compile(r"mean|sd|std|variance|\bvar\b|nperm|npermut|nrot|nrotate|count|null_?m|"
                      r"observed|obsr|effectsize|nsampl")
    vals = []
    for blob in blobs.values():
        for path, v in numbers_with_path(blob):
            if not (0.0 <= v <= 1.0):
                continue
            if concept.search(path) and pmark.search(path) and not excl.search(path):
                vals.append(v)
    return vals


def parametric_p(blobs):
    """Reported parametric / analytic (or label-shuffle) p-value(s): a p-value marker on the
    path, NOT under a spatial-null concept."""
    concept = re.compile(r"spin|spun|spatialnull|surrogate|surr|rotat|variogram|brainsmash|"
                         r"smash|moran|autocorr|geodesic")
    pmark = re.compile(r"pparametric|parametricp|panalytic|analyticp|pnominal|pasympt|pshuffle|"
                       r"labelshufflep|plabel|pvalueparam|(?:^|/)pvalue$|(?:^|/)pval$|(?:^|/)p$")
    excl = re.compile(r"mean|sd|std|nperm|count|spin|spatial|surr")
    vals = []
    for blob in blobs.values():
        for path, v in numbers_with_path(blob):
            if not (0.0 <= v <= 1.0):
                continue
            if pmark.search(path) and not concept.search(path) and not excl.search(path):
                vals.append(v)
    return vals


def spin_null_sd(blobs):
    """Reported SD/width of the spin/surrogate null distribution (a real spatial null is wide)."""
    key = re.compile(r"(?:spin|surrogate|surr|spatial|rotat|variogram|smash|null).*"
                     r"(?:sd|std|standarddev|width|scale)|(?:sd|std).*(?:spin|surrogate|null)")
    vals = []
    for blob in blobs.values():
        for path, v in numbers_with_path(blob):
            if key.search(path) and math.isfinite(v):
                vals.append(abs(v))
    return vals


def find_null_distribution(blobs, out_dir=None, min_len=100):
    """Find the submitted spatial-null / surrogate correlation DISTRIBUTION: the array of
    correlation values from the sampling procedure the agent used to assess significance. Search
    JSON numeric lists under a null/spin/surrogate/sampling-tagged key path (values in [-1,1]), and
    a few sidecar file names. Returns a numpy array or None.

    The grader recomputes the p-value from this distribution and validates its spread, so it cannot
    be replaced by a reported scalar and a fabricated flat/narrow (parametric-sized) null fails."""
    concept = re.compile(r"spin|spun|surrogate|surr|null|rotat|variogram|brainsmash|smash|permut|"
                         r"resampl|sampling|spatial|bootstrap|montecarlo")
    candidates = []

    def consider(nums, path):
        if len(nums) < min_len:
            return
        arr = np.asarray(nums, float)
        if not np.all(np.isfinite(arr)):
            arr = arr[np.isfinite(arr)]
            if len(arr) < min_len:
                return
        inrange = float(np.mean((arr >= -1.01) & (arr <= 1.01)))
        if concept.search(path) and inrange >= 0.9:
            candidates.append(arr)

    def walk(o, path=""):
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, path + "/" + _norm(k))
        elif isinstance(o, list):
            nums = [x for x in o if isinstance(x, (int, float)) and not isinstance(x, bool)]
            if len(nums) == len(o) and nums:
                consider(nums, path)
            else:
                for v in o:
                    walk(v, path)

    for blob in blobs.values():
        walk(blob)
    if candidates:
        # If several null arrays are provided (e.g. a spin null AND a naive label-shuffle null),
        # take the WIDEST -- the grader assesses the spatial-autocorrelation-preserving null, which
        # is wide; a submission that provides only a narrow shuffle null is then correctly judged
        # against that narrow null (and fails, as it should).
        return max(candidates, key=lambda a: float(np.std(a)))
    if out_dir is not None:
        for name in ("spin_null.csv", "null_distribution.csv", "spin_null.txt", "null.csv",
                     "surrogate_correlations.csv", "spin_null_distribution.csv", "spin_nulls.csv",
                     "null_correlations.csv"):
            p = Path(out_dir) / name
            if p.exists():
                try:
                    vals = [float(x) for x in re.split(r"[\s,]+", p.read_text().strip()) if x]
                    vals = [v for v in vals if math.isfinite(v)]
                    if len(vals) >= min_len:
                        return np.asarray(vals, float)
                except Exception:
                    pass
    return None


def recompute_spin_p(r_obs, null):
    """Two-tailed spatial-null p = fraction of the null correlations whose magnitude is at least the
    observed |r|. Sign-robust (the gradient sign convention is arbitrary; the null is ~symmetric)."""
    null = np.asarray(null, float)
    null = null[np.isfinite(null)]
    if len(null) < 1:
        return float("nan")
    return float(np.sum(np.abs(null) >= abs(r_obs)) / len(null))


def find_bool_by_key(obj, key_re):
    out = []
    pat = re.compile(key_re)

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if pat.search(_norm(k)):
                    if isinstance(v, bool):
                        out.append(v)
                    elif isinstance(v, str):
                        s = v.strip().lower()
                        if s in ("true", "yes", "significant", "sig"):
                            out.append(True)
                        elif s in ("false", "no", "notsignificant", "ns", "nonsignificant",
                                   "not_significant", "not significant"):
                            out.append(False)
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(obj)
    return out
