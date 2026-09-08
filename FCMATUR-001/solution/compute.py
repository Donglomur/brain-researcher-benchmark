"""Reference (oracle) for FCMATUR-001 — connectivity strength vs age across the ABIDE sample.

Estimand: the relationship between each participant's overall functional-connectivity strength
(mean of the Fisher-z CC200 connectome edges) and age, across the ABIDE resting-state sample.

Ground truth (validated on the nilearn-pinned ABIDE_pcp / cpac / filt_noglobal / rois_cc200,
1035 participants, 20 sites):

  POOLED across all participants : r = +0.077 (p = 0.013)      # significant, positive
  WITHIN-site (site fixed effects): r = -0.020 (p = 0.53)      # null / slightly negative
  SITE-MEAN (between-site)       : r = +0.391 (n = 20 sites)   # strong, positive

ABIDE pools 20 sites that differ enormously in mean age (site means span ~10-34 yr; age is
~50% between-site variance) AND independently differ in mean connectivity (a scanner/site batch
effect; ~10% of connectivity variance is between-site). Sites with older cohorts happen to have
higher mean connectivity, so the naive pooled correlation is dominated by this between-site
covariance and comes out significant and positive. Within participants of the same site the
relationship is null: the positive pooled correlation is a between-site (aggregation) artifact,
not a within-person age effect (Simpson's paradox; ecological correlation, Robinson 1950).

This reference computes the pooled correlation an analyst would report, THEN volunteers the
un-cued check the instruction never asks: whether that correlation survives the multi-site
structure. It does not.

Data is fetched at runtime with nilearn (no credentials). Set NILEARN_DATA to reuse a local
cache; otherwise nilearn downloads to its default directory.
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


try:
    from nilearn.datasets import fetch_abide_pcp
    abide = fetch_abide_pcp(pipeline="cpac", band_pass_filtering=True,
                            global_signal_regression=False, derivatives=["rois_cc200"],
                            quality_checked=False, data_dir=os.environ.get("NILEARN_DATA"),
                            verbose=0)
except Exception as e:  # pragma: no cover
    fail(f"could not fetch ABIDE derivatives: {e}")

series = abide["rois_cc200"]
ph = abide["phenotypic"]
if not isinstance(ph, pd.DataFrame):
    ph = pd.DataFrame(ph)
ph = ph.reset_index(drop=True)
if len(series) != len(ph) or len(series) < 300:
    fail(f"unexpected ABIDE size: {len(series)} series, {len(ph)} phenotype rows")

conn = np.array([subject_connectivity(x) for x in series], dtype=float)
age = pd.to_numeric(ph.get("AGE_AT_SCAN"), errors="coerce").to_numpy(dtype=float)
site = ph.get("SITE_ID").astype(str).to_numpy()
sub_id = ph.get("FILE_ID").astype(str).to_numpy() if "FILE_ID" in ph.columns else \
    np.array([f"sub-{i}" for i in range(len(series))])

df = pd.DataFrame({"subject": sub_id, "connectivity": conn, "age": age, "site_id": site})
df = df[np.isfinite(df.connectivity) & np.isfinite(df.age) & (df.age > 0) & (df.age < 120)]
if len(df) < 300:
    fail(f"only {len(df)} usable participants after cleaning")

# --- The pooled correlation an analyst reports when asked to relate connectivity to age ---
r_pool, p_pool = stats.pearsonr(df.connectivity, df.age)
rho_pool, prho_pool = stats.spearmanr(df.connectivity, df.age)
n = int(len(df))

# --- The un-cued check: does it survive the multi-site structure? ---
# within-site = correlation of connectivity and age after removing site fixed effects
vc = df.site_id.value_counts()
keep = vc[vc >= MIN_PER_SITE].index
w = df[df.site_id.isin(keep)]
D = pd.get_dummies(w.site_id, drop_first=True).astype(float).to_numpy()
D = np.column_stack([np.ones(len(w)), D])


def _resid(v):
    v = np.asarray(v, dtype=np.float64)
    beta, *_ = np.linalg.lstsq(D, v, rcond=None)
    r = v - D @ beta
    s = r.std()
    return (r - r.mean()) / s if s > 0 else r  # standardise (defensive; avoids overflow)


with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    with np.errstate(all="ignore"):
        r_within, p_within = stats.pearsonr(_resid(w.connectivity.to_numpy()),
                                            _resid(w.age.to_numpy()))

# between-site (ecological) = each site's mean connectivity vs its mean age
sm = df.groupby("site_id").agg(n=("connectivity", "count"),
                               mean_connectivity=("connectivity", "mean"),
                               mean_age=("age", "mean")).reset_index()
sm = sm[sm.n >= MIN_PER_SITE]
r_site, p_site = stats.pearsonr(sm.mean_connectivity, sm.mean_age)
n_sites = int(len(sm))
site_age_lo, site_age_hi = float(sm.mean_age.min()), float(sm.mean_age.max())

df[["subject", "connectivity", "age", "site_id"]].to_csv(OUT / "connectivity.csv", index=False)

(OUT / "connectivity_age.json").write_text(json.dumps({
    "atlas": "cc200",
    "connectivity_metric": "mean of upper-triangular Fisher-z CC200 edges",
    "n": n,
    "connectivity_age_r": float(r_pool),
    "p_value": float(p_pool),
    "connectivity_age_spearman_rho": float(rho_pool),
    "spearman_p_value": float(prho_pool),
    "within_site_r": float(r_within),
    "within_site_p_value": float(p_within),
    "between_site_mean_r": float(r_site),
    "n_sites": n_sites,
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok",
    "dataset": "ABIDE_pcp (fetch_abide_pcp)",
    "pipeline": "cpac / band_pass_filtering=True / global_signal_regression=False",
    "derivative": "rois_cc200",
    "atlas": "Craddock-200 (CC200)",
    "n_participants": n,
    "n_sites": n_sites,
    "connectivity_metric": "per-participant mean of the upper-triangular Fisher-z connectome edges",
    "method": ("Pearson correlation of connectivity strength with AGE_AT_SCAN across participants; "
               "cross-checked after removing site fixed effects and at the site-mean level"),
}, indent=2))

(OUT / "findings.md").write_text(f"""# Functional connectivity and age across the ABIDE sample

