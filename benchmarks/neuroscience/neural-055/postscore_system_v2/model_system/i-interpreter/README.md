# Fixed THINGS-EEG2 investigator

`renderer.render_i_program(loop_spec, participant_interface)` returns exactly
`source_bytes`, `source_sha256`, and `I_policy_fragment`. It emits one standalone
I.py with no project-relative runtime dependency. The existing actor mounts the
original broker client and the exact acknowledged public interface. The common
policy and independent method review remain the parent's responsibility.

The emitted program implements the existing literal FIT/INFER commands. It
validates the full cell, public source pins, source commitment and broker lease.
It uses the existing `Broker.request`, so global and shared FIT+INFER call/token
accounting remains with the original host. Unknown/unavailable provider replies
abort. Only successful malformed text can consume an explicitly selected parser
repair slot. Analysis failure also aborts; this version does not silently repair
or retry scientific analysis.

## Explicit spec

`schema` is `neural055-fixed-i-loop-v1`. Every following field is mandatory:

- `model_provider`, `tool_provider` (explicit null for no tool), `fit_prompt`,
  `infer_prompt`, `max_new_tokens`, `phase_steps` with positive FIT/INFER counts,
  `malformed_repair_slots` (per phase), `dependencies`, and
  `row_sum_abs_tolerance`.
- `limits` contains `context_bytes`, `decision_bytes`, `analysis_source_bytes`,
  `analysis_seconds`, `closure_seconds`, `stream_bytes`, `workspace_bytes`,
  `workspace_files`, `artifact_bytes`, `seal_bytes`, `seal_header_bytes`,
  `state_count`, and `sealed_action_count`.

Prompts, model identity, method, dependencies and limits have no production
defaults. The accompanying `INERT_LOOP_SPEC.json` is a metadata-only engineering
fixture, not a proposed production selection. It must never be used to claim
model or scientific qualification.

## Actual loop and analysis interface

The local text model returns one strict JSON decision, without code fences:

- FIT: `{"kind":"analysis","source":"..."}`, a tool decision, or
  `{"kind":"finish_fit"}`.
- INFER: `{"kind":"sealed_analysis","action":"NAME"}`, a tool decision,
  or `{"kind":"finish_infer"}`.
- Tool: `{"kind":"tool","operation":"OP","payload":{...}}`.

Only the original phase-specific R2 operations are accepted. Numeric envelopes
are checked before decoding: exact dtype, geometry, byte/base64 extents and
finite values. Full numeric tool results stay in bounded scratch, available to
analysis; model dialogue receives their actual pins/geometries or the permitted
development report. This does not claim the LLM itself consumed every original
signal sample.

Analysis runs with fixed argv:

`python -I -B analysis.py --request REQUEST.json --result RESULT.json`

`REQUEST.json` has schema `neural055-i-analysis-request-v1`, `phase`, `cell`,
original `input` path, prior typed `state`, actual tool-result file descriptors,
the inherited `original_work_deadline`, `no_query_fit`, and a fresh `artifact_root`.
The model receives this ABI in its first bounded observation, alongside the
explicitly selected prompt.

FIT analysis writes a `neural055-i-fit-analysis-v1` result with exactly
`observation`, `state`, `inference_actions`, `selected_method`, and `context`.
State is a finite list of `{name,dtype,shape,path}` with path exactly
`artifacts/NAME.raw`. Supported finite C-order raw types are `<f8`, `<f4`, `<i8`,
`<i4`, `<u8`, `<u4`, and `|u1`; there is no object codec or pickle. Inference
actions are a nonempty list of `{name,source}`. Method fields are the unchanged
selected-method-v2 contract and describe actual work; they are not approval.
All needed fitted quantities and context must be in this result.

`finish_fit` seals the last successful actual analysis, including method,
fixed action sources, typed arrays and training context. The binary format is
magic, a little-endian uint64 JSON-header length, bounded strict JSON metadata,
then exact contiguous raw payloads with shapes, extents and SHA-256 pins. It is
streamed, and rejects extra/truncated/nonfinite/mismatched bodies. The complete
model remains under the original 268435456-byte cap and the explicit smaller
selected cap, if any.

INFER starts from a fresh process and that same-cell source/spec-bound seal.
It can select only the frozen action map and declared FIT broker pairs.
Every action produces `neural055-i-infer-analysis-v1` with `observation` and
literal `prediction:"artifacts/prediction.json"`. The unchanged mounted public
validator admits the actual complete 200x200 prediction and bijection. No
normalization, repaired assignment, fallback or dropped case is performed.
Extracted state is rechecked after inference analysis. Sealed source does not
independently prove an absence of prohibited query-dependent learning; source
and operation semantics still require the existing independent review.

## Process custody and limits

The real analysis executor captures both streams concurrently, uses the
original remaining deadline, enforces a per-file OS extent limit, checks the
whole scratch namespace against selected byte/file limits, waits/reaps the
child and preserves the first failure. It uses a concrete Linux actor observer:
production requires PID1 and uid65534 in the original actor, begins with no
other actor processes, and uses same-cgroup membership plus pidfd signals to
retire escaped process-group children before continuing. Unknown closure or
leftover children refuses completion. It cannot be used as an ambient host PID
killer. The unchanged outer host/cgroup still provides primary containment and
hard scratch capacity. Periodic per-analysis workspace scanning is an observed
limit, not a claim of instantaneous aggregate filesystem quota enforcement.

Generated analysis has the actor's existing privileges and declared libraries;
the interpreter is not a separate security sandbox. All native isolation and
process visibility semantics remain unqualified until genuine Linux/runtime
evidence exists. Local engineered controls explicitly substitute the Linux
observer and science/model leaves where stated; they do not establish those
claims.

The output namespace remains exactly model.bin/selected_method.json/operations.json
for FIT and prediction.json/operations.json for INFER. Operations retain model
text, actual code/result identities and process failures. They are participant
claims, not authoritative cost/score records. Original host observations remain
authoritative. A publication failure leaves nonzero execution and available
partial evidence; no success record is fabricated.
