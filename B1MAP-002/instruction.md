# Relative transmit-field (B1+) mapping of a heterogeneous cohort

## Task
`/app/data/` holds a cohort of B1-transmit-mapping exams (`sub-01` … `sub-08`). Each subject was
scanned with **one** B1-mapping sequence and its accompanying images. From these images, estimate
the per-voxel **relative transmit field** — the actual flip angle delivered as a fraction of the
nominal flip — and write it out.

The cohort is **heterogeneous**: every subject's sidecar declares which images it acquired and with
what parameters, and different subjects were mapped with **different sequences**, so you must choose
the estimator the acquisition supports — a pipeline that assumes one fixed sequence will not fit
them all. There is no reference solver provided — implement the estimators yourself and get the
physics, the units, and the per-subject adaptation right.

Grading is **outcome-based and voxelwise against the true underlying physiology**. The field you
write is compared voxel-by-voxel, inside the brain mask, to the *true* relative transmit field that
generated the images. **Any scientifically valid estimator is accepted** — double-angle,
actual-flip-angle, or Bloch-Siegert, with whatever SNR threshold, noise handling, or clip
convention you prefer — because every correct method converges to the same physical field within
tolerance. You are **not** required to reproduce any particular reference implementation's output.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects: the exact definition of the
**graded quantity** (`B1rel` = actual/nominal flip, a receive-invariant physical field), and the
estimator for each B1-mapping sequence — the **double-angle** method, **actual-flip-angle imaging
(AFI)**, and the **Bloch-Siegert** phase-shift method — together with the **units** and the
**tissue legend**. Read it before you start.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `field_T`, `n_vox`, `b1_method`, `flip_nom_deg` (nominal flip), `noise_sigma`,
  and an `images` list; each entry gives a `role`, a `kind` (`mag` or `phase`), the `file` holding
  it, and any parameters it needs (`tr_ms`; AFI adds `tr1_ms`/`tr2_ms`; Bloch-Siegert adds
  `kbs_rad`). File names for `tissue_file` and `mask_file` are given too.
- one `.npy` per image — a float32 array of shape `(n_vox,)` in the subject's voxel order (a
  magnitude image, or a phase image in radians, as declared by its `kind`).
- `tissue.npy` — per-voxel tissue label (shape `(n_vox,)`; see the protocol legend, white
  matter = 2).
- `mask.npy` — the brain mask (shape `(n_vox,)`; the field is graded over these voxels).

## Robustness / data-quality contract  (READ THIS)
The images are realistic, not clean:

- **Signal-void (dropout) regions.** A **subset of subjects** carry a region where the
  contributing magnitude collapses into the **noise floor** (a receive/signal dropout). There the
  magnitude ratio or phase difference the estimator uses carries **no transmit information**, and
  a naive estimator returns a *finite but spurious* relative-transmit value. **You must detect
  such signal-void voxels** (e.g. by their weakest contributing magnitude falling below a small
  multiple of the per-subject `noise_sigma`) **and EXCLUDE them** — write them non-finite (NaN)
  or ~0, not a quantified transmit value. *Which* subjects and *which* voxels are affected is
  **not disclosed** — you must find them from the data. Any scientifically valid reliability
  criterion is accepted.

Modest Rician noise is present on every image and does **not** need special handling beyond an
ordinary estimate in the adequate-signal voxels.

## Required output (`/app/output/sub-XX/`)
Write `B1rel.npy` — a float32 array of shape `(n_vox,)` in the subject's voxel order: the relative
transmit field (fraction of nominal, 1.0 = nominal) over the brain mask.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write a valid `B1rel.npy` for the
subjects you can produce so the rest of the cohort can be graded.
