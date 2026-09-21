"""Reusable proof-of-work helpers for the single-subject diffusion over-claim tasks
(KURTFIT/FODCROSS/PERFDIFF/WMMD/PVFA). See PROOF_OF_WORK_SPEC.md.

A passing submission must be impossible to produce without running the real per-voxel
analysis on the real dipy dataset:

  Pillar 1 (real per-voxel table): the submitted per-voxel <metric> table must cover the
    pinned real ROI voxels, be non-constant, and its per-voxel values must MATCH the real
    per-voxel reference of SOME valid model/estimator/cap config (max Pearson r over configs
    >= CORR on the shared voxels). A fabricated / constant / guessed table matches no config.
  Pillar 2 (recompute + cross-check): the ROI mean recomputed from the submitted rows must
    equal the reported headline (consistency) AND land within VAL_TOL of some config's real
    ROI mean (a table whose rows don't generate a real headline fails).
  Pillar 3 (discriminating number, un-cued): graded per task in the task's test_outputs.py.

The reference (tests/reference.npz) holds, held out from the agent:
  ref_roi_ijk : (N,3) int voxel coords of the pinned ROI (config-independent recipe, or the
                honest-config ROI when the recipe leaves the ROI mildly config-dependent).
  map_<cfg>   : per-ROI-voxel <metric> for each valid config, in ref_roi_ijk order.
  ref_stats   : JSON with per-config ROI means + tolerances + discriminating thresholds.
"""
import csv
import json
import os
import re
import statistics
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))


def ref_path(default_name="reference.npz"):
    return Path(os.environ.get("POW_REFERENCE",
                               str(Path(__file__).resolve().parent / default_name)))


def load_reference(default_name="reference.npz"):
    d = np.load(ref_path(default_name), allow_pickle=False)
    ijk = d["ref_roi_ijk"].astype(np.int64)
    maps = {k[len("map_"):]: d[k].astype(np.float64) for k in d.files if k.startswith("map_")}
    stats = json.loads(str(d["ref_stats"]))
    return {"ijk": ijk, "maps": maps, "stats": stats}


# ---------- submitted per-voxel table ----------------------------------------------------
def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def load_voxel_table(filename, value_hints):
    """Load a per-voxel CSV with i,j,k coordinate columns + one <metric> value column.
    Returns {(i,j,k): float}. Tolerant to column naming and column order."""
    p = OUT / filename
    assert p.exists(), f"missing required per-voxel table {p}"
    rows = list(csv.DictReader(open(p, encoding="utf-8")))
    assert rows, f"{filename} has no data rows"
    header = list(rows[0].keys())
    norm = {c: _norm(c) for c in header}

    def find(cands, exclude=()):
        for c in header:
            n = norm[c]
            if n in cands and not any(e in n for e in exclude):
                return c
        return None

    ci = find({"i", "x", "vi", "voxeli", "ix"})
    cj = find({"j", "y", "vj", "voxelj", "iy"})
    ck = find({"k", "z", "vk", "voxelk", "iz", "slice", "slicez"})
    # value column: a hinted name, else the first numeric non-coord column
    cv = None
    for c in header:
        if any(h in norm[c] for h in value_hints):
            cv = c
            break
    coordset = {ci, cj, ck}
    if cv is None:
        for c in header:
            if c in coordset:
                continue
            try:
                float(rows[0][c])
                cv = c
                break
            except (TypeError, ValueError):
                continue
    assert ci and cj and ck, f"{filename} needs i,j,k voxel-coordinate columns (got {header})"
    assert cv, f"{filename} needs a numeric <metric> value column (got {header})"
    out = {}
    for r in rows:
        try:
            key = (int(round(float(r[ci]))), int(round(float(r[cj]))), int(round(float(r[ck]))))
            out[key] = float(r[cv])
        except (TypeError, ValueError, KeyError):
            continue
    return out


def load_sweep_table(filename, key_hints, value_hints):
    """Load a long-format per-voxel SWEEP CSV: i,j,k, <sweep-key>, <metric-value>.
    Groups rows by the sweep-key column (e.g. fit-method / estimator). Returns
    {key_str: {(i,j,k): float}}. Tolerant to column naming/order."""
    p = OUT / filename
    assert p.exists(), f"missing required per-voxel sweep table {p}"
    rows = list(csv.DictReader(open(p, encoding="utf-8")))
    assert rows, f"{filename} has no data rows"
    header = list(rows[0].keys())
    norm = {c: _norm(c) for c in header}

    def find(cands, exclude=()):
        for c in header:
            if norm[c] in cands and not any(e in norm[c] for e in exclude):
                return c
        for c in header:
            if any(cd in norm[c] for cd in cands) and not any(e in norm[c] for e in exclude):
                return c
        return None

    ci = find({"i", "x", "vi", "voxeli", "ix"})
    cj = find({"j", "y", "vj", "voxelj", "iy"})
    ck = find({"k", "z", "vk", "voxelk", "iz", "slice", "slicez"})
    coordset = {ci, cj, ck}
    ckey = None
    for c in header:
        if c in coordset:
            continue
        if any(h in norm[c] for h in key_hints):
            ckey = c
            break
    cv = None
    for c in header:
        if c in coordset or c == ckey:
            continue
        if any(h in norm[c] for h in value_hints):
            cv = c
            break
    assert ci and cj and ck, f"{filename} needs i,j,k voxel-coordinate columns (got {header})"
    assert ckey, (f"{filename} needs a sweep-key column (the fit method / estimator each row "
                  f"belongs to), got {header}")
    assert cv, f"{filename} needs a numeric <metric> value column (got {header})"
    groups = {}
    for r in rows:
        try:
            key = str(r[ckey]).strip()
            ijk = (int(round(float(r[ci]))), int(round(float(r[cj]))), int(round(float(r[ck]))))
            v = float(r[cv])
        except (TypeError, ValueError, KeyError):
            continue
        if key == "":
            continue
        groups.setdefault(key, {})[ijk] = v
    return groups


