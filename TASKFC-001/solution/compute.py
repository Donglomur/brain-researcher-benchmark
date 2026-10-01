"""Public canonical-HRF task-FC sensitivity with retained source/design/residual evidence."""
import glob
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)
TR = 1.5
RADIUS = 8.0
ROI = {"L_lateral_occipital": (-30, -90, -6), "R_lateral_occipital": (30, -90, -6)}
MOTION_COLS = ["X", "Y", "Z", "RotX", "RotY", "RotZ"]


def fail(reason):
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset_id": "language_localizer_demo"}, indent=2))
    (OUT / "connectivity_summary.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


def ols_resid(y, X):
    y = np.ascontiguousarray(y, dtype=np.float64)
    X = np.ascontiguousarray(X, dtype=np.float64)
    beta, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    # errstate guards a harmless, BLAS-specific matmul warning (macOS Accelerate) on some
    # non-contiguous inputs; the residual itself is finite and correct.
    with np.errstate(all="ignore"):
        return y - X @ beta


def fisher_mean(vals):
    return float(np.tanh(np.mean(np.arctanh(np.clip(np.asarray(vals, float), -0.999, 0.999)))))


try:
    from nilearn import datasets
    from nilearn.maskers import NiftiSpheresMasker
    from nilearn.glm.first_level import make_first_level_design_matrix
except Exception as e:  # pragma: no cover
    fail(f"nilearn import failed: {e}")

try:
    d = datasets.fetch_language_localizer_demo_dataset()
    data_dir = d["data_dir"] if isinstance(d, dict) or hasattr(d, "keys") else d[0]
except Exception as e:
    fail(f"could not resolve language_localizer_demo dataset: {e}")

subs = sorted({os.path.basename(p) for p in glob.glob(os.path.join(data_dir, "sub-*")) if os.path.isdir(p)})
if not subs:
    # derivatives-only layout fallback
    subs = sorted({os.path.basename(p) for p in glob.glob(os.path.join(data_dir, "derivatives", "sub-*"))})
if len(subs) != 10:
    fail(f"expected ~10 subjects, found {len(subs)}: {subs}")

coords = list(ROI.values())
rows = []
raws, bgs = [], []
for s in subs:
    func = glob.glob(os.path.join(data_dir, "derivatives", s, "func", "*preproc_bold.nii.gz"))
    ev = glob.glob(os.path.join(data_dir, s, "func", "*events.tsv"))
    cf = glob.glob(os.path.join(data_dir, "derivatives", s, "func", "*confounds*regressors.tsv"))
    if not (func and ev and cf):
        fail(f"missing input for pinned participant {s}")
    import nibabel as nib
    n = nib.load(func[0]).shape[-1]
    events = pd.read_csv(ev[0], sep="\t")
    conf = pd.read_csv(cf[0], sep="\t")
    ft = np.arange(n) * TR + TR / 2.0
    dm = make_first_level_design_matrix(ft, events, hrf_model="glover", drift_model="cosine", high_pass=0.01)
    task = dm[[c for c in dm.columns if c in ("language", "string")]].values
    drift = dm[[c for c in dm.columns if c.startswith("drift")]].values
    motion = conf[[c for c in MOTION_COLS if c in conf.columns]].fillna(0).values
    N = np.column_stack([np.ones(n), drift, motion])           # common nuisance (drift + motion)
    NT = np.column_stack([N, task])                            # + task-evoked response

    masker = NiftiSpheresMasker(coords, radius=RADIUS, detrend=False, standardize=False,
                                t_r=TR, allow_overlap=True)
    ts = masker.fit_transform(func[0])

    # task-state FC (the requested deliverable): correlation of the cleaned time series
    raw = float(np.corrcoef(ols_resid(ts[:, 0], N), ols_resid(ts[:, 1], N))[0, 1])
    # background connectivity: correlation of residuals after removing the task-evoked response
    bg = float(np.corrcoef(ols_resid(ts[:, 0], NT), ols_resid(ts[:, 1], NT))[0, 1])
    raw_residuals = ols_resid(ts, N)
    background_residuals = ols_resid(ts, NT)
    np.savez_compressed(OUT / f"intermediates_{s}.npz", roi_signals=ts,
                        nuisance_design=N, task_design=task,
                        raw_residuals=raw_residuals, background_residuals=background_residuals,
                        schema_version="taskfc-residual-v2")
    raws.append(raw)
    bgs.append(bg)
    rows.append(dict(subject=s, region_a="L_lateral_occipital", region_b="R_lateral_occipital",
                     connectivity=raw, background_connectivity=bg))

if len(rows) != 10:
    fail(f"only {len(rows)} subjects processed")

df = pd.DataFrame(rows)
# required deliverable: per-subject task-state FC (the raw correlation the instruction asks for)
df.to_csv(OUT / "connectivity.csv", index=False)

raw_g = fisher_mean(raws)
bg_g = fisher_mean(bgs)
t, p = stats.ttest_rel(np.arctanh(np.clip(raws, -0.999, 0.999)), np.arctanh(np.clip(bgs, -0.999, 0.999)))
n_infl = int(np.sum(np.asarray(raws) > np.asarray(bgs)))
delta_z = np.arctanh(np.clip(raws, -.999, .999)) - np.arctanh(np.clip(bgs, -.999, .999))
delta_mean = float(delta_z.mean())
delta_halfwidth = float(stats.t.ppf(.975, len(rows)-1) * delta_z.std(ddof=1)/np.sqrt(len(rows)))

(OUT / "connectivity_summary.json").write_text(json.dumps({
    "group_connectivity": raw_g,
    "n_subjects": int(len(rows)),
    "region_a": "L_lateral_occipital", "region_b": "R_lateral_occipital",
    "raw_task_state_connectivity": raw_g,
    "background_connectivity": bg_g,
    "evoked_inflation": raw_g - bg_g,
    "analysis_scope": "canonical-HRF model-dependent FC sensitivity; not intrinsic coupling",
    "inflation_paired_t": float(t), "inflation_p": float(p),
    "paired_z_sensitivity": {"n": len(rows), "mean_raw_minus_background_z": delta_mean,
                             "ci95": [delta_mean-delta_halfwidth, delta_mean+delta_halfwidth]},
    "n_subjects_raw_gt_background": n_infl,
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok",
    "dataset_id": "language_localizer_demo",
    "n_subjects": int(len(rows)),
    "roi": {"L_lateral_occipital": ROI["L_lateral_occipital"],
            "R_lateral_occipital": ROI["R_lateral_occipital"], "radius_mm": RADIUS},
    "preprocessing": "cosine high-pass drift (0.01 Hz) + 6 motion regressors; 8mm spheres; "
                     "task-state FC = Pearson r of regional BOLD time series; background FC = "
                     "Pearson r of residuals after also regressing the GLM task-evoked response "
                     "(language + string, Glover HRF)",
    "aggregation": "Fisher-z mean across subjects",
}, indent=2))

(OUT / "findings.md").write_text(
    f"# Canonical-HRF task-regression sensitivity\n\n"
    f"Raw Fisher-z averaged FC={raw_g:.4f}; canonical Glover task-regressed FC={bg_g:.4f}. "
    f"The signed raw-minus-residual group contrast is {raw_g-bg_g:+.4f}. "
    "The residual estimate depends on the response model and nuisance choices, and neither "
    "estimate identifies genuine/intrinsic coupling. This is a paper-derived sensitivity "
    "application, not a reproduction of Cole's flexible-response correction analysis.\n")

print(f"OK: raw={raw_g:.3f} background={bg_g:.3f} inflation={raw_g-bg_g:+.3f} "
      f"p={p:.2e} raw>bg in {n_infl}/{len(rows)}")
