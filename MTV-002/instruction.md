# Macromolecular tissue volume (MTV) from a proton-density-mapping cohort

## Task
`/app/data/` holds a cohort of proton-density-mapping exams (`sub-01` … `sub-08`). Each
subject was scanned with a proton-density-weighted (long-TR, small-flip) spoiled gradient-echo
acquisition. From these signals, estimate the per-voxel **water content** quantities and write
them out.

The cohort is **heterogeneous**: every subject's sidecar declares what it actually acquired
(the echo times, and whether a receive-sensitivity map is provided), and the tissue map declares
which tissues are present — you must adapt the analysis per subject and **compute a quantity
only where the subject's acquisition determines it; where it does not, omit that quantity.**
There is no reference pipeline provided — implement the estimators yourself and get the physics,
units, and per-subject adaptation right.

Grading is **outcome-based and voxelwise**: each map you write is recomputed from the signals by
a held-out reference and compared voxel-by-voxel inside the brain mask.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects: the **signal model**, the
definition of the **TE=0 intercept `S0`** and **`R2star`**, the **receive-sensitivity
convention**, and the exact definitions of the graded quantities. Read it before you start. In
brief:

- The measured signal is `S(TE) = S0 * exp(-TE * R2star)`, where `S0` (the TE=0 intercept) is the
  apparent proton density `M0 = G * rx * WF`: `G` a global receive/scale gain (unknown, and it
  cancels in every graded quantity), `rx` the per-voxel receive sensitivity, and `WF` the tissue
  **water fraction** (proton density relative to pure water = 1.0).
- **`S0`** is the TE=0 intercept of a log-linear fit of `ln(S)` vs `TE` over a subject's echo
  train; when a subject provides only a single echo, `S0` is the measured signal itself.
  **`R2star`** (1/s) is the corresponding slope, determinable only for a multi-echo subject.
- The **receive-corrected proton density** is `PD = S0 / rx` when the sidecar ships an `rx_file`;
  when it does not, the acquisition is already receive-corrected (`rx = 1`).

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `field_T`, `n_vox`, `tr_ms`, `te_ms` (the echo times), `pdw_file`, `rx_file`
  (the receive map, or `null`), `tissue_file`, `mask_file`.
- `pdw.npy` — the PD-weighted signal, a float32 array of shape `(n_echoes, n_vox)` in the
  subject's voxel order.
- `rx.npy` — the per-voxel receive-sensitivity factor (shape `(n_vox,)`, 1.0 = nominal), present
  only when the subject needs it.
- `tissue.npy` — per-voxel tissue label (shape `(n_vox,)`; legend in the protocol: GM = 1,
  WM = 2, CSF = 3).
- `mask.npy` — the brain mask (shape `(n_vox,)`; maps are graded over these voxels).

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **computable** quantity, each of shape `(n_vox,)` in the subject's
voxel order:
- `WF_rel.npy` — the **relative water fraction** `PD / median_WM(PD)`, the receive-corrected
  proton density normalised by its median over the white-matter mask (label 2). Always computable.
- `R2star.npy` — the transverse relaxation rate (1/s) — **only for a multi-echo subject**.
- `MTV.npy` — the **macromolecular tissue volume** `MTV = 1 - PD / PD_water`, one minus the
  absolute water fraction, where `PD_water` is the receive-corrected proton density of **pure
  water**, anchored by the subject's cerebrospinal-fluid ROI (tissue label 3), whose water
  fraction is 1.0 by definition. **Only for a subject that has a CSF ROI** — a subject with no
  CSF voxels cannot pin the absolute normalisation.

Do **not** write a file for a quantity the subject's acquisition cannot support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for the
quantities you can produce so the rest of the cohort can be graded.
