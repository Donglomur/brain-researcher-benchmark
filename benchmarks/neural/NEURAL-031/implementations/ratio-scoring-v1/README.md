# Recovered ratio endpoint and paired scorer

This package restores an executable endpoint and evaluator for the declared NEURAL-031 finite panel. It recovers the scientific logic from retained preparation and producer-neutral scoring source. It does not recover the authentic public input packet, stage targets, fit a model, execute a participant, or qualify any neural-understanding access mode.

`endpoint.py` provides the source-derived eligibility rule and a standard-library scorer. `score.py` validates the complete paired submission before reading an externally held target file. No historical task, numerical result, runtime declaration or private target has been changed. [SOURCES.json](SOURCES.json) pins the sources inspected; [INTEGRATION_PROPOSAL.md](INTEGRATION_PROPOSAL.md) records corrections for the definition owner.

## Scientific endpoint recovered

The target is **follow-up volume / baseline volume**, dimensionless, with no change equal to 1. This is the `norm=False` branch of author `calculate_volume_change`, and the exact target selected by the recovered NEURAL-031 protocol. It is neither raw follow-up volume nor a difference, percentage change or normalized difference. The author README calls follow-up the next-day session; exact elapsed hours remain unverified.

The prediction protocol uses 27 Early control members from 20 mice, 1,143 original rows, 774 baseline-defined requests, and 731 observed targets. These counts are retained declarations, not new data measurements. All compartments of a mouse remain in one fold, including mice represented in both apical and basal compartments.

`eligibility()` preserves the recovered rules:

- Request membership uses baseline flags and volume only. The spine must be present, nonshaft, and have finite strictly positive baseline volume. Baseline `New Spine` is included.
- A requested row is scored only if follow-up flags contain none of `Eliminated Spine`, `Absent`, `New Spine`, or `Shaft Spine`, follow-up volume is finite and nonnegative, and the ratio is finite.
- Recorded zero follow-up volume with valid flags gives ratio zero. Missing or eliminated spines are never assigned zero. There is no epsilon denominator or target clipping.
- Every simultaneous exclusion reason is returned. Typed string versus sequence membership retains the original author semantics.

The historical prediction cohort differs from the source paper's retrospective stable-at-both-visits cohort. This scorer evaluates the recovered prediction task; it does not claim exact reproduction of the paper's pooled correlations. Its estimand is conditional on observed, associated follow-up size. Missing targets may be informative.

## Input and scoring contract

The public support and submission schemas are unchanged from the recovered producer-neutral implementation: `neural031_ordinary_public_support_v1`, `neural031_ordinary_prediction_v1`, and `neural031_ordinary_submission_bundle_v1`. Every output binds to the exact input-manifest descriptor and ordered row IDs for one fold and view. All 40 outputs must be supplied. Predictions must be finite, nonnegative numbers; constant predictions are valid controls. Missing predictions, including predictions for unscored requests, invalidate the submission.

The only new serialization is the operator-owned `neural031_ratio_targets_v1` JSON object:

```json
{
  "schema": "neural031_ratio_targets_v1",
  "candidate_id": "NEURAL-031",
  "mice": ["the exact 20 source mouse IDs in endpoint.MICE order"],
  "rows": [
    {"rowid": 0, "mouse": 0, "y": null, "request": 1,
     "observed": 0, "baseline_new": 0, "compartment": 0}
  ]
}
```

The illustration shows a single generated unavailable row, not an executable panel. Actual targets require all 1,143 rows, ordered by original row ID, and exactly the 20 pinned mouse IDs. `mouse` indexes that list. `compartment` is 0 for apical and 1 for basal. Flags are integer 0/1; unavailable targets are JSON `null`, replacing the legacy NPZ NaN representation. An observed target must be a finite nonnegative ratio and a requested row. Exactly 774 requests must match public support and exactly 731 must be observed; every mouse must have at least one observed target. An authentic source preparation must establish these values and identities independently before using this scorer.

The primary score is the mean over 20 mice of baseline MAE minus neural MAE. Each mouse's MAE uses all its observed targets. The output also includes separate absolute MAEs, all mouse differences, positive-difference count, full request/scored/unavailable coverage, compartment and baseline-New strata, no-change ratio-1 MAE, and a training-only mouse-balanced median control. The median gives each of the other 19 mice equal total weight; exact rational cumulative weights implement the lower median at a half-mass tie. Strata do not change the primary denominator. Stable finite means avoid overflow without clipping values.

The scorer does not enforce learner architecture or a fit count. The comparison still requires an external review that baseline and neural arms use matched learning/tuning procedures and training-only transforms. The recovered baseline shares both neural-feature missingness indicators with the neural view; otherwise an apparent gain could come only from measurement availability.

## Operator use

With Python 3.9 or later, no third-party dependency is needed:

```sh
python3 -B score.py --support /operator/public/support.json \
  --submission /operator/committed/submission.json \
  --targets /operator/private/targets.json \
  --targets-sha256 '<frozen target file SHA-256>' \
  --output /operator/results/new-score.json
```

The target hash must come from trusted preparation, not a participant. Output creation is exclusive so an existing result is not overwritten. JSON reads have byte limits and reject duplicate keys and nonstandard NaN/Infinity literals. The CLI finishes validation of all public outputs before opening, hashing or decoding the target file, then checks its frozen hash before decoding. Failed submissions return a nonzero exit and no metric file. The input hashes in a successful result bind its exact byte inputs.

This is an operator utility, not a sandbox. Keep evaluator inputs inaccessible to participant processes. No candidate runs here; isolated fold delivery, program freezing before query access, prevention of cross-fold label leakage, frozen preparation, and matched-method review remain required. Direct observation, typed viewer, tool-assisted and frozen-program qualification remain unchanged by this package. No model, human or agent performance is claimed.

## Verification and remaining work

`test_endpoint.py` contains generated full-size controls with deliberately unequal mouse support, independently calculable MAEs and training medians, exact request/target count checks, malformed/duplicate/mismatched identities, missing predictions on unavailable targets, constant outputs, nonfinite values, and a target-open barrier check. Run it through the coordinator's reviewed two-slot test pool during construction. These controls do not use authentic biological observations or establish scientific qualification.

Still missing: authentic current source preparation and source-member/row association proof; independently verified roster and exclusions; physically isolated matched input delivery; complete participant execution and independently reproduced scoring. The historical declaration's source/runtime evidence does not transfer automatically. No confidence interval treating the 20 overlapping leave-one-mouse-out fits as independent is produced.
