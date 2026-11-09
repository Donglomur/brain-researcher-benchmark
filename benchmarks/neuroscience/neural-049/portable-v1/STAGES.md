# NEURAL-049 constructor stages

Use the selected constructor's exact bytes and externally pinned metadata inputs. This guide describes static interfaces; no command below is a claim that recordings, qualifications, providers, interpreters, or execution environments are available. Commands are assembled for a real selected operation only after its missing inputs and independent approvals exist.

## Command interface

There are **17** CLI actions: `build`, `bind-route`, `activate-route`, and the 14 metadata actions listed below. A command starts with the operator-selected interpreter and the constructor source path. If isolation flags are used, preserve their actual selected interpreter semantics; the constructor itself does not authenticate its launcher.

Every action requires:

`--deadline-monotonic FLOAT --read-cap-bytes INT --write-cap-bytes INT --live-cap-bytes INT`.

Every action except build also requires `--origin-monotonic FLOAT`. Build may accept that flag too; when omitted only build samples its construction origin. Subsequent run stages inherit the selected original origin and cannot extend the run clock.

Build additionally requires:

`--release PATH --release-bytes INT --release-sha256 SHA --profile PATH --profile-bytes INT --profile-sha256 SHA --public-root PATH --root PATH`.

The other 16 actions require:

`--instance PATH --instance-bytes INT --instance-sha256 SHA --input PATH --input-bytes INT --input-sha256 SHA`.

Here `--instance` is the exact `BUILD_RESULT.json` descriptor, and `--input` is the selected action input. This is a flag inventory, not a runnable authority template. Caps, clocks, roots, actual byte lengths and hashes must come from the genuine selected operation.

The returned CLI envelope is bounded to 65,536 bytes. It reports costs and `own_future_exit_not_self_certified=true`; observing that envelope is not observing the process's final exit. The constructor returns failure on later close/clock/output problems and does not automatically retry.

## Build and route actions

`build` consumes the full build profile described in `OPERATOR_RECORDS.md`, the pinned release, the exact origin map, nine portable sources and all 137 original public prerequisite files. All 27 requirements remain missing in the source-only instance. Use its exact build descriptor and current registry-state descriptor in later calls.

`bind-route` input has exactly:

`schema, registry_state, name, routes, evidence`, with schema `neural049_portable_bind_route_v1`.

`routes` is exactly `default, named, grade`. Default and named need the original verification record fields `status, receipt_path, receipt_sha256, qualification_path, qualification_sha256, source_binding_path, source_binding_sha256`, with genuine passed evidence. `grade` is null or exactly `{program, scoring}`; scoring is exactly `{status, receipt_path, receipt_sha256}` and has its own genuine terminal/freeze join. Evidence is a map of 1–32 named JSON files to externally selected absolute descriptors outside the instance. Route references name their exact direct Q copies. No caller-supplied status substitutes for independent qualification.

The action copies exact evidence, evaluates the original route predicates and prepares `V/<name>-registry.json` plus `V/<name>-transaction.json`; it does not replace J.

`activate-route` input is exactly `{schema, registry_state, transaction}`, schema `neural049_portable_activate_route_v1`. It binds the earlier state and transaction, reruns route checks, requires a same-device V/J-parent publication domain, owns `V/ACTIVATION.lock`, and publishes the new J with explicit generation/state/activation/closure evidence. An active or abandoned lock requires separate inspection. Failures may occur after J changes; preserve all observations and do not repeat activation automatically. Scientific qualification remains false; route qualification is a separate property.

## Shared wrapper for the 14 metadata stages

The wrapper fields are exactly:

`schema, action, registry_state, name, parameters`.

The schema is `neural049_portable_stage_input_v1`; action must equal the selected CLI action. The wrapper is a pinned sealed JSON file beneath P. `registry_state` is the explicit current immutable state descriptor. `name` is 1–64 ASCII letters, digits, underscores or hyphens; unlike build/route tokens, a stage token may start with an underscore or hyphen. The owned stage leaf `P/<action>--<name>` must be fresh.

