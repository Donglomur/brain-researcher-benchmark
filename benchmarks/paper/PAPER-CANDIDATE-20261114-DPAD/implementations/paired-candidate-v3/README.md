# DPAD paired scorer with stable channel correlations

This successor fixes a numerical defect in the paired candidate scorer. Scaling
raw values before subtracting their mean can distort a channel's representable
variation when it has a large common offset. For example,
`x = [3*2**52, 3*2**52+2, 3*2**52+4]` and `y = [-1, 0, 1]` have exact Pearson
correlation 1. The predecessor's arithmetic returns `3/sqrt(10)`, approximately
0.948683. This affects both author references and candidate scores.

The new calculation subtracts an observed finite anchor before scaling. If a
finite opposite-sign subtraction overflows, it halves both operands first.
Centered unit-vector dot products then compute each channel's Pearson CC. A
constant channel still produces `null`, and full scoring still refuses an
undefined channel. Nonfinite values, missing rows, identity changes and incomplete
prediction grids retain their existing rejection behavior. Arithmetic means of
channel correlations remain the endpoints; correlations are not pooled across
channels or flattened samples.

`paired.py` loads the pinned initial evaluator into a private module and replaces
only its `channel_cc` function. The original evaluator's full author-grid path
and the candidate comparison therefore call the same corrected function. The
on-disk initial evaluator and `paired-candidate-v2` remain unchanged. Both
predecessor source identities are checked when this component loads.

Author references, candidate plans and paired results use v3 schemas and carry
`dpad-shifted-channel-pearson-float64-v1`. References made with the old arithmetic
are rejected by the new comparison, even if supplied with a matching content
hash. Owners must freeze a new author reference and candidate plan before using
this scorer. Its commands preserve the earlier argument structure:

```sh
python3 paired.py freeze-author --training AUTHOR_TRAINING --targets TARGETS --predictions AUTHOR_PREDICTIONS --output REFERENCE
python3 paired.py select-candidate --training CANDIDATE_TRAINING --output PLAN
python3 paired.py compare --targets TARGETS --reference REFERENCE --plan PLAN --predictions CANDIDATE_PREDICTIONS --reference-sha256 OWNER_REFERENCE_DIGEST --plan-sha256 OWNER_PLAN_DIGEST --output RESULTS
```

The original seven-session, five-fold, eight-dimension and seven-author-method
comparison is retained: 1,960 author grid cases, 280 candidate grid cases, 35
training-selected candidate cases and 245 paired fold contrasts. Author model
selection, candidate dimension selection, channel order/units, target identity,
paired aggregation and the declared frontier diagnostic are unchanged.

The four new test methods use exact-rational mathematical oracles, finite
extremes, subnormals, strict input refusals and one generated complete-grid
comparison that traverses both scoring paths. They write no generated fixtures
to disk. Run `python3 -B -m unittest -v test_stable_pearson` through the maintained
source-test pool. No existing successful test suite needs to be replayed to
qualify this numerical change.

This remains a prediction-scoring component. It provides no model fitting,
authentic recording result, source-paper reproduction, improvement, new task or
SOTA claim. The session/electrode crosswalk, original preprocessing/sanitization,
authentic author predictions, reference protection, paired participant delivery
and scientific inference gaps documented in the predecessor remain unresolved.
The numerical policy evaluates float64 Pearson arithmetic; it does not claim
bitwise agreement with the original scientific runtime.
