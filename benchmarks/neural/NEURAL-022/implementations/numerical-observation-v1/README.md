# Complete numerical observations for NEURAL-022

This component exports the complete existing active-to-passive velocity panel as numerical text and collects its complete prediction table. It supplies **141 labeled active trials and all 92 queries**, each containing **six consecutive 20 ms bins × 65 units**. It preserves 90,870 nonnegative integer spike counts, 282 training velocity values, every opaque identity, commanded direction and allowed query mode. These are retrospective binned counts, not raw waveforms, within-bin spike times or learned features.

The new route is intended for **direct numerical interpretation without arbitrary analysis tools**. It supplies neither a typed viewer nor a model/provider interface. Export and collection working correctly do not prove that a model received the full panel, followed the training-only policy or used neural information. Canonical access statuses remain unchanged. No authentic preparation, native execution, provider/model call, score or scientific result is added by this source component.

## Source and preparation boundary

Runtime dependencies are three unchanged public modules from `artifact-grading/private/vendor`: `candidate.py`, `io_support.py` and `packet.py`. They are captured, hash-checked and executed from those captured bytes rather than imported through a source/bytecode cache. `SOURCE.json` binds this component's executing source, instructions, dependency manifest and verbatim `ORIGINAL_TASK.md`. The operator supplies the exact selected source-manifest hash. A stable operator-controlled checkout and ordinary Python/NumPy installation remain prerequisites; this is not protection against an adversary changing the executing launcher or its Python installation.

`DEPENDENCIES.json` pins the complete existing packet producer from commit `9889c058`, including its source manifest, original finite contract and public task. That producer is not imported or copied wholesale. Its future authenticated preparation must still run under its own original protocol, historical costs and closure requirements. This exporter consumes its `PACKET.json` and only four public files:

| Public file | Contents |
|---|---|
| `training.npz` | All 141 active IDs, counts, labeled velocity and directions; no source-row metadata. |
| `queries.npz` | All 92 query IDs, counts, modes and directions; no velocities. |
| `cases.json` | The same complete query roster in required order. |
| `TASK.md` | The original public programme contract, including historical reference summaries. |

The exporter authenticates the operator-selected packet-manifest hash, source identities, complete projection-closure declaration and every public-file hash before decoding. It validates the complete arrays and context against the existing public contract. The operator metadata also describes `reference.private.npz` and the projection receipt, but this component never constructs, stats, hashes, opens or mounts either private operand. No directory walk is used. The declarations in `PACKET.json` are not independently observed native custody: truthful source/input/closure provenance depends on the existing producer and externally authenticated operator records.

Only `OBSERVATION.json` goes to a participant. `EXPORT.json`, source/input commitments, private descriptors and operator paths stay outside the participant channel. The original task is retained as source provenance; programme execution instructions are excluded from the participant observation. The numerical instructions replace them, followed by the unchanged original scientific-contract excerpt containing the score, all public historical reference scalars and exposure limitations. No newly measured score feedback is supplied.

## Complete observation and collection

The observation is one deterministic UTF-8 JSON panel. For each trial, `counts[bin][unit]` has shape 6 × 65. The outer axis advances through `[0,20), …, [100,120)` ms relative to retrospective movement onset; the inner axis retains all 65 source-unit positions. No normalization, filtering, smoothing, interpolation, lag, unit selection or summary is introduced. JSON integer serialization preserves the full nonnegative int64 range without converting counts to floating point. Training velocities round-trip as their original finite float64 values, including signed zero.

All training examples and queries retain their original order. There is no selected demonstration subset or per-query retrieval. The complete query batch is visible, as in the programme condition; fitting, selection and normalization must still use active training only. Query-dependent fitting/transduction is prohibited but cannot be certified by output validation or by a successful export.

The response uses the original `neural022_predictions_v1` schema: exactly 92 ordered objects containing `id` and a finite, nonboolean two-component `velocity`. Missing, extra, duplicate or reordered cases are rejected by the unchanged canonical validator. The collector verifies the externally selected export and response hashes, authenticates the complete observation, validates the full response, and writes the response bytes unchanged to `predictions.json`. It emits the original committed-artifact `submission.json` with `schema_version`, `task_id` and the `{path,bytes,sha256}` file descriptor. No private grader is imported or dispatched here.

