# Original post-score role host v2

This is source for an operator-owned local Transformers role. It does not select a model, prompt, token budget, hosted backend, qualification issuer, or scientific result. Parent code owns the original campaign ledger, pending external costs, once-only join, operation/qualification/response publication, and consumer. No TokenLedger is constructed or settled by this package.

This guide is installed at `<installed-root>/role-host/README.md`. All captured runtime paths below are relative to `<installed-root>/complete_study`, and all four bodies are already included in the package. The historical author filenames in the first column are provenance labels, not additional files to locate or install.

The curated public source package contains 130 files and 31 directories, with 118 files at 0644, 12 retained runtime files at 0444, and directories at 0755. Its87-member runtime identity is distinct. Omitted bodies are inert historical adapters, duplicate contracts, acquisition helper and private provenance ledgers; live scientific methods and retained file modes remain unchanged.

Already-installed operative source mapping:

| Author file | Captured runtime path |
| --- | --- |
| role_host.py | n055/postscore_role_host.py |
| reserved_adapter.py | n055/postscore_reserved.py |
| role_worker.py | postscore_role_worker.py |
| gated_clone.c | postscore_gated_clone.c |

The worker's fixed `CAPSULE` list contains only these required ordinary modules, the pure post-score service module, original common/budget/journal/process/cgroup/native/provider/resource-policy/registry/seals code, and the model entry. It excludes original source/authority loaders, protected targets, scorer, credentials, campaign journal, and arbitrary participant modules. Captured byte bodies are compiled directly; ambient n055 or stale bytecode is refused. The model container receives a separate readonly directory containing only model_provider_entry.py, the exact request/config files, and the explicitly selected model directory.

## Callable interface

`admit_controller(runtime, budget, journal, carrier, deployment) -> ControllerAdmission` must run before campaign/preparation work. The process must already occupy the selected controller leaf. The function observes actual current PID membership, directory identities, parent topology, enabled controllers, current leaf limits and memory.peak. It does not claim to place the controller retroactively. Qualified preactivation controller launch, including its earlier interpreter/bootstrap costs, is an explicit deployment prerequisite.

`RoleHost(runtime, budget, journal, carrier, source, controller, deployment, *, authority)` requires the same actual original Budget, Journal, FailureCarrier, Sources and Authority objects. The controller runtime mapping needs common, budget, journal, process, cgroup, native, native_providers, resource_policy, registry, seals, source, authority and postscore_services. The source must include the fixed CAPSULE bodies. Parent's narrowly typed pending-cost admission scope remains responsible for permitting only the exact current request's owned pending unknowns through original Budget.admit.

`host.run(request, role_spec, prepared_payload) -> dict` accepts:

- The exact `neural055-postscore-operation-request-v2` with the original token reservation and absolute clocks.
- The admitted provider's six fields: id, kind, config, qualification, model_directory, model_manifest. Kind is local_transformers_text_v1; all descriptors are operator-root relative and model_directory is explicit absolute. The controller verifies original trusted_provider_source_and_runtime authority; the worker captures/revalidates the full model namespace and bodies.
- Exactly messages, authorized_inputs, response_contract, output_policy. Parent selects these fields from the actual pure renderer and supplied output policy. Only messages reach the model. The worker invokes actual `bind_result` on the returned text without retry or repair, then publishes RESULT.json before closure.

Success fields are schema=`neural055-closed-role-result-v2`, request_sha256, result (descriptor relative original campaign journal), result_bytes (actual bytes), usage, original_processes (durable descriptors relative that journal), costs (six external quantities), memory, origin, end, complete, costs_complete, unknown_quantities, known_lower_bounds, role_observation, original. `original` is the raw retained object, never a JSON projection. Failure is `RoleFailure(original)`; its original dict always contains all six costs as actual known values or None, costs_complete, unknown_quantities and separately labeled known_lower_bounds. Missing/unknown quantities are never converted to zero. Actual model usage may remain unknown, so parent's reservation remains unresolved. Parent joins known external values/prefixes once; it never charges those same values again from child wait4 records.

The six costs are cpu_seconds, read_bytes, write_bytes, files, stream_bytes, model_calls. Worker-managed final publication precedes its final transport frame. The controller observes the actual frame stream on its own ledger. Closed enclosing role-cgroup CPU includes worker bootstrap, dedicated daemon, provider, result binding/publication and final frame encoding/send. Worker/helper/client/daemon wait4 numbers are nonadditive evidence. Controller launcher, observer, capture and final receipt work stays on original controller Budget.

## Explicit deployment operands

The deployment has exactly schema=`neural055-role-host-deployment-v2`, controller_leaf, delegated_parent, controller_memory_bytes, role_memory_bytes, whole_memory_bytes, controller_pids, role_pids, launcher, python, docker, dockerd, daemon_data_roots, native_profile, operator_root, closure_reserve_seconds, capsule_paths, controller_reserve. Each executable is `{path,bytes,sha256}`; each path names a qualified ordinary local executable. capsule_paths must equal source-owned CAPSULE, in order. No installation or compilation occurs at runtime.

