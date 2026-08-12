"""Reference (oracle) for BRAINAGE-001 — the brain-age gap and its regression-to-the-mean bias.

Paper anchor: Franke et al. 2010, NeuroImage (10.1016/j.neuroimage.2010.01.005, "BrainAGE"):
estimate age from structural MRI; the brain-age gap (predicted - chronological age) is used as a
biomarker of accelerated/decelerated brain ageing. Un-cued check / bias correction: de Lange &
Cole 2020, NeuroImage: Clinical (10.1016/j.nicl.2020.102229); Smith et al. 2019, eLife.

This reference builds a working brain-age model on OASIS gray-matter maps (cross-validated Ridge;
MAE ~12 yr, r(pred,true) ~0.80) and computes the brain-age gap. It then VOLUNTEERS the check the
task never asks: is the raw gap a clean biomarker? It is NOT — because any imperfect regressor
shrinks predictions toward the training-sample mean, the brain-age gap is strongly, SPURIOUSLY
correlated with chronological age (r ~ -0.62, a regression-to-the-mean artifact). Left uncorrected
the gap (a) manufactures an age 'effect' that is a pure artifact, and (b) DISTORTS the downstream
group comparison: because dementia subjects are older and the gap is biased downward with age, the
naive dementia-vs-healthy gap difference is non-significant (~+2 yr, p~0.2) and MASKS the real
effect. It reappears once the gap is properly bias-corrected AND the comparison is age-adjusted.

The REPAIR (maintainer #23), leakage-free:
  * brain-age model: Ridge, 5-fold CV over all subjects -> out-of-fold predictions.
  * age-bias correction (de Lange & Cole 2020): fit pred ~ a*age + b and rescale
      pred_corr = (pred - b) / a. Crucially the a,b line is fit on CONTROL (non-demented) subjects
      only, CROSS-FITTED within CV folds (the correction for each held-out subject uses controls
      from the OTHER folds) — so the patient group we are testing never defines its own correction
      and no subject informs its own correction (no leakage).
  * group comparison: dementia (CDR>0) vs healthy elderly (CDR=0), AGE-ADJUSTED (chronological age
      as a covariate in an OLS), reported next to the naive raw t-test.

Emitted for the verifier to CHECK the actual data (not just prose):
  subject_gaps.csv  — one row per subject: age, cdr, group, predicted_age, gap_naive, gap_corrected
  brain_age.json    — model accuracy, gap~age before/after correction, dementia-vs-healthy naive vs
                      corrected (raw + age-adjusted), group counts, n_subjects
  run_metadata.json — dataset, n, method (the repaired, leakage-free pipeline)
  findings.md       — reproduces the model + the RTM confound + the masked-then-recovered dementia
                      effect + the conclusion (bias-correct before interpreting)
Validated numbers are written by this run and echoed to stdout (the receipt).
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


def fail(reason):
    (OUT / "brain_age.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset": "oasis1"}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    from nilearn.datasets import fetch_oasis_vbm
    from nilearn.maskers import NiftiMasker
    from sklearn.linear_model import RidgeCV
    from sklearn.model_selection import KFold
    from scipy.stats import pearsonr, ttest_ind
    from scipy.stats import t as tdist
except Exception as e:  # pragma: no cover
    fail(f"import failed: {e}")


def parse_cdr(x):
    """OASIS-1 CDR: 0 / 0.5 / 1 / 2, or blank (younger subjects were not assessed -> NaN)."""
    s = str(x).strip()
    if s in ("", "nan", ".", "N/A", "--"):
        return np.nan
    try:
        return float(s)
    except Exception:
        return np.nan


def ols_group_effect(y, group, age):
    """OLS  y ~ 1 + group + age  (age-adjusted group contrast). Returns (beta_group, t, p, df)."""
    Xd = np.column_stack([np.ones_like(y), group.astype(float), age])
    beta, *_ = np.linalg.lstsq(Xd, y, rcond=None)
    resid = y - Xd @ beta
    dof = len(y) - Xd.shape[1]
    cov = (resid @ resid) / dof * np.linalg.inv(Xd.T @ Xd)
    se = np.sqrt(np.diag(cov))
    tg = float(beta[1] / se[1])
    return float(beta[1]), tg, float(2 * tdist.sf(abs(tg), dof)), int(dof)


try:
    d = fetch_oasis_vbm(n_subjects=403)
except Exception as e:
    fail(f"could not resolve OASIS: {e}")

ext = d.ext_vars
age = np.asarray(ext["age"], float)
cdr = np.array([parse_cdr(x) for x in np.asarray(ext["cdr"])])

# gray-matter maps -> voxel matrix (4 mm, gray-matter mask); drop low-variance voxels
masker = NiftiMasker(mask_strategy="gm-template", target_affine=np.eye(3) * 4.0, standardize=False)
X = masker.fit_transform(d.gray_matter_maps)
ok = np.isfinite(age)
X, age, cdr = np.nan_to_num(X[ok]), age[ok], cdr[ok]
v = X.var(0)
keep = (v > 0) & np.isfinite(v)
X, v = X[:, keep], v[keep]
X = X[:, v > np.percentile(v, 50)]        # keep the top-variance half
n = len(age)
if n < 100:
    fail(f"only {n} usable subjects")

demented = cdr > 0                         # CDR 0.5 / 1 / 2
control = ~demented                        # non-demented: CDR==0 (elderly) or blank (younger, unassessed)
hc_elderly = cdr == 0                      # the age-comparable healthy comparison group
if demented.sum() < 20 or hc_elderly.sum() < 20:
    fail(f"too few dementia ({int(demented.sum())}) or healthy-elderly ({int(hc_elderly.sum())}) subjects")

# ---- brain-age model: Ridge, 5-fold CV over all subjects -> out-of-fold predictions ----
pred = np.full(n, np.nan)
for tr, te in KFold(5, shuffle=True, random_state=0).split(np.arange(n)):
    pred[te] = RidgeCV(alphas=np.logspace(-1, 4, 12)).fit(X[tr], age[tr]).predict(X[te])
mae = float(np.mean(np.abs(pred - age)))
r_pt = float(pearsonr(pred, age)[0])

gap = pred - age                                                # naive brain-age gap
r_gap_age = float(pearsonr(gap, age)[0])                        # regression-to-the-mean confound

# ---- de Lange & Cole (2020) age-bias correction: CONTROLS-ONLY, cross-fitted within folds ----
# For each held-out fold, fit pred ~ a*age + b on the CONTROL subjects of the OTHER folds, then
# rescale pred_corr = (pred - b)/a. Patients never define their own correction; no subject informs
# its own correction -> no leakage.
pred_corr = np.full(n, np.nan)
for tr, te in KFold(5, shuffle=True, random_state=1).split(np.arange(n)):
    ctr = tr[control[tr]]                                       # controls in the training folds
    a, b = np.polyfit(age[ctr], pred[ctr], 1)
    pred_corr[te] = (pred[te] - b) / a
gap_corr = pred_corr - age
r_gapc_all = float(pearsonr(gap_corr, age)[0])
r_gapc_ctrl = float(pearsonr(gap_corr[control], age[control])[0])

# ---- downstream: dementia (CDR>0) vs healthy elderly (CDR=0) ----
dem, hc = demented, hc_elderly
mask = dem | hc
tn, pn = ttest_ind(gap[dem], gap[hc], equal_var=False)                   # naive, raw
tc, pc = ttest_ind(gap_corr[dem], gap_corr[hc], equal_var=False)         # corrected, raw
diff_n = float(gap[dem].mean() - gap[hc].mean())
diff_c = float(gap_corr[dem].mean() - gap_corr[hc].mean())
bN, tNa, pNa, dof = ols_group_effect(gap[mask], dem[mask], age[mask])          # naive, age-adjusted
bC, tCa, pCa, _ = ols_group_effect(gap_corr[mask], dem[mask], age[mask])       # corrected, age-adjusted

# ---- subject_gaps.csv: the per-subject data the verifier checks ----
group_name = np.where(dem, "dementia", np.where(hc_elderly, "healthy_elderly", "healthy_young"))
with open(OUT / "subject_gaps.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["index", "age", "cdr", "group", "predicted_age", "gap_naive", "gap_corrected"])
    for i in range(n):
        w.writerow([i, f"{age[i]:.1f}", ("" if not np.isfinite(cdr[i]) else f"{cdr[i]:g}"),
                    group_name[i], f"{pred[i]:.3f}", f"{gap[i]:.3f}", f"{gap_corr[i]:.3f}"])

(OUT / "brain_age.json").write_text(json.dumps({
    "dataset": "OASIS VBM (oasis1)", "n_subjects": int(n),
    "n_dementia": int(dem.sum()), "n_healthy_elderly": int(hc.sum()),
    "n_controls_nondemented": int(control.sum()),
    "model": "RidgeCV on gray-matter maps, 5-fold CV (out-of-fold predictions)",
    "mae_years": mae, "corr_pred_true": r_pt,
    "corr_gap_vs_chronological_age_naive": r_gap_age,
    "corr_gap_vs_chronological_age_corrected": r_gapc_all,
    "corr_gap_vs_age_corrected_controls": r_gapc_ctrl,
    "bias_correction": "de Lange & Cole 2020; controls-only; cross-fitted within CV folds (no leakage)",
    "dementia_vs_healthy_gap_naive_raw": {
        "mean_diff_years": diff_n, "t": float(tn), "p": float(pn)},
    "dementia_vs_healthy_gap_corrected_raw": {
        "mean_diff_years": diff_c, "t": float(tc), "p": float(pc)},
    "dementia_vs_healthy_gap_naive_age_adjusted": {
        "beta_years": bN, "t": tNa, "p": pNa, "df": dof},
    "dementia_vs_healthy_gap_corrected_age_adjusted": {
        "beta_years": bC, "t": tCa, "p": pCa, "df": dof},
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "OASIS VBM (oasis1)", "n_subjects": int(n),
    "groups": {"dementia_cdr_gt0": int(dem.sum()), "healthy_elderly_cdr0": int(hc.sum()),
               "healthy_young_unassessed": int((~demented & ~hc_elderly).sum())},
    "preprocessing": "gray-matter maps, 4 mm, gray-matter mask, top-variance-half voxels",
    "method": ("cross-validated Ridge brain-age model (out-of-fold); brain-age gap = predicted - "
               "chronological age; de Lange & Cole 2020 age-bias correction fit on CONTROLS ONLY and "
               "cross-fitted within CV folds (no leakage); dementia-vs-healthy comparison age-adjusted "
               "(chronological age as covariate)"),
}, indent=2))

(OUT / "findings.md").write_text(f"""# BRAINAGE-001 — the brain-age gap on OASIS

