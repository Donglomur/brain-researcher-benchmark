"""Reference solution for PERFDIFF-001 (un-cued estimator-dependence / over-claim).

The brief asks, plainly, to estimate the intravoxel-incoherent-motion (IVIM)
perfusion fraction f (and D, D*) in a defined ROI of a real diffusion-MRI dataset
(dipy `fetch_ivim` / `read_ivim`, 21 b-values 0..1000 s/mm^2). It does NOT mention
that the answer depends on the fit algorithm.

The trap is over-claim. The IVIM biexponential is ill-conditioned, and its
parameters -- especially the perfusion fraction f and the pseudo-diffusion
coefficient D* -- are notoriously **fit-method dependent** (Barbieri et al. 2016;
While 2017). On this exact ROI, the *same voxels* give a materially different f
depending on the estimator:

  Full biexponential Trust-Region NLLS (dipy fit_method='trr') : f ~ 0.21 (median 0.20)
  Segmented two-step fit (D from high-b, then f)               : f ~ 0.12 (median 0.09)
  per-voxel f spans ~0.03 - 0.36; D* differs even more between methods.

So the honest deliverable is NOT one confident number: it DISCOVERS and REPORTS
that f is estimator-dependent (roughly 0.09-0.21 here), and that the perfusion
compartment (f, D*) is only weakly determined. A solution that runs one fitter and
asserts a single confident f is unwarranted.

Reproducible ROI: dipy IVIM example slice z=33, box x[90:120], y[90:120]; tissue
voxels (S0 above half the ROI median).
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

Z = 33
X0, X1, Y0, Y1 = 90, 120, 90, 120
BSEG = 200.0   # high-b threshold for the segmented tissue-diffusion step


def fail(reason):
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset_id": "ivim"}, indent=2))
    (OUT / "ivim_results.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason}))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    from dipy.data.fetcher import read_ivim
    from dipy.reconst.ivim import IvimModel
except Exception as e:  # pragma: no cover
    fail(f"import failed: {e}")

try:
    img, gtab = read_ivim()          # fetch_ivim under the hood
    data = np.asarray(img.get_fdata())
    bvals = np.asarray(gtab.bvals, float)
except Exception as e:
    fail(f"could not resolve the IVIM dataset: {e}")

if data.ndim != 4 or len(set(np.round(bvals).astype(int))) < 15:
    fail(f"unexpected IVIM data: shape {data.shape}, {len(bvals)} b-values")

roi = data[X0:X1, Y0:Y1, Z, :].astype(float)
s0 = roi[..., 0]
tissue = s0 > (0.5 * np.median(s0[s0 > 0]))
n_tissue = int(tissue.sum())
if n_tissue < 100:
    fail(f"ROI tissue mask too small ({n_tissue} voxels)")


def summarise(f, D, Dstar, label):
    f = np.asarray(f, float); D = np.asarray(D, float); Dstar = np.asarray(Dstar, float)
    ok = tissue & np.isfinite(f) & np.isfinite(D) & np.isfinite(Dstar) & (f >= 0) & (f <= 1)
    fv = f[ok]
    return {
        "method": label,
        "f_mean": float(np.mean(fv)), "f_median": float(np.median(fv)),
        "f_p10": float(np.percentile(fv, 10)), "f_p90": float(np.percentile(fv, 90)),
        "D_mean": float(np.mean(D[ok])), "Dstar_mean": float(np.mean(Dstar[ok])),
        "n_voxels": int(ok.sum()),
    }


# --- estimator 1: full biexponential, Trust-Region NLLS (dipy default) ---
trr_fit = IvimModel(gtab, fit_method="trr").fit(roi)
res_trr = summarise(trr_fit.perfusion_fraction, trr_fit.D, trr_fit.D_star, "trr")


# --- estimator 2: segmented two-step fit (classic IVIM) ---
def segmented(sig):
    S0 = sig[0]
    if S0 <= 0:
        return np.nan, np.nan, np.nan
    hi = bvals >= BSEG
    if hi.sum() < 3:
        return np.nan, np.nan, np.nan
    y = np.log(np.clip(sig[hi], 1e-6, None))
    A = np.vstack([np.ones(hi.sum()), -bvals[hi]]).T
    intercept, D = np.linalg.lstsq(A, y, rcond=None)[0]
    f = 1.0 - np.exp(intercept) / S0
    # D* from the low-b perfusion residual (fixed D, f)
    lo = bvals < BSEG
    Dstar = np.nan
    if f > 1e-3 and lo.sum() >= 3:
        perf = (sig[lo] / S0) - (1.0 - f) * np.exp(-bvals[lo] * D)
        perf = np.clip(perf / max(f, 1e-6), 1e-6, None)
        A2 = np.vstack([np.ones(lo.sum()), -bvals[lo]]).T
        Dstar = np.linalg.lstsq(A2, np.log(perf), rcond=None)[0][1]
    return f, D, Dstar


fS = np.full(s0.shape, np.nan); DS = np.full(s0.shape, np.nan); DsS = np.full(s0.shape, np.nan)
for idx in np.argwhere(tissue):
    t = tuple(idx)
    fS[t], DS[t], DsS[t] = segmented(roi[t])
res_seg = summarise(fS, DS, DsS, "segmented")

results = [res_trr, res_seg]
f_means = [r["f_mean"] for r in results]
f_lo = min(r["f_p10"] for r in results)
f_hi = max(r["f_p90"] for r in results)

(OUT / "ivim_results.json").write_text(json.dumps({
    "status": "ok",
    "roi": {"slice_z": Z, "x": [X0, X1], "y": [Y0, Y1], "n_tissue_voxels": n_tissue},
    "fits": results,
    "perfusion_fraction_by_method": {r["method"]: r["f_mean"] for r in results},
    "perfusion_fraction_range": [round(min(f_means), 4), round(max(f_means), 4)],
    "perfusion_fraction_voxelwise_range": [round(f_lo, 4), round(f_hi, 4)],
    "estimator_dependent": True,
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset_id": "ivim",
    "n_bvalues": int(len(bvals)), "bval_max": float(bvals.max()),
    "roi": {"slice_z": Z, "x": [X0, X1], "y": [Y0, Y1], "n_tissue_voxels": n_tissue},
    "fit_methods": ["trr (full biexponential NLLS)", "segmented (two-step)"],
    "note": "biexponential IVIM fit; f and D* compared across estimators",
}, indent=2))

t, s = res_trr, res_seg
(OUT / "findings.md").write_text(f"""# PERFDIFF-001 - IVIM perfusion fraction in the ROI

