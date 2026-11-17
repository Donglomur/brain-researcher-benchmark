# Proposed canonical clarification; no readiness promotion

The integration owner may narrow `same_task.metric` and corresponding blocker wording using the pinned source evidence in `source-recovery.json`:

> The author's per-model predictive score is the unnormalized sum of Poisson log probabilities over all stitched CV prediction bins, including the log-factorial constant; `cv2NegLnL` is its negative. The source final hierarchy score uses the joint predictions of its leaves. No authentic numerical author baseline, original fold realization or cross-cell predictive aggregation has been recovered.

Keep `disposition: source_unresolved`, `metric.status: unresolved`, all original cohort/split/preprocessing requirements and the unrecovered published/reproduced baseline. The complete original metric support remains unresolved despite recovery of its arithmetic reduction.

Add a source-recovery caveat: saved fit objects do not reliably preserve local CV selections, and inherited leaf `fitInfo.cv2NegLnL` can describe progenitor support. Replay therefore requires original prediction/bin identities and computes likelihood on those rows; summing leaf fields or treating reconstructed folds as original is not justified.

Register the replay component only as source-grounded software construction. MATLAB bridge execution, authentic author score replay, complete-cohort coverage, same-fold candidate evaluation and all scientific qualification remain pending. Generated test success is not evidence for any of those claims.
