# Version-bound selective NWB access for NEURAL-063

This is an alternative **operator preparation path** for the existing omission-conditional population dF/F task. It retains all 107 mice, 703 sessions, 1,936 planes, 133,066 published ROI rows, and the 73/15/19 mouse split. It does not add benchmarks, change the endpoint, or activate a solver condition.

The original full-file preparation mode remains unchanged. That mode authenticates each complete local NWB with SHA256 and the provider's BLAKE2b checksum. This alternative reads selected byte ranges from the **same exact S3 object versions**, validates response identities, and hashes consumed slices and produced artifacts. It explicitly reports `full_object_BLAKE2b_verified: false`. A multipart ETag is an identity token, not a content checksum.

## What is preserved

The six files in `ORIGINAL_SOURCES.json` supply the unchanged native ROI mapping, native-clock validation, presentation combination, omission schedule, support and privacy checks, population averaging, and artifact custody helpers. The adapter consumes the exact allowed published ROI set, includes every qualifying presentation table, and keeps every timing/clock exclusion. It preserves the original 15 half-open 200-ms bins, the final-history-bin baseline, the three prediction targets, and the original stable averaging order. It never substitutes provider event detections, reduces planes, or treats observations as independent mice.

The new schemas distinguish alternative custody from the existing canonical S00–S06 receipts. They do not masquerade as those receipts or set their full-file admission flags. A later explicit adoption step is required before a reference or participant programme consumes these alternative projections.

## Stages

| CLI stage | Inputs and operation | Completion boundary |
|---|---|---|
| `compile-assets` | Authenticate the saved source-selection and extent-index inputs, then each saved HEAD receipt. Produce a private fixed-version/ETag/extent manifest. | Saved metadata identity only; no request or neural payload read. |
| `headers` | Inspect only required HDF5 dataset layouts in every original NWB. | Shapes, dtypes, chunks and storage metadata; no array-value decoding. |
| `metadata` | Require the complete layout bank first; use the original native reader to obtain full clocks, ROI identities and presentation tables. | No dF/F value decoding or projection. |
| `schedule` | Require every plane; check presentation consensus within all sessions and run the original schedule, support and frame-intersection functions. | Complete pre-response schedule and exclusion accounting. |
| `project` | Recheck same-version metadata, then use the unchanged population function on every supported event and valid ROI. Hash exact consumed native slices. | All 1,936 planes represented; missing mouse support or excess bounds fails, never yields a scored subset. |

The first metadata/layout cache can fetch opaque bytes adjacent to requested HDF5 metadata. “No neural values decoded” does **not** mean zero neural bytes arrived in the operator's private cache.

## Complete native field selection

The required source is the original NWB dF/F, with its native clock and published ROI lineage. The reader retains these fields:

| Native path | Required content |
|---|---|
| `processing/ophys/dff/traces/data` | Layout and every supported omission's 15 native frame intervals; population reduction uses every original valid ROI. |
| `processing/ophys/dff/traces/timestamps` | Complete native clock, including units. |
| `processing/ophys/dff/traces/rois` | Complete DynamicTableRegion and its exact table reference. |
| `processing/ophys/image_segmentation/cell_specimen_table/{id,cell_specimen_id,valid_roi}` | Complete table identity, specimen lineage and valid-ROI census. |
| Every qualifying `intervals/<table>/{id,start_time,image_name,omitted}` | Complete presentation schedule, including all timing and clock exclusions. |

The existing reader verifies unit/conversion/offset attributes and rejects soft, external and virtual dataset links. ROI image masks and unrelated acquisition arrays are not scientific inputs to this endpoint. Full original experiment/session/mouse hierarchy and split metadata remain required.

The sealed HEAD census covers all 1,936 fixed versions and declares **855,657,138,152 bytes** of complete NWB bodies. The smallest is 227,971,260 bytes; the largest is 3,389,972,962 bytes. Grouping those same saved extents by original session gives a largest complete-session raw staging requirement of 4,000,174,531 bytes (up to eight planes). These are body extents, not selected-data transfer or RAM estimates. Sequential full-session staging could preserve full-file authentication, but would still transfer all original bodies and needs its own storage lifecycle.

For a fixed-width field, logical bytes are `product(shape) × dtype.itemsize`; an uncompressed chunk is `product(chunks) × dtype.itemsize`. An event slice additionally uses all source columns before the unchanged valid-column reduction, plus the slice hash copy and Python-list representation. Cache, touched compressed chunks, HDF5 metadata, clocks/presentations, output accumulation and variable-length heaps must be admitted separately. The historical one-file schema cannot certify these bounds for every original. A complete native layout/support census is still required.

## Maintained reader and limits

`range_io.py` uses fsspec HTTPFile with its bounded block cache and h5py's file-object interface. No HDF5 parser or general downloader is implemented here. Production accepts only the original Allen S3 origin and exact experiment path/version query.

