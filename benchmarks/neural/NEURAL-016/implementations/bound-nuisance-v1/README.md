# Operator-bound nuisance scoring

This component closes a concrete gap in the existing NEURAL-016 evaluator: a
candidate could increase the reported full-minus-nuisance contrast by worsening
its own nuisance predictions. The new operator entrypoint accepts **full-only
candidate predictions**, injects nuisance predictions from a separately pinned
operator file, and recomputes the original held-out contrast. The predecessor,
canonical definition and historical results remain unchanged.

The current primary is signed SSE-based `delta_r2`. Both signs are valid. The
component retains the predecessor's exact row matching, complete recording
accounting, person/movie separation, temporal guards, complete-block scoring,
constant-target rejection, distinct EV, and paired participant bootstrap. It adds
absolute nuisance/full R² and EV summaries with the same equal weighting of
blocks within electrodes, electrodes within participants, and participants.
`full_prediction_statistic` is absolute full R²; `claim_score.absolute_error`
measures agreement of the candidate's stated signed contrast with the recomputed
contrast. Neither a large increment nor a positive claim is rewarded as accurate
interpretation by itself.

## Trust and scientific scope

The operator must acquire and freeze the nuisance recipe, fit artifacts and
held-out predictions **before examining candidate outcomes**, and store their
expected file SHA256 in operator-controlled configuration. The CLI's
`--expected-nuisance-sha256` is supplied by that configuration. It must never be
copied from a candidate packet or generated from whatever file the candidate
submits. The comparator file is validated against that exact byte digest before
the CLI reads private targets. Replacing predictions, artifact identities, or
even file formatting invalidates the binding. A candidate cannot insert nuisance
values or choose an alternative comparator through its schema.

This is byte binding, not an authentication service or proof of correct fitting.
The digest does not establish actual train-only execution, baseline competence,
independent ownership, or freeze timing. Those must be independently established
by the operator. No authentic comparator or fit receipt is fabricated or supplied
here. The existing `public_development_only` restriction and unqualified output
remain. This repair does not establish an executed native reference, protected
participant transport, direct interpretation, viewer interpretation or a complete
benchmark. Cross-person clinical electrode correspondence, neural extraction,
complete source admission and conditional null validity remain unresolved.

## Inputs and execution

Use an existing Python 3.10+ environment with NumPy. No installation, network
request or fitting is performed. Run from the repository root:

```sh
python3 benchmarks/neural/NEURAL-016/implementations/bound-nuisance-v1/evaluator.py \
  --protocol /operator/frozen-protocol.json \
  --private-targets /operator/private-targets.json \
  --operator-nuisance /operator/frozen-nuisance.json \
  --expected-nuisance-sha256 OPERATOR_CONFIGURED_64_CHARACTER_SHA256 \
  --candidate /operator/full-predictions.json \
  --output /operator/private-score.json
```

All example paths and the digest are placeholders. The protocol/private-target
schema is the [preserved evaluator schema](../../docs/initial-evaluator-v1.md),
with `recipe.primary_metric` fixed to `delta_r2` for the current contract.

The nuisance packet has exactly `schema_version: 1`, `task_id: "NEURAL-016"`,
`protocol_sha256`, `predictions` and `fit_provenance`. Each prediction is
`{row_id, nuisance}`; each fit item is
`{fold_id, fit_row_ids, recipe_sha256, nuisance_artifact_sha256}`. The byte digest
binds the complete packet, including every prediction, fold and artifact hash.

The candidate packet has exactly `schema_version: 1`, `task_id: "NEURAL-016"`,
`protocol_sha256`, `predictions`, `fit_provenance`, and `claimed_delta_r2`, with
optional `null_predictions`. Each prediction is `{row_id, full}`; each fit item
is `{fold_id, fit_row_ids, recipe_sha256, full_artifact_sha256}`. IDs must cover
exactly the frozen evaluation rows and folds. All numerical values must be finite;
booleans are not numeric predictions. Unknown fields, duplicate row IDs, missing
rows and JSON duplicate keys are rejected. Both packets use the same frozen
protocol/recipe and identical fitting row sets.

Optional refitted nulls retain the predecessor's fields `permutation_id`,
`control`, `refitted_recipe_sha256`, `shift_manifest_sha256`, `predictions` and
`fit_provenance`, but predictions and fits use the same full-only schema as the
candidate. The operator nuisance is injected unchanged for every null. Null
exchangeability remains unverified and the resulting rank remains descriptive.

Output retains private block scores and the original population/qualification
limits, plus `operator_nuisance_file_sha256`, `absolute_summary`, `claim_score`,
`full_prediction_statistic` and exact input-file hashes. It is operator-private,
not adaptive participant feedback. Successful output replaces the destination
atomically; invalid inputs leave an existing score untouched. File access
isolation is the operator's responsibility; this CLI is not a sandbox.

## Controls and provenance

`test_evaluator.py` contains generated software controls for the known SSE=4,
SST=20 oracle; a correct negative contrast; constant bias; unequal nested group
weights; nuisance substitution in predictions and fit metadata; independently
pinned malformed comparator data; missing/extra/duplicate full rows; ordering;
full-only nulls; strict JSON; and CLI hash rejection before target reads.
The fixtures are artificial and reuse the predecessor's explicitly generated
roster fixture. They are not neural data, native fits or empirical outcomes.

Use the project's shared lightweight test pool when active. The bounded command
inside that pool is:

```sh
python3 -I -B benchmarks/neural/NEURAL-016/implementations/bound-nuisance-v1/test_evaluator.py
```

All 11 generated controls passed in the reviewed two-slot pool on 2026-11-17.
The successful receipt SHA256 is
`71ab61c88086e3d6d75a07bda698850ae8818a65569eda00cdc2d67a40069e3c`;
the test log SHA256 is
`323807d796c5db643fb63702efc1c432ace77bbba7600a4b9399c428203f6589`.
Measured child CPU was 0.567451 seconds and maximum child RSS was 42,008,576
bytes. One earlier busy-pool attempt launched no test process. These are software
validation costs, not scientific execution or participant performance.

[SOURCE.json](SOURCE.json) pins the contract and unchanged predecessor used by
this implementation. The predecessor's source manifest preserves all original
source holds. The author release commit remains
`c54ba38eab7814538bc03b1b6d29a3f50f034e12`; it is background provenance, not a
newly executed or copied reference. No source payload was downloaded for this
component, and no genuine targets, models or candidate trials were accessed.
