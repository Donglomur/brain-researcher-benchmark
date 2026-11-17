# Reproduction and improvement scope

This is a concise derived description of the accepted construction recipe. It supplies no article excerpt, upstream implementation, authentic data or reference outputs. Exact source identities and canonical provenance are in `SOURCE_MANIFEST.json`.

## Original reproduction

Use the original five source-defined mouse/session pairs, with independent archive/member/subject joins still required. Reproduce the state-specific stationary and locomotion analyses separately. Source roster syntax does not establish that real inputs have been admitted.

The original within-time endpoint covers all 191 sliding 100 ms windows stepped by 10 ms across the source [-0.2, 1.8] s response interval, for every animal and both states. Source full-contrast dot-motion eligibility, six absolute-velocity classes, condition balancing, complete unit/trial census and original exclusions must be authenticated. The original full-session unit-rate mask belongs to reproduction; it cannot be reused for the calibration-only extension.

The original within-time recipe uses diagonal covariance LDA, delta tuning, three outer folds and five repetitions. Preserve the class-shared trial split, training-only zero-variance filtering, fold-level accuracies, all raw held predictions and the stated mean-of-folds/mean-of-repeats aggregation. Inner folds, hyperparameter search, seeds and numerical environment require explicit reference qualification.

The cross-time endpoint covers the complete 20 training by 20 test windows, each 100 ms, for all five animals and both states. The selected full-population source trains on one random half and tests the complement per repetition, repeated five times; it does not automatically evaluate both complementary directions. Regularized full-covariance LDA tunes gamma and delta. The complete matrices remain required even if a summary ratio is undefined.

The Figure 4e diagnostic uses the 100–200 ms training window and 0–1000 ms test windows. `relative_generalization` keeps the paper's unclipped chance-corrected ratio and the analysis source's below-chance-clipped ratio as separate named conventions. It does not choose a qualified reference. Nonpositive chance-corrected denominators are refused.

`compare_reproduction` requires the five-animal/two-state complete 191-element curves and 20-by-20 matrices. It reports numerical errors and an optional owner tolerance only. Matching arrays does not establish that the inputs came from a competent independently rebuilt reference, and it does not calibrate the tolerance.

## Chronological improvement endpoint

This extension evaluates a new robustness question, not the paper's random-split accuracy. For each complete original session, the first floor(N/2) trials are calibration, the next original trial is a guard and all remaining trials are evaluation. Apply eligibility after partitioning; never move the boundary to improve support. The guard must strictly separate complete source [-0.2, 1.8] s response windows. Each state/class needs six calibration and one evaluation trial or the complete five-animal protocol refuses.

Training uses the 100–200 ms neural window; evaluation covers ten fixed 100 ms stimulus-period windows. Windows from one trial remain together. Calibration alone determines unit-rate selection, zero-variance filtering, transformations and fitted parameters. A future trusted adapter must generate independent random opaque IDs, attach genuine neural features and audit all projections. Hex syntax and sorting alone do not prove that IDs lack target/source-order information.

For each held animal, the other four animals freeze the algorithm and tuning policy. The frozen policy may fit parameters from the held animal's labeled calibration, equally for candidates and both references. It cannot inspect held evaluation or receive iterative evaluation feedback. Independent outer attempts, no cross-fold agent memory and a protected owner execution boundary remain unimplemented admission requirements.

The matched references are explicit **pooled-state** adaptations of regularized full-covariance and diagonal LDA with uniform six-class priors. Neither reference nor candidate receives state labels or privileged state-based dispatch. The owner uses state only to stratify scoring. Full LDA tunes gamma/delta; diagonal LDA fixes gamma=1 and tunes delta under predeclared stratified five-fold calibration splits. The split manifest, search policy and budget must be frozen before exposure.

All three systems must provide exactly one valid integer class prediction for every identical trial/window case. Scoring averages six class recalls equally within each animal/state/window, then equally across two states and ten windows, then equally across five animals. The primary paired delta is against full LDA; diagonal LDA is a required companion. Report all five animal differences and their descriptive SEM; correlated trials are not additional independent animals.

Condition A receives the paper plus the same admitted neutral data, calibration and schema documentation. Condition B receives the identical inputs/resources plus historically qualified official code. Both exclude grading targets and reference outputs. Conditions are not separate task counts.

## Gates that remain open

- Authentic compressed archive/member identities, animal/session joins, complete trial/unit support and MAT field structure.
- Physical velocity values/class order, wheel sampling/support/units, neural/stimulus clocks and eligible source response intervals.
- Paper strict >75% versus code >=75% state boundary, full-population implicit `nTrials`, and random-half versus complementary two-fold conventions.
- Inner-fold/default behavior, Bayesian acquisition-function discrepancy, search/RNG budgets and full licensed MATLAB/toolbox environment.
- Clipped/unclipped relative metric adjudication, complete competent numerical reference and calibrated tolerances.
- Data/code/third-party rights, independently authenticated neutral adapter, trusted artifact store and isolated five-attempt execution/resource custody.
- Public-outcome contamination; no current SOTA, unseen-test or scientific qualification claim.

The published data descriptor advertises CC BY 4.0 for the selected data archive and source archive, while customized third-party code and MATLAB/toolbox terms need separate review. This package does not redistribute those original archives or assert that all downstream rights are settled.
