# Normalized artifact contracts

These are new evaluator interfaces, not a claim about the uninspected structure
of `VO_dataset.mat`. `evaluate.py` is the executable validator. Unknown fields are
refused on structured records so that participant-provided masks, hidden weights
or replacement grouping cannot change the estimand.

## Assessor reference: `vestibular-reference-v1`

The reference is a protected, independently reviewed input selected by its complete
file SHA-256. Its top-level fields are:

| Field | Meaning |
| --- | --- |
| `schema`, `task_id` | Exactly `vestibular-reference-v1` and `NEURAL-DISC-20261114-VESTIBULAR-VO`. |
| `evaluation_id` | Frozen evaluation identity, a nonempty string. |
| `evidence_id` | SHA-256 identifying the selected public evidence/exposure packet. |
| `access_condition` | Frozen assistance/input condition, such as a particular numerical-tools arm. It must match all compared artifacts. |
| `binding` | Provenance declarations described below. They are not self-validating certificates. |
| `animals` | Three unique authentic animal IDs, or explicitly generated IDs in software controls. |
| `neurons` | Exactly 49 records `{id, animal_id}`. |
| `pairs` | Exactly 35 records `{id, animal_id, neuron_ids}` with two distinct neurons from the same animal. This preserves recorded relationships; it does not infer simultaneity from two names. |
| `groups` | Recording groups `{id, animal_id, session_id, recording_id, stratum, neuron_ids, pair_id}`. |
| `excluded_pairs`, `excluded_neurons` | Exact maps of census identities absent from all declared groups to their pre-established reasons. No omitted census record disappears silently. |
| `conditions` | Unique condition IDs containing all nine registered conditions. |
| `additional_conditions` | Exact map of any extra condition IDs to their source-grounded descriptions. Additional authentic strata cannot be silently dropped. |
| `coverage` | Every animal × condition × stratum cell, with availability and full group/repeat support. |
| `cases` | Exact complete held repeats specified by the coverage rows, including clocks, masks, target and selected-prior arrays. |

The nine registered condition IDs are `naturalistic`, `sinusoidal0.5Hz`,
`sinusoidal1Hz`, `sinusoidal2Hz`, `sinusoidal3Hz`, `sinusoidal4Hz`,
`sinusoidal5Hz`, `sinusoidal8Hz`, and `sinusoidal17Hz`. Their inclusion in the
coverage table does **not** mean that every animal or pair was recorded under
every condition. Authentic availability is unresolved and must be reported.

`binding` has exactly these fields:

```text
kind: generated_control | assessor_supplied
source_version: nonempty source/version description
source_sha256: external source identity
roster_sha256: external authentic inventory/identity review identity
protocol_sha256: frozen split/QC/evaluation protocol identity
target_unit: verified physical target unit, or an explicit generated-control unit
tick_unit: verified exact native clock unit, or an explicit generated-control unit
mask_basis: input_acquisition_metadata
prior:
  id: selected comparator identity
  selection_split: training_only
  selection_protocol_sha256: independently frozen prior-selection procedure
```

The four SHA fields and `evidence_id` are lowercase 64-character SHA-256 strings.
They are retained as externally assigned identities; this module does not retrieve
or authenticate the external source, packet, roster or selection procedure. Every
report explicitly leaves authentic binding, training provenance and scientific
qualification unverified. A reference must not be treated as authenticated merely
because its author supplied these fields.

### Recording groups and dependence

`stratum` is `simultaneous_pair` or `single_neuron`. A simultaneous group must match
the exact two neurons and animal of one declared `pair_id`. A singleton contains
one neuron and has `pair_id: null`; it receives a separate diagnostic vector.
Duplicate group aliases for the same animal, session, recording and neuron set
are refused. Different genuine recordings of a pair can have different group IDs;
the evaluator does not equate 35 recorded pair relationships with 35 groups.

