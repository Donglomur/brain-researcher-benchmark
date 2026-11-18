# Original-input custody and command preparation

This owner-side operator stages the three exact original inputs before any native replay is authorized, then binds commands for either a new original producer run or verification of an existing bundle. It never launches those commands, downloads data, parses the workbook, installs a runtime, or evaluates R.

The inspected source base is commit `4010072594f139371370c9828ecfcc53113f879f`, tree `7ddd70514966882f824a9c270cde51896d3ba1c7`. Existing trusted-owner configuration prepares symbolic candidate assets and locator metadata. Existing replay code copies caller inputs inside a native run. This component supplies the missing preparation step and reuses the existing pinned `trusted-owner/engine/runtime/custody.py` reader/writer.

## Stage exact originals

The fixed original revision is `90e8f324f78701bc3b1a8af3b79685ca91084d05`. The code accepts exactly:

| Role | Original repository path | Bytes |
| --- | --- | ---: |
| workbook | data/studyInformation/studyInformation_publication.xlsx | 63870 |
| script | scripts/s3_RmetaAnalysis.R | 18666 |
| lock | renv.lock | 60147 |

Their exact SHA256 values are fixed in `ASSETS`; there is no CLI pin override. Together they contain 142683 bytes. Source acquisition and authorization to read these actual inputs must precede this operation. No acquisition occurred while developing this component.

Create a JSON request with exactly this shape, replacing paths with existing absolute, canonical, non-symlink paths:

```json
{
  "schema": "nider_original_input_locations_v1",
  "inputs": {
    "workbook": "/owner/original/studyInformation_publication.xlsx",
    "script": "/owner/original/s3_RmetaAnalysis.R",
    "lock": "/owner/original/renv.lock"
  }
}
```

Use the actual request digest, never a placeholder:

```text
python3 -I -B prepare_original_inputs.py stage --implementation-root IMPLEMENTATIONS --request REQUEST.json --request-sha256 REQUEST_SHA256 --output NEW_PRIVATE_STAGE
```

`IMPLEMENTATIONS` is this task's absolute implementations directory. The output must be absent, outside implementation/source trees, and immediately inside an owner-owned directory with no group/other permissions. All source/consumer identities pass before output creation. Inputs must be regular unique files, not symlinks or hard links. Staged copies have independent inodes and mode 0400. The source locations are historical observations; their later movement does not alter the staged copies.

A successful result identifies `CUSTODY.json`. It records both source and staged identities, the twelve pinned existing consumer files and this operator's identity. `INCOMPLETE.json` is removed only after completion metadata was written. Any failure preserves partial files and attempts `FAILURE.json`; a stage with either marker cannot be rebound. Failed outputs are never silently deleted or reused.

These are owner-controlled local copies. File hashes establish equality to the fixed recorded identities, not remote transport history, input rights, scientific validity, immutability against the owner, or runtime admission.

## Bind commands without executing them

The bind request has exactly these common fields:

```json
{
  "schema": "nider_original_command_binding_request_v1",
  "operation": "producer",
  "custody": {"path": "/owner/stage/CUSTODY.json", "bytes": 123, "sha256": "ACTUAL_SHA256"},
  "python": {"path": "/absolute/regular/python3", "bytes": 123, "sha256": "ACTUAL_SHA256"},
  "rscript": {"path": "/absolute/regular/Rscript", "bytes": 123, "sha256": "ACTUAL_SHA256"},
  "owner_runtime_identity": "owner-selected-runtime-description",
  "arm": "A",
  "artifact_byte_limit": 134217728,
  "bundle_output": "/owner/private/NEW_BUNDLE",
  "producer_timeout_seconds": 1800
}
```

The displayed byte counts and SHA placeholders are explanatory only and fail real validation. Supply measured regular-file executable identities; resolve symlinks to canonical paths before preparing the request. The Python and Rscript files must be distinct, unique regular files, executable, and no larger than 8 MiB each. Their hashes and executable bits do not demonstrate their language version, packages, genuine behavior, architecture, or suitability. Those remain external runtime checks.

