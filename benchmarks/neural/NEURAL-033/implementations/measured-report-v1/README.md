# Recovered full-cohort activity-rank report grading

This package restores the previously absent **numerical report grader** for the
historical full30 public investigation. It preserves the recovered estimator, adds portable input delivery, and tests
rejection of scientifically wrong values. The current artifact scorer corrects
mean accumulation so representable positive errors cannot disappear when each
term is divided before summation; the declared metric and panel weights are unchanged. Structural admission alone does not establish
numerical correctness.

The exact historical feature is `spine_activity_rate`, projected as `event_rate`.
The current registered question calls its feature **coactivity**. Those are not
established as equivalent. This package is a historical activity-rate comparator,
not a completed implementation of that coactivity target. No canonical task,
understanding contract, registry, or access-mode declaration is changed here.
The current nuisance-only/common-slope comparison and acquisition-covariate
analyses also remain outside this recovered historical estimator.

## Measured endpoint and independent units

The source projection comprises all 1,936 rows, 44 source members, and 30 mice:
1,143 control rows from 27 members/20 mice and 793 Kir rows from 17 members/10 mice.
It contains source-measured baseline/followup volumes and activity rates; later
volumes are permitted public observations, not protected prediction labels.

The recovered protocol in [protocol/CONTRACT.json](protocol/CONTRACT.json) fixes:

- Persistent-spine eligibility with source flag semantics and ordered exclusions.
- Difference of base-2 volume logs as the outcome; dimensionless weighted mid-CDF
  activity and baseline ranks, initially equal total mass per mouse within group.
- Four treatment-by-compartment WLS models, with all support and fixed joint
  thirds balancing; balanced fits retain the initial ranks.
- Kir-minus-control slopes in both compartments and their apical-minus-basal
  difference. These separate group fits encode the complete slope interaction;
  they do not estimate a randomized causal effect.
- Whole-mouse deletion across both compartments, reranking and balancing both
  cohorts on every replicate, with the prebalance eligible deletion roster.
- Explicit rank-deficient, insufficient-support, zero-overlap, null-point and
  unavailable-uncertainty outcomes. No forced nonzero effect or ridge fallback.

Activity-rate unit equivalence between cohorts remains unverified. Relative
ranks do not resolve that construct issue. Mice, not rows/FOVs, are the independent
units; conditioning on persistence does not measure formation or survival.

## Operator use

Use the already available Python 3.12.8 / NumPy 2.2.6 environment for comparisons
to the recovered implementation. No dependency installation, container pull, or
network fetch is part of this package.

The operator must supply a directory containing the **exact** external
`identity.json`, `observations.json`, and `submission.schema.json` pinned by
[SOURCE_INPUTS.json](SOURCE_INPUTS.json). The pins came from the historical source
manifest. The schema enumerates real source identities, so it also stays external.
An arbitrary similarly shaped table or narrowed panel is refused. The remaining
three public view files are supplied under `protocol/`. All six files are checked
before any participant view is created. Use a fresh output path:

```sh
python -I -B operator.py prepare --source-input /operator/full30-public --output /operator/new-public-view
python -I -B operator.py grade --source-input /operator/full30-public --submission /submission/report.json --output /operator/new-grade.json
```

These examples are operator commands, not authorization to launch native analysis
under an active resource limit. `prepare` checks joins and exports exact bytes;
it does not fit. `grade` admits the complete artifact before reading observations,
then recomputes the report using the pinned measured inputs. Candidate code is
never imported or executed. Exit 2 means an invalid submission, and exit 3 means
an operator/input/recomputation failure. The numerical grade JSON remains a
continuous diagnostic with no scientific-success threshold.

The primary metric is the mean normalized absolute contrast error within each
panel, then the equal mean of the two panels. Missing availability or support,
counts, statuses, ranks, exclusion identities or deletion-roster disagreements
make the primary null. Defined coefficient, overlap-mass, effective-mouse and
uncertainty errors remain secondary numerical diagnostics. A null primary is not
a perfect score. No new pass tolerance is invented.

Use only `operator.py` as the portable CLI. Files under `recovered/` retain the
historical estimator and interfaces, with the mean-accumulation correction in
`score.py`; their historical standalone CLIs expect the old package layout. `run_checks.py` runs all inherited generated controls and the new operator
controls. In this parallel construction wave it must run through the shared test
pool; no authentic input is read by any test.

## Delivery and qualification boundaries

| Condition | This package supplies | Remaining gap |
| --- | --- | --- |
| Direct observation | Exact six-file numerical observation export and complete artifact schema | Bounded no-tools presentation and response collection |
| Typed viewer | Same source contract only | Audited task-specific image transport and complete responses |
| Tool assisted | Numerical operator recomputation; no participant-facing tools | Matched investigator transport, action budget, and case reset |
| Frozen program | Complete observation export and artifact grading boundary | Frozen program capture, isolated execution, natural-exit evidence |

No participant-mode or native-runtime qualification is claimed. This revision
opens answer-free source and old public protocol/schema metadata only. It does not open
historical private answers or authentic observation/identity bodies, rerun source
preparation, fit measured data, or run an agent/model. The historical 30-mouse
scope is retained; eligible uncertainty support may be smaller. Historical source
preparation receipts do not become a new authentic-data execution result.

Primary provenance is Wright et al. (2025),
[Science DOI 10.1126/science.ads4706](https://doi.org/10.1126/science.ads4706), and
[Zenodo release 15047046](https://doi.org/10.5281/zenodo.15047046).
The analysis is the benchmark's prospective estimator, not the paper's estimator.
See [protocol/LICENSES.md](protocol/LICENSES.md) for attribution and the selected
archive-member checksum limitation. The 2.1 GB whole-archive checksum was not
newly verified. Original recovered-source hashes and validation results remain recorded in
`RECOVERY.json` as historical provenance; its original `score.py` hash describes
the predecessor, not the corrected current scorer. `test_mean_precision.py` adds
generated complete-report controls for that correction. External construction
receipts retain actual resource costs.
