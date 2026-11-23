# Integer-safe original endpoint arithmetic

This successor preserves the twelve-dataset CBraMod endpoint definitions and
explicitly converts already-accepted integer SEED-VIG regression operands to
float64 before computing R² and RMSE. Integer residual squaring can wrap in
older scikit-learn versions and falsely report zero error. Newer scikit-learn
versions already promote these operands internally; the explicit conversion
makes the component independent of that implementation detail.

Floating inputs, including extended-precision arrays, retain the predecessor's
`.tolist()` / `np.array` reconstruction without forced narrowing. Only integer
operands are promoted to float64. All classification routes are unchanged. Original PERCLOS units, ordered row
support, metrics, and undefined-value reporting remain unchanged. The preserved
`original-endpoints-v1` source and its historical validation are not modified.
This is mathematical handling of an already-accepted numeric input domain, not
a claim of byte-for-byte historical evaluator parity for pathological integer
inputs or qualification of a paper reproduction/improvement.

The existing `score` API and positional CLI arguments remain compatible with
`original-endpoints-v1/endpoints.py`.
`test_regression_bounds.py` contains three focused generated controls: signed
and unsigned integer residuals with known R²/RMSE, ordinary floating-input
parity, and floating-dtype preservation at the metric boundary (with metric
functions mocked so extended-precision dependency support is not assumed).
The integer counterexample requires a scikit-learn version that retains integer
arithmetic to reproduce the predecessor's failure. No EEG, models, source
cohort, comparison decisions, or scientific result is supplied by this change.

For arrays carrying position identities, `score_aligned(dataset, targets,
outputs, target_row_ids=..., output_row_ids=...)` checks identical declared
support and order before calling the same scorer. Both identity lists must
match the target layout: `[N]` for ordinary datasets, or `[blocks,20]` for ISRUC.
Each identity is a unique nonempty string associated with one output position;
ISRUC identities must distinguish every epoch within its sequence block.
Reordered, missing, extra or duplicate identities are rejected. There is no
sorting, intersection, dropping of rows, or change to metric aggregation.

The CLI accepts the two JSON lists through paired optional flags:

```sh
python3 -I -B endpoints.py PhysioNet-MI targets.npy scores.npy \
  --target-row-ids target-positions.json --output-row-ids output-positions.json
```

The [pinned author evaluator](https://github.com/wjq-learning/CBraMod/blob/b9e961003214326972c567eff390e75b0287e32a/finetune_evaluator.py)
collects targets and predictions in the same loop before computing pooled
metrics. The optional identity check helps preserve that correspondence when
arrays are exported separately. It establishes agreement of supplied identities
only: it cannot authenticate original cohort membership, sequence context,
splits, or the attachment of an ID to its numeric value. Identity lists should
be established during export, rather than copied onto mismatched arrays later.
The report adds `row_alignment` and does not emit the supplied identities.
`test_alignment.py` exercises actual metric parity across all twelve dataset
routes, mismatched support/order, ISRUC axes, and the optional CLI path using
generated values only.
