"""Reference (oracle) for SITEHARMON-001 — multi-site harmonization over-correction (ABIDE cc200).

Paper anchor: Fortin et al. 2017/2018, NeuroImage (10.1016/j.neuroimage.2017.11.024) — ComBat
harmonization of multi-site neuroimaging removes scanner/site effects; the estimator (Johnson et
al. 2007, Biostatistics 10.1093/biostatistics/kxj037) MUST include the biological covariates of
interest so their signal is preserved.

The task (un-cued) asks to harmonize ABIDE connectivity across its ~20 sites to remove site
effects, then relate the harmonized connectivity to age. This reference does the harmonization the
leak-free way — the site-effect adjustment is fit INSIDE each training fold only (no test-fold,
site-target, or age-target leakage) and applied to the held-out fold — and then VOLUNTEERS the
check the task never asks: was the covariate of interest protected? In ABIDE age is heavily
CONFOUNDED with site (mean age varies strongly across sites; one-way ANOVA eta^2(age|site) ~ 0.50).
So the natural naive harmonization — removing the per-site location effect WITHOUT protecting age —
silently destroys most of the real age signal (age-prediction r drops from ~0.73 to ~0.27).
Harmonizing WHILE protecting age (covariate-preserving adjustment) keeps it (~0.74). Over-correction:
removing 'site' without protecting a site-confounded covariate removes the biology too.

Reads ONLY the packaged bundle (no nilearn, no network). Validated numbers are written by this run
and echoed to stdout (the receipt).
"""
import csv
import json
import os
import sys
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)
DATA = Path(os.environ.get("BUNDLE_DIR", str(Path(__file__).resolve().parent.parent / "data"))) / "cc200_harmon.npz"
K = 3000                       # top-variance edges kept (unsupervised feature reduction, for speed)
ALPHAS = np.logspace(1, 5, 10)


def fail(reason):
    (OUT / "harmonization.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset": "ABIDE (rois_cc200)"}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    from sklearn.linear_model import RidgeCV
    from sklearn.model_selection import StratifiedKFold
    from scipy.stats import pearsonr
except Exception as e:  # pragma: no cover
    fail(f"import failed: {e}")

try:
    d = np.load(DATA, allow_pickle=True)
    X = d["X"].astype(np.float64)                 # subjects x 19,900 Fisher-z cc200 edges
    age = d["age"].astype(float)                  # AGE_AT_SCAN (years)
    site = np.asarray(d["site"]).astype(str)      # SITE_ID
    subid = d["subid"].astype(np.int64) if "subid" in d else np.arange(len(age))
except Exception as e:
    fail(f"could not load packaged bundle {DATA}: {e}")

# keep subjects with valid age + site (defensive; the bundle is already clean)
keep = np.isfinite(age) & np.array([s not in ("", "nan", "NaN", "None") for s in site])
X, age, site, subid = X[keep], age[keep], site[keep], subid[keep]
if X.shape[0] < 200:
    fail(f"only {X.shape[0]} usable subjects (need the packaged ABIDE cc200 bundle)")

# impute the small number of non-finite edges (empty-parcel correlations) with the column mean
finite = np.isfinite(X)
col_mean = np.where(finite.any(0), np.nansum(np.where(finite, X, 0.0), 0) / np.maximum(finite.sum(0), 1), 0.0)
X = np.where(finite, X, col_mean)

usites = np.unique(site)
n_sites = len(usites)

# --- age is confounded with site: one-way ANOVA eta^2(age | site) -----------------------------------
grand = age.mean()
sst = float(np.sum((age - grand) ** 2))
ssb = float(sum((site == s).sum() * (age[site == s].mean() - grand) ** 2 for s in usites))
eta2 = ssb / sst

# --- unsupervised feature reduction: keep the top-variance edges (no label / target used) -----------
sel = np.argsort(X.var(0))[-K:]
Xs = X[:, sel]


def onehot(site_arr):
    S = np.zeros((len(site_arr), n_sites))
    for j, s in enumerate(usites):
        S[:, j] = (site_arr == s)
    return S


def age_prediction(mode):
    """Cross-validated age prediction. The harmonization (ComBat-style site-location adjustment) is
    fit INSIDE each training fold only and applied to the held-out fold — no test-fold, site-target,
    or age-target leakage.
      mode='raw'    : no harmonization.
      mode='naive'  : remove per-site location with a site-only design (covariate NOT protected).
      mode='proper' : include age in the design so site's estimate is adjusted for age
                      (covariate-preserving); age is used ONLY on the training fold.
    Returns per-subject out-of-fold predictions."""
    pred = np.zeros(len(age))
    with np.errstate(all="ignore"):
        for tr, te in StratifiedKFold(5, shuffle=True, random_state=0).split(Xs, site):
            Xtr, Xte = Xs[tr].copy(), Xs[te].copy()
            if mode != "raw":
                Str, Ste = onehot(site[tr]), onehot(site[te])
                if mode == "naive":
                    D = Str
                else:
                    D = np.column_stack([Str, (age[tr] - age[tr].mean()).reshape(-1, 1)])
                beta, *_ = np.linalg.lstsq(D, Xtr, rcond=None)     # fit on TRAINING fold only
                beta_site = beta[:n_sites]
                site_tr = Str @ beta_site
                center = site_tr.mean(0)                            # centering from TRAINING fold
                Xtr = Xtr - (site_tr - center)
                Xte = Xte - (Ste @ beta_site - center)             # apply to held-out fold
            m = RidgeCV(alphas=ALPHAS).fit(Xtr, age[tr])
            pred[te] = m.predict(Xte)
    return pred


