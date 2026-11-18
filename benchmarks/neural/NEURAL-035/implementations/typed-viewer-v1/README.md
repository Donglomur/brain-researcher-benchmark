# NEURAL-035 public trace viewer and response collection

This proposed component lets a participant inspect the complete permitted early
astrocytic fluorescence blocks and submit the original later-block ordering
scores. It addresses the missing typed-viewer component in
`understanding.v1.json`; it does not activate that condition or establish native
neural understanding. All 14 sessions, 1,012 session-local cells, five public
blocks per session and 28 later query responses remain required.

The trusted operator uses the existing `public-delivery-v2.load(folder, np)`
loader in a separately qualified NumPy environment, then calls
`Observations.from_loaded(rows)` and `Viewer(observations)`. Admission checks the
complete existing metadata and all public array dimensions before copying any
trace values. It makes immutable public-only copies and rejects nonfinite
values. The viewer independently validates every immutable observation axis,
the complete 14/1,012/28 identities and all finite samples before building its
lookup tables. Direct dataclass construction cannot bypass those checks or
silently collapse duplicate session/query IDs. No authentic data is packaged
here. The missing original delivery and
protected binding records are still missing; self-described metadata cannot
prove cohort authenticity.

`Viewer.handle(bytes)` accepts strict bounded JSON with four actions:

* `{"action":"catalogue"}` returns all opaque sessions, ordered cell IDs,
  permitted public block starts and the original 28 query IDs/times. It omits
  file paths, content hashes, biological identities and private outcomes.
* `{"action":"view","session_id":"…","block":0,"cells":[0,1]}` returns
  one SVG with one to eight separate cell panels. Block indices 0–4 correspond
  exactly to starts 0, 30, 60, 90 and 150 seconds. Each panel includes all 300
  samples at their original 10 Hz sample centres; no smoothing, sample selection
  or decimation is applied. Every cell is available. A cell's y scale is shared
  across its five public blocks, with numeric endpoints and processed-fluorescence
  labeling. Constant traces remain visible. Future block indices are rejected.
* `{"action":"answer","query_id":"…","ordering_scores":[…]}` commits
  one complete vector in original cell order. Every score must be finite,
  nonboolean and within [0,1]. Ties are valid. Invalid requests cannot partially
  commit, and accepted answers cannot be revised.
* `{"action":"finish"}` returns the unchanged
  `neural035-order-predictions-v1` JSON bytes only after all 28 vectors are
  committed. It then closes the state machine. Generated controls pass this
  document through the existing original output validator; they do not grade
  authentic observations.

The proposed fixed display budget is 10,120 views: enough for two complete
passes if every cell and public block is requested separately. A view has at
most eight panels and 200,000 encoded SVG bytes; action input is capped at
131,072 bytes. Reaching the display budget does not prevent answer submission.
This is a construction choice requiring selection in an eventual run protocol,
not a retrospectively imposed resource rule or a measured runtime budget.

This module is an operator API, **not process or filesystem isolation**. The host
must own the observations, expose only allowed serialized actions, freeze the
source and resource policy, record actions and complete outputs, and close the
participant before separately authorized protected grading. Those host/process
and persistence mechanisms are not supplied here. Never give a participant the
Python object, raw-array filesystem or evaluator. In particular, **SVG text is
not a raster vision condition**: a vision-only host must rasterize it and
deliver the image rather than the SVG coordinates. Raster readability, complete
authentic packet compatibility, transport isolation, process closure and actual
agent behavior remain unqualified. No raw query, target, flat-cell mask,
surrogate, mouse/context mapping or private callback is accepted by this API.

The original task is retrospective chronological within-session peak-order
prediction. It is not event-selected sequence reproduction, cross-animal
generalization or a causal-memory claim. Whole-session preprocessing and the
historical public release remain exposure limitations. The original rank-error
scorer and seven-mouse aggregation are unchanged. This component introduces no
scientific score, performance threshold, benchmark count or readiness promotion.

Run the maintained generated control module with
`python3 -B benchmarks/neural/NEURAL-035/implementations/typed-viewer-v1/test_viewer.py`.
During construction this must use the existing shared two-slot test pool. The
fixtures exercise all 14/1,012/28 identities through the actual viewer and
existing output admission, plus complete per-panel samples, extreme finite
values, forbidden actions, immutable commits and fail-before-array metadata
checks. They use a generated array-ABI witness, not authentic data or a NumPy
qualification. No model, fit, protected target or scientific scorer runs.

Source evidence is the existing local participant contract, full public loader,
understanding definition and scalar output validator pinned in
`SOURCE_PROVENANCE.json`. No fresh remote source availability is asserted.
