# OSL concrete owned transport source

This directory supplies a real local Docker lifecycle adapter for the parent OSL whole-study driver. It has not launched Docker, contacted a socket, processed authentic data, fitted a model, or qualified a runtime. Six invented RAM-only lifecycle/capture controls passed before the gated-launch revision; four focused gate/token/journal-order controls pass on the revised engine. All unchanged members retain their earlier source pins. V3 adds six focused cleanup/pidfd fault controls; prior V2 source is preserved under review-revisions/v2. Source construction and control success are not execution authorization.

The concrete CLI/process custody and resource retirement code derives from the reviewed paper-program-b engine at source commit 5cca3bd86d1c559fb5635fbc46aba50ca2fb3d98 (root-reported merge d31d034f7310a20b773bd06be07b92d46cc94528). SOURCE_BINDINGS.json pins the held manifest and donor bodies. Qualification does not transfer. Numeric CLI/base64 capture was removed; complete artifact bodies use bounded raw local Unix-socket Docker archive streaming.

## Main API

Import Provider from transport. Its constructor is:

    Provider(control_root, quarantine_root, docker_binary, docker_socket,
             engine_source_pin, trusted_exposures,
             source_read_limit, host_write_limit)

The two roots must already exist, be disjoint, ordinary, operator-private directories (no group/other access). They must not be exposed to a producer. Executable and Unix-socket paths must be absolute and have no symlink ancestors. engine_source_pin is the externally approved bytes/SHA256 descriptor of this directory's SOURCE_MANIFEST.json. trusted_exposures maps an independently approved exposure SHA256 to its operator-owned JSON path. The future operator host must be Linux with trusted /proc; process ownership tokens deliberately refuse other hosts. Constructor limits are prospective aggregate transport-read and reserved host-write ceilings across this Provider, not producer logical-I/O measurements.

    execute_phase(request, mounts, original_deadline, journal)

request is the exact osl_owned_phase_request_v1 object defined in contract.py. Its keys are schema, phase_id, action, role, image, command, workdir, source, exposure, clock, resources, output. The source and exposure fields are bytes/SHA256 descriptors. phase_id must be globally fresh at these roots; no automatic retry occurs. command is the precommitted exact argv with an absolute executable, never a shell string. workdir is /work. image is an already installed sha256 image ID; pulling is disabled. Both producer and holder use UID:GID 65534:65534. The approved image must supply /usr/local/bin/python for the standard-library holder, and must have no implicit VOLUME or healthcheck process. Image environment inheritance and fixed overrides are checked against image inspection.

Actions prepare_originals, prepare_fold, selection_evaluate, final_evaluate, and report require role operator. native_attempt and held_attempt require role A, B, or reference. Native attempts always emit the primitive CAPTURE.json endpoint; other phases use OUTPUTS.json. The parent binds these generic transport actions to the original complete cohorts, 20 fold preparations/static passes, 453 native and 5,400 held attempts, exact candidate program/source rosters, and private evaluators. This module does not invent or narrow scientific selection.

clock has origin and phase_deadline as monotonic values from the existing outer clock. original_deadline is that same outer global cutoff. All four complete time allowances must fit before any resource creation. The source never refreshes the outer cutoff.

resources has exactly these positive integer fields, with no implicit production defaults:

- setup_seconds, producer_seconds, capture_seconds, cleanup_seconds
- memory_bytes, cpu_nanos, pids, scratch_bytes
- max_files, max_directories (including root), max_file_bytes, max_output_bytes, manifest_bytes
- max_cli_calls, max_cli_bytes, inventory_bytes
- source_read_bytes, host_write_bytes

The two tmpfs capacities must be page-exact multiples of 4,096. max_output_bytes is the output-volume capacity and aggregate output ceiling. Host transport metadata, complete source/input authentication, capture wire bytes, receipt publication, and recovery need explicit allocations. The holder adds 128 MiB memory, one CPU, 64 PIDs, a 4 KiB readiness tmpfs, and each container has a 16 MiB /dev/shm; these are separately reported ceilings. They are not measured peak use. /work is the sole private scratch tmpfs; TMPDIR and HOME point there. All host binds are read-only. /output is the fresh private output volume.

