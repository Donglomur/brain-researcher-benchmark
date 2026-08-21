# Model-free deconvolution of a heterogeneous multi-PLD ASL cohort

## Task
`/app/data/` holds a cohort of multi-post-labeling-delay (multi-PLD) arterial-spin-labeling
(ASL) exams (`sub-01` … `sub-08`). Each subject was scanned with one or more perfusion-weighted
(label-control difference) series along a PLD schedule. From these signals, estimate the
per-voxel **perfusion maps** and write them out.

The cohort is **heterogeneous**: every subject's sidecar declares the series it actually
acquired and its PLD schedule, and you must adapt the analysis per subject — a pipeline that
assumes one fixed recipe will not fit them all. **Compute a map only where the subject's
acquisition determines it; where it does not, omit that map.** There is no reference fitter
provided — implement the estimators yourself and get the kinetics, units, and per-subject
adaptation right.

Grading is **outcome-based and voxelwise**: each map you write is recomputed from the signals
by a held-out reference and compared voxel-by-voxel inside the brain mask. Partial cohorts and
partial map sets are scored proportionally, so produce every map you can support and omit the
rest.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects: the two inversions and
when each applies (the **block-circulant SVD deconvolution** of the crushed tissue curve with
the measured local arterial input, with its **pinned** truncation `p_svd`; and the
**single-compartment pCASL general kinetic model**), the exact definitions of **CBF**, **ATT**,
and **aBV**, the **unit** of each quantity, and the **tissue legend**. Read it before you start.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `n_vox`, `n_pld`, `n_rep`, the PLD step `dt_s`, the `pld_s` list, and a
  `series` list; each entry gives a `name`, a `kind` (`crushed`, `noncrushed`, or `asl`), and
  the `file` holding its signal.
- one `<name>.npy` per series — a float32 array of shape `(n_rep, n_pld, n_vox)`: the
  perfusion-weighted difference signal, one plane per repetition and PLD, in the subject's
  voxel order.
- `tissue.npy` — per-voxel tissue label (shape `(n_vox,)`; see the protocol legend, white
  matter = 2).
- `mask.npy` — the brain mask (shape `(n_vox,)`; maps are graded over these voxels).

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **computable** map, each of shape `(n_vox,)` in the subject's
voxel order:
- `CBF.npy` — cerebral blood flow (mL/100g/min).
- `ATT.npy` — arterial transit time (s).
- `aBV.npy` — arterial blood volume (calibrated units) — **only where determinable**.

Do **not** write a file for a map the subject's acquisition cannot support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for
the maps you can produce so the rest of the cohort can be graded.