I estimated the IVIM parameters (perfusion fraction f, tissue diffusion D, and
pseudo-diffusion D*) in the ROI (slice z={Z}, {n_tissue} tissue voxels) with the
biexponential model, using two standard estimators.

## The perfusion fraction is estimator-dependent
The perfusion fraction **f is not a single well-determined value** on these data -
it depends materially on the fitting algorithm:

| fit method | f (ROI mean) | f (median) | D (mm^2/s) | D* (mm^2/s) |
|---|---|---|---|---|
| Full biexponential, Trust-Region NLLS (`trr`) | {t['f_mean']:.3f} | {t['f_median']:.3f} | {t['D_mean']:.2e} | {t['Dstar_mean']:.2e} |
| Segmented two-step fit | {s['f_mean']:.3f} | {s['f_median']:.3f} | {s['D_mean']:.2e} | {s['Dstar_mean']:.2e} |

Across estimators the ROI-mean f ranges **{min(f_means):.2f} - {max(f_means):.2f}**,
and per-voxel it spans roughly **{f_lo:.2f} - {f_hi:.2f}**. The pseudo-diffusion
coefficient D* is even less stable between methods.

## Why
The IVIM biexponential is ill-conditioned: the perfusion compartment is constrained
almost entirely by the few low-b (b < ~200) points, so f and D* trade off strongly
and the solution depends on the estimator and its initialisation (Barbieri et al.
2016; While 2017).

## Conclusion
The honest answer is a **range, not a point**: f is estimator-dependent, ~
{min(f_means):.2f}-{max(f_means):.2f} (ROI mean; wider per-voxel). Reporting a
single confident perfusion fraction from one fitter would overstate what these data
determine.
""")

print(f"OK: f_by_method={ {r['method']: round(r['f_mean'],3) for r in results} } "
      f"range={round(min(f_means),3)}-{round(max(f_means),3)}")
