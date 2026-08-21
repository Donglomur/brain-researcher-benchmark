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

Grading is **outcome-based and voxelwise**: the field you write is recomputed from the images by a
held-out reference and compared voxel-by-voxel inside the brain mask.

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

## Required output (`/app/output/sub-XX/`)
Write `B1rel.npy` — a float32 array of shape `(n_vox,)` in the subject's voxel order: the relative
transmit field (fraction of nominal, 1.0 = nominal) over the brain mask.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write a valid `B1rel.npy` for the
subjects you can produce so the rest of the cohort can be graded.