The table gives **all and only** the parameter keys. Except `payload`, `selection`, `launcher`, and explicit proof maps, values are exact existing metadata descriptors. The special null bank proof is defined below. Outputs are descriptors to sealed artifacts, not duplicated full bodies.

| Action | Exact parameter keys | Principal output / admission boundary |
|---|---|---|
| `select-run` | `profile` | `RUN.json`; selected-not-qualified full run or honest unresolved plan. |
| `request-prepare` | `run, payload` | `REQUEST.json`, `QUALIFICATION_REQUESTS.json`; all ten preparation proof requests. |
| `bind-prepare` | `request, qualifications, launcher` | The fresh direct P preparation authority, `WORKER_REQUEST.json`, `COMMAND.json`; requires all ten real proofs. |
| `request-bank` | `run, payload, preparation_completion` | Bank request and proof request, joined to genuine complete preparation. |
| `bind-bank` | `request, qualification, launcher` | Bank authority, worker request, command; real build qualification required. |
| `request-execution` | `run, payload, preparation_completion, bank_completion, bank_qualification` | First pass: only bank prequalification request. Second: complete execution/general-gate requests. |
| `bind-execution` | `request, qualifications` | `AUTHORITY.json`; full 20-key gate map, with only the defined optional dispositions. |
| `request-review` | `run, authority, selection` | `REQUEST.json`, `REVIEW_PLAN.json`; full central selection, no approval verdict. |
| `bind-request` | `request, approval` | `REQUEST_BUNDLE.json`, `QUALIFICATION_NEXT_STEP.json`; authentic external request approval. |
| `bind-review` | `review_plan, request_bundle, qualification` | Final R review at the selected slot, `APPROVAL_REQUEST.json`; genuine central qualification. |
| `admit-approved-review` | `review, approval_registry` | `COMMAND.json`; 1–32-entry independently issued approval registry, exact one-match admission. |
| `bind-collection-completion` | `run, authority, collection, completion` | `COLLECTION_BUNDLE.json`; actual collection plus separately observed process closure. |
| `request-late-grade` | `run, authority, collection_bundle, payload` | Late-grade request; already completed collection and genuine outer closure required. |
| `bind-late-grade` | `request, declaration` | `DECLARATION_BUNDLE.json`; independently issued exact declaration, not private scoring. |

Every action rechecks the current registry identity and time before publishing `STAGE_RESULT.json`; after publication it checks time before returning. There is no additional post-publication registry read in this stage handler. An unresolved request action instead emits `PLAN.json` and no admissible authority/payload identity. The fresh stage leaf may remain after refusal. A later successful-looking file does not override an actual failed process.

## Preparation and bank launch records

For prepare, `qualifications` maps exactly the ten names in `OPERATOR_RECORDS.md` to their independent proof descriptors under P. Preparation proofs and their evidence/completion descriptors use the original relative-to-P grammar. The complete source-closure and memory-profile metadata must already exist there. The prepared authority preserves the fixed roster and geometry contracts.

For bank build, `qualification` is an external operator proof with exactly `qualified, realm, selection, source_manifest, issuer, evidence, backend, exclusive_namespace, source_completion, full_resource_plan, external_observer`. The five findings must be genuinely established. There is no bank-build proof schema field in this exact original record.

Both bind stages take a literal `launcher={python, context, operation_live_bytes}` equal to the run's earlier observer selection. The emitted command has schema `neural049_portable_stage_command_v1` and fields `schema, instance, operation, argv, cwd, launcher, request, context, status, own_future_exit_not_self_certified`. It is `bound_external_launch_required`, not executed.

The emitted argv is the selected absolute Python, `-I -S -B`, the instance's `shared/stage_launcher.py`, then flags in this order:

