# Fixed Generic-feature MEG classification

Predict face versus object from one supplied connectivity feature per observation.
The input contains 188 category-averaged observations from 94 participants. It is
the released Generic CS↔PFC maximum-squared-DTW-barycenter feature with source
labels task-irrelevant, stimulus ON, and duration 1000 ms. These labels do not
reconstruct the physical raw-signal window or its timing. The evaluator supplies the feature
after the author's complete four-category QC. That source construction is an
oracle input; you are not asked to reconstruct it from regional time series.

Your frozen `submission.py` receives `--input /input --output /output/RESULT.json`.
Read `/input/FEATURES.npy`, a little-endian float64 array of shape `(188,)`, and
`/input/CONTEXT.json`. Array positions match the context's `rows` list exactly.
Each row has an opaque `id`, opaque participant `group_id`, and commitment to its
eight scalar bytes. Source names, categories, and original row ordering are not
encoded in these opaque IDs or the bank order.

The context's `training` list supplies face/object labels for nonheld participants
in the frozen source order. `queries` contains the held participant rows in opaque
order. Each participant contributes one face and one object observation. Held
labels are private. All scalar values and the complete held batch are available;
the original classifier used training location/scale followed by separately
computed transform-batch extrema. This transductive convention is disclosed.

Both information conditions receive identical scalars, contexts, folds, paper,
and budgets. The paper is `/paper/PAPER.bin`; only the code-assisted condition
receives `/author`, containing the pinned official code/config capsule. Your
programme freezes before any outer-fold labeled view is exposed. Each of the ten
folds runs in a fresh isolated phase. No other fold's state, results, or grading
feedback is available. Public source data may have been seen elsewhere; these
restrictions do not claim to prevent external memorization.

Write exactly one JSON object, with no extra fields:

```json
{
  "schema": "meg-generic-classification-response/v1",
  "input_mode": "generic_feature_classification_v1",
  "context_sha256": "the exact context commitment",
  "probabilities": {"every query ID exactly once": 0.5}
}
```

Probabilities mean P(object), must be finite and in [0,1], and cover exactly the
held query IDs. Exactly 0.5 predicts face. Do not submit aggregate scores, labels,
source-feature claims, or distribution plots. Missing, additional, duplicate, or
cross-context predictions invalidate the attempt. Write no other output files;
use `/work` only for bounded temporary work.

The primary score is the unweighted mean of the ten held-fold accuracies, with
population fold SD reported separately. The evaluator computes all scores from
private labels and your probabilities. Two independent questions are evaluated:

- **Published-precision numerical reproduction:** mean accuracy in [64.25,64.35)%
  and population fold SD in [9.35,9.45) percentage points. These half-open bounds
  are the benchmark's explicit precision criterion, not a recovered historical
  rounding implementation. Agreement of these summaries does not mean identical
  individual predictions.
- **Reference score exceeded:** a strictly positive difference from the accepted
  author-method reference, using the same cases, folds, and mean-fold metric.
  This is an observed score increase, not established statistical superiority.

Both outcomes can be true together. Exact differences, fold counts, paired
participant effects, and probability discrepancies remain reported. Statistical
superiority and SOTA are not established by either flag. This mode concerns the
selected classifier endpoint; it does not qualify raw feature extraction, the
paired-feature distribution panel, AUC companions, or the whole paper.