mounts maps exact container targets to:

    {"path": "/absolute/operator/staged/source",
     "kind": "file" or "directory",
     "purpose": "input" or another exact approved role purpose,
     "files": {"relative/name": {"bytes": 123, "sha256": "..."}}}

For a file mount, files contains only the host file's basename. A directory descriptor enumerates its complete ordinary single-link file tree; extra files, empty undeclared directories, symlink ancestors, or changed bytes fail. Complete input/source trees are hashed before and after execution. Stage readable files/directories for UID:GID65534 (usually files0444 and directories0555 inside an operator-private parent). The provider verifies readability without chmod or source mutation. Native readonly /work/training_data and /work/data mounts are supported. Caller mounts cannot overlap one another or shadow /work, /output, /request.json, device/proc/sys paths, or fixed holder resources.

The provider privately adds a pinned read-only /request.json and creates /output and /work. These internal mounts are not caller entries. The holder receives only its pinned source, policy and read-only output volume. A never receives historical source through this adapter; full-image/source exclusions still require the externally reviewed A exposure audit. The transport cannot discover arbitrary source semantics merely from hashes.

## Exposure approval

The pinned approval document is osl_transport_exposure_v1 with exactly:

    schema, role, image, source, command, mounts,
    approved_image_inventory_sha256, boundary_audit,
    role_boundary_verified

