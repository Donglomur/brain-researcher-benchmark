"""Reference (oracle) for HARMON-001 — multi-site harmonization over-correction (ABIDE).

Paper anchor: Fortin et al. 2017/2018, NeuroImage (10.1016/j.neuroimage.2017.11.024) — ComBat
harmonization of multi-site neuroimaging removes scanner/site effects; the method (Johnson et al.
2007) MUST include the biological covariates of interest so their signal is preserved.

The task (un-cued) asks to harmonize ABIDE connectivity across its ~20 sites to remove site
effects, then relate connectivity to age. This reference does the harmonization and then VOLUNTEERS
the check the task never asks: was the covariate of interest protected? In ABIDE, age is heavily
CONFOUNDED with site (mean age varies strongly across sites; one-way ANOVA eta^2(age|site) ~ 0.49).
So the natural naive harmonization — removing the per-site location effect WITHOUT protecting age —
silently destroys the real age signal (age-prediction r collapses from ~0.66 to ~0.02). Harmonizing
WHILE protecting age (a covariate-preserving adjustment) keeps it (~0.74). Over-correction: removing
'site' without protecting a site-confounded covariate removes the biology too.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)


def fail(reason):
    (OUT / "harmonization.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    from nilearn.datasets import fetch_abide_pcp
    from nilearn.connectome import ConnectivityMeasure
    from sklearn.linear_model import RidgeCV
    from sklearn.model_selection import KFold
    from scipy.stats import pearsonr
except Exception as e:  # pragma: no cover
    fail(f"import failed: {e}")

import pandas as pd

# Populate the nilearn cache (may partially fail on a flaky mirror), then read whatever cc200 time
# series are present directly — robust to individual missing files.
try:
    fetch_abide_pcp(derivatives=["rois_cc200"], pipeline="cpac",
                    band_pass_filtering=True, global_signal_regression=False, quality_checked=False)
except Exception:
    pass
base = os.path.expanduser("~/nilearn_data/ABIDE_pcp")
ddir = os.path.join(base, "cpac", "filt_noglobal")
pheno_csv = os.path.join(base, "Phenotypic_V1_0b_preprocessed1.csv")
if not os.path.exists(pheno_csv):
    fail("could not resolve ABIDE phenotypic table")
ph = pd.read_csv(pheno_csv)
ph = ph[ph["FILE_ID"] != "no_filename"]

ts, ages, sites = [], [], []
for _, row in ph.iterrows():
    f = os.path.join(ddir, str(row["FILE_ID"]) + "_rois_cc200.1D")
    if not os.path.exists(f):
        continue
    a = np.loadtxt(f)
    if a.ndim != 2 or a.shape[0] <= 50 or a.shape[1] < 200:
        continue
    if not np.isfinite(float(row["AGE_AT_SCAN"])):
        continue
    ts.append(a[:, :200]); ages.append(float(row["AGE_AT_SCAN"])); sites.append(row["SITE_ID"])
age = np.asarray(ages, float)
site = np.asarray(sites)
if len(ts) < 200:
    fail(f"only {len(ts)} usable subjects (need the ABIDE cc200 cache)")

usites = np.unique(site)
grand = age.mean()
sst = np.sum((age - grand) ** 2)
ssb = sum((site == s).sum() * (age[site == s].mean() - grand) ** 2 for s in usites)
eta2 = float(ssb / sst)                      # age variance between sites

cm = ConnectivityMeasure(kind="correlation", vectorize=True, discard_diagonal=True)
X = cm.fit_transform(ts)
vv = X.var(0)
X = X[:, np.argsort(vv)[-3000:]]             # keep top-variance edges for speed

S = np.zeros((len(age), len(usites)))
for j, s in enumerate(usites):
    S[:, j] = (site == s)


def harmonize(Xin, protect=None):
    """remove the per-site location effect. If protect (age) is given, include it in the design so
    its variance is NOT attributed to (and removed with) site — covariate-preserving harmonization."""
    D = S if protect is None else np.column_stack([S, protect - protect.mean()])
    beta, *_ = np.linalg.lstsq(D, Xin, rcond=None)
    site_part = S @ beta[:len(usites)]
    return Xin - (site_part - site_part.mean(0))


def age_pred_r(Xin):
    pred = np.zeros(len(age))
    for tr, te in KFold(5, shuffle=True, random_state=0).split(Xin):
        m = RidgeCV(alphas=np.logspace(-1, 4, 10)).fit(Xin[tr], age[tr])
        pred[te] = m.predict(Xin[te])
    return float(pearsonr(pred, age)[0])


r_raw = age_pred_r(X)
r_naive = age_pred_r(harmonize(X, protect=None))
r_proper = age_pred_r(harmonize(X, protect=age))

(OUT / "harmonization.json").write_text(json.dumps({
    "dataset": "ABIDE (rois_cc200)", "n_subjects": int(len(ts)), "n_sites": int(len(usites)),
    "age_variance_between_site_eta2": eta2,
    "age_prediction_r_raw": r_raw,
    "age_prediction_r_after_naive_harmonization_no_covariate": r_naive,
    "age_prediction_r_after_covariate_preserving_harmonization": r_proper,
    "method": "site-location (ComBat-style) harmonization; age-prediction via cross-validated Ridge",
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "ABIDE (ABIDE_pcp, cpac, rois_cc200)", "n_subjects": int(len(ts)),
    "n_sites": int(len(usites)),
    "method": "ComBat-style site-location harmonization (with and without protecting age) + "
              "cross-validated Ridge age prediction",
}, indent=2))

(OUT / "findings.md").write_text(f"""# HARMON-001 — multi-site harmonization (ABIDE)

## Site and age are confounded
ABIDE aggregates {len(ts)} subjects across {len(usites)} sites, and **mean age varies strongly
across sites**: a one-way ANOVA gives eta² (age | site) = **{eta2:.2f}** — about half the age
variance is between-site.

## Naive harmonization destroys the age signal (over-correction — the un-cued check)
Predicting age from connectivity (cross-validated Ridge):
- raw connectivity: r(predicted, true age) = **{r_raw:.2f}**
- after **naive** site-effect removal (no covariate protected): r = **{r_naive:.2f}** — the age
  signal is **destroyed**
- after **covariate-preserving** harmonization (age protected in the model): r = **{r_proper:.2f}**
  — the age signal is preserved

Because age is confounded with site, removing the site "location" effect without protecting age
silently removes the age-related variance as well.

## Conclusion
Harmonizing multi-site data by removing site effects **without preserving the biological covariate
of interest over-corrects**: when the covariate (here age) is confounded with site, naive
harmonization throws the biology out with the batch effect (age-prediction r {r_raw:.2f} → {r_naive:.2f}).
The covariate of interest must be protected in the harmonization model (ComBat with covariates;
Fortin 2017); reporting results after naive site-removal is misleading.
""")
print(f"OK: n={len(ts)} sites={len(usites)} eta2={eta2:.2f}; age-pred r raw={r_raw:.2f} "
      f"naive={r_naive:.2f} proper={r_proper:.2f}")
