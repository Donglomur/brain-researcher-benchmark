# NEURAL-063 full-cohort census

This package prepares the original omission-forecasting data for a complete cohort census: **107 mice, 703 sessions, 1,936 planes, 133,066 published ROI rows, and the unchanged 73/15/19 mouse split**. It reuses the accepted versioned reader and original scientific functions.

The included profiles are disabled proposals. They contain `selected: false`, `runtime_qualified: false`, and unresolved input/component pins. A source package, successful generated controls, or a single-original reader comparison does not authorize an authentic census. An exact future profile needs separate resource admission and an owned runtime before any provider access.

| Stage | Required input | Produced evidence |
|---|---|---|
| `layouts` | Complete frozen cohort and versioned assets | Required dataset structure, shapes, dtypes, nominal chunks, filters, storage sizes, and a disposition for every original |
| `metadata_support` | Complete, exactly bound 1,936-plane layout bank | Complete native clocks, ROI mappings and presentation tables; unchanged agreement checks across each session's original planes; per-plane event support and exclusions |
| `chunks` | Complete metadata/support bank for all planes and sessions, with linked layouts | Support-derived physical storage coordinates, offsets, stored lengths, filter masks and transport-block coverage |

No stage projects dF/F values. The entrypoint does not offer a projection or model-running stage. Layout inspection and chunk-index lookup do not decode dataset values; scientific metadata inspection does decode clocks, ROI arrays and presentation columns. Fixed-block transport caches can contain adjacent signal bytes, so caches and outputs remain private operator evidence.

Success means completion of the **selected census stage** only. A complete 1,936-original disposition inventory can record a failed scientific metadata/support stage, including refusal of unknown VLEN payloads despite a complete layout bank. Census success does not establish finite dF/F values, full-cohort projection equivalence, model performance or benchmark readiness.

Every original has an explicit `complete`, `failed` or `unattempted` disposition. Execution stops at the first failure; later original IDs remain unattempted. The full disposition inventory preserves coverage and custody, but is not an exhaustive diagnosis of every original. An incomplete plane holds its session and the cohort. A complete bank is withheld when required coverage is incomplete. Resource or source failures never become scientific clock exclusions, and zero eligible events are recorded without dropping the plane. Earlier valid artifacts remain retained and charged after failure; an incomplete set does not automatically become a reusable checkpoint. The optional [typed partial-layout continuation](PARTIAL_LAYOUTS.md) authenticates every selected seed before provider access and keeps bounded-step success separate from full-cohort completion.

The scientific functions retain the original presentation normalization, schedule, binning, exclusions and query-frame privacy checks. Presentation agreement is checked across every original plane in a session. Native-clock support is then computed separately for each plane; a clock failure on one plane does not remove an event from another plane.

The physical chunk census preserves the existing read/hash path. The qualified projection reader materializes `dataset[left:right, :]` before valid-ROI reduction, and hashes that complete array. Therefore the census covers **all source columns** for every supported interval, even when only a subset belongs to the published valid population. Selecting only valid-column chunks would require a separate change and qualification.

For chunk shape `(ct, cc)`, source column count `C`, and supported interval `[l, r)`, the number of intersecting coordinates before union is:

```text
(floor((r - 1) / ct) - floor(l / ct) + 1) * ceil(C / cc)
```

Stored chunk offsets and lengths come from maintained h5py dataset-ID metadata APIs. A chunk at offset `o` with stored length `s` intersects the following number of fixed blocks of width `b`, clipped to the original object extent:

```text
floor((o + s - 1) / b) - floor(o / b) + 1
```

The census distinguishes unique storage coverage from repeated logical uses and possible repeated transfers. Unioned payload blocks exclude additional HDF5 index reads and do not predict cache eviction. Allocated contiguous data needs an addressable offset and its complete source-column row stride. Unallocated/fill storage is recorded explicitly without reading fill values or assuming zero-valued neural data. Positive storage with no usable offset, including unsupported compact storage, is refused.

Pre-allocation admission uses bounded structure counts, fixed-width array sizes, numeric chunk sizes, complete-table representations and per-session holdings. Unknown variable-length or reference payloads are refused before native value decoding. In particular, a later 512-byte image-name validation cannot certify the allocation needed to decode a variable-length string heap. Some authentic originals may therefore remain unadmitted by `metadata_support`; the package reports that limitation without replacing their values or shrinking the cohort.

Fixed-width scientific metadata reservations exclude the dF/F matrix. Nominal dF/F chunk shapes and raw sizes are recorded as evidence for a future projection budget; no current signal decoding or decoded-signal RAM qualification occurs.

Plane and session memory amounts are explicit reservation estimates. Transport-cache limits, numeric-array sizes and JSON output caps do not constitute a hard process-memory certificate. A future authentic invocation still needs its separately selected outer deadline, sampled-RSS stop policy and owned process-group cleanup. Any unknown or unbounded representation remains a refusal.

The three JSON profiles give finite **admission caps**, not expected transfer or a guaranteed complete-census budget:

| Profile | Ordinary artifact allowance | Metered local-read allowance | Mixed admission ceiling |
|---|---:|---:|---:|
| `profiles/layouts.json` | 671,088,640 B | 1,073,741,824 B | 6,065,969,152 B |
| `profiles/metadata_support.json` | 4,294,967,296 B | 34,359,738,368 B | 9,689,847,808 B |
| `profiles/chunks.json` | 536,870,912 B | 17,179,869,184 B | 5,931,751,424 B |

Each profile separately reserves `D = core.disposition_bytes` for the complete disposition report and `R = receipt_bytes` for the wrapper's final failure/resource receipt. Ordinary writes cannot consume either reserve. The total write allowance is `W = ordinary + D + R`.

