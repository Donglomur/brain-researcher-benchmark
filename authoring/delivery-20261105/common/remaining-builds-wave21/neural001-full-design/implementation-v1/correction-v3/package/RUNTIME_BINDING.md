# Trusted deployment binding (currently absent)

This is a required implementation/qualification contract, not a mock accepted as
isolation proof. The source reviewer can inspect the composition without loading
authentic arrays, credentials or model states. A future separately selected
deployment supplies one operator-owned `binding` with the following interfaces.

1. `independent_admission.verify(receipt, receipt_pin, source_pin)` authenticates
   exact issuer/custody and every `protocol.GATES` evidence object. `guard` binds
   the same receipt/source and original origin/deadline before each operation.
   `admit_phase(request, request_pin, report)` joins actual namespace, data exposure,
   provider resets, frozen assets, method, complete resource usage, natural exit,
   streams and cleanup evidence. A candidate cannot issue these observations.
2. `configuration()` returns exact finite JSON, pinned by
   `receipt.environment_binding_pin`: resource_profile, storage, host, container,
   provider, documents, source_tools, replicate, instructions_pin and clock_domain. No credential
   value appears in it. `manifest()` returns24 immutable `protocol.Subject`s;
   `input_records()` returns the corresponding exact PacketStore descriptors.
   All aliases,94run/epoch support and query metadata join in `qualified_entry`.
3. `clock` must be the actual host `time.monotonic` callable, with declared
   clock_domain=`host_time_monotonic`, because the unchanged caller observer uses
   that absolute clock domain. The same callable is threaded into every phase; `sink.emit` and `journal` append bounded
   durable operator evidence, preserving failed attempts even if the worker dies.
   They never send protected audit identities or logs to the candidate/provider.
4. `monitor_factory(request,pin,context)` returns a monitor with `start`,
   `child_usage`, `reference_progress`, `finish` and `fail`. It independently
   combines parent, provider, native library, Docker daemon/container and nested
   process CPU/accelerator time, RAM/scratch/retention peaks, logical read/write,
   logs, source revisions and provider token/request usage. It joins PacketStore
   counter deltas and ArtifactStore meter events into the current phase and
   whole-program totals without omitting/double-counting shared preparation.
   Missing observations are unknown, not zero. `finish` returns exact usage/peaks,
   observation and admission fields. A local phase's wall cutoff also includes
   output capture and cleanup. HTTP/socket timeouts alone are not a whole-operation
   deadline proof; the outer original-clock supervisor must contain stalls.
5. `artifact_meter(event)` reserves every logical read/write/expanded event before
   the store operation, persists observed/failed facts and enforces the whole clock.
   `artifact_qualifier(request)` joins allowed role/audience/custody and live
   authority. Neither callback may claim that returningTrue proves a sandbox.
6. `custody` implements `admit_host_root`, `before_container`, `after_container`,
   `read_owned_output`, `bind_state_program`, `program_for_state` and
   `confirm_trained_state_unchanged`. It authenticates owner roots, safe descriptors,
   exact source and actual immutable mounts; a returned path is not sufficient.
   `after_container` supplies natural_zero, container_absent,
   all_nested_resources_closed, readonly_unchanged, complete usage/peaks and an
   evidence_pin. It must observe Docker daemon ownership and descendants outside
   the worker. The copied observer does not kill children or guarantee cleanup.
   `read_owned_output(path,cap,context,budget)` returns stable complete bounded
   ordinary-file bytes with no-follow custody and charges every read. State/program
   mappings are immutable and exact, and sealing returns explicitTrue. No access to unrelated services or processes.
7. `credential_capability()` yields only the selected provider token at request
   time. It remains operator-only, never hashed, logged, mounted or sent as model
   input. No provider calls were selected here. Provider selection pins HTTPS
   endpoint/model revision, seed behavior and observed token definitions, including
   explicit reasoning-token detail. Fresh requests have no hidden session reuse;
   the provider/reset mechanism needs independent evidence.
8. `method_reviewer` implements `admit_action`, `admit_submission`,
   `admit_frozen_training` and `admit_case_method` under the exact V2 broad
   computational rules and return explicitTrue on admission. False/None refuses. Diagnostics and novel synthesis are allowed; learned-state
   fitting and preprocessing changes after query access are forbidden. Numeric
   format and immutable mounts cannot universally distinguish arbitrary equivalent
   computations. Bounded conformance review and its residual limitation remain
   disclosed. Disclosed half-shift inversion/realignment is explicitly permitted;
   its score is robustness only and cannot establish absent neural information or
   alignment; never silently replace this treatment with finite-bank routing.
9. `protected_target_loader(person)` and `protected_group_loader()` are sealed
   protected-store capabilities, invoked only by captured `operators.grade_all`
   after all264 submission validations. They supply complete exact target support
   and the admitted24×120 identity grouping into70 groups. Their custody and
   authorized grading exposure need independent evidence. No target/private-key
   body was inspected for this source delivery. `reference_progress` is an
   operator-only progress capability; actual per-phase progress goes to its monitor.

The resource_profile schema is exact in `runtime._profile`: origin, deadline,
whole, person_candidate, person_reference, phase, prelaunch_usage, prelaunch_peaks
and prelaunch_evidence_pin. Every budget has complete `resources.ADDITIVE` and
`PEAK` fields. All eight actor/operation phase ceilings are supplied. No number is
silently defaulted to legacy1200s or to an assumed zero. Complete authoring,
training investigation, current-case work, failed attempts, repeated reads and
all permitted ensemble/diagnostic work count. `phase_budget` known observations
are lower bounds that the external monitor cannot erase.

The storage configuration supplies packet_root, artifact_root, execution_root,
packet_logical_limits, role_caps, metadata_cap, expanded_cap and max_audit_events.
The packet limits name source_read_limit, expanded_limit, materialized_limit and
serialized_limit. Role caps include every produced role from runtime plus `model`
for the sanitized R0 prior. Host profile includes artifact_bytes, model_state_bytes,
expanded_model_state_bytes, tool_feedback_byte_cap and max_investigation_steps.
These bounds must fit complete original support; refusal requires requalification,
not cropping, dropping a person/run, lowering rank or changing the endpoint.

The container profile pins docker_executable, image digest, python_executable,
non-root uid/gid, cpus, memory_bytes, pids, tmpfs_bytes, cleanup_seconds,
host_environment and host_cwd. Native packages, BLAS behavior, architecture and
threads need exact qualified image evidence; NumPy2.2.6 is required by full
reference training and uncertainty. Dependencies are not installed here. Only the
three source tools are mounted under /tools: candidate_reference_tool.py from this
package, reference_engine.py from reference/, and reference_bundle_codec.py from
reference/artifact-store-v1/artifact_store.py. R1/R2 frozen states and the sanitized
R0 scalar are supplied separately according to arm. Exact public source/documents,
container image and complete environment exposure must be audited for answers,
aliases, data paths, credentials and public-source shortcuts before admission.

The whole caller must close naturally with exact final outputs and EOF under its
original clock. `StudyRuntime` returns only a provisional result pending that
outside admission. Source completeness, code correctness controls and a signed
qualification receipt do not themselves establish scientific performance or a
submission-ready benchmark.

V3 host artifact access uses min(host artifact_bytes, role_caps[role]) and rejects
a handle that exceeds either bound before path/body access. Small program/method
ceilings need not equal the largest model-state ceiling. Qualification must still
admit complete original objects and all repeated read/materialization costs.