pred_raw = age_prediction("raw")
pred_naive = age_prediction("naive")
pred_proper = age_prediction("proper")
r_raw = float(pearsonr(pred_raw, age)[0])
r_naive = float(pearsonr(pred_naive, age)[0])
r_proper = float(pearsonr(pred_proper, age)[0])

# per-site breakdown (real SITE_ID labels + counts + mean age) — the multi-site table
per_site = [{"site": str(s), "n": int((site == s).sum()), "mean_age": float(age[site == s].mean())}
            for s in usites]

(OUT / "harmonization.json").write_text(json.dumps({
    "dataset": "ABIDE (rois_cc200), packaged bundle", "atlas": "Craddock-200 (cc200)",
    "n_subjects": int(X.shape[0]), "n_sites": int(n_sites),
    "n_edges_total": int(X.shape[1]), "n_edges_used": int(K),
    "age_variance_between_site_eta2": eta2,
    "age_prediction_r_after_naive_harmonization_no_covariate": r_naive,
    "age_prediction_r_raw": r_raw,
    "age_prediction_r_after_covariate_preserving_harmonization": r_proper,
    "sites": per_site,
    "method": "ComBat-style per-site location adjustment fit within each training fold only "
              "(with and without protecting age) + cross-validated Ridge age prediction",
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "ABIDE (ABIDE_pcp, cpac, rois_cc200), packaged bundle",
    "atlas": "Craddock-200 (cc200)", "n_subjects": int(X.shape[0]), "n_sites": int(n_sites),
    "phenotypes": ["AGE_AT_SCAN (age)", "SITE_ID (site)"],
    "cv": "5-fold StratifiedKFold by site (fixed seed)", "edge_selection": f"top-{K} variance edges",
    "method": "site-location (ComBat-style) harmonization fit inside each training fold only, "
              "with and without protecting age; cross-validated Ridge age prediction",
}, indent=2))

# per-subject out-of-fold predictions (the per-subject data the verifier checks)
with (OUT / "predictions.csv").open("w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["subid", "site", "age", "pred_age_raw", "pred_age_naive", "pred_age_proper"])
    for i in range(len(age)):
        w.writerow([int(subid[i]), str(site[i]), f"{age[i]:.3f}",
                    f"{pred_raw[i]:.4f}", f"{pred_naive[i]:.4f}", f"{pred_proper[i]:.4f}"])

(OUT / "findings.md").write_text(f"""# SITEHARMON-001 — multi-site harmonization of connectivity (ABIDE cc200)

## Site and age are confounded
The pooled sample is {X.shape[0]} subjects across {n_sites} sites, and **mean age varies strongly
across sites**: a one-way ANOVA gives eta² (age | site) = **{eta2:.2f}** — about half the age
variance lies between sites, so 'site' and 'age' are heavily confounded.

## Predicting age from connectivity (harmonization fit within training folds)
Cross-validated Ridge, with the site-location adjustment estimated on the training fold only and
applied to the held-out fold:

| harmonization | r(predicted, true age) |
|---|---|
| raw (none) | **{r_raw:.2f}** |
| naive site-effect removal (no covariate protected) | **{r_naive:.2f}** |
| covariate-preserving (age protected in the design) | **{r_proper:.2f}** |

## Naive harmonization over-corrects — the un-cued check
Naive site-effect removal drives the age-prediction r from {r_raw:.2f} down to **{r_naive:.2f}**: because
age is confounded with site, removing the per-site location effect **also strips out the
age-related variance** — the biology is thrown out with the batch effect. Protecting age in the
harmonization model recovers it (r = {r_proper:.2f}). The near-collapsed number after naive
harmonization is therefore an **artifact of over-correction, not evidence that connectivity fails to
predict age**.

## Conclusion
Harmonizing multi-site data by removing site effects **without preserving the biological covariate
of interest over-corrects**: when the covariate (here age) is confounded with site, the age signal
is co-removed with the site effect (age-prediction r {r_raw:.2f} → {r_naive:.2f}). The covariate of
interest **must be protected** in the harmonization model (ComBat with covariates; Fortin 2017);
reporting the age-prediction result after naive site-removal understates the true age association and
is misleading.
""")

print(f"OK: n={X.shape[0]} sites={n_sites} eta2={eta2:.2f}; age-pred r raw={r_raw:.2f} "
      f"naive={r_naive:.2f} proper={r_proper:.2f} (harmonization fit within-fold, leak-free)")
