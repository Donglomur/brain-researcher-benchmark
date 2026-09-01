# VASO cerebral-blood-volume quantification for a heterogeneous cohort

## Task
`/app/data/` holds a cohort of vascular-space-occupancy (VASO) functional exams
(`sub-01` … `sub-08`). Each subject was scanned with a blood-nulled VASO run during a block-design
task; some subjects were additionally scanned with an interleaved not-blood-nulled (BOLD) run.
From these signals, estimate the per-voxel **task-evoked change in cerebral blood volume (CBV)**
and write it out.

The cohort is **heterogeneous**: every subject's sidecar declares how it was acquired (the
acquisition type, which image files exist, the per-frame block-design labels, and the TE/TI/TR),
and you must adapt the analysis per subject — a pipeline that assumes one fixed recipe will not
fit them all. **Compute a map only where the subject's acquisition determines it; where it does
not, omit that map.** There is no reference pipeline provided — implement the estimators yourself
and get the physics, units, and per-subject adaptation right.

Grading is **outcome-based and voxelwise against the true underlying physiology**: each map you
write is compared voxel-by-voxel, inside the grey+white-matter region of interest, to the *true*
task-evoked change that generated the signals. **Any scientifically valid estimator is accepted**
— any robust frame-rejection scheme, any code path — because every correct method recovers the
same physiology within tolerance; you are **not** required to reproduce any particular reference
implementation's output. Subjects and maps are scored independently, so produce every map you can
support and omit the rest.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects: the blood-nulled and
not-nulled **signal models**, the **BOLD correction** (the blood-nulled image divided by the
not-nulled image, which cancels the activation T2\*/BOLD weighting and leaves the tissue-volume
modulation), the exact pinned **definitions** of the graded quantities (`dCBV_taskK` in mL/100mL
and `dBOLD` in percent), the pinned **baseline CBV** `V0`, the averaging **conventions**, the
**units**, and the **tissue legend**. Read it before you start — the graded quantities are fixed
by those definitions.

## Robustness / data-quality contract  (READ THIS)
The signals are realistic, not clean:

- **Grossly corrupted frames.** In a **majority of subjects, a few individual time frames are
  grossly corrupted** (motion / inversion-failure events that scale a whole frame's signal by a
  large factor) and are physically inconsistent with the rest of the run. **You must detect and
  reject such corrupted frames robustly before forming the block means** for `dCBV` and `dBOLD`.
  *Which* subjects and *which* frames are affected is **not disclosed** — you must find them from
  the data. Any scientifically valid robust scheme is acceptable (temporal-outlier rejection on a
  per-frame summary statistic, robust averaging, etc.); a non-robust average over all frames will
  recover the wrong block means on the affected subjects and fail those panels. The corruptions
  are gross (far larger than the few-percent physiological block-to-block modulation), so a wide
  robust margin rejects them without dropping any legitimate frame.
- **BOLD contamination on SS-SI-VASO subjects.** On the SS-SI-VASO subjects the blood-nulled
  signal carries an activation-driven T2\*/BOLD weighting that must be removed with the not-nulled
  image (`Vc = nulled/not-nulled`); using the raw nulled signal biases — and can even sign-flip —
  the CBV change. See the BOLD correction in the protocol.

Modest additive noise is present on every frame and does **not** need special handling beyond the
ordinary block averaging.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `acquisition` (`SS-SI-VASO` or `VASO`), `te_ms`, `ti_ms`, `tr_ms`, `n_vox`,
  `n_frames`, `n_conditions`, a `frame_labels` list (one label per frame; `0` = rest, `1` = task 1,
  `2` = task 2), and the file names below.
- `vaso.npy` — the blood-nulled run, a float32 array of shape `(n_frames, n_vox)`, one row per
  time frame, in the subject's voxel order.
- `bold.npy` — the not-blood-nulled (BOLD) run, same shape; **present only** when the subject's
  sidecar names a `notnulled_file` (the SS-SI-VASO acquisition).
- `tissue.npy` — per-voxel tissue label (shape `(n_vox,)`; see the protocol legend, GM = 1,
  WM = 2).
- `mask.npy` — the brain mask (shape `(n_vox,)`).
- `roi.npy` — the grey+white-matter region of interest (shape `(n_vox,)`; maps are graded over
  these voxels).

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **computable** map, each of shape `(n_vox,)` in the subject's voxel
order:
- `dCBV_task1.npy` — the CBV change for task condition 1 (mL/100mL).
- `dCBV_task2.npy` — the CBV change for task condition 2 (mL/100mL) — **only** for subjects whose
  block design contains a second condition.
- `dBOLD.npy` — the not-nulled BOLD percent-signal-change for task 1 (percent) — **only** where a
  not-nulled image is present.

Do **not** write a file for a map the subject's acquisition cannot support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for the
maps you can produce so the rest of the cohort can be graded.