Before each request, the adapter requires a bounded explicit GET range, reserves its complete response-body allowance and receipt, and enforces the cumulative request limit. The response must be HTTP 206 with matching URL, version ID, ETag, exact Content-Range/total and Content-Length, no redirects, and identity encoding. It refuses full-body fallback. fsspec's final cache block is clipped to the verified object extent. The wrapper refuses unbounded reads.

The selected installed versions are fsspec 2026.6.0, aiohttp 3.14.3 and h5py 3.16.0. `RUNTIME_SOURCES.json` records the static critical-source observations; it is not a complete environment or ABI certificate. The adapter explicitly disables aiohttp's private `_retry_connection` setting because its default idempotent retry occurs inside a single request-start callback. This pinned compatibility dependency must be requalified when the library changes. Cleanup closes h5py, the file/cache and the HTTP session in that order, including failure paths. The preparation runs serially in a dedicated process. It temporarily suspends cyclic garbage collection across h5py file construction, use and close, then restores the entering state. h5py documents that service-thread cyclic collection can deadlock against its global lock; the first generated runtime attempt timed out in an identity-refusal case without a stack, so this mechanism is a source-grounded risk rather than a proven diagnosis of that timeout.

Limits distinguish:

- Reserved HTTP **response-body** bytes, including failed requests; complete observed body bytes; and logical file-read bytes.
- Retained block-cache capacity (`block_bytes × cache_blocks`) and the separate declared HDF5 raw-data cache.
- The original ArtifactStore's cumulative logical writes, including failed writes, with a reserved final receipt allowance.
- Physical TLS/wire bytes, parser/kernel buffering, imports and some local source/input capture I/O, which are not measured by these counters. The operation clock is an admission/check deadline; an independently owned outer deadline and process/container limits remain necessary.

HDF5 decompression, Python lists and variable-length strings need additional RAM. Layout records identify object/reference-containing dtypes and leave their full decoded payload/chunk/heap size unknown. Fixed element-buffer size and HDF5 storage size are not bounds on variable-length decoded content. The header census must precede numerical budget selection; there is no all-cohort transfer/RAM forecast yet.

## Running an explicitly selected preparation

`run.py` accepts physical input locations as arguments; the source-selection and saved extent-index contents are pinned in `manifest.py`. No machine-specific absolute input location is built into the component. The original source root must match the six hashed modules and have no bytecode-cache directories; it is loaded once in a fresh process. An explicitly retained, exact private copy of that closure is supported. These frozen metadata inputs are operator dependencies and are not bundled as third-party data here.

Each stage takes a SHA256-bound operation profile, a fresh output directory under an already provisioned private parent, and the original implementation root. A profile declares the exact stage, local read allowance, total logical write allowance, per-artifact ceiling and final-receipt reserve. Network/native stages also declare every `Limits` field, exact runtime versions and prior runtime qualification. Profiles are supplied by the selected operation; the package does not invent a data budget or claim runtime qualification.

Example command shape:

```sh
python3 -I -B run.py headers \
  --selection /operator/source-selection.json \
  --assets /operator/assets.json --assets-sha256 ASSETS_SHA256 \
  --original-root /repo/benchmarks/neural/NEURAL-063/implementations/neural-063/complete-omission-v1 \
  --profile /operator/headers-profile.json --profile-sha256 PROFILE_SHA256 \
  --output /operator/fresh-headers --execute-authentic
```

`metadata`, `schedule` and `project` additionally require the preceding bank's exact `--input-bank` and `--input-bank-sha256`. The `compile-assets` stage uses `--extent-index` and does not require the authentic-operation flag. Input SHA identities and full-cohort checks are independent of that flag; the flag is an accidental-execution guard, not a security or approval system.

All intermediates, raw source identities, range receipts and query targets remain operator-only. Participant views must still use the separately qualified original hiding/aliasing and assessment path. This component does not grant participants raw source/network access.

## Qualification and remaining work

`tests/test_range_source.py` exercises the actual pure policy and projection-wrapper code with invented responses, fake cache/array surfaces and unchanged original pure scientific functions. It is not HDF5 or provider qualification. `tests/test_runtime.py`, when separately selected, exercises the real maintained stack against one invented local HDF5 fixture and a loopback server; the test-only origin override does not exist in production.

The operator’s separately retained exact-original qualification proposal specifies the next authentic comparison. Exact original identities, fold assignments and saved provider receipts remain private preparation evidence and are excluded from the public component. One exact original is compared through the full-file-authenticated reader and this range path. No authentic provider ranges, complete-file comparison, all-cohort native layout/support census, reference fits, model run, score or scientific equivalence is established by source presence or generated controls. The full original task remains unfinished until those separate dependencies are qualified.

Primary documentation: [PyNWB streaming](https://pynwb.readthedocs.io/en/stable/tutorials/advanced_io/streaming.html), [fsspec block cache](https://filesystem-spec.readthedocs.io/en/latest/api.html#fsspec.caching.BlockCache), [h5py file objects](https://docs.h5py.org/en/stable/high/file.html), and [aiohttp response hooks](https://docs.aiohttp.org/en/stable/client_reference.html).
