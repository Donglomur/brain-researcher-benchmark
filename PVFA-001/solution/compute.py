"""Reference solution for PVFA-001.

Estimate the fractional anisotropy (FA) of periventricular white matter from the
dipy Sherbrooke 3-shell diffusion-MRI dataset (`read_sherbrooke_3shell`,
b = 0/1000/2000/3500 s/mm^2) and report its mean over the pinned region.

The scientifically correct choice the task never spells out: periventricular white
matter is heavily contaminated by cerebrospinal fluid (CSF) partial volume. A
single diffusion tensor conflates the fast, isotropic CSF signal with the tissue,
which deflates the apparent FA. The recognised remedy (Pasternak et al. 2009;
Hoy et al. 2014) is to model an explicit free-water compartment (fwDTI) and report
the *tissue* FA. A naive single-tensor DTI fit reports the CSF-deflated FA.

Everything else is pinned so the number is reproducible: brain mask from the b0 via
median_otsu; a 1.25 mm FWHM Gaussian pre-smoothing; a periventricular region grown
from a CSF seed with fixed MD/FA criteria; model estimation on b <= 2000 (the
b = 3500 shell is too heavily diffusion-weighted for tensor estimation).

Validated reference (dipy-pinned Sherbrooke 3-shell, region below, 1740 voxels):
  free-water-accounted (fwDTI) tissue FA : 0.617   <- correct / reported
  single-tensor DTI FA (b <= 2000)       : 0.527   <- naive (CSF-deflated)
  single-tensor DTI FA (b <= 1000)       : 0.427   <- naive (standard DTI)
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

# pinned parameters
MR, NP, DIL = 4, 2, 1                     # median_otsu
FWHM = 1.25
CSF_MD, CSF_FA = 2.0e-3, 0.2
ROI_DIL, ROI_MDLO, ROI_MDHI, ROI_FA = 2, 0.8e-3, 1.5e-3, 0.25


def fail(reason):
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason,
         "dataset_id": "sherbrooke-3shell"}, indent=2))
    (OUT / "results.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason}))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    from scipy.ndimage import gaussian_filter, binary_dilation
    from dipy.data import read_sherbrooke_3shell
    from dipy.core.gradients import gradient_table
    from dipy.segment.mask import median_otsu
    import dipy.reconst.dti as dti
    import dipy.reconst.fwdti as fwdti
except Exception as e:  # pragma: no cover
    fail(f"import failed: {e}")

try:
    img, gtab = read_sherbrooke_3shell()   # fetch_sherbrooke_3shell under the hood
    data = np.asarray(img.get_fdata())
    bvals, bvecs = gtab.bvals, gtab.bvecs
except Exception as e:
    fail(f"could not resolve the Sherbrooke 3-shell dataset: {e}")

if data.ndim != 4 or bvals.max() < 3000:
    fail(f"unexpected data: shape {data.shape}, max b {bvals.max()}")


def gt(selb):
    sel = np.zeros(len(bvals), bool)
    for lo, hi in selb:
        sel |= (bvals >= lo) & (bvals <= hi)
    return gradient_table(bvals[sel], bvecs[sel]), sel


B0 = (-1, 50)
B1 = (950, 1050)
B2 = (1950, 2050)

# --- pinned preprocessing ---
_, mask = median_otsu(data, vol_idx=[0], median_radius=MR, numpass=NP,
                      autocrop=False, dilate=DIL)
gstd = FWHM / np.sqrt(8 * np.log(2))
data_s = gaussian_filter(data, sigma=(gstd, gstd, gstd, 0))

# --- conventional DTI maps (b <= 1000) for locating the region ---
g1, s1 = gt([B0, B1])
t1 = dti.TensorModel(g1).fit(data_s[..., s1], mask=mask)
FA1, MD1 = t1.fa, t1.md

CSF = mask & (MD1 > CSF_MD) & (FA1 < CSF_FA)
ROI = (binary_dilation(CSF, iterations=ROI_DIL) & mask & (~CSF)
       & (MD1 > ROI_MDLO) & (MD1 < ROI_MDHI) & (FA1 > ROI_FA))
n_roi = int(ROI.sum())
if n_roi < 300:
    fail(f"periventricular ROI too small ({n_roi} voxels)")

# --- the un-cued choice: account for the free-water (CSF) compartment ---
g2, s2 = gt([B0, B1, B2])
fw = fwdti.FreeWaterTensorModel(g2, fit_method='NLS').fit(data_s[..., s2], mask=ROI)
FA_fw, f_map = fw.fa, fw.f

# for context only: the single-tensor (CSF-deflated) FA a naive pipeline reports
FA_dti2 = dti.TensorModel(g2).fit(data_s[..., s2], mask=ROI).fa

v = ROI & np.isfinite(FA_fw)
fa_corr = float(np.mean(FA_fw[v]))
fa_unc = float(np.mean(FA_dti2[v]))
f_mean = float(np.mean(f_map[v]))
n = int(v.sum())

(OUT / "results.json").write_text(json.dumps({
    "status": "ok",
    "fa_periventricular_wm": fa_corr,
    "n_roi_voxels": n,
    "shells_used": [0, 1000, 2000],
    "free_water_fraction_mean": f_mean,
    "fa_single_tensor_context": fa_unc,
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset_id": "sherbrooke-3shell",
    "brain_mask": f"median_otsu vol_idx=[0] median_radius={MR} numpass={NP} dilate={DIL}",
    "smoothing_fwhm_mm": FWHM,
    "roi_definition": (
        f"CSF seed = (MD>{CSF_MD} & FA<{CSF_FA}) on b<=1000 DTI; "
        f"region = dilate(CSF,{ROI_DIL}) & in-brain & ~CSF & "
        f"{ROI_MDLO}<MD<{ROI_MDHI} & FA>{ROI_FA}"),
    "shells_available": sorted({int(round(b / 50) * 50) for b in bvals}),
    "shells_used_in_fit": [0, 1000, 2000],
    "n_roi_voxels": n,
}, indent=2))

(OUT / "findings.md").write_text(f"""# PVFA-001 - fractional anisotropy of periventricular white matter

Over the pinned periventricular white-matter region ({n} voxels), the fractional
anisotropy of the white-matter tissue is **{fa_corr:.3f}**.

These voxels border the lateral ventricles and are substantially contaminated by
cerebrospinal fluid (mean isotropic free-water signal fraction {f_mean:.2f}). A
single diffusion tensor conflates this fast, isotropic CSF signal with the tissue
and deflates the apparent anisotropy; accounting for the free-water compartment
recovers the tissue FA. For comparison, a single-tensor fit over the same voxels
gives FA = {fa_unc:.3f}. The value reported above is the tissue (free-water
accounted) FA.
""")

print(f"OK: FA_pv(free-water)={fa_corr:.4f}  FA_pv(single-tensor)={fa_unc:.4f}  "
      f"f={f_mean:.3f}  n_roi={n}")
