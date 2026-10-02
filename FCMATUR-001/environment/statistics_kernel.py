"""Prospective public FCMATUR numerical kernel; no loading or execution on import.

All original parsing/phenotype-token decisions remain outside this module.
``analyze`` accepts normalized source rows and source-close participant scalars.
Source rows define samples/designs/support; accepted scalars alone supply the
downstream estimates. The same reviewed kernel may be copied into public and
private namespaces; this is deliberately not an independent-solver claim.
"""
from dataclasses import dataclass
import math
import numbers

import numpy as np
from scipy import linalg, stats

EPS = np.finfo(np.float64).eps
ACTIVITY_REL = 1e-12
FIDELITY_REL = 1e-6
VALUE_ATOL = VALUE_RTOL = 1e-6
DERIVED_ATOL = DERIVED_RTOL = 1e-6
PHENOTYPE_ATOL, PHENOTYPE_RTOL = 1e-10, 1e-9
EDGE_CLIP = 0.999
CONNECTIVITY_LIMIT = math.atanh(EDGE_CLIP)
MIN_PER_SITE = 5


def require(ok, message):
    if not ok:
        raise ValueError(message)


def _no_python_bool(value):
    if isinstance(value, (list, tuple)):
        for item in value:
            _no_python_bool(item)
    else:
        require(not isinstance(value, (bool, np.bool_)), "Boolean numeric input")


def real(value, name="value"):
    require(isinstance(value, numbers.Real) and not isinstance(value, (bool, np.bool_)),
            f"{name}: real non-Boolean number required")
    result = float(value)
    require(math.isfinite(result), f"{name}: nonfinite")
    return result


def array(value, ndim, name="array"):
    _no_python_bool(value)
    a = np.asarray(value)
    require(a.ndim == ndim and a.dtype.kind in "iuf", f"{name}: real numeric shape/type")
    out = np.array(a, dtype=np.float64, order="C", copy=True)
    require(np.isfinite(out).all(), f"{name}: nonfinite")
    return out


def fsum(values):
    result = math.fsum(float(v) for v in values)
    require(math.isfinite(result), "nonfinite reduction")
    return result


def stable_norm(values):
    v = array(values, 1)
    if not v.size:
        return 0.0
    scale = float(np.max(np.abs(v)))
    if scale == 0:
        return 0.0
    result = scale * math.sqrt(fsum((v / scale) ** 2))
    require(math.isfinite(result), "norm overflow")
    return result


def _center_parts(v):
    if not v.size or np.all(v == v[0]):
        return np.zeros_like(v), 1.0
    # Subtract a source anchor before reduction. In particular, do not divide
    # a large common level first and destroy represented small differences.
    with np.errstate(over="ignore", invalid="ignore"):
        shifted = v - v[0]
    if np.isfinite(shifted).all():
        try:
            average = math.fsum(float(t) for t in shifted) / len(v)
        except OverflowError:
            scale = float(np.max(np.abs(shifted)))
            average = scale * (fsum(shifted / scale) / len(v))
        with np.errstate(over="ignore", invalid="ignore"):
            c = shifted - average
        if np.isfinite(c).all():
            return c, 1.0
    # Opposite extreme finite signs can overflow the anchor difference. This
    # fallback keeps Pearson/column normalization in a safe scaled domain.
    scale = float(np.max(np.abs(v)))
    z = v / scale
    return z - fsum(z) / len(z), scale


def _scaled_center(values):
    c, _ = _center_parts(array(values, 1))
    scale = float(np.max(np.abs(c))) if c.size else 0.0
    return c / scale if scale else c


def center(values):
    """Accurate anchor-centered reduction before projection; constant guard."""
    centered, scale = _center_parts(array(values, 1))
    with np.errstate(over="ignore", invalid="ignore"):
        result = np.ascontiguousarray(centered * scale, dtype=np.float64)
    require(np.isfinite(result).all(), "centered value overflow")
    return result


