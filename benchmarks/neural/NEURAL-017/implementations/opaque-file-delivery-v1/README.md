# Complete opaque packet files and artifact scoring

This operator companion makes the accepted in-memory opaque transform usable with authenticated files. It exports the complete public count packet, keeps the inverse mapping in separate operator custody, and admits a complete submitted NPZ before restoring its original axes and calling the unchanged numerical scorer. It does not execute a participant, qualify a transport, or complete the existing research campaign.

The preserved support is 1,721 training trials and 574 query trials, 137 observed and 45 withheld units, and all 140 bins at 5 ms from −250 through 445 ms. Every query requires 140 × 45 strictly positive finite expected counts: 3,616,200 predictions in total. Counts, masks, clocks and the permitted original condition labels are preserved. There is no smoothing, filtering, trial reduction, new past-only restriction, fitted reference or changed score.

`SOURCE_BINDINGS.json` pins six existing files from accepted commit `31c05a9d2675c7d4235f7a8a0df88c88981b9395`. The adapter captures and authenticates those source bytes before compiling them. It reuses `opaque-delivery-v1/delivery.py`, the complete operator's bounded array container functions, and the original `engine/investigation/grade.py` and `engine/metrics.py`. The current controller, scientific definitions and predecessor sources remain unchanged.

## Export

Provide the original public NPZ specified by the unchanged `registered-runtime/assets.json`: 113,599,728 bytes, SHA-256 `6c4ae66d25a3727fa00927cfee847f60bc84a55de41d5898ad6d4f3c9e48f884`. The stored panel fingerprint is `ba1b50199d8a326e1292b7e36bc6bb694ea8d3d6fa31df7bc910b45268924825`. The adapter checks the file pin before decoding and recomputes the complete public-content fingerprint through the accepted transform. This verifies the selected artifact; it does not independently rederive the raw NWB or prove upstream acquisition equivalence.

Use an independently generated, privately retained 32-byte key. Public and operator output directories must be absent, disjoint and have existing parents. They must also be separate from the source file, key and this implementation directory.

```sh
python3 -I -B /absolute/checkout/benchmarks/neural/NEURAL-017/implementations/opaque-file-delivery-v1/file_delivery.py export \
  --source /absolute/operator/original-public.npz \
  --key /absolute/operator/opaque-key.bin \
  --public-output /absolute/new-public-packet \
  --operator-output /absolute/new-operator-binding
```

The public directory receives only `public.npz`. The operator directory receives `binding.json` and `EXPORT.json`. The command prints byte counts and SHA-256 pins; independently retain the export-receipt pin before participant exposure. The private binding contains original identities and original axis order, which retains the source chronology. It must never be mounted to a participant. Sorted opaque IDs are not acquisition chronology. The key is not copied into either output.

Both directories are mode 0700 and their completed files are mode 0400. These are operator-custodied deliverables. A future participant running under a different UID needs a separately qualified readable projection or mount containing only the public archive; these permissions alone do not establish participant delivery or isolation. No entire operator folder or repository should be exposed as that projection.

Export changes the packet fingerprint and trial/unit axes. The existing campaign's programme, information-view and shuffle commitments cannot simply be reused. A later campaign must regenerate those commitments from the one frozen common export while preserving original chronology privately. This companion does not perform that campaign change.

## Complete submission and scoring

The participant output remains the original six-array schema:

- `expected_counts`: real numeric shape `(574, 140, 45)`, finite and strictly positive.
- `trial_ids`: every delivered query ID once, shape `(574,)`.
- `heldout_unit_ids`: every delivered withheld unit ID once, shape `(45,)`.
- `bin_left_edges_ms`: the exact original 140-value clock.
- `prediction_units`: Unicode scalar `expected_spikes_per_bin`.
- `panel_fingerprint`: the delivered public packet's Unicode fingerprint.

