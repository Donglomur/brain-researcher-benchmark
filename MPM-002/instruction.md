# Quantitative multi-parameter mapping (MPM) of a heterogeneous SPGR cohort

## Task
`/app/data/` holds a cohort of quantitative multi-parameter-mapping exams
(`sub-01` … `sub-07`). Each subject was scanned with one or more multi-echo spoiled
gradient-echo (SPGR/FLASH) contrasts. From these signals, estimate the per-voxel
**quantitative maps** and write them out.

The cohort is **heterogeneous**: every subject's sidecar declares the contrasts it actually
acquired (flip angle, TR, echo times, and whether the contrast is MT-weighted), and you must
adapt the analysis per subject — a pipeline that assumes one fixed recipe will not fit them
all. **Compute a map only where the subject's acquisition determines it; where it does not,
omit that map.** There is no reference fitter provided — implement the estimators yourself and
get the physics, units, and per-subject adaptation right.

Grading is **outcome-based and voxelwise**: each map you write is recomputed from the signals
by a held-out reference and compared voxel-by-voxel inside the brain mask. Partial cohorts and
partial map sets are scored proportionally, so produce every map you can support and omit the
rest.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects: the SPGR **signal
model**, the **B1+ convention** (`a = B1 × radians(flip_deg)`, applied wherever a flip angle
enters), and the exact definitions of **R2\*** (ESTATICS joint fit), **R1 / PD** (the
rational-SPGR variable-flip-angle solve; `PD_norm` = the proton-density amplitude divided by
its white-matter median), **MTsat** (Helms 2008, in p.u.), the **unit** of each quantity, and
the **tissue legend**. Read it before you start.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `field_T`, `f0_mhz`, `n_vox`, and a `contrasts` list; each contrast gives
  `name`, `mt_weighted`, `flip_deg` (nominal), `tr_ms`, `te_ms` (the echo times), and the
  `file` holding its signal.
- one `<name>.npy` per contrast — a float32 array of shape `(n_echoes, n_vox)`: the magnitude
  SPGR signal, one row per echo, in the subject's voxel order.
- `b1.npy` — the per-voxel transmit factor B1 (shape `(n_vox,)`, 1.0 = nominal).
- `tissue.npy` — per-voxel tissue label (shape `(n_vox,)`; see the protocol legend, white
  matter = 2).
- `mask.npy` — the brain mask (shape `(n_vox,)`; maps are graded over these voxels).

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **computable** map, each of shape `(n_vox,)` in the subject's
voxel order:
- `R1.npy` — longitudinal relaxation rate (1/s).
- `PD_norm.npy` — white-matter-normalised proton density (dimensionless).
- `R2star.npy` — effective transverse relaxation rate (1/s) — **only where determinable**.
- `MTsat.npy` — magnetization-transfer saturation (p.u.) — **only where determinable**.

Do **not** write a file for a map the subject's protocol cannot support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for
the maps you can produce so the rest of the cohort can be graded.
