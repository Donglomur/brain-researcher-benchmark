# NEURAL-062 public phase access

`phase_input.py` provides a model-free participant reader for the existing
separated FIT/INFER interface. The fixed reference reader ignores the compressed
training-mouse groups because its recipes do not tune. A participant that adapts
inside FIT needs those groups joined to the correct rows to keep any internal
validation within training mice. This reader validates their pin, complete run
counts, opaque identities and alignment, including the same mouse recurring in
nonadjacent runs. It makes no new inner split or fitting choice.

The reader also provides public-only prediction preflight. It detects incomplete
or misidentified responses before submission without importing the protected
grader or reading a target. Empty INFER cases remain required and accept exactly
an empty probability collection. A valid artifact is a structural result, not a
score or evidence of model competence.

## Use

In the published source tree, the default public-code location is the preserved
`registered-runtime/source/public` sibling. A participant distribution can put
those two pinned public modules in another directory and pass `--public-code`.
Only `protocol.py` and `delivery_io.py` are loaded. No evaluator, cohort, targets,
NumPy, scikit-learn or learned state is needed by this reader.

```sh
python3 -I -B phase_input.py --input FIT_DIRECTORY
python3 -I -B phase_input.py --input INFER_DIRECTORY --prediction prediction.json
```

Both commands print a compact structural summary to stdout. Malformed data raises
an error and exits unsuccessfully. They do not create or overwrite outputs.

Programmatic access preserves the original float32 values and NaN missingness:

```python
from phase_input import open_phase

with open_phase("FIT_DIRECTORY") as phase:
    feature_names = phase.view["feature_names"]
    for row in phase.rows():
        # row: index, features, label, original weight, opaque training group
        consume_training_row(row)
```

INFER rows instead contain exactly `id` and `features`. The reader exposes no
query label or mouse identity. The input directory must have the exact phase
file set; adding FIT arrays or metadata to an INFER directory is rejected. The
one-pass row iterator is valid only inside the context manager. No row selection,
resampling, truncation, aggregation, normalization or rounding is performed.

Before yielding the phase, the reader hashes the complete matrix and checks every
row's geometry and values. It checks all eight training classes and positive
sample weights, then seeks back to the payload for the single traversal. Numeric
working storage is one row; the existing bounded public JSON documents are held
in memory. Logical matrix reads are one complete hash, one semantic scan and one
row traversal. File identity is rechecked when the held descriptor closes.
Abandoning the iterator does not remove any case from the scientific evaluation;
complete response support remains mandatory at preflight and protected grading.

## Scientific and integration boundary

This additive utility retains the existing 107-mouse cohort, 73/15/19 split,
136 cases, four panels, F/I phase semantics, weights, features and eight-class
probability grammar. It creates no new benchmark condition. Its opaque class
indices preserve the declared known-image task; they are not image-name labels.
The old programme/source locks and projection formats are unchanged.

This is participant tool-building support, not delivered direct or restricted
viewer interpretation. It supplies neither a renderer nor an agent interaction.
It does not authenticate a dataset issuer, prove that a valid-looking group is
really a training mouse, inspect raw source observations, qualify sandboxing, or
verify native preparation/model execution. Those remain the trusted preparation
and programme's existing obligations. Cross-table projection integration and
full authentic cohort/reference qualification remain open.

This directory must be enrolled in the current implementation artifact registry
and its generated control suite in CI. It does not change the legacy runtime's
participant code allowlist automatically. A future runtime must explicitly bind
and deliver this public helper with the preserved public dependency hashes before
claiming it is available inside a qualified participant invocation.

## Generated controls

```sh
python3 -I -B -m unittest discover -s . -p 'test_phase_input.py' -v
```

The tests generate small NPY1 arrays with standard-library code and exercise all
four existing widths, repeated mouse-group runs, complete and empty INFER cases,
late invalid rows, pin/geometry corruption, phase leakage, invalid group support,
and missing/duplicate/wrong probability rows. They use no authentic observations
or model fits. For an isolated candidate checkout, set `NEURAL062_PUBLIC_CODE`
to the preserved public module directory; `NEURAL062_TEST_TMP` can bound scratch
to an owned directory. Passing these controls establishes software behavior only.
