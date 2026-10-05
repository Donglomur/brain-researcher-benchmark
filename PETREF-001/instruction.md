# Midpoint SRTM fitting on public DASB TACs (PETREF-001)

## Scientific target

Fit the simplified reference tissue model (SRTM) to four acquired [11C]DASB PET
time-activity curves (TACs), then describe the two within-person repeat pairs.
This is a **computational method control**, not a reproduction of a published
putamen BP value or a population-reliability finding.

Model: Lammertsma and Hume (1996), https://doi.org/10.1006/nimg.1996.0066.
Data resource: PET-BIDS/Cimbi example, https://doi.org/10.1038/s41597-022-01164-1.
The original SRTM paper used other tracer/cohort combinations; the PET-BIDS paper
describes a data standard, not the four fitted numbers requested here.

## Offline data

The original OpenNeuro ds001420 snapshot 1.2.0 source bundle is baked into
`/app/data/petref`. Its `source_manifest.json` records exact file paths, original
URLs, SHA256 hashes and published Git/Git-annex identity checks. The snapshot's
root metadata declares CC0. No download is needed during analysis.

Use the four `pvc-nopvc_desc-mc_tacs.tsv` files for sub-01/sub-02 and
ses-baseline/ses-rescan. Sub-01 baseline has 32 frames over 53.6 minutes; the
other scans have 36 frames over 90 minutes. Keep all 140 frames, including
initial measured zeros. The input units are Bq/mL, inherited from the original
PET sidecars and no-rescale extraction logs; TACs lack separate Units sidecars.

Validate TAC bounds against each raw PET sidecar's `FrameTimesStart` and
`FrameDuration` in seconds. All four have `ScanStart=InjectionStart=0`, are
decay-corrected, and have correction time zero. Reject missing, nonfinite,
inconsistent or reordered source data. The four required regional columns are
nonnegative in this frozen input; preserve that domain and all measured zeros.
This is not a general assertion that PET reconstructions can never be negative.
Do not repair failed preconditions with invented values.

Motion correction and regional extraction were already performed upstream; you
are not asked to rerun them. The retained logs provide lineage, not proof that
the preprocessing is scientifically error-free.

## Public analysis contract

The answer-free `/app/method_contract.json` gives the complete machine-readable
recipe and numerical tolerances. Implement this recipe or an equivalent
numerical implementation of the same estimator.

- Target TAC: arithmetic mean of `left_putamen` and `right_putamen`.
- Reference TAC: arithmetic mean of `left_cerebellum_cortex` and
  `right_cerebellum_cortex`. These are equal-hemisphere means, not
  volume-weighted pooled masks. Do not use the convenience `reference` column:
  its AGTM processing lineage differs; it is not a whole-cerebellum label.
- Frame time: `(frame_start + frame_end)/120` minutes.
- Reconstruct the reference linearly through `(0,0)` and all measured
  midpoint values. The zero origin is an explicit approximation, not an
  observed within-frame curve.
- For parameters `R1,k2,BP_ND`, let `theta=k2/(1+BP_ND)` and calculate
  `z'(t)=C_R(t)-theta*z(t)`, `z(0)=0`, then
  `C_T(t)=R1*C_R(t)+(k2-R1*theta)*z(t)`.
  Evaluate at the measured midpoints. Analytic interval propagation or an
  equivalently converged integrator is acceptable.
- Fit unweighted squared midpoint residuals, dividing both target and reference
  by the same per-scan maximum reference value for numerical conditioning.
  Report predictions and residuals in original activity units.
- Numerical bounds, in parameter order `R1,k2,BP_ND`, are
  `[0.01,0.0001,-0.5]` to `[3,5,15]`; `k2` is in min^-1.
  These bounds are not physiological acceptance bands.
- Prespecified starts are `[1,0.05,0.5]`, `[1,0.2,2]`, `[1,0.8,5]`.
  The reference implementation uses SciPy TRF, three-point numerical Jacobian,
  `x_scale=1`, linear loss, `ftol=xtol=gtol=1e-10`, `max_nfev=5000`.
  Select the successful finite in-bounds candidate with smallest squared error;
  break an exact objective tie by start index. Failed fits are not estimates.
