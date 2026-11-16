# Marmoset condition-permitted training response adapter

This closes the unsafe response-loading branch identified by the existing
`marmoset-retinal-contrast-generalization` contract. It is a complete response
projection for the frozen 170 selected cells in both original preparations,
under each declared information condition. It is not a complete stimulus packet,
native model, scorer, authenticated original census or qualified benchmark.

The retained official `SpatiotemporalSCModel` loader at commit
`76b733421cc16131c2229e66a7714d8892de39d7` calls `load_responses` for both training
and test arrays before checking `responses` (dataio.py lines74–84 and104–107).
Its `load_responses` opens both NPY paths (277–294), and `load_stas` always opens
the white-noise STA (252–253). Therefore `get_data(responses=False)` cannot be a
protected candidate interface. This adapter never imports or calls that loader,
never constructs a test-response path, and never opens an original STA.

## Executable interface

```python
result = train_only.prepare_training(
    policy,
    policy_sha256=externally_frozen_canonical_policy_sha256,
    source_root=original_release_root,
    read_byte_budget=complete_allowed_source_bytes,
    output_byte_budget=complete_selected_count_bytes,
)
```

The result carries one typed count buffer for every permitted declared stream,
with full selected-cell, trial and frame support. Buffers are immutable raw
little-endian C-order primitives with explicit shape, dtype, units and SHA-256.
No rate conversion, averaging across repeats/seeds, fitting, smoothing, target
statistic or hidden original array object is returned. The owner can deliver
these count buffers with independently prepared stimulus/timing inputs. This
component does not serialize a final participant packet or run a candidate.

The canonical policy identity is required before any file access. Canonical
encoding is sorted compact ASCII JSON without nonfinite values. An arbitrary
caller cannot claim scientific authentication by setting a Boolean; the policy
must be frozen externally after original census, channel/row, timing and source
permissions have been independently resolved. Matching a policy hash proves
identity, not that its scientific assertions are true.

## Exact policy

Top-level fields are exactly `schema`, `task_id`, `source_release`, `condition`,
`cohort_evidence_sha256`, `complete_stream_census_sha256`, `preparations`, `streams`.
Schema is `marmoset-train-only-policy-v1`, task ID is the existing ID above, and
release is exactly `10.12751/g-node.t43ph1`, never the superseded DOI or four-retina
processed mirror.

Both source preparations must appear exactly once:

- `20220412_SN_252MEA6010_le_s4`
- `20220426_SS_252MEA6010_le_n3`

Each preparation has exactly `dataset` and `cells`; each cell has `cell_id` and
`published_class`. IDs are opaque32-hex identities with authenticated external
source joins. The entire fixed paper-selected roster has170 distinct cells:
51 `off_midget`,69 `off_parasol`,35 `on_parasol`,15 `large_off_pooled`. Large OFF is
a pooled label, not one established cell type. Per-preparation cell counts are
not guessed. Both must be nonempty; the complete external source ledger supplies
the actual split. The ten other reliable cells are not silently turned into
members of the classified170-cell estimand.

Each stream has exactly:

```text
dataset, stimulus, seed, source_cell_ids, train_trial_ids,
train_frames_per_trial, test_frames_per_trial,
timing_evidence_sha256, independent_extent_evidence_sha256, artifact
```

Stimulus is `WN` or `NM`. Each preparation has exactly one WN declaration with
`seed=null` and at least one NM declaration with integer seed1 or2. Every declared
dataset/domain/seed tuple is unique. This vocabulary comes from the official
loader; it does **not** establish which NM seeds are present in the original
release. `complete_stream_census_sha256` must bind a separately authenticated
complete census. The adapter cannot detect an entirely omitted native seed from
an invented policy, and a hash does not remove that qualification gate.

`source_cell_ids` and `train_trial_ids` are nonempty unique opaque-ID lists in
source order. Every selected cell of that preparation must be represented in
every declared stream. Raw arrays may include additional unselected rows; those
are validated but never returned. All selected cells, every declared training
trial, every frame and every allowed seed are preserved in the projection.

