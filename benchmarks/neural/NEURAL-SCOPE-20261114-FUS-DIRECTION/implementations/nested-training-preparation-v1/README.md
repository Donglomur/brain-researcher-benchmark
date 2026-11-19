# Nested training preparation for fUS reference selection

This component fills the input-construction gap before
`outer-training-selection-v1`. For one outer-held record, it prepares all 47
permitted training episodes, each with a scale derived from exactly the other
46 training records. It reuses the existing full-field delta, quantization and
lossless packet primitives. It does not implement a native MAT reader, infer
clock units, resolve Run99 lineage, run a scientific baseline, or qualify a
protected participant environment.

## Scientific and custody boundary

The input is an authenticated private projection containing only the canonical
47-record complement of the outer-held record. It retains the complete declared
trial census, eligibility/adjudication decisions, source identifiers and common
clock intervals for those records. The outer-held record is represented only by
its public identifier; its arrays, labels and assessment artifacts are not input.
The separate zero-record reconciliation remains explicit.

Every record ID, complete trial census, eligibility decision, timing interval,
earliest-support selection and query-class denominator is admitted before any
normalized-record callback. The new projection is not a fabricated canonical
49-record intake. The existing `prepare_fold` and `prepare_packets` complete
interfaces are not called or relabeled: their 47-contributor receipts describe a
different operation.

The callback supplies a record as immutable normalized JSON bytes with an exact
declared size and SHA256. Both loads of each record must match that identity.
Byte identity can establish consistency with the authenticated projection; it
cannot establish that an original clock, source catalogue or eligibility decision
is scientifically correct. Authentic MAT normalization and independent native
source/clock/trial/Run99 review remain prerequisites for real-data use.

## Nested scales and complete fields

The existing `record_deltas` selects complete pre-cue and memory acquisitions
according to frozen intervals and applies the declared source-format arithmetic.
Every eligible full-field map contributes its finite absolute maximum and exact
valid/invalid pixel counts. Per-record summaries are then combined for each
pseudo-held training episode using exactly the other 46 contributors. Its own
maps and the outer-held record cannot affect that scale. An individual invalid
record may contribute no valid pixels; every completed episode still requires a
positive finite scale. All 47 scales are validated before any packet is staged.

The same pinned normalized bytes are loaded again for rendering. The eight
earliest eligible class supports are collected first. Every remaining eligible
query is then emitted in original source order, including queries that precede
some supports. This is the task's offline calibrated condition. Reusing the
second private decoded record for both traversals avoids additional source loads
and avoids retaining all rendered maps.

Native shape, spatial pitch, source floating format, invalid masks and every
spatial pixel are preserved. Existing `encode` and delivery `_map`/PNG/JSON
primitives are called directly; there is no new rounding rule, codec, crop,
resizing, voxel selection, predictor or scorer. The fixed delivery context and
eight canonical calibration angles remain unchanged. Query direction and source
identifiers stay in protected metadata, never inside the common nine-map packet.

The completed selector manifest contains actual packet extents and hashes, the
fixed scale-policy identity and truthful nested46 receipt identities. Final
validation uses the existing selector admission function. The provenance receipt
distinguishes 46 contributors from the canonical outer operation's 47 and retains
all source, map and pixel counts. No cross-outer record, scale or packet cache is
implemented.

## Supported entry

Use `prepare.py.prepare_training` with immutable projection bytes, a trusted
`load_record(record_id)` callback and a private
`stage_packet(record_id, query_id, bytes)` callback. Explicit positive bounds are
required for projection bytes, one record, both complete source passes, one RGB
map, one packet, all packets, and the returned manifest and receipt.

The result contains `manifest` and `receipt` as canonical bytes. The caller must
authenticate the projection and dependencies, keep all staged packets private,
and commit the complete result only after successful return. A late source,
budget, staging or validation failure may leave partial private output; it does
not produce an admitted completed manifest and never permits a smaller cohort.
There is no automatic retry, deletion or publication.

The pinned wrapper supplies the exact existing primitives and new producer. Its
private module namespaces prevent accidental ambient module substitution. The
callbacks remain trusted owner capabilities: this is not a process sandbox.
Payload limits bound the explicit returned/read content, not hidden callback I/O,
Python allocation, a whole native dataset, or an operating-system memory quota.

## Generated validation and limits

The component-local `test_nested_training.py` is a direct stdlib Python 3.11
entry with an explicit fresh `--output` directory. It emits the actual unittest
transcript. The generated checks exercise held-record exclusion, independent
maximum/count expectations, complete contributor and case support, unchanged
geometry/masks, cross-pass identity, failure bounds, and selector admission and
packet-byte compatibility. The selector compatibility check uses a no-fit
prediction stub; existing reference-fit evidence is retained separately.

Generated normalized catalogues are not authentic neural data and their
adjudication digests are labeled fixture values. Passing these controls does not
establish native/source agreement, protected delivery, model competence,
scientific readiness, an AI result, or a new benchmark count.

Run from the repository root using a fresh output path:

```sh
python -I -S -B benchmarks/neural/NEURAL-SCOPE-20261114-FUS-DIRECTION/implementations/nested-training-preparation-v1/test_nested_training.py --output "$RUNNER_TEMP/fus-nested-training-check"
```
