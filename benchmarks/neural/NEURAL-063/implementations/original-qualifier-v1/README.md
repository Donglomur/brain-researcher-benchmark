# Same-original qualification for NEURAL-063

This operator component tests whether the maintained selective reader reproduces the required arrays and scientific calculations from **one complete, authenticated original NWB**. It is an access qualification step for the full NEURAL-063 task. It does not add a benchmark, replace the full original cohort, establish session consensus, fit a reference model, or score an AI system.

The exact original, its private fold/lineage and the proposed resource profile remain operator-owned inputs. They are not bundled with this public component. The complete original cohort and split are still authenticated when selecting the qualification object; no canonical full-cohort acquisition guard is bypassed by passing it a one-row selection.

## What the implementation does

`acquire_original.py` performs one exact full GET using the already qualified aiohttp version. It checks the original URL/version/ETag/extent, requests identity encoding with If-Match, refuses redirects and retries, and streams into one exclusive immutable ordinary file while calculating SHA256 and provider BLAKE2b. Failed or uncertain writes remain visible; they never become authenticated native sources.

`qualifier.py` opens that file through the unchanged original native reader, which freshly hashes the complete file on the same descriptor before HDF5 use. It reads every required layout, clock, ROI identity and presentation field, derives the original omission schedule/support, and compares all supported omissions through the maintained range reader. The comparison requires exact consumed native slice hashes, shapes and dtypes, followed by the unchanged stable population calculations, all 15 bins and the original baseline subtraction. Complete metadata also has canonical equality checks.

The local and range custody claims stay separate. The local full file can be BLAKE2b verified; selective access alone cannot verify the provider's full-object checksum. No supported omission means an explicit metadata-only result. Any bound, identity, metadata, support or equality failure stops qualification and retains its costs. There is no truncation, alternate original, automatic retry or relaxed tolerance.

`run.py` binds a SHA256-selected operation profile, the immutable whole-cohort selection and saved asset manifest, exact source dependencies, the selected original's full row/asset hashes, and a fresh private output namespace. Authentic execution requires both the explicit CLI flag and a separately selected profile. These are accidental-execution guards; the external owner remains responsible for authorization and supervision.

## Source and runtime dependencies

`DEPENDENCIES.json` pins the critical sibling `versioned-range-v1` source files and the six unchanged original `neural-063/complete-omission-v1` modules. A fresh process and uncached exact source roots are required. The maintained versions remain aiohttp 3.14.3, fsspec 2026.6.0 and h5py 3.16.0. Their earlier generated qualification is not an all-platform or complete ABI certificate.

The range reader retains its strict response checks, bounded cache, no-whole-file fallback and serial-process cyclic-GC guard. The acquisition helper has its own total request timeout and no persistent retry. Closing an operation includes its file, session, connector and owned process resources.

## Resource and accounting boundaries

Each operation profile reserves these named writers before work:

| Writer | Content |
|---|---|
| `original.nwb` | One full raw acquisition and its first retained write, charged once. |
| `local_metadata.json` | Complete required metadata, schedule and every support/exclusion. |
| `local_projection.json` | Every supported original event and consumed native slice hash. |
| `comparison.json` | Exact comparison outcome and hashes of all range-produced values. |
| `acquisition_receipt.json` | Successful or failed full-GET custody and costs. |
| `range_receipt.json` | Complete accepted range ledger and failed reservations. |
| `operation_receipt.json` | Final outcome, intermediate identities and failure status. |
| External controller artifacts | Separately reserved profile, launch, log and supervision records. |

The raw acquisition is already part of the total write ceiling. It must not be charged again as a separate artifact. Every selective-range body remains cumulatively charged even if its cache entry is discarded. A persisted extra copy would also consume its own write allowance. Terminal receipts and controller records have reserved space that ordinary writes cannot spend.

Request/header/body limits, logical file reads, retained block/HDF5 cache capacity and logical artifact writes are separate counters. Parsed-header reservations are conservative planning charges, not measurements or hard limits on physical TLS/wire/interim-header traffic. Normal bootstrap source/import I/O is identified separately. Fixed-width field/chunk/slice checks do not bound variable-length decoded heaps.

The authentic CLI does **not** provide an OS RSS hard limit or replace an outer process supervisor. A selected owned launch path must supply the agreed RAM boundary and hard wall deadline. The private proposed profile stays unselected until those requirements, actual available grant capacity and upstream execution ordering are resolved. Running bare Python is not an admitted substitute for that supervision.

## Generated checks and future authentic use

`tests/test_qualifier_runtime.py` uses only the explicitly synthetic fixture in `FIXTURE_PROVENANCE.json` and a guarded loopback server. Its five methods cover full acquisition followed by same-file local/range comparison; strict header/redirect refusals; truncation, disconnect and deadline handling; BLAKE/write uncertainty; and no-request origin/exclusive-file/descriptor-ownership checks. Additional local-only cases verify that insufficient chunk/event budgets fail before new requests or output writes.

The fixture is entirely invented. It contains two omissions and a permuted valid-ROI mapping with an invalid distractor; it is not participant data or neuroscience performance evidence. Supplying the exact retained bytes makes these controls reproducible without depending on binary file-generation timestamps.

Git records the fixture as an ordinary non-executable file and does not preserve its read-only mode. After checkout, remove its write bits before the controls: they require immutable fixture custody. This changes no fixture bytes.

Run shape for the generated controls, in an explicitly selected compatible runtime and resource envelope:

```sh
chmod a-w tests/fixtures/omission_generated.nwb
python3 -I -B tests/test_qualifier_runtime.py \
  --range-source ../versioned-range-v1 \
  --original-root ../neural-063/complete-omission-v1 \
  --fixture tests/fixtures/omission_generated.nwb \
  --evidence-root /operator/fresh-precreated-generated-evidence
```

The generated campaign exercises the acquisition/comparison APIs. It does not execute the authentic CLI, supervise an authentic process, contact the provider or certify the full cohort. The authentic command additionally requires operator-owned selection/assets/profile paths, their exact hashes, the unchanged source roots, a fresh output path and `--execute-authentic`, under the separately selected supervisor. A successful one-original comparison still precedes the full 1,936-plane native layout/support census and the original task's complete scientific pipeline.