`artifact` contains exactly `bytes`, `sha256`, `dtype`, `shape`; shape is the full
declared `[source_cells,training_trials,training_frames]`. The metadata states the
positive test-frame extent independently, so the adapter never opens protected
response files to infer stimulus-loader dimensions. Timing/extent evidence must
come from qualified target-independent source metadata. The returned declared
test-frame number is not a native clock validation or a read of a protected
array's header. No arbitrary pathname field is accepted.

## Condition permissions

| Condition | Response streams supplied | Role |
| --- | --- | --- |
| `wn_to_wn` | WN training only | fit |
| `nm_to_nm_source_only` | NM training only | fit |
| `nm_to_nm_wn_calibrated_author` | NM training plus WN training | NM fit; WN calibration only |
| `wn_to_nm_source_only` | WN training only | fit |
| `nm_to_wn_source_only` | NM training only | fit |
| `nm_to_wn_wn_assisted` | NM training plus WN training | NM fit; WN calibration only |

The strict source-only conditions restrict **new** response-derived fitting and
calibration. They remain conditional on the historical WN/NM test-reliability
selection of the170-cell roster. This is not a newly target-unexposed cohort.
NM-only RF/STA estimation remains unvalidated; merely preparing NM counts does
not qualify that modeling condition. The mixed and assisted labels never become
strict transfer scores. Providing WN counts with a `calibration_only` label is
not enforcement of how a future program uses them; that needs a separately
reviewed fitting operator and matched experiment design.

Original cached WN STAs are not delivered in any condition. Allowed calibration
must later be recomputed or separately qualified from the permitted training
responses. This is not literal historical model reproduction and makes no
equivalence claim about author STA orientation, training choices or parameters.

## Physical response boundary

Only these official training leaf forms are constructed:

```text
data/white_noise/<dataset>/responses/train_responses_binned.npy
data/naturalistic_movies/responses/<dataset>/seed_<1-or-2>/train_responses_binned.npy
```

An insufficient total read/output allocation refuses before any file open. The
reader requires the exact SHA/extent and an ordinary single-link file, using
nonblocking/no-follow open and same-descriptor validation. Symlinks at the leaf,
FIFOs and hardlinks are refused. Ancestor-directory trust and effective mounts
remain the owner's responsibility; this API is not a filesystem sandbox.

The whole selected training body is authenticated, then its NPY v1/v2 header,
unique fields, complete3D shape, dtype, storage order and exact payload extent
are checked. Supported primitives are signed/unsigned1/2/4/8-byte little-endian
integers and float32/64 counts. All values must be finite, nonnegative and
integral. Fractional rates or normalized responses require a separate qualified
conversion; there is no implicit counts-per-second conversion. Objects, pickles,
structured dtypes, unknown encoding, malformed shapes and trailing bytes refuse.

Projection retains the exact original count bytes/dtype while selecting the
frozen complete cell roster. C and Fortran input layouts are handled explicitly;
output is C-order with exact cell/trial/frame identities. It does not concatenate
different seed sequences or average nonmatching repeats. All selected streams
must succeed before a result is returned; a later failure never returns an
earlier partial population as a successful result.

Read and output byte totals are admission arithmetic, not a measured process
peak: raw bytes, buffers, Python metadata and conversion temporaries coexist.
A future owner must separately select the full operation, memory/time/storage
allowances and output custody. No authentic operation is selected here.

## Evidence and remaining work

Ten new generated methods cover both preparations/all170 selected cells, all six
permission conditions, asymmetric source-row order and an excluded raw row,
both memory layouts, every supported primitive dtype, exact trial/frame bytes,
allocation and identity refusal, missing support, malformed fields and counts,
nonregular files and later-stream failure. Instrumented opens allow only the
selected training leaves; forbidden-domain training bodies and all test/STA
bodies are absent. These are software checks, not an authentic-data result.

The complete original170/180 census, biological animal mapping, native seed
membership, actual headers/clock/row identities and independent extent evidence
remain unqualified. The original47GiB source is not the expanded four-retina
processed library. Safe stimulus reconstruction, grouped frame split/context,
condition-specific RF/STA methods, competent baselines, complete scorer including
undefined-correlation coverage policy, protected packet execution and scientific
qualification remain separate. Frozen contract/registry/readiness and task count
are unchanged. This source can close the hazardous response-read behavior
without claiming to close those other obligations.
