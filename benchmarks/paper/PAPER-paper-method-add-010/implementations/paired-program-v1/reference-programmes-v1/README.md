# MEG fixed-feature reference programmes

These are two standalone scientific reference programmes for the existing
`generic_feature_classification_v1` endpoint. Each `submission.py` can be frozen
by the existing paired-programme preparer without copying any sibling modules.
They are engineering/scientific comparators, not AI-generated predictions or an
experiment measuring access to author code.

| Programme | Method |
| --- | --- |
| `programmes/original/submission.py` | Author sigmoid fit on training rows; final minimum/range recomputed separately for each complete transform batch. The entire held fold is transformed together. |
| `programmes/training-range/submission.py` | Same sigmoid and classifier, with final minimum/range fitted on training rows only. Values outside the training range remain unclipped. This is a separately named method variant. |

Both use L1 logistic regression with `C=1`, `solver="liblinear"`, balanced class
weights and `random_state=127`, retaining the other scikit-learn 1.5.0 defaults.
The original scaler file is embedded byte for byte. Six numerical helpers and
the public context validator are copied as exact source-line segments; their
identities are recorded in `programmes/DERIVATION.json`.

## Runtime and invocation

Use Python 3.11 and the exact package versions in `requirements.txt`. The
selected generated-check runtime is Python 3.11.6. Compatibility with another
Python patch or platform requires qualification; package-version checks are not
a complete binary, BLAS, operating-system or historical-runtime guarantee.
This package does not install anything or qualify a container image.

The existing candidate wrapper invokes a frozen programme as:

```sh
/usr/local/bin/python -I -B /program/submission.py --input /input --output /output/RESULT.json
```

For local preparation, provide absolute input/output paths to the same two CLI
arguments. The output must not exist. The programme writes only that JSON file.
The wrapper owns the later `OUTPUTS.json` manifest and runtime containment.
Thread environments and `threadpoolctl` restrict numerical library threads to
one; resource admission remains the runner's responsibility.

## Public input and prediction

The input directory contains exactly `CONTEXT.json` and `FEATURES.npy`. The
feature file uses the preparer's NumPy-v1 encoding: 188 finite little-endian
float64 scalars. Header shape, dtype and exact byte extent are checked before
allocating the array. Every scalar must match its context row commitment.

The programme preserves `CONTEXT.training` order when constructing training
features and labels. It maps opaque IDs to the feature-bank positions and
transforms the complete `CONTEXT.queries` batch once. Held folds contain 18 or 20
rows from 9 or 10 participants. It does not create new folds, infer source row
ordering, exploit paired held-label constraints, or use any other fold's state.

The result has exactly `schema`, `input_mode`, `context_sha256` and
`probabilities`. Probabilities mean `P(object)` and cover every current query ID
exactly once. The existing grader treats exactly 0.5 as face and calculates the
unweighted mean of the ten fold accuracies. Neither programme reads saved OOF
probabilities, private labels, an original bank, a private source mapping or a
reference result. They do not emit aggregate metrics.

## Interpretation

The feature input consists of category-averaged Generic CS–PFC
`bary-sq_dtw_max` scalars from the fixed 94-participant endpoint, after the
author's broader category QC. The curator's category knowledge remains part of
that input construction. These programmes do not reproduce raw feature
extraction, the full measure search, or the whole paper.

The prior exposed-fold reference summaries, 64.2777778% for the original and
66.5% for the training-range variant, motivate this packaging but are not
candidate input constants, new programme-run results, untouched validation or
SOTA claims. A future authenticated execution must establish the adapted
programmes' same-case scores. Any difference is an observed method comparison.

The runner's A/B labels denote information conditions. Assigning different
reference algorithms to A and B does not measure code assistance; declare such
a run as an engineering method comparison. An AI access comparison requires its
own frozen programmes and provenance.

Generated checks in this source phase cover the new adapter and IO boundaries.
They do not run original data, qualify container isolation, or change benchmark
readiness counts.
