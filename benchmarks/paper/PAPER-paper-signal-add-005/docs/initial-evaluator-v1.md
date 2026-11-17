# Initial beta-amplitude evaluator

This package implements the downstream beta suppression/rebound endpoint for **PAPER-paper-signal-add-005** from already extracted, trial-resolved, 13–30 Hz source-peak Hilbert amplitudes. It computes participant amplitudes, separate-finger age associations, trial-count sensitivity, nuisance-adjusted associations, participant uncertainty and local event-shift diagnostics. It is a complete executable analysis at this declared boundary. It is **not** a raw-MEG pipeline, an empirical reproduction, a qualified grader or a trained-model benchmark. Scientific qualification remains unknown.

## Frozen scientific boundary

The unchanged task contract is 22,792 bytes, SHA-256 `63db4f561502a929cbff41fbdf04a6fdb7fa6b9ccf8972803304bf3c247d36d6`. Author code is pinned at `0eb3a56af3d0e3a44b0f65c364e999f69cd4563f` in [RierRhodes_2024_Neurodevelopmental_OPMMEG](https://github.com/LukasRier/RierRhodes_2024_Neurodevelopmental_OPMMEG). [The paper](https://elifesciences.org/articles/94561) and [correction](https://elifesciences.org/articles/103993) retain distinct identities. The correction concerns duplicate Figure 4A connectivity panels, not the beta endpoint.

Inputs are **amplitude**, not squared power or dB. Each participant supplies separate index/D2 and little-finger/D5 trial arrays at their own condition's source peak. Native filenames use D1/D4 labels. The native upstream path filters cleaned sensor data at 13–30 Hz with a fourth-order forward/backward Butterworth filter, estimates condition-specific spatial filters and selects minimum pseudo-T source peaks. The evaluator does not certify those operations. It requires recorded preprocessing, artifact, source-selection, envelope-extraction and metadata provenance.

At 1,200 Hz each trial has 4,200 samples (3.5 seconds). Windows translate the author's **inclusive MATLAB sample indices**, not the plotting time grid:

| Endpoint | Seconds | MATLAB samples | Python slice |
|---|---|---|---|
| Active | 0.3–0.8 | 360:960 | 359:960 |
| Rebound | 1–1.5 | 1200:1800 | 1199:1800 |
| Rest | 2.5–3 | 3000:3600 | 2999:3600 |

For trial j let B_j, S_j and P_j be rest, active and rebound mean amplitudes. The primary code profile computes mean_j((S_j−B_j)/B_j), mean_j((P_j−B_j)/B_j), and modulation **mean_j((P_j−S_j)/B_j)**. Every trial baseline must be positive. This follows `index_pinky_Tstat_func.m:get_envelope`, which normalizes each trial before averaging.

There is a material paper/code discrepancy: the paper methods describe averaging amplitudes before normalization, giving (mean P−mean S)/mean B. The package reports this separately under `paper_equation_sensitivity`. The broadband TFS helper also uses the latter normalization; it is not the primary beta branch. Heterogeneous trial baselines demonstrably distinguish the two. Authentic reference reconciliation remains held.

The author's pinky result script has vector-valued colon endpoints where index uses scalar start/end endpoints. This implementation explicitly repairs pinky to the same scalar windows. It is a **declared prospective repair**, not a claim that defective source code executes identically.

## Population and analyses

The ledger must contain exactly all 53 original IDs: children `sub-001`–`sub-027`, adults `sub-101`–`sub-126`. Exactly 51 have input arrays; `sub-120` and `sub-123` remain explicit fixed source exclusions. The source plot omits those IDs; the paper describes two adult exclusions for HMM data quality. Their individual reason-to-ID mapping and native cohort lineage still require reconciliation. No participant or invalid trial is silently dropped.

The source-aligned primary association is pooled children/adults, separately for each finger: intercept-plus-age OLS, Pearson r and two-sided p, and R². Within-child and within-adult fits are additional descriptive results. Active, rebound and rebound-minus-active endpoints are all reported; fingers are never pooled. No causal age inference is made. Per-finger group contrasts also report adult-minus-child means and Mann–Whitney U. The explicitly chosen SciPy asymptotic, tie-corrected, continuity-corrected p is a prospective numerical policy, not asserted MATLAB `ranksum` parity. Multiple comparisons are reported without declaring significance or a pass threshold.

The following are prospective robustness policies required by the contract, not reconstructed historical analyses:

- All-retained adjusted OLS includes age, retained trial count for that finger, head size in cm and motion in mm. Provenance must freeze the measurement definitions before observing effects. HC3 participant-level standard errors and t-based 95% intervals are explicit approximations. Rank deficiency and inadequate residual degrees of freedom yield a named `held` result.
- Matched analysis draws the same predeclared trial count without replacement for both fingers and every included participant. SHA-256-derived participant/condition RNG streams make selection independent of amplitudes and participant input ordering. It records selected zero-based row indices. Age/head-size/motion adjustment omits the fixed count to avoid a rank-deficient intercept duplicate.
- Pooled age slope and R² percentile intervals resample participants within child/adult cohorts, keeping all outcomes and both fingers paired. The manifest explicitly sets replication count and seed; no scientific precision is claimed from low-replication engineering controls.
- Each matched trial envelope is circularly shifted by an independent uniform nonzero sample shift. This preserves **cyclic autocorrelation within that supplied epoch**, not continuous-recording boundaries or raw event structure. The plus-one absolute surrogate exceedance fraction is an uncalibrated diagnostic and explicitly not a randomization p-value. It cannot establish the contract's authentic continuous event-shift control.
- Prospective extension folds sort participants by age within cohort and allocate round-robin to five folds; every condition and window follows its participant. This freezes a split utility only. No predictive model or train/test performance is established.

## Run

No dependencies are installed by the package. It uses Python 3.11+, NumPy and SciPy already present in the execution environment. Verified runtime here: `/opt/homebrew/bin/python3.11`, NumPy 2.4.6, SciPy 1.17.1. A different system `python3` lacked SciPy and failed import; this was not a scientific failure.

From repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/bin/python3.11 -m unittest discover -s benchmarks/paper/PAPER-paper-signal-add-005/implementations/initial-evaluator-v1/tests -v
/opt/homebrew/bin/python3.11 benchmarks/paper/PAPER-paper-signal-add-005/implementations/initial-evaluator-v1/beta_evaluator.py /absolute/input/manifest.json /absolute/output/report.json
```

The manifest must have `schema_version: 1`, the exact `task_id` and `source_revision`, `band_hz: [13,30]`, `quantity: "hilbert_amplitude"`, `sampling_frequency_hz: 1200`, nonnegative integer `seed`, positive `event_shift_repeats`, `bootstrap_repeats >= 2`, and `matched_trial_count >= 2`. It also requires nonempty strings for `preprocessing_provenance`, `artifact_policy_provenance`, `source_peak_provenance`, `envelope_extraction_provenance`, and `metadata_provenance`. These are provenance declarations, not independent attestations.

Each included `participants` row requires:

```json
{
  "participant_id": "sub-001", "group": "children", "included": true,
  "age_years": 7.5, "head_size_cm": 51.2, "motion_mm": 1.8,
  "retained_index_trials": 60, "retained_pinky_trials": 58,
  "envelopes_npz": "sub-001.npz", "envelopes_sha256": "<actual file SHA-256>"
}
```

Numbers in this example are schematic, not subject observations. Head-size and motion scalar definitions must be frozen in `metadata_provenance` and shared across participants. The two excluded rows require their ID, `group: "adults"`, `included: false`; they have no array. NPZ files contain exactly `index` and `pinky`, each a finite nonnegative array shaped **retained trials × 4,200 samples**, with at least two trials. Original retained order must be preserved and traceable to the artifact mask; matching indices refer to that order. File paths resolve relative to the manifest. Pickled arrays are disabled. Every file hash is checked before analysis; the output pins all 51 files and the manifest. The Python `evaluate(manifest, arrays)` API uses the same contract but does not provide CLI file-hash verification.

## Requirements and remaining holds

| Contract requirement | Delivered here | Remaining evidence |
|---|---|---|
| Fixed band/windows/metric | Executable 13–30 Hz amplitude endpoints and exact sample translation | Native filter/Hilbert/spatial equivalence; paper/code discrepancy |
| Full cohort and subject unit | Complete 53 dispositions, fixed 51 analysis IDs | Authentic payload and exclusion-to-ID reconciliation |
| Age effect and interval | OLS/Pearson R², HC3 and paired participant bootstrap | Empirical estimates and reference tolerances |
| Trial/head/motion robustness | All-retained and globally matched endpoints; explicit covariate models | Authentic covariates and native matched upstream recomputation |
| Event-shift surrogate | Local epoch-envelope diagnostic | Continuous raw event surrogate and exchangeability validation |
| Age-stratified held-out extension | Participant fold assignment | Candidate execution and predictive evaluation |
| Artifact/ICA/spatial/spectral reproduction | Provenance required; no substituting a band sensitivity | Native MATLAB/FieldTrip/beamformer qualification and masks |
| Rights/reference/fair access | Source identities and holds preserved | Protected verifier, access budgets, rights/exposure qualification |

Data remain the unchanged Zenodo 11126593 version 1.0.0 Adults.zip/Children.zip identities in `task.json` (saved CC BY 4.0 terms); author code has saved MIT terms. No archives were acquired and no third-party source is vendored. Full-text/component/stimulus rights, exposure, protected reference, submission isolation and numeric acceptance thresholds are not established. The missing `index_pinky_4mm_evoked_func` branch is excluded explicitly; it neither licenses a substitute primary band nor prevents this downstream beta implementation.

Tests use generated positive envelopes, known algebraic endpoints and a schematic full cohort. They establish engineering behavior, not baseline competence, neuroscience findings, scientific qualification or completion of the full native task. See package `provenance.json` for source locations and the declared policies.
