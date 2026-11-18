# Figure 4D shared-draw identity checks

The existing prediction scorer cannot tell whether two exports with the same
`Boot_rep` values used the same population vectors. This component checks that
association against independently supplied operator metadata. It does not create
new train/test splits, fit a decoder, prepare neural observations or decide an
improvement claim. The original descriptive hierarchy reconstruction is unchanged.

For every one of the 25 source sessions and 100 repetitions, the operator supplies
all source PV identities, exhaustive disjoint 70/30 partitions, and ordered
replacement draws made *inside* each partition. Repeated identities are retained
as distinct draw occurrences. The recorded sample fraction is explicit; its
historical value is not inferred. Both author and candidate must supply all five
existing comparison arms, each covering every test occurrence exactly once.
Conditional exports may reorder rows by condition. `Draw_occurrence` restores
their shared identity without confusing repeated samples or relying on a label
histogram. Supplied target/condition fields must agree with the independent
operator metadata, including in the shuffled-training controls.

The training draw must contain every declared context-by-condition combination.
This fail-closed feasibility check is consistent with the visible retry condition
in the pinned combined author routine. It does not authenticate the original
accepted draws or stratification, or resolve the original condition support.
Failure leaves that supplied ledger unusable here; this component never retries,
drops or repairs draws and grants no authority to change historical support.

The existing, hash-bound `figure4d-prediction-scoring-v1/scorer.py` then calculates
the scores. Both accuracy and error remain available; conditional groups retain
equal weight, and missing conditions remain undefined. No cross-session average,
biological uncertainty, paper baseline or pass threshold is introduced.

## Operator interface

`validate_session(source, ledger, source_sha256, scoring)` checks one session's
metadata. `score_session(...)` additionally joins both methods' five exports.
`score_panel(manifest, directory)` requires the complete original 25-session
roster and consumes pinned JSON/CSV files. The command is:

```sh
python3 -I -S -B paired_draws.py /operator/paired-panel.json
```

The panel contains `schema: hierarchy-figure4d-paired-panel/v1` and `sessions`.
Each session has `animal`, `date`, `source`, `ledger` and `exports`. The latter
maps `author` and `candidate` to the five arm names in the existing scorer.
Every file descriptor has exactly `path`, `bytes` and lowercase `sha256`.
Paths are operator-controlled; this is not an untrusted candidate file interface.
Files are captured once before their hash is checked, with a 64 MiB per-member
limit. That limit is an engineering input guard, not a measured full-data resource
qualification.

The source JSON has schema `hierarchy-figure4d-pv-metadata/v1`, source `animal`
and `date`, two `context_labels`, explicit `condition_labels`, a
`preparation_receipt_sha256`, and `vectors`. Each vector records `pv_id`,
`context`, and actual-position `condition`. This component cannot determine
whether fine or coarse position is the correct original Figure 4D operand.

The ledger has schema `hierarchy-figure4d-draw-ledger/v1`, the exact source-file
`source_sha256`, `generation`, and 100 `repeats`. Generation contains `kind`
(`historical_record` or `regenerated_original_protocol`), `receipt_sha256`, and
`sample_fraction`. Every repetition contains integer `repeat` (0–99), unique
`train_partition` and `test_partition`, and multiplicity-preserving `train_draw`
and `test_draw` lists. Each list contains source PV IDs. The ledger is a new
instrumentation format: released author exports do not already contain it.

Each CSV has exactly `Boot_rep`, `Draw_occurrence`, `PV_id`, `Real_label`,
`Pred_label`, and `Condition`. The first two are canonical nonnegative integer
strings; occurrence numbers index that repetition's recorded test draw. Exported
rows must use independently retained source identities. Creating identities from
already emitted CSV row order cannot recover omitted historical lineage.

## What remains unresolved

The checks establish internal operator-metadata and prediction-row consistency.
They do **not** show that a classifier actually used the declared training draw,
that the data were speed-equalized correctly, or that the source-preparation and
generation receipts are authentic. Hashes bind supplied bytes, not their scientific
origin. Stratification counts are reported but its RNG/library algorithm is not
replayed or certified. In particular, a matching ratio and class support do not
prove stratified sampling. Shuffle construction, model competence, preprocessing,
feature support, complete source eligibility, historical versus regenerated
protocol qualification, and exposure controls need separate verification.

An authentic operational export must be recorded during independently verified
preparation and fitting, with the ledger frozen before protected candidate
predictions. Participant-supplied targets or a post-hoc invented ledger do not
establish pairing. The published ordinate, numeric baseline, aggregation and
rat-level uncertainty remain unresolved. All scientific outcomes remain unknown;
`paper_win` remains null. A successful generated control is not a reproduction,
improvement result or a ready benchmark.

## Source and checks

The pinned author [decoder source](https://github.com/hchiossi/hpc-hierarchy/blob/95b94942608b2f3e3f7389aeed724459ab3e679e/func_decoder.py)
performs replacement sampling after partitioning; its combined routine shares
sampled vectors across decoding/control arms but does not export those identities.
The adjacent scoring component's `SOURCE_AUDIT.md` retains the known author-code
defects and unresolved paper conventions. `SOURCE_BINDINGS.json` records the
reused local dependency identities and the separate hosted-source observations.

`test_paired_draws.py` exercises generated identity substitution, train/test
crossing, duplicate and omitted occurrences, target corruption, missing controls,
source drift, and the complete 25-session composition with the existing scorer.
No original neural data, author model or candidate model is executed.
