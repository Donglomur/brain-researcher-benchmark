# Complete-field FUS query packets

This component turns the existing full-field preparation output into one
lossless, nine-map packet for every query in a complete held-record fold. Each
packet contains the same eight labeled calibration maps and exactly one query
map. It supplies a shared byte artifact for the strict native, fixed-program and
tool-assisted conditions. It does not run any of those conditions.

The component is additive. The registered task, existing full-field producer,
scorer, roster and historical source manifests are unchanged. No new benchmark
ID or scientifically qualified result is created.

## Interface and source admission

Use Python 3.11 or later and the standard library. Admit the exact source graph
from the trusted release's
[current descriptor](../../../../integrity/current-closures/construction-fus-delivery/SOURCE.json)
before importing `delivery.py`. The descriptor's expected identity must itself
come from a trusted release, not an untrusted source tree. The runtime separately
checks the exact bytes of the existing `scorer.py` and `roster.py` dependencies
before executing them in private module namespaces. It neither trusts stale
bytecode nor overwrites global `scorer`/`roster` module bindings.

```python
from delivery import prepare_packets

completion = prepare_packets(
    frozen_intake,
    successful_fullfield_preparation_receipt,
    load_private_prepared_map,
    stage_private_packet,
    held_record_id=private_held_record,
    max_map_bytes=reviewed_native_rgb_byte_limit,
    max_packet_bytes=reviewed_nine_map_byte_limit,
    max_total_packet_bytes=reviewed_complete_fold_byte_limit,
)
```

`load_private_prepared_map(query_id)` returns the exact map dictionary emitted by
the existing [full-field producer](../fullfield-preparation/README.md).
`stage_private_packet(packet_bytes)` receives immutable canonical JSON bytes.
The private `held_record_id` is explicit because the original producer receipt
does not contain it. The operator must establish that intake, prepared maps,
receipt and this held-record selection belong to the same accepted preparation;
this function checks consistency and does not establish their physical origin or
custody.

The existing scorer validates every one of the 49 records and 20,622 declared
source slots before any map callback. The explicit zero record remains required.
The selected fold must be one of the 48 positive records. The component checks
the receipt's 47 training records, complete training-map count, eight calibration
maps, full query count, exclusions, frozen scale and pixel counters. Declared
population counts are not newly authenticated observations.

Calibration is selected from the frozen intake's earliest eligible trial in each
direction; those eight trials need not be the first eight rows. They are loaded
once in canonical angle order. Every other eligible held-record trial is then
loaded once, in frozen source order, including queries that preceded some
calibration trials. No query subset is selected. One successful call covers one
fold; the full assay still requires all 48 prescribed outer folds and their
separate construction/inference boundaries.

## Packet representation

Every packet has schema `fus_nine_map_packet_v1`, opaque fold/query keys, fixed
general context, the eight angles, eight calibration entries and one query
entry. A map entry contains only its opaque key, native dimensions and pitch,
pitch unit, acquisition rate, source float format, fixed training scale,
invalid/saturated counts and a base64-encoded PNG. Calibration entries also
contain their canonical angle. Query entries contain no direction.

Input map dictionaries have exact allowed fields; extra fields are refused.
Behavior, source record/trial/frame identifiers, acquisition times, filenames,
intake hashes and preparation receipts are not included in the packet. The
operator remains responsible for provenance and for ensuring that permitted
image/metadata values and opaque keys do not encode forbidden information.
An allowlist cannot prove absence of covert information in untrusted pixels.

The PNG is RGB8 at the exact native dimensions, with filter-zero scanlines and
no auxiliary chunks. It retains every source RGB byte. Valid pixels must be
grayscale; the sole invalid-pixel color is magenta `(255, 0, 255)`, and the actual
magenta count must equal the declared invalid count. Saturation is checked only
as a nonnegative count bounded by valid pixels: rendered gray values cannot
reconstruct whether an original delta exceeded the training scale. Saturation
authenticity remains the original producer's responsibility. All nine maps must
agree on geometry, pitch/unit, acquisition rate, format and scale.

The API has no mode argument or mode-dependent representation. Retain each
packet once, by its completion-record SHA-256, and supply those exact bytes to
all strict A/B/C conditions. Do not independently re-encode a packet per mode.
PNG output is deterministic for a fixed source/runtime; zlib-version differences
may produce different compressed bytes with identical decoded pixels, so the
retained packet identity—not re-encoding elsewhere—defines shared evidence.
Actual provider transport, image tokenization/resizing, fresh per-query state,
network restrictions, learned-tool exposure and protected execution remain
separate qualification requirements.

Matched reference methods are also separate work. This component does not
choose template-mask/empty-overlap rules or a kernel, scaling, intercept,
hyperparameter tie rule or probability conversion for the required eight-shot
ridge reference. The six registered ridge candidates stay unchanged; the
remaining policies and reference implementation must be frozen and reviewed
before comparison. Equal packet bytes alone do not establish informative
direction evidence or competent reference performance.

## Staging and resource boundary

All callback output is evaluator-private staging. A malformed late map,
counter mismatch, byte-cap refusal or callback failure can leave earlier staged
packets behind. Those packets are an incomplete fold. Publish or deliver none
until this call returns successfully and the operator commits the entire staged
set. This module does not provide filesystem transactions, durable publication,
process isolation, or adversarial callback containment.

All three byte limits are required positive integers. They bound each native
RGB input, each serialized nine-map packet and the sum of serialized packets,
including the eight repeated calibration images for every query. Exceeding a
limit refuses; it never crops, resizes or drops cases. These are payload-size
checks, not RSS, physical-I/O or wall-time limits. Eight calibration images and
one current query are retained; PNG/JSON/base64 buffers and Python object
overhead require an independently measured deployment memory allowance.

The success receipt binds the intake and preparation-receipt representations,
every packet's opaque ID, exact byte size and hash, and the complete output
count. It is operator-private and includes the private held-record identity.
All native-source, full-resolution-delivery, protected-evaluation and scientific
qualification flags remain false.

## Why native normalization remains held

The [source-context record](SOURCE_CONTEXT.json) separates verified consumer-code
facts from missing original observations. Authenticated source describes
task-aligned `iDop` axes as y, x, window, trial and continuous `dop` axes as y, x,
frame. It does not establish physical acquisition start/end intervals, actual
stored array types, frame-to-trial lineage or original geometry/pitch. The
author's `getEpochs` maps `behavior.target_acquire` to its go-cue variable but
uses successful-trial medians and a missing-memory fallback. Those operations
cannot replace this task's per-trial, wholly-in-memory acquisition rule.

No exact invocation list for the five Run99 records was found in the inspected
first-party source. Matching slot labels also does not prove identical physical
planes. The next native bridge requires genuine producer/schema evidence,
complete archive/member and trial reconciliation, exact physical clocks and
geometry, and independently reviewed lineage. This delivery component does not
manufacture them or change any existing native/admission hold.

Run the generated source controls from the repository root:

```sh
python3 -I -S -B -m unittest discover -s tests/construction -p test_fus_delivery.py -v
```

The controls preserve the complete logical roster using invented tiny images;
they check native-pixel PNG round trips, exact support/query membership,
redaction, counter/budget failures and staged-error semantics. They establish
engineering behavior, not authentic neuroscience agreement or model quality.
