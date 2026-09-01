# Vessel-size imaging (VSI) from a heterogeneous dynamic-susceptibility-contrast cohort

## Task
`/app/data/` holds a cohort of dynamic-susceptibility-contrast (DSC) perfusion exams
(`sub-01` … `sub-08`). Each subject was scanned with a **gradient-echo (GE)** dynamic series
during a contrast bolus; some subjects additionally have a **spin-echo (SE)** dynamic series.
From these signals estimate the per-voxel **perfusion / vessel maps** and write them out.

The cohort is **heterogeneous**: every subject's sidecar declares what it actually acquired
(the echo type(s), echo times, frame timing, field, an arterial input function and an ADC map),
and you must adapt the analysis per subject — **compute a map only where the subject's
acquisition determines it, and omit it otherwise.** There is no reference pipeline provided —
implement the estimators yourself and get the physics, units, and per-subject adaptation right.

Grading is **outcome-based and voxelwise against the true underlying physiology**: each map you
write is compared voxel-by-voxel, inside the brain mask, to the *true* map that generated the
signals. **Any scientifically valid estimator is accepted** — any Boxerman–Weisskoff leakage-
correction linear algebra, any peak/ratio estimator, any integration scheme — because every
correct method recovers the same physical quantities within tolerance; you are **not** required
to reproduce any particular reference implementation's output. Each (subject × map) is scored
independently.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects: the DSC **signal model**
(how `DeltaR2*` / `DeltaR2` relate to the measured signal), the exact definitions of **rCBV**
(the WM-normalised first-pass gradient-echo integral), **vessel_radius** (the vessel-size index,
with its pinned constants and the bolus-peak convention) and **Q** (the vessel-density index),
the **unit** of each quantity, and the **tissue legend**. Read it before you start.

## Robustness / data-quality contract  (READ THIS)
The signals are realistic, not clean:

- **Contrast-agent leakage (BBB breakdown).** In a **majority of subjects, a sub-region has
  blood–brain-barrier leakage**: the gradient-echo `DeltaR2*(t)` curve there is corrupted by a
  slowly-accumulating **T1 extravasation term** that is physically inconsistent with the
  intravascular first-pass response of the surrounding tissue. **You must detect and remove this
  leakage before the rCBV integral** (a Boxerman–Weisskoff two-parameter fit of each voxel's curve
  against a leakage-free reference curve, e.g. the white-matter mean, recovers and subtracts the
  extravasation term; it is a no-op where there is no leakage). Left uncorrected it biases rCBV
  and the bolus-peak vessel maps on the affected voxels. *Which* subjects and *which* voxels leak
  is **not disclosed** — you must find them from the data; any scientifically valid leakage-
  correction scheme is acceptable.
- **Recirculation second pass.** Every bolus has a second (recirculation) pass after the first;
  rCBV integrates the **first pass only** (the window `[n_baseline, first_pass_end)` is given in
  the sidecar). Integrating past it biases the WM-normalised rCBV, because the recirculation
  fraction is tissue-dependent.

Modest additive noise is present on every frame and does **not** need special handling beyond the
ordinary conversion and integration.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `field_T`, `n_vox`, `n_frames`, `n_baseline` (pre-bolus frames),
  `first_pass_end`, `has_spin_echo`, the file names for the ADC map / AIF / tissue / mask, and a
  `contrasts` list; each contrast gives `name` (`GE` or `SE`), `te_ms`, and the `file` holding
  its dynamic signal.
- one `<name>.npy` per contrast — a float32 array of shape `(n_frames, n_vox)`: the magnitude
  DSC signal, one row per time frame, in the subject's voxel order.
- `adc.npy` — the per-voxel apparent diffusion coefficient (shape `(n_vox,)`, µm²/ms).
- `aif.npy` — the arterial input function, the arterial contrast concentration per frame
  (shape `(n_frames,)`, mM).
- `tissue.npy` — per-voxel tissue label (shape `(n_vox,)`; see the protocol legend).
- `mask.npy` — the brain mask (shape `(n_vox,)`; maps are graded over these voxels).

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **computable** map, each of shape `(n_vox,)` in the subject's voxel
order:
- `rCBV.npy` — relative cerebral blood volume (WM-normalised, dimensionless).
- `vessel_radius.npy` — mean vessel radius (µm) — **only where determinable**.
- `Q.npy` — vessel-density index — **only where determinable**.

Do **not** write a file for a map the subject's acquisition cannot support. Where an individual
voxel's value is not determinable, write `NaN` at that voxel.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for
the maps you can produce so the rest of the cohort can be graded.
