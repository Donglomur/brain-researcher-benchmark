# FIND032 complete corrected output protocol

Both access arms return the same complete output family. The assigned input plan
supplies the fixed 33-participant roster and all four recordings per participant.
The condition names are `random`, `midminus`, `midplus`, and `ordered`, in that
order. Use the caller's prospectively selected seed, output member limit, total
output limit, and scientific profile. This protocol is descriptive metadata for
the outputs; it does not supply reference scientific implementation code.

The output is one flat directory. Every entry is an ordinary file named in the
terminal manifest below. No nested directories, extra files, aliases, or omitted
planned families are part of this protocol. No successful terminal manifest is
published when the programme fails. The parent captures the complete output
before either protected reference is opened. Neither a manifest nor a matching
hash establishes scientific correctness, execution provenance, isolation, or a
qualified reward.

## File descriptors and JSON

A file descriptor has exactly `name`, `bytes`, and `sha256`: a basename, its
positive integer byte length, and lowercase hexadecimal SHA-256 of those exact
bytes. Participant matrix descriptors additionally have `key`, the five-element
JSON array `[participant, stimulus, pipeline, condition, score]`. No other
descriptor fields are accepted. Every file fits the explicit member limit; the
sum of all files, including `RESULT_MANIFEST.json`, fits the explicit total
limit. Neither limit has a default.

JSON is finite UTF-8 JSON with no duplicate object keys. Arrays, objects, integers,
booleans, nulls, and strings have their literal types; `true` and `1.0` do not
replace an integer. Metadata pins must match the actual captured bytes. Names
must be unique and the observed complete namespace must equal the declared
files plus `RESULT_MANIFEST.json`.

## Terminal manifest

`RESULT_MANIFEST.json` has exactly these fields:

- `profile`: `corrected_methods_v1`.
- `status`: `source_run_returned_unqualified` when `unavailable` is empty,
  otherwise `partial_scientific_support_unqualified`.
- `products`: every output descriptor, including participant NPZs, all 33
  coverage JSON files, every available group NPZ, `GROUP_INDEX.json`, the
  averaged-confusion NPZ, and all six PDFs. It excludes itself.
- `unavailable`: the full ordered participant and group dispositions described
  below; it is not permission to select a smaller cohort or arbitrary endpoint.
- `structural_controls`: the two complete structural records below, identical
  to `GROUP_INDEX.json`.
- `scientific_qualification`: `false`.
- `native_qualification`: `false`.
- `cost_before_publication`: the original logical cost snapshot. It has exactly
  `limits`, `reserved`, `known`, `unknown_reservations`, and `native_costs`.
  Each of the first three is an object with integer `read`, `write`, and `files`;
  limits are positive and `0 <= known <= reserved <= limits`. Unknown
  reservations are `[domain, nonnegative_integer]` pairs, with each domain's sum
  no greater than its reserved-minus-known amount. `native_costs` is the literal
  `not_observed_by_controller`. This snapshot excludes terminal publication and
  does not measure native resource use.

The qualification fields are required literals of the original serialization
format. They do not provide an authority channel.

## Participant products: 990 planned slots

Each product basename joins its five key components with `__` and appends
`.npz`. Every participant has these 30 planned slots:

| Stimulus | Pipeline | Conditions | Score | Count |
|---|---|---|---|---:|
| sound and omission | replication and empirical_null | all four | accuracy | 16 |
| sound | replication and empirical_null | midminus, midplus, ordered | most_likely | 6 |
| sound | random_oof | all four | confusion | 4 |
| sound | theoretical_null | all four | accuracy | 4 |

Every participant NPZ contains exactly `value.npy`, `train_times.npy`, and
`test_times.npy`. The original corrected layout uses 141 train and test times
from -0.70 through 0.70 seconds at 0.01-second intervals. Accuracy values are
141 by 141; confusion values are 5 by 141 by 141 by 4 by 4. These layouts are
payload-decoder requirements, not facts established by reading metadata.

Only a participant's four theoretical-null accuracy slots can be absent. Such
absence requires the corresponding complete five-fold coverage disposition.
All other 858 participant slots are mandatory. Every planned participant remains
in the cohort; there is no arbitrary successful subset.

## Coverage: all 33 files

`coverage_<participant>.json` has exactly `participant`, `coverage`, and
`structural_random`.

`coverage` has exactly `theoretical_coverage/<condition>` for each of the four
conditions. Each value is the complete ordered array of five folds. A fold has
exactly:

