# Regional brain-iron mapping from R2* and susceptibility

## Task
`/app/data/` holds a cohort of iron-mapping exams (`sub-01` … `sub-08`). Each subject was
scanned with a multi-echo gradient-echo sequence and has an accompanying quantitative
susceptibility map. From these two iron-sensitive contrasts, estimate the per-voxel **non-heme
iron concentration** (mg per 100 g wet weight) and write it out.

The cohort is **heterogeneous**: every subject's sidecar declares its own field strength, echo
times and echo count, and the region map declares which tissue each voxel belongs to — you must
adapt the analysis per subject, because a pipeline that assumes one fixed recipe (one field, one
region, one echo count) will not fit them all. **Compute a map only where the subject's
acquisition determines it; where it does not, omit that map.** There is no reconstruction library
provided — implement the estimators yourself and get the physics, units, referencing and
per-subject/per-region adaptation right.

Grading is **outcome-based and voxelwise**: each map you write is recomputed from the signals by
a held-out reference and compared voxel-by-voxel inside the brain mask. Each (subject × map) is
scored independently, so produce every map you can support and omit the rest.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the definitions and conventions common to all subjects. **Read it before you
start.** It pins:
- the **R2\*** definition (per-voxel mono-exponential decay rate of the multi-echo magnitude,
  fitted by ordinary least squares on `ln(S)` vs `TE`) and the fact that R2\* is determinable
  **only for multi-echo subjects**;
- the **susceptibility referencing** convention (subtract the mean of `chi` over the
  reference-region voxels before calibrating);
- the pinned **linear iron calibrations** — a per-region susceptibility calibration and a
  per-field, per-region R2\* calibration, with their coefficients;
- the **validity window**: report `NaN` for any voxel whose calibrated iron falls outside the
  physical range stated there;
- the **region legend** and the **units**.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `field_T`, `f0_mhz`, `n_vox`, `tr_ms`, a `gre` block (`file`, `te_ms`,
  `n_echoes`), and the `chi_file` / `region_file` / `mask_file` names.
- `gre_mag.npy` — the multi-echo GRE **magnitude**, a float32 array of shape `(n_echoes, n_vox)`,
  one row per echo, in the subject's voxel order.
- `chi.npy` — the provided per-voxel susceptibility map (ppm, shape `(n_vox,)`).
- `region.npy` — per-voxel region label (shape `(n_vox,)`; see the protocol legend).
- `mask.npy` — the brain mask (shape `(n_vox,)`; maps are graded over these voxels).

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **computable** map, each of shape `(n_vox,)` in the subject's voxel
order:
- `iron_chi.npy` — susceptibility-based iron concentration (mg/100 g).
- `iron_r2s.npy` — R2\*-based iron concentration (mg/100 g) — **only where R2\* is determinable**.

Do **not** write a file for a map the subject's acquisition cannot support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for the
maps you can produce so the rest of the cohort can be graded.
