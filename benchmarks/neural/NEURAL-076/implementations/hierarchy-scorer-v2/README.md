# NEURAL-076 hierarchy scorer, version 2

This package supplies the missing target-consuming numerical component for the
current task. It recovers the historical trial/feature artifact reader and unit
identities, validates the complete 650-context prediction collection before any
target access, and computes the registered signed cnn7-minus-cnn1 interaction.
It does not run a decoder or qualify a biological result. Canonical task,
understanding contract, historical declaration and earlier source remain unchanged.

The source audit found a real endpoint mismatch: the recovered legacy scorer's
primary was the average CNN5–8 minus average CNN1–4 interaction. This successor
reports that statistic as a named secondary contrast. The current primary is
exactly, for each of five people:

`D = [r(HVC,cnn7) - r(HVC,cnn1)] - [r(LVC,cnn7) - r(LVC,cnn1)]`.

The equal-five-person mean and all five signed values are returned. A negative
or zero interaction is a valid outcome, not an error or biological inaccuracy.
There is no p-value or confidence interval: inferential choices and multiplicity
must be frozen separately before a scientific execution.

## Estimand and full coverage

Each of the five people has all ten ROIs and thirteen families, for 650 contexts.
Every context contains 500 imagery and 1,750 perception predictions for the same
1,000 identity-selected units. The exact v1 public manifest and flat NPZ formats
are retained; GIST's 1,000 of 1,024 units use the original identity-only hash rule.

The operator privately averages predictions within each of 50 categories (ten
imagery repeats; all 35 perception repeats). For each unit it computes signed
Pearson correlation **across categories** against the category-feature bank,
then takes the arithmetic mean over all 1,000 units. This is the source's profile
correlation axis and category-first order, not a correlation across feature units,
flattened correlation, Fisher-z mean, or category identification accuracy.

The complete 5 × 2 × 10 × 13 matrix is reported. Perception retains every supplied
repeat; the recovered legacy scorer's ten-repeat perception subsampling is not
used. Consequently the transfer diagnostic compares ten-repeat imagery against
35-repeat perception and may reflect different averaging precision. A separately
frozen matched-repeat diagnostic is still needed before interpreting that gap.

Undefined constant correlations produce a null cell mean with the exact unit
positions, and propagate to any dependent contrast/person mean. No unit or person
is silently dropped; no zero is imputed. This deliberately differs from both the
legacy zero convention and the author demo's `nanmean`. The ordinary nonconstant
case preserves the source arithmetic correlation mean. A no-neural predictor
constant across categories is thus explicitly undefined under Pearson, not an
invented zero-performance measurement. Strict handling may reveal genuine
undefined source units; any eligibility alternative requires a prospective,
training-only protocol rather than outcome-based filtering.

## Operator execution

Use an externally prepared, authenticated compact operator bundle and a frozen
complete submission. This component never creates targets or launches candidates:

```sh
python score.py --public /operator/public_manifest.json \
  --operator /operator/operator_manifest.json \
  --submission /frozen/submission.json --out /new/report.json
```

The trusted operator manifest uses the recovered `neural076_operator_v1` format:
it pins the public manifest and target archive by exact bytes and SHA-256. The
public manifest uses `neural076_matched_hierarchy_v1`; the submission uses
`neural076_predictions_v1`. Each NPZ has exactly `features` (2250 × 1000 float32
or float64), `trial_ids` (U25), and `unit_ids` (integer). Public trial IDs and units
must match in order. The first 500 rows are imagery and the remaining 1,750 rows
are perception. Every context and filename is unique and canonically ordered.

The target NPZ contains the ten `<person>_<phase>` integer label vectors and
thirteen `bank_<family>` 50 × 1000 floating matrices. Labels are compact category
indices, with complete fixed repeats. Target schema, expanded size and NPY headers
are checked before loading. The real target packet is never shipped with source.

All 650 prediction blocks are read, checked for finite values and hashed before
the private loader is called. The scoring pass rechecks those exact bytes. Failed
or changed submissions receive no primary value. A completed collection with
undefined correlations retains its full report and a distinct status. Reports
are created exclusively; an existing report is never overwritten. Hashes provide
content binding, not sandboxing or proof of train-only fitting. The operator must
freeze candidate execution separately and keep its target location inaccessible.

## Evidence and limits

`SOURCE_PINS.json` records the exact recovered software and primary-source files.
`test_generated.py` exercises numerical and malformed-output controls, including a
full 650-context numerical dispatch over generated full-size in-memory blocks.
The archive reader is tested on a real generated 2250 × 1000 NPZ. No biological
arrays, historical target values, candidate predictions or empirical scores were
read or generated in this revision. No data acquisition or model trial occurred.

The component still needs an integrated, authenticated producer/participant
delivery route; independent validation on legitimate source arrays; the frozen
perception-trained, category/no-neural and training-permuted comparator collections;
and a prospective inference protocol. The supplied historical source pins do not
prove availability or correctness of their data payloads. Category identification
ranks and decoder training are outside this component. It establishes software
scoring behavior, not direct/viewer interpretation, original-paper replication,
cue-free imagery, temporal/causal hierarchy or scientific qualification.

## Paired complete-collection comparison

`compare.py` admits two frozen program/analysis collections against the same
authenticated public manifest and one operator target packet. Each condition
retains all 650 contexts, 1,300 phase cells, matched unit identities and five
participants. Both full public validation passes finish before the single target
load; scoring rechecks every captured prediction hash. A missing, malformed or
changed block in either collection yields no partial comparison.

```sh
python compare.py --public /operator/public_manifest.json \
  --operator /operator/operator_manifest.json \
  --first /frozen/first/submission.json --second /frozen/second/submission.json \
  --out /new/paired-report.json
```

The report preserves each condition's current primary, legacy secondary and
complete diagnostics. It adds first-minus-second values for every participant,
phase/ROI/family cell, signed contrast and absolute-imagery companion, with the
equal-five-person mean. An undefined value in either condition propagates to the
corresponding paired difference and dependent mean; participants are never
removed. No confidence interval, p-value, multiplicity correction or superiority
decision is introduced. A larger signed hierarchy interaction is not better
accuracy. Direct and viewer conditions remain unsuitable for this registered
endpoint; condition names here do not establish an access mode or train-only
provenance. Candidate execution and target custody must be enforced separately.

The same existing frozen formats and target loader are used, without modifying
the single-collection scorer or historical controller bindings. The comparison
requires twice the single scorer's prediction-read allowance: two passes over
each complete collection, capped at 65,431,142,400 prediction bytes in total,
plus operator/source/report I/O. This is a prospective bound, not a measured
authentic workload or an execution authorization. Runtime, resource, input and
scientific qualification remain outstanding.

Run the focused generated controls with `python -I -B test_compare.py`. They
exercise both complete panels, target-load ordering, source/row/unit bindings,
late malformed or changed second submissions, strict undefined propagation,
negative effects and exclusive report creation. The full-panel orchestration
uses invented broadcast blocks and a scripted cell scorer; separate real
category-correlation controls use generated arrays. These are software checks,
not 1,300 authentic predictions or evidence of neural understanding.
