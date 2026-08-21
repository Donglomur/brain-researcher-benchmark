# Magnetic susceptibility source separation (chi-separation) of a heterogeneous cohort

## Task
`/app/data/` holds a cohort of quantitative susceptibility exams (`sub-01` … `sub-08`). Each
subject was scanned with a multi-echo gradient-echo (GRE) magnitude train and comes with the
already-computed **total susceptibility** map from QSM; most subjects were additionally scanned
with a multi-echo spin-echo (SE) magnitude train. From these, **separate the susceptibility
into its paramagnetic (iron) and diamagnetic (myelin/calcium) sources** and write the per-voxel
maps out.

The cohort is **heterogeneous**: every subject's sidecar declares exactly which acquisitions it
has (GRE echo times, whether an SE series is present, field strength, TRs), and you must adapt
the analysis per subject — a pipeline that assumes one fixed recipe will not fit them all.
**Compute a quantity only where the subject's acquisition determines it; where it does not, omit
that map.** No fitter is provided — implement the estimators yourself and get the physics, units,
and per-subject adaptation right.

Grading is **outcome-based and voxelwise**: each map you write is recomputed from the signals by
a held-out reference and compared voxel-by-voxel inside the brain mask. Partial cohorts and
partial map sets are scored proportionally, so produce every map you can support and omit the rest.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects: the mono-exponential
**signal model** for each train, the **relaxation-rate estimator** (ordinary least squares on the
natural-log magnitude), the definition of **R2′** (`= R2* − R2`), the **relaxometric constant**
`D_r = 90 × (field_T / 3)` (1/s per ppm), and the **chi-separation closed form** that turns the
given total susceptibility `chi_tot` and `R2′` into the two sources. Read it before you start.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `field_T`, `f0_mhz`, `n_vox`, a `gre` block (`file`, `tr_ms`, `te_ms`) and —
  when acquired — an `se` block of the same shape; plus the tissue/mask/chitot file names.
- `GRE.npy` — float32 `(n_echoes, n_vox)`: the multi-echo gradient-echo magnitude, one row per
  echo, in the subject's voxel order.
- `SE.npy` — float32 `(n_echoes, n_vox)`: the multi-echo spin-echo magnitude (**present only for
  some subjects**).
- `chitot.npy` — the given total susceptibility map `χ_tot` (shape `(n_vox,)`, ppm), already
  produced by QSM.
- `tissue.npy` — per-voxel tissue label (`(n_vox,)`; see the protocol legend).
- `mask.npy` — the brain mask (`(n_vox,)`; maps are graded over these voxels).

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **computable** map, each of shape `(n_vox,)` in the subject's voxel
order:
- `R2star.npy` — effective transverse relaxation rate (1/s) — **only where determinable**.
- `R2.npy` — irreversible transverse relaxation rate (1/s) — **only where determinable**.
- `chi_para.npy` — paramagnetic susceptibility source `χ_para ≥ 0` (ppm) — **only where determinable**.
- `chi_dia_abs.npy` — magnitude of the diamagnetic source `|χ_dia| ≥ 0` (ppm) — **only where determinable**.

Do **not** write a file for a map the subject's acquisition cannot support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for the
maps you can produce so the rest of the cohort can be graded.