- `complete`: a boolean, true exactly when `reasons` is empty.
- `planned_cells`: a positive integer multiple of 141.
- `reason_counts`: positive integer counts for categories that occur; their
  sum equals `planned_cells`. The only categories are `supported`,
  `no_actual_bracketing_onsets`,
  `omission_context_has_no_sound_confusion_model`, and
  `observed_offset_outside_confusion_support`.
- `reasons`: every unsupported cell. Each record has exactly `target_event`
  (nonnegative integer), `test_offset_samples` (integer -70 through 70),
  `context_event`, and `reason`. Target/offset pairs are unique. A missing
  bracket has null context; the other reasons have a nonnegative context event.
  Category counts exactly match these records. Unsupported targets cannot occur
  in two test folds and cannot exceed the fold's planned target count. Supported
  target identities are not reconstructed from the reduced summary.

An incomplete condition creates exactly one participant unavailable record:
`participant`, `endpoint` (`theoretical_null/<condition>`), `reason`
(`complete observed theoretical support unavailable`), `planned_cells` (the
sum across all five folds), and `reason_counts` (the exact sum by category).
The theoretical NPZ is absent exactly in this case. Participant dispositions
appear in roster and condition order.

`structural_random` has exactly `structural_random/sound` and
`structural_random/omission`. Each record has exactly:

- `kind`: `same_original_random_recording`.
- `input_sha256`: the lowercase SHA-256 of the original random recording; it
  is the same in these sound and omission records.
- `event_indices`: a nonempty array of unique nonnegative integer indices.
- `support_checked`: `exact events/original-samples/labels/data/times`.
- `fit_route`: `paired_condition_random`.

These literal records describe source-produced support. Their presence alone
does not establish the underlying recording, events, fits, arrays, or execution.
The coverage format omits full fold/fit support and must not be used to
reconstruct the original in-memory participant result.

## Group index and all 52 comparison dispositions

`GROUP_INDEX.json` has exactly `comparisons`, `BF10_names`, `policy`,
`unavailable`, `structural_controls`, and `products`.

The full planned comparison identities comprise:

| Identity pattern | Fixed substitutions | Count |
|---|---|---:|
| accuracy/stimulus/pipeline/condition | sound or omission; replication or empirical_null; all four conditions | 16 |
| fisher/stimulus/pipeline | sound or omission; replication or empirical_null | 4 |
| accuracy_difference/stimulus/empirical/condition | sound or omission; all four conditions | 8 |
| fisher_difference/stimulus/empirical | sound or omission | 2 |
| accuracy/sound/theoretical_null/condition | all four conditions | 4 |
| accuracy_difference/sound/theoretical/condition | all four conditions | 4 |
| fisher/sound/theoretical_null | literal identity | 1 |
| fisher_difference/sound/theoretical | literal identity | 1 |
| accuracy/sound/pipeline/most_likely/condition | replication or empirical_null; three nonrandom conditions | 6 |
| fisher/sound/pipeline/most_likely | replication or empirical_null | 2 |
| accuracy_difference/sound/most_likely_empirical/condition | three nonrandom conditions | 3 |
| fisher_difference/sound/most_likely_empirical | literal identity | 1 |

`comparisons` is the sorted array of available identities. `unavailable` maps
every other planned identity to exactly `status`, `reason`, `dependencies`, and
`subjects_required`. Status is `unavailable`; subjects required is integer 33;
dependencies is the exact ordered array below. Available and unavailable form a
disjoint complete partition of all 52 identities.

Only these original dependency dispositions are accepted:

- If any participant lacks a theoretical-null condition, both of that
  condition's theoretical accuracy comparisons are unavailable with reason
  `one or more complete subject theoretical endpoints unavailable` and sole
  dependency `theoretical_null/<condition>`.
- If any theoretical condition is unavailable, theoretical Fisher is
  unavailable with reason `complete four-condition theoretical support
  unavailable`; its dependencies are the missing theoretical-null conditions
  in condition order.
- An otherwise supported Fisher endpoint can be unavailable with either
  `undefined within-person correlation; whole endpoint unavailable` or
  `nonfinite Fisher coefficient; no historical clipping in corrected profile`.
  Its dependency array is empty. The metadata reader does not calculate or
  certify those correlations.
- Each Fisher difference is available exactly when both original Fisher
  operands are available. Otherwise its reason is `required complete Fisher
  endpoint unavailable`, with the absent operands in left-then-right order.
  Empirical contrasts use replication then empirical-null Fisher for the same
  stimulus; theoretical uses sound replication then theoretical-null Fisher;
  most-likely uses sound replication/most_likely then
  empirical_null/most_likely.

