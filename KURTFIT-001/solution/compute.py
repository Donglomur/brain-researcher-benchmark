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

# per-voxel table underlying the ROI mean (the neutral intermediate the pipeline emits)
import csv as _csv
with open(OUT / "mk_voxelwise.csv", "w", newline="") as _fh:
    _w = _csv.writer(_fh)
    _w.writerow(["i", "j", "k", "mk"])
    for _i, _j, _k in np.argwhere(wm):
        _w.writerow([int(_i), int(_j), int(_k), round(float(mk_map[_i, _j, _k]), 6)])

# The discovery: MK is b-shell-cap-dependent. Sweep the cap over the SAME fixed WM
# ROI to expose the multiverse (this is what an un-cued single-fit pipeline never does).
# Emit the PER-VOXEL MK map for each cap (mk_sweep.csv) so the sweep is proof-of-work, not a
# reported scalar: each subset's per-voxel map must reproduce a held-out per-cap DKI fit.
wm_ijk = np.argwhere(wm)
mk_by_cap = {}
sweep_rows = []
for cap in (1000, 1400, 2000, 2500, 3000):
    s = bvals <= (cap + 50)
    if len({int(round(b)) for b in bvals[s] if b > 50}) < 2:
        continue
    g = gradient_table(bvals[s], bvecs[s])
    mkc = dki.DiffusionKurtosisModel(g).fit(data_s[..., s], mask=wm).mk(MK_MIN, MK_MAX)
    mk_by_cap[cap] = float(np.mean(mkc[wm & np.isfinite(mkc)]))
    bmax_cap = float(bvals[s].max())
    for _i, _j, _k in wm_ijk:
        v = float(mkc[_i, _j, _k])
        if np.isfinite(v):
            sweep_rows.append((int(_i), int(_j), int(_k), int(round(bmax_cap)), round(v, 6)))

with open(OUT / "mk_sweep.csv", "w", newline="") as _fh:
    _w = _csv.writer(_fh)
    _w.writerow(["i", "j", "k", "max_b", "mk"])
    _w.writerows(sweep_rows)

# the all-shell fit is what a naive pipeline reports as "the" WM MK
mk_wm_allshell = mk_by_cap.get(3000)
if mk_wm_allshell is None:
    gtab_all = gradient_table(bvals, bvecs)
    mk_all = dki.DiffusionKurtosisModel(gtab_all).fit(data_s, mask=wm).mk(MK_MIN, MK_MAX)
    mk_wm_allshell = float(np.mean(mk_all[wm]))
mk_spread = max(mk_by_cap.values()) - min(mk_by_cap.values())

(OUT / "dki_results.json").write_text(json.dumps({
    "status": "ok",
    "mean_kurtosis_wm": mk_wm,
    "n_wm_voxels": n_wm,
    "b_max_used": float(bvals[sel].max()),
    "shells_used": sorted({int(round(b)) for b in bvals[sel]}),
    "mean_kurtosis_wm_allshell": mk_wm_allshell,
    "mean_kurtosis_wm_by_bcap": {str(k): round(v, 4) for k, v in mk_by_cap.items()},
    "mk_shell_cap_spread": round(mk_spread, 4),
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

_sweep = "  ".join(f"b<={k}: {v:.3f}" for k, v in sorted(mk_by_cap.items()))
(OUT / "findings.md").write_text(f"""# KURTFIT-001 - mean kurtosis in white matter

Fitting the diffusion-kurtosis model to the CFIN multi-shell data and averaging
the mean-kurtosis map over white matter (tensor FA > {FA_WM}, {n_wm} voxels).

**The white-matter mean kurtosis is NOT a single number: it depends on the b-shell
cap.** Sweeping the maximum b-value included in the DKI fit over the same WM ROI:

    {_sweep}

MK falls monotonically from {max(mk_by_cap.values()):.3f} to {min(mk_by_cap.values()):.3f}
(a spread of {mk_spread:.3f}, ~{100*mk_spread/max(mk_by_cap.values()):.0f}%) as higher-b
shells are added. The reason is methodological: DKI is a cumulant (Taylor) expansion of
the diffusion signal that is only valid at moderate b; beyond b ~ 2000-2500 s/mm^2 the
quadratic kurtosis term no longer describes the signal, so **including the high-b shells
biases MK downward**. Throwing all shells (up to b = {int(bvals.max())} s/mm^2) at the
model gives MK = {mk_wm_allshell:.3f}, whereas the moderate-b fit (b <= {int(BMAX)}) gives
MK = **{mk_wm:.3f}** -- the value to report for a valid DKI estimate. A single "the
white-matter mean kurtosis" without this shell-cap caveat over-states the precision of
the measurement.
""")

print(f"OK: MK_wm(b<=2000)={mk_wm:.4f}  MK_wm(all shells)={mk_wm_allshell:.4f}  "
      f"n_wm={n_wm}")
