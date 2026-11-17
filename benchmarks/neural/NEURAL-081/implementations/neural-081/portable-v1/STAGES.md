# Finite stages and write domains

The enclosing input for every non-build stage has exactly `schema,stage,instance,run,payload`. Schema is `neural081_portable_stage_input_v1`; stage is one literal name below. Instance is the pinned generated BUILD_RESULT descriptor. Run is null for select-run and source-qualification binding/activation, or the actual P/RUN.json descriptor for run-dependent stages. The whole input must itself lie in a selected external operator namespace. Every record operand in a payload is a descriptor unless the table explicitly describes a nested object.

| Stage | Exact payload keys | Effect and prerequisites |
|---|---|---|
| select-run | input, selection | Admit complete input/execution metadata, publish P/RUN.json, immutable selected operands and role requests. |
| bind-environment | records | Admit independently supplied environment/source records, publish P/environment manifests/configuration/binding. |
| bind-channel | environment, registry | Join actual bound environment with independent authority registry/templates, publish P/controller and fresh P/channel request/response directories. |
| request-launch | controller | Admit complete controller configuration and publish original acyclic P/launch/REQUEST.json. |
| bind-launch | request, authority | Admit independently issued authority bound to that request; publish P/launch/ENVELOPE.json. |
| bind-route | current_registry, records | records is exactly receipt/qualification/source_binding descriptors; import their exact bytes into Q, run genuine qualification predicates, publish V generation/preimage/transaction. No J replacement. |
| activate-route | transaction | Authenticate the exact selected transaction/preimage, perform the sole J replacement; retain V intent/result and final source/metadata rechecks. |
| request-review | envelope, registry, declaration | Publish bounded R review payload and qualification request for independent review. |
| publish-review | payload, qualification | Admit independently supplied review qualification; publish final R review and P command approval request. |
| admit-approved-review | review, approval | Admit exact protected approval, produce a planned absolute invocation under P/commands; no process launch. |
| respond | intent, authority | Admit actual original phase intent and independent request-bound authority; publish only the source-owned exact response path. |

The source/run chain is select-run → bind-environment → bind-channel → request-launch → bind-launch. Route qualification/binding/activation is a separate source-metadata chain; a qualified selected registry is needed for review/command planning. Independent issuers supply their records between the corresponding request and binding stages. This is not a sequence that can run unattended with invented evidence.

S denotes the fresh source instance. Q=S/neural081/central/runtime-qualification; R=S/neural081/central/operator-selections; J=S/benchmarks/neuroscience/neural-081/manifest.json; V=S/neural081/registry-generations. These are explicit protected metadata exceptions inside S. Source/archive/build/profile bodies remain immutable. P is an external selected operator-root/portable-runs/<canonical-run-sha256> directory. Run metadata stays under P; raw, secret, protected assessment and result/output data namespaces remain separate. The task never loads an entire private WORK_ASSIGNMENTS history.

Activation has no automatic retry or rollback. All lock, staged generation, intent, preimage, result and failure metadata is in V; only selected J replacement occurs outside V. Held V/J-parent directory identities must be on the same filesystem. Both directories are fsynced after rename; only the verified J preimage-to-postimage read identity transitions. A stale transaction, changed generation, failed flush or uncertain final state refuses and requires independent inspection. Successful metadata activation still does not make assertions in external qualification records true.

## Registry template and actual invocation

For c equal to `default` or `full10_instructed_excerpt_v1`, the registry T(c) uses cwd `.` and this relative wrapper/whole-token placeholder argv:

```text
{python} -I -S -B -X pycache_prefix=ABS_INSTANCE/neural081/central/fresh-central-pycache
neural081/central/entry.py --condition c
--program {program} --output {output} --review {review}
--other-reserve-bytes {other_reserve_bytes}
--source-bytes EXACT_CENTRAL_MANIFEST_BYTES --source-sha256 EXACT_CENTRAL_MANIFEST_SHA256
```

T(c) is generated metadata, not a shell command. A(c), emitted by `admit-approved-review`, replaces the five entire placeholder tokens with the selected absolute Python/program/output/review and reserve string, replaces argv slot 6 with ABS_INSTANCE/neural081/central/entry.py, and sets cwd to ABS_INSTANCE. All other token order remains exact. The pycache path must satisfy the actual fresh/absent-path gate. The default and named route each need their own review/approval even though both cover complete support. The program operand is the admitted full-program envelope, not a generic per-row scoring function.

The actual central process checks its real original argv/interpreter and invokes the preserved complete parent path. Original observers, whole-program graph/target-last replay and independent original central exit/streams are required before scientific success. The constructor emits only a plan and cannot self-certify that future completion.
