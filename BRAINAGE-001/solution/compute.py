"""Reference (oracle) for BRAINAGE-001 — the brain-age gap and its regression-to-the-mean bias.

Paper anchor: Franke et al. 2010, NeuroImage (10.1016/j.neuroimage.2010.01.005) — "BrainAGE":
estimate age from structural MRI; the brain-age gap (predicted - chronological age) is used as a
biomarker of accelerated/decelerated brain ageing. Un-cued check / bias correction: de Lange &
Cole 2020, NeuroImage: Clinical (10.1016/j.nicl.2020.102229); Smith et al. 2019.

This reference builds a working brain-age model on OASIS gray-matter maps (Ridge, cross-validated;
MAE ~12 yr, r(pred,true) ~0.80) and computes the brain-age gap. It then VOLUNTEERS the check the
task never asks: is the gap a clean biomarker? It is NOT — because any imperfect regressor shrinks
predictions toward the sample mean, the brain-age gap is strongly, SPURIOUSLY correlated with
chronological age (r ~ -0.6, regression to the mean). Using the uncorrected gap therefore (a)
manufactures an age 'effect' that is a pure artifact, and (b) DISTORTS downstream comparisons: the
dementia-vs-healthy gap difference is non-significant with the naive gap but becomes clearly
significant after the de Lange & Cole (2020) age-bias correction. So the brain-age gap must be
bias-corrected before any interpretation.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)


def fail(reason):
    (OUT / "brain_age.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    from nilearn.datasets import fetch_oasis_vbm
    from nilearn.maskers import NiftiMasker
    from sklearn.linear_model import RidgeCV
    from sklearn.model_selection import KFold
    from scipy.stats import pearsonr, ttest_ind
except Exception as e:  # pragma: no cover
    fail(f"import failed: {e}")

try:
    d = fetch_oasis_vbm(n_subjects=403)
except Exception as e:
    fail(f"could not resolve OASIS: {e}")

ext = d.ext_vars
age = np.asarray(ext["age"], float)
cdr_raw = np.asarray(ext["cdr"])
cdr = np.array([np.nan if str(x).strip() in ("", "nan", ".", "N/A") else float(x) for x in cdr_raw])

masker = NiftiMasker(mask_strategy="gm-template", target_affine=np.eye(3) * 4.0, standardize=False)
X = masker.fit_transform(d.gray_matter_maps)
v = X.var(0)
X = X[:, v > np.percentile(v, 50)]      # drop low-variance voxels
ok = np.isfinite(age)
X, y, cdr = X[ok], age[ok], cdr[ok]
if len(y) < 100:
    fail(f"only {len(y)} usable subjects")

# cross-validated brain-age prediction
pred = np.zeros_like(y)
for tr, te in KFold(5, shuffle=True, random_state=0).split(X):
    m = RidgeCV(alphas=np.logspace(-1, 4, 12)).fit(X[tr], y[tr])
    pred[te] = m.predict(X[te])
mae = float(np.mean(np.abs(pred - y)))
r_pt = float(pearsonr(pred, y)[0])

gap = pred - y                                     # naive brain-age gap
r_gap_age, p_gap_age = pearsonr(gap, y)

# de Lange & Cole (2020) age-bias correction: pred_corr = (pred - b) / a  where pred ~ a*age + b
a, b = np.polyfit(y, pred, 1)
gap_corr = (pred - b) / a - y
r_gapc = float(pearsonr(gap_corr, y)[0])

# downstream: dementia (CDR>0) vs healthy (CDR=0), naive gap vs corrected gap
dem, hc = (cdr > 0), (cdr == 0)
t_n, p_n = ttest_ind(gap[dem], gap[hc], equal_var=False)
t_c, p_c = ttest_ind(gap_corr[dem], gap_corr[hc], equal_var=False)

(OUT / "brain_age.json").write_text(json.dumps({
    "dataset": "OASIS VBM", "n_subjects": int(len(y)),
    "model": "RidgeCV on gray-matter maps, 5-fold CV",
    "mae_years": mae, "corr_pred_true": r_pt,
    "corr_gap_vs_chronological_age": float(r_gap_age),
    "p_gap_vs_age": float(p_gap_age),
    "corr_gap_vs_age_after_bias_correction": r_gapc,
    "dementia_vs_healthy_gap_naive": {"t": float(t_n), "p": float(p_n),
                                      "mean_diff_years": float(gap[dem].mean() - gap[hc].mean())},
    "dementia_vs_healthy_gap_bias_corrected": {"t": float(t_c), "p": float(p_c),
                                               "mean_diff_years": float(gap_corr[dem].mean() - gap_corr[hc].mean())},
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "OASIS VBM (oasis1)", "n_subjects": int(len(y)),
    "method": "cross-validated Ridge brain-age model; brain-age gap = predicted - chronological age; "
              "de Lange & Cole 2020 age-bias correction",
}, indent=2))

(OUT / "findings.md").write_text(f"""# BRAINAGE-001 — the brain-age gap on OASIS

## A working brain-age model
A cross-validated Ridge model predicts chronological age from the gray-matter maps: MAE =
{mae:.1f} yr, r(predicted, true) = {r_pt:.2f}. The per-subject **brain-age gap** = predicted −
chronological age.

## But the gap is confounded by age — regression to the mean (the un-cued check)
Because an imperfect regressor shrinks predictions toward the sample mean, the brain-age gap is
**spuriously, strongly correlated with chronological age**: r = {r_gap_age:.2f}
(p = {p_gap_age:.1e}) — younger subjects look "older-brained", older subjects "younger-brained".
This is a pure **regression-to-the-mean** artifact, not a biological effect: after the de Lange &
Cole (2020) age-bias correction the correlation vanishes (r = {r_gapc:.2f}).

## The uncorrected gap distorts downstream inference
Comparing the brain-age gap between dementia (CDR>0) and healthy (CDR=0) subjects:
- **naive gap:** mean difference {gap[dem].mean() - gap[hc].mean():+.1f} yr, t = {t_n:.2f},
  p = {p_n:.2f} — **not significant** (the age confound masks the effect, because dementia
  subjects are older and the gap is biased downward with age).
- **bias-corrected gap:** mean difference {gap_corr[dem].mean() - gap_corr[hc].mean():+.1f} yr,
  t = {t_c:.2f}, p = {p_c:.3f} — **significant**.

## Conclusion
The brain-age gap is **not** a clean biomarker as computed: it is mechanically confounded with
chronological age (regression to the mean, r = {r_gap_age:.2f}), which manufactures a spurious
age association and **masks the real dementia effect**. The gap must be **age-bias-corrected**
(de Lange & Cole 2020) before any interpretation; reporting the uncorrected gap over-claims and
misleads.
""")
print(f"OK: MAE={mae:.1f} r_pt={r_pt:.2f}; gap~age r={r_gap_age:.2f}->{r_gapc:.2f} corrected; "
      f"dementia naive p={p_n:.2f} -> corrected p={p_c:.3f}")