## A working brain-age model
A cross-validated Ridge model predicts chronological age from the gray-matter maps: MAE =
{mae:.1f} yr, r(predicted, true) = {r_pt:.2f} (n = {n}). Each subject's **brain-age gap** =
predicted - chronological age.

## The raw gap is confounded with age — regression to the mean (the un-cued check)
Because an imperfect regressor shrinks predictions toward the training-sample mean, the raw
brain-age gap is **spuriously, strongly correlated with chronological age**: r = {r_gap_age:.2f} —
younger subjects look "older-brained", older subjects "younger-brained". This is a
**regression-to-the-mean** artifact, not biology: after a de Lange & Cole (2020) age-bias
correction fit on **controls only** and **cross-fitted within CV folds** (no leakage), the
correlation vanishes (r = {r_gapc_ctrl:+.2f} in controls). The raw gap therefore manufactures an
age association that is a pure modelling artifact.

## The uncorrected gap masks the real dementia effect
Comparing the gap between dementia (CDR>0, older) and healthy-elderly (CDR=0) subjects:
- **naive raw gap:** mean difference {diff_n:+.1f} yr, t = {tn:.2f}, p = {pn:.2f} — **not
  significant**. This is exactly the age confound at work: dementia subjects are older, and the gap
  is biased downward with age (regression to the mean), so the raw comparison **masks** their
  accelerated ageing.
