# PETREF-001 — source-bound midpoint SRTM method control

## Scientific role

This is a **small computational method/easy control** on public, acquired
[11C]DASB PET derivatives. It applies the three-parameter simplified reference
tissue model (SRTM) of [Lammertsma and Hume (1996)](https://doi.org/10.1006/nimg.1996.0066)
to four regional TACs from the Cimbi example dataset.

The [PET-BIDS paper](https://doi.org/10.1038/s41597-022-01164-1) is a data-standard
and resource paper, not a published four-scan putamen BP target. The original SRTM
paper studied other tracer/cohort combinations. This task is therefore not a
numerical reproduction of a named physiological finding from either paper.
Its target is reproducible kinetic computation under an explicit approximation,
with source-bound predictions and honest within-person repeat summaries.

## Source, timing and provenance

Use OpenNeuro ds001420 snapshot 1.2.0, the four deposited
`derivatives/PETPrep1/*/*/pet/*_pvc-nopvc_desc-mc_tacs.tsv` files, their raw PET
sidecars, motion-correction sidecars and retained provenance documents. Original
bytes are checked against the published Git tree and independently hashed with
SHA256. The fixed manifest and build-time staging make runtime analysis offline.

The current snapshot's root `dataset_description.json` says **CC0**; the earlier
proposal's 'not for public distribution (yet)' statement was stale. CHANGES
records the license update and addition of derivatives in 1.2.0.

The data are two people measured twice, not four independent participants.
Sub-01 baseline has 32 frames over 53.6 minutes; the other three scans have
36 frames over 90 minutes. All TAC frame bounds agree with the original PET
sidecars. Those sidecars specify seconds, Bq/mL, scan/injection start zero, and
decay correction to time zero. Initial measured zeros are retained.

The motion-correction sidecars identify PETPrep HMC v0.0.1 and the raw PET
sources. Snapshot 1.2.0 lacks a derivative dataset-description file and separate
TAC sidecars. The original extraction logs provide additional lineage, but this
repair does not rerun PET motion correction, segmentation or TAC extraction from
images. Agreement with a deposited derivative is not independent validation of
that preprocessing.

## Public estimator

- Target: arithmetic mean of the left/right no-PVC putamen columns.
- Reference: arithmetic mean of the left/right no-PVC cerebellar cortex columns.
  These are equal-hemisphere means, not voxel-volume-weighted pooled ROIs.
- Use frame midpoints in minutes. Reconstruct the reference TAC linearly through
  the explicit origin assumption `(0,0)` and the measured midpoint values.
- With `theta=k2/(1+BP_ND)`, evaluate
  `z'=C_R-theta*z, z(0)=0` and
  `C_T=R1*C_R+(k2-R1*theta)*z` by stable analytic interval integration.
- Fit unweighted midpoint residuals, with both curves divided by the same
  per-scan maximum reference value for numerical conditioning. Publish numerical
  bounds, three initializations and deterministic optimizer settings.
- Retain optimizer success, boundary and residual diagnostics. Failed source
  preconditions or absence of a valid fit must not become a guessed result.

This is deliberately a **midpoint-TAC approximation**, not exact frame-averaged
forward modeling or a claim that noisy reference TACs equal physiological input
functions. Numerically integrating the declared interpolant exactly does not
remove the interpolation, measurement, reference-region or compartment-model
assumptions.

No reference-region choice is hidden. The generic `reference` column is not used:
the original extraction log selects cortical labels 8 and 47, contradicting the
old whole-cerebellum/white-matter/vermis narrative. The convenience column's
processing lineage must not be inferred from its name.

## Outputs and verifier

Every scan retains its original frame schedule, four hemisphere-level input
curves, derived target/reference means, fitted parameters, predicted TAC and
signed residuals. The verifier checks complete source membership, then
parameter-to-prediction and prediction-to-residual/QC arithmetic. It does not
accept a literature-like mean as evidence that fitting was performed.

Report the two subject-specific baseline/rescan differences and
`100*abs(baseline-rescan)/mean(baseline,rescan)` when that pair mean is positive;
otherwise report an undefined percentage explicitly. The group percentage is
defined only when both pairs are defined. Two people and unequal acquisition
durations do not establish population reliability.

Remove the old physiological BP band, R1 dispersion floor, test-retest range,
3-of-4 partial match, SUVR-distance and prose-keyword gates. A legitimate constant
result is not automatically wrong. Invalid constant/aliased or invented results
must fail source and model reconstruction, not an artificial variance rule.

## Claims removed

The earlier tables and statements about BP near 1.92, approximately 2% estimator
agreement, approximately 3% whole-cerebellum differences and approximately 33%
PVC effects are not carried forward as verified results. The old oracle did not
compute all those comparisons; its grid refinement did not establish the
current source-bound kinetic target. This task no longer claims to accept
unspecified Logan/MRTM/reference/weighting variants against one hidden SRTM bank.

## Evidence gates

Generate the reference only from the verified original TACs under the public
model. Check the forward model using an independently implemented integration
method and inspect alternate-fit stability; disclose shared components and any
weak identifiability. Exercise genuine-output positives and coherent
source/parameter/prediction/summary forgeries. Run the clean-commit offline Harbor
oracle, retain raw logs/results, and distinguish this from any later agent trial.

Executed results are recorded in `REPAIR_STATUS.md` and the external receipt.
No scientific result or model-difficulty conclusion follows from unit fixtures,
a local commit or this proposed contract. No push, PR comment or merge is part
of the local repair.
