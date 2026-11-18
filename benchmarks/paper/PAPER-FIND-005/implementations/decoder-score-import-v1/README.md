# Original decoding score import

This operator component reconstructs the five original population-decoding effect
vectors from a frozen export of author results. It verifies every real run against
its concatenated outer-test predictions and imports the complete recorded null
grid. It makes no scientific performance claim. Source cohort authentication,
published baseline recovery, author replay, and paper/code adjudication remain open.

Reproduction and same-task improvement are separate first-class outcomes. This
component supplies numerical reconstruction for the reproduction route and an
author reference for a later improvement comparison. A reproduction score still
requires full source fidelity and comparison to recovered original values; an
improvement score additionally requires a justified gain and paired uncertainty.
Neither outcome has been achieved by generated software controls. Future paired
`paper + data` and `paper + data + author code` conditions must retain separate
results on the same frozen cases; this operator importer does not deliver or run
either participant condition.

The preserved `initial-evaluator-v1` computes single-cell sensitivity, which is a
different endpoint. An earlier external `brainwide/decoding.py` implementation was
also inspected and is hash-bound in provenance. This component adds an executable
formatted-result importer to the current task: it rejects duplicated/missing null
run identities, changed trial/unit/probe/fold support, and changed targets across
repetitions. It preserves the original within-session split. It does not add a
mouse-held-out evaluation or train a decoder.

## Scoring

For stimulus side, choice and feedback, probabilities are thresholded with
`p > 0.5`, as in author `process_outputs.py`. Balanced accuracy is computed on the
whole run, then averaged over ten runs. The earlier external helper used `>=` and
would differ at exact ties. Both classes must occur in the full real-run targets.

Wheel speed and velocity use R² after concatenating all original trial/bin
values, then average over two runs. Scores may be negative. The scorer preserves
the scikit-learn 1.1.2 `force_finite=True` convention for constant targets: perfect
prediction scores one, imperfect prediction zero. An undefined single-observation
R² is rejected. The previous helper instead returned an undefined constant-target
score. No average of fold R² or mean of trial R² is substituted.

Binary endpoints require every pseudo ID 1–200 and every run 1–10; wheel endpoints
require IDs 1–100 and runs 1–2. The observed dataset has pseudo ID `-1`. These are
the one-based run IDs in `05_format_results.py`; raw fit files use zero-based runs
and need explicit conversion. Repeated runs are averaged separately for each
pseudo dataset before null medians are computed.

Two effect vectors are reported without choosing a winner:

| Output | Session null summary | Regional reduction |
| --- | --- | --- |
| `source_figure_effect` | Median including the observed run-mean score | Median observed score minus median session null summary |
| `paper_text_effect` | Median of null run-mean scores only | Median of paired observed-minus-null session effects |

The distinction is present in the cached author `process_outputs.py` and
`bwm_figs.py`, versus the paper's Methods. The paper contract currently describes
the second column's paper profile; the implementation exposes both so that an
unresolved historical discrepancy cannot silently become the comparison rule.

Companion statistics use the literal source convention: session p-values include
the observed score and count null ties using `>=`; session p-values are combined
by Fisher's method and corrected by BH independently over the supplied complete
region family for each endpoint (`q < 0.01`). Significant-session fractions use
`p < 0.05`. These are information-presence statistics, not candidate-superiority
tests. The two-session and five-unit minimums apply to the accepted source
region/session roster. Probe populations are merged within a session and region.

## Input and execution

Both JSON files are operator-owned. They contain targets or source result values
and must stay outside public Git and outside the participant interface. The CLI
accepts file SHA256 values pinned independently before import and refuses to
overwrite an existing report. File pins detect changes; they do not authenticate
the original experiment or establish that a caller-supplied roster is complete.

```sh
python3 scorer.py \
  --roster /operator/roster.json --roster-sha256 FROZEN_FILE_SHA256 \
  --bundle /operator/source-export.json --bundle-sha256 FROZEN_FILE_SHA256 \
  --output /operator/score-report.json
```

The roster uses schema `brainwide-decoder-roster/v1`, source revision
`118fc36cb3602934466ad2c6087c2b3b441f9f1f`, freeze `2023_12_bwm_release`, and an
`evidence_kind` of `generated_control` or `unverified_source_export`. Its `cells`
list contains exactly one entry for each planned endpoint/session/region:

- `endpoint`: `stimulus_side`, `choice`, `feedback`, `wheel_speed`, or `wheel_velocity`.
  All five must be represented; region coverage may differ by endpoint.
- `eid`, `region`, `subject`: source session, Beryl region, and mouse identities.
- `pids`, `unit_ids`: ordered merged probe and unit inventories.
- `trial_ids`, `bin_counts`: original retained trial identities and per-trial bin
  counts. Binary targets have one bin. Wheel bin counts are preserved, never
  fabricated, rebinned, or inferred from a convenient array length.
