# Audit the original cross-time decoding panel from predictions

This operator component reconstructs the complete Horrocks cross-time accuracy panel from held prediction exports. It closes an arithmetic gap in the existing `source_metrics.py` interface, which receives already-computed accuracy arrays. It does not qualify source data, fit a decoder, independently observe a submitted program, award paper reproduction or improvement, or establish current SOTA.

The source route trains on a random ceiling-half of the balanced trial positions and tests on the ordered remaining floor-half. It shares each draw across stationary/locomotion states, six classes, and all20×20 training/testing windows; five draws are retained for each of the five original sessions. These details follow the pinned [publication script](https://github.com/eabhorrocks/Horrocksetal24_TemporalDynamics/blob/e3796c13fe7afe7a84854cd5a02c36de268e88f4/Decoding/CrossTimeDecodingAnalysis.m). The current repository's [source findings](../source-decoding-metrics-v1/SOURCE_FINDINGS.md) remain authoritative about unresolved provenance and the implicit `nTrials` dependency.

## Operator inputs

`cross_time_audit.py` requires a separately frozen operator manifest and a newline-delimited prediction export, each with an externally supplied SHA256. The manifest contains all five named original sessions, exact per-state/class trial identities, common ordered good-unit identities, five explicit one-based train/test position draws, and source binding digests. The four source bindings refer to observations, eligibility recipe, the actual `nTrials` assignment, and the original six-class mapping. These are required references, not proof of source authenticity. No source cohort, default trial count, split seed or class-to-physical-speed mapping is invented.

The format is defined by `validate_manifest` and the generated fixtures in `test_cross_time_audit.py`. Every draw has exactly `ceil(n_trials/2)` unique training positions; testing must be the sorted exact complement. Each source state/class must contain the full declared trial roster. Missing mice, states, classes, cells or duplicates are rejected. Original unit identity/order must agree across states; source training-window variance filtering remains outside this audit. A resource ceiling of10000 trials per class causes a refusal above that extent; it must never cause subsampling.

Each prediction record identifies a mouse/state/repeat/train-time/test-time cell, includes the frozen held-order digest, and contains six ordered class-specific prediction lists. Only integer classes1..6 are accepted. Every list must include every held trial. No participant-supplied labels, accuracies or extra fields are accepted. Exactly20000 distinct cells are required. The output retains each integer correct count, denominator and corresponding fraction accuracy in repeat×train-time×test-time order. It preserves all20×20 cells and does not select a favorable time window or collapse the task to a scalar.

**This is an operator-only export.** Grouping predictions by source true class exposes label structure; never present this schema, manifest, trial identity map or evaluator to a participant. A malicious producer can fabricate perfect predictions. Hash and arithmetic checks do not prevent that: an independent execution/capture boundary and authentic protected outputs are still necessary. The code supplies no filesystem/process isolation and does not prove train/test access or fitting provenance.

## Invocation

```sh
python3 -I -S -B cross_time_audit.py \
  --manifest operator-manifest.json --manifest-sha256 <frozen-manifest-sha256> \
  --predictions predictions.jsonl --predictions-sha256 <frozen-predictions-sha256> \
  --output audited-cross-time.json
```

Manifest input is bounded at16MiB; prediction input at128MiB with1MiB per line. Duplicate JSON keys, nonfinite JSON, blank lines, trailing nulls and missing final newlines are rejected. Both complete input digests are checked before a new output is written. Existing output files are not overwritten. These are source construction limits, not measured resources for authentic study execution.

The output is deliberately a cross-time-only audit schema. It cannot masquerade as the existing reducer's complete within-time-plus-cross-time input. A future operator must separately verify the within-time folds and join both authenticated endpoints before using the full source reducer. Both author and candidate can be audited against the same frozen support; comparing them still requires the separately frozen full-panel effect/uncertainty, denominator protection, exposure and information-condition policy.

## Validation and limits

The maintained tests use generated in-memory exports only. They cover the complete20000-cell panel, asymmetric train/test indices, odd/even half splits, support and identity mismatches, malformed labels, omission/duplication, streamed digest checks and trailing-data rejection. They do not exercise authentic recordings, MATLAB, author fitting, candidate execution, disk-success CLI output or scientific results. No task/schema authority or readiness state changes with this additive component.