- Report proximity to each bound using absolute threshold
  `1e-7*max(1,upper-lower)`, with zero relative tolerance.
  Do not conceal boundary estimates or drop them to improve repeat agreement.
- Derive `k2prime=k2/R1`. For each participant calculate the absolute baseline/
  rescan BP difference and `100*abs(baseline-rescan)/pair_mean` when the pair mean
  is positive; otherwise the percentage is undefined. Report their mean
  percentage only if both pairs have defined percentages. Weight all four scans
  equally for mean BP, and both participants equally for mean repeat percentage.

This is a **midpoint-TAC approximation**, not an exact frame-average forward
model. Numerical integration accuracy does not validate its reference-region,
interpolation, compartment or measurement assumptions. Do not impose a required
BP range, between-scan variability or repeat percentage.

## Required outputs

Write to `${OUTPUT_DIR}` (default `/app/output`). Row order and extra descriptive
columns are unrestricted; preserve complete keyed source membership.

1. `bp_estimates.csv`: one row per scan, with
   `subject,session,target,reference_region,model,R1,k2,BP_ND,k2prime,status,selected_start_index,optimizer_status,nfev,at_lower_bound,at_upper_bound,sse,rmse,normalized_rmse,reference_scale`.
   Labels are `putamen_equal_hemisphere`,
   `cerebellar_cortex_equal_hemisphere`, `SRTM-PWL-midpoint`, and `status=ok`.
   Start indices are zero-based. Report a successful optimizer status (SciPy
   1=gradient, 2=objective, 3=step, 4=objective-and-step convergence) and an actual
   evaluation count in 1..5000; exact counts are not reference-answer targets.
   An equivalent solver may map its termination reason to this convention and
   retain its original status/solver name in extra fields. Bound flags
   are three-element JSON boolean arrays in parameter order. Use signed
   residual = prediction minus observation;
   `sse=sum(residual²)`, `rmse=sqrt(sse/n_frames)`, and
   `normalized_rmse=rmse/reference_scale`.
2. `tac_fit.csv`: every frame of all four scans, with
   `subject,session,frame_index,frame_start_s,frame_end_s,mid_time_min,left_putamen,right_putamen,left_cerebellum_cortex,right_cerebellum_cortex,target,reference,predicted_target,residual`.
   Frame indices are zero-based within scan. The four hemisphere columns are
   original source measurements; target/reference are their declared means.
3. `pet_results.json`: `status=ok`, `pipeline_id=srtm-pwl-midpoint-v2`,
   `n_scans=4,n_subjects=2,putamen_BP_ND_mean,n_defined_pairs,test_retest_pct`,
   plus `per_subject`, a two-item list keyed by `subject`, containing
   `baseline_BP_ND,rescan_BP_ND,absolute_difference,pair_mean,test_retest_pct,status`.
   Pair status is `ok` or `undefined_nonpositive_mean`; undefined percentages
   are JSON `null`, not zero or nonstandard `NaN`.
4. `run_metadata.json`: preserve all public-template fields, add `status=ok`
   and `per_scan_observations`, one keyed record per scan with
   `subject,session,n_frames,start_s,end_s,duration_s`.
5. `findings.md`: summarize actual estimates, fit diagnostics and paired
   differences. Note the two-person scope, unequal scan durations, upstream
   derivative dependence and midpoint/model assumptions. No particular wording
   or language is required.

The verifier checks every scan/frame against frozen source data, recomputes the
forward model and residual diagnostics, and reconstructs both participant pairs.
Private oracle arrays are not required participant outputs. Numerical tolerances
are public in the template; counts and identifiers must match exactly. Scoring
is binary: all required checks must pass. There are no hidden physiological,
variability, repeat-quality or prose-keyword gates.

## Failure handling

If source or numerical preconditions fail, exit nonzero, write
`run_metadata.json` with `status=failed_precondition`, the pipeline ID and a
nonempty `reason`, and write a short `findings.md`. Do not fabricate a BP result
or silently replace the dataset/model. Failure is diagnostic, not a passing
solution. No uncomputed Logan/MRTM, whole-reference or PVC result should be
claimed.
