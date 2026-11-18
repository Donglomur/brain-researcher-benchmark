# Complete 54-fold viewer collection bridge

This operator-side component connects the previously reviewed one-fold
`typed-waveform-v1/FoldViewer` to complete, first-final NEURAL-084 prediction
collection. It freezes all 54 fold records before any participant delivery,
uses one fresh viewer at a time, and withholds prediction export until all
21,600 query responses have been collected. The existing prediction schema,
source representation, task, metric, comparator requirements and scorer are
unchanged. This remains source construction, not an executed benchmark.

## Relationship to existing implementations

`sequential-programme/sequential-view-v2/program/controller.py` already manages
the complete frozen-programme fit/infer workflow and 270 native phases. This
bridge does not replace or repeat that controller. It has no native process
launch, fitting, source-array staging, model artifact or private-gold operation.
Its separate `neural084-viewer-collection-v1` receipt is **not** a programme
`COMPLETE.json` or `GRADE_HANDOFF.json` and cannot substitute for those proofs.

The existing `full-cohort-scoring-v1/score.py` already requires complete
candidate, CCA, constant and frequency-permuted outputs before opening gold.
This bridge supplies only candidate prediction bytes in the unchanged
`neural084_scores_v1` interface. It cannot manufacture missing comparator
results or establish which method produced a score file. A future scorer call
still needs all four complete modes, authenticated pool/gold and separately
qualified delivery and execution provenance.

**Dependency:** integrate the accepted phase1 `typed-waveform-v1` package first.
`panel.py` verifies its exact 13,035-byte viewer SHA-256
`c3f7b05f1afd007096cbc31d0b5165fd9a6cbad26cbb07ce15e47cd6e2dce345`
before compiling the captured bytes. That viewer in turn checks the existing
protocol, public transport and frozen-programme contracts. No dependency is
implicitly assumed to be present in the current public repository.

## Trusted operator API

Construct `Panel(folds, max_requests=..., max_capture_bytes=...)`. `folds` is
the ordered list of all original public `fold001` through `fold054` records.
Each has 400 sorted opaque query IDs and the unchanged public descriptors.
Generation, class order and all 21,600 disjoint IDs are checked before delivery;
metadata are copied and pinned. These pins establish supplied-object identity,
not the authenticity of the underlying recordings or biological mappings.

The explicit resource operands are declared construction limits, not measured
authentic-workload requirements. Every operator open/close and participant
request consumes the request allowance, including rejected requests. Captured
prediction bytes cannot exceed either the caller's allowance or the original
54×262,144-byte hard ceiling. This is accounting within a trusted API, not an
OS memory or process-time limit.

For each fold in the fixed order:

1. The operator calls `open_next(training_raw, training_epoch, query_epoch)`.
   `training_raw` must be the exact captured public `training.json` bytes,
   matching the fold's frozen byte count/hash before decoding. The accepted
   viewer verifies all 21,200 rows, all53 donor people and exact class support.
   Provider callables remain trusted operator inputs; this bridge does not
   inspect or authenticate their source arrays.
2. Forward bounded typed JSON requests to `handle`. It reuses the original
   information/training/begin_queries/view/answer actions. Every donor row stays
   addressable; optional calibration closes before query access. All400 query
   responses remain first-final, in the original order, with four raw scores.
3. On a successful per-fold `finish`, the bridge captures the immutable
   prediction bytes, runs the existing frozen prediction validator, drops the
   active viewer and returns only a small fold-closed acknowledgement. It does
   **not** return the captured predictions through this endpoint. A subsequent
   fold cannot open until the current one closes.

After all54 close, `finish_collection()` returns a separate unqualified
collection receipt with exact fold/prediction pins and aggregate support.
Only then does `candidate_prediction("fold001")` (and the other53 exact names)
return immutable original-format bytes to the operator. No partial-panel export,
fold skipping, resubmission, alternate-mode export or comparator fallback is
provided. A training-admission or post-finish capture failure makes the
collection terminally unexportable. No automatic retry or resume is supplied.

For a private source layout, the operator can provide `viewer_source` and
`source_root`; these are trusted construction operands, not participant-selected
paths. The same exact source hash checks apply.

## What this does not establish

A fresh `FoldViewer` resets its API state. It does not reset an external model,
memory, code, process, conversation or other fold's exposure. Participant context
retirement, transport isolation, request/time/resource enforcement and complete
action recording remain external controller responsibilities. The object and
its Python attributes/providers must never be handed to an untrusted client.

The observation remains SVG text, with the phase1 finite-precision coordinates
and proposed128-view-per-epoch policy. This is not raster delivery, a native
no-tools condition or proof of readability. Authentic108-recording preparation,
array/schema/provider binding, full54-fold execution, independent protected
scoring and model performance remain unqualified. No new split, target, access
condition, numerical preprocessing, accuracy result or ready-benchmark count
is introduced.

## Focused controls

`test_panel.py` builds complete generated metadata with54×400 disjoint query IDs
and lazily constructs each21,200-row donor metadata object. It never constructs
or stores waveform banks; providers deliberately fail if accessed. The complete
collection passes both the existing frozen-programme prediction validator and
the existing full-cohort scorer's prediction admission. No gold is opened.
Negative controls cover missing/reordered/overlapping/mixed-generation folds,
invalid donor support, changed metadata bytes, incomplete collection, stale
answers, training retirement and exhausted request/capture allowances.

Run `python3 -I -S -B test_panel.py` after both components are integrated. Private
checks may set `NEURAL084_SOURCE_IMPLEMENTATIONS` and `NEURAL084_VIEWER_SOURCE`
to the exact accepted source locations. Central CI enrollment belongs to the
sole integrator; this proposal does not modify it.
