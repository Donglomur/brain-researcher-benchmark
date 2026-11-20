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

The public API and CLI are the same as `original-endpoints-v1/endpoints.py`.
`test_regression_bounds.py` contains three focused generated controls: signed
and unsigned integer residuals with known R²/RMSE, ordinary floating-input
parity, and floating-dtype preservation at the metric boundary (with metric
functions mocked so extended-precision dependency support is not assumed).
The integer counterexample requires a scikit-learn version that retains integer
arithmetic to reproduce the predecessor's failure. No EEG, models, source
cohort, comparison decisions, or scientific result is supplied by this change.