mounts is the complete caller mount descriptor map excluding host paths, preserving kind, purpose and exact member pins. boundary_audit is the separately approved full-image/source boundary receipt pin (the parent's access.admit/validate route). role_boundary_verified must be true, and the approval registry must have been fixed by the operator outside candidate control. The adapter checks these joins and actual image, argv, environment, mount and isolation settings. It does not transform an unaudited claim into a verified image inventory.

## Output closure and streaming

Native CAPTURE.json is the existing osl19_primitive_native_capture_v1 envelope. Every unique fields member file/bytes/SHA256 is admitted to the transport closure, with no extra output files. Parent native.assemble retains complete observable/coordinate/schema admission and A/B/reference auxiliary rules.

All other phases emit exactly this OUTPUTS.json envelope plus its enumerated files:

    {"schema":"osl_transport_output_manifest_v1",
     "phase_id":"...", "request_sha256":"...",
     "files":{"RESULT.json":{"bytes":2,"sha256":"..."}, ...}}

The request hash is SHA256 of canonical transport.engine.encoded(request), also equal to the exact /request.json bytes hash. The envelope excludes its own self-referential pin and must include RESULT.json. Per-file, file-count, directory-count, manifest-size and aggregate byte bounds apply. The complete observed directory membership must equal the envelope plus the envelope file itself.

Before capture, the provider verifies Docker wait/inspect natural exit zero, no OOM, stopped PID0, and removes the producer. The independently isolated read-only holder inventories all files and directories. Each exact file is streamed from the local AF_UNIX Docker archive endpoint /v1.41/containers/<owned-holder-id>/archive. Only a single regular tar member of the exact basename/extent is accepted. Bounded local PAX metadata is permitted; links, sparse/global overrides, extra members, ambiguous HTTP framing, compression, checksum errors, trailing bodies and premature EOF fail. File data is written directly to exclusive quarantine files with checked writes, full hash, fsync and close. Numeric bodies never pass through Docker CLI output or host command arguments. A final complete holder inventory must be unchanged. Holder and volume retirement then complete, followed by source/input reauthentication.

execute_phase returns receipt, receipt_pin, receipt_path, final_transport_counters and finished_after_receipt. The pinned receipt has output_inventory (including every captured pin), quarantine_root, natural_exit, producer_closed_before_capture, retired_resources, all_native_resources_closed, command custody records, input/source joins and failure evidence. Failed phases return an immutable failure receipt with no admitted output_inventory; receipt publication failure raises and preserves evidence. Quarantine is never success by existence.

    observe(phase_id, request_sha256, expected_receipt_pin, original_deadline)

This independent parent path reads only the exact operator-private receipt and verifies its phase/request/original-clock join. It requires the externally retained expected pin. Observation does not reset the deadline.

## Parent crash recovery and independent terminal absence

Before resource creation, OWNERSHIP.json fixes all and only three unique resource names, owner labels and kinds: volume, holder, producer. Its exact pin is emitted in the OWNERSHIP journal event before any create is attempted. A durable CREATE-ATTEMPT event precedes each create; RESOURCE-ACK follows its exact acknowledgement. The supplied journal callback must durably preserve events and return; the outer supervisor handles a stuck controller under the same global deadline.

    recover(phase_id, request_pin, ownership_pin, original_deadline,
            journal, limits, controller_closed_proof)

The parent must first independently establish complete inner-controller closure and closure of every owned CLI process group, after natural exit or kill, and supply that proof pin. Docker clients use independent sessions, so the controller PGID alone is insufficient. Every Docker client now starts through a standard-library bootstrap using the operator interpreter with -I -S -B and close_fds=True. Before its exact one-byte gate is sent, the provider anchors /proc/<pid>, captures Linux PID/PGID/session/UID/start-time plus boot ID, and durably publishes that token in CLI-CHILD. Docker is execv-replaced in the same PID/PGID only after G followed by EOF. Parent loss before release closes the sole gate writer, so the bootstrap cannot initiate a Docker command. Docker cleanup opens a pidfd while its exact Popen child is still gated, then signals only that identity-bound leader. Numeric process-group IDs are used only for zero-signal absence probes; a surviving/reused group remains unknown. The parent likewise must use identity-bound signals and independently observe group absence. Missing/mismatched ownership or unresolved process/daemon outcomes remain unknown; empty Docker namespaces do not establish host process closure. The prior ungated source/manifest/receipts are preserved under review-revisions/v1. The method cannot prove closure of the process that calls it. The ownership pin must have reached the parent before creation; recovery never scans arbitrary Docker resources. It authenticates the ownership source/phase/request/original-cutoff joins, reads bounded operator-private lifecycle records, and retires only the declared owner/name/id joins. Unattempted collisions are preserved. Incomplete history makes creation outcomes unknown. An unacknowledged create that is absent remains unknown, even when independent terminal-absence queries are empty.

Recovery limits are max_records, max_record_bytes, max_metadata_bytes, max_cli_calls, max_cli_bytes, source_read_bytes, host_write_bytes. They come from the existing outer cleanup reserve and original global deadline. Result all_namespaces_empty is independent of all_resource_custody_closed; an unknown create or history/CLI failure prevents the latter. Child scientific outcome/cost is not reconstructed. Recovery receipts and events have fresh private names, never overwrite a prior phase record, and do not authorize a retry.

## Cost and validation limits

Transport read counters include source/input/metadata file bytes, bounded Linux process-identity metadata, bounded CLI response bytes and archive wire bytes. Transport write counters include actual checked host publication bytes; attempted write reservations are separate. External journal writes, executable/library reads, daemon/kernel I/O, producer logical reads/writes and exact producer peak memory are not measured here. Receipt construction costs are reported in returned final_transport_counters; the pinned inner receipt explicitly labels its earlier subtotal. Provider ceilings are never substituted for actual costs. An outer whole-study actual-resource closure must remain incomplete without separately qualified measurement.

Engineering receipts preserve every attempt. The first attempt's receipt serialization was outside its reported fixture encoding meter; later attempts explicitly meter internal identity/request JSON and report serialization with a conservative upper bound. Native's older live-cap/accounting uncertainties remain preserved in native/LEDGER.json and are not repaired by this later prospective grant. No interpreter/OS RSS claim is made. Donor code, source hashes and syntax checks are evidence about source only. Docker API compatibility, cgroup behavior, real input staging, native science, full study budget and provider qualification remain untested.

V3 failure discipline: every owned descriptor, stream, selector and pidfd cleanup is attempted independently. A primary read/write/protocol failure remains the raised exception; secondary cleanup failures attach as cleanup_errors and are retained in phase error metadata. Unowned replacement output inodes are preserved. No successful capture is claimed after unresolved cleanup. These fault controls use mocked calls and provide no actual runtime qualification.

V4 capture reservation repair: the prospective write reservation now precedes socket creation. The dedicated RAM-only refusal control proves that a rejected reservation constructs no socket. V3 archive/source-manifest bodies remain under review-revisions/v3. The latest helper encoding grant is prospectively 8 MiB cumulative (4 MiB retained, 16 MiB live); prior grants and uncertainties remain historical evidence.
