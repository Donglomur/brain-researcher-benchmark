"""Reference solution for FODCROSS-001.

Estimate the fibre orientation distribution (fODF) on dipy's multi-shell
`sherbrooke_3shell` acquisition (b = 0, 1000, 2000, 3500) and report the fraction of
white-matter voxels in a fixed centrum-semiovale ROI that contain a crossing (>= 2 fODF
peaks), with the ROI and peak/crossing definition pinned by the task.

The one choice the task leaves open is HOW the fODF is estimated from this acquisition.
Because the data are genuinely multi-shell, the correct estimator is multi-shell
multi-tissue constrained spherical deconvolution (MSMT-CSD; Jeurissen et al. 2014):
it models white matter, grey matter and CSF jointly, so it removes the spurious fODF
lobes that single-shell CSD produces from grey-matter / CSF partial volume. Single-shell
CSD (a single-tissue response fed one shell, or the mixed multi-shell signal) OVER-detects
crossings in exactly the lower-FA, partial-volume voxels of this ROI.

Validated crossing fractions (sherbrooke_3shell, ROI box [45:83, 45:90, 31:36] & mask &
0.30<FA<0.90 = 5060 voxels; peaks_from_model rel_thr=0.5, sep=25 deg, npeaks=3, sh8):
    MSMT-CSD (correct)                 : crossing_frac = 0.349   <-- reported here
    single-shell CSD, all mixed shells : crossing_frac = 0.484
    single-shell CSD, b=1000 only      : crossing_frac = 0.457
    single-shell CSD, b=3500 only      : crossing_frac = 0.696
MSMT gives materially FEWER crossings; the single-shell values are inflated by partial
volume. The gap is stable across the individual ROI slices.
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

BOX = (slice(45, 83), slice(45, 90), slice(31, 36))
REL_THR, SEP_ANGLE, NPEAKS, SH = 0.5, 25, 3, 8


def fail(reason):
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason,
         "dataset_id": "sherbrooke_3shell"}, indent=2))
    (OUT / "crossing.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason}))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    from dipy.data import read_sherbrooke_3shell, default_sphere
    from dipy.core.gradients import gradient_table
    from dipy.segment.mask import median_otsu
    import dipy.reconst.dti as dti
    from dipy.reconst.mcsd import (auto_response_msmt,
                                   multi_shell_fiber_response,
                                   MultiShellDeconvModel)
    from dipy.direction import peaks_from_model
except Exception as e:  # pragma: no cover
    fail(f"dipy import failed: {e}")

try:
    img, gtab = read_sherbrooke_3shell()   # fetches to ~/.dipy if absent, then loads
    data = img.get_fdata()
except Exception as e:
    fail(f"could not resolve sherbrooke_3shell: {e}")

bvals, bvecs = gtab.bvals, gtab.bvecs
shell = np.round(bvals, -2).astype(int)          # 0, 1000, 2000, 3500
b0 = data[..., shell == 0].mean(-1)
_, mask = median_otsu(b0, median_radius=3, numpass=1)

# ---- fixed ROI: centrum-semiovale slab & brain mask & 0.30 < FA < 0.90 ----
sel1 = (shell == 0) | (shell == 1000)
gtab1 = gradient_table(bvals[sel1], bvecs=bvecs[sel1])
box = np.zeros(mask.shape, bool)
box[BOX] = True
tfit = dti.TensorModel(gtab1).fit(data[..., sel1], mask=box & mask)
FA = tfit.fa
roi = (box & mask) & (FA > 0.30) & (FA < 0.90)
n_roi = int(roi.sum())
if n_roi < 100:
    fail(f"ROI has too few voxels ({n_roi})")

# ---- CORRECT fODF estimator for multi-shell data: MSMT-CSD ----
gtab_r = gradient_table(shell.astype(float), bvecs=bvecs)
rwm, rgm, rcsf = auto_response_msmt(gtab_r, data, roi_radii=10)
response = multi_shell_fiber_response(
    sh_order_max=SH, bvals=np.array([0., 1000., 2000., 3500.]),
    wm_rf=rwm, gm_rf=rgm, csf_rf=rcsf)
model = MultiShellDeconvModel(gtab_r, response, sh_order_max=SH)

pk = peaks_from_model(model, data, default_sphere,
                      relative_peak_threshold=REL_THR,
                      min_separation_angle=SEP_ANGLE,
                      mask=roi, npeaks=NPEAKS, return_odf=False, parallel=False)
npeaks_vox = (pk.peak_values > 0).sum(-1)[roi]
n_cross = int(np.sum(npeaks_vox >= 2))
crossing_fraction = float(np.mean(npeaks_vox >= 2))

(OUT / "crossing.json").write_text(json.dumps({
    "crossing_fraction": crossing_fraction,
    "n_roi_voxels": n_roi,
    "n_crossing_voxels": n_cross,
    "mean_peaks_per_voxel": float(npeaks_vox.mean()),
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok",
    "dataset_id": "sherbrooke_3shell",
    "fodf_method": "multi-shell multi-tissue constrained spherical deconvolution (MSMT-CSD)",
    "sh_order_max": SH,
    "roi_box": "data[45:83, 45:90, 31:36] & brain-mask & 0.30<FA<0.90",
    "n_roi_voxels": n_roi,
    "peak_params": {"relative_peak_threshold": REL_THR,
                    "min_separation_angle": SEP_ANGLE, "npeaks": NPEAKS,
                    "sphere": "default_sphere"},
}, indent=2))

(OUT / "findings.md").write_text(f"""# FODCROSS-001 — crossing-fibre fraction in the centrum semiovale

Using dipy's multi-shell `sherbrooke_3shell` acquisition, I estimated the fibre
orientation distribution with **multi-shell multi-tissue constrained spherical
deconvolution (MSMT-CSD)**, which is the appropriate estimator for a multi-shell
acquisition: by modelling white matter, grey matter and CSF together it suppresses the
spurious fODF lobes that single-tissue single-shell CSD produces from partial-volume
contamination.

In the fixed centrum-semiovale ROI ({n_roi} white-matter voxels, 0.30 < FA < 0.90), the
fraction of voxels whose fODF contains a crossing (>= 2 peaks; peaks_from_model with
relative_peak_threshold=0.5, min_separation_angle=25 deg, npeaks=3) is
**{crossing_fraction:.3f}** ({n_cross} / {n_roi} voxels; mean {npeaks_vox.mean():.3f}
peaks per voxel).
""")
print(f"OK: crossing_fraction={crossing_fraction:.3f} n_roi={n_roi} n_cross={n_cross} "
      f"mean_peaks={npeaks_vox.mean():.3f}")
