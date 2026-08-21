# Quantitative DSC perfusion of a heterogeneous cohort (rCBV, rCBF, rMTT)

## Task
`/app/data/` holds a cohort of dynamic-susceptibility-contrast (DSC) perfusion exams
(`sub-01` … `sub-08`). Each subject was scanned during the first pass of a gadolinium bolus
with a gradient-echo DSC sequence. From the signal time-series, estimate the per-voxel
**normal-appearing-white-matter-normalised perfusion maps** and write them out.

The cohort is **heterogeneous**: every subject's sidecar declares its acquisition (TR, TE,
baseline length, whether an arterial input function was captured, and the clinical
blood-brain-barrier leakage status), and you must adapt the analysis per subject — a pipeline
that assumes one fixed recipe will not fit them all. **Compute a map only where the exam
determines it; where it does not, omit that map.**

There is no reference tool provided — implement the estimators yourself and get the physics,
units, and per-subject adaptation right. Grading is **outcome-based and voxelwise**: each map
you write is recomputed from the signals by a held-out reference and compared voxel-by-voxel
inside the brain mask.

## Graded quantities (all NAWM-normalised, dimensionless)
For each voxel report, divided by the same quantity's mean over the **normal-appearing white
matter (NAWM)** reference:

- **rCBV** — relative cerebral blood volume: the NAWM-normalised time-integral of the tissue
  concentration `dR2*(t)`.
- **rCBF** — relative cerebral blood flow: the NAWM-normalised peak of the flow-scaled residue
  from deconvolving `dR2*(t)` with the AIF.
- **rMTT** — relative mean transit time = `rCBV / rCBF` (central-volume theorem).

Normalising to NAWM makes the global scale (κ/ρ/hematocrit), the echo time, and the AIF
amplitude cancel, so these three quantities are uniquely determined by the pinned recipe.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the conventions common to all subjects: the **concentration** definition
(`dR2*(t) = -ln(S(t)/S0)/TE`, `S0` = mean of the first `n_baseline` frames), the **AIF**
convention, the **pinned block-circulant truncated-SVD deconvolution** (padding to `L=2·n_frames`,
matrix `G[i,j]=dt·AIF[(i-j) mod L]`, singular-value truncation threshold `PSVD=0.20`, CBF =
peak of the residue), the **Boxerman-Weisskoff leakage correction** to apply to leakage exams,
the **NAWM normalisation**, the **units**, and the **tissue legend**. Read it before you start.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `n_frames`, `n_vox`, `tr_ms`, `te_ms`, `n_baseline`, `leakage` (bool), and
  `aif_file` (the AIF filename, or `null` when no AIF was captured).
- `dsc.npy` — the DSC signal, a float32 array of shape `(n_frames, n_vox)` in voxel order.
- `aif.npy` — present only when an AIF was captured: the pinned arterial `dR2*(t)`, shape
  `(n_frames,)`.
- `tissue.npy` — per-voxel tissue label (shape `(n_vox,)`; see the protocol legend, white
  matter = 2).
- `mask.npy` — the brain mask (shape `(n_vox,)`; maps are graded over these voxels).

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **determinable** map, each of shape `(n_vox,)` in voxel order:
- `rCBV.npy` — always.
- `rCBF.npy` — **only when an AIF is available**.
- `rMTT.npy` — **only when an AIF is available**.

Do **not** write a file for a map the exam cannot support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for
the maps you can produce so the rest of the cohort can be graded.
