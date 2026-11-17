# Platform and storage decisions for the event campaign

This document is a source design proposal. It authorizes no acquisition,
projection, model run, native probe, dataset reduction or change to a frozen
preparation contract. The detection campaign and the historical reconstruction
campaign remain separate routes.

## Preserve exact views while bounding the live cache

The frozen `streaming-preparation-v1/original.py` generates and pins all 529
original view groups using the unchanged original `views.make_views` function.
There are 2,093 JSON packets: 23 final groups with three packets and 506 inner
groups with four. The 70,229,426,176-byte figure is their combined admission
ceiling at 32 MiB per packet, not their measured size. View JSON repeats metadata
and training labels; it does not copy the H5 signal arrays.

An exact lazy provider can retain every descriptor while caching one selected
group at a time. Its packet cache ceiling is then 128 MiB, or 64 MiB when the
selected operation uses only TRAIN and SUPPORT. It must preserve the precise
original bytes, observations, biological splits and complete 686-record /
23-person support. It must not substitute a smaller panel or change a worker's
training information.

The following changes require a versioned source route and review before use:

1. A privileged materializer owns the full reconciled annotation table and
   private identity key. The observation/exchange controller must not construct
   the original preparation backend merely to resolve a selected view. Protected
   operator intake can read source-to-opaque bindings and the authorized final
   fold's TRAIN packet to apply the existing training allowlist; this is distinct
   from supplying those private bindings or the held person's labels to a
   participant. Global assessment access remains behind the complete freeze.
2. The controller requests an exact selected view descriptor. The materializer
   creates the original bytes in a fresh, bounded worker namespace and verifies
   the complete packet's size and SHA256 before release.
3. For an arbitrary participant, the phase12 training projection still removes
   source filenames, raw EDF digests and other historical reference-worker
   fields. Lazy delivery must not bypass that allowlist.
4. Each delivered group has an immutable request/delivery receipt. Retirement
   requires independently established worker/group quiescence and verifies the
   owned cache identity before deleting only that cache. Its bytes remain in
   cumulative accounting. Delivery and retirement receipts are retained.
5. Reference request construction and release replay consume the same immutable
   receipt/pin identities. They must not require all historical packet paths to
   remain materialized. The current v2 dispatch's `require_all_views=True` and
   release replay therefore need a reviewed successor; deleting current files
   or merely disabling that check is not sufficient.
6. The materializer should authenticate the complete immutable signal corpus
   once in a bounded session, then serve selected groups under an explicitly
   reviewed custody model. Calling the current `export_views` command 529 times
   would rehash all completed H5 files on every invocation. Avoiding those
   repeated reads needs a justified immutable-storage/session boundary, not a
   fabricated verification receipt.

This bounds simultaneous packet cache, not total cumulative generation, retained
signals, durable receipts, or failed attempts. Actual byte totals must come from
the authenticated complete view index. No lazy provider or retirement change is
installed by this proposal.

The initial event-campaign H5 provider also authenticates a selected complete H5
file on every observation request before delivering the requested window. Its
logical reads therefore include the complete file repeatedly, not just the
window's samples. A viewer sweep can cost substantially more I/O than its image
payloads suggest. The one-record projection-parity timing does not qualify that
campaign cost. Any authenticated-session cache optimization needs its own source,
mutation/custody and cumulative-budget review; none is implied here.

## What can and cannot be proved about H5 size

For each successfully accepted EDF, let B be original file size, D complete
integer seconds, S selected EEG channels and C source channels. The unchanged
writer retains `eeg_digital` as int16 at 256 Hz, with chunks `(256, S)` and no
compression. Thus its digital array payload is `512 * D * S` bytes, with exactly
D complete chunks and no final partial-second padding. Exact source extent and
selected-channel geometry imply this payload does not exceed `B - header`.

For the complete locked cohort, digital array payload is therefore at most
45,756,643,072 bytes: total source bytes 45,756,994,304 minus at least 512 header
bytes for each of 686 files. The successful full-cohort contract separately caps
total observed seconds, and hence chunks, at 10,000,000. Under the observed
float64 calibration representation, the four auxiliary arrays add 50 bytes per
selected channel, at most 17,561,600 bytes for 686 files with 512 channels each.
These statements bound array payload, not the enclosing HDF5 files.

The existing writer leaves HDF5 file/index/allocation properties at library
defaults. This source review does not prove a uniform upper bound on container
metadata, chunk-index trees, block allocation or fragmentation under a fully
qualified pinned runtime. The historical `sum(B) + 2 GB` check in the adapter's
separate `build` helper is a budget choice, not such a proof; the accepted
streaming route calls `project` directly.

Consequently, retain the current full projection admission ceiling of
97,268,573,696 bytes (`sum(2*B + 8 MiB)`). A single measured projection, a sample
ratio, typical HDF5 overhead or a smaller fail-on-excess budget cannot establish
that all 686 files will fit. A tighter container ceiling requires a derivation
for explicitly pinned allocation/index behavior, followed by review of any
necessary versioned writer change. Logical admission and post-write checks are
not an OS filesystem quota or a bound on arbitrary partial failures.

## A small, explicit Mac clock successor

The existing streaming CLI unconditionally obtains Linux
`/proc/sys/kernel/random/boot_id` and pairs it with Python's monotonic clock. Its
contract has no Mac fallback. The successful one-record projection on macOS
establishes producer compatibility for that record, not streaming CLI or
reference-runtime qualification.

If local Mac preparation is selected, introduce a separately named clock-source
successor rather than changing `streaming-preparation-v1`:

- Preserve the Linux boot-ID behavior under its existing versioned identity.
- Add an explicit Darwin domain only after a bounded metadata qualification
  confirms that the selected host supplies a stable boot-session identifier.
  A candidate is the `kern.bootsessionuuid` sysctl key; its availability and
  semantics have not been probed or qualified by this work.
- A future probe would use an independently pinned absolute sysctl executable,
  fixed arguments, no shell, a small stdout/stderr cap and a short external
  deadline. Missing, malformed, changing or unsupported identity fails closed;
  there is no fallback to wall time, PID, an operator-invented boot ID or a
  generated-test clock.
- Bind platform, clock scheme, boot-session identity, host authority and selected
  Python monotonic implementation to the new immutable genesis. Recheck that
  domain on every resumed invocation. Linux and Darwin domains are never
  interchangeable, and old journal timestamps are never translated or reset.
- Keep cumulative costs and deadlines nonrefundable. An independent launcher
  still supplies the hard interval for blocked input/native I/O. Suspend,
  process termination, reboot and unavailable clock identity require explicit
  handling; clock metadata alone does not qualify process containment.

Generated clock doubles could check domain mismatch, reboot, failed probes and
nondecreasing deadline behavior before any separately admitted host probe. No
Darwin clock implementation or probe is included in this package, and no Mac
streaming qualification is claimed.

The immediate priority remains the genuine participant event-detection route.
Storage and clock work must not turn a successful preparation into a claim that
the participant observed signals, generated detections, or surpassed a reference.
