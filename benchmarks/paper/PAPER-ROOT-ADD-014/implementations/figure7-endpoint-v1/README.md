# Original Figure 7 endpoint component

This component implements the original figure's broadband-based electrode
selection and paired alpha prediction comparison. It adds the pooled electrode
median that the existing 433-electrode, equal-participant program does not
compute. It preserves that program unchanged. It is a source-grounded software
component, not a qualified benchmark, author reproduction or improvement result.

The source recovery also establishes that **both alpha conditions use signed
gain fits in Figure 7**. The older program's primary positive-gain GS condition
cannot be relabeled as this figure. See [SOURCE.md](SOURCE.md) for the exact
entrypoint, selection expressions, limits and integration proposal.

## Operator API

`compile_selection(rows, thresholds)` requires all 366 original quality-selected
electrodes from all nine participants, in source order. Every row contains:

- `participant`, `electrode_id`, and source-normalised `wangarea`.
- `corrected_broadband_xval_percent`, `raw_broadband_xval_percent`.
- `corrected_broadband_ecc_pixels`, `raw_broadband_ecc_pixels`.

The threshold dictionary has `corrected` and `raw`, each the source-rounded
95th percentile of its original broadband permutation results, in percent.
The selector takes the intersection of both branches' broadband scores strictly
above their thresholds and eccentricities strictly below 50 pixels, then keeps
V1/V2/V3. It requires the reported 31-electrode panel. Alpha scores and gain
signs are absent from the selection interface. A missing permutation file or
nonfinite operand refuses selection; it cannot silently pass through MATLAB's
negated-NaN comparison. Unsummarised labels such as V1d are not collapsed here.
Their source-normalisation step must be completed before this API.

`evaluate_predictions(selection, candidate, expected_selection_sha256=...,
load_reference=...)` accepts a list of exactly 31 identity-keyed prediction rows.
Each has `participant`, `electrode_id` and `predictions`, mapping
`corrected_alpha`, `raw_alpha`, and `broadband` to 75 finite numbers. All candidate
rows are admitted and copied before the reference callback runs. Input order
may vary; the participant/electrode pair defines the join. A candidate cannot
submit a score, choose a subset, or replace a companion control.

For each selected identity, the operator callback supplies `observations` and
`author_predictions`, each with the same three signals and 75-sample support.
The author alpha reference must use the source signed-gain GS fits; broadband
uses the source positive-gain GS companion. The original deterministic halves
are retained: predictions at indices 0–37 come from training on indices 38–74,
and predictions at 38–74 come from training on 0–37. The artifact cannot prove
producer isolation; the execution owner must freeze and enforce that protocol.

The grader reuses the existing locked metric implementation. Primary scores
remove DC separately in the two test folds and then pool their residual energy.
The literal paper equation is reported separately. Each signal reports candidate
and author electrode medians and their difference in percentage points. Median
paired differences are explicitly separate, as they can differ from the primary
difference of medians. Corrected-minus-raw contrasts and participant summaries
are retained. Undefined metrics refuse the complete result; there is no
candidate-dependent omission, score clipping or all-electrode substitution.

## Granular operator report

The report also retains `per_electrode`: exactly 31 rows in frozen selection
order, keyed by `participant` and `electrode_id`. Each row contains both
`source_cv` and `literal_eq6` metrics for all three signals, with
`candidate_percent`, `author_percent`, and `paired_difference_pp`, plus each
method's corrected-minus-raw alpha contrast in percentage points. The existing
summary medians, primary comparison, selection and scoring formulas are unchanged.

This table preserves the source Figure 7 prediction distributions that a median
alone cannot reconstruct. The source violin consumes each selected electrode's
xval value ([author script, lines 890–937](https://github.com/KenYMB/ECoG_alphaPRF/blob/4321eb4374db782d09f3f43362836f234a4e4f9b/scripts/ecog_APRFF_10k1e_checkalpha_bothgaind.m#L890-L937)).
The table supports identity-level audit and downstream figure construction;
plot rendering, gain/geometry outputs and the rest of the original panel remain
unimplemented here. Source and literal metrics remain explicitly separate.

These are operator evaluation outputs. They contain protected reference-derived
scores and must not be exposed as candidate inputs or unrestricted development
feedback. This API does not implement access control or a feedback budget.
The table includes no raw response or prediction arrays and establishes no
source authenticity, native parity, uncertainty interval or scientific win.

## Qualification and use limits

The 366 population and 31 selected identities have **not** been authenticated or
prepared by this component. A complete ordered original roster, both source
permutation thresholds, native source prediction comparison, raw preprocessing
parity and execution provenance remain required. Hashes bind supplied values;
they cannot establish source authenticity or freeze chronology. The callback
and expected selection hash belong to the trusted operator, never a candidate.

The rounded published 43% and 10% anchors remain calibration references. This
component does not infer a minimum improvement, confidence interval, population
replication claim or SOTA result from them. A participant-aware uncertainty
protocol must retain the source electrode median as the point estimand.

`test_endpoint.py` exercises only generated controls. It requires the existing
NumPy dependency of the reviewed metric module, with no new installation.
`verify_sources.py` checks only an explicit list of cached public source files
against existing inventories and emits [SOURCE_LOCK.json](SOURCE_LOCK.json).
All Python execution must follow the campaign's shared lightweight test pool.

The new API is an integration proposal. The task contract, registry, existing
vendor locks and central routes are unchanged.
