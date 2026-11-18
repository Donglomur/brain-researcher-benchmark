# Fresh runtime program and state/custody adapter

These additive sources construct the first runtime control and validate its fresh original evidence. They do not launch Docker, authorize execution, or update historical qualification. The parent driver, guard, resource protocol and launcher remain separate dependencies. The module starts no explicit I/O or live-adapter actions when imported; Python/runtime initialization is outside that claim.

`qualification_cases_v3.programs(canary_path, socket_path, *, probe_source)` returns the existing six names in their original order. It requires the exact 20,443-byte probe with SHA-256 `f513ed96f8598d5693fa2dc4e2589d18bc5b92f14ea6d88be7f58311e76f3848`. The five other program byte strings are unchanged from `qualification_cases_v2.py` (`19375aad81bc5f214a1bd8b91917d151d9bb887ddeec77ee66adbd400a29693b`). The full `validate_normal` function is also retained verbatim. The driver uses it only for the other normal controls.

The new runtime program retains the old UID/GID, environment, executable/cwd, Python/NumPy, numerical-thread, mounted-file, default-IPv4-route and numeric TEST-NET connectivity observations. It also retains namespace-interface and bounded sysfs observations. It captures that runtime object, executes the exact embedded probe in the **same candidate process/container**, and emits one canonical `dosei_fresh_runtime_observation_v1` envelope. The host never executes the candidate program. The embedded source is trusted, fixed source; this is not an arbitrary participant-code execution path.

The envelope binds the mounted generated observation, the SHA-256 of the complete mounted composite program, and the separate embedded-probe SHA-256. Hashing the program creates no self-hash cycle: its digest is an output field, not an embedded source literal. The whole original attach output has its own independent raw binding. Canonical nested-state and reparsed-state hashes in the adapter receipt are explicitly **derived** hashes, not claims about separately captured files.

The runtime component is capped at 16,384 bytes including its canonical newline; the probe component at 262,144 bytes; the combined envelope at 524,288 bytes. Source plus all generated staging remains within 65,536 bytes. One 20-second candidate alarm and the existing CPU soft/hard 2/3-second limits cover the combined program. The host must enforce the exact 512 KiB runtime attach cap and complete EOF; the backend's original requested cap remains separately recorded. The flood control still needs its unchanged 2 MiB effective cap. Candidate limits are not whole-host/daemon/VM resource guarantees.

## Original-body API

```
derive_runtime_state(originals, *, profile_bytes, probe_source, authority, modules)
bind_context_close(provisional, close_bytes, *, expected_call_bindings)
```

`originals` is an exact mapping of the first 27 original evidence names to immutable bytes. `ORIGINAL_NAMES` exports the ordered roster, positions 0000 through 0026: all eight command intents, eight original command output prefixes, eight command receipts, setup, complete program source and runtime call. Source position 0004 and original attach position 0012 are included, unlike the historical metadata-only adapter. Context close is supplied separately after all four calls.

`Authority` has fields `protocol_sha256`, `context_id`, `worker_pid`, `output_directory`, `python_executable`, `cli_shim_path`, `docker_executable`, `docker_socket`, `canary_path`, `program_sha256`, `original_bindings`, and `module_source_sha256`. `original_bindings` is an exact tuple of `(name, byte_count, sha256)` rows selected from confirmed trusted-store entries. `modules` contains exactly `docker_policy`, `network_policy`, `owned`, `probe`, and `cases`; `MODULE_PINS` fixes their source pins.

The trusted loader authenticates all module bytes, protocol/worker identity and original custody before injection. A namedtuple, matching strings or a self-consistent fabricated transcript do not authenticate a caller. This pure adapter does not read the resource ledger or establish root admission.

The adapter recomputes the complete composite source from the selected paths and exact probe bytes. It validates the eight-command order and CPU-shim/Docker prefix, exact staged mounts, immutable image, policy-generated create arguments, the full created container ID, initial/final/ownership inspections, first call/source/output receipts, removal output and exact-ID absence. Each CLI must have successful bounded EOF accounting and complete owned-process closure, including leader reap and observed group absence. Strict integer checks supplement the unchanged Docker policy's scalar equality checks. No name/suffix-only role attribution is used.

