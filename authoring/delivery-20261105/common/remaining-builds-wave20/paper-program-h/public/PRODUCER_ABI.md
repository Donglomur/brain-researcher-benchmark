# Current candidate producer interface

This common declaration applies equally to A and B. It takes precedence over
legacy submission filenames and launcher directions in TASK.md and
ORIGINAL_PROTOCOL.json. Those retained originals continue to define the selected
native scientific observables, original cohort order, element order and units.
Do not submit legacy submission.json or call a legacy contract.py. No author
implementation or private evaluator is included in this interface.

## Entry, inputs and publication

The controller invokes the candidate's precommitted absolute `native_argv` for
`native_attempt` or `train_argv` for `train_model` under `/program`. Read the
current scientific job from `/job/REQUEST.json`; `/job/JOB.json` contains the
launcher command. `/request.json` is the transport envelope, not a second
scientific-input file. The shared launcher invokes the candidate once, requires
exit status zero, and publishes `/output/OUTPUTS.json` only after the producer
exits. Do not create OUTPUTS.json yourself. Write only bounded ordinary files
beneath `/output` and use `/work` for fresh scratch; links, sockets, devices,
extra hard links and traversal paths are refused. An optional producer
`RESULT.json` can describe its own run; if absent the launcher creates a generic
exit receipt. Neither exit zero nor that receipt establishes scientific success.
Every producer has fresh writable namespaces. No other fold/family/model,
private query, reference output or persistent numerical cache is mounted.

The request includes action, role, case/family where applicable, resource and
model limits, output_root `/output`, and `container_elapsed_seconds`. Its host
absolute `deadline` belongs to the host clock and must not be compared with a
container monotonic epoch. The outer transport deadline is authoritative;
container-local elapsed guards may only restrict it. Images and full source
exposure require a separate independent audit. `/paper` and `/contract` are
common. B additionally receives the exact nineteen author files at
`/historical_author`; A has neither that mount nor author/operator code in its
image. All candidate source is committed before numerical exposure.

## Native output

For native_attempt, `/originals` contains the exact three original MAT objects
listed by the ordered request `originals` records (filename, path, bytes,
sha256). Preserve all 23 behavior animals and all 11 imaging animals, all four
days and both source-preprocessing variants. A/B may use any implementation;
they are not required to use MATLAB, the historical variable names, or eleven
internal calls. Eleven is original recipe coverage per role. Only the fixed
independent reference actually specifies eleven literal calls. No native output
or fitted state is reused in prospective training.

Write `/output/native-dispositions.json` as strict UTF-8 JSON, no duplicate keys,
NaN, Infinity, complex values or executable serialization. Its canonical
scientific envelope has:

- `schema`: `h_native_dispositions_v2`.
- `task_id`: `PAPER-FIND-ADD-003`.
- `slots_expected`: integer 56868.
- `slots`: the complete ordered list below, without omission or duplicates.
- `counts`: count of each emitted status (absent statuses may be omitted).
- `scientific_qualification`: false.

The fixed reference additionally records `call_ledger`,
`ledger_validation_error`, `export_validation_error` and `reference_admission`.
These are its source/run provenance, not a requirement that a candidate mimic
its internal call trace; a candidate may supply its own declarative provenance.
Those extra fields do not replace any slot or establish independent custody.
The score consumes slot identity, value and status; provenance alone is not a
scientific attestation.

Each slot has these fields:
`ordinal`, `variant`, `family`, `animal`, `animal_ordinal`, `element`,
`element_ordinal`, `index`, `units`, `call_ordinal`, `status`, `undefined_kind`,
`reason`, `value`. Ordinals and indices are zero-based except call_ordinal,
which is a one-based original recipe dependency tag, not a candidate call count.
Use variant order `source_preprocessing`, `no_smoothing_no_flooring`, then the
family order below, then cohort order from
ORIGINAL_PROTOCOL.json `cohorts[family.cohort]`, then the exact listed
`families[family].elements` order. `animal` is that cohort identifier;
`animal_ordinal` its position; `element` is the corresponding literal string;
`element_ordinal` and `index` both equal its position. `ordinal` increments
across the entire list, 0 through 56867. This gives 28434 slots per variant.

| Family | Cohort | Elements per animal | Units |
| --- | --- | ---: | --- |
| behavior_accuracy | behavior (23) | 16 | fraction |
| behavior_lick_latency | behavior (23) | 16 | seconds |
| sequence_peak_fraction | imaging (11) | 14 | fraction |
| sequence_index | imaging (11) | 16 | dimensionless |
| time_bin_correlation | imaging (11) | 16 | correlation |
| time_confusion | imaging (11) | 784 | fraction |
| odor_accuracy | imaging (11) | 1096 | fraction |
| odor_information | imaging (11) | 592 | bits_per_cell |

