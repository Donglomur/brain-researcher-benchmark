# Original recording sentence-content projection

This component produces the complete content-only input consumed by
[`materials-join-v1`](../materials-join-v1). It advances NEURAL-085's unresolved
join between original ZuCo 2.0 stimulus materials and recorded sentence text.
It does not create participant observations, change the source-condition
target, or establish a qualified matched item set.

The operator supplies independently reviewed original MAT identities and the
source `sentence_group`/`content_field` bindings. The extractor authenticates
each complete file against those pins, then follows only the declared sentence
content references. It preserves literal UTF-16 text, original zero-based
indices, repeated sentences, quotes and whitespace. The downstream join owns
normalization and separately evaluates both existing material-quote dialects.
No dialect is selected to obtain a desired duplicate count.

## Complete scope and refusals

The input must contain all 18 original people and both NR/TSR containers for
each person: 349 NR and 390 TSR sentence positions, totaling 13,302
presentations. Missing, duplicate, reused-file, wrong-size or mis-hashed
containers are refused. The source-byte ceiling is checked before any source
file is opened. Unexpected reference geometry, null references, non-UTF-16
content, invalid surrogates, unsupported filters and external/virtual content
storage are refused. Unknown schemas fail instead of selecting a convenient
subset or guessing a replacement field.

Whole-file authentication **reads every selected MAT file's raw bytes**,
including bytes that encode physiological data. Only sentence text is
materialized through the HDF5 value interface; EEG/gaze arrays and their
reference columns are not accessed. This is not an assertion of zero physical
I/O to neural data. It is also not an OS sandbox or a hard resource envelope.
Actual original-file use requires a separately admitted finite runtime and
source-byte allowance. No original recording has been used to validate this
new component.

## Operator input and output

The input JSON has exactly `schema` and `containers`. Its schema is
`zuco2-presentation-content-input/v1`. Each of the 36 container rows has exactly:

- `person`, `condition`: an original person ID and `NR` or `TSR`.
- `path`, `bytes`, `sha256`: an absolute ordinary local file and its independently
  established complete original-release identity.
- `sentence_group`, `content_field`: an explicit ordinary HDF5 group path and
  sentence-reference field name established from the original source schema.

Paths are operator-private. A typical binding may name `/sentenceData` and
`content`, but names are supplied explicitly; this example is not a source
qualification or a synthetic default manifest.

Using an existing compatible Python environment with NumPy and h5py:

```sh
python -I -B presentation_content.py \
  --manifest /operator/reviewed-original-container-bindings.json \
  --max-source-bytes REVIEWED_TOTAL_BYTE_CEILING \
  --output /operator/fresh-content-projection
```

The output directory must be fresh, outside Git, under an existing operator
directory. Only after all 36 projections succeed does the operator write:

- `presentation_content.json`: the exact
  `zuco2-presentation-content-v1` input to the existing material join.
- `projection_receipt.json`: manifest/content hashes, declared source identities,
  field bindings, complete counts and explicit unqualified states.

The output contains original stimulus text and stays operator-private. If
writing fails, discard the partial output; no missing receipt is an admitted
result. Supply the complete content file to the existing material join's
`--presentation-content` option. That join still checks cross-person content
agreement and unique ordered alignment, and reports ambiguity without guessing.

## Validation and remaining limits

Thirteen distinct generated controls passed across three bounded invocations:
eight initial controls, two new integration controls, then three new review
regressions plus one affected integration control. The review regressions refuse
oversized/variable-length/array MATLAB-class attributes before reading values,
limit a growing manifest read to65,537 bytes, and reject FIFO sources without
blocking. Valid source attributes are tiny scalar fixed-length strings. The
integration controls authenticate/project a generated HDF5 file and pass a
complete generated36-container/13,302-position document to the pinned existing
material join. Previous attempts remain recorded; the full suite was not
replayed. These controls establish format behavior, not original compatibility.
No original MAT, EEG/gaze array, candidate prediction, model or scientific score
was read or produced.

After deployment alongside the existing material join, the proposed focused
test command is:

```sh
python -I -B test_presentation_content.py
```

The private construction invocation supplied the existing join's exact path
with `--materials-join`; the test authenticates that implementation's SHA-256.
CI enrollment is proposed to the sole integrator and is not claimed here.

Supplied file hashes authenticate bytes against a manifest; they do not prove
that the manifest identifies the intended source release or that its HDF5
bindings have independent scientific provenance. The receipt therefore retains
`independent_source_binding_qualification=false`. Actual complete MAT/content
joins, the paper's 63 duplicate obligations, EEG/gaze representation semantics,
source operators and study execution remain unresolved. Fixed chronology still
precludes a causal reading-demand claim. No direct/viewer/tool condition,
readiness, model performance or scientific superiority is promoted.
