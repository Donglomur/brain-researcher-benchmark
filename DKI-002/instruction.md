# Diffusion-kurtosis imaging (DKI) of a heterogeneous multi-shell cohort

## Task
`/app/data/` holds a cohort of diffusion-MRI exams (`sub-01` … `sub-08`). Each subject was
scanned with a b=0 baseline plus one or more diffusion-weighted b-shells. From each subject's
signal and gradient table, estimate the per-voxel **diffusion-kurtosis scalar maps** and write
them out.

The cohort is **heterogeneous**: each subject's sidecar declares the shells it actually
acquired, and you must adapt the analysis per subject — **compute a map only where the
subject's acquisition determines it; where it does not, omit that map.** There is no fitter
provided — implement the estimators yourself and get the model, units, and per-subject
adaptation right.

Grading is **outcome-based and voxelwise against the true underlying physiology**: each map you
write is compared voxel-by-voxel, inside the brain-tissue mask, to the *true* metric that
generated the signals. **Any scientifically valid estimator is accepted** (ordinary or weighted
least squares, any dense direction set for the kurtosis averages, any robust volume-rejection
scheme) — every correct method recovers the same physical metrics within tolerance. You are
**not** required to match any particular reference implementation. Each (subject × map) is
scored independently.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects: the DKI **signal
model**, the **shell rule** (how the number of non-zero shells decides which maps are
determinable), the **estimator**, the exact **scalar definitions** and their **units**, and
the **tissue legend**. Read it before you start. In brief:

- **Signal model** (cumulant / Jensen 2005), per voxel:
  `ln S(b,n) = ln S0 − b·D(n) + (1/6)·b²·MD²·W(n)`, where `D(n)=nᵀD n` is the apparent
  diffusivity along unit direction `n`, `MD` the mean diffusivity, and
  `W(n)=Σ nᵢnⱼnₖnₗ Wᵢⱼₖₗ` the kurtosis-tensor form. Volumes with `b<50 s/mm²` are b0
  (`S0` = their mean). The apparent kurtosis along `n` is `K(n)=MD²·W(n)/D(n)²`.
- **Shell rule.** With **≥ 2 distinct non-zero b-shells** the kurtosis term is determined: fit
  the joint diffusion tensor `D` and kurtosis tensor `W` and report `MD, FA, MK, AK, RK`. With
  **exactly one non-zero shell** the `b²` term is not determinable: fit the mono-exponential
  diffusion tensor only, report `MD, FA`, and **omit** `MK, AK, RK`.
- **Estimator.** Fit the parameters by least squares on the natural-log signal (22 parameters
  for DKI: `ln S0`, the 6 unique `Dᵢⱼ`, the 15 unique `Wᵢⱼₖₗ`; 7 for the single-shell DTI
  fall-back). `MD` and `FA` are taken from the diffusion tensor `D` of the model you fit.

## Graded scalar definitions (convention-invariant)
- `MD = trace(D)/3`, reported in **µm²/ms** (= 10⁻³ mm²/s; multiply mm²/s by 1000).
- `FA = √(3/2)·‖D − (trace(D)/3)·I‖_F / ‖D‖_F` from the eigenvalues of `D` (0…1).
- `MK` = mean of the apparent kurtosis `K(n)` over the **unit sphere**.
- `AK` = `K(e1)` along the **principal** (largest-eigenvalue) eigenvector `e1` of `D`.
- `RK` = mean of `K(n)` over directions **perpendicular to `e1`**.

`MK`, `AK`, `RK` are dimensionless. These are rotation-invariant physical quantities; the
directional averages are over the whole sphere / the perpendicular ring, not a fixed triad.

## Robustness / data-quality contract  (READ THIS)
The signals are realistic, not clean:

- **Grossly corrupted volumes.** In a **majority of subjects, a handful of diffusion-weighted
  volumes are grossly corrupted** (motion spikes / signal dropouts) and are physically
  inconsistent with the diffusion-kurtosis decay of the rest of that subject's data. **You must
  detect and reject these corrupted volumes robustly before fitting** the tensor(s). *Which*
  subjects and *which* volumes are affected is **not disclosed** — find them from the data.
  Any scientifically valid robust scheme is acceptable (robust regression, log-residual outlier
  rejection, etc.); a non-robust fit over all volumes recovers a biased tensor/kurtosis on the
  affected subjects and fails those panels.
- **Rician noise** (modest, per-subject SNR) is present on every volume and needs no special
  handling beyond an ordinary fit.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `n_vox`, `n_meas`, the `shells` list (`b`, `n_dir`), and the file names.
- `dwi.npy` — float32 array of shape `(n_meas, n_vox)`: the magnitude diffusion signal, one
  row per acquired volume, in the subject's voxel order.
- `bvals.npy` — shape `(n_meas,)`, b-values in s/mm² (b<50 are b0).
- `bvecs.npy` — shape `(n_meas, 3)`, unit gradient directions (b0 rows arbitrary).
- `mask.npy` — the brain-tissue mask (shape `(n_vox,)`; maps are graded over these voxels).
- `tissue.npy` — per-voxel tissue label (shape `(n_vox,)`; see the protocol legend).

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **determinable** map, each of shape `(n_vox,)` in the subject's
voxel order:
- `MD.npy` — mean diffusivity (µm²/ms) — always.
- `FA.npy` — fractional anisotropy (0…1) — always.
- `MK.npy` — mean kurtosis — **only where the acquisition supports kurtosis**.
- `AK.npy` — axial kurtosis — **only where determinable**.
- `RK.npy` — radial kurtosis — **only where determinable**.

Do **not** write a file for a map the subject's acquisition cannot support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for
the maps you can produce so the rest of the cohort can be graded.
