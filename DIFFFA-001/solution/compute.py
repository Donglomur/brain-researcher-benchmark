"""Reference (oracle) for DIFFFA-001 — fractional anisotropy and the crossing-fiber trap.

Paper anchor: Pierpaoli & Basser 1996, Magn Reson Med (10.1002/mrm.1910360612, "Toward a quantitative
assessment of diffusion anisotropy") establishes FA as the standard rotationally-invariant measure of
white-matter organization; the crossing-fiber limitation of the single-tensor model is characterized
by Jeurissen et al. 2013, HBM (10.1002/hbm.22099) and Tournier et al. 2007 (CSD). The diffusion tensor
is a rank-1 (single-orientation) model, so in voxels containing >=2 crossing fiber populations it
cannot represent the geometry and FA drops sharply — NOT because the tissue is less organized, but
because the model is mis-specified. Crossing-fiber configurations occur in a large fraction of white
matter (~40-90%).

The task (un-cued) asks to compute FA and identify the white-matter regions of LOWEST microstructural
integrity/organization. The naive move is to report the lowest-FA white-matter voxels as the least
organized tissue. This reference VOLUNTEERS the check the task never asks: about half the white-matter
voxels contain crossing fibers, and those are exactly where single-tensor FA collapses (single-fiber
FA ~0.50 vs crossing ~0.33) — so the lowest-FA regions are dominated by crossing-fiber model failure,
not by genuinely low integrity. A multi-fiber model (CSD fODF peak count) identifies them.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)


def fail(reason):
    (OUT / "fa.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    from dipy.data import read_stanford_hardi, default_sphere
    from dipy.reconst.dti import TensorModel, fractional_anisotropy
    from dipy.reconst.csdeconv import ConstrainedSphericalDeconvModel, auto_response_ssst
    from dipy.direction import peaks_from_model
    from dipy.segment.mask import median_otsu
except Exception as e:  # pragma: no cover
    fail(f"import failed (need dipy): {e}")

try:
    img, gtab = read_stanford_hardi()
except Exception as e:
    fail(f"could not fetch Stanford HARDI diffusion data: {e}")
data = img.get_fdata()

b0, mask = median_otsu(data, vol_idx=[0], median_radius=3, numpass=1)
ten = TensorModel(gtab).fit(data, mask=mask)
FA = np.nan_to_num(fractional_anisotropy(ten.evals))
wm = mask & (FA > 0.2)
if int(wm.sum()) < 5000:
    fail(f"white-matter mask too small ({int(wm.sum())} voxels)")

resp, ratio = auto_response_ssst(gtab, data, roi_radii=10, fa_thr=0.7)
csd = ConstrainedSphericalDeconvModel(gtab, resp)
pk = peaks_from_model(csd, data, default_sphere, relative_peak_threshold=0.5,
                      min_separation_angle=25, mask=wm, npeaks=3, parallel=False)
npeaks = (np.abs(pk.peak_values) > 0).sum(-1)

single = wm & (npeaks == 1)
cross = wm & (npeaks >= 2)
n_wm, n_single, n_cross = int(wm.sum()), int(single.sum()), int(cross.sum())
fa_single, fa_cross = float(FA[single].mean()), float(FA[cross].mean())
frac_cross = n_cross / n_wm

# of the lowest-FA white-matter voxels (bottom 20% "least organized"), what fraction are crossing?
thr = np.percentile(FA[wm], 20)
lowfa = wm & (FA <= thr)
frac_lowfa_crossing = float((lowfa & cross).sum() / max(lowfa.sum(), 1))

(OUT / "fa.json").write_text(json.dumps({
    "dataset": "dipy Stanford HARDI (single subject, 150 directions, b=2000)",
    "n_white_matter_voxels": n_wm,
    "fraction_white_matter_with_crossing_fibers": frac_cross,
    "mean_FA_single_fiber": fa_single,
    "mean_FA_crossing_fiber": fa_cross,
    "FA_collapse_in_crossing_pct": float(100 * (1 - fa_cross / fa_single)),
    "fraction_of_lowest_FA_voxels_that_are_crossing": frac_lowfa_crossing,
    "method": "DTI fractional anisotropy vs CSD fODF peak count (single- vs multi-fiber voxels)",
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "dipy Stanford HARDI",
    "method": "single-tensor DTI FA vs constrained spherical deconvolution peak count",
}, indent=2))

(OUT / "findings.md").write_text(f"""# DIFFFA-001 — lowest-FA white matter and crossing fibers

White-matter voxels: {n_wm}. Fractional anisotropy (FA) from the diffusion tensor is the standard
measure of white-matter organization.

## The lowest-FA regions are dominated by crossing fibers, not low integrity
- **{frac_cross*100:.0f}% of white-matter voxels contain crossing fibers** (≥2 CSD fODF peaks) — the
  single-tensor model cannot represent them.
- Mean FA is **{fa_single:.2f}** in single-fiber voxels but only **{fa_cross:.2f}** in crossing-fiber
  voxels — a **{100*(1-fa_cross/fa_single):.0f}% collapse** caused by model mis-specification, not by
  less-organized tissue.
- Of the lowest-FA (bottom-20%) white-matter voxels — the "least organized" by FA —
  **{frac_lowfa_crossing*100:.0f}%** are crossing-fiber voxels.

## Conclusion
Low FA in white matter **does not** by itself indicate low microstructural integrity: the diffusion
tensor is a single-orientation model, so it under-estimates anisotropy wherever fibers cross, kiss, or
fan — which is roughly half of all white-matter voxels here (Jeurissen 2013; Tournier 2007). The
lowest-FA regions are largely crossing-fiber regions where the model fails, not genuinely disorganized
tissue. Assessing "integrity" from FA requires a crossing-aware model (e.g. CSD fODF peaks); reporting
the lowest-FA voxels as the least-organized white matter is misleading.
""")
print(f"OK: WM={n_wm} crossing={frac_cross*100:.0f}%; FA single={fa_single:.2f} cross={fa_cross:.2f} "
      f"({100*(1-fa_cross/fa_single):.0f}% collapse); low-FA crossing frac={frac_lowfa_crossing:.2f}")
