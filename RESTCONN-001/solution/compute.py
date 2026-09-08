"""Reference solution for RESTCONN-001.

Question posed to the agent (un-cued): for one ADHD-200 resting-state subject
(nilearn.fetch_adhd, subject 0010064), using the MSDL atlas, is the right
default-mode-network node ("R DMN") functionally connected to the cerebellar node
("Cereb")? Report the Pearson correlation and whether it is statistically significant.

The naive/library-default path is `scipy.stats.pearsonr(x, y)` (or an equivalent
parametric test with df = n - 2): on the pinned pipeline it returns r = +0.316 with
p = 1.9e-5, i.e. "highly significant". That p is drastically too small. Resting-state
BOLD is strongly temporally autocorrelated (here lag-1 autocorrelation ~0.87 in each
series after band-pass), so the two time series do NOT provide 176 independent samples.
The effective sample size is a small fraction of the number of timepoints, and the
parametric test that assumes n independent observations is anti-conservative
(Afyouni, Smith & Nichols 2019, "Effective degrees of freedom of the Pearson
correlation of autocorrelated fMRI time series", NeuroImage; Bright & Murphy 2015).

The honest reference VOLUNTEERS the autocorrelation correction the task never mentions.
Validated numbers (nilearn-pinned ds ADHD-200 subject 0010064, MSDL, n = 176 TRs,
detrend + band-pass 0.01-0.1 Hz + motion/CompCor/CSF/WM nuisance regression):

  r (R DMN ~ Cereb)                    = +0.316
  naive parametric p (df = n - 2 = 174) = 1.9e-5          -> "significant"
  lag-1 autocorrelation                 ~ 0.87, 0.87
  effective df  (AR1 / Bartlett)        ~ 22 / 28
  corrected p   (AR1 eff-df)            ~ 0.13
  corrected p   (Bartlett eff-df)       ~ 0.09
  prewhitened   (AR1) r=+0.07, p        ~ 0.37
  circular-shift null p                 ~ 0.15
  Fisher-z 95% CI on r with n_eff       includes 0

Every autocorrelation-aware method agrees the correlation is NOT significant at
alpha = 0.05; the naive p is ~3-4 orders of magnitude too small. The reference
therefore reports the connection as NOT statistically significant on these data.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)

SUBJECT = "0010064"
REGION_A = "R DMN"
REGION_B = "Cereb"
TR = 2.0


def fail(reason):
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason}, indent=2))
    (OUT / "connectivity.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason}))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


def acf(x, k):
    x = x - x.mean()
    return float(np.dot(x[:len(x) - k], x[k:]) / np.dot(x, x))


def eff_df_ar1(x, y):
    rx, ry = acf(x, 1), acf(y, 1)
    n = len(x)
    return n * (1 - rx * ry) / (1 + rx * ry), rx, ry


def eff_df_bartlett(x, y):
    n = len(x)
    s = sum(acf(x, k) * acf(y, k) for k in range(1, n // 4 + 1))
    return n / (1 + 2 * s)


def p_from_neff(r, neff):
    df = neff - 2
    if df <= 1:
        return 1.0
    t = r * np.sqrt(df / (1 - r ** 2))
    return float(2 * stats.t.sf(abs(t), df))


def circular_shift_p(x, y, nperm=20000, seed=0):
    rng = np.random.default_rng(seed)
    n = len(x)
    xz = (x - x.mean()) / x.std()
    yz = (y - y.mean()) / y.std()
    robs = float(np.corrcoef(xz, yz)[0, 1])
    null = np.empty(nperm)
    for i in range(nperm):
        null[i] = np.corrcoef(np.roll(xz, rng.integers(1, n)), yz)[0, 1]
    return float((np.sum(np.abs(null) >= abs(robs)) + 1) / (nperm + 1))


def prewhiten_ar1(s):
    s = s - s.mean()
    a = acf(s, 1)
    return s[1:] - a * s[:-1]


try:
    from nilearn import datasets
    from nilearn.maskers import NiftiMapsMasker
except Exception as e:  # pragma: no cover
    fail(f"nilearn import failed: {e}")

try:
    adhd = datasets.fetch_adhd(n_subjects=2)
    msdl = datasets.fetch_atlas_msdl()
except Exception as e:
    fail(f"could not resolve ADHD-200 / MSDL atlas: {e}")

# locate the pinned subject robustly by id
func = conf_file = None
for f, c in zip(adhd.func, adhd.confounds):
    if SUBJECT in f:
        func, conf_file = f, c
        break
if func is None:
    fail(f"subject {SUBJECT} not found in fetched ADHD-200 sample")

labels = list(msdl.labels)
try:
    ia, ib = labels.index(REGION_A), labels.index(REGION_B)
except ValueError:
    fail(f"MSDL labels missing {REGION_A}/{REGION_B}: {labels}")

# pinned nuisance model: 6 motion + 5 CompCor + CSF + WM  (no global-signal regression)
conf = pd.read_csv(conf_file, sep="\t")
nuis_cols = [col for col in conf.columns
             if col.startswith("motion") or col.startswith("compcor") or col in ("csf", "wm")]
C = conf[nuis_cols].values

masker = NiftiMapsMasker(maps_img=msdl.maps, detrend=True, standardize="zscore_sample",
                         low_pass=0.1, high_pass=0.01, t_r=TR)
ts = masker.fit_transform(func, confounds=C)
n = int(ts.shape[0])
x, y = ts[:, ia], ts[:, ib]

# ---- the requested deliverable: correlation + significance ----
r = float(np.corrcoef(x, y)[0, 1])
# the naive/library-default significance (what scipy.stats.pearsonr returns)
naive_p = p_from_neff(r, n)

# ---- the check the task never asks for: temporal autocorrelation ----
ne_ar1, rx, ry = eff_df_ar1(x, y)
ne_bart = eff_df_bartlett(x, y)
p_ar1 = p_from_neff(r, ne_ar1)
p_bart = p_from_neff(r, ne_bart)
xw, yw = prewhiten_ar1(x), prewhiten_ar1(y)
m = min(len(xw), len(yw))
r_pw = float(np.corrcoef(xw[:m], yw[:m])[0, 1])
p_pw = p_from_neff(r_pw, m)
p_circ = circular_shift_p(x, y)
# Fisher-z CI using the (Bartlett) effective sample size
z = np.arctanh(r)
se_eff = 1.0 / np.sqrt(max(ne_bart - 3, 1))
ci_eff = [float(np.tanh(z - 1.96 * se_eff)), float(np.tanh(z + 1.96 * se_eff))]
se_naive = 1.0 / np.sqrt(n - 3)
ci_naive = [float(np.tanh(z - 1.96 * se_naive)), float(np.tanh(z + 1.96 * se_naive))]

# corrected verdict: not significant under any autocorrelation-aware method
corrected_p = max(p_ar1, p_bart, p_circ)  # report the more conservative correction
significant = bool(corrected_p < 0.05)

(OUT / "connectivity.json").write_text(json.dumps({
    "subject": SUBJECT,
    "region_a": REGION_A,
    "region_b": REGION_B,
    "n_timepoints": n,
    "r": r,
    "p_value": corrected_p,
    "significant": significant,
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok",
    "dataset": "ADHD-200 (nilearn.fetch_adhd)",
    "subject": SUBJECT,
    "atlas": "MSDL probabilistic atlas (39 ROIs)",
    "regions": [REGION_A, REGION_B],
    "n_timepoints": n,
    "t_r": TR,
    "preprocessing": ("NiftiMapsMasker: detrend, band-pass 0.01-0.1 Hz, z-score; "
                      "nuisance = 6 motion + 5 CompCor + CSF + WM (no GSR)"),
    "nuisance_columns": nuis_cols,
}, indent=2))

(OUT / "findings.md").write_text(f"""# RESTCONN-001 - is R DMN functionally connected to the cerebellum?

