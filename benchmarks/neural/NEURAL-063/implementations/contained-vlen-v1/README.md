# NEURAL-063 contained metadata preparation

This component prepares the original omission benchmark's plane metadata and complete-session support while keeping variable-length HDF5 decoding inside a separately qualified Linux container. It preserves the original scientific readers, session derivation, input identities and full cohort: 107 mice, 703 sessions, 1,936 planes and 133,066 ROI identities, with the 73/15/19 mouse split.

The package is source preparation. Its inactive templates do not authorize a run. A generated-control pass would qualify only the declared control path; it would not establish authentic cohort completion, Docker containment, deployment portability or benchmark readiness. Historical local results from an earlier source version do not qualify this version.

## Components

- `scientific_adapter.py` calls the immutable original readers and session derivation. Plane access uses the version-bound range reader; session access requires every original member and the authenticated plane artifacts.
- `worker.py` loads the exact source closure in the fixed container namespace. It authenticates the original selection wrapper before using its `original_selection` member. This worker is unchanged from the preceding implementation.
- `host_inventory.py` keeps the full plane/session inventory outside the worker's failure domain, reserves finite per-unit costs before admission and records complete, failed and unattempted dispositions.
- `fixed_export.py` exports only the fixed `plane_metadata.json` or `session_support.json` artifact. Binary copyout preserves byte identity, bounded writes and uncertain partials.
- `controller.py` implements the fixed plane/session lifecycle, export, cleanup and recovery routes. Runtime, helper, endpoint and host-location inputs are explicit and authenticated.
- `tests/` provides one portable generated-control entry, its plan builder, invented HDF5 fixtures and deterministic fake-engine controls.
- `DEPENDENCIES.json` records the immutable original/range closure and canonical dependency locations. The scientific source files are reused, not copied into this component.

## Scientific boundary

The plane route preserves `native.neural_metadata` and `native.presentations`, including complete `asstr()[:]` decoding followed by the existing 512-byte UTF-8 validation. An object/VLEN layout remains an unknown heap allocation; the later string check is not an allocation bound. The source proposes containment of that decode, not a new bounded HDF5 parser.

Session derivation uses the full authenticated original session and unchanged `derive_session`. A failed or missing plane holds its session and cohort. Valid zero-supported-event results remain distinct from source, budget, timeout, memory, export or cleanup failures. No missing member is relabelled as a scientific clock exclusion.

The session artifact is a transport envelope retaining the complete original schedule, support values and every plane input identity. The host treats scientific payload bytes as opaque. It does not parse clocks, presentation records or support values.

This preparation does not request or decode dF/F dataset values; authenticated range/cache blocks may incidentally contain adjacent signal bytes. It makes no model prediction or performance claim. The original all-source-column projection semantics remain unchanged in the reused pipeline.

## Generated controls

The maintained `neural063-range` runtime profile and the checked-in `tests/runtime-profile.ci.json` must agree. The entry checks the selected interpreter and exact source closure before scientific imports, then checks imported package versions and locations. A selected local runtime requires its own explicit profile; a previous macOS result is not evidence for Linux runtime equivalence. Generated CI declares Linux/x86_64. The separate actual container gate retains its Linux/arm64 image requirement, so generated CI does not imply actual x86_64-container support.

From the repository root, the maintained dispatcher can use:

```sh
"${PYTHON}" -I -B benchmarks/neural/NEURAL-063/implementations/contained-vlen-v1/tests/run_generated_ci.py \
  --component-root benchmarks/neural/NEURAL-063/implementations/contained-vlen-v1 \
  --range-source-root benchmarks/neural/NEURAL-063/implementations/versioned-range-v1 \
  --original-root benchmarks/neural/NEURAL-063/implementations/neural-063/complete-omission-v1 \
  --artifact-root "${ARTIFACT_DIR}" \
  --python "${PYTHON}" \
  --runtime-profile benchmarks/neural/NEURAL-063/implementations/contained-vlen-v1/tests/runtime-profile.ci.json
```

