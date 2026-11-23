# Opaque delivery projection

This operator component fills the gap between source-ordered, natively prepared
arrays and the existing NEURAL-001 `PacketStore`. It preserves all 120 sentence
intervals per participant and the two or four released audiobook run groups. It
does not load raw MEG, perform FieldTrip preprocessing, normalize, fit a decoder,
read targets, or establish an admitted runtime.

`project_person()` accepts prepared 64 Hz arrays in original channel order. It
uses a private key to assign separate person, run, epoch, and query aliases, then
permutes whole query intervals using a target-independent keyed order. The native
calibration epoch order and whole-run grouping are retained. Alias derivation and
presentation order do not depend on signal values, duration, sentence identity,
SNR, intelligibility, or targets. Do not use the generated-control key for a real
delivery. Operators must preserve their secret separately and freeze a single
projection for every comparison condition.

`write_projection()` writes deterministic `training.npz` and `queries.npz` files
with the exact predecessor dtype/member conventions, and returns that person's
operator descriptor including byte/SHA-256 pins. It writes a separate private
`identity.json` mapping. The packet and custody roots must exist, be outside public
Git, and be separate and non-nested. New person directories are exclusive; existing
outputs are never overwritten. The returned descriptor still contains the
canonical person ID and must remain operator-only. Neither filesystem root is a
participant mount: the existing store serializes only the permitted training and
single-query views into fresh actor contexts.

The adapter requires the original native epoch number within each source run;
retained epochs must not be renumbered after native rejection. It requires query
indices 1 through 120 in source event order. Thus an operator must connect the
native preprocessing loss ledger and source identities explicitly. This code
checks structure and preservation, not whether an operator supplied authentic
inputs. It does not resolve the sub-02 audiobook source conflict or authenticate
the 3 ms timing correction. Caps inherited from the predecessor are rejection
limits, never permission to crop a person or omit a run.

For later protected grading, `reorder_intervals(source_target, source_offsets,
private_mapping["projected_to_source_zero_based"])` applies the identical full
permutation to a source-order target vector. It rejects duplicate or missing
intervals. Every boundary must lie within the supplied sample array before
signed differences are computed; malformed int64 offsets cannot wrap into
apparently valid lengths or invoke negative-index slicing. Shared-sentence
dependency groups must follow the same permutation;
that protected identity adapter and source preparation are still required.

After preparing all 24 people, pass the complete returned record mapping to the
existing `PacketStore`; it validates all 24 identities, all 94 run groups, and all
120 intervals per person. Complete cohort preparation and target alignment must
be independently checked before any participant delivery. This component does
not select a candidate, reference, provider, direct response renderer, or typed
viewer; no program performance or neural-understanding claim follows from it.

`test_delivery_projection.py` uses generated values only. It exercises full
24-person/94-run schema interoperability, unequal-length interval round trips,
target-independent identities, source metadata exclusion, owned array copies,
deterministic file pins, and malformed input rejection. It must run through the
coordinator's reviewed lightweight test pool. No authentic data is in these files.

Source basis: MEG-SCANS author commit
`32bfc690e28e7591b45d96615c59b2d53b6a7165`, source dataset snapshot 1.1.1 commit
`5c1d52d66c6bfe4c1c908d496df8a2ecbe3fece1`, and the task-local corrected scientific
contract. The operator interoperability target is the unchanged
`programme-source/implementation-v1/correction-v3/package/support/store-v1/packet_store.py`.
