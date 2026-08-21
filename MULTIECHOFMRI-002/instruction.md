# Multi-echo fMRI: T2* mapping and the optimal echo combination

## Task
`/app/data/` holds a cohort of multi-echo functional-MRI (BOLD/EPI) exams (`sub-01` … `sub-08`).
Each subject was scanned with a short resting time series acquired at **two to five echoes**.
From these echo time series, estimate the per-voxel **T2\*** and the temporal SNR of the
**T2\*-weighted optimal echo combination**, and write them out.

The cohort is **heterogeneous**: every subject's sidecar declares the echo times it actually
acquired, and you must adapt the analysis per subject — the number of echoes determines which
quantities the data can support, so a pipeline that assumes one fixed recipe will not fit them
all. **Compute a map only where the subject's acquisition determines it; where it does not,
omit that map.** There is no reference fitter provided — implement the estimators yourself and
get the physics, units, and per-subject adaptation right.

Grading is **outcome-based and voxelwise**: each map you write is recomputed from the echo
time series by a held-out reference and compared voxel-by-voxel inside the brain mask. Partial
cohorts and partial map sets are scored proportionally, so produce every map you can support
and omit the rest.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects: the multi-echo **signal
model** (`S_e(t) = S0·exp(-TE_e/T2*)`, TE and T2\* in **ms**), the exact definitions of **T2\***
and **S0** (the per-voxel mono-exponential fit of each echo's temporal-mean magnitude; log-linear
`ln(mean_e)` vs `TE_e`; reported **only** from ≥3 echoes; `S0_norm` = S0 divided by its brain-mask
median), the **optimal-combination weighting** (`w_e = TE_e·exp(-TE_e/T2*)`, Poser 2006) and the
**tSNR** definition (temporal mean / temporal standard deviation, `ddof=0`, of the combined
series), the **unit** of each quantity, and the **tissue legend**. Read it before you start.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `field_T`, `f0_mhz`, `n_vox`, `n_echoes`, `n_frames`, `te_ms` (the echo-time
  list), and the filenames below.
- one `echo-<k>.npy` per echo (listed in `echo_files`, acquisition order) — a float32 array of
  shape `(n_frames, n_vox)`: the magnitude signal of that echo, one row per time frame, in the
  subject's voxel order.
- `tissue.npy` — per-voxel tissue label (shape `(n_vox,)`; see the protocol legend).
- `mask.npy` — the brain mask (shape `(n_vox,)`; maps are graded over these voxels).

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **computable** map, each of shape `(n_vox,)` in the subject's voxel
order:
- `tSNR.npy` — temporal SNR of the T2\*-weighted optimal echo combination (dimensionless).
- `T2star.npy` — effective transverse relaxation time (ms) — **only where determinable**.
- `S0_norm.npy` — brain-mask-median-normalised TE=0 amplitude (dimensionless) — **only where
  determinable**.

Do **not** write a file for a map the subject's echo train cannot support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for
the maps you can produce so the rest of the cohort can be graded.
