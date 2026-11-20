# Finite-offset feature correlation

This successor keeps the original Fig. 2d face roster, 1,000 leave-one-face-out
folds, 36 familiar queries per fold, output types and signed Pearson metric from
[feature-decoding-v1](../feature-decoding-v1/README.md). The predecessor stays
unchanged. Only the numerical centering step in `feature_correlation` changes.

Previously, rescaling before subtracting the mean could erase the exact mean of
finite vectors with a large common offset. For example, `[1, 1, nextafter(1,+inf)]`
is perfectly correlated with `[0, 0, 1]`, but the previous arithmetic returns
about 0.9428. The successor subtracts one observed value first when every value
has the same sign. That subtraction cannot overflow. For mixed signs it uses a
zero anchor so opposite finite extrema are never subtracted. Scaling and
centering then operate on the remaining deviations. Constant vectors retain the
existing explicit undefined states; no tolerance makes a nonconstant vector
constant and no face or coordinate is omitted.

`test_numerics.py` contains three generated regression methods: the concrete
predecessor counterexample, signed/permuted finite extremes checked against an
independent exact-rational Pearson oracle, and the complete existing scoring
entrypoint preserving all 1,000 × 36 familiar-fold positions. It requires only
the standard library and the retained predecessor module. It does not execute
old test suites or train a model.

The source roster, original decoder parity, source windows and scaling,
published reference curves and complete-panel improvement decision remain
unqualified as described in the predecessor documentation. This is a numerical
software correction, not an authentic-data result, reproduction, improvement,
or additional benchmark. The existing panel comparison accepts the unchanged
score object structure; no panel mean or scientific success threshold is added.
