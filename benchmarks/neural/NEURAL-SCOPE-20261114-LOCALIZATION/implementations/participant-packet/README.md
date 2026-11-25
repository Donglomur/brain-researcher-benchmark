# Complete physical localization participant packet

`packet.py` fills the physical delivery gap in the existing normalized-input
projection. It validates and copies every admitted waveform, template, probe
geometry and observed-support body, then publishes the existing participant
manifest. It preserves all **11 cells × 16 conditions × 5 realizations = 880
cases** and every requested spike/template. No reference argument, source
selection, estimator, fitted model or new scientific task is introduced.

This is an executable owner-side delivery component. It has only generated
software-control evidence. Authentic archive normalization, unit provenance,
patch/probe joins, animal/recording identities and competent author methods remain
unqualified. No authentic source body or private spatial reference was inspected
or prepared in this revision.

## Inputs and invocation

Keep this directory adjacent to the pinned `centroid-scorer` directory.
`packet.py` authenticates the 20,365-byte `neutral_contract.py` at SHA-256
`5069aca47290434f302c9c2b43fd51d81aa21c91f3ff281194bee04731aeeef8` before loading
its complete-grid validator and allowlist projection. Python's standard library
and Unix `O_NOFOLLOW`/directory descriptors are required. No NumPy, scientific
dependency installation or original author repository is needed.

The owner supplies an independently qualified `localization-normalized-neural-v1`
manifest and files stored as `SOURCE_ROOT/inputs/<sha256>.npy`. The manifest uses
the existing [normalized ABI](../centroid-scorer/SPECIFICATION.md). Its exact raw
bytes and SHA-256 must be supplied to the CLI. The array allocations are explicit
operator limits; they do not authorize a native preparation or enforce an OS
memory limit.

```text
python3 -B packet.py \
  --manifest OWNER_NORMALIZED.json \
  --manifest-bytes EXACT_RAW_MANIFEST_BYTES \
  --manifest-sha256 EXACT_RAW_MANIFEST_SHA256 \
  --source-root OWNER_NORMALIZED_INPUT_ROOT \
  --destination NEW_PARTICIPANT_DIRECTORY \
  --receipt NEW_OWNER_RECEIPT_OUTSIDE_PARTICIPANT_DIRECTORY.json \
  --total-input-byte-budget COMPLETE_UNIQUE_BODY_BYTES \
  --maximum-artifact-bytes LARGEST_ADMITTED_BODY_BYTES
```

This describes the interface and does not select an authentic execution. The
callable API accepts the **canonical** normalized-manifest hash instead:

```python
receipt = packet.stage(
    normalized_neural, source_root, new_destination,
    expected_manifest_sha256=canonical_normalized_manifest_sha256,
    total_input_byte_budget=complete_unique_body_bytes,
    maximum_artifact_bytes=largest_body_bytes,
)
```

## What is actually enforced

The unchanged validator requires the complete 880-case grid and complete request
indices. The builder snapshots the supplied JSON before validation, refuses an
insufficient whole-input allocation before source access, and reads only declared
hash-named bodies. Extra source files are not copied. Original source paths,
cell identities, realization identities, biological groups and reference fields
are absent from the participant projection. Opaque condition and request IDs
remain as required by the existing ABI.

Every body is authenticated by exact byte count and SHA-256. NPY versions 1.0
and 2.0 must have exactly the three unique header fields, declared shape and dtype,
a Boolean storage-order flag and exact payload extent. Pickles, object/structured
dtypes, nonfinite numeric values, trailing payload and noncanonical Boolean bytes
are refused. Waveforms, templates and geometry must be numeric; observed support
must be Boolean. Both C and Fortran orders are accepted and copied **byte for
byte**, with no cast, inferred transpose, crop, channel selection or waveform
recomputation. Complete waveform shapes remain `[spike, sample, channel]` and
template shapes `[sample, channel]` as declared in the existing contract.

All contacts must preserve their ordered two-axis coordinates throughout each
cell's degradation trajectory. A matching channel-ID/coordinate permutation is
accepted. This check cannot establish that source signal columns were correctly
joined to channel IDs; that remains a source-normalization responsibility. Axis
names, `um` coordinate units, `uV` voltage units, sampling frequency and complete
sample offsets are retained without calibration inference. Observed support
cannot be proven different from a private corruption mask by inspecting Boolean
bytes; its source role must be qualified independently.

The destination must be new. The participant manifest is written through a
temporary file and renamed only after complete body and trajectory checks.
Failure leaves an incomplete destination for owner inspection and never permits
reuse or selective continuation. Only a successful external receipt together
with its matching participant-manifest hash identifies a complete delivery.
The CLI creates that receipt exclusively outside the participant directory and
records failed delivery attempts there. This is not a crash-durable transaction
across the packet and receipt, and no automatic failure cleanup conceals partial
files.

The source directory, its `inputs` child and individual bodies refuse final
symlinks; body reads also refuse special files using nonblocking opens. Trusted
parent paths, exclusive owner access while writing, disk allocation, process
memory, deadlines, candidate execution isolation and reference custody are
external. The packet contains authenticatable observations, not an executable
participant or a filesystem sandbox.

## Access conditions and scientific limits

| Condition | Contribution of this component | Still required |
| --- | --- | --- |
| Direct observation | Same complete allowed observations can underlie a future display. | No-tools representation and response interface. |
| Typed viewer | Hash-bound waveform/geometry bodies are available for a future renderer. | Typed actions, complete target-free rendering and response capture. |
| Tool assisted | A real directory of admitted numerical inputs can be delivered. | Investigator execution/response transport and qualified scientific tools. |
| Frozen program | The same physical observations can be handed to an executor. | Candidate freeze, protected execution, complete response capture and scorer connection. |

All four access-mode qualification flags remain false. These are distinct
experimental conditions, not added task counts. The existing strict `<50 um`
nearest-contact-proxy endpoint, hierarchical spike scoring, separate templates
and stability diagnostics remain unchanged. Packet integrity proves neither
correct biological provenance nor neural interpretation.

`test_packet.py` uses invented arrays across the full grid to check physical
byte-preserving delivery, exclusion of an unrequested private sentinel, array
validation, geometry mapping, source-file refusal, complete support and CLI
receipts. It does not establish author parity, authentic data preparation,
benchmark readiness or model performance. Final test evidence and exact source
hashes are recorded in `SOURCE.json` and the external owner handoff.