def mean(values):
    v = array(values, 1)
    require(v.size > 0, "empty mean")
    if np.all(v == v[0]):
        return float(v[0])
    try:
        return math.fsum(float(t) for t in v) / len(v)
    except OverflowError:
        scale = float(np.max(np.abs(v)))
        return scale * (fsum(v / scale) / len(v))


def dot(x, y):
    a, b = array(x, 1), array(y, 1)
    require(a.shape == b.shape, "dot shape")
    with np.errstate(over="raise", invalid="raise"):
        return fsum(a * b)


def pearson(x, y):
    """Signed Pearson; zero support is None, not an epsilon denominator.

    Exact equal/opposite normalized vectors return exactly +/-1. Otherwise
    the accurately summed normalized dot is clipped only for float roundoff.
    """
    a = _scaled_center(x)
    b = _scaled_center(y)
    require(a.shape == b.shape, "Pearson shape")
    na, nb = stable_norm(a), stable_norm(b)
    if len(a) < 2 or na == 0 or nb == 0:
        return None
    a, b = a / na, b / nb
    if np.array_equal(a, b):
        return 1.0
    if np.array_equal(a, -b):
        return -1.0
    value = dot(a, b)
    require(abs(value) <= 1 + 64 * EPS, "Pearson numerical domain")
    return float(np.clip(value, -1.0, 1.0))


def connectivity(time_by_column):
    """Signed equal-edge mean Fisher-z on all canonical nonconstant columns.

    No source loading, near-constant cutoff, abs(), diagonal, imputation or
    shrinkage. Column normalization before the matrix product avoids overflow.
    """
    raw = array(time_by_column, 2, "source ROI table")
    n, p = raw.shape
    require(n >= 2 and p >= 1, "source ROI dimensions")
    normalized = []
    active = np.zeros(p, dtype=bool)
    for j in range(p):
        c = _scaled_center(raw[:, j])
        norm = stable_norm(c)
        if norm > 0:
            active[j] = True
            normalized.append(c / norm)
    k = len(normalized)
    out = dict(n_frames=n, n_columns=p, active_columns=active.tolist(),
               n_active_columns=k, n_edges=k * (k - 1) // 2,
               connectivity=None, status="insufficient_active_columns")
    if k < 2:
        return out
    z = np.ascontiguousarray(np.column_stack(normalized), dtype=np.float64)
    r = z.T @ z
    edges = r[np.triu_indices(k, k=1)]
    require(np.isfinite(edges).all() and np.max(np.abs(edges)) <= 1 + 64 * EPS,
            "source correlation numerical domain")
    fisher = np.arctanh(np.clip(edges, -EDGE_CLIP, EDGE_CLIP))
    out.update(connectivity=fsum(fisher) / len(fisher), status="ok")
    return out


@dataclass(frozen=True)
class Projection:
    design: np.ndarray
    column_ids: tuple
    basis: np.ndarray
    singular_values: np.ndarray
    rank: int
    cutoff: float

    def residual(self, values):
        v = center(values)
        require(len(v) == self.design.shape[0], "projection row count")
        # Accurate centering occurs BEFORE the nuisance projector. Association
        # is fixed: U @ (U.T @ centered), not a materialized dense projector.
        return np.ascontiguousarray(v - self.basis @ (self.basis.T @ v))


def projection(design, column_ids):
    d = array(design, 2, "design")
    ids = tuple(column_ids)
    require(len(ids) == d.shape[1] and len(set(ids)) == len(ids) and
            all(type(v) is str and v for v in ids), "design column identities")
    require(ids and ids[0] == "intercept" and np.all(d[:, 0] == 1), "design intercept")
    if not d.shape[0]:
        return Projection(d, ids, np.zeros((0, 0)), np.zeros(0), 0, 0.0)
    u, s, _ = linalg.svd(d, full_matrices=False, check_finite=True, lapack_driver="gesvd")
    cutoff = max(d.shape) * EPS * float(s[0]) if len(s) else 0.0
    keep = s > cutoff
    return Projection(d, ids, np.ascontiguousarray(u[:, keep]), s, int(keep.sum()), cutoff)


