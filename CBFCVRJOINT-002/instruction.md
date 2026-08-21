# Joint CBF + cerebrovascular-reactivity mapping from a dynamic ASL / CO2 challenge

## Task
`/app/data/` holds a cohort of dynamic pseudo-continuous ASL (pCASL) exams (`sub-01` … `sub-08`),
each acquired as a time series of interleaved **control/label** image pairs at a single
post-labeling delay **during a hypercapnia (CO2) challenge**. From these signals estimate, per
voxel, the **baseline cerebral blood flow (CBF)**, the **hemodynamic lag** of the CO2 response,
and the **cerebrovascular reactivity (CVR)**, and write them out.

The cohort is **heterogeneous**: every subject's sidecar declares its kinetic constants, how to
obtain the M0 reference, and whether an external end-tidal-CO2 (PetCO2) trace was recorded — and
you must adapt the analysis per subject, because a pipeline that assumes one fixed recipe will not
fit them all. **Compute a map only where the subject's acquisition determines it; where it does
not, omit that map.** There is no reference pipeline provided — implement the estimators yourself
and get the physics, units, timing, and per-subject adaptation right.

Grading is **outcome-based and voxelwise**: each map you write is recomputed from the signals by a
held-out reference and compared voxel-by-voxel over the graded brain voxels. Partial cohorts and
partial map sets are scored proportionally, so produce every map you can support and omit the rest.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the conventions common to all subjects, all of which you should read before
starting:
- the single-compartment (blood-T1) pCASL **signal model** and the **white-paper single-PLD CBF
  inversion** (mL/100g/min) of the control−label difference `dM`, with its constants;
- the two **M0 calibration** paths (a dedicated background-suppressed M0 scan, versus the
  baseline-averaged control image divided by its saturation-recovery factor);
- the **baseline CBF** definition (invert the mean `dM` over the sidecar's normocapnia
  `baseline_pairs`);
- the **regressor convention**: an external PetCO2 trace resampled onto the pair-time grid and
  converted to mmHg, versus the **data-driven** gray-matter-mean CBF signal when no trace exists;
- the exact **lag definition** (the integer-frame shift `k·tr_pair`, of either sign, over
  `lag_window_s`, that maximizes the detrended Pearson correlation of the per-pair CBF series with
  the shifted regressor);
- the exact **reactivity definitions**: `rCVR`, the detrended reactivity slope at the optimal lag
  divided by its gray-matter median (dimensionless, always determinable); and `aCVR`, that slope in
  mL/100g/min per mmHg, determinable only for an external-PetCO2 (mmHg) regressor;
- the **unit** of each quantity and the **tissue legend**.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `n_vox`, `n_pairs`, `tr_pair_s`, `label_duration_s`, `post_label_delay_s`,
  `labeling_efficiency`, `T1_blood_s`, `field_T`, `background_suppression`, `m0_source`
  (`"m0_scan"` or `"control_pd"`), `regressor_source` (`"external_petco2"` or `"data_driven"`),
  `baseline_pairs`, and the file names below. `m0_scan` subjects also give `m0_file`; `control_pd`
  subjects also give `tr_ctrl_s` and `t1_tissue_s`. External subjects also give `petco2_file`,
  `petco2_units` (`"mmHg"` or `"kPa"`), `petco2_dt_s`, and `petco2_start_s`.
- `control.npy`, `label.npy` — float32 arrays of shape `(n_pairs, n_vox)`: the per-pair control and
  label images in the subject's voxel order (row `t` is pair `t`, at time `t·tr_pair_s`).
- `m0.npy` — present only for `m0_source = "m0_scan"`: the fully-relaxed M0 reference `(n_vox,)`.
- `petco2.npy` — external subjects only: the end-tidal CO2 trace `(n_samples,)`; sample `i` is at
  time `petco2_start_s + i·petco2_dt_s` seconds.
- `tissue.npy` — per-voxel tissue label `(n_vox,)` (see the protocol legend; gray matter = 1,
  white matter = 2).
- `mask.npy` — the brain mask `(n_vox,)`; maps are graded over the brain voxels.

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **computable** map, each of shape `(n_vox,)` in the subject's voxel
order:
- `CBF.npy` — baseline cerebral blood flow (mL/100g/min).
- `lag.npy` — hemodynamic lag (seconds), the integer-frame correlation-peak shift (either sign).
- `rCVR.npy` — relative cerebrovascular reactivity (dimensionless, gray-matter-normalized).
- `aCVR.npy` — absolute cerebrovascular reactivity (mL/100g/min per mmHg) — **only where an
  external PetCO2 trace determines it**.

Do **not** write a file for a map the subject's acquisition cannot support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for the
maps you can produce so the rest of the cohort can be graded.
