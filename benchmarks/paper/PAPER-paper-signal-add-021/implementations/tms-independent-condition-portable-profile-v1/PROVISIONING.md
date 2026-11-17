# Owner-authorized provisioning

Authentic execution requires the complete accepted input and protected reference, independently admitted by the benchmark owner. This public source package contains neither. Do not replace missing authority with candidate-created receipts or guessed hashes.

## Complete required inputs

The owner configuration has exactly these eleven asset roles. Each is an absolute ordinary-file locator with exact byte length and SHA-256; no symlink or hardlink alias is admitted.

| Role | Required content and use |
|---|---|
| `input_manifest` | Complete `INPUT.json` for original scientific operands; at most 65,536 bytes. |
| `input_values` | Complete `values.f64`: 11,665,920 bytes, shape [4,62,2,7,28,15], little-endian binary64. |
| `projection_receipt` | Accepted original-source-only projection receipt binding both input files and zero reference reads. |
| `projection_outcome` | Unchanged original preparation outcome selected by the owner. |
| `projection_review` | Independent accepted projection review selected by the owner. |
| `identity` | Exact original-source geometry/provenance metadata; 5,214 bytes. Its fixed hash is an input identity, not an answer identity. |
| `paper` | Authorized exact article material; 1,996,585 bytes, shared by both arms. |
| `driver` | Authorized `generateFigure2B.m`; 1,872 bytes, B only. |
| `helper` | Authorized `publication__create_topo.m`; 2,546 bytes, B only. |
| `runtime_review` | Owner-private acceptance evidence for the exact selected candidate runtime. |
| `reference_review` | Owner-private acceptance evidence for the historical protected reference. |

Fixed source-material hashes are supplied in `OPERATOR_CONFIG_TEMPLATE.json` and authenticated by `portable_config.py`. The source identity's closed schema contains released-array geometry/provenance, not target coordinates, target values, support hashes or machine paths. Its informational study roster does not establish a physical-person mapping across conditions.

The candidate input directory contains only `INPUT.json` and `values.f64`, each a regular single-link file with mode 0400, inside a mode-0500 directory. All 15 stored positions are retained. No reference-derived target, mask, score or certificate may be used to construct these input files.

Separately supply the accepted private reference directory with `OWNED_REFERENCE.json`, `LAUNCH_RESULT.json`, `work/RUNTIME_OBSERVED.json`, `work/RESULT.json`, `work/REFERENCE.private.json` and `work/SUPPORT.private.bin`. Bind its exact private descriptor and historical constructor source-lock identity in the owner configuration. Those answer identities belong only in private bindings. The source expects the historical `authentic-interval-reference-01` protocol context; it is not a generic fresh-reference constructor. Moving a reference pathname does not recreate its historical observations.

## Two authorized acquisition routes

If the owner already holds an accepted full projection, `package/provision.py` can copy its two input files into a fresh sealed destination. It authenticates the unchanged original receipt and exact file identities, preserves every byte, reads no reference body and fetches nothing.

```text
PINNED_HOST_PYTHON -I -S -B package/provision.py
  --config PRIVATE_CONFIG_PATH --config-sha256 CONFIG_SHA256
  --source-lock-sha256 SOURCE_LOCK_SHA256 --output FRESH_OUTPUT_DIRECTORY
```

The lines above describe one command with owner-bound operands. The importer has a 120-second deadline; partial output is preserved after failure, and an existing output directory is refused. After import, create a new immutable owner configuration pointing to the imported files with the same content identities. Preserve the original receipt unchanged. The import itself has not been established by the two compatibility attempts, which reused the original input root.

If starting from the original data, obtain `masterTFR_allsubs.mat` through its authorized original distribution. The exact selected input is 298,290,277 bytes, SHA-256 `536e9513b13dc721cf60613334ee37ce546e7bf67154d95bd067ddc0f0023a95`. Use the separately admitted owner reader/constructor to call the unchanged `source_projection.project_original` API. That operation selects all original operands and preserves binary64/NaN bits; it never reads a target certificate. The required authenticated `identity`, `OwnedDerivative` and `TransferBudget` runtime closure is not bundled here. An original MAT file alone therefore cannot launch this profile. A new preparation needs its own complete custody, owner admission and independent result review; the protected reference also remains separately provisioned. This package contains no download script or signed acquisition URL and grants no data, article, code or image redistribution permission.

## Runtime and private execution

Fill the operator template privately with exact host Python and Docker CLI paths, file lengths and hashes; typed Unix-socket identity; the invoking numeric UID:GID; and a private workspace. The authentic owner requires isolated, no-site, no-bytecode Python 3.11.6 and an explicit Darwin or Linux declaration. Its immutable candidate image is fixed by the source. The actual accepted compatibility evidence is from one admitted host/image profile; accepting a platform string is not proof of equivalent execution on another host, operating system, architecture or version. Supply the exact image independently under appropriate terms. No launcher command pulls or installs an image.

The workspace, candidate input and protected reference must be disjoint. Create private `selections/` and `attempts/` directories under the workspace. Complete `RUN_MANIFEST_TEMPLATE.json` using a fresh attempt ID, the exact completed configuration hash, explicit owner authority, `model_calls=0`, two independently frozen program locators, and `comparator_calibration=false`. Store it as `selections/ATTEMPT.json` and authenticate it. Configuration and selection are mode-0400 regular single-link files. The attempt output must not already exist.

```text
PINNED_HOST_PYTHON -I -S -B package/outer_once.py
  --attempt-id ATTEMPT --run-manifest-sha256 MANIFEST_SHA256
  --source-lock-sha256 SOURCE_LOCK_SHA256
  --config PRIVATE_CONFIG_PATH --config-sha256 CONFIG_SHA256
```

These are command forms, not configured executable requests. The unchanged launcher enforces active-owner, total-owner and outer horizons of 300, 360 and 390 seconds. The owner must select and admit the exact complete runtime, asset set, image policy and resource bounds before authentic execution; the source release is not that selection.

Candidate mounts contain only the full input, exact task materials and that arm's frozen program. Owner configuration, reviews, reference, scorer and reports are excluded. Both candidates close before protected reference capture and assessment. Preserve complete streams, every output and all failure evidence; never reuse an attempt or report partial outputs as a complete case. Scores and target-dependent diagnostics remain owner-private. An ingestion receipt is not a score.
