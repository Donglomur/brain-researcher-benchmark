# Calibrated-BOLD CMRO2 estimation across a heterogeneous gas-challenge cohort

## Task
`/app/data/` holds a cohort of calibrated-BOLD exams (`sub-01` … `sub-08`). Each subject was
scanned with **simultaneous BOLD and ASL perfusion (CBF)** during a functional **task**, and
most subjects additionally had a **gas-calibration** run (a hypercapnia or a hyperoxia
challenge). From these timeseries, estimate the **Davis (1998) calibration constant M** and the
**relative CMRO2 change during the task**, and write the maps out.

The cohort is **heterogeneous**: every subject's sidecar declares the runs it actually acquired
and, for each run, the challenge condition. You must adapt the analysis per subject — a pipeline
that assumes one fixed recipe will not fit them all. **Compute a map only where the subject's
acquisition determines it; where it does not, omit that map.** There is no reference pipeline
provided — implement the estimators yourself and get the physics, units, and per-subject
adaptation right.

Grading is **outcome-based and voxelwise**: each map you write is recomputed from the timeseries
by a held-out reference and compared voxel-by-voxel inside the grey-matter mask. Partial cohorts
and partial map sets are scored proportionally, so produce every map you can support and omit the
rest.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects: the **Davis model**, the
fixed model constants (`alpha`, the field-dependent `beta`, and the blood-oxygen constants
`phi`, `epsilon`), the exact **percent-change** definition, the **M-value** estimators for the
**hypercapnia** and the **hyperoxia** calibrations, the **relative-CMRO2** inversion, the
**unit** of each quantity, and the **tissue legend**. Read it before you start.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `field_T`, `beta`, `n_vox`, a `runs` list, and (for a hyperoxia subject) a
  `blood_gas` block. Each run gives `name`, `condition` (`task`, `hypercapnia`, or `hyperoxia`),
  the `bold_file` and `cbf_file`, `n_frames`, and the `baseline_frames` / `active_frames`
  indices.
- one `<run>_bold.npy` and one `<run>_cbf.npy` per run — each a float32 array of shape
  `(n_frames, n_vox)`: the BOLD magnitude timeseries and the simultaneously-acquired
  perfusion-weighted (ASL) CBF timeseries, in the subject's voxel order. The CBF timeseries is in
  arbitrary perfusion units (only ratios are used).
- `tissue.npy` — per-voxel tissue label (shape `(n_vox,)`; see the protocol legend, grey
  matter = 1).
- `gm_mask.npy` — the grey-matter mask (shape `(n_vox,)`; maps are graded over these voxels).

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **computable** map, each of shape `(n_vox,)` in the subject's voxel
order, in the **percent units** defined by the protocol:
- `rBOLD.npy` — relative BOLD change during the task (%).
- `rCBF.npy` — relative CBF change during the task (%).
- `M.npy` — the Davis calibration constant (%) — **only where a gas calibration determines it**.
- `rCMRO2.npy` — relative CMRO2 change during the task (%) — **only where determinable**.

Do **not** write a file for a map the subject's acquisition cannot support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for the
maps you can produce so the rest of the cohort can be graded.
