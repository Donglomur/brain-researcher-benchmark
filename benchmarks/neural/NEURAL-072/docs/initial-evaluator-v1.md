# Prospective matrix encoder and contrast evaluator

This additive package implements NEURAL-072's nuisance, lexical and contextual held-story contrasts on externally prepared, frozen matrices. It supplies an executable train/dev/test encoder, an independent held-out scorer, crossed-cluster uncertainty and a temporal alignment diagnostic. It does not supply a Narratives recording reader, contextual checkpoint, admitted case manifest, author encoding baseline, or a scientifically qualified benchmark. The authoritative task and NEURAL-071 specification remain unchanged.

The recipe is prospective. Neither task fixes the exact variance denominator, model or inferential procedure. The paper and official code provide timing, preprocessing and reliability evidence, not this encoder. The full real population, clock alignment, native execution, protected references and rights gates remain open; a successful generated control or asserted pin does not resolve them.

## Source and semantic provenance

- NEURAL-072 task SHA-256: `26b292bd06b0b3a11c7e9b96e44e4a7a1cd0a14ac559b579a3cb70db684630ae`.
- The paired NEURAL-071 task is pinned in `evaluator.SOURCE_TASK_SHA256`. The supplied case manifest must name NEURAL-071, match that task pin and exactly match the protocol's semantic JSON digest. No authentic frozen NEURAL-071 case manifest currently ships with this package.
- [Narratives data descriptor](https://pmc.ncbi.nlm.nih.gov/articles/PMC8479122/) explains that transcript alignment is relative to the audio file; per-scan event onsets map audio to scanner time. Participant identities persist across datasets. Missing word alignment is not time zero.
- [Official code at 1736849ff80c80e1c73eda375ccf6497f5e234a9](https://github.com/snastase/narratives/tree/1736849ff80c80e1c73eda375ccf6497f5e234a9) supplies preparation and ISC analysis, not a predictive encoder. Its `compile_metadata.py` can round onset to TR units and retain the first participant's onset; it is not an exact scan-clock adapter. EAC reliability or best-lag results must not select hidden cases or become an encoding baseline.
- The official code is GPL-3.0; this package is a new implementation of the explicitly stated prospective mathematics and does not copy or vendor author code. MRI/metadata CC0 does not establish rights for every story or contextual checkpoint. Redistribution remains gated.

`provenance.json` maps contract requirements and source observations to this implementation. Code revision pins identify inspected source, not executed or compatible native dependencies.

## Inputs and strict access boundary

The only runtime dependency is an existing Python 3 environment with NumPy. There is no downloader, feature extractor, model invocation or native scientific workflow.

`cases.json` is the complete, externally reviewed NEURAL-071 case manifest. It contains `source_task`, `source_task_sha256`, ordered unique `target_ids`, and a `runs` list. Every run contains:

| Field | Meaning |
|---|---|
| `id`, `listener`, `story_family`, `story`, `scan_identity` | Stable reviewed identities; scan identity is globally unique in this prospective packet. Split runs from the same scan require a separately reviewed adapter, not arbitrary new IDs. |
| `passage_ids` | Reviewed repeated-passage identities. A repeated passage or story cannot be assigned to multiple families. This checks declared metadata; it cannot discover undocumented retellings. |
| `split` | `train`, `dev` or `test`; each family belongs to exactly one partition across all listeners. Every listener must have all three partitions. |
| `n_time`, `tr`, `scanner_start` | Complete feature time axis, positive TR and scanner-clock origin in seconds. |
| `story_start`, `story_end` | Permitted story interval in the same scanner clock, including declared hemodynamic support. These must be established from native scan-specific timing. |
| `indices` | Frozen contiguous fitting/scoring row indices. Every row and target is retained; boundary violations reject rather than silently trim. At least three rows per run are required. |

The protocol is an object with these required fields:

```json
{
  "task_id": "NEURAL-072",
  "task_sha256": "26b292bd06b0b3a11c7e9b96e44e4a7a1cd0a14ac559b579a3cb70db684630ae",
  "recipe": "prospective-whitened-ridge-v1",
  "cases_sha256": "SEMANTIC_JSON_DIGEST_OF_REVIEWED_NEURAL071_CASES",
  "case_scope": "within_listener",
  "context_direction": "past_and_present",
  "nuisance_columns": ["acoustic_envelope", "word_rate", "lexical_log_frequency", "time"],
  "metric": "run-centered-pooled-family-r2",
  "constant_target_policy": "reject",
  "lags": [0, 1, 2, 3],
  "feature_rank": 8,
  "alphas": [0.1, 1, 10, 100],
  "bootstrap_replicates": 2000,
  "null_replicates": 1000,
  "seed": 109,
  "null_min_shift": 20,
  "atlas_pin": "REQUIRES_REVIEW",
  "clock_manifest_pin": "REQUIRES_REVIEW",
  "checkpoint_pin": "REQUIRES_REVIEW",
  "checkpoint_exposure": "REQUIRES_REVIEW",
  "feature_lineage_pin": "REQUIRES_REVIEW",
  "rights_review_pin": "REQUIRES_REVIEW"
}
```

Values above illustrate schema, not an approved scientific configuration or resource budget. All numeric choices, feature lineage, checkpoint exposure, family map, target atlas and case membership must be frozen before outcomes. The runtime accepts nonempty provenance strings but **does not certify their authenticity**; its result always retains scientific holds. A semantic digest is SHA-256 over UTF-8 JSON with sorted keys, separators `(',', ':')`, and no nonfinite numbers; use `evaluator.digest` to avoid serialization ambiguity. CLI output additionally pins exact input file bytes.

`features.json` maps every run ID to five entries. `nuisance` is a time-by-four matrix in the declared order; `lexical` and `contextual` are time-by-feature matrices with stable dimensions across runs. Their columns must be fixed feature coordinates, not hidden responses. `support_start` and `support_end` are per-timepoint union bounds in scanner seconds covering **all** raw feature context across all three blocks. The adapter rejects future support, feature support outside the declared story and lags outside frozen rows. The same nonnegative lag list applies to every arm. The declared bounds and source alignment still require external audit; numbers alone cannot prove a checkpoint was causal or unexposed.

Train/dev target JSON maps exactly those run IDs to matrices with `len(indices)` rows and `len(target_ids)` columns. `predict` rejects any test target key. Test target JSON is supplied only to `score`; it must contain every test run and no training run. Predictions must contain all three arms, every frozen test row and target, and matching case/protocol digests. Missing, duplicate, nonfinite and constant-target cases reject; there is no result-dependent target or row exclusion.

## Fitting and capacity control

Fitting proceeds separately for each listener. Transform fitting uses training rows only during development selection. Nuisance columns are centered and whitened using their nonzero singular directions (relative tolerance `1e-10`). Each linguistic block is centered, projected off those nuisance directions using training least squares, and its first frozen `feature_rank` residual singular directions are whitened. Residual rank tolerance is tied to the original centered feature scale, so floating-point residuals from nuisance-only features are not promoted to signal. Insufficient residual rank or failure of the training Gram orthogonality check rejects the packet.

The resulting lexical and contextual training designs have the same number of orthogonal columns with Gram matrix `n I`; each contains the identical nuisance block. Thus at a shared ridge penalty their effective degrees of freedom match, including the intercept: `1 + d*n/(n+alpha)`. The code computes actual Gram eigenvalue leverage and checks equality. The nuisance-only model has fewer columns by design and is reported as such; the task's matched-capacity control applies to the lexical/contextual comparison.

Each candidate alpha fits both matched arms. The shared alpha minimizes the mean development squared error, first averaging equally across runs and arms within a story family, then equally across development families. Ties use the first ordered alpha. All arms share the selected alpha. Final transformations and coefficients are refitted using that listener's train plus dev rows, with no test targets or test-derived normalization. The output records the full development-loss grid, ranks, effective degrees of freedom, fit counts and allowed fitting row counts. Capacity matching is a deliberate prospective recipe and does not establish that supplied representations are strong or scientifically matched in training exposure.

## Metric and uncertainty

For each test run and target, compute squared prediction error and `SST = sum((y - mean_run(y))^2)` on exactly the same rows in all arms. Pool SSE and SST across repeated runs within each listener/story-family cell, preserving target identity. Per-target `R² = 1 - pooled_SSE/pooled_SST`; the signed contrast is `(SSE_reduced - SSE_full)/SST`. Negative R² and negative contrasts are retained. This is variance prediction, not squared correlation; a biased perfect correlation can score negatively.

The cell contrast is the equal mean across frozen targets, then the primary result averages cells equally within each listener and listeners equally. It is not a duration-, voxel- or trial-weighted participant count. All three pairwise contrasts, target-wise cell values, listener values and family-stratified values are emitted. Any run/target with zero SST rejects the entire packet under the frozen policy, even if another run has variance.

Uncertainty uses independent multinomial resampling of complete listener and story-family clusters (the crossed or pigeonhole bootstrap). Each replicate weights families within listener, then weights listeners. In sparse incidence designs, listeners with no selected observed family receive no value in that replicate and the remaining listener weights are renormalized; entirely empty replicates are counted. Fewer than 90% valid replicates rejects the calculation. Percentile intervals are descriptive for the frozen observed incidence design. The evaluator requires at least two listeners and two test families, but this minimum does not establish adequate inferential power or random population sampling.

The null diagnostic circularly shifts each run's **contextual-minus-lexical prediction contribution** and adds it to the unchanged lexical prediction. It preserves that contribution's circular autocorrelation and parcel pairing, stays inside a single contiguous scored run, and uses a common phase fraction for a family across listeners (identical shift for equal run lengths). Every shift exceeds `null_min_shift` at both circular ends; prediction preparation checks that this guard covers declared feature context plus maximum lag. Scoring external predictions trusts the frozen protocol's guard, so external lineage review is required. Different run lengths map a common phase to different integer shifts; this is not a verified exact alignment null across differing recordings. Output includes all null values and an explicitly diagnostic upper-tail fraction. It is **not** a calibrated p-value, conditional independence test, or refitted null encoder; stationarity and exchangeability are unresolved.

## Execution and engineering checks

From the repository root:

```sh
python3 benchmarks/neural/NEURAL-072/implementations/initial-evaluator-v1/evaluator.py predict --protocol protocol.json --cases cases.json --features features.json --targets train_dev_targets.json --output predictions.json
python3 benchmarks/neural/NEURAL-072/implementations/initial-evaluator-v1/evaluator.py score --protocol protocol.json --cases cases.json --targets protected_test_targets.json --predictions predictions.json --output report.json
python3 -m unittest discover -s benchmarks/neural/NEURAL-072/implementations/initial-evaluator-v1/tests -v
```

The bounded generated controls exercise independently derived exact signed contrasts, biased correlation failure, listener macro weighting, target-scale aggregation, equal effective capacity, train-only transformations, forbidden test labels, family/scan/passage leakage, clock/context boundaries, missing rows/arms, rank and constant failures, reproducible clustered calculations, and CLI input/output byte pins. They use only small generated matrices. They establish engineering behavior, never a Narratives result, a competent contextual baseline, native execution or scientific qualification.

Remaining admission requirements include coherent raw/derivative/git-annex identities, all eligible participant/story memberships, NEURAL-071 authentic case equality, exact clock and HRF support, fixed atlas, checkpoint training exposure, strong source-locked predictive reference, audited redistribution terms, resource admission, protected data handling, native controls and independent authentic reproduction. No recording or checkpoint was fetched and no population was silently reduced for this deliverable.