`${ARTIFACT_DIR}` must be a fresh, nonexistent directory beneath an ordinary existing parent. The entry creates it, publishes the bounded generated plan, and runs the controls in the same process. It does not install packages or invoke a second executor. The dispatcher supplies the declared runtime, 180-second timeout and one-thread environment.

There are six unittest methods. Five deterministic fake-engine graph cases run inside the first method; ten binary-copyout modes run inside the sixth. The positive scientific fixture path uses installed HDF5/NumPy libraries and the original functions. Mocked engine/authority cases are recorded separately from that library evidence. No generated control authorizes Docker, provider access, original arrays or an actual native lease.

The worker's 512 KiB cumulative saved-artifact allowance includes the plan-maker's requested writes, not merely the final plan size. Five invented HDF5 fixtures have a 128 KiB extent cap each and a 5 MiB aggregate in-memory HDF5 requested-write cap. A separate 4 MiB counter bounds serialized fake-file and inventory material; it does not cap Python's decoded heap. Interpreter authentication has a separate finite source-read ceiling. A selected execution proposal must state its exact interpreter/source reads and reserve its external supervisor log independently.

A JSON `controls` success marker is emitted only if all six methods pass. Failure remains nonzero and retains its bounded evidence. Static review or the presence of this command is not a test result.

## Actual-operation admission

All `templates/` files are inactive. Actual input, deployment, image, runtime, native lease and output identities are unresolved. The fixed scientific input digests remain in code to prevent substituting an equal-sized cohort.

Portability changes the host configuration, not its authority. The independent authority policy must be outside the operation's output/package roots and must be included in the independently approved native command/protocol. The controller joins its exact source and helper identities to the registered lease, approval, command, bounded ledger snapshots and live owner/process identities. A held lock or a supplied JSON receipt alone is insufficient.

The approved native protocol binds its authority descriptor, host/recovery mode, operation path and every operation field except `native.protocol`. Finalization is ordered: construct that payload, approve/hash the protocol, insert its descriptor into the operation, then bind the finalized operation hash in the exact native command. This avoids a hash cycle without leaving the operation's other fields unbound. Recovery binds its own payload.

Only a qualified local Unix Docker endpoint is accepted. The host launcher is typed, the interpreter and timer are pinned, and the fixed commands do not accept arbitrary executable arguments. Reused helper code is authenticated by its accepted source hash. Generated runtime plans cannot satisfy actual native admission. Actual host paths use a bounded ASCII/no-whitespace grammar so the qualified process inspection can reconstruct exact argv. The authority model assumes a cooperative same-UID operator; it does not claim to resist malicious modification by that same UID.

## Resource and recovery limits

The profile proposes a 1.75 GiB worker cgroup with equal memory/swap limits, 32 PIDs, nofile 1,024, one CPU thread and a 128 MiB tmpfs. These are requested deployment limits awaiting qualification, not an observed whole-system bound. Host memory, daemon/VM overhead and native runtime startup I/O remain separate. Host and container monotonic clocks have distinct epochs; only bounded durations cross that boundary.

Plane and session output caps are 32 MiB and 96 MiB. They are stop policies, not evidence that every original output fits. A complete authenticated layout bank and qualified deployment remain authentic prerequisites; this public package does not contain those original data.

The surviving inventory reserves request/body/header, scientific-read, export, worker-write, host-write, control and cleanup costs before each unit. Successful settlement requires the source-owned cumulative requested/confirmed counters and durable, identity-bound closure evidence. Retained file length alone cannot justify releasing a requested-write reservation. Unmeasured residual allowances remain charged. Unknown or partial failures retain their full reservation.

Ready publication, producer exit, export completion, container exit and removal are separate facts. A reaped Docker CLI does not establish container exit. Unknown control custody blocks later dispatch even if a container-absence snapshot succeeds. The recovery route consumes the exact durable intent and recorded container identity; actual hard-kill recovery and kernel enforcement require separate qualification.