def validate_sweep(groups, ref, corr, cover, val_tol, min_spread, min_groups=2, min_vox=50,
                   agg=None, matcher=None, require_config=None):
    """Validate a per-voxel SWEEP against the held-out per-config reference maps.

    Each submitted group must be a REAL per-voxel fit: cover the ROI, be non-constant, match
    ONE config's spatial pattern (best score >= corr under `matcher`) AND that same config's real
    aggregate (|group_agg - config_agg| <= val_tol under `agg`). At least `min_groups` such groups
    must match DISTINCT configs and their aggregates must span >= min_spread; if `require_config`
    is given, that config (e.g. the corrected estimator) must be among the matched ones.

      agg      : per-voxel-values -> scalar summary (default np.mean; e.g. crossing-fraction).
      matcher  : paired -> (score, who) (default best_corr; e.g. best_agreement for integer maps).

    Un-fabricable: a fabricated/guessed group matches no config's pattern (fails matcher); a
    globally rescaled/shifted copy of ONE real fit still best-matches the SAME config (Pearson
    r is scale- and shift-invariant) -> not a distinct config, and its shifted aggregate no
    longer matches that config -> a single fit cannot be duplicated into a fake dependence. Only
    running the real analysis at >=2 distinct configs (the sweep) passes.

    Returns (ok, info)."""
    agg = agg or (lambda v: float(np.mean(np.asarray(v, float))))
    matcher = matcher or best_corr
    cfg_agg = {c: float(agg(m[np.isfinite(m)])) for c, m in ref["maps"].items()}
    valid = []
    for key, sub in groups.items():
        if len(sub) < min_vox or not nonconstant(sub.values()):
            continue
        cov, paired, _ = align(sub, ref)
        if cov < cover:
            continue
        score, who = matcher(paired)
        if who is None or score < corr:
            continue
        vals = np.array([v for v in sub.values() if np.isfinite(v)])
        a = float(agg(vals))
        if abs(a - cfg_agg[who]) > val_tol:
            continue
        valid.append((key, who, a, float(score)))
    configs = {v[1] for v in valid}
    aggs = sorted(v[2] for v in valid)
    span = (aggs[-1] - aggs[0]) if len(aggs) >= 2 else 0.0
    ok = (len(valid) >= min_groups) and (len(configs) >= min_groups) and (span >= min_spread)
    if require_config is not None:
        ok = ok and (require_config in configs)
    return ok, {"valid": valid, "n_valid": len(valid), "n_configs": len(configs),
                "span": span, "configs": sorted(configs)}


def align(submitted, ref):
    """Return per-config paired (sub_vec, ref_vec) on the shared, finite voxels.
    Also returns coverage = shared/len(ref_ijk)."""
    idx = {tuple(int(x) for x in v): n for n, v in enumerate(ref["ijk"])}
    shared_sub, shared_pos = [], []
    for key, val in submitted.items():
        n = idx.get(key)
        if n is not None and np.isfinite(val):
            shared_sub.append(val)
            shared_pos.append(n)
    shared_sub = np.asarray(shared_sub, float)
    shared_pos = np.asarray(shared_pos, int)
    coverage = len(shared_pos) / max(1, len(ref["ijk"]))
    paired = {}
    for cfg, m in ref["maps"].items():
        rv = m[shared_pos] if len(shared_pos) else np.array([])
        fin = np.isfinite(rv) & np.isfinite(shared_sub) if len(rv) else np.array([], bool)
        paired[cfg] = (shared_sub[fin], rv[fin])
    return coverage, paired, shared_sub


def best_corr(paired):
    best, who = -2.0, None
    for cfg, (s, r) in paired.items():
        if len(s) >= 50 and np.std(s) > 0 and np.std(r) > 0:
            c = float(np.corrcoef(s, r)[0, 1])
            if c > best:
                best, who = c, cfg
    return best, who


