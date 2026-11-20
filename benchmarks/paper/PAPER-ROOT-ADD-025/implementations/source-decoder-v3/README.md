# Finite-offset source decoder scores

This numerical successor preserves every selection, recorded fold, source
metric and output axis in [source-decoder-v2](../source-decoder-v2/README.md).
The predecessor remains unchanged. Design and score schemas stay at `/v2`
because their structures and scientific meanings are unchanged. The source
revision, signed within-fold Pearson metric, all five repeats, ten folds,
three metrics, original PC dimensions and 129 timepoints remain the same.

The earlier Pearson kernel subtracted the raw mean before scaling. Finite
values around `1e308` could overflow that mean, and finite values separated by
one representable step around a common offset could produce an incorrect
correlation. The successor removes a same-sign anchor before scaling and
centering. When values have mixed signs it uses zero, preventing subtraction
of opposite finite extrema. Constant and singleton folds remain undefined;
there is no deletion, imputation, pooled correlation or absolute-correlation
substitution.

`test_numerics.py` has three generated regression methods. They establish the
predecessor failures, compare finite-offset and extreme-value cases against an
independent exact-rational oracle, and exercise `score_predictions` on an
in-memory generated design. The last method also verifies the successor panel's
source pin and retained fold arithmetic. Tests use existing NumPy, create no
fixture files and perform no fitting. The target-derived generated predictions
are software controls, never scientific candidates.

Use [paired-panel-v2](../paired-panel-v2/README.md) when joining this version's
records. Source trial identity, historical MATLAB parity, complete S11 support,
original published arrays, protected execution and a scientific improvement
decision remain unresolved. No author result, benchmark completion or SOTA is
claimed by the numerical correction.