Group unavailable records are repeated after participant dispositions in
`RESULT_MANIFEST.json`, sorted by endpoint and with an added `endpoint` field.
All repeated records must agree exactly.

The two structural controls are always available:
`accuracy_difference/sound/empirical/random` and
`accuracy_difference/omission/empirical/random`. Each has exactly `status`
(`structural_identity_null`), `reason` (`identical random recording, selected
support, paired fits and actual products`), `subjects` (33), `coverage` (the
ordered 33 participant structural records, each with an added `participant`),
`inference`, `t`, `p`, and `BF10` (all null), and `interpretation`
(`construction identity control, not evidence for a scientific null`).
Every coverage record must exactly match its participant coverage file.

For index `i` in `comparisons`, `group_comparison_<i padded to three digits>.npz`
contains `subject_values.npy`, `train_times.npy`, and `test_times.npy`.
Nonstructural comparisons additionally contain `t.npy`, `cluster_masks.npy`,
`cluster_p.npy`, and `null_max.npy`. Structural comparisons have no manufactured
statistics. Subject values have the full 33 by 141 by 141 layout; cluster
metadata has the original variable cluster/null extents.

## BF10, averaged confusion, and figures

The three planned BF10 identities, in order, are:

1. `fisher_difference/sound/empirical`.
2. `fisher_difference/sound/theoretical`.
3. `fisher_difference/sound/most_likely_empirical`.

`BF10_names` contains these identities filtered to available comparisons, in
this order. Missing BF10 entries carry their exact comparison dispositions.
For index `i` in `BF10_names`, `group_BF10_<i>.npz` contains exactly `BF10.npy`,
`train_times.npy`, and `test_times.npy` (141 by 141 BF10 values).

`group_oof_confusion.npz` is always present and contains exactly `value.npy`,
`train_times.npy`, and `test_times.npy`; the averaged-confusion layout is
141 by 141 by 4 by 4.

All six PDF files are required: `figure1.pdf`, `figure2.pdf`,
`supplement1.pdf`, `supplement2.pdf`, `supplement3.pdf`, and `supplement4.pdf`.
Metadata checks neither certify PDF validity nor assign a figure-quality metric.

`GROUP_INDEX.products` is the ordered array of group NPZ descriptors only:
comparison NPZs in comparison order, BF10 NPZs in BF10 order, then averaged
confusion. It does not include `GROUP_INDEX.json` itself. Every pin must match
the terminal manifest; extra or missing group files are refused.

## Exact group policy

The policy has exactly these fields and literal values:

- `fixed_seed`: the caller's preselected integer in `[0, 2**32)`.
- `subjects`: 33.
- `correlation`: `Pearson ordinal predictability`.
- `contrast`: `paired difference of Fisher z; never correlation of accuracy difference`.
- `BF`: `BF10 Cauchy scale sqrt(2)/2`.
- `cluster_family`: all 52 sorted planned identities.
- `available_cluster_maps`: `comparisons` minus the two structural controls.
- `structural_control_maps`: the sound control followed by the omission control.
- `BF10_planned`: the three identities in the order above.
- `BF10_available`: exactly `BF10_names`.
- `BF10_unavailable`: the exact unavailable records for missing BF10 identities.
- `unavailable_cluster_maps`: exactly `GROUP_INDEX.unavailable`.
- `cross_map_FWER`: `not claimed`.
- `historical_parity`: `false`.

The metadata reader validates the reported seed's type and range and returns it
for the parent to compare with its original request. It supplies no seed default
and cannot establish that a seed was selected before data access.

## Capture and assessment boundary

First capture `RESULT_MANIFEST.json` to its exact descriptor. The metadata reader
then requests exactly `GROUP_INDEX.json` and all 33 coverage files. After their
pins and full joins are checked, it returns every required NPZ/PDF capture
descriptor and the required NPZ member names. Capture all payload bytes before
opening either protected reference. Checking these metadata records does not
decode the arrays or figures and does not prove their reported dispositions.

Numerical decoding, scientific validation, an independent protected reference,
preselected tolerance, native resource qualification, and any figure assessment
are separate requirements. The existing numerical-agreement diagnostic retains
its explicit endpoint contract; a partially available theoretical family does
not silently become a complete-990 numerical comparison. No improved result,
historical reproduction, or qualified reward follows from metadata acceptance.