The original artifact grader can consume that manifest once its existing operator packet is provisioned. Its legacy `candidate_identity: candidate_program` field is unchanged; it does not establish that the response was generated by code. `COLLECTION.json` separately records this numerical condition and explicitly leaves provider-session, no-tools-boundary and training-only-method verification false. External delivery evidence must identify the actual model, complete delivered bytes, tool configuration, context handling, response, resets, budgets and exposure before a capability comparison is reported.

## Commands and limits

Run from the repository root in an existing NumPy environment. Each output directory must be new, with an existing parent:

```text
python3 -I -B benchmarks/neural/NEURAL-022/implementations/numerical-observation-v1/observation.py --source-sha256 SOURCE_SHA256 export --packet PREPARED_PACKET --packet-sha256 PACKET_SHA256 --output FRESH_EXPORT
python3 -I -B benchmarks/neural/NEURAL-022/implementations/numerical-observation-v1/observation.py --source-sha256 SOURCE_SHA256 collect --export FRESH_EXPORT --export-sha256 EXPORT_SHA256 --response RESPONSE.json --response-sha256 RESPONSE_SHA256 --output FRESH_COLLECTION
```

The hashes are explicit operator-selected commitments, not assertions supplied by the participant. `SOURCE_SHA256` selects this component's `SOURCE.json`; `PACKET_SHA256` selects the producer's `PACKET.json`; `EXPORT_SHA256` selects the returned `EXPORT.json`; the response hash binds the externally captured response. Keep those records outside participant control.

The complete observation has a 2 MiB UTF-8 byte cap. At the maximum nonnegative int64 value, the 90,870 count tokens occupy at most 1,817,400 bytes including one separator per count, before axes, context and instructions. Generated full-panel worst-integer controls verify that the actual complete representation fits the cap. This is not a measurement of authentic counts or model tokens. A panel can still exceed a provider's context limit. Before any model run, freeze and verify complete delivery, exact tokenizer/context capacity, all model and output limits, no-tools configuration and cumulative cost; refuse incompatible contexts instead of truncating, summarizing, choosing a few examples or silently changing conditions.

Prepared public arrays remain bounded by the original caps (524,288 B training, 393,216 B queries and 16,384 B each for cases/task). The response cap is unchanged at 65,536 B. Collection needs no original array files after export. Fresh output files are exclusive and read-only after writing; partial files remain if a write fails. The final record is written last, but a retained file alone never proves successful process exit or external provider delivery. There is no retry, resource supervisor, arbitrary-program sandbox or failure-recovery qualification in this component. Future preparation and execution require the existing shared supervisor, current cumulative reservations and 60 GiB free-disk policy; no legacy budget is reset or transferred by these commands.

## Scientific scope and controls

The target is mean nominal two-axis hand velocity over the same retrospective 120 ms window, averaging 120 native 1,000 Hz samples with the original raw × 0.01 + 0 m/s convention. The unchanged primary loss is trial-weighted squared Euclidean velocity error over all 40 passive queries. Keep the 52 active secondary queries, all 16 mode/direction strata and all seven signed comparisons. The fixed passive-neural/direction/mean references use 131 additional passive calibration labels; they are privileged comparisons. Active direction, active mean and zero controls do not use neural counts, so beating only a weak baseline does not isolate neural-information use.

This is an exposed Han animal/session, with behavior-derived timing, public historical reference results and unresolved kinematic overlap. It is not unseen-animal generalization, online prediction, causal sensory-coding evidence, reproduction of the original whole-arm paper or a SOTA claim. Shared cases and nominal count information make the conditions comparable in scope; different presentation, calibration, memory and compute prevent interpreting their score difference as an isolated causal effect of tools.

Generated controls exercise the complete panel, exact bin/unit order and count/float preservation; full int64 text capacity; no private-file access or descriptor release; malformed/changed inputs; complete ordered answer collection; original artifact manifest compatibility; source and output bindings; and source-byte loading despite poisoned cached module names. They use invented arrays and no authentic data, provider, model or native runtime. The command is:

```text
python3 -I -B benchmarks/neural/NEURAL-022/implementations/numerical-observation-v1/test_observation.py
```
