# NEURAL-099 portable source package

This package supplies local metadata regeneration, the two-implementation count preparer, and matched current-trial observation/collection interfaces for the separately defined assumed-support condition. It contains source, public source metadata and generated examples. It contains no prepared signals, private click-time tables, case files, predictions or populated execution manifests.

The corrected portable entry points have now reconstructed all 9,867 cases and the full count packet from the selected 26 source files on the specified local runtime. Both output byte counts and SHA-256 values exactly match the original commitments; see the [reconstruction status](RECONSTRUCTION_STATUS.json). The earlier private preparation remains recorded in the adjacent [preparation receipt](../PREPARATION_STATUS.json), and the [identifier storage status](IDENTIFIER_STORAGE_STATUS.json) preserves the header evidence behind the signed 32-bit unit-ID repair. The preceding portable attempt stopped at the incorrect 64-bit requirement before counting. A subsequent full-cohort fixed history-copy engineering control completed collection and unchanged scoring on 2026-11-18 UTC; see the [engineering status](PAIRED_ENGINEERING_STATUS.json). Reconstruction on other machines or native stacks, participant isolation and model/reference performance remain unqualified. This execution does not establish physiological coverage, model performance or submission readiness.

## Fixed data and scientific contract

Use DANDI 001421 version **0.250521.2343**, the complete selected MGN component. `contract/SOURCES.json` gives the exact 26 official source assets, byte counts and SHA-256 values. Place already acquired files directly under an operator-selected raw directory using their source basenames; the manifest validates that this mapping is unambiguous. There is no download or network helper.

`contract/DECLARED_SUPPORT.json`, `COHORT_BINDING.json` and `PROTOCOL.json` are exact copies of the selected public contract. They retain 26 source-declared animals, 5,238 trials, 49 available region cells, 1,387 named good/MUA clusters and 666 unassigned clusters in the audit. All 9,867 regional cases are required. Unknown animal aliases remain a limitation.

The response is deposited events per retained source cluster per nominal second over [0,100) ms, in 100 half-open 1-ms bins. Permitted history covers [−100,0) ms. Empty eligible clusters retain their denominator contribution; missing regions are unsupported, not zero targets. Physical stimulus-onset parity and observation coverage remain unverified. Whole-session sorting may use retrospective information, and clusters are not individual neurons.

The frozen primary equal-animal → available-region → trial → bin MSE, secondary MAE and five-bin aggregation MSE are preserved. The original sequential, four-non-query-fold trained programme and competent reference remain separate from the two zero-label, fresh-current-trial profiles in `paired/CONDITIONS.json`. Those profiles do not train, refit, retain cross-trial state or receive benchmark response labels. A live tool-using agent is a different mode. Comparisons do not by themselves establish native neural understanding or a causal effect of tool access.

## Supported environment

Generated checks need a supported POSIX Python 3 interpreter and the standard library. Authentic preparation additionally requires exactly **h5py 3.13.0, linked HDF5 1.14.6 and NumPy 2.2.6** in the selected interpreter. The linked HDF5 version is checked, not inferred from the h5py version. No installation is performed by this package.

Set `HDF5_PLUGIN_PRELOAD=::` before starting Python. Native entry points refuse a pre-imported h5py stack or different runtime versions. They reject indirect dataset links, external/VDS storage and unreviewed filters; supported filters are built-in deflate, shuffle and Fletcher32. POSIX no-follow descriptors are required. Use an interpreter compatible with the host architecture; no personal virtual environment or platform-specific ARM launcher is embedded here. Native commands intentionally omit `-S`, so the compatible interpreter can find its installed packages.

Logical array and output limits do not establish a total native-memory bound. Variable-length metadata strings can allocate native heap memory before their returned lengths are checked. Use separately qualified process/resource supervision for authentic operations. The source execution flags are accident guards, not authorization or a supervisor.

## Local preparation

The following are templates for a separately authorized, bounded operator run. Replace every placeholder. Raw files, generated metadata and count outputs stay in private operator directories outside the repository. Output directories must be fresh; failed/partial directories are retained and cannot be silently reused.

```sh
NEURAL099_PACKAGE=/ABSOLUTE/OPERATOR/portable-v1
NEURAL099_PYTHON=/ABSOLUTE/OPERATOR/compatible-python
NEURAL099_RAW=/ABSOLUTE/OPERATOR/official-nwb-files
NEURAL099_METADATA=/ABSOLUTE/OPERATOR/fresh-private-metadata
NEURAL099_COUNTS=/ABSOLUTE/OPERATOR/fresh-private-counts

env HDF5_PLUGIN_PRELOAD=:: "$NEURAL099_PYTHON" -I -B \
  "$NEURAL099_PACKAGE/preparation/regenerate_metadata.py" \
  --execute-authenticated-metadata-regeneration \
  --raw-root "$NEURAL099_RAW" --output "$NEURAL099_METADATA"
```