```text
python3 -I -B prepare_original_inputs.py bind --implementation-root IMPLEMENTATIONS --request REQUEST.json --request-sha256 REQUEST_SHA256 --output NEW_COMMAND_BINDING.json
```

For `producer`, the binding emits the existing `replay_companions.py` command with all three staged paths, owner runtime identity, arm and prospective bounds. This is the **new original 57-expression producer**; it involves native work and requires separate admission. The output bundle must remain absent. The binder does not create it.

For `qualification`, retain all common fields but replace the two producer-specific fields with:

```json
{
  "payload_view": "/owner/existing/exact26-view",
  "native_component_root": "/owner/selected/native-artifact-consistency",
  "native_receipt": "/owner/private/NEW_NATIVE_RECEIPT.json",
  "verification_wall_seconds": 180
}
```

The existing view must have exactly the 26 payload paths in `PAYLOADS`; the published 28-file bundle also has two publication files and cannot be passed directly. This check only reads directory metadata. It does not parse or authenticate payloads, create a view, assert original provenance, or certify an authentic 17-artifact bundle.

The ordered commands are:

1. Existing corrected `companion_contract.py` full bundle closure.
2. Accepted `native_verifier.R`, using the pinned existing exporter and collector, against the 17-artifact native subset.
3. Accepted `receipt_bridge.py` to bind the resulting receipt to payload identities.

The native verifier and bridge are accepted private sources absent from the inspected published base. Their exact source hashes are required, and the output retains `reviewed_private_requires_root_selection`; copying or identifying them does not select or integrate them. The operator also does not rerun their previous tests.

Root must authenticate the owner publication, explicitly select these sources, establish an appropriate locked R environment and admit the finite verification operation. A view made with hard links shares source inodes: neither its source nor view may be written or chmodded; before/after checks alone do not provide an immutability barrier. Supply external read-only handling. A native receipt must be a fresh file outside the view, stage and source trees.

Every bind rechecks staged bytes, the custody document, exact current consumer files and executable file identities. The resulting command document must itself be pinned, reviewed and rechecked at dispatch. Source changes require explicit rebinding. No dispatcher is included. Bounds are prospective requests, not hard enforcement by this preparation tool; one-thread environment values are recorded for later admitted execution.

## Scientific and runtime limits

All outputs retain false values for producer execution, native verifier execution, runtime admission, scientific agreement and readiness. The tool cannot establish original RDS authenticity from metadata, prove that a Bayesian fit consumed an adjacent input object, or report numerical agreement. The original full120 support and row ledger remain required. The original amy_self DL rating-n versus Bayesian questionnaire-n distinction, Fisher-z values/raw weights, inclusion BF versus pairwise model BF, and primary null finding versus Figure5b distinction are unchanged. Neither larger correlations nor smaller p-values become an improvement criterion.

## Focused controls

The 21 generated methods exercise immutable-input pins, independent copies, symlink/hardlink rejection, nonblocking bootstrap rejection before a FIFO body read, invalid bootstrap paths, blank/NUL runtime labels, partial completion failure, no overwrite, changed staged/consumer/runtime bytes, receipt forgery, producer/qualification command separation, exact26 filename closure and private native source gates. They patch expected input pins only inside the test process and use opaque synthetic bytes; the CLI has no such override. Synthetic executable markers are never executed. A generated payload view cannot establish native correctness.

The narrow invocation is:

```text
python3 -I -S -B tests/generated_controls.py --implementations ABSOLUTE_TASK_IMPLEMENTATIONS
```

Run it only within the authorized existing two-slot pool. It uses no subprocess, R, model, network or authentic input. The test report, not this source README, records whether that invocation passed. The test's printed output is bounded to 16 KiB.

