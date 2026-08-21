# QUASAR multi-TI ASL: model-free / model-based perfusion quantification

## Task
`/app/data/` holds a cohort of multi-inversion-time (multi-TI) pulsed arterial-spin-labeling
(ASL) exams (`sub-01` … `sub-08`). Each subject was scanned with many label/control repetitions
at a schedule of inversion times; some subjects were additionally scanned **with flow-crushing
gradients** that dephase the fast-flowing intravascular spins. From these signals, estimate the
per-voxel perfusion parameters and write them out.

The cohort is **heterogeneous**: each subject's sidecar declares its acquisition (whether a
flow-crushed series accompanies the non-crushed one, the TI schedule, and how to calibrate the
equilibrium magnetization), and you must adapt the analysis per subject — a pipeline that assumes
one fixed recipe will not fit them all. **Compute a map only where the subject's acquisition
determines it; where it does not, omit that map.** There is no reference quantifier provided —
implement the estimators yourself and get the physics, units, and per-subject adaptation right.

Grading is **outcome-based and voxelwise**: each map you write is recomputed from the signals by
a held-out reference and compared voxel-by-voxel inside the grey- and white-matter mask. Subjects
and maps are scored independently, so produce every map you can support and omit the rest.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects: the single-compartment
**signal model** (a dispersed-boxcar arterial delivery convolved with the tissue residue), the
**crusher convention** (non-crushed = tissue + arterial; flow-crushed = tissue only), the exact
definitions of **CBF**, **ATT** and **aBV**, the pinned physical **constants** (`alpha`,
`lambda`, `T1b`, `T1t`, `tau`, `sigma_disp`), the **unit** of each quantity, and the **tissue
legend**. Read it before you start.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `field_T`, `n_vox`, `ti_s` (the inversion times, s), `n_reps`, `acquisition`
  (`"crushed+noncrushed"` or `"noncrushed"`), the signal file names, and `m0_file`.
- `noncrushed.npy` — a float32 array of shape `(n_TI, n_reps, n_vox)`: the ASL difference
  (control − label) at each inversion time, one plane per repetition, in the subject's voxel order.
- `crushed.npy` — present **only** when `acquisition = "crushed+noncrushed"`: the same, acquired
  with flow-crushing gradients.
- `m0.npy` — per-voxel equilibrium tissue magnetization (shape `(n_vox,)`, a.u.).
- `tissue.npy` — per-voxel tissue label (shape `(n_vox,)`; see the protocol legend, GM = 1, WM = 2).
- `mask.npy` — the grey/white-matter mask (shape `(n_vox,)`; maps are graded over these voxels).

## Graded quantities (defined precisely in `protocol.json`)
- **CBF** — cerebral blood flow, **mL/100g/min**. With a crusher pair, from the model-free solve
  (the tissue curve regressed onto the convolution of the *measured* arterial input with the
  pinned residue); otherwise from the model-based kinetic fit against the assumed delivery.
- **ATT** — arterial transit time, **s**. With a crusher pair, the first moment of the
  T1-corrected arterial curve minus `tau/2`; otherwise the fitted transit time.
- **aBV** — arterial blood volume fraction, **dimensionless**. The T1-corrected area of the
  measured arterial curve, normalised by `2·alpha·(M0/lambda)·tau`. **Determinable only where a
  crusher pair exists.**

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **computable** map, each of shape `(n_vox,)` in the subject's voxel
order:
- `CBF.npy` — always.
- `ATT.npy` — always.
- `aBV.npy` — **only** for a subject with a crusher pair.

Do **not** write `aBV.npy` for a subject whose acquisition is non-crushed only.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for the
maps you can produce so the rest of the cohort can be graded.
