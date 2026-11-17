# Original and streaming preparation compatibility

This read-only operator adapter admits either a genuine original preparation
receipt or the separate streaming preparation receipt, preserving **686 records,
23 biological people and all 529 original fold-view identities**. It returns the
descriptor structure used by the unchanged reference-study request builder and
connects the same complete payloads to the existing detector projection API.

It never fabricates `neural010-original-preparation-v1` for streaming output and
never says that the old monolithic preparer executed when it did not. The actual
receipt body and descriptor stay in `prepared['receipt']` and
`prepared['receipt_pin']`; a route-independent `prepared['assessment_pin']` names
the still-protected assessment without opening it.

This package has generated software controls. It does not establish authentic
full-cohort preparation, runtime qualification, trained references, a signal
viewer, participant performance or scientific readiness.

## Admission boundaries

`admit(selection, io, require_all_views=False)` reads only selected metadata:

- the exact public `RECORDS` file;
- the actual preparation receipt;
- public panel and target-free metadata;
- for streaming, the selected configuration, independent anchor frames, current
  publication journal and target-free lazy view index.

It opens **no EDF/H5, identity key, annotation body, private per-record target
receipt, assessment, TRAIN or VALIDATION body**. It does not instantiate the
streaming `Original` or `Engine`, because those upstream components legitimately
read annotations and the private key. The operator's independent source,
execution and custody evidence must establish that the producer actually ran;
valid metadata cannot establish that by itself.

Before any receipt capture, its path must be exactly the selected private root's
`PREPARATION.json` or `STREAMING_PREPARATION.json`, according to the declared route.
An assessment or training-label path is rejected before opening it. Captures
enforce exact size/SHA256, duplicate-key rejection, strict numeric types,
canonical unlinked paths, stable file identity and prospective read reservations.
Inventory and journal bounds are finite. `FileIO` has a caller-selected aggregate
read cap up to 256 MiB and cooperative deadline up to 180 seconds. An independently
supervised launcher must provide hard process and filesystem containment.

The original route validates the exact 17-field producer receipt, immutable
original source/roster/vendor pins, zero model/scoring activity, original logical
cost metadata and all original view descriptors. It preserves the original
schema, status and actual receipt identity.

The streaming route checks the truthful streaming schema/status and exact payload
pins. It authenticates both configuration copies and the complete journal chain
against an **independently selected current checkpoint**, requiring exact matching
local/anchor inventories. It checks first-and-only genesis, nonrefunded cumulative
counter identities, original event clock bounds, full source bindings, all 686
source commits and staging retirements, final-intent identity and the actual
publication receipt. It never opens the private per-record receipts referenced
by those commits. The source bindings must implement the chb01/chb21 biological
merge, and the original metadata namespace and public roster pin must match the
fixed source contract.

External checkpoint custody matters: changing local and anchor histories together
is outside this adapter's protection. Do not derive the supposedly independent
checkpoint from the same untrusted files immediately before admission. A completed
artifact's metadata admission is distinct from authorizing streaming execution or
resume in a new clock domain.

## Selection and command-line entry

The selection has these common fields:

```json
{
  "schema": "neural010-preparation-compatibility-selection-v1",
  "route": "original",
  "receipt": {"path": "/operator/prepared/private/PREPARATION.json", "bytes": 1, "sha256": "<selected exact digest>"},
  "public_root": "/operator/prepared/public",
  "private_root": "/operator/prepared/private",
  "records": {"path": "/operator/RECORDS", "bytes": 13056, "sha256": "72b640d6a3fef4b40de255933d1403823d1655c56f93d69761105a653798fc08"},
  "selected_source_manifest": {"bytes": 1630, "sha256": "ad64dcbe1f9543725f2e4720ad974a608c512e8a2c833adad37dfd23119baef9"},
  "selected_original_roster": {"bytes": 270520, "sha256": "7485ba994f8d0a33f596e68d6f552d0849d911dd9c971bf9fbeee77dad1c4111"}
}
```

The one-byte receipt placeholder is an example of shape, not a usable authority.
For `route="streaming"`, use the actual `STREAMING_PREPARATION.json` descriptor
and add `configuration` (located descriptor), `workspace_root`, `anchor_root`
and `checkpoint`. Its checkpoint has exactly `sequence`, `sha256` and `total`,
where `total` contains `read_bytes`, `write_bytes`, `input_bytes` and `attempts`.
The public/private roots must be `workspace_root/prepared/public` and
`workspace_root/prepared/private`; the configuration must be
`workspace_root/CONFIG.json`.

After separately admitting source/runtime/resources and selecting exact pins:

```text
python3 -B /selected/bridge.py
  --selection /operator/selection.json
  --selection-bytes EXACT_BYTES --selection-sha256 EXACT_SHA256
  --read-root /operator/prepared --read-root /operator/RECORDS
  --read-bytes ADMITTED_LIMIT --seconds ADMITTED_SECONDS
```

