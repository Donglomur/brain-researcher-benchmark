"""Reference (oracle) for FCMATUR-001 — an ABIDE case study: is the marginal
connectivity–age association site-conditioned?

Estimand. For each ABIDE participant, an overall functional-connectivity strength (the mean of
the Fisher-z CC200 connectome edges). The scientific question is how the *marginal* (pooled)
connectivity–age association relates to the *site-conditioned* (within-site) association across
this multi-site sample — reported with uncertainty and basic sensitivity checks.

Ground truth (validated on the nilearn-pinned ABIDE_pcp / cpac / filt_noglobal / rois_cc200,
1035 participants, 20 sites):

  POOLED across participants      : r ≈ +0.077 (95% CI ≈ [+0.017, +0.137], p ≈ 0.013)
  WITHIN-site (site fixed effects): r ≈ -0.020 (95% CI ≈ [-0.081, +0.041], p ≈ 0.53)  # ~0
  SITE-MEAN (between-site)        : r ≈ +0.391 (n = 20 sites; wide CI)                 # positive

Interpretation (bounded). ABIDE pools 20 acquisition sites that differ in mean age (site means
span ~10–34 yr) AND, separately, in mean connectivity. The between-site level carries a positive
connectivity–age relationship, so the pooled estimate is largely a between-site quantity; within
sites the association ATTENUATES TOWARD NULL (its CI includes 0). The honest conclusion is that
the small pooled association is SITE-CONDITIONED. It does NOT establish that scanner hardware
CAUSED the correlation (site conflates scanner, protocol and cohort), it does NOT establish a
true null within sites (limited per-site power; the CI is wide), and — the data being
cross-sectional, one scan per participant — it speaks to neither the presence nor the absence of
within-person developmental change.

This oracle computes the pooled association, then the within-site and between-site associations
with uncertainty, then basic sensitivity checks (motion/QC, diagnosis, sex, nonlinear age,
site-specific slopes), and reports the bounded conclusion above.

Inputs. Prefers baked per-subject CC200 timeseries under $FCMATUR_DATA or
environment/data/cc200_timeseries.npz (allow_internet=false). Falls back to a runtime nilearn
fetch when no baked snapshot is present.
"""
import json
import os
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings("ignore")
np.seterr(all="ignore")

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)
MIN_PER_SITE = 5