Regeneration authenticates the four exact public contract files before native initialization. Each NWB is then hashed completely and read on the same descriptor. It preserves original unit row order and literal anatomy/quality, reads only the required metadata and three click columns, and does not decode spike/index values. It rejects any altered full-cohort support or canonical case-file commitment before writing schema, click metadata and a relocatable `BINDING.json`. Private regenerated timing and schema provenance may differ from historical receipts; canonical cases and counts may not.

Require successful supervised completion and verify the resulting files and receipt. `METADATA_COMPLETE.json` or `BINDING.json` existence alone is insufficient after a write/fsync failure. The completion output reports the binding byte count and SHA-256. Pass those verified values explicitly to the counting launcher:

```sh
env HDF5_PLUGIN_PRELOAD=:: "$NEURAL099_PYTHON" -I -B \
  "$NEURAL099_PACKAGE/preparation/launch_preparation.py" \
  --execute-authenticated-preparation \
  --binding "$NEURAL099_METADATA/BINDING.json" \
  --binding-bytes VERIFIED_BINDING_BYTE_COUNT \
  --binding-sha256 VERIFIED_BINDING_SHA256 \
  --raw-root "$NEURAL099_RAW" --output "$NEURAL099_COUNTS"
```

Bindings resolve relative metadata/coordinator paths against the binding location and authenticate exact bytes. The counting stage authenticates the full sources again: metadata regeneration and counting require **two full 455,615,424-byte source hashing passes**. Counting retains the original selected-unit slicing, two independent counting implementations, per-cluster and regional comparisons, and full packet round trips. Before completion it requires the committed canonical case-file and count-packet sizes and hashes. Generated validation does not establish that this authentic reconstruction has succeeded on another machine.

The private output is a little-endian uint64 packet with 100 history then 100 response bins per case, plus case metadata and verification receipts. The count stage's 24-MiB logical artifact ceiling and metadata stage's 2.25-MiB ceiling are internal bounds, not allocated disk or runtime permission. A completion marker must be combined with successful supervised exit and independent artifact verification before downstream use.

## Paired observations and collection

See [paired setup and access conditions](paired/README.md). `paired/EXECUTION_MANIFEST.example.json` is a deliberately non-executable generated template with operator-path and procedure-hash placeholders. Bind and freeze both actual procedures before any query access. The trusted controller verifies the exact complete packet and cases, releases matching current-trial observations, and locks both arms before reading the next trial's history.

The operator JSONL interface is not candidate containment. Never provide a participant the private packet, case file, journal, controller object or entire operator process stream. Actual no-tools enforcement, fresh candidate contexts/processes and filesystem/cache/provider isolation remain unqualified. The collection interface launches no model, programme or baseline and computes no scores. The separately invoked [completed-collection evaluator](paired/README.md#completed-collection-evaluation) connects sealed predictions to the frozen scorer.

The [fixed history-copy engineering run](PAIRED_ENGINEERING_STATUS.json) exercised both complete schema arms on all 26 source-declared animals, 5,238 trials and 9,867 regional cases per arm, including all 49 available region cells and 1,387 retained good/MUA clusters. It copied current history rates unchanged, with no AI model, fit or trained baseline. Collection and evaluation took 10.335 and 20.452 seconds of recorded native-stage wall time, excluding the interval between stages and review time. Both stages closed successfully. The evaluator checked the complete journal, both arms, and original observation hashes before response decoding; both full score objects matched. This confirms the local fixed-control workflow, not AI capability, trained-reference performance, isolation, physiology or readiness.

## Generated validation

Run the generated suites from any working directory:

```sh
python3 -I -S -B /ABSOLUTE/OPERATOR/portable-v1/run_generated_tests.py
```

The bootstrap discovers preparation and paired tests in separate Python children. It supplies module-state separation, not process containment or its own deadline; the outer supervisor supplies runtime/resource bounds. Fixtures are generated, including fake HDF5 objects. They do not import the native scientific stack or read authentic NWBs/counts. The repository checkout must be writable for temporary generated fixtures.

`SOURCE.json` and `VALIDATION.json` retain the 2026-11-17 UTC source/generated-control cutoff; their then-unexecuted paired runtime fields are historical. The subsequent [engineering status](PAIRED_ENGINEERING_STATUS.json) records the 2026-11-18 UTC authentic fixed-control execution. The saved generated qualification scope remains unchanged: the historical 118-method full run, subsequent 11-method affected metadata suite, and later 18-method completed-collection evaluator suite are separate. The current source declares 82 preparation and 56 paired methods. The existing 120 methods were unchanged and not rerun for the evaluator addition; no full 138-method run is claimed. No internal machine histories, private source-output maps or populated execution manifests are part of the release.