Streaming admission also needs explicit read roots for its workspace and
independent anchor. Add `--view OPAQUE_PERSON/final` or an exact indexed inner view
name to resolve selected descriptors. `--require-all-views` requires every indexed
view to have materialized-file evidence and matching ordinary file extents. The
command prints operator metadata only; its private paths and view descriptors are
not participant observations.

The executable source manifest and Python import environment must be authenticated
by the independent launcher. No CLI flag grants source, process or scientific
qualification.

## Exact lazy views and reference requests

`prepared['views']` is an indexed mapping with exactly 529 names. Looking up one
name returns the exact original TRAIN/QUERY/SUPPORT descriptors, plus VALIDATION
only for an inner view. It checks selected file identity/extent metadata without
opening the label-bearing bodies. Isolated workers must authenticate actual view
bytes when an admitted fit/validation request authorizes those reads.

For streaming output, a view also needs a matching `view_intent` and
`view_complete` in the selected published journal. A missing view is a hard
requirement, not an invitation for the downstream controller to read annotations
and generate it. Use the separately admitted upstream streaming `view` command
to materialize exact original bytes, then select the resulting updated independent
checkpoint and re-admit the preparation. The adapter does not invent a viewer or
materialization service.

`compose_reference_request(prepared, job_id, reference_root, source_identity,
worker_limits, io, prior_operations=..., feature_bindings=...)` captures the
unchanged pinned `common.py`, `schedule.py`, `arrays.py` and `reference_study.py`.
It selects one exact job from the original complete schedule and invokes the
actual unchanged `ReferenceStudy.request` method with this prepared object.
It returns request descriptors and opaque-input paths; it runs no worker, model
or feature computation. Prior operation/feature provenance remains an independent
requirement, and this helper does not make caller-supplied prerequisites trustworthy.

A complete future reference campaign must require all views/materialization and
independently qualify its full native schedule. The 29,781 historical job count
remains a prospective source schedule, not completed computation, and the old
fixed candidate is not automatically a new participant detector.

## Separate detector projection

`export_detection(prepared, detection_root, io)` is a separate **upstream operator**
operation. It opens the exact protected source-provenance metadata and calls the
actual pinned detector `project_preparation()` function, retaining the complete
source/person alias join, channel duplicates and observed exposure. It returns:

- `projection.support`: the only participant-facing document;
- `projection.scientific_panel` and `projection.private_bindings`: protected
  operator documents, alongside the true preparation receipt descriptor.

It does not open the assessment or signal body. Returning private fields to an
operator is not authorization to mount or send them to a participant. Actual EEG
delivery, provider isolation, held-person training custody, candidate freezing,
independent reference streams and later protected scoring remain separate work.

## Actual successor runtime wiring

The separate `programme-source/implementation-v2` now closes 40 runtime source
files, the unchanged original preparer and reference workers, 13 central files,
and 12 exact historical shared gate/contract sources. Its real captured
`reference_study.preparation` dispatches both explicit compatibility routes;
the existing five-field original selector remains supported and reuses the same
strict original receipt validator. The actual phase-driver and release replay
calls both reach this function. Every route checks all529 materialized view
extents before native construction, using the caller's existing read budget and
original clock. The release implementation uses `prepared['assessment_pin']`
only after its original complete four-stream/observer barrier.

The successor entry manifests and central parent/shared bindings name the
same actual captured sources. Stale historical shared paths are replaced by
exact-byte task-local copies; gate/validator mathematics and reference worker
bodies are unchanged. Version1 remains frozen. The central deployment contract
explains the still-required independent runtime/source/custody registration.
Generated controls exercise real entry/bootstrap, phase dispatch, replay and
post-barrier descriptor use, with explicit generated doubles for unperformed
scientific/observer precursors. They establish software composition, not a
finished native graph, authenticated corpus or qualified scientific benchmark.

The standalone `compose_reference_request` still captures the pinned original
request method as an independent adapter control. `export_detection` invokes the
actual detector projection API but does not install a participant viewer or a
new candidate-detection campaign route. Neither implementation changes the
historical programme's analytical endpoint or resolves its target mismatch.

## Generated controls

`test_bridge.py` builds one immutable, full-support in-memory fixture from the
exact public filename roster and generated numerical descriptors. It uses the
unchanged original view generator for all 529 identities, retains only selected
view bodies in memory, and creates no authentic signal data. The controls exercise
both actual receipt identities, literal path admission, type/count rejection,
independent checkpoints, materialized-view selection, no protected-body reads,
the actual reference-request method and actual detector projection.

Run through the shared short-test pool with a fresh
`NEURAL010_COMPAT_CONTROL_ROOT`. Staged controls may set
`NEURAL010_ORIGINAL_ROOT`, `NEURAL010_DETECTION_ROOT` and
`NEURAL010_STREAMING_ROOT` to their existing pinned source directories. Those
paths select test source dependencies only; no production switch relaxes the
cohort, source hashes or read boundaries. Generated controls and metadata checks
are not evidence of an authentic prepared cohort, neural understanding or benchmark
performance.
