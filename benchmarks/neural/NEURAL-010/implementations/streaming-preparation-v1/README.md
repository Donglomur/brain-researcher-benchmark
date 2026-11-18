# Complete-cohort streaming source preparation

This operator command prepares the same **686 CHB-MIT recordings and 23 biological
people**, one complete original at a time, and resumes from durable record
receipts. It reuses the pinned original EDF projector, annotation reconciliation
and fold-view generator. The chb01/chb21 identity merge, calibrated int16 signal
representation, duplicate channel order, full observed durations and annotation
semantics remain unchanged.

**This is an implemented source route with generated controls. It has not prepared
the authentic full corpus, qualified a runtime, supplied an EEG viewer, trained a
reference, or run a participant.** Registration, scientific readiness and access
mode qualification are unchanged. The generic generated-test backend is never
selectable through the production CLI.

## Inputs and custody

The operator supplies a pinned JSON request with exactly these fields:

```json
{
  "original_source_root": "/operator/original-preparation-source",
  "lock_path": "/operator/source_assets.json",
  "metadata_root": "/operator/source_metadata",
  "metadata_pins": {"<each of the 51 required filenames>": {"bytes": 1, "sha256": "<exact digest>"}},
  "key_path": "/operator/private/identity.key"
}
```

The example shows shape, not usable pins. `Original` accepts only the exact
270,520-byte source lock at SHA256
`7485ba994f8d0a33f596e68d6f552d0849d911dd9c971bf9fbeee77dad1c4111`
and the original ten-member preparation closure at manifest SHA256
`ad64dcbe1f9543725f2e4720ad974a608c512e8a2c833adad37dfd23119baef9`.
It authenticates every original source member and all 51 metadata operands before
using the unchanged original reconciliation function. It preserves the chb07
inventory correction and original chb24 reconciliation policy. Missing or invalid
source data never become a zero-seizure recording.

The identity key is the original private 32-byte key. Its bytes or digest are
never serialized. Every invocation recomputes the original HMAC record/person
identities and checks all of them against the immutable campaign. Metadata,
reconciled annotations, source closure, paths and bindings cannot change across
resume.

Keep three separate operator-controlled directories:

- **workspace:** private record attempts, receipts, pending signals and eventual
  prepared payloads;
- **anchor:** independently retained configuration and journal checkpoints;
- **invocation ledger:** create-only reservations for every CLI launch, including
  launches that fail before workspace authentication.

They must be disjoint from source metadata/code and the private identity key.
These paths are operator infrastructure, never participant mounts. Independent
custody of the anchor is essential: changing both histories together is outside
this component's protection. A hash chain alone is not external authority.

## Commands and complete streaming

Run with a selected, source-authenticated Python environment on a **qualified
Linux host**. The CLI uses the Linux boot ID and monotonic clock to reject resume
after a reboot or migration. It does not install NumPy/h5py or provide a container
image. The original projector imports those libraries only when a real source
record is processed. Environment provenance and hard resource enforcement remain
the independent launcher's responsibility.

Every invocation takes these arguments:

```text
python3 -B /selected/stream.py COMMAND
  --root /operator/campaign
  --anchor /independent/operator-anchor
  --invocation-directory /independent/invocation-ledger
  --invocation-id UNIQUE_ID
  --request /operator/request.json
  --request-bytes EXACT_BYTES --request-sha256 EXACT_SHA256
```

Select and authenticate this package's source manifest before launching it, and
prevent an uncontrolled Python import path from substituting local modules.
These example commands do not themselves supply execution qualification.

`init --limits /operator/limits.json` requires fresh workspace and anchor paths.
It returns the configuration descriptor. Every later command must include
`--config-bytes EXACT_BYTES --config-sha256 EXACT_SHA256`, supplied from the
operator's retained descriptor rather than recomputed from an untrusted workspace.

The fixed limits JSON has positive integer fields `read_bytes`, `write_bytes`,
`input_bytes`, `attempts`, `whole_seconds`, `operation_seconds`,
`project_peak_bytes`, `minimum_free_bytes` and `max_events`. At most 10,000 journal
events are admitted. Set an independently reviewed complete-cohort envelope;
there is no default 45 GB acquisition or preparation authorization.