- **bias-corrected, age-adjusted gap:** {bC:+.1f} yr, t = {tCa:.2f}, p = {pCa:.3f} — **significant**
  (bias-corrected raw: {diff_c:+.1f} yr, p = {pc:.3f}). Once the regression-to-the-mean bias is
  removed and chronological age is controlled for, the real dementia effect **emerges**.

## Conclusion
The raw brain-age gap is **not** a clean biomarker as computed: it is mechanically confounded with
chronological age (regression to the mean, r = {r_gap_age:.2f}), which manufactures a spurious age
association and **masks the genuine dementia effect** ({diff_n:+.1f} yr naive, n.s.). The gap must be
**age-bias-corrected** (controls-only, within-fold, no leakage) and the group comparison
**age-adjusted** before any interpretation; only then does the real dementia effect appear
({bC:+.1f} yr, p = {pCa:.3f}). Reporting the uncorrected gap over-claims and misleads.
""")

print(f"OK: n={n} (dem={int(dem.sum())}, hc-eld={int(hc.sum())}); MAE={mae:.1f} r_pt={r_pt:.2f}; "
      f"gap~age {r_gap_age:.2f}->{r_gapc_ctrl:+.2f} corrected; "
      f"dementia naive {diff_n:+.1f}yr p={pn:.2f} -> corrected(age-adj) {bC:+.1f}yr p={pCa:.3f}")