- `outer_folds`: each one-based run ID as a string maps to five arrays of retained
  trial positions. Each trial occurs once; folds operate on whole trials, so all
  wheel bins remain in the same fold. The manifest is frozen by the operator.

The bundle uses schema `brainwide-decoder-formatted-export/v1`, `roster_digest`
from `scorer.digest(roster)`, and a `records` list. Each record contains `endpoint`,
`eid`, `region`, `pseudo_id`, `run_id`, and the original full-run `score`. Source
columns map `balanced_acc_test` or `R2_test` to `score`. For every observed row,
also supply `subject`, `n_units`, `pids`, `unit_ids`, `trial_ids`, `idxes_test`,
`targets`, and `predictions`. The last two are original-trial-order lists of lists,
with one value per binary trial or all original wheel bins per trial. The original
`target`/`predictions_test` arrays are transported without sorting by target value.

Export must use a trusted source reader separately; this tool intentionally does
not deserialize arbitrary pickles. Real targets, identity rosters and folds are
checked across runs. All candidate training history, inner folds and feature
construction are outside this scorer's verification scope. Null masks may differ
from real masks in the source, so real trial membership is never incorrectly
imposed on the null scalar records.

The author's figure settings set `SAVE_PREDICTIONS_PSEUDO=False`. Null scores are
therefore imported as recorded scalars and are **not** relabelled as rescored or
authenticated predictions. This route can reconstruct the original numerical
vector for reproduction from authentic exports when available; it cannot admit unverified
candidate-submitted null scores as a paper improvement. A future protected
comparison needs an independently qualified source export and candidate execution
protocol, complete same-task coverage, and a paired biological uncertainty rule.

## Verification and remaining limits

The standard-library tests use generated arrays, full source repetition counts,
analytic Fisher/BH cases, and counterexamples for fold averaging, class imbalance,
probability ties, constant/negative R², null pooling, and the two median rules.
They exercise CLI pins and reject incomplete or identity-changing exports.
Actual execution status and source hashes are recorded in `provenance.json` and
the external handoff. No new source data, published score vector, real predictions,
author inference, or candidate performance is created by these tests.

Complete source cohort and endpoint masks, paper/code setting discrepancies,
published numeric baselines, author inference, meaningful improvement margins,
paired mouse uncertainty, and episode budgets remain unresolved. Canonical
`task.json`, `improvement.v1.json`, historical evidence and initial evaluator are
unchanged. Registering this importer as a component is an integration proposal;
the task remains `source_unresolved`.

## Optional complete indexed scalar export

Pass `--include-indexed` (or `evaluate(..., include_indexed=True)`) to add
`indexed_collections` with schema `brainwide-decoder-indexed-collections/v1`.
The default report and all existing numerical reductions are unchanged. The
optional operator report exposes all14 scalar members declared for each of the
five endpoint families in `reproduction.v2.json`: observed/null run scores,
observed session means, per-pseudo run means, both null medians, corrected session
effects, session p-values, both regional effects, Fisher/BH statistics, significant
session fractions and regional calls. It does not emit ragged prediction/time
course companions or constitute the full reproduction contract.

Each collection key is its existing `endpoint.member` manifest key. Records retain
exact `eid`, `region`, `pseudo_id` and/or one-based `run_id` coordinates as declared
for that member. Endpoint-specific region support remains separate; no rectangular
region-by-endpoint grid is invented. Records are deterministically ordered and
carry a digest of their key fields/support. These digests bind the supplied
validated roster only; they do not establish authentic original-paper membership.

Observed run `value` preserves the formatted source score, alongside the
`recomputed_value` from existing prediction rechecks. They may differ within the
existing relative1e-9/absolute1e-10 tolerance. Existing session/regional outputs
continue to use the recomputed real scores. Null `value` remains a recorded source
scalar and per-pseudo means average its original repetitions before median
reductions. Neither those leaves nor their derived means become independently
rescored or authenticated predictions. Boolean regional calls remain booleans.

This closes an output-export gap explicitly noted in the current reproduction
declaration, without selecting between conflicting source/paper reductions,
recovering any original observations or result vector, adopting a reproduction
criterion, or qualifying a candidate comparison. Canonical authority/pin updates
remain an integration step. The complete output can be large; empirical execution
needs separately admitted input and resource bounds. No original data run occurred.

The new `IndexedExport` methods in the existing test module cover all70 collection
identities, original repetition counts, heterogeneous region support, retained
negative wheel scores, recorded-versus-recomputed precision, original validation,
deterministic ordering and unchanged legacy summaries. Run just those methods with
`python3 -I -B tests/test_scorer.py IndexedExport`; the existing full test command
also discovers them. Generated controls are software checks, not paper results.