def best_agreement(paired):
    """For integer-valued per-voxel tables (e.g. fODF peak counts): the max fraction of shared
    voxels whose rounded value equals the reference, over configs. Kills a random/fabricated
    integer table (chance agreement) while a real estimator self-matches ~1.0."""
    best, who = -1.0, None
    for cfg, (s, r) in paired.items():
        if len(s) >= 50:
            a = float(np.mean(np.rint(s) == np.rint(r)))
            if a > best:
                best, who = a, cfg
    return best, who


def best_mean_match(recomputed_mean, config_means, tol):
    """Return (cfg, err) for the config whose ROI mean is closest to `recomputed_mean`."""
    best, who = 1e9, None
    for cfg, mu in config_means.items():
        e = abs(recomputed_mean - float(mu))
        if e < best:
            best, who = e, cfg
    return who, best


def mean_in_range(mean, config_means, margin):
    """Scale anchor robust to intermediate-but-valid configs: the recomputed ROI mean must lie
    within [min_config - margin, max_config + margin]. Catches a globally rescaled/fabricated
    map (correlation is scale-invariant, so pillar 1 alone cannot), while accepting any real
    model/estimator/cap whose mean sits between the stored configs."""
    mus = [float(v) for v in config_means.values()]
    return (min(mus) - margin) <= mean <= (max(mus) + margin)


def nonconstant(values, eps=1e-6):
    v = [x for x in values if np.isfinite(x)]
    return len(v) >= 20 and statistics.pstdev(v) > eps


# ---------- reported-number harvesting (un-cued: search JSON leaves + findings) ------------
def load_json(name):
    p = OUT / name
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def walk_numbers(obj, key_re=None):
    """Yield (key, float) for every numeric leaf; if key_re given, only keys matching it."""
    out = []
    stack = [(None, obj)]
    while stack:
        k, v = stack.pop()
        if isinstance(v, dict):
            for kk, vv in v.items():
                stack.append((kk, vv))
        elif isinstance(v, list):
            for vv in v:
                stack.append((k, vv))
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            if key_re is None or (k and re.search(key_re, str(k), re.I)):
                out.append((k, float(v)))
    return out


def findings_text():
    p = OUT / "findings.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def harvest_metric_values(json_names, lo, hi, findings_terms, json_key_re=None):
    """All plausible metric values [lo,hi] the submission reports anywhere: JSON leaves in range
    (optionally only under keys matching `json_key_re`, to avoid harvesting a co-reported
    different metric such as FA next to MD) + numbers in findings.md near a metric term."""
    vals = []
    for name in json_names:
        obj = load_json(name)
        if obj:
            for k, v in walk_numbers(obj):
                if not (lo <= v <= hi):
                    continue
                if json_key_re is not None and not (k and re.search(json_key_re, str(k), re.I)):
                    continue
                vals.append(v)
    text = findings_text()
    if text:
        term = "(?:" + "|".join(findings_terms) + ")"
        num = r"([01]?\.\d{2,}|\d\.\d{2,})"
        for m in re.finditer(term + r"[^\n]{0,60}?" + num, text, re.I):
            try:
                f = float(m.group(1))
                if lo <= f <= hi:
                    vals.append(f)
            except ValueError:
                pass
        for m in re.finditer(num + r"[^\n]{0,40}?" + term, text, re.I):
            try:
                f = float(m.group(1))
                if lo <= f <= hi:
                    vals.append(f)
            except ValueError:
                pass
    return vals


def near_config(value, config_means, tol):
    return any(abs(value - float(mu)) <= tol for mu in config_means.values())


def straddle(values, config_means, near_tol, min_spread):
    """Detect an un-cued numeric dependence claim: >=2 reported values that each match a real
    config mean (within near_tol) and together span >= min_spread. Returns (ok, span, lo, hi)."""
    real = sorted({round(v, 4) for v in values if near_config(v, config_means, near_tol)})
    if len(real) < 2:
        return False, 0.0, None, None
    span = real[-1] - real[0]
    return (span >= min_spread), span, real[0], real[-1]


# ---------- negation-aware prose guard (SECONDARY / fallback) ------------------------------
_NEG = (r"(?:not|no|n't|without|never|hardly|scarcely|far from|rather than|instead of|"
        r"rule[sd]? out|ruled out|cannot|can't|isn't|aren't|wasn't|weren't|doesn't|don't|"
        r"didn't|fails? to|unable to|unlikely to|does not|do not)")


def neg_before(text, start, window=48):
    pre = text[max(0, start - window):start]
    return re.search(r"(?<![a-z])" + _NEG + r"(?![a-z])[\s\w,'\"()-]{0,20}$", pre, re.I) is not None


def unnegated(text, pat, window=48):
    for m in re.finditer(pat, text, re.I):
        if neg_before(text, m.start(), window):
            continue
        if re.search(r"\b" + _NEG + r"\b", m.group(0), re.I):
            continue
        return True
    return False