def nuisance_design(n, *, sites=None, covariates=None):
    require(type(n) is int and n >= 0, "row count")
    cols, names = [np.ones(n)], ["intercept"]
    if sites is not None:
        require(len(sites) == n and all(type(v) is str and v for v in sites), "site identities")
        for site in sorted(set(sites))[1:]:
            cols.append(np.array([v == site for v in sites], dtype=np.float64))
            names.append("site:" + site)
    if covariates is not None:
        require(type(covariates) is dict, "covariates mapping")
        for key in sorted(covariates):
            require(type(key) is str and key and not key.startswith("site:") and key != "intercept",
                    "covariate identity")
            v = array(covariates[key], 1, key)
            require(len(v) == n, "covariate row count")
            cols.append(v)
            names.append(key)
    return projection(np.column_stack(cols), names)


def supported(canonical_direction, original_canonical):
    residual_norm = stable_norm(center(canonical_direction))
    original_norm = stable_norm(center(original_canonical))
    threshold = ACTIVITY_REL * original_norm
    return dict(active=bool(original_norm > 0 and residual_norm > threshold),
                centered_norm=residual_norm, original_centered_norm=original_norm,
                activity_threshold=threshold)


def fidelity(accepted_direction, canonical_direction, support):
    a, b = center(accepted_direction), center(canonical_direction)
    require(a.shape == b.shape, "fidelity shape")
    if support["active"]:
        error = stable_norm(a - b)
        require(error <= FIDELITY_REL * support["centered_norm"], "centered/projected fidelity")


def _status_fields(status):
    return dict(r=None, t=None, p=None, ci95=None, estimate_status=status,
                t_status=status, p_status=status, ci_status=status)


def correlation_inference(r, df):
    require(type(df) is int, "integer degrees of freedom")
    value = real(r, "r")
    require(-1 <= value <= 1, "r domain")
    out = dict(r=value, t=None, p=None, ci95=None, estimate_status="ok",
               t_status="nonpositive_df", p_status="nonpositive_df", ci_status="insufficient_ci_df")
    if abs(value) == 1:
        out["estimate_status"] = "perfect_correlation"
        out["ci_status"] = "perfect_correlation"
        if df > 0:
            out.update(p=0.0, t_status="infinite_t", p_status="perfect_correlation_limit")
        return out
    if df > 0:
        t = value * math.sqrt(df / (1 - value * value))
        out.update(t=t, p=float(2 * stats.t.sf(abs(t), df)), t_status="ok", p_status="ok")
    if df > 1:
        z = math.atanh(value)
        width = float(stats.norm.ppf(.975)) / math.sqrt(df - 1)
        out.update(ci95=[math.tanh(z - width), math.tanh(z + width)], ci_status="ok")
    return out


def added_term_inference(gain, error, df1, df2, denominator_active):
    gain, error = real(gain, "gain"), real(error, "error")
    require(gain >= 0 and error >= 0, "nonnegative sums of squares")
    require(type(df1) is int and type(df2) is int and type(denominator_active) is bool,
            "typed F support/df")
    out = dict(F_added_quadratic=None, p_added_quadratic=None)
    if df1 <= 0:
        out["status"] = "no_added_rank"
    elif df2 <= 0:
        out["status"] = "nonpositive_residual_df"
    elif not denominator_active:
        out["status"] = "inactive_full_model_residual"
    elif error == 0 or error / df2 == 0:
        # Support was established from stable unsquared norms, so a zero here
        # is representational underflow, not a true exact-zero residual.
        out["status"] = "numerical_underflow"
    else:
        value = (gain / df1) / (error / df2)
        if not math.isfinite(value):
            out["status"] = "numerical_overflow"
        elif gain > 0 and value == 0:
            out["status"] = "numerical_underflow"
        else:
            out.update(F_added_quadratic=value, p_added_quadratic=float(stats.f.sf(value, df1, df2)),
                       status="ok")
    return out


