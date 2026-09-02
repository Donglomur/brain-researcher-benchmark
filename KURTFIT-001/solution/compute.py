"""Reference solution for KURTFIT-001.

Fit the diffusion-kurtosis model (DKI) to the CFIN multi-shell diffusion MRI
dataset (dipy `fetch_cfin_multib` / `read_cfin_dwi`, b = 0..3000 s/mm^2 in steps
of 200) and report the mean kurtosis (MK) averaged over white matter.

The scientifically correct choice the task never spells out: DKI is a *cumulant
(Taylor) expansion* of the log-signal in b, valid only up to moderate b-values.
Beyond b ~ 2000-2500 s/mm^2 the second-order kurtosis term no longer describes
the signal and the fit is biased. The standard recommendation (Jensen & Helpern
2010; Veraart et al. 2011) is to CAP the fit at b <= ~2000 s/mm^2. Fitting all
shells up to b = 3000 biases MK downward.

Everything else is pinned so the number is reproducible: brain mask from the b0
via median_otsu; a 1.25 mm FWHM Gaussian pre-smoothing (the canonical DKI-example
preprocessing); white matter defined as tensor FA > 0.4; MK clipped to [0, 3].

Validated reference (nilearn/dipy-pinned CFIN multi-b, whole brain):
  MK in WM, fit capped at b <= 2000  : 1.021   <- correct / reported
  MK in WM, fit over ALL shells      : 0.957   <- naive (high-b bias)
"""
import json
import os
import sys
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")
OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)

FA_WM = 0.40
FWHM = 1.25
BMAX = 2000.0          # cap the cumulant expansion at moderate b
MK_MIN, MK_MAX = 0.0, 3.0


def fail(reason):
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason,
         "dataset_id": "cfin-multib"}, indent=2))
    (OUT / "dki_results.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason}))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    from scipy.ndimage import gaussian_filter
    from dipy.data import read_cfin_dwi
    from dipy.core.gradients import gradient_table
    import dipy.reconst.dki as dki
    import dipy.reconst.dti as dti
    from dipy.segment.mask import median_otsu
except Exception as e:  # pragma: no cover
    fail(f"import failed: {e}")

try:
    img, gtab = read_cfin_dwi()   # fetch_cfin_multib under the hood
    data = np.asarray(img.get_fdata())
    bvals, bvecs = gtab.bvals, gtab.bvecs
except Exception as e:
    fail(f"could not resolve the CFIN multi-shell dataset: {e}")

if data.ndim != 4 or bvals.max() < 2500:
    fail(f"unexpected data: shape {data.shape}, max b {bvals.max()}")

# --- pinned preprocessing ---
_, mask = median_otsu(data, vol_idx=[0], median_radius=4, numpass=2,
                      autocrop=False, dilate=1)
gstd = FWHM / np.sqrt(8 * np.log(2))
data_s = gaussian_filter(data, sigma=(gstd, gstd, gstd, 0))

# --- the un-cued choice: restrict the DKI fit to moderate b (cumulant validity) ---
sel = bvals <= (BMAX + 50)
gtab_fit = gradient_table(bvals[sel], bvecs[sel])
data_fit = data_s[..., sel]

# white matter ROI from a tensor fit (on the same moderate-b data)
FA = dti.TensorModel(gtab_fit).fit(data_fit, mask=mask).fa

# DKI mean kurtosis
mk_map = dki.DiffusionKurtosisModel(gtab_fit).fit(data_fit, mask=mask).mk(MK_MIN, MK_MAX)

wm = mask & (FA > FA_WM) & np.isfinite(FA) & np.isfinite(mk_map)
n_wm = int(wm.sum())
if n_wm < 500:
    fail(f"white-matter ROI too small ({n_wm} voxels)")

mk_wm = float(np.mean(mk_map[wm]))

# for context only: the all-shell fit (what a naive pipeline reports)
gtab_all = gradient_table(bvals, bvecs)
mk_all = dki.DiffusionKurtosisModel(gtab_all).fit(data_s, mask=wm).mk(MK_MIN, MK_MAX)
mk_wm_allshell = float(np.mean(mk_all[wm]))

(OUT / "dki_results.json").write_text(json.dumps({
    "status": "ok",
    "mean_kurtosis_wm": mk_wm,
    "n_wm_voxels": n_wm,
    "b_max_used": float(bvals[sel].max()),
    "shells_used": sorted({int(round(b)) for b in bvals[sel]}),
    "mean_kurtosis_wm_allshell": mk_wm_allshell,
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset_id": "cfin-multib",
    "n_shells_total": len(sorted({int(round(b)) for b in bvals})),
    "b_max_available": float(bvals.max()),
    "b_max_used_in_fit": float(bvals[sel].max()),
    "wm_definition": f"tensor FA > {FA_WM}",
    "preprocessing": f"median_otsu brain mask; {FWHM} mm FWHM Gaussian smoothing",
    "mk_clip": [MK_MIN, MK_MAX],
    "n_wm_voxels": n_wm,
}, indent=2))

(OUT / "findings.md").write_text(f"""# KURTFIT-001 - mean kurtosis in white matter

Fitting the diffusion-kurtosis model to the CFIN multi-shell data and averaging
the mean-kurtosis map over white matter (tensor FA > {FA_WM}, {n_wm} voxels):

**Mean kurtosis (MK) in white matter = {mk_wm:.3f}.**

DKI is a cumulant expansion of the diffusion signal that is only valid at moderate
b-values; beyond b ~ 2000-2500 s/mm^2 the quadratic kurtosis term no longer
describes the signal. The fit was therefore restricted to b <= {int(BMAX)} s/mm^2.
For comparison, fitting *all* shells up to b = {int(bvals.max())} s/mm^2 pulls MK
down to {mk_wm_allshell:.3f} - a downward bias of {mk_wm - mk_wm_allshell:.3f}
driven by the high-b shells where the cumulant expansion breaks down. The value
reported above uses the moderate-b fit.
""")

print(f"OK: MK_wm(b<=2000)={mk_wm:.4f}  MK_wm(all shells)={mk_wm_allshell:.4f}  "
      f"n_wm={n_wm}")