**Sample.** {n} participants across {n_sites} sites (ABIDE preprocessed, cpac, CC200 atlas).
Overall connectivity strength = the mean of each participant's upper-triangular Fisher-z
connectome edges.

## The headline correlation
Across the {n} participants, overall connectivity strength correlates **positively** with age:
Pearson r = **{r_pool:+.3f}** (p = {p_pool:.3f}; Spearman rho = {rho_pool:+.3f}, p = {prho_pool:.3f}).
Taken at face value this says connectivity increases with age.

## That correlation does not survive the multi-site structure
ABIDE pools {n_sites} acquisition sites that differ enormously in **mean age** (site means span
{site_age_lo:.0f}-{site_age_hi:.0f} years) and, independently, in **mean connectivity** (a
scanner/site batch effect). Correlating each site's mean connectivity with its mean age gives a
strong between-site relationship (r = **{r_site:+.2f}**, n = {n_sites} sites): sites with older
cohorts happen to have higher mean connectivity. Because age is largely a *between-site* variable
here, the pooled correlation is dominated by this between-site covariance.

When the between-site differences are removed — correlating connectivity and age **within** sites
(site fixed effects) — the relationship **collapses to r = {r_within:+.3f} (p = {p_within:.2f}),
essentially null**.

## Conclusion
The positive pooled connectivity-age correlation is a **between-site (aggregation) artifact**, not
a within-person association: within any given site, connectivity strength does **not** increase with
age. Reading the pooled/site-driven correlation as a developmental connectivity-age effect is a
Simpson's-paradox / ecological-correlation error (Robinson 1950); the honest summary is that this
CC200 connectivity summary shows **no within-site relationship with age** in ABIDE.
""")

print(f"[FCMATUR-001] pooled r={r_pool:+.4f} (p={p_pool:.4f}), within-site r={r_within:+.4f} "
      f"(p={p_within:.3f}), site-mean r={r_site:+.4f} over {n_sites} sites, n={n}")
