"""Reference (oracle) for EKLUND-001 — cluster failure: parametric cluster-extent inference has
inflated family-wise false-positive rates.

Paper anchor: Eklund, Nichols & Knutsson 2016, PNAS (10.1073/pnas.1602413113, "Cluster failure: Why
fMRI inferences for spatial extent have inflated false-positive rates"). Parametric cluster-extent
inference (Gaussian random-field theory, as in SPM/FSL/AFNI) assumes the spatial autocorrelation of
the statistic image is Gaussian with a known smoothness. Real fMRI spatial autocorrelation is
non-Gaussian and heavier-tailed, so real data produce much larger null clusters than the parametric
model predicts — inflating the cluster-level FWE false-positive rate (Eklund report up to ~70% vs the
nominal 5%). The fix is non-parametric permutation inference.

The task (un-cued) uses ADHD-200 resting-state fMRI as NULL data with a synthetic block-design task
regressor (true activation ~ 0), applies the standard cluster-forming threshold + cluster-extent FWE
correction, and asks how many clusters survive and how much to trust them. This reference VOLUNTEERS
the check the task never asks: the max-cluster null on REAL fMRI is far larger than a Gaussian field
of matched smoothness, so using the parametric (Gaussian) cluster-size threshold gives a family-wise
false-positive rate ~0.4-0.5 (≈8-10x nominal); permutation inference is calibrated.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)


def fail(reason):
    (OUT / "cluster.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    from scipy import ndimage
    from scipy.ndimage import gaussian_filter
    from scipy.stats import gamma
    from nilearn.datasets import fetch_adhd
    from nilearn.maskers import NiftiMasker
except Exception as e:  # pragma: no cover
    fail(f"import failed: {e}")

try:
    adhd = fetch_adhd(n_subjects=12)
except Exception as e:
    fail(f"could not fetch ADHD-200 resting-state data: {e}")

masker = NiftiMasker(mask_strategy="epi", smoothing_fwhm=8, standardize=True, detrend=True)
masker.fit(adhd.func[0])
mask_img = masker.mask_img_
mask3d = mask_img.get_fdata().astype(bool)
idx = np.where(mask3d)
try:
    Y = [masker.transform(f) for f in adhd.func]
except Exception as e:
    fail(f"could not mask/transform ADHD data: {e}")
if len(Y) < 6:
    fail(f"too few usable subjects ({len(Y)})")


def hrf(tr=2.0, n=32):
    t = np.arange(0, n * tr, tr)
    h = gamma.pdf(t, 6) - 0.35 * gamma.pdf(t, 16)
    return h / np.abs(h).sum()


def maxclust(tvec, thr):
    vol = np.zeros(mask3d.shape); vol[idx] = tvec
    lab, nl = ndimage.label(vol > thr)
    if nl == 0:
        return 0
    return int(np.max(np.bincount(lab.ravel())[1:]))


rng = np.random.default_rng(0)
NDES = 100
TTHR = 2.58   # cluster-forming threshold ~ p < 0.01 (one-sided z)
Tmax = max(ys.shape[0] for ys in Y)

real_max = []
for d in range(NDES):
    x = np.zeros(Tmax); i = 0; s = 0
    while i < Tmax:
        b = int(rng.integers(8, 14))
        if s:
            x[i:i + b] = 1
        i += b; s ^= 1
    xc = np.convolve(x, hrf(), mode="full")[:Tmax]; xc -= xc.mean()
    betas = []
    for ys in Y:
        xx = xc[:ys.shape[0]]
        betas.append((xx @ ys) / (xx @ xx))
    B = np.array(betas)
    t = B.mean(0) / (B.std(0, ddof=1) / np.sqrt(len(Y)) + 1e-9)
    real_max.append(maxclust(t, TTHR))
real_max = np.array(real_max)

# Gaussian field of matched (~8 mm FWHM) smoothness = what parametric RFT assumes
gauss_max = []
for d in range(NDES):
    g = gaussian_filter(rng.standard_normal(mask3d.shape), sigma=8 / 2.355 / 3.0)
    gv = g[idx]; gv = (gv - gv.mean()) / (gv.std() + 1e-9)
    gauss_max.append(maxclust(gv, TTHR))
gauss_max = np.array(gauss_max)

thr_param = float(np.percentile(gauss_max, 95))       # parametric FWE cluster-size threshold
thr_real = float(np.percentile(real_max, 95))         # true (permutation) FWE threshold on real data
fwer_param = float(np.mean(real_max > thr_param))     # FWER if you USE the parametric threshold on real data

(OUT / "cluster.json").write_text(json.dumps({
    "dataset": "ADHD-200 resting-state (null) + synthetic block design",
    "n_subjects": len(Y), "cluster_forming_threshold_z": TTHR, "n_null_realizations": NDES,
    "real_fmri_max_cluster_p95_voxels": thr_real,
    "gaussian_matched_smoothness_max_cluster_p95_voxels": thr_param,
    "familywise_error_rate_parametric_threshold": fwer_param,
    "nominal_rate": 0.05,
    "inflation_vs_nominal": fwer_param / 0.05,
    "method": "cluster-extent inference on null fMRI: parametric (Gaussian) vs permutation FWE",
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "ADHD-200 (nilearn fetch_adhd), resting-state as null",
    "n_subjects": len(Y),
    "method": "group one-sample t on synthetic block designs; cluster-extent FWE, parametric vs permutation",
}, indent=2))

(OUT / "findings.md").write_text(f"""# EKLUND-001 — cluster-extent inference on null fMRI

Data: {len(Y)} ADHD-200 **resting-state** subjects (no task), 8 mm smoothing, with a synthetic
block-design regressor — so the **true** number of activated clusters is ≈ 0 and a calibrated
cluster-extent test should wrongly flag activation ~5% of the time (family-wise).

## Parametric cluster-extent correction is anti-conservative
At a cluster-forming threshold z > {TTHR} (~p<0.01), over {NDES} random null designs:
- **Real fMRI** max-cluster null: 95th percentile = **{thr_real:.0f} voxels**.
- A **Gaussian field of matched smoothness** (what parametric RFT assumes): 95th percentile =
  **{thr_param:.0f} voxels**.
- Real fMRI produces far larger null clusters, because its spatial autocorrelation is **non-Gaussian /
  heavier-tailed** than the parametric model assumes. Using the parametric (Gaussian) cluster-size
  threshold on real data gives a **family-wise false-positive rate of {fwer_param:.2f}** — about
  **{fwer_param/0.05:.0f}× the nominal 0.05**.

## Conclusion
Standard **parametric cluster-extent inference** (Gaussian random-field theory, as in SPM/FSL/AFNI)
has **inflated cluster-level false-positive rates** on real fMRI, because the true spatial
autocorrelation violates the Gaussian-smoothness assumption (Eklund, Nichols & Knutsson 2016). Clusters
that "survive" parametric correction on null data are largely artifacts; valid cluster inference
requires **non-parametric permutation** testing. Reporting the parametric cluster count as real
activation over-states the evidence.
""")
print(f"OK: n={len(Y)} real-p95={thr_real:.0f} gauss-p95={thr_param:.0f}; "
      f"parametric FWER={fwer_param:.2f} ({fwer_param/0.05:.0f}x nominal)")