The biological simultaneity and source recording IDs must be independently
established. A fabricated pair table could satisfy structural checks and would
still be scientifically inadmissible. No nonsimultaneous or simulated traces may
be relabeled as the primary observed pair stratum.

### Coverage cells

Each coverage record contains:

```text
animal_id, condition, stratum
status: available | unavailable
group_repeats: [{group_id, repeat_ids: [complete held repeat IDs]}]
unavailable_groups: {every other group in this animal/stratum: reason}
reason: required only when the entire cell is unavailable
```

The selected and unavailable groups must partition **all** declared groups in the
cell's animal/stratum. Every selected group has at least one unique held-repeat ID.
Unavailable cells have no selected groups and a nonempty reason. Both strata have
a row for every animal and condition, even when an entire stratum is unavailable.
At least one simultaneous-pair cell must contain usable cases; an entirely empty
endpoint is refused. There is no imputed score for unavailable cells.

Reasons and exclusions are frozen assessor decisions based on the acquisition and
input protocol. The module checks their accounting, not their scientific validity.
It cannot establish that a supplied list contains every authentic repeat. That
requires the original complete input inventory and an independent admission review.

### Repeat cases

A case has exactly:

```text
id, group_id, condition, repeat_id
sample_ticks: [strictly increasing exact Python/JSON integers]
valid_mask: [booleans, including at least one true]
target: [finite numbers; null permitted only at masked-out samples]
prior: [finite selected-prior prediction for every sample]
```

Case membership must exactly match coverage, without duplicate group-condition-
repeat tuples. Arrays have identical complete native length. Integer clocks never
pass through floating point. The mask is an input-only quality/core mask, including
any previously fixed boundary/halo rule. It is never selected by candidate error.
Preserve every native position once; do not concatenate different repeats or pairs
to fabricate simultaneity. Unusable repeats must be resolved in the externally
reviewed input/QC inventory before this normalized scored-repeat roster is frozen.

## Participant artifact: `vestibular-predictions-v1`

```json
{
  "schema": "vestibular-predictions-v1",
  "task_id": "NEURAL-DISC-20261114-VESTIBULAR-VO",
  "evaluation_id": "selected-public-evaluation-id",
  "evidence_id": "<64-character selected public evidence hash>",
  "access_condition": "selected-access-condition",
  "mode": "fixed_program",
  "cases": [
    {"id": "selected-case-id", "sample_ticks": [0, 1], "prediction": [0.1, 0.2]}
  ]
}
```

This is a shape illustration with placeholders, not an admitted reference or a
valid complete submission. Every required case and native sample is mandatory;
even masked-out positions require finite predictions. Booleans, numeric strings,
NaN/infinity, duplicate cases, extra cases, shifted clocks, missing samples and
participant-supplied masks are refused. Case order may vary; sample order cannot.

Metric arrays use finite binary64 arithmetic. Integer target/prior/prediction
values must be exactly representable in binary64; otherwise admission fails rather
than silently rounding away a prediction error. Exact integer sample clocks are
separate and have no binary64 conversion. Nonfinite metric results and detected
arithmetic underflow fail the whole result; they never become a perfect score.

`mode` is a declared producer label only. Matched comparison requires exactly
`fixed_program` and `case_investigation`, with the same reference/evidence/assistance
condition. Alternative control artifacts can be evaluated individually with clear
labels. Actual code execution, exposure equality, tool calls, time/resource parity
and neural transformations require external observations and are not inferred from
JSON fields.

## Output and failure behavior

`valid_submission` includes the primary animal-condition vector, separate singleton
diagnostics, per-repeat secondary metrics, exact group/sample weights and shared-
neuron links. `valid_comparison` includes both complete evaluations and the paired
cellwise MSE difference. There is no cross-animal primary score and no frozen
scientific pass threshold.

Invalid input, reference, submission or comparison returns an explicit failure
status and `null` primary result, never a partial favorable aggregate. The original
scientific-readiness flags stay false. Full diagnostics belong to the assessor;
safe participant feedback and evaluation-query budgets are separate study controls.
