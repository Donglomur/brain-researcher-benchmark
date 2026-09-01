# Partial-volume correction of a heterogeneous ASL cerebral-blood-flow cohort

## Task
`/app/data/` holds a cohort of arterial-spin-labelling (ASL) perfusion exams
(`sub-01` … `sub-08`). Each subject provides a measured cerebral-blood-flow (CBF) map that is
**partial-volume contaminated** — every voxel mixes the perfusion of the tissues it contains —
together with a tissue segmentation. Recover the per-voxel **pure-tissue CBF** by the
linear-regression partial-volume correction (PVC) and write the maps out.

The cohort is **heterogeneous**: every subject's sidecar declares the segmentation it actually
provides and the correction kernel to use, and you must adapt per subject — a pipeline that
assumes one fixed recipe will not fit them all. **Produce a pure-tissue map only where the
subject's segmentation determines it; where it does not, omit that map.** There is no reference
implementation provided — implement the correction yourself and get the mixture model, the
windowed regression, the per-subject adaptation, and the units right.

Grading is **outcome-based and voxelwise against the true underlying physiology**. Each map you
write is compared voxel-by-voxel, where the local windowed fit determines that pure-tissue CBF, to
the *true* pure-tissue CBF the kernel supports (the locally-constant regression estimate of the
clean mixture — the true field varies gently within the kernel, so this is the *apparent*
pure-tissue value any correct PVC recovers). **Any scientifically valid estimator is accepted** —
any kernel gather, batched solve, or robust gross-spike rejection scheme — because every correct
method recovers the same value within tolerance. You are **not** required to reproduce any
particular reference implementation's output.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects: the **mixture model**
(`CBF_meas = P_GM·CBF_GM + P_WM·CBF_WM`, CSF non-perfusing and excluded), the **PVC definition**
(the windowed least-squares regression over each subject's pinned in-plane kernel), the
**segmentation fork** (which pure-tissue maps each segmentation supports), the **unit** of each
quantity, the **tissue legend**, and the **grid / array layout**. Read it before you start.

## Robustness / data-quality contract  (READ THIS)
The measured CBF is realistic, not clean:

- **Grossly corrupted voxels.** In a **minority of voxels on a majority of subjects**, the
  measured CBF is a **gross intravascular / motion spike** (values far above any plausible tissue
  perfusion) that is physically inconsistent with the local tissue mixture. Because the PVC is a
  *windowed* regression, one spike inside a kernel corrupts the fitted pure-tissue CBF of every
  central voxel whose window contains it. **You must detect and reject such grossly corrupted
  voxels robustly before (or during) the regression** — a plain least-squares fit over the raw
  kernel turns a spike into a large spurious pure-tissue CBF. *Which* voxels are corrupted is
  **not disclosed** — you must find them from the data. Any scientifically valid robust scheme is
  acceptable (robust/iteratively-reweighted regression, residual-outlier rejection, etc.).

Modest Gaussian measurement noise is present on every voxel and does **not** need special handling
beyond an ordinary fit.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `grid_shape` (`(nx, ny, nz)`; arrays are flattened C-order, slices along the
  last axis), `n_vox`, `tr_s`, `segmentation` (`"probabilistic"` or `"gm_only"`),
  `pvc_kernel_hw` (in-plane kernel half-width; side = `2·hw+1`), and the file names below.
- `cbf.npy` — the measured (partial-volume) CBF, float32 shape `(n_vox,)`, mL/100g/min.
- `pgm.npy` — the GM tissue fraction, float32 `(n_vox,)` in `[0, 1]`.
- `pwm.npy`, `pcsf.npy` — the WM and CSF tissue fractions (**probabilistic** subjects only).
- `mask.npy` — the brain mask, `(n_vox,)`; maps are graded within the brain.

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **computable** map, each of shape `(n_vox,)` in the subject's
voxel order:
- `CBF_GM.npy` — pure grey-matter CBF (mL/100g/min).
- `CBF_WM.npy` — pure white-matter CBF (mL/100g/min) — **only where the segmentation supports it.**

Do **not** write a file for a map the subject's segmentation cannot support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for
the maps you can produce so the rest of the cohort can be graded.