def association(x, y, canonical_y, model, *, ids=None, unit="participant"):
    x, y, ref = array(x, 1), array(y, 1), array(canonical_y, 1)
    require(x.shape == y.shape == ref.shape and len(x) == model.design.shape[0], "association shape")
    require(unit in ("participant", "site"), "association unit")
    keys = list(ids) if ids is not None else [str(i) for i in range(len(x))]
    require(len(keys) == len(x) and len(set(keys)) == len(keys) and
            all(type(v) is str and v for v in keys), "association identities")
    rx, ry0, ry = model.residual(x), model.residual(ref), model.residual(y)
    sx, sy = supported(rx, x), supported(ry0, ref)
    fidelity(ry, ry0, sy)
    out = dict(unit=unit, ids=keys, n=len(x), column_ids=list(model.column_ids),
               rank=model.rank, df=len(x) - model.rank - 1,
               age_support=sx, connectivity_support=sy)
    if len(x) < 2:
        status = "insufficient_sample"
    elif not sx["active"] and not sy["active"]:
        status = "inactive_age_and_connectivity"
    elif not sx["active"]:
        status = "inactive_age"
    elif not sy["active"]:
        status = "inactive_connectivity"
    else:
        value = pearson(rx, ry)
        require(value is not None, "accepted active correlation lost support")
        out.update(correlation_inference(value, out["df"]))
        return out
    out.update(_status_fields(status))
    return out


def quadratic(age, y, canonical_y, *, ids=None):
    age, y, ref = array(age, 1), array(y, 1), array(canonical_y, 1)
    require(age.shape == y.shape == ref.shape, "quadratic shape")
    n = len(age)
    keys = list(ids) if ids is not None else [str(i) for i in range(n)]
    require(len(keys) == n and len(set(keys)) == n and
            all(type(v) is str and v for v in keys), "quadratic identities")
    out = dict(ids=keys, n=n, base_rank=0, full_rank=0, added_rank=0, df1=0, df2=n,
               added_norm=None, added_cutoff=None, added_basis_orthogonality=None,
               quadratic_beta=None, beta_status="inactive_age", gain_ss=None,
               rss_linear=None, rss_quadratic=None, F_added_quadratic=None,
               p_added_quadratic=None, status="inactive_age")
    age_centered = center(age)
    norm = stable_norm(age_centered)
    if n < 2 or norm == 0:
        out["status"] = "insufficient_sample" if n < 2 else "inactive_age"
        out.update(base_rank=int(n > 0), full_rank=int(n > 0), df2=n - int(n > 0))
        return out
    az = age_centered / (norm / math.sqrt(n))
    base = projection(np.column_stack([np.ones(n), az]), ["intercept", "standardized_age"])
    q = az * az
    h = base.residual(base.residual(q))
    hn = stable_norm(h)
    cutoff = max(n, 3) * EPS * stable_norm(q)
    add = int(hn > cutoff)
    out.update(base_rank=base.rank, full_rank=base.rank + add, added_rank=add,
               df1=add, df2=n - base.rank - add, added_norm=hn, added_cutoff=cutoff)
    e0, e00 = base.residual(y), base.residual(ref)
    s0 = supported(e00, ref)
    fidelity(e0, e00, s0)
    out.update(linear_residual_support=s0, rss_linear=dot(e0, e0))
    if not add:
        out.update(status="no_added_rank", beta_status="no_added_rank",
                   rss_quadratic=out["rss_linear"])
        return out
    u = h / hn
    # One nested R1 for source support, fidelity, gain and denominator. There is
    # no independent X1-SVD rank/estimability or orthogonality acceptance gate.
    a, a0 = dot(u, e0), dot(u, e00)
    e1, e10 = e0 - u * a, e00 - u * a0
    s1 = supported(e10, ref)
    fidelity(e1, e10, s1)
    gain, error = a * a, dot(e1, e1)
    beta = a / hn
    require(math.isfinite(gain) and math.isfinite(beta), "quadratic overflow")
    out.update(quadratic_beta=beta, beta_status="ok", gain_ss=gain, rss_quadratic=error,
               full_residual_support=s1,
               added_basis_orthogonality=float(np.max(np.abs(base.basis.T @ u))))
    if a != 0 and gain == 0 and out["df2"] > 0 and s1["active"]:
        # A nonzero added coefficient whose square underflows must not be
        # relabelled the exact G=0,F=0,p=1 case.
        out.update(F_added_quadratic=None, p_added_quadratic=None, status="numerical_underflow")
    else:
        out.update(added_term_inference(gain, error, 1, out["df2"], s1["active"]))
    return out