Trial and unit permutations are accepted when their IDs agree. Omissions, duplicates, wrong units, altered clocks, foreign fingerprints and malformed values refuse. The original parser checks the exact ZIP inventory, NPY shapes, primitive types and declared payload sizes before NumPy allocation. Its original 32 MiB compressed/expanded cap remains unchanged.

After independently capturing the submission pin, invoke grading with the original protected target and comparator files named by `registered-runtime/assets.json`:

```sh
python3 -I -B /absolute/checkout/benchmarks/neural/NEURAL-017/implementations/opaque-file-delivery-v1/file_delivery.py grade \
  --export-receipt /absolute/new-operator-binding/EXPORT.json \
  --export-bytes RETAINED_EXPORT_BYTES --export-sha256 RETAINED_EXPORT_SHA256 \
  --binding /absolute/new-operator-binding/binding.json \
  --submission /absolute/committed/predictions.npz \
  --submission-bytes CAPTURED_SUBMISSION_BYTES --submission-sha256 CAPTURED_SUBMISSION_SHA256 \
  --target /absolute/operator/original-targets.npz \
  --comparator /absolute/operator/original-reference.npz \
  --output /absolute/new-private-grade
```

The export pin must come from independently retained operator custody, never from the participant. The command captures the submitted bytes into its fresh private output directory, reuses the original bounded parser, verifies that captured file again, restores every original coordinate and writes `restored_predictions.npz`. Only then does the deferred loader inspect and authenticate the protected target/comparator files. The unchanged scorer writes `score.json`, retaining signed bits per spike, the original fixed condition/time comparison and undefined zero-target behavior. `RECEIPT.json` records the source and artifact identities, observed runtime versions, callback invocation count and result status. It does not assert that candidate code was run or that training-only selection was enforced.

The grade directory also retains the exact captured submitted NPZ. Invalid attempts after creation preserve their captured artifact and failure receipt; failures before creating an output produce an exception without an output receipt. Partial export directories are retained and have no complete receipt. Existing destinations are never overwritten, and the adapter performs no automatic retries or deletions.

## Boundaries and generated controls

This is trusted operator file custody. Private parent directories must remain controlled for the entire operation. The source does not provide an operating-system sandbox against a hostile same-user writer. Source snapshots and private candidate capture reduce mutable-path ambiguity; they do not establish global filesystem isolation. Public array containers have a 256 MiB compressed/expanded ceiling; candidate archives retain 32 MiB and ordinary metadata has a 2 MiB ceiling. These are file/container bounds, not hard CPU, RSS, elapsed-time or total disk limits. Future authentic export and grading need a separately budgeted operator process and storage allocation. The source release neither reserves that workload nor runs it.

The generated suite retains the full original shapes. It checks every exported count cell and retained condition/clock, private/public separation, original-axis restoration of reordered predictions, an independently calculated negative score across all 3,616,200 cells, undefined zero-spike behavior, missing and duplicate support, wrong units/clocks/fingerprint, nonfinite or zero predictions, extra payloads, source mutation before decoding, mapping/receipt changes, captured-file mutation before protected access, invalid private pins, symlink/role alias refusal and overwrite refusal. The test process prints its actual Python, NumPy and zlib versions and a bounded known fixture-write counter. Tests do not open any authentic task payload, private target, model or native workload.

```sh
python3 -I -B /absolute/checkout/benchmarks/neural/NEURAL-017/implementations/opaque-file-delivery-v1/test_file_delivery.py
```

This remains retrospective co-smoothing in one exposed Jenkins session. Removing explicit source identifiers does not anonymize distinctive signals, establish a pristine holdout or prove neural-information necessity. Artifact scoring does not complete the controller's authoring, frozen-method, execution, information-view, reporting or independent-review stages. Direct observation, typed viewing, tool-assisted investigation and frozen programs therefore retain their existing distinct qualification states. No authentic run, AI result, scientific readiness or SOTA claim is added.