Use `stream` for a complete sequential acquisition/preparation session. An
independently authorized source owner provides one JSON line after acquiring a
complete locked original:

```json
{"record":"chb01/chb01_01.edf","source":"/source-owner/current-original.edf"}
```

The source owner must wait for `source_record_committed` before replacing or
removing its own incoming file. The orchestrator copies and hashes that original
into its own staging, runs the unchanged projector, commits the complete result,
and retires only its own staging file. It never deletes the source owner's input.
The source owner accounts for acquisition, failed transfers, retries and its
incoming storage separately. There is no network client or download retry in
this component. Exact locked URLs include an encoded-plus filename and should
be used literally by the external source owner.

The stream accepts at most the remaining number of original records plus one EOF
check, with a 16 KiB maximum complete line. It reserves each read before waiting.
EOF before all 686 recordings raises an incomplete-cohort error; it never
publishes a partial benchmark. On complete EOF it finalizes the full cohort.
Committed records remain resumable after an incomplete or interrupted stream.

The supervisor **must enforce the process deadline while stdin or native I/O is
blocked**. Internal clock checks do not interrupt a blocked read or a native
library call. The same-boot campaign deadline never resets at resume. Cross-boot
or remote migration requires a separately designed/admitted recovery route and
is deliberately unsupported here.

Other commands are:

- `process --record LOCKED_PATH --source ABSOLUTE_PATH`: one record; useful for
  explicit repair, but repeated one-record invocations reauthenticate the growing
  completed corpus and can be expensive. Prefer one bounded `stream` session.
- `check`: reauthenticate completed record receipts and retained projections.
  This is not scientific evaluation or proof of runtime containment.
- `cleanup --attempt ORDINAL`: finish interrupted cleanup of one committed
  record, including the case where unlink succeeded before its acknowledgment.
- `abort --attempt ORDINAL --proof ABSOLUTE_PATH --proof-bytes N --proof-sha256 H`:
  recover a pending attempt only after the independent operator has established
  producer quiescence. The proof pin binds supplied evidence; it does not prove
  its truth. Partial projections are quarantined, incomplete staging is retained,
  and all prior reservations remain charged. A retry uses a fresh attempt path.
- `finalize`: reauthenticate all completed projections and metadata and publish
  only the full cohort. Repeated verification has a fresh read reservation.
- `view --view OPAQUE_PERSON/final --view OPAQUE_PERSON/inner/OPAQUE_OTHER_PERSON`:
  materialize one or more selected original views in a single verified session.
  Multiple selections share one full-cohort reauthentication.

## Durable progression and failure behavior

Each command runs under one writer lock. A stale replay cannot acquire the lock
and act after another process appended. Before staging or projecting, the command
persists and fsyncs an attempt with its full conservative reservation in both the
local journal and the disjoint anchor. No new source attempt is admitted while a
prior producer is unresolved, or while a completed record's owned staging has not
been retired.

A record becomes complete only after exact source extent/SHA256 verification,
unchanged source stat identity through original conversion, output sync and hash,
original annotation/metadata construction, and a durable create-only receipt.
Resume authenticates the saved receipt and projection, recomputes its semantic
payload using the original code/annotations, and checks its private binding.
File existence or size alone never adopts an orphan projection.

Cleanup requires that durable record completion, a reauthenticated retained
projection, and the original owned staging path/inode/content. It persists a
cleanup intent before unlinking and then records the result. A missing staging
file is acceptable only when that exact cleanup intent was already durable.
Historical originals, external source inputs and projection files are not
cleanup targets.

Canonical no-symlink checks guard owned creation, rename, read and cleanup, with
single-link ordinary files and exclusive creation. They reject dangling links as
occupied paths. These guards are not a race-proof sandbox against a privileged
actor changing the filesystem concurrently; namespace isolation is an external
qualification requirement.

Truncated journal/anchor frames, disagreement between the two histories, unknown
or missing retained artifacts, or torn final metadata fail closed. The command
does not erase/rewrite those frames or infer that an unresolved producer is dead.
Such failures need independent recovery assessment. Local replay also rejects a
rollback to an older valid prefix when the external anchor retains the newer tip.

