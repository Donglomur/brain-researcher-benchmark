# Typed native-grid map viewer and response collector

This adds an operator-owned viewer component for NEURAL-073. It renders complete
native-index slices of the existing canonical little-endian float64 maps and
collects one immutable first response per explicitly selected blinded query key.
It does not run the 9,532-map benchmark or change the registered scientific task.

The missing component is the task's typed-viewer route. The existing source
already includes a full-catalogue program/tool study, original-map conversion and
an independent conversion-fidelity checker. This component reuses their declared
native C-order geometry; it supplies neither another converter nor a smaller
scientific endpoint.

## Information and scope

`CanonicalMap` accepts already admitted immutable canonical bytes, their expected
SHA-256, the complete three-dimensional native shape, literal 4-by-4 affine and
declared spatial unit. It verifies extent, digest, finite float64 values and
geometry. The digest alone does not establish source authenticity or permission.
Original NIfTI identity, independent conversion fidelity and context admission
remain the existing operator's responsibilities.

Each typed slice request selects a native axis, integer index and finite display
window. Every voxel position in that plane becomes one RGB8 pixel in an embedded
PNG. No interpolation, cropping, masking, orientation change, atlas, source
filename, header, record digest or label is embedded. The literal affine and
spatial units remain visible because grid/support information is part of this
task's declared observation and nuisance-control problem. They can themselves
carry protocol information; this component does not eliminate that confound.

Colors are **lossy, quantized and clipped** blue–white–red display information.
They do not preserve exact numerical values or prove equivalence to numerical
tool access. A requested native-index slice is not automatically an anatomical
axial, sagittal or coronal slice, especially for oblique geometry. The display
explicitly labels native axes; pixel spacing is in voxel indices, with no inferred
physical-axis rendering. An operator must qualify actual screen rendering,
readability, precision and cross-condition information budgets before using a
viewer score scientifically.

## Operator interface

The trusted operator constructs a `ViewerSession` with:

- The complete ordered tuple of blinded query keys for one admitted context and
  its independently selected canonical-JSON SHA-256.
- An explicit ordered 25-class public label ontology and its independently
  selected digest. The participant receives this class order. It is never
  inferred from held-person labels or refreshed from a changed source.
- A trusted loader from an allowed blinded key to a validated `CanonicalMap`.
- Frozen explicit `Limits`: maximum full-map voxels, full-plane pixels, serialized
  SVG bytes, total actions, frames per query and wall time.

The operator must bind this context to the existing complete source and
person-disjoint study plan. A matching roster digest cannot prove that the
operator selected the right source cohort, split or training support. This
component accepts at most 9,532 keys, but it does not authenticate the global
9,532-map/13-person/25-protocol/300-cell or 234-context study. Different context
sizes are not separate benchmarks.

Only JSON-safe `dispatch` responses belong on a separately qualified participant
transport. Never give the participant the Python session, loader, canonical
bytes, filesystem or process. This is a typed protocol boundary, **not an OS
sandbox or proof of no-tools access**. SVG source is inspectable; this is also
not evidence that a model viewed rasterized brain images.

Accepted actions use closed schemas:

```json
{"action":"describe"}
{"action":"slice","case_id":"00000000000000000000000000000001","axis":2,"index":0,"low":-3.0,"high":3.0}
{"action":"answer","case_id":"00000000000000000000000000000001","probabilities":null}
```

`describe` supplies the current blinded key, ordinal, geometry, remaining frame
budget and public class order. A slice returns exactly one SVG frame. An answer
is either `null` for explicit abstention or 25 finite probabilities in that
declared class order, each in `[0,1]` and summing to one within `1e-8`.

The session moves through the complete explicit query roster sequentially.
Earlier answers cannot be changed through this API; held-person targets and
feedback are never accepted. Missing queries cannot be removed to finish early.
The operator's `finish()` succeeds once, only after every required key has a
response, and binds the collection to its roster and ontology digests. It returns
an ungraded collection and explicit false qualification flags. An abstention
collection is not a model result. The existing evaluator's denominator and
failure treatment must be retained by a separately reviewed adapter.

The sequential interaction policy differs from the existing batch-investigation
route. It needs a frozen comparison design; no I-versus-F or viewer-versus-tool
fairness claim follows from this component. Training/calibration presentation,
matched original/scrambled/nuisance conditions and all three repetitions remain
outside this component and must be delivered without changing the task.

Malformed/refused actions consume the global action budget. Failed requested
frames consume the frame budget. A complete native plane exceeding selected
limits is refused rather than cropped. Deadlines are checked around map loading
and during row rendering. These are cooperative logical checks; the host must
enforce process, memory and total wall limits and close the participant before
grading. A loader exception is replaced by a generic message to avoid projecting
an author's filename or private deployment path.

## Construction validation

Run the generated-only tests from this directory with Python 3.11 or later:

```sh
python3 -I -S -B test_viewer.py
```

The construction wave uses the shared two-slot test pool. Thirteen initial
controls passed, then nine affected/new controls passed after explicitly binding
the public class order. Independent review found that a valid JSON integer too
large for float64 escaped the typed refusal path; the numeric guard was repaired
and one affected control passed for oversized window/probability inputs and
unchanged pending-case state: **15 distinct methods** across three attempts.
Tests construct small non-cubic maps and a 9,532-key abstention roster in memory.
They read no authentic maps, catalogue labels, hidden targets, private data or
model outputs and fit no models. Source pins and exact attempt receipts are in
`SOURCE_EVIDENCE.json`.

The tests check independent pixel-coordinate expectations, every native slice,
PNG structure/CRC and absence of ancillary metadata, oblique-affine disclosure,
digest/extent/finiteness failures, explicit class order, malformed actions,
budget exhaustion, loader/render deadline checks, first-response immutability
and complete-roster collection. They establish source behavior on generated
controls; they do not establish scientific validity, visual comprehension,
provider isolation, original-source completeness or a ready benchmark.

Integration must enroll `test_viewer.py` in the repository's source-integrity
workflow/component command inventory. This private package has not changed any
shared CI, task, registry, catalogue, deployment or admission file.
