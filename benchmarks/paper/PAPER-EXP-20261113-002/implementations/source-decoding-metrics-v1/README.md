# Source decoding metric reduction

This standard-library component computes the original decoder-output reductions
for the five-mouse Horrocks task. It preserves separate stationary (`stat`) and
locomotion (`run`) results, the within-time accuracy curves, the complete
cross-time accuracy matrices, and the denominator of relative generalization.
It does not fit a decoder, select trials, authorize a scientific run, or award a
reproduction or paper-improvement result. The historical frozen-decoder component is unchanged.

Reproduction and improvement are separate first-class outcomes. For
reproduction, this reducer provides the original accuracy arrays and
mouse-level reductions needed for numerical agreement against authenticated
source output. For improvement, it provides the same metrics and companion
denominators for a paired candidate-author comparison. Neither outcome is
established by source recovery or generated controls. Paired paper+data and
paper+data+author-code conditions require a separate matched participant
delivery protocol; this operator component supplies no such trial.

The implementation is grounded in the publication commit
`e3796c13fe7afe7a84854cd5a02c36de268e88f4`, with source identities recorded in
[SOURCES.json](SOURCES.json). The source scripts have been recovered and their
bytes matched to the cached publication tree's Git blob identities. This
recovers executable aggregation semantics; it does not recover original
accuracy values or authenticate the exact figure-producing configuration.

## Native arrays and reduction order

`source_metrics.py` accepts an operator-exported JSON document with schema
`horrocks-source-decoding-accuracies-v1` and a `sessions` object keyed by all five
public source session names: `M22027_20220517`, `M22029_20220607`,
`M22031_20220524`, `M22032_20220621`, and `M22033_20220706`.
Each session must contain exactly `stat` and `run`. Each state contains:

| Field | Shape | Native source quantity |
|---|---|---|
| `within_time` | 5 × 191 | Five `GammaOne.perm.meanPerf` curves in the author reference route; candidate uses the same original evaluation support. |
| `cross_time` | 5 × 20 × 20 | Five `perm.perf` matrices, axes permutation × training time × testing time. |

Accuracy is a fraction in `[0,1]`, not percent. Within-time window centers run
from −150 through 1750 ms in steps of 10 ms; cross-time centers use 100 ms steps.
All windows are 100 ms wide. No missing mouse, state, permutation or time cell
is accepted. Numerical source arrays and any exported results belong outside
Git and outside candidate access when they are protected evaluation outputs.

The operator must independently bind these arrays to the original cohort,
trial/unit eligibility, split draws, population setting and method. The JSON
shape and session names do not prove those facts. This component cannot
silently adapt the subsampled `session.popSize.rep` route into the full-population
figure route, or promote the historical chronological pooled-state extension.
There is no automatic MAT-file discovery or private target access.

The additional source recovery is described in
[SOURCE_FINDINGS.md](SOURCE_FINDINGS.md). In particular,
`CrossTimeDecodingAnalysis.m` supplies a full-population route with this native
array structure. Its existence does not authenticate a saved paper-producing
run; it has an implicit `nTrials` workspace/input dependency that must be
resolved before a clean replay.

Within-time `do_cvDA.m` calculates accuracy within each held fold, then averages
the three fold accuracies equally. `score_within_time_folds` exposes that
calculation for six class-ordered prediction lists in each fold. For fold sizes
3, 3 and 2 trials per class, fold accuracies 1, 0 and 0 give 1/3, whereas pooling
held predictions gives 3/8. The reducer consumes the resulting native
`meanPerf` curves and averages the five permutations before averaging mice.

For cross-time accuracy, the reducer first averages the five 20×20 permutation
matrices for each mouse/state. For each training row, relative generalization
is the sum of positive accuracy-minus-1/6 over testing windows 0–100 through
900–1000 ms, divided by the corresponding sum from the matrix diagonal. This
is a ratio of sums after permutation averaging. Each mouse's ratio is computed
before the five-mouse mean and sample SEM. The early training window is
100–200 ms (MATLAB index 4, Python index 3).

The raw matrices, diagonal curves, numerator and denominator remain in the
output. Ratios can exceed one and are not clipped. A zero denominator produces
`null` and an explicit reason; group relative summaries remain undefined if
any mouse is undefined. No mouse is dropped and no epsilon is substituted.
The output includes all 20 mathematical row reductions; the source analysis
plots the first 12 training windows and selects index 4 for its early-window
comparison. Extra row reductions are diagnostics, not extra benchmark tasks.

## Run on a frozen operator export

```sh
python3 -I -S -B source_metrics.py \
  --input operator-accuracies.json \
  --input-sha256 "$ACCURACY_EXPORT_SHA256" \
  --output source-summary.json
```

The SHA-256 must come from the operator's frozen export receipt. Input is
limited to 4 MiB; output must be new. Duplicate JSON keys, nonfinite values,
Boolean accuracies, incomplete shapes and percentages are rejected. The
completion receipt gives the new output digest. This is an operator-side
numeric reducer, not a hostile-participant sandbox or a source-authentication
system. The output contains numerical per-mouse results and must remain in the
appropriate evaluation boundary.

## Qualification and remaining work

Eleven generated controls passed under Python 3.11 in the shared one-thread
test pool, including the real CLI on a generated complete cohort. They exercise
arithmetic and full-support handling. The test child used 0.207 CPU seconds
and a recorded maximum child RSS of 25.6 MB; queue time is excluded from CPU
cost. No
authentic accuracy array, recording, coefficient, hidden target or prediction
was opened or evaluated to implement this component; no MATLAB job, fitting,
inference or candidate trial was run. Python arithmetic has not been
numerically calibrated against an actual MATLAB reference execution.

Still required for the registered task: bind the precise figure-producing
cross-time run to the recovered full-population route and original stochastic protocol; produce or
recover complete native accuracy arrays; independently qualify author output;
freeze paired candidate-author comparisons, meaningful effects, uncertainty
and budgets. A higher ratio caused by a weaker diagonal denominator is not an
improvement. The reducer exposes both quantities and grants no binary reward.
The existing task and improvement contract remain `source_unresolved`.
