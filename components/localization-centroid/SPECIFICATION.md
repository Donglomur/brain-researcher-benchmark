# Public normalized ABI and scope

Task: `NEURAL-SCOPE-20261114-LOCALIZATION`. This component delivers the complete
previously accepted normalized scorer and one geometry-only negative control.
It does not choose original array roles, calibrate channels, extract waveforms,
manufacture animal identities or establish empirical reference provenance.

## Normalized neural input

`neutral_contract.validate_neural(owner)` requires an exact dictionary with:

| Field | Required content |
| --- | --- |
| `schema` | `localization-normalized-neural-v1` |
| `task_id` | Exact task ID above |
| `axis_names` | Two distinct ordered axis names chosen from `x`, `y`, `z` |
| `coordinate_unit` | `um` |
| `cells` | Exactly 11 unique opaque 32-character lowercase hexadecimal IDs |
| `conditions` | Exactly 16 distinct opaque IDs |
| `realizations` | Exactly 5 distinct opaque IDs |
| `artifacts` | Complete declared artifact list, no unused artifacts |
| `cases` | Exactly every one of the 880 cell/condition/realization combinations |

An artifact has exactly `sha256`, `bytes`, `role`, `dtype`, `shape`. Digest is
64 lowercase hexadecimal characters, bytes is a positive integer, and role is
one of `waveforms`, `template`, `probe_geometry`, `observed_support`. Dtypes are
primitive `<f4`, `<f8`, `<i4`, `<i8`, or `|b1`; shapes have 1–3 positive integer
dimensions. The geometry decoder further limits geometry to the four numeric
dtypes, never Boolean. Hash declarations alone do not authenticate a body.

Each case has exactly:

```text
case_id, cell_id, condition_id, realization_id,
sampling_frequency_hz, voltage_unit, sample_offsets,
channel_ids, inputs, requests
```

Case and channel identifiers are opaque IDs; cases are unique and refer to the
declared grid. Sampling frequency is finite and positive, voltage unit is `uV`,
and `sample_offsets` is a nonempty contiguous list of integer indices. Channel
IDs are unique and nonempty. `inputs` maps exactly the four roles to declared
artifact digests of the matching roles. With `N` channels, `T` sample offsets
and `S` requested individual spikes, the required shapes are:

| Role | Shape and dtype |
| --- | --- |
| `waveforms` | `[S,T,N]` |
| `template` | `[T,N]` |
| `probe_geometry` | `[N,2]`, numeric |
| `observed_support` | `[N]`, `|b1` |

Every request has exactly `request_id`, `kind`, `array_index`. IDs are globally
unique. Each case requires one `template` at index 0 and at least one `spike`,
with all spike indices `0..S-1` present once. The number of spikes may differ
between cases; the producer must preserve the complete actual requested support.

`neutral_contract.project` rebuilds the participant manifest from allowed fields,
adds only hash-named artifact paths, and removes owner cell/realization fields.
It does not copy files or enforce physical isolation. Source animal/group
identities and spatial references are never part of this input or projection.

## Geometry control and predictions

The producer authenticates its own published source and the complete canonical
neural manifest before body access. Canonical encoding is compact sorted-key
ASCII JSON, with nonfinite values disallowed. The CLI additionally authenticates
the exact raw manifest bytes before canonicalization.

Only selected `probe_geometry` bodies reach its callback. All unique geometry
bytes must fit the selected explicit allocation before the first callback. Each
body must match SHA-256 and byte extent. NPY versions 1.0 and 2.0, header length
at most 65,536 bytes, exactly the three unique fields `descr`, `shape` and
`fortran_order`, exact numeric N×2 shape/dtype, finite payload and no trailing
bytes are required. C and Fortran storage are both decoded explicitly. No
pickle, inferred transpose, coordinate calibration or favorable subset is used.

The contact-ID→coordinate map must agree across all 80 cases belonging to each
fixed cell. A matching channel/coordinate permutation is valid; relabeling or
changed contacts are refused. The point estimate is the unweighted mean of
every contact in each ordered axis. All requested spike/template rows receive
that point. A geometry-only constant estimate is a negative control, never
evidence of waveform understanding, physical stability or method competence.

Submission has exactly `schema="localization-predictions-v1"`, `program_sha256`,
`coordinate_unit="um"`, `axis_names`, and `rows`. Every row has exactly
`request_id`, `case_id`, `status="ok"`, `coordinate_um=[a,b]`, with finite
coordinates. It must cover every requested row exactly once. Frozen source
identity, axis order and units must match the owner contract.

## Trusted reference and complete scoring

The separate reference dictionary has exactly:

```text
schema="localization-owner-reference-v1",
coordinate_unit="um", axis_names,
reference_kind="nearest_contact_proxy",
reference_evidence_sha256, group_evidence_sha256,
undegraded_condition_id, cells
```

All 11 reference cells are required, each with exactly `cell_id`, `recording_id`,
`animal_id`, `coordinate_um`. Coordinates are finite and ordered by the same
axes. Opaque biological grouping IDs are owner evidence, not inferred from an
archive name; a recording cannot belong to two animals. The undegraded condition
must be a declared, source-adjudicated condition. Declared evidence hashes are
identities, not proof that reference/group evidence is correct. Original proxy
positions and their calibration/indexing require independent qualification.

`neutral_contract.score` validates the normalized input, reference and prediction
structure. Extra, missing, duplicated or invalid output causes
`PROTOCOL_FAILURE` and null headline accuracies. Complete requested denominators
and valid-row error diagnostics remain; there is no selective valid-only primary.
Unrepresentable coordinate distances are typed failures/null diagnostics rather
than clipped finite values. The owner must authenticate inputs before this pure
API call; no protected-file admission or candidate sandbox is implied.

For complete output, an individual prediction is correct iff its Euclidean
distance to the nearest-contact proxy is **strictly less than 50 µm**. Equality
at 50 fails. Per-cell/condition spike accuracy pools every spike over all five
realizations. Templates have separate complete support. Accuracy is then averaged
equally over cells within recording, recordings within animal, animals within
condition and all 16 conditions. This is the registered prospective balanced
metric, not a claim to reproduce an original pooled paper number.

The result retains per-row distances, per-case counts, cell/condition summaries,
animal/condition and condition summaries, plus separate primary spike and template
macro accuracies. Complete-support continuous summaries average cell medians
through the same hierarchy. Template stability is distance to the same cell and
realization's undegraded template estimate. Stability is a separate diagnostic;
zero values do not establish accurate localization or absence of biological drift.

## Boundaries still requiring work

Original archive roles and full normalization; geometry/channel-axis/calibration
provenance; source masks and condition labels; gain convention; spatial workbook
and animal/recording joins; target-independent competent native methods and their
dependencies/RNG; protected input/output execution and scientific qualification
remain outside this component. It contains no original data or targets and
establishes no native paper reproduction, SOTA result, campaign result or readiness.