The element lists, including predicted-row/actual-column confusion order,
original padded positions and all real/shuffled conditions, are not replaced
by a smaller panel. For variant index v=0 or 1, call_ordinal is 1 for behavior,
2+5v for sequence_peak_fraction, 2+5v+floor(index/8) for sequence_index,
4+5v for both time families, 5+5v for odor_accuracy, and 6+5v for
odor_information. Behavior values are the same source observables in both
variants and must agree across those variants.

`status` is one of `finite`, `source_undefined`, `failed`, `unstarted`.
For finite, `value` is a finite JSON number and `undefined_kind` is null.
Fractions lie in [0,1], correlations in [-1,1], latency strictly in (0,3),
bits_per_cell is nonnegative and sequence_index is finite without a further
range constraint. For every other status, value is null. For source_undefined,
undefined_kind is exactly `structural` or `computed`; otherwise it is null.
`reason` is a descriptive string, never a substitute for typed status.

Structural undefined positions are behavior elements beginning `standard_`
and containing `_revcued`, and odor_accuracy elements beginning
`bothstandardalignsecond_` whose final bin suffix is <=7. Preserve them as
source_undefined/structural; a finite value there contradicts the literal
observable. A native numerical NaN in another position may be recorded
source_undefined/computed with its cause still requiring independent scientific
audit. Missing work, absent output, failed fitting, invalid nonfinite/complex
values and interrupted execution are failed or unstarted, never relabeled
source_undefined to avoid a failure. No actual undefined census is claimed.

Native comparison joins every slot against the independently executed
reference. Matching finite slots give absolute error in that family's original
units; matching source_undefined kinds remain explicit. Any other disposition
is incomplete/mismatched. Aggregate complete within-animal support, then equal
animals per family/variant; never combine incompatible units, select favorable
cells, or claim that matching computed-undefined causes establish competence.

## Prospective training and model export

For train_model, `/input/TRAINING.json` has schema `h_training_view_v2` and
keys `schema`, `family`, `rows`, `groups`, `arrays`, `inner_folds`, `channels`,
`clock`, `null`, `feature_support`, `both_classes`, `query_labels_exposed`.
It describes only the admitted outer training trials. There are 595 rows for
an edge fold or 590 for an interior fold (five windows per trial), with 119 or
118 whole-trial groups. Group labels are local training identifiers, not
original trial IDs. Rows are not chronological query order. Candidate internal
tuning is unrestricted inside this view; the public inner_folds describe the
fixed independent comparator's six purge-respecting inner partitions.

Array descriptors contain exactly path, bytes, sha256, shape, dtype. Paths are
relative to `/input`. NPY version1 arrays are primitive and C-contiguous:
`values` `<f8` [rows,C,15] and `missing` `|u1` [rows,C,15] (1 means missing;
values are zero there); `labels` `<i8` [rows,1] and `trial_group` `<i8`
[rows,1]; clock-permitted families also have `clock` `<f8` [rows,5]. Labels
0/1 represent first odor A/B. Neural-only has eligible neural ROI channels and
no explicit clock; nuisance_clock has locomotion then lick counts; combined
and shuffled_combined append those two channels after neural ROIs. The same
source iscell>0.3 eligible ROI support applies to every role. Other background
ROIs are not prospective inputs. Fixed clock_prior is separately produced by
the common analytic program and contains no trained candidate model.

The shuffled family receives only the shared conditional atom-permuted outer
labels, plus the public commitment and count summary. No seed, source atom
indices, permutation, unshuffled training vector or original validation target
is exposed. A candidate does not see the private query IDs, order, conditions,
labels or other windows. Public-data/prior-memorization limitations remain.

Write `/output/MODEL.json` with exactly these keys:
`schema` (`h_model_v1`), `family` (the request family), `graph`, `arrays`,
`input_shapes`, `training_provenance`. The graph and its exact supported
primitives are in GRAPH_ABI.md. `arrays` maps constant names to exact
`{path,bytes,sha256,shape,dtype}` descriptors under `/output`; use NPY version1
float64 `<f8` or Boolean encoded `|u1` values exactly 0/1. Constants must be
finite and every declared constant must be used. No pickle, object array,
executable model, callback or fitted private evaluator may be exported.
`training_provenance` is declarative producer-reported metadata, not trusted
resource telemetry. All model JSON plus constant bodies count toward the
complete model cap; all output bodies and manifests also count toward phase
capture caps.

`input_shapes` is exactly values=float64 [C,15], missing=bool [C,15], plus
clock=float64 [5] for clock-permitted families; neural-only omits clock.
The schema uses `{shape:[...],dtype:"float64"|"bool"}`. Arbitrary candidate
training can choose any admitted graph, including nonlinear predictors, within
the agreed method and full-shape/work limits. At each private query the
operator creates a fresh graph workspace and immutable snapshots, passes only
one local window, and requires one finite scalar margin; class1 iff margin>=0.
Calibration is already part of the graph. Models may not preserve query state.
All 9240 slots seal before any query evaluation. All 924000 predictions,
complete OOF class support and all matched controls remain mandatory. Undefined
or failed support is retained; no cohort is reduced to make a comparison pass.