Controller leaf is a literal direct child of delegated_parent under unified /sys/fs/cgroup. The parent has no direct processes and enables cpu/memory/pids. Controller leaf has selected memory.max, memory.swap.max=0, pids.max and cpu.max=100000 100000, with no enabled subtree controllers. The controller and newly created role parent are disjoint siblings. Both enforce selected limits, and controller_memory_bytes + role_memory_bytes <= whole_memory_bytes, exactly matching the request's memory_limit_bytes.

controller_reserve has six cost fields plus live_bytes, all explicitly positive. Worker resource limits intersect the original request with current controller headroom after existing terminal/capacity reservations, selected controller finalization reserve, and a prospectively computed bootstrap-publication bound. The worker retains original origin and absolute cutoff. It gets no fresh campaign budget, deadline, or token ledger. Parent additionally keeps whole original Budget authoritative throughout.

daemon_data_roots maps each exact role to its own qualified prepared local cached-image root. It must have no existing role claim, containers or active daemon; the source creates a one-use exclusive claim retained on success and failure. Reuse requires a separately prepared root, never automatic cleanup or shared-daemon takeover. Dedicated dockerd gets explicit config/data/exec/socket/pid paths, private containerd namespaces, cgroupfs, no bridge or iptables, and no live restore. The source joins its actual gated PID, pidfile, cgroup, DockerRootDir and daemon ID. Model image is cached and digest-pinned; pull is never. Daemon/model native cumulative I/O, storage churn and model/framework memory allocation details remain the original policy's expressly unobserved quantities, not measured zeroes.

The journal path must be short enough for Linux Unix socket names (less than108 encoded bytes including socket name); `GatedProcess.start` refuses a longer gate path. Supply a short qualified operator/journal root. Docker/client/worker executables, runtime dependencies, delegation, role-exclusive cache custody and all native interfaces require independent actual deployment qualification. None is established by the controls in this packet.

## Kernel boundary and evidence

The helper uses [Linux clone3](https://man7.org/linux/man-pages/man2/clone.2.html) with CLONE_INTO_CGROUP and CLONE_PARENT, exit_signal=0. Child is born in an actual process leaf and is a direct child of its real observer. It creates its own session and acknowledges that fact before helper exit, avoiding ProcessRunner's group-absence race. It waits on an observer Unix socket before exec; observer verifies SO_PEERCRED, actual /proc membership and owned PGID before release. Parent-death SIGKILL and all pipe/socket closure are explicit. The accepted accounting Cgroup's controller-enabled parent never receives a direct process: worker and daemon each get a separate leaf; Docker creates children under an empty provider parent. This follows the [cgroup v2 no-internal-process constraint](https://docs.kernel.org/admin-guide/cgroup-v2.html). The actual [dockerd command interface](https://docs.docker.com/reference/cli/dockerd/) supplies dedicated service paths; this package never starts the machine's shared daemon.

Build the helper only in a separately authorized/qualified Linux environment using its exact source, for example explicit `cc -std=c11 -O2 -Wall -Wextra -Werror -o /selected/launcher <absolute-installed-root>/complete_study/postscore_gated_clone.c`; record actual compiler/runtime source and binary identity. No helper compilation or Linux kernel execution was selected in this build-only delivery.

`role_observation` is a durable controller-budget publication after role closure, not part of its own future external costs. Its body binds request_sha256, source, role_owner, original processes, actual provider/daemon evidence, all group identities/final counters and complete chunked kernel observations, costs, usage, typed memory, controller process breakdown and component allocation. Raw objects remain in host.originals/carrier. Timing is:

request.created <= observation.origin <= role_scope_origin == returned origin <= role_scope_created_observed_at <= role_child_end <= role_scope_closed_at == returned end <= controller_checkpoint_at <= closure_observation_end.

memory_observation records these actual scope/checkpoint times. Controller peak scope is preexisting_partition_lifetime_through_checkpoint, with controller_partition_created_at=None. Its age is not invented. Memory scalar schema is neural055-disjoint-component-memory-v2: controller_peak_bytes/kind=checkpoint; role_peak_bytes/kind=closed_subtree_final; component_peak_sum_upper_bound_bytes; component_peak_sum_scope=through_controller_checkpoint; simultaneous_peak_bytes=None; controller_cap_bytes; role_cap_bytes; enforced_lifetime_cap_sum_bytes; whole_limit_bytes; later_controller_work_is_not_in_closed_role_measurement=True. Summing independently observed peaks is a conservative bound through that checkpoint, not simultaneous whole-system peak. Later controller finalization remains under its original enforced cap and Budget.

All four owned cgroups must finish empty and be removed, all role original processes must be naturally reaped with zero exit and absent groups, and provider resources must retire before a complete return. Failures preserve partial streams, costs, original objects and containment attempts; a kill acknowledgment is never natural closure. Genuine service/operation/blinding qualifications come from the existing independent authority path, never this module.


The additional [role environments](../environment-v1/roles/README.md) provide concrete acquisition locks, offline build recipes and inspection for trusted ingestion/controller, the actual shared campaign image, and the fixed older feature extractor. The Python 3.9 bootstrap successor retains original and secondary cleanup failures. Source recipes do not establish built images, binary/ABI compatibility, checkpoint equivalence or scientific qualification. The full inactive component has 128 discovery members plus this inspection wrapper and its manifest (130 files total); all scientific scope, contracts and protected-target rules remain unchanged.