Only the exact original UTF-8/canonical attach bytes are parsed, not the backend's replacement-decoded text. `validate_runtime_component` keeps the old non-network runtime checks while replacing the literal `['lo']` criterion with bounded interface-name observations that must join the fresh parsed link dump. It does not qualify the runtime by itself.

Three audited pure helpers are copied exactly from saved checker `c3e02250bc92a2387344683b10e84994e7add4961c0ee99bc545c877abae64f2`: `exact_counters`, `verify_cli_closure`, and `reparse_saved_frames`. Their source spans and block hashes are in the provenance. The external checker's `Context` and entrypoint are not imported. Reconstructed datagrams must cover all retained frames and agree with their byte counts/hashes, exact requests, sequence/port/kernel identity, attributes, parsed records and counters. The pinned probe receives only fake socket/clock adapters for this host-side reparse. It is not a second kernel observation and does not remeasure actual collection timing. Only retained selected `/proc/self/status` lines can be reparsed; the unretained complete original body is not rehashed.

After those custody and parser checks, the adapter calls only the immutable `network_state_policy_v1.state_condition` function on the fresh state view. It never calls historical `evaluate`, synthesizes a historical verified-proof schema, or imports an old observation as fresh authority. This uses the selected state condition: flagged loopback and down non-loopback links, loopback-only supported addresses/routes, supported attribute descriptors, zero capability masks, NNP 1 and Seccomp 2. Firewall/policy-rule contents, filter contents, cross-namespace state, atomicity and future hostile behavior remain outside the claim. Priority/cache/preference route payload values remain unparsed as documented by the unchanged predicate.

## Provisional and final closure

The first result has schema `dosei_fresh_runtime_state_v1`, status `provisional_runtime_evidence`, `context_closure_pending=true`, and `runtime_control_confirmed=false`, even when the necessary condition matches. The parent must not increment a confirmed control count at this point. Invalid/incomplete source, custody or parser evidence raises; a valid state that does not match the selected condition returns a bounded refusal reason and remains unqualified.

After the shared first context's four calls, `bind_context_close` requires its original successful, non-poisoned, unresolved-object-free close and four distinct detached call bindings in exact order. The first must equal the original runtime call. The final status is `fresh_runtime_context_closed`; only a matched necessary condition then permits `runtime_control_confirmed=true`. A valid semantic nonmatch stays false. `network_qualified` and `complete_six_control_qualification` remain false in this component: the parent separately owns all six controls and aggregate qualification.

The trusted parent retains the exact provisional record and supplies the independently checked complete call roster. The second phase checks those binding/closure joins; typed hashes alone cannot prove the other three calls' semantic outcomes. The returned roster is detached from caller mutation. No cryptographic seal or participant-authentication claim is made for these in-memory objects.

Per original body is at most 512 KiB, the first-call body set at most 4 MiB, and each provisional/final receipt at most 32 KiB. The parent may impose tighter retained-memory/artifact limits and must account the raw output once, deleted staging, partials and unknown grants. These pure functions perform no reads or writes themselves.

## Generated validation

Six authored groups passed incrementally. The initial run passed three groups and exposed a source schema error in three others: successful frozen probe output omits `failure`, while the first adapter expected `failure: null`. The exact predecessor and failed receipt remain preserved. A one-line optional-field fix was followed by only the three affected groups; all passed. There was no full final-suite replay.

The controls cover unchanged five programs/legacy validator and embedded source AST, complete fresh original-body/reparse/predicate flow, provisional-to-four-call closure, coherent source/context mismatches, retained non-network requirements, valid semantic refusal and incomplete collection, and CLI/closure failures. Real socket, interface, file-open, process and historical-evaluate paths are tripwires. No actual historical proof, original runtime output, Docker, host Netlink, model, EEG or candidate program was executed.

Independent review and any portable reviewer controls are recorded separately in the provenance. These source/generated checks are preparation evidence, not actual native qualification or permission to run.