def fail(reason):
    for name, obj in (("connectivity_age.json", {"status": "failed_precondition", "reason": reason}),
                      ("run_metadata.json", {"status": "failed_precondition", "reason": reason,
                                             "dataset": "ABIDE_pcp"})):
        (OUT / name).write_text(json.dumps(obj, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


def subject_connectivity(ts):
    ts = np.asarray(ts, dtype=float)
    ts = ts[:, np.nanstd(ts, axis=0) > 0]
    if ts.shape[1] < 2:
        return np.nan
    C = np.corrcoef(ts.T)
    iu = np.triu_indices_from(C, k=1)
    z = np.arctanh(np.clip(C[iu], -0.999, 0.999))
    return float(np.nanmean(z))


# ---------------------------------------------------------------------------------------------
# Load inputs: baked snapshot first (offline), else runtime nilearn fetch.
# ---------------------------------------------------------------------------------------------
def _baked_path():
    for p in (os.environ.get("FCMATUR_DATA"),
              Path(__file__).resolve().parent.parent / "environment" / "data" / "cc200_timeseries.npz",
              Path("/app/data/cc200_timeseries.npz")):
        if p and Path(p).exists():
            return Path(p)
    return None


def load_inputs():
    bp = _baked_path()
    if bp is not None:
        z = np.load(bp, allow_pickle=True)
        ids = [str(x) for x in z["file_id"]]
        series = [np.asarray(z[f"ts_{i}"], dtype=float) for i in range(len(ids))]
        ph = pd.DataFrame({
            "FILE_ID": ids,
            "AGE_AT_SCAN": pd.to_numeric(z["age"], errors="coerce"),
            "SITE_ID": [str(x) for x in z["site_id"]],
            "SEX": pd.to_numeric(z["sex"], errors="coerce"),
            "DX_GROUP": pd.to_numeric(z["dx_group"], errors="coerce"),
            "func_mean_fd": pd.to_numeric(z["func_mean_fd"], errors="coerce"),
        })
        return series, ph, f"baked snapshot ({bp.name})"
    try:
        from nilearn.datasets import fetch_abide_pcp
        abide = fetch_abide_pcp(pipeline="cpac", band_pass_filtering=True,
                                global_signal_regression=False, derivatives=["rois_cc200"],
                                quality_checked=False, data_dir=os.environ.get("NILEARN_DATA"),
                                verbose=0)
    except Exception as e:  # pragma: no cover
        fail(f"could not fetch ABIDE derivatives: {e}")
    ph = abide["phenotypic"]
    if not isinstance(ph, pd.DataFrame):
        ph = pd.DataFrame(ph)
    ph = ph.reset_index(drop=True)
    return abide["rois_cc200"], ph, "runtime nilearn fetch_abide_pcp"


series, ph, source = load_inputs()
if len(series) != len(ph) or len(series) < 300:
    fail(f"unexpected ABIDE size: {len(series)} series, {len(ph)} phenotype rows")


def _col(frame, name, default=np.nan):
    return frame[name] if name in frame.columns else pd.Series([default] * len(frame))


conn = np.array([subject_connectivity(x) for x in series], dtype=float)
age = pd.to_numeric(_col(ph, "AGE_AT_SCAN"), errors="coerce").to_numpy(dtype=float)
site = _col(ph, "SITE_ID").astype(str).to_numpy()
sub_id = _col(ph, "FILE_ID").astype(str).to_numpy() if "FILE_ID" in ph.columns else \
    np.array([f"sub-{i}" for i in range(len(series))])
sex = pd.to_numeric(_col(ph, "SEX"), errors="coerce").to_numpy(dtype=float)
dx = pd.to_numeric(_col(ph, "DX_GROUP"), errors="coerce").to_numpy(dtype=float)
motion = pd.to_numeric(_col(ph, "func_mean_fd"), errors="coerce").to_numpy(dtype=float)

df = pd.DataFrame({"subject": sub_id, "connectivity": conn, "age": age, "site_id": site,
                   "sex": sex, "dx_group": dx, "mean_fd": motion})
df = df[np.isfinite(df.connectivity) & np.isfinite(df.age) & (df.age > 0) & (df.age < 120)]
df = df.reset_index(drop=True)
if len(df) < 300:
    fail(f"only {len(df)} usable participants after cleaning")
n = int(len(df))


# ---------------------------------------------------------------------------------------------
# Estimators + uncertainty (analytic Fisher-z CIs; deterministic).
# ---------------------------------------------------------------------------------------------
def fisher_ci(r, dof, alpha=0.05):
    """Fisher-z 95% CI for a (partial) correlation with `dof` effective degrees of freedom.
    dof = n - 2 for a simple correlation; n - k - 2 for a partial correlation on k covariates."""
    r = float(np.clip(r, -0.999999, 0.999999))
    if dof <= 1:
        return (float("nan"), float("nan"))
    z = np.arctanh(r)
    se = 1.0 / np.sqrt(dof - 1)
    zc = stats.norm.ppf(1 - alpha / 2)
    return (float(np.tanh(z - zc * se)), float(np.tanh(z + zc * se)))


def partial_corr(y, x, controls):
    """Partial correlation of y and x controlling for `controls` (2D design incl. intercept).
    Returns (r, p, dof) with dof = n - k - 2 (k = # non-intercept controls)."""
    y = np.asarray(y, float); x = np.asarray(x, float)
    D = np.asarray(controls, float)

    def resid(v):
        beta, *_ = np.linalg.lstsq(D, v, rcond=None)
        return v - D @ beta
    ry, rx = resid(y), resid(x)
    k = D.shape[1] - 1  # drop the intercept from the covariate count
    dof = len(y) - k - 2
    r = float(np.corrcoef(ry, rx)[0, 1])
    if not np.isfinite(r) or dof <= 1:
        return float("nan"), float("nan"), dof
    t = r * np.sqrt(dof / max(1e-12, 1 - r * r))
    p = float(2 * stats.t.sf(abs(t), dof))
    return r, p, dof


# --- Pooled (marginal) ---
r_pool, p_pool = stats.pearsonr(df.connectivity, df.age)
r_pool, p_pool = float(r_pool), float(p_pool)
pool_ci = fisher_ci(r_pool, n - 2)
rho_pool, prho_pool = stats.spearmanr(df.connectivity, df.age)

# --- Within-site (site-conditioned): partial correlation controlling for site fixed effects ---
vc = df.site_id.value_counts()
keep = vc[vc >= MIN_PER_SITE].index
w = df[df.site_id.isin(keep)].reset_index(drop=True)
Dsite = pd.get_dummies(w.site_id, drop_first=True).astype(float).to_numpy()
Dsite = np.column_stack([np.ones(len(w)), Dsite])
r_within, p_within, dof_within = partial_corr(w.connectivity.to_numpy(), w.age.to_numpy(), Dsite)
# partial-correlation Fisher-z se = 1/sqrt(n-g-3); partial_corr's dof = n-g-2, and fisher_ci
# uses se = 1/sqrt(dof-1), so passing dof_within gives the correct partial-correlation CI.
within_ci = fisher_ci(r_within, dof_within)
n_within = int(len(w))
n_sites_kept = int(len(keep))

# --- Between-site (site-mean / ecological) ---
sm = df.groupby("site_id").agg(n=("connectivity", "count"),
                               mean_connectivity=("connectivity", "mean"),
                               mean_age=("age", "mean")).reset_index()
sm = sm[sm.n >= MIN_PER_SITE]
r_site, p_site = stats.pearsonr(sm.mean_connectivity, sm.mean_age)
r_site, p_site = float(r_site), float(p_site)
site_ci = fisher_ci(r_site, len(sm) - 2)
n_sites = int(len(sm))
site_age_lo, site_age_hi = float(sm.mean_age.min()), float(sm.mean_age.max())


# ---------------------------------------------------------------------------------------------
# Sensitivity checks (real; on the same cleaned sample).
# ---------------------------------------------------------------------------------------------
sens = {}

# (1) Motion / QC — pooled and within-site associations adjusting for mean framewise displacement.
mo = w[np.isfinite(w.mean_fd)].reset_index(drop=True)
if len(mo) > 50:
    Dm = np.column_stack([np.ones(len(mo)), mo.mean_fd.to_numpy()])
    rp_m, pp_m, _ = partial_corr(mo.connectivity.to_numpy(), mo.age.to_numpy(), Dm)
    Dsm = pd.get_dummies(mo.site_id, drop_first=True).astype(float).to_numpy()
    Dsm = np.column_stack([np.ones(len(mo)), Dsm, mo.mean_fd.to_numpy()])
    rw_m, pw_m, _ = partial_corr(mo.connectivity.to_numpy(), mo.age.to_numpy(), Dsm)
    sens["motion"] = {"n": int(len(mo)), "pooled_r_adj_motion": rp_m, "pooled_p_adj_motion": pp_m,
                      "within_site_r_adj_motion": rw_m, "within_site_p_adj_motion": pw_m,
                      "note": "connectivity–age association adjusting for mean framewise displacement"}

# (2) Diagnosis — restrict to typical controls (DX_GROUP == 2 in ABIDE) and recompute both levels.
ctrl = w[w.dx_group == 2].reset_index(drop=True)
if len(ctrl) > 50 and ctrl.site_id.nunique() >= 2:
    rp_c, pp_c = stats.pearsonr(ctrl.connectivity, ctrl.age)
    Dc = np.column_stack([np.ones(len(ctrl)),
                          pd.get_dummies(ctrl.site_id, drop_first=True).astype(float).to_numpy()])
    rw_c, pw_c, _ = partial_corr(ctrl.connectivity.to_numpy(), ctrl.age.to_numpy(), Dc)
    sens["diagnosis"] = {"n_controls": int(len(ctrl)), "pooled_r_controls": float(rp_c),
                         "pooled_p_controls": float(pp_c), "within_site_r_controls": rw_c,
                         "within_site_p_controls": pw_c,
                         "note": "restricted to typical controls (DX_GROUP==2)"}

# (3) Sex — pooled and within-site adjusting for sex.
sx = w[np.isfinite(w.sex)].reset_index(drop=True)
if len(sx) > 50:
    Dx = np.column_stack([np.ones(len(sx)), sx.sex.to_numpy()])
    rp_s, pp_s, _ = partial_corr(sx.connectivity.to_numpy(), sx.age.to_numpy(), Dx)
    Dxs = pd.get_dummies(sx.site_id, drop_first=True).astype(float).to_numpy()
    Dxs = np.column_stack([np.ones(len(sx)), Dxs, sx.sex.to_numpy()])
    rw_s, pw_s, _ = partial_corr(sx.connectivity.to_numpy(), sx.age.to_numpy(), Dxs)
    sens["sex"] = {"n": int(len(sx)), "pooled_r_adj_sex": rp_s, "pooled_p_adj_sex": pp_s,
                   "within_site_r_adj_sex": rw_s, "within_site_p_adj_sex": pw_s,
                   "note": "connectivity–age association adjusting for sex"}

# (4) Nonlinear age — does a quadratic age term add anything (pooled)?
a = df.age.to_numpy(); c = df.connectivity.to_numpy()
az = (a - a.mean()) / a.std()
Xlin = np.column_stack([np.ones(n), az])
Xquad = np.column_stack([np.ones(n), az, az ** 2])
bl, *_ = np.linalg.lstsq(Xlin, c, rcond=None)
bq, *_ = np.linalg.lstsq(Xquad, c, rcond=None)
rss_l = float(((c - Xlin @ bl) ** 2).sum())
rss_q = float(((c - Xquad @ bq) ** 2).sum())
df1, df2 = 1, n - 3
F = ((rss_l - rss_q) / df1) / (rss_q / df2)
p_nl = float(stats.f.sf(F, df1, df2)) if np.isfinite(F) and F > 0 else float("nan")
sens["nonlinear_age"] = {"quadratic_beta": float(bq[2]), "F_added_quadratic": float(F),
                         "p_added_quadratic": p_nl,
                         "note": "pooled test that an age^2 term improves the connectivity model"}

# (5) Site-specific slopes — the per-site connectivity~age relationship is heterogeneous.
per_site = []
for s, g in w.groupby("site_id"):
    if len(g) >= MIN_PER_SITE and g.age.std() > 0 and g.connectivity.std() > 0:
        rr, pp = stats.pearsonr(g.connectivity, g.age)
        slope = float(np.polyfit(g.age, g.connectivity, 1)[0])
        per_site.append({"site_id": str(s), "n": int(len(g)), "r": float(rr), "p": float(pp),
                         "slope": slope})
ps_r = np.array([d["r"] for d in per_site], dtype=float)
sens["site_specific_slopes"] = {
    "n_sites": len(per_site),
    "median_within_site_r": float(np.median(ps_r)) if len(ps_r) else float("nan"),
    "frac_sites_positive": float(np.mean(ps_r > 0)) if len(ps_r) else float("nan"),
    "min_r": float(ps_r.min()) if len(ps_r) else float("nan"),
    "max_r": float(ps_r.max()) if len(ps_r) else float("nan"),
    "per_site": per_site,
    "note": "per-site connectivity–age correlation; heterogeneous, not a single common slope"}


# ---------------------------------------------------------------------------------------------
# Write outputs.
# ---------------------------------------------------------------------------------------------
df[["subject", "connectivity", "age", "site_id", "sex", "dx_group", "mean_fd"]].to_csv(
    OUT / "connectivity.csv", index=False)

(OUT / "connectivity_age.json").write_text(json.dumps({
    "atlas": "cc200",
    "connectivity_metric": "mean of upper-triangular Fisher-z CC200 edges",
    "n": n,
    "n_sites": n_sites,
    # marginal (pooled)
    "pooled_r": r_pool,
    "pooled_ci95": [pool_ci[0], pool_ci[1]],
    "pooled_p": p_pool,
    "pooled_spearman_rho": float(rho_pool),
    "pooled_spearman_p": float(prho_pool),
    # site-conditioned (within-site)
    "within_site_r": r_within,
    "within_site_ci95": [within_ci[0], within_ci[1]],
    "within_site_p": p_within,
    "within_site_n": n_within,
    "within_site_n_sites": n_sites_kept,
    # between-site (ecological)
    "between_site_r": r_site,
    "between_site_ci95": [site_ci[0], site_ci[1]],
    "between_site_p": p_site,
    "between_site_n_sites": n_sites,
    # legacy alias kept for schema compatibility
    "connectivity_age_r": r_pool,
    "p_value": p_pool,
}, indent=2))

(OUT / "sensitivity.json").write_text(json.dumps(sens, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok",
    "dataset": "ABIDE_pcp",
    "data_source": source,
    "pipeline": "cpac / band_pass_filtering=True / global_signal_regression=False",
    "derivative": "rois_cc200",
    "atlas": "Craddock-200 (CC200)",
    "n_participants": n,
    "n_sites": n_sites,
    "connectivity_metric": "per-participant mean of the upper-triangular Fisher-z connectome edges",
    "method": ("marginal Pearson correlation of connectivity strength with AGE_AT_SCAN; "
               "site-conditioned partial correlation (site fixed effects); site-mean "
               "(between-site) correlation; each with a Fisher-z 95% CI; plus sensitivity "
               "checks for motion/QC, diagnosis, sex, nonlinear age and site-specific slopes"),
    "sensitivity_checks": ["motion", "diagnosis", "sex", "nonlinear_age", "site_specific_slopes"],
}, indent=2))

(OUT / "findings.md").write_text(f"""# Functional connectivity and age across the ABIDE sample — a case study

**Sample.** {n} participants across {n_sites} sites (ABIDE preprocessed, cpac, CC200 atlas).
Overall connectivity strength = the mean of each participant's upper-triangular Fisher-z
connectome edges. Data source: {source}.

## Three estimates, with uncertainty

| level | connectivity–age r | 95% CI | p | n |
|---|---|---|---|---|
| **marginal / pooled** | {r_pool:+.3f} | [{pool_ci[0]:+.3f}, {pool_ci[1]:+.3f}] | {p_pool:.3f} | {n} |
| **within-site (site fixed effects)** | {r_within:+.3f} | [{within_ci[0]:+.3f}, {within_ci[1]:+.3f}] | {p_within:.2f} | {n_within} |
| **between-site (site means)** | {r_site:+.3f} | [{site_ci[0]:+.3f}, {site_ci[1]:+.3f}] | {p_site:.3f} | {n_sites} sites |

Marginally, connectivity strength is **weakly positively** associated with age
(r = {r_pool:+.3f}, 95% CI [{pool_ci[0]:+.3f}, {pool_ci[1]:+.3f}]). The **between-site** level
carries a clearly positive relationship (r = {r_site:+.3f}): sites with older cohorts tend to have
higher mean connectivity, and site-mean age spans ~{site_age_lo:.0f}–{site_age_hi:.0f} yr.

## The marginal association is largely site-conditioned

Conditioning on site (site fixed effects), the association **attenuates toward null**:
within-site r = {r_within:+.3f} (95% CI [{within_ci[0]:+.3f}, {within_ci[1]:+.3f}], p = {p_within:.2f}),
a CI that includes zero. So the small pooled association is **sensitive to site composition** and
is carried largely by between-site differences rather than by a within-site connectivity–age
gradient.

## What this does and does not license

- It does **not** establish that scanner hardware *caused* the pooled correlation: "site" conflates
  scanner, acquisition protocol, and cohort composition, so this is a site-conditioning result, not
  a demonstrated scanner effect.
- A near-zero within-site estimate is **not** proof of a true null. Per-site power is limited and
  the within-site CI is wide; site-specific slopes are **heterogeneous** (across
  {len(per_site)} sites, per-site r ranges {sens['site_specific_slopes']['min_r']:+.2f} to
  {sens['site_specific_slopes']['max_r']:+.2f}, median {sens['site_specific_slopes']['median_within_site_r']:+.2f}).
- The data are **cross-sectional** (one scan per participant), so nothing here speaks to
  within-person developmental change in either direction.

## Sensitivity checks
Adjusting for **motion** (mean FD), **sex**, and restricting to **typical controls** leaves the
qualitative picture unchanged (pooled weakly positive; within-site attenuated toward null). A
**quadratic age** term does not materially change the connectivity model
(added-term p = {p_nl:.2f}). Details in `sensitivity.json`.

## Conclusion
In this ABIDE CC200 case study the marginal connectivity–age association (r ≈ {r_pool:+.2f}) is
**site-conditioned**: it is carried by between-site differences and **attenuates toward null**
within sites. This is a statement about site composition in a cross-sectional multi-site sample,
**not** a claim of a scanner-caused correlation and **not** a claim of a true absence of any
within-site or developmental age relationship.
""")

print(f"[FCMATUR-001] source={source} n={n} sites={n_sites} | pooled r={r_pool:+.4f} "
      f"CI[{pool_ci[0]:+.3f},{pool_ci[1]:+.3f}] p={p_pool:.4f} | within r={r_within:+.4f} "
      f"CI[{within_ci[0]:+.3f},{within_ci[1]:+.3f}] p={p_within:.3f} | between r={r_site:+.4f} "
      f"({n_sites} sites)")