## Publication and lazy exact views

The pending payload tree remains private. Publication requires the exact complete
source set, all 23 people, all committed owned staging retired, and the exact
686-file signal namespace. The resulting panel, metadata, protected assessment
and source provenance retain the original row shapes, carrier task tags, ordering,
float annotation endpoints and source-to-opaque mapping. Their bytes feed the
genuine detection interface's `project_preparation()` without exposing labels or
source filenames to participants.

All **529 original views** are generated and indexed by exact byte/hash descriptor
before publication: 23 final and 506 inner views. Their redundant training/query
documents are generated again by the unchanged original function and materialized
only when requested. Each output is checked against the indexed descriptor.
No scientific samples are compressed, dropped, downsampled or approximated.

The final payload directory is published by same-filesystem atomic rename, so
signal bytes are not copied a second time. A crash between rename and journal
acknowledgment can resume after complete artifact authentication. Partial/torn
final payload writes cannot be silently repaired.

The receipt is truthfully named `STREAMING_PREPARATION.json`, schema
`neural010-streaming-preparation-v1`. It explicitly states that the monolithic
legacy `prepare.py` was not executed. **This is not a drop-in receipt for the old
reference-study driver**, which expects the old schema and physical view files.
A separately authenticated compatibility bridge is still required before that
driver can consume this route; manufacturing an old receipt is not a shortcut.

## Resource accounting and limits

For each processing attempt with locked source size B, the journal reserves:

- input admission B, recording imported source volume rather than new network
  acquisition;
- staging/output writes B + (2B + 8 MiB) + a bounded record receipt;
- source/projector/output-hash reads conservatively before conversion;
- an original native memory gate of 16B + 16 MiB;
- two 64 KiB journal-frame allowances per transition, even if actual frames are
  smaller.

Cleanup verification, resumed output verification, final metadata verification,
streamed command input and view materialization add their own nonrefunded
reservations. All successful, failed, aborted, quarantined and deleted artifacts
remain charged. The full original projection write envelope remains
**97,268,573,696 bytes**, before staging, receipts, journals, metadata and requested
views. This conservative logical allowance is not a measured retained H5 size.
One external incoming original and one owned staging copy can coexist while a
source is processed. Failed-attempt quarantines also consume space.

Workspace authentication cannot safely write to an untrusted workspace journal.
Therefore every CLI launch first writes a unique, create-only reservation to the
separate invocation ledger: **43 MiB metadata-read allowance** and a conservative
genesis/receipt-write allowance. These charges survive preflight failures and are
separate from the signal-operation counters. The independent launcher must admit
their cumulative cost, including the small initial reservation-creation operation;
the invocation ledger is not an approval service or a substitute for that
launcher. Reusing an invocation ID fails before large preflight reads. Account
for both ledgers and external acquisition; do not report the inner vector alone
as total physical I/O or as a measured RSS bound.

The disk guard checks the owned workspace filesystem before each new source.
Journal/anchor capacity, metadata/view writes, external incoming storage and
other processes still need a complete independent storage reservation. The code
does not create storage, shrink the task, stop other jobs or grant itself more
budget. Cooperative checks and source review do not qualify physical CPU/RAM,
process, namespace or deadline containment.

## Construction checks

`test_stream.py` uses only generated bytes and the pinned public filename roster.
Its generic two-record kernel fixtures test interruption, anchored replay,
nonrefunded costs, cleanup, corruption, symlinks and publication. The separate
full-support control constructs generated numerical descriptors for all 686
filenames, retains the biological merge, runs the original 529-view generator in
memory and joins the outputs to the actual detection projection interface. It
does not invoke the original EDF reader/projector or any native scientific library.

Run controls through the project's short-test pool, with a fresh
`NEURAL010_CONTROL_ROOT` so failed and successful artifacts remain attributable.
When staged outside the repository, `NEURAL010_ORIGINAL_ROOT` and
`NEURAL010_DETECTION_ROOT` select existing pinned source dependencies for controls
only. They do not alter production source admission. Construction evidence lists
the actual executed controls and independent review; generated success is not
authentic preparation, detection performance, comparator competence or readiness.
