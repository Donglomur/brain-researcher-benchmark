# Aggregate g-ratio mapping across a heterogeneous cohort

## Task
`/app/data/` holds a cohort of exams (`sub-01` … `sub-08`). Each subject carries a **myelin**
input and a **neurite** input. From these, estimate the per-voxel **myelin volume fraction**,
**fiber volume fraction**, and the **aggregate g-ratio**, and write them out.

The cohort is **heterogeneous**: every subject's sidecar declares what each input actually is
(the acquisition `model` and, for myelin, its calibration), and you must adapt per subject — a
pipeline that assumes one fixed recipe, or that trusts the mere presence of a file, will not
fit them all. **Compute a map only where the subject's inputs determine it; where they do not,
omit that map.** There is no reference implementation provided — combine the maps yourself and
get the definitions, units, and per-subject adaptation right.

Grading is **outcome-based and voxelwise against the true underlying physiology**: each map you
write is compared voxel-by-voxel, inside the brain mask, to the *true* map that generated the
data (the pinned definitions evaluated on the recoverable inputs — the myelin index recovered
from its repeats, and the neurite maps as acquired). **Any scientifically valid estimator is
accepted** — any NaN-aware robust repeat combine, the pinned volume-fraction arithmetic,
whatever validity floor for the g-ratio — because every correct method recovers the same maps
within tolerance. You are **not** required to reproduce any particular reference implementation's
output.

## Shared definitions and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects. Read it before you start.
The pinned definitions (dimensionless fractions throughout):

- **MVF** (myelin volume fraction) `= mvf_calibration × myelin_index`, where `myelin_index` is
  the single per-voxel index you **derive by combining the repeated acquisitions** listed in
  `myelin.files` (see below). Computable only when `myelin.model` is a quantitative myelin index
  (`mtsat` or `mtv`); `mvf_calibration` is given per subject (it is `1.0` for `mtv`).
- **FVF** (fiber/neurite volume fraction) from `neurite.model`: for `noddi`,
  `FVF = v_ic × (1 − v_iso)` (maps `neurite.vic_file`, `neurite.viso_file`); for `restricted`,
  `FVF = fr` (map `neurite.fr_file`).
- **AVF** (axonal volume fraction) `= (1 − MVF) × FVF`.
- **Aggregate g-ratio** `g = sqrt( 1 / (1 + MVF/AVF) ) = sqrt( AVF / (AVF + MVF) )`,
  dimensionless in (0, 1). A g-ratio requires **both** a myelin index and a neurite model.
  Where a myelinated axonal compartment is **not** present — the volume fractions are not
  physically positive (`AVF` collapses toward zero, e.g. CSF / near-void voxels) — the g-ratio
  is **undefined** and must be written as **NaN**, not a spurious number.

## Robustness / data-quality contract  (READ THIS)
The inputs are realistic, not clean:

- **The myelin index is delivered as repeats that must be combined robustly.** `myelin.files`
  lists several nominally-identical repeats of the same index. In a **majority of subjects, some
  repeats carry unannounced single-repeat corruption**: a localised **motion/spike** artifact
  (a large additive offset in one repeat) and/or a **failed-fit `NaN`** (the standard qMRI
  sentinel for a voxel where the quantitative fit did not converge in that repeat). The
  corruptions are spread across the repeats so that **no single repeat is clean**, but each voxel
  is hit in **at most one** repeat by **at most one** artifact. You must combine the repeats with
  a **NaN-aware, single-outlier-rejecting** combine (e.g. a per-voxel NaN-aware median): a plain
  mean propagates the spike (and is poisoned by the NaN), and a NaN-*unaware* median returns
  `NaN` wherever any repeat is `NaN` — poisoning the myelin index, MVF (which must be finite over
  the mask) and the g-ratio there. *Which* subjects / repeats / voxels are affected is **not
  disclosed**.
- **Not every provided file is a usable quantitative map.** The sidecar's `model` fields declare
  what each input actually is. A myelin `model` of `t1w`, or a neurite `model` of `dti`, is a
  **non-quantitative decoy**: the corresponding map (and any g-ratio depending on it) is **not
  computable and must be omitted** — trusting the mere presence of a file is wrong.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `n_vox`, `tissue_file`, `mask_file`, a `myelin` block (`model`,
  `mvf_calibration`, `files`), and a `neurite` block (`model` and its map file(s)). The `model`
  fields declare what each input is; **not every provided file is a usable quantitative map.**
- **The myelin input is delivered as repeated acquisitions:** `myelin.files` is a **list** of
  `.npy` paths — several nominally-identical repeats of the same myelin index, in acquisition
  order. Derive the single per-voxel `myelin_index` by combining them per voxel; they are
  repeats of one quantity, not independent maps.
- the input `.npy` maps named in the sidecar — each a float32 array of shape `(n_vox,)` in the
  subject's voxel order.
- `tissue.npy` — per-voxel tissue label (`(n_vox,)`; see the protocol legend, white matter = 2).
- `mask.npy` — the brain mask (`(n_vox,)`; maps are graded over these voxels).

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **computable** map, each of shape `(n_vox,)` in the subject's voxel
order:
- `MVF.npy` — myelin volume fraction.
- `FVF.npy` — fiber/neurite volume fraction.
- `g_ratio.npy` — aggregate g-ratio (NaN where undefined) — **only where both inputs support it.**

Do **not** write a file for a map the subject's inputs cannot support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for the
maps you can produce so the rest of the cohort can be graded.