def _rows(rows):
    require(isinstance(rows, (list, tuple)), "source rows")
    out, seen = [], set()
    fields = {"subject", "connectivity", "age", "site_id", "mean_fd", "sex", "typical_control"}
    for row in rows:
        require(type(row) is dict and fields <= row.keys(), "normalized source row fields")
        sid = row["subject"]
        require(type(sid) is str and sid and sid not in seen, "literal unique subject ID")
        seen.add(sid)
        r = {key: row[key] for key in fields}
        for key in ("connectivity", "age", "mean_fd", "sex"):
            if r[key] is not None:
                r[key] = real(r[key], key)
        if r["connectivity"] is not None:
            require(abs(r["connectivity"]) <= CONNECTIVITY_LIMIT + 8 * EPS,
                    "source connectivity domain")
        require(r["site_id"] is None or (type(r["site_id"]) is str and bool(r["site_id"])),
                "normalized site identity")
        require(r["typical_control"] is None or type(r["typical_control"]) is bool,
                "normalized typical-control flag")
        out.append(r)
    return sorted(out, key=lambda r: r["subject"])


def validate_values(rows, accepted, *, atol=VALUE_ATOL, rtol=VALUE_RTOL):
    atol, rtol = real(atol, "atol"), real(rtol, "rtol")
    require(atol >= 0 and rtol >= 0, "nonnegative tolerances")
    require(type(accepted) is dict and set(accepted) == {r["subject"] for r in rows},
            "complete accepted participant keys")
    out = {}
    for row in rows:
        sid, canonical = row["subject"], row["connectivity"]
        if canonical is None:
            require(accepted[sid] is None, "canonical undefined participant")
            out[sid] = None
        else:
            value = real(accepted[sid], "accepted connectivity")
            # A receipt may round outward at the canonical Fisher cap. This
            # exception applies ONLY to serialized participant connectivity.
            require(abs(value) <= CONNECTIVITY_LIMIT + atol + rtol * CONNECTIVITY_LIMIT,
                    "accepted connectivity serialized domain")
            require(abs(value - canonical) <= atol + rtol * abs(canonical), "participant source fidelity")
            out[sid] = value
    return out


