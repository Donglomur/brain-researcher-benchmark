# Validated primitive adapter for NEURAL-100

This successor implements the existing primitive-to-count interface and fixes
silent input corruption before onset analysis. The preserved predecessor used
negative contact-table indices as Python negative indexing, passed unsorted
per-unit spikes to `searchsorted`, and allocated `np.empty` before verifying that
the ragged endpoint vector contained one endpoint per unit. A short endpoint
vector could therefore leave count rows uninitialized. Input-file hashes bind
bytes but do not validate those structural relationships.

`data_adapter.py` validates all nine primitive arrays before allocating counts:
one-dimensional numeric types, finite values, integer identities and indices,
unique unit/contact IDs, complete contact columns, nonnegative in-range
unit-to-contact row indices, known layer codes, and a complete chronological
ragged spike partition. Coincident spikes and empty unit segments remain valid.
Malformed data is rejected without sorting spikes, dropping units, or repairing
identities. Source order, unused contacts, and mixed layer labels at tied depths
are retained.

The count definition stays exactly `trial_start + arange(-50,51)/1000`, with
left-inclusive/right-exclusive bins and output shape trials × units × 100.
Timestamps remain native seconds; output values are integer spike counts, not
rates. The unchanged analysis core performs rate conversion and selects even
zero-based trials for evaluation and odd trials for development. The native
trial stop is a 100-microsecond click-pulse endpoint, not an observation-window
endpoint. Positive pulse durations and matching start/stop cardinality are
validated; a stop is not required to cover the 50-ms response window.

The existing nonnegative/nonoverlapping 100-ms window rule, 100,000,000-byte
per-record count cap, 8,000,000-byte NPZ bounds, file hashes, and streaming
one-record-at-a-time behavior are retained. `normalized(record, arrays)`,
`records(packet, manifest)`, and `load_manifest(path, expected_sha)` retain their
existing call signatures. The adapter uses the original `artifact_io` module
provided by the operator's source loader. It returns the same record shape to
the unchanged onset, aggregation, bootstrap, numerical, and claims scorers.

Before loading any array, the successor preflights every NPY member in the
archive. It accepts uncompressed, unencrypted members with NPY version 1.0,
2.0, or 3.0, a header of at most 10,000 bytes, and a one-dimensional primitive
integer/unsigned/float dtype. The declared element count times item size must
exactly match the physical payload length and fit the 8,000,000-byte bound.
Compressed members, object/structured dtypes, malformed declarations,
truncated payloads, and trailing payload bytes are rejected before `np.load`.
This closes a predecessor allocation hole: a physically tiny archive could
otherwise request a large array through its NPY shape declaration. The
uncompressed-member requirement is an explicit packaging restriction of this
successor; authentic packet compatibility still requires operator validation.

## Verification

Run `test_primitive_adapter.py` with an existing Python/NumPy environment. In
the coordinated revision, invoke it through the shared test pool. The suite
loads source-pinned predecessor code, reproduces its negative-index and
unsorted-input acceptance, and verifies rejection before count allocation.
It compares half-open bin counts to hand-specified results and a scalar
inequality oracle. It also passes 47 generated NPZ members for 41 invented
mice, with 39 A1/eight A2 records, through the real streaming interface and
unchanged full analysis core. All eight condition outputs must equal the
predecessor outputs for valid input. Generated signals are software controls,
not source measurements or a benchmark result.

All 15 tests passed in pooled run `neural01-n100-primitives-v2-04`, including
ten malformed NPY declarations with an `np.load` sentinel, compressed-member
rejection, valid v1/v2/v3 NPY readback, and the complete47/41 differential
control. The earlier 12-test run `neural01-n100-primitives-v2-03` preceded the
independent review's NPY preallocation finding and is retained. The first
launched attempt failed because the test's allocation spy also intercepted
NumPy validation scratch arrays; narrowing the spy to the three-dimensional
count buffer resolved that test defect. All attempts and the initial busy-pool
attempt remain in the external pool ledger. These checks establish software
behavior, not native qualification.

## Source and integration boundary

The scientific source remains [DANDI 001419 version 0.250521.2343](https://dandiarchive.org/dandiset/001419/0.250521.2343)
and the [Garcia study](https://doi.org/10.1038/s41467-025-61020-9), with official
layer-assignment code pinned to
`KatoLabUNC/Garcia_et_al_2025@78fda1573ce376629f75399c7e046fe31c0a6d85`.
The onset investigation is benchmark-authored. The original source audit and
current task contract were reused; no source request, authentic array read,
reference result, or candidate trial was performed for this change.

| Preserved source | SHA-256 |
| --- | --- |
| `investigation/source_repository/private/data_adapter.py` | `1acf5c26d1eaee7f04117fc68864537446bddba45312060d74a24e8f0afbf476` |
| `investigation/source_repository/private/analysis_core.py` | `8b1d19029d244701e93ee309a7ca9a1b0a1790474280cecd6ae2cf68d4c80502` |
| `investigation/source_repository/private/artifact_io.py` | `adf200892c5b850721d2ac479d506f7287bc325974c9d1ffcae8cedae4b6b817` |

Paths in this table are relative to the sibling `implementations` directory.
No predecessor body, source manifest, canonical task, or historical artifact is
modified. Integration requires selecting this adapter and updating the
corresponding immutable source/export pins; the old frozen runtime does not
silently import this successor. No runtime selection or scientific authority is
created here.

The task still requires the complete 47-recording/41-mouse panel and all eight
conditions. Direct observation remains unsuitable for the full numerical
endpoint; typed-viewer and case-adaptive tool delivery remain absent; the
frozen-program condition retains its separate source-only qualification.
Complete operator export and physical timing/anatomy validation remain external.
The absence of unit observation intervals still prevents certifying observed
silence; structural validity does not establish exposure, causal pathways,
manuscript cohort reconciliation, direct neural interpretation, or empirical
model performance.
