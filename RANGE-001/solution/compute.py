"""Reference (oracle) for RANGE-001 — a wide-age-range 'brain maturity' prediction accuracy is inflated
by RANGE RESTRICTION (between-age-group discrimination), not within-cohort maturation tracking.

Paper anchor: the brain-age / 'brain maturity' prediction literature (Dosenbach et al. 2010, Science,
"Prediction of individual brain maturity using fMRI") and its critiques — a connectivity→age model
evaluated across a very wide age span reports a high accuracy that mostly reflects the ability to tell
a 7-year-old from a 60-year-old, and collapses within any narrow band. Correlation magnitude depends on
the sampling range (range restriction / attenuation).

The task (un-cued) asks to predict age from connectivity as a 'brain maturity' index and judge how well
it tracks maturation. The naive move is to report the wide-range cross-validated accuracy (r ~ 0.67) as
strong maturity tracking. This reference VOLUNTEERS the check the task never asks: the same model,
evaluated WITHIN any single developmental band, predicts age near chance (r ~ -0.04 to 0.18) — the wide-
range accuracy is a range-restriction artifact (between-age-group separation), not within-cohort
maturation tracking.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)


def fail(reason):
    (OUT / "maturity.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    from nilearn.datasets import fetch_abide_pcp
    from nilearn.connectome import ConnectivityMeasure
    from sklearn.linear_model import Ridge
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    from sklearn.model_selection import cross_val_predict, KFold
    from scipy.stats import pearsonr
except Exception as e:  # pragma: no cover
    fail(f"import failed: {e}")

import pandas as pd

try:
    fetch_abide_pcp(derivatives=["rois_cc200"], pipeline="cpac",
                    band_pass_filtering=True, global_signal_regression=False, quality_checked=False)
except Exception:
    pass
base = os.path.expanduser("~/nilearn_data/ABIDE_pcp")
ddir = os.path.join(base, "cpac", "filt_noglobal")
pheno = os.path.join(base, "Phenotypic_V1_0b_preprocessed1.csv")
if not os.path.exists(pheno):
    fail("could not resolve ABIDE phenotypic table")
ph = pd.read_csv(pheno)
ph = ph[ph["FILE_ID"] != "no_filename"]

ts, age = [], []
for _, r in ph.iterrows():
    f = os.path.join(ddir, str(r["FILE_ID"]) + "_rois_cc200.1D")
    if not os.path.exists(f):
        continue
    a = np.loadtxt(f)
    if a.ndim != 2 or a.shape[0] <= 50 or a.shape[1] < 200 or not np.isfinite(float(r["AGE_AT_SCAN"])):
        continue
    ts.append(a[:, :200]); age.append(float(r["AGE_AT_SCAN"]))
if len(ts) < 200:
    fail(f"only {len(ts)} usable subjects")
X = np.nan_to_num(ConnectivityMeasure(kind="correlation", vectorize=True, discard_diagonal=True).fit_transform(ts))
age = np.asarray(age)


def pred_r(Xm, ym):
    if len(ym) < 40:
        return None
    pr = cross_val_predict(make_pipeline(StandardScaler(), PCA(50), Ridge(10.0)), Xm, ym,
                           cv=KFold(5, shuffle=True, random_state=0))
    return float(pearsonr(pr, ym)[0])


full_r = pred_r(X, age)
bands = [(6, 12), (12, 18), (18, 30)]
within = {}
for lo, hi in bands:
    m = (age >= lo) & (age < hi)
    within[f"{lo}-{hi}y"] = {"n": int(m.sum()), "r": pred_r(X[m], age[m])}
within_vals = [v["r"] for v in within.values() if v["r"] is not None]
mean_within = float(np.mean(within_vals))

(OUT / "maturity.json").write_text(json.dumps({
    "dataset": "ABIDE (rois_cc200)", "n_subjects": int(len(ts)),
    "age_range": [float(age.min()), float(age.max())],
    "full_range_FC_to_age_prediction_r": full_r,
    "within_band_prediction_r": within,
    "mean_within_band_r": mean_within,
    "method": "connectivity->age Ridge (PCA) 5-fold CV, full range vs within developmental bands",
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "ABIDE (ABIDE_pcp, cpac, rois_cc200)", "n_subjects": int(len(ts)),
    "method": "FC->age prediction, full-range vs within-band (range-restriction check)",
}, indent=2))

blines = "\n".join(f"| {k} (n={v['n']}) | {v['r']:+.2f} |" for k, v in within.items())
(OUT / "findings.md").write_text(f"""# RANGE-001 — does connectivity track brain maturation?

{len(ts)} subjects, ages {age.min():.0f}-{age.max():.0f}. A connectivity→age model as a 'brain maturity'
index.

## The wide-range accuracy is a range-restriction artifact
- **Full age range ({age.min():.0f}-{age.max():.0f}y)**: FC→age prediction r = **{full_r:+.2f}** — looks
  like connectivity strongly tracks maturation.
- **Within any single developmental band**, the same model predicts age near chance:

| band | within-band r |
|---|---|
{blines}

Mean within-band r = **{mean_within:+.2f}**. The high full-range accuracy comes from telling far-apart
age groups apart (a 7-year-old from a 40-year-old), **not** from tracking maturation within a cohort. The
correlation magnitude is inflated by the wide sampling **range**, not by a strong per-subject maturity
signal (range restriction / attenuation).

## Conclusion
Reporting the wide-range r ({full_r:+.2f}) as evidence that connectivity **tracks brain maturation**
over-states it: within any developmental band the signal is ~{mean_within:+.2f} (near chance). The
apparent 'maturity index' is a between-age-group discriminator whose accuracy depends on the age range
sampled; it does not demonstrate within-cohort maturational tracking. Prediction accuracy across a wide
range must be interpreted against the within-range effect.
""")
print(f"OK: n={len(ts)}; full-range r={full_r:+.2f}; within-band r={[round(v['r'],2) for v in within.values()]} "
      f"mean={mean_within:+.2f}")