def analyze(canonical_rows, accepted_connectivity, *, value_atol=VALUE_ATOL, value_rtol=VALUE_RTOL):
    """Three levels + existing five sensitivities from one accepted-y replay.

    Row fields are normalized upstream; this function never decides raw token
    mappings. mean_fd/sex None means ineligible for that adjustment. The caller
    supplies a true/false/None typical_control flag after documentary decoding.
    Returns JSON-compatible finite primitives/nulls; no source I/O or writes.
    """
    rows = _rows(canonical_rows)
    accepted = validate_values(rows, accepted_connectivity, atol=value_atol, rtol=value_rtol)
    base = [r for r in rows if r["connectivity"] is not None and r["age"] is not None and 0 < r["age"] < 120]
    sites = sorted({r["site_id"] for r in base if r["site_id"] is not None})
    site_counts = {s: sum(r["site_id"] == s for r in base) for s in sites}
    eligible_sites = [s for s in sites if site_counts[s] >= MIN_PER_SITE]
    within = [r for r in base if r["site_id"] in eligible_sites]

    def vectors(sample):
        return ([r["age"] for r in sample], [accepted[r["subject"]] for r in sample],
                [r["connectivity"] for r in sample], [r["subject"] for r in sample])

    def estimate(sample, site_adjustment=False, covariate=None):
        x, y, ref, ids = vectors(sample)
        covs = None if covariate is None else {covariate: [r[covariate] for r in sample]}
        model = nuisance_design(len(sample), sites=[r["site_id"] for r in sample] if site_adjustment else None,
                                covariates=covs)
        return association(x, y, ref, model, ids=ids)

    # Explicit base-direction check also protects the nonlinear and site-mean
    # calculations; later projected directions are checked on their own scales.
    _, by, bref, _ = vectors(base)
    fidelity(by, bref, supported(bref, bref))
    site_means, site_source_means = [], []
    for site in eligible_sites:
        sample = [r for r in within if r["site_id"] == site]
        x, y, ref, ids = vectors(sample)
        site_means.append(dict(site_id=site, ids=ids, n=len(sample), mean_age=mean(x),
                               mean_connectivity=mean(y)))
        site_source_means.append(mean(ref))
    between = association([r["mean_age"] for r in site_means],
                          [r["mean_connectivity"] for r in site_means], site_source_means,
                          nuisance_design(len(site_means)), ids=eligible_sites, unit="site")

    def sensitivity(sample, covariate=None):
        return dict(ids=[r["subject"] for r in sample], n=len(sample),
                    site_counts={s: sum(r["site_id"] == s for r in sample)
                                 for s in sorted({r["site_id"] for r in sample})},
                    pooled=estimate(sample, covariate=covariate),
                    within_site=estimate(sample, True, covariate))

    motion = [r for r in within if r["mean_fd"] is not None]
    sex = [r for r in within if r["sex"] is not None]
    controls = [r for r in within if r["typical_control"] is True]
    per_site = []
    for site in eligible_sites:
        sample = [r for r in within if r["site_id"] == site]
        rec = estimate(sample)
        x, y, _, _ = vectors(sample)
        cx, cy = center(x), center(y)
        xn = stable_norm(cx)
        slope = dot(cx / xn, cy) / xn if xn > 0 else None
        rec.update(site_id=site, slope=slope, slope_status="ok" if xn > 0 else "inactive_age")
        per_site.append(rec)
    defined = [r["r"] for r in per_site if r["r"] is not None]
    complete = bool(per_site) and len(defined) == len(per_site)
    site_summary = dict(n_expected=len(per_site), n_defined=len(defined), per_site=per_site,
                        status="ok" if complete else "incomplete_support",
                        median_within_site_r=float(np.median(defined)) if complete else None,
                        frac_sites_positive=sum(v > 0 for v in defined) / len(defined) if complete else None,
                        n_sites_positive=sum(v > 0 for v in defined) if complete else None,
                        min_r=min(defined) if complete else None, max_r=max(defined) if complete else None)
    x, y, ref, ids = vectors(base)
    within_ids, motion_ids, sex_ids, control_ids = (
        {r["subject"] for r in sample} for sample in (within, motion, sex, controls))
    base_ids = set(ids)
    ledger = []
    for row in rows:
        sid = row["subject"]
        if row["connectivity"] is None:
            reason = "undefined_source_connectivity"
        elif row["age"] is None:
            reason = "missing_age"
        elif not 0 < row["age"] < 120:
            reason = "age_outside_open_0_120"
        else:
            reason = "included"
        ledger.append(dict(subject=sid, base_eligible=sid in base_ids, base_reason=reason,
                           within_eligible=sid in within_ids, motion_eligible=sid in motion_ids,
                           sex_eligible=sid in sex_ids, control_eligible=sid in control_ids))
    return dict(n_source=len(rows), n_base=len(base), n_within=len(within),
                eligible_site_ids=eligible_sites, all_base_site_counts=site_counts, cohort=ledger,
                pooled=estimate(base), within_site=estimate(within, True), between_site=between,
                site_means=site_means,
                sensitivity=dict(motion=sensitivity(motion, "mean_fd"),
                                 diagnosis=sensitivity(controls), sex=sensitivity(sex, "sex"),
                                 nonlinear_age=quadratic(x, y, ref, ids=ids), site_specific_slopes=site_summary))
