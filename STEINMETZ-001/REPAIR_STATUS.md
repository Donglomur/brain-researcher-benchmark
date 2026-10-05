# Local repair and validation boundary — 2026-10-01

## Implemented

- Exact published Cori NWB bytes, DANDI release/asset/source SHA256 and CC-BY-4.0
  attribution pinned and baked into a network-disabled task image.
- Honest single-session registered-response method-control framing; no upcoming,
  strictly pre-movement, causal choice-coding or hard-model claim.
- Correct source signs: right=-1, left=+1. All 1,085 stored clusters retained,
  including351MUA,5Good,729Unsorted; no silent paper-quality filter.
- Public feature windows, split allocation, training-only scaler, logistic fit,
  baseline ties, aggregation, tolerances and metadata template.
- Genuine full four-recipe source/count/OOF reference replaces five scalar fold
  scores. Verifier binds exact trial identities, choices, folds and decisions,
  then recomputes all20folds and mean/pooled/baseline results.
- Half-open registered-response timing counts, not inferred movement timing;
  no hidden accuracy band, direction, fold-variability or prose-keyword gate.

## Original-data execution

Owned image `brbench-pr148-offline:20261001`, CPU2/memory8GB, network disabled;
no host source-data mount.214source trials ->134selected binary response trials,
69right/65left; all10,017,476stored spikes preserved.

| Recipe | Mean fold accuracy | Pooled trial accuracy |
| --- | ---: | ---: |
| stimulus_blocked | 0.723931624 | 0.723880597 |
| stimulus_random | 0.761538462 | 0.761194030 |
| peri_response_blocked | 0.940740741 | 0.940298507 |
| peri_response_random | 0.954700855 | 0.955223881 |

Training-fold-majority mean accuracy is0.379772080blocked and0.514814815random.
The full-sample majority fraction0.514925373 is merely descriptive. All134
registered responses occur after the stimulus window, which says nothing about
first movement onset. These numbers do not reproduce Figure4c's regional finding.

Independent Python-bisect source counts, explicit fold construction and manual
training-only mean/variance match all536OOF labels and every source count.
Decision differences are zero; maximum probability difference1.12e-16. The
sklearn/L-BFGS optimizer is shared and is not independently validated by this.

Actual globally standardized negative-control fits give7/4/0/0different labels
across the four recipes and changed decision/probability values in every recipe.
The control uses numerically self-consistent public outputs and deliberately
unchanged claimed metadata; the verifier rejects its numerical predictions.
This does not prove that every window/split difference is caused by leakage.

Final native authoring matrix: **120passed**, comprising52parser/arithmetic,
14numerical,27source-staging and27genuine-output cases (4positive/contract checks,
23rejections including the separately executed global-scaling control).

## Final clean-commit gate

The final commit still requires its own offline Harbor oracle, final-image
regressions and content-digest comparison. Do not treat the native receipt as
that result. Authoritative final status is the external
`tracking/pr_repairs_2026-10-01/pr-148/receipt.json` and associated raw
result/config/lock/oracle/verifier artifacts in the umbrella workspace.

All source/native/independent/negative-control execution records are retained
outside the task image. No model calibration, push, PR comment or merge was run.
Prose requires human review: the numerical verifier intentionally does not claim
to judge scientific interpretation from keywords.