The protected full-cohort disposition reserve is `8192 + 4096 * 1936 + 2048 * 703 = 9,377,792` bytes. It accommodates bounded compact name/bytes/SHA256/role references to partial plane and session artifacts. The final wrapper receipt has its own 16,793,600-byte reserve.

With at most 16 qualifying presentation tables, the layout source reserves `1936 * (8192 + (6 + 4 * 16) * 4096) + 33554432 = 604,504,064` ordinary output bytes. The profile's 671,088,640-byte ordinary allowance exceeds that structural bound. This establishes an output reservation; it does not establish network demand or a decoded-memory certificate. Metadata/support and chunk admission additionally depend on complete saved layouts and support summaries, and may legitimately remain unadmitted.

The proposed network profiles use 32,768 request admissions, a 4,294,967,296-byte response-body cap, 131,072-byte blocks and a 16,777,216-byte range-record allowance. With request cap `K`, record allowance `J`, block width `b` and body cap `B`, admitted requests are bounded by `min(K, floor(J / 512))`; reserved response bodies are bounded by `min(B, admitted_requests * b)`. Repeated, failed and evicted requests remain charged.

The separate conservative header-planning amount is 32,768 bytes per admitted request. Thus each profile's mixed admission ceiling is:

```text
W + B + K * 32768
```

That amount combines cumulative artifact writes, response-body allowance and a planning reservation. It is not a measurement of downloaded bytes or complete physical TLS/header/parser/kernel traffic. The existing reader checks accepted decoded headers after parsing; the planning charge does not make parsing a hard wire-byte bound.

At the chosen 128 KiB block size, even one fresh request for each original gives a conditional floor of 317,194,240 bytes for the layout pass including the same header-planning policy. The existing separate layout and metadata passes reopen every object with a fresh cache, giving a corresponding two-pass floor of 634,388,480 bytes before outputs and extra requests. A successful three-stage fresh-cache execution also rechecks the same-version layout for every original during `chunks`, including zero-event planes. Its corresponding minimum is 5,808 GETs, 761,266,176 body bytes and a conditional 190,316,544-byte header-planning charge: 951,582,720 bytes before outputs. Metadata/support refusal can prevent reaching that stage entirely. These are lower bounds, not completion budgets. The block size is a profile choice rather than a built-in default. A one-ROI original's transfer ratio supplies no full-cohort estimate.

Exact identities are required for the complete selection, versioned assets, previous complete bank, new component sources, accepted range-reader sources and six original scientific modules. Dependencies remain external and are bound by `DEPENDENCIES.json`; they are not re-exported here. The maintained runtime versions are h5py 3.16.0, fsspec 2026.6.0 and aiohttp 3.14.3, on the separately qualified interpreter. These version pins do not claim a complete portable wheel or ABI certificate.

Selective access retains the original URL/version/ETag/extent checks and requires accepted bounded range responses. It never falls back to whole-body acquisition. Range output keeps `full_object_BLAKE2b_verified: false`; array and chunk custody must not be presented as a provider whole-object hash verification. The original full-file authenticated mode remains unchanged.

The focused worker is `tests/test_census_generated.py`; `CI_COMMAND.json` declares its invocation and prerequisites. The public `tests/make_generated_plan.py` helper constructs a fresh generated-data plan from relocated exact source/runtime descriptors. Its pure `build_plan(core_source, wrapper_source, range_source, original_root, operation_profiles, evidence_root, worker_source)` API returns a dictionary without writing files, importing native libraries or accessing a network. The CLI writes one fresh PLAN JSON and prints only its SHA256; it never launches the worker.

From the package directory, this POSIX shell example constructs and then invokes the plan. It must run within the already admitted source-test pool or CI runner described below:

```sh
N063_CENSUS_CI_DIR="$(mktemp -d /tmp/n063-census-ci.XXXXXX)"
N063_CENSUS_PLAN_SHA="$(python3.11 -I -B tests/make_generated_plan.py \
  --component-root . \
  --range-source-root ../versioned-range-v1 \
  --original-root ../neural-063/complete-omission-v1 \
  --evidence-root "$N063_CENSUS_CI_DIR/evidence" \
  --output "$N063_CENSUS_CI_DIR/PLAN.json")"
python3.11 -I -B tests/test_census_generated.py \
  --plan "$N063_CENSUS_CI_DIR/PLAN.json" \
  --plan-sha256 "$N063_CENSUS_PLAN_SHA"
```

The plan binds `range_source`, `original_root`, `core_source`, `wrapper_source`, all three `operation_profiles`, `evidence_root`, the worker source and exact source/runtime descriptors. Both the plan path and evidence path must be fresh. The private construction PLAN is excluded from the public package; relocation requires a newly constructed and reviewed plan rather than copying its machine-specific paths.

The helper is a plan constructor, not a scheduler or runtime qualification. The selected source-test pool or CI runner must enforce the 180-second wall limit and declare one GiB of working RAM. A new runtime's compatibility remains a result of its own generated tests; neither the constructor nor these version pins certify a portable wheel or ABI combination. There is no authentic/provider/model operation in the plan.

The local ARM profile prefixes either Python script with `/usr/bin/arch -arm64 /opt/homebrew/bin/python3.11 -I -B`. This is local runtime context, not a portable-platform or census-suite outcome claim.
The selected control campaign must stay within its existing source-test execution envelope, at most one GiB of declared working RAM and 180 seconds. Its exact result and independent acceptance are retained separately. Documentation and dependency pins make no test-outcome claim, and earlier full suites need not be replayed.

No profile is funded by its presence in this repository. Future admission must use the current resource ledger without changing the program's cumulative acquisition cap or free-disk floor. A census establishes source coverage and support information; it does not establish model performance, a new scientific result, or a finished benchmark.
