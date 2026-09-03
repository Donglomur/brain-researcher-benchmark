"""Reference solution for WMMD-001.

Report the white-matter mean diffusivity (MD) and fractional anisotropy (FA) on dipy's
pinned multi-b `cfin_multib` acquisition (b = 0 .. 3000 s/mm^2 in steps of 200), over a
fixed white-matter ROI.

The one choice the task leaves open is HOW the diffusion signal is modelled from this
acquisition. The acquisition samples b-values up to 3000 s/mm^2, where the diffusion-
weighted signal departs measurably from a single mono-exponential decay. Fitting a plain
diffusion tensor (Gaussian / mono-exponential DTI) over the whole b-range therefore
biases the estimated diffusivity: the estimator absorbs the high-b signal curvature into
an artificially low apparent diffusion coefficient. The appropriate model here is the
diffusion-kurtosis tensor (DKI), whose diffusion tensor is the b -> 0 limit and recovers
the true Gaussian diffusivity. (Restricting a plain tensor to the low-b shells, b <= 1000,
gives a close-to-unbiased value too; fitting DTI over ALL shells does not.)

Validated WM-ROI means (cfin_multib, ROI = brain-mask & FA_lowb>0.5 = 10084 voxels;
MD reported in 1e-3 mm^2/s = um^2/ms):
    DKI, all shells (CORRECT)                 : MD = 0.883   FA = 0.638   <-- reported here
    DTI, low-b (b<=1000) only  (also correct) : MD = 0.801   FA = 0.649
    DTI, ALL shells (NAIVE, biased)           : MD = 0.586   FA = 0.660
The naive DTI-over-all-shells estimate underestimates MD by ~34% (a robust ~0.30e-3
gap, stable across WLS/OLS fitting and light smoothing). The verifier matches the
Gaussian MD region and every DTI-over-all-shells answer falls outside it.
"""
import json
import os
import sys
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")
import logging
logging.getLogger("dipy").setLevel(logging.ERROR)

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)

FA_ROI_THR = 0.5


def fail(reason):
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason,
         "dataset_id": "cfin_multib"}, indent=2))
    (OUT / "diffusivity.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason}))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    from dipy.data import read_cfin_dwi
    from dipy.core.gradients import gradient_table
    from dipy.segment.mask import median_otsu
    import dipy.reconst.dti as dti
    import dipy.reconst.dki as dki
except Exception as e:  # pragma: no cover
    fail(f"dipy import failed: {e}")

try:
    img, gtab = read_cfin_dwi()   # fetches to ~/.dipy if absent, then loads
    data = img.get_fdata()
except Exception as e:
    fail(f"could not resolve cfin_multib: {e}")

bvals, bvecs = gtab.bvals, gtab.bvecs
shell = np.round(bvals, -2).astype(int)          # 0, 200, ..., 3000

# ---- brain mask (fixed) ----
_, mask = median_otsu(data, vol_idx=[0], median_radius=4, numpass=2, dilate=1)

# ---- fixed WM ROI: low-b (b<=1000) DTI FA > 0.5, intersect brain mask ----
sel_low = shell <= 1000
gtab_low = gradient_table(bvals[sel_low], bvecs=bvecs[sel_low])
FA_low = dti.TensorModel(gtab_low).fit(data[..., sel_low], mask=mask).fa
roi = mask & (FA_low > FA_ROI_THR)
n_wm = int(roi.sum())
if n_wm < 500:
    fail(f"WM ROI has too few voxels ({n_wm})")

# ---- CORRECT model for a wide multi-b range: diffusion-kurtosis tensor ----
dkifit = dki.DiffusionKurtosisModel(gtab).fit(data, mask=roi)
MD = dkifit.md          # mm^2/s
FA = dkifit.fa

md_v = MD[roi]; md_v = md_v[np.isfinite(md_v)]
fa_v = FA[roi]; fa_v = fa_v[np.isfinite(fa_v)]
md_mean = float(np.mean(md_v)) * 1e3   # report in 1e-3 mm^2/s (= um^2/ms)
fa_mean = float(np.mean(fa_v))

(OUT / "diffusivity.json").write_text(json.dumps({
    "md_mean": md_mean,
    "fa_mean": fa_mean,
    "md_units": "1e-3 mm^2/s",
    "n_wm_voxels": n_wm,
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok",
    "dataset_id": "cfin_multib",
    "diffusion_model": "diffusion-kurtosis tensor (DKI), all shells; MD/FA from its diffusion tensor",
    "roi": "brain-mask (median_otsu vol_idx=[0], radius=4, numpass=2, dilate=1) & FA_lowb(b<=1000)>0.5",
    "n_wm_voxels": n_wm,
    "md_units": "1e-3 mm^2/s",
}, indent=2))

(OUT / "findings.md").write_text(f"""# WMMD-001 — white-matter mean diffusivity (cfin multi-b)

Using dipy's multi-b `cfin_multib` acquisition (b = 0 .. 3000 s/mm^2), I estimated the
diffusion parameters with the **diffusion-kurtosis tensor model (DKI)** and read the mean
diffusivity and fractional anisotropy from its diffusion-tensor part. Because this
acquisition extends to high b-values, a plain single-tensor (mono-exponential) fit over
the full b-range absorbs the high-b signal curvature and underestimates the diffusivity;
the kurtosis-tensor diffusion tensor (the b -> 0 limit) recovers the unbiased value.

In the fixed white-matter ROI ({n_wm} voxels; brain mask & low-b FA > {FA_ROI_THR}), the
mean diffusivity is **{md_mean:.3f} x 1e-3 mm^2/s** and the mean fractional anisotropy is
**{fa_mean:.3f}**.
""")
print(f"OK: md_mean={md_mean:.3f}e-3 mm2/s  fa_mean={fa_mean:.3f}  n_wm={n_wm}")
