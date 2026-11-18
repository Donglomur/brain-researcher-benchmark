# Per-case raster participant transport

This operator component runs a new local participant process for each original
frozen case and connects it to the accepted raster `Session`. Its only data wire
is newline-delimited JSON on stdin/stdout: existing allowlisted metadata and PNG
pages go to the participant; existing typed viewer actions come back. It does not
send the source packet, EEG sample arrays, labels, complete roster, Python objects
or score. The same 30-second, 18-channel causal packet and single probability
remain bound to the unchanged complete-case collector and scorer.

## Existing source authority and exact wire

`transport.py` verifies the accepted `raster-collection-v1/collector.py` bytes.
That collector pins `typed-raster-viewer-v1/viewer.py`, which pins the original
`complete-support-evaluator/protocol.py`. `SOURCE.json` records these dependencies
and the existing task contract. No protocol, cohort, target or access-status file
is changed. This is implementation of the existing raster interface, not a new
scientific arm or an admission of native neural understanding.

On launch the participant receives the original `helsinki-raster-description-v1`
message. It may emit the original `describe`, `view` and `answer` objects, one
newline-terminated UTF-8 JSON object at a time. Responses are precisely the
original description, frame or final-answer-receipt schema. Each response schema
has an exact field allowlist; description and frame bindings remain unchanged.
Visible metadata includes relative sample clock, units, channel names, original
quality flags and frame clipping counts. Frames contain base64 PNG bytes and
their hash; they contain no numeric waveform export or hidden raw-signal text.

Invalid UTF-8, duplicate JSON keys, nonfinite constants, malformed/partial frames,
oversized output, coalesced extra frames, invalid typed actions and any bytes
after the first final answer fail the case. The first answer still passes through
the accepted `Session`; wrong bindings and revised answers are not accepted.
Stderr is discarded and is never treated as a protocol message or model result.

## Operator integration

```python
from transport import run_case

# owner is the existing phase-two Collector over the protected original schedule.
# argv, limits and the participant's immutable artifacts must be frozen separately.
for packet in original_ordered_packet_iterator:
    receipt = run_case(owner, packet, argv=frozen_participant_argv,
                       limits=admitted_process_limits, scratch_root=private_scratch)
complete = owner.finish()
# Protect the complete export's digest, then use the existing admit_collection
# and unchanged evaluator with the identical source Reference.
```

`argv[0]` must be an absolute executable path. No shell, inherited environment,
extra file descriptors or host-object serializer is used. Each invocation creates
an empty private working directory and calls `Popen(start_new_session=True)`;
the observed child PID, process-group ID and session ID are recorded. The process
receives only a fixed minimal locale/thread environment. A random operator-side
launch ID, command/environment hashes, typed wire-event hashes and cleanup facts
are returned to the operator, not sent as observations to the participant.

All six limits are explicit operator inputs: `wall_seconds`, `max_actions`,
`max_action_bytes`, `max_stdout_bytes`, `max_response_bytes`, `max_wire_bytes`.
The wall limit is 1–60 seconds, including a reserved final 0.5 seconds for cleanup.
The source imposes finite outer caps; these are engineering protections, not a
selected scientific evaluation budget. An insufficient budget fails the full
case rather than reducing sample support or silently skipping it.

After the final answer the participant must close stdout, exit successfully and
leave no observed process group. Only then, after owned cleanup and scratch
removal, does the wrapper call `Collector.commit_current()`. A failed transport
leaves the original current case uncommitted and blocks complete export. The
operator must discard that failed assessment attempt; it must not bypass this
wrapper to commit a finalized Session or silently retry selected cases.

Cleanup only addresses the process group created by this invocation. An exited
leader is reaped before group observation; an unavailable OS observation is
recorded as unknown and never treated as absence. If group observation or signaling
is unavailable while the current Popen-owned leader is alive, the wrapper directly
requests that leader's termination and reaps it. That fallback does not establish
descendant or group absence: the case remains failed and uncommitted. Residual
observed owned groups are terminated and failures retain their cleanup facts. This does not track a child
that deliberately escapes its process group or prove an arbitrary descendant
tree has vanished.

## Generated execution evidence and limits

There are 14 maintained focused controls. The first pool run executed 11 methods:
the complete generated schedule used 80 distinct processes for 79 invented
infants, producing 84 actual PNG frames and 80 correctly bound final rows. The
fixture checked fresh local globals and empty cwd, PNG structure/CRC/hash, exact
wire fields, environment/FD exclusion, failure budgets and final-answer rules.
One malformed partial-frame case exposed a macOS group-observation EPERM race.
That failed run is retained. After the cleanup repair, only four affected/new
methods ran: framing, deadlines, residual groups and an injected EPERM regression;
all four passed. Static review then found the still-live/unknown-group variant.
Two new focused controls passed after the direct-owned-leader fallback: persistent
unknown group status remains explicitly unknown after the leader is reaped, and
a transient unavailable observation can later be independently resolved. The
unchanged 80-case construction was not replayed after either localized cleanup
repair. All three runs used the existing two-slot pool; no authentic EEG or model
was involved. The original sealed source package and all attempts are retained.

Fresh exec, fresh cwd and a clean environment establish local fixture lifecycle
facts. They do **not** establish a fresh remote model context, prevent shared
files/network/provider memory, deny same-user process inspection, or prove that
a model interpreted the PNGs. A participant may still answer without requesting
a page. The constant fixture probability is a protocol probe, not a baseline or
neuroscience result. Raw authentic-source storage must be independently hidden
from a real participant; this local process wrapper alone does not do that.

Remaining gates include authentic full-source custody and preparation; qualified
quality flags and train-only comparators; all required controls on identical
support; protected persistence and provenance; actual participant/model identity,
fresh remote context and process/filesystem/network isolation; native-rate PNG
readability and information equivalence; and full authentic-scale resource
qualification. The original task remains unqualified and not submission-ready.

CI seam for the sole integrator, after installing the three pinned dependencies:

```sh
python3 -B -m unittest discover -s benchmarks/neural/NEURAL-EXP-005/implementations/raster-process-transport-v1 -p 'test_*.py' -v
```

The optional `HELSINKI_TRANSPORT_PROOF_PATH` writes at most 24 KiB of generated
control receipts to a new operator-selected path. The optional `HELSINKI_LIVE_CLEANUP_PROOF_PATH` separately writes at most 8 KiB
of the two live-unknown fixture receipts. No EEG bank or PNG fixture is persisted; each owned case creates only a one-byte generated cwd marker, then its
directory is removed. OS process controls require a POSIX host. No task or central
registry/CI file is modified by this private package.
