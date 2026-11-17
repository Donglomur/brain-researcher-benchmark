# Same-packet rendered references

This component implements the registered full-field template and eight-shot
kernel-ridge references on the existing `fus_nine_map_packet_v1` bytes. It adds
an executable reference component, not an authentic benchmark run or a model
result. The source preparation, 49-record intake, 48-fold scope, known direction
target, grouped scorer and existing implementations remain unchanged.

`reference.predict(packet_bytes, method=..., ridge_lambda=...,
max_packet_bytes=..., max_map_pixels=...)` returns one exact
`{query_id, probabilities}` row for the existing direction scorer. The two
positive integer budgets are supplied by the operator; exceeding either
refuses the input without cropping or resizing. There are no third-party
dependencies. The function reads no files, private intake, source IDs, other
queries, targets, fitted weights or training corpus. It is a reference function,
not a process isolation or participant execution controller.

The parser accepts all eight canonical support maps and exactly one query,
checks their common native shape, pitch, scale and format, and preserves the
PNG grayscale and magenta validity mask. It validates CRCs and bounds decoded
image length before extraction. It intentionally supports only the lossless
RGB8, filter-zero, one-IDAT codec emitted by `fullfield-delivery-v1`. Unknown
map fields, query labels, repeated identities, duplicate JSON keys and omitted
support classes refuse. Source authentication and target-free custody remain
external responsibilities; syntactic validation cannot establish them.

## Frozen numerical choices

These are prospective implementation choices, not methods attributed to the
source paper. All methods consume the same packet and return eight entries in
0, 45, ..., 315 degree order. None selects a method or hyperparameter from query
performance. Method choice and the ridge value must be frozen using only
outer-training episodes before exposing the held session. The required
outer-training selection procedure has not been run or implemented here.

- `uniform`: each class gets 1/8. Because the packet has exactly one support
  for every direction, the support class-prior control is identically uniform.
- `squared_distance`: nearest support under full-field squared distance on the
  common valid-pixel intersection of all nine maps. The intersection uses only
  validity, never labels or response magnitudes. Dividing by the same number
  of pixels and by the same quantization scale would not change the winner.
- `cosine`: nearest support by cosine of `2*gray-255` on that same common
  validity intersection. This centers on zero encoded response, not on a mean
  derived from query or support pixels. Empty intersection or zero norm yields
  uniform output. Exact best-score ties in both template methods share mass
  equally; the existing scorer's lowest-angle argmax tie rule is preserved.
- `linear_ridge`: each of all `d` native pixels contributes two features:
  `(2*gray/255-1)` for a valid response (zero when invalid), plus an invalid
  indicator. Divide both channels by `sqrt(2*d)`. This yields an explicitly
  defined linear kernel over every pixel, including invalid-mask channels;
  there is no voxel selection. Center the kernel using only the eight support
  vectors and fit centered one-hot labels with an unpenalized intercept of
  1/8 per class. Solve `(H K H + lambda I)` with Cholesky. The objective is a
  **sum** of eight squared errors plus `lambda` times squared weight norm;
  lambda is not multiplied by eight. Require exactly one registered value
  `{0.001, 0.01, 0.1, 1, 10, 100}`. A fixed rectification at zero followed by
  normalization converts raw regression scores to probabilities. This is not
  a claim of calibrated probabilities. All-invalid query or all-invalid
  support corpus returns uniform. An individual invalid support stays in the
  eight-way fit; it is not removed. Strictly positive ridge handles identical
  or linearly dependent support vectors without dropping classes.

The normalized grayscale uses only the delivered quantized information. No
source-float values are reconstructed or obtained. Template outputs can be
overconfident and mask patterns can carry nuisance information; authentic
qualification still requires the registered nuisance controls and rendered
versus full-precision comparison. Numerical singularity or malformed packet
raises `ReferenceError`; the owner must preserve the query and existing failure
penalty, not exclude it or silently select another method.

## Source context and limits

The local contract is `task.json`, especially `baselines_and_controls`,
`split_and_access`, and the current `understanding.v1.json`. Existing
`fullfield-delivery-v1/delivery.py` defines the byte interface. Source background
remains [the original paper](https://www.nature.com/articles/s41467-025-63826-z),
[Caltech v0.0.1 data](https://data.caltech.edu/records/p5jan-02r60), and
[first-party code at a5571a3](https://github.com/wsgriggs2/PPC_directional_tuning/tree/a5571a3488b1d25e7259bccd8f3fe894b5e852bd).
No new source payload was acquired, and none of those native data were opened.
Existing native clock, geometry, Run99 lineage and complete-cohort problems
remain unresolved; this code does not infer a native MAT schema.

The adjacent generated tests check exact template outputs, a closed-form ridge
solution at all six lambdas, an independent uncentered intercept-system oracle
with masks, degenerate inputs, query independence, permutation invariance,
packet failure cases, bounded PNG decoding and the existing producer codec.
They establish software behavior only. Run them through the coordinated test
pool with `python3 -I -B test_reference.py`; no authentic data preparation,
training, inference or scientific qualification is implied. Fresh per-query
processes, freeze/exposure receipts, authentic complete 48-fold inputs,
outer-training method/lambda selection, full-information reference parity,
matched-reference competence and real participant transport remain required.
Native interpretation and creation/use of tools, models or pipelines are
separate first-class outcomes on matched cases. This component supports the
latter and paired comparisons without doubling the task count or establishing
either outcome empirically.