`--operation prepare|bank --parent-root PATH --source-bytes INT --source-sha256 SHA --bootstrap-bytes INT --bootstrap-sha256 SHA --request PATH --request-bytes INT --request-sha256 SHA --context-json JSON`.

Only the separate launcher can enter the original producer. Its exact source, bootstrap, full parent manifest, request, context, actual environment and external observer must be selected and authenticated first. Original producer return values do not certify the enclosing process's future natural exit.

## Two execution-request passes

Start both passes from the same full base execution payload with a fixed proof path and `bank.qualification.pin=null`; all packet/store/kernel operands must already be authentic and complete. First use `bank_qualification=null` and a fresh stage name. The result is `BANK_QUALIFICATION_REQUEST.json` only. It cannot be passed to `bind-execution`.

After independent bank-consumption qualification, use a new stage name and supply its absolute descriptor as `bank_qualification`. Do not mutate the first request or insert a speculative proof hash. The code verifies that attaching the actual proof leaves the bank-domain selection unchanged, then forms the full main execution selection. General proof evidence paths are relative to `roots.operator`; the portable proof descriptors themselves are absolute.

## Central review, approval, collection and late grading

`request-review.selection` is exactly `operation, condition, output, review_slot, central_observation_deadline, central_validation_deadline, limits, other_reserve_bytes, collection, collection_completion, grading_selection`.

- Collect selects `operation="collect"` and condition null or the fixed profile. The three collection/grade fields are null; future completion placeholders are forbidden.
- Grade selects `operation="grade"`, condition null, and the actual completed collection, external completion and late-grade declaration.
- Output is outside the instance and every parent run root. The review slot is a fresh named direct JSON child of R.
- `readback_end < central_observation_deadline < central_validation_deadline`; those later observation bounds never extend parent work.
- Limits contain exactly `read_bytes, write_bytes, host_memory_bytes, parent_retained_storage_bytes, free_floor_bytes, qualification_read_bytes, validation_read_bytes, validation_cpu_ns, validation_numeric`. The final map is exactly `allocation_bytes, elements, serialized_bytes, files, work`. These are selected limits, not demonstrated feasibility.

The request and review project the three portable clock fields to finite floats before hashing. The original parent clock is separately retained. The request's issuer approval binds that exact request and source freeze. The central qualification binds the full review with its request/approval pair, excluding only the qualification field; all eight selected central findings need actual independent support.

`bind-review` writes only the selected R slot. Final approval is separately issued in `R/APPROVAL_REGISTRY.json`; each entry binds review, request, current registry, actual argv, cwd, environment pin, approval and evidence. An independently issued evidence-set record binds the entire 1–32-entry list. `admit-approved-review` emits an external-launch command after these joins; it does not run it.

A collection result must be the exact central `RESULT.json` for the same sources/authority/modules/cache/origin and must explicitly report no private grading. Its separate `neural049_external_central_completion_v1` must witness natural exit zero and complete streams after central return, join the exact intent argv/cwd/review, and complete before the original readback deadline. `bind-collection-completion` never converts a returned result into its own completion evidence.

Late grading preserves that completed collection, nested caller and independent original outer-completion witness. `request-late-grade` checks these already-existing facts and the exact original selection/observation; `bind-late-grade` requires an independently issued declaration identical to the requested payload. A separate grade review/approval is still needed. Final external scoring completion remains a distinct obligation. No constructor action reads protected target arrays or awards a scientific result.

## Failure and applicability

All inputs, selected roots, source versions, clocks, resource settings and publication names must remain fixed for the selected operation. Preserve partial outputs, failed captures, costs, lock state and uncertain cleanup. There is no automatic retry, replacement of missing evidence, or retroactive qualification. A newly chosen clock or budget is a new selection, not a repair to already-issued identity bytes.

The schema index is a static field/constraint index, not a runtime validator or a successful example profile. Original nested numerical/resource/source contracts remain authoritative. These documents establish neither installed dependency compatibility nor physical isolation, actual source admission, reference competence, provider readiness, completed operation, or full scientific qualification.