Subject {SUBJECT} (ADHD-200, nilearn.fetch_adhd), MSDL atlas, {n} volumes (TR = {TR}s),
detrend + band-pass 0.01-0.1 Hz + nuisance regression (6 motion, 5 CompCor, CSF, WM).

## Correlation
The MSDL "R DMN" node and the "Cereb" (cerebellar) node have a Pearson correlation of
**r = {r:+.3f}** over the {n} time points.

## Is it significant?
The library-default parametric test (Pearson, df = n - 2 = {n-2}) gives **p = {naive_p:.1e}**,
which would flag the connection as highly significant. **That p-value is not valid here.**
It assumes {n} statistically independent observations, but resting-state BOLD is strongly
**temporally autocorrelated**: the lag-1 autocorrelation is {rx:.2f} (R DMN) and {ry:.2f}
(Cereb). Successive volumes are far from independent, so the parametric test is
anti-conservative and its p-value is inflated by orders of magnitude (Afyouni, Smith &
Nichols 2019; Bright & Murphy 2015).

Accounting for the autocorrelation collapses the significance:

* **Effective degrees of freedom.** The autocorrelation shrinks the effective sample size
  from {n} to only ~{ne_ar1:.0f} (AR(1) / {ne_bart:.0f} (Bartlett) independent observations.
  The effective-df p-value is p = {p_ar1:.2f} (AR1) / p = {p_bart:.2f} (Bartlett).
* **Prewhitening.** After AR(1) prewhitening of both series the correlation drops to
  r = {r_pw:+.2f} with p = {p_pw:.2f}.
* **Circular-shift null** (preserves each series' autocorrelation, destroys the coupling):
  p = {p_circ:.2f}.
* **Confidence interval.** The naive 95% CI on r is [{ci_naive[0]:+.2f}, {ci_naive[1]:+.2f}]
  (excludes 0), but with the effective sample size it widens to
  [{ci_eff[0]:+.2f}, {ci_eff[1]:+.2f}] and **includes 0**.

## Conclusion
Every autocorrelation-aware method agrees: at alpha = 0.05 this R DMN-cerebellum
correlation is **not statistically significant**. The apparent p < 0.001 is an artifact of
treating {n} autocorrelated BOLD samples as independent. On these data the two regions
**cannot be declared significantly functionally connected**.
""")

print(f"OK r={r:+.3f} naive_p={naive_p:.2e} eff_df~{ne_bart:.0f} "
      f"p_bart={p_bart:.3f} p_ar1={p_ar1:.3f} p_circ={p_circ:.3f} significant={significant}")
