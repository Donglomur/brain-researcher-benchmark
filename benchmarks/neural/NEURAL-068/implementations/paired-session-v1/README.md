# Paired recalibration scorer

This executable component implements the **current NEURAL-068 contract**: seven source velocity channels, fourteen later runs grouped into seven official H1 sessions, both `neural_clock` and `clock_only`, and fixed 0/5/10-second calibration budgets. Its primary output is the equal-session mean of paired recalibrated-minus-unchanged variance-weighted R² at **each** budget. It does not select the best budget.

`scorer.py` uses only Python's standard library. `make_layout` accepts complete source clock, TrialNum, mask and source-identity metadata for all fourteen later runs. It recovers the historical split without reading targets: the first 250/500 bins form 5/10-second elapsed-time calibration prefixes; only source-mask-positive prefix rows may be labelled. The common query is the complete third TrialNum segment. A one-second guard separates the full target-construction support (12 past / 13 future bins) from the ten-second calibration prefix. It requires a verified zero-origin 20-ms source clock, never infers timestamp semantics from an NWB `rate` value. The source loader and timestamp audit are still required upstream.

The output layout binds every source hash, official dataset/session ID, ordered native-bin row ID, query mask and calibration-label count. The hash binds the supplied metadata; it does not prove source authenticity. Operators must verify each source SHA against the pinned archive and persist the exact prepared layout before execution. No authentic layout or target packet is shipped here.

`score(layout, submission, target_loader)` admits all 84 contexts before opening evaluator targets. Each prediction contains every ordered query row and seven finite, nonboolean values, including masked rows. Targets are joined by the same explicit ordered IDs. Each admitted target row is copied before the next loader call, so a streaming loader may reuse mutable row buffers without changing earlier runs. Within each session, masked rows from both source sets are concatenated **before** computing multichannel variance-weighted R². Sessions then receive equal weight, regardless of row count. The zero-second prediction in each arm is the unchanged-decoder comparator on exactly the same suffix. A frozen operator protocol must establish that this arm actually uses the unchanged, competent decoder; the scorer cannot infer fitting provenance from predictions.

Constant target columns receive zero metric weight, matching the official variance-weighted estimator where other columns vary. Their SSE, zero SST and undefined per-channel R² remain in the result; no errors are silently removed from diagnostics. A session with all seven targets constant makes the complete primary result undefined and remains in the output. This intentionally avoids sklearn's finite constant-target fallback. Extreme arithmetic overflow and nonconstant variance underflow fail explicitly.

Secondary results contain both arm curves, paired gains, neural-minus-clock R², and the difference between both arms' recalibration gains. Session/run counts are descriptive repetitions of **one person**, not biological replication. The scorer establishes neither causal motor interpretation nor a direct/viewer understanding capability.

## Operator interface

Create a layout using `make_layout(source_metadata)` after authentic source preparation. Source metadata is a list in `RUNS` order with exactly `run`, `source_sha256`, `time_s`, `trial`, `eval_mask`. The full arrays must describe the complete recording. Keep the source payloads and evaluator targets outside the repository and outside participant access.

Submissions have `schema`, `packet_id`, `contexts`. `contexts` is keyed by `RUN__ARM__BUDGET`; every value has `row_ids` and a row-major `predictions` list. The schema is `neural068-paired-session-v1`; the packet ID comes from the frozen layout. Operator targets are keyed by the exact fourteen run IDs; each value has `row_ids` and `targets` on the complete common suffix.

```sh
python3 -I -B scorer.py --layout /operator/layout.json \
  --submission /frozen-output/submission.json --targets /operator/targets.json \
  --output /operator/score.json
```

The CLI rejects duplicate JSON keys and malformed submissions before opening targets. Target staging and this CLI are trusted operator actions, not a participant transport. Do not expose evaluator targets, query kinematics, other-case state or post-score selection to participants.

## Source lineage and current limits

The official source pins are recorded in `source_pins.json`. Existing cached source files were checked against the previous source manifest. The recovered legacy `public/protocol.py` provides the complete fourteen-run roster and fixed-prefix/third-segment split. The source official `H1_NEW_TO_OLD` map independently binds those runs to sessions S6–S12. The pinned evaluator's `compute_metrics_regression` pools sets in sessions, applies the evaluation mask and calls `r2_score(..., multioutput='variance_weighted')` before equal-session averaging.

The recovered historical scorer, including its exact-constant successor, instead averaged run-level all-dimension energy R² and selected absolute neural-clock 10-second R² as primary. That behavior is preserved in its historical location and is **not** asserted to implement the current contract. This new version resolves the current endpoint mismatch without rewriting historical artifacts, registrations, source data or outcomes.

The generated controls exercise full 84-context admission, independent closed-form paired gains, session pooling of individually constant runs, unequal session lengths, mask exclusion, channel weighting, exact constants, target joins, clock/prefix boundaries, numerical failures and the real CLI. They are software checks, not authentic performance evidence. No new native preparation, baseline execution, candidate trial or empirical recalibration benefit is claimed.

Still unresolved: authentic NWB ingestion/alignment and full packet verification; dataset terms versus redistribution restrictions; precommitted unchanged/source-reference and shuffle controls; causal participant execution and budget enforcement; cross-task 067/068 exposure; complete direct/viewer/tool/programme delivery; independent scientific qualification. This component alone does not make NEURAL-068 submission-ready.

## Matched direct/program assessment

`compare_access.py` compares complete `direct_observation` and `frozen_program`
submissions on the identical frozen layout. It validates both 84-context
submissions before opening evaluator targets and captures each of the fourteen
target runs once for reuse by both conditions. Each condition retains the
unchanged scorer's full output and original recalibration primary endpoint.
The additional outputs are program-minus-direct differences in absolute R²,
recalibration gain, and neural-minus-clock recalibration gain, at every fixed
budget. Contrasts are paired within the same seven sessions, then equally
averaged across sessions; no best budget or subset is selected.

```sh
python3 -I -B compare_access.py --layout /operator/layout.json \
  --direct /frozen-output/direct.json --program /frozen-output/program.json \
  --targets /operator/targets.json --output /operator/access-comparison.json
```

Both submissions use the existing `neural068-paired-session-v1` format. An
all-constant target session leaves the comparison undefined while preserving
both conditions' full session diagnostics. The target panel and comparison
CLI remain operator-only. The condition names are assertions supplied by the
operator: this component does not verify no-tools compliance, matched permitted
observations, compute entitlements, unchanged-decoder provenance or recipe
freezing. Establish those independently before interpreting the contrast as an
access-condition effect. These are descriptive paired sessions from one person,
with no human-population confidence interval. Generated comparison controls do
not deliver authentic observations or establish neural understanding.
