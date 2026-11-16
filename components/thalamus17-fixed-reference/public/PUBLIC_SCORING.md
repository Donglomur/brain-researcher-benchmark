# Reconstruction scoring specification

This is a source-only specification. No new candidate or grader has run. The task has one primary continuous error and complete diagnostics; it has no accuracy, AUC or p-value success floor.

## Admission and support

All 17 producer outcomes must be committed and their resources absent before private grading. A missing outcome, candidate failure, timeout or infrastructure error remains explicit; it is never removed from a full-cohort average. Infrastructure failure is not a candidate score. Only the exact public schema is checked before any private reference body is opened. Invalid JSON, wrong public identity/order, missing fields/cells, wrong types, nonfinite probabilities, illegal ranges, duplicate keys, incorrect partition sizes or oversized output give `invalid_submission`, a null primary metric and zero private reference reads.

For every structurally valid cell, compare the candidate-derived feature order, ordered training rows and ordered test rows with the fixed source reconstruction. A mismatch gives primary cell error **1** and an explicit support-mismatch reason. The cell stays in all 34 primary slots. The hidden empirical identity is not treated as an undisclosed public parse requirement. A matching support permits prediction comparison and metric recomputation from trusted labels. The grader does not trust candidate-supplied labels, metrics, fit counts, p-values or summaries; none is required in the output schema.

## Primary error

For each matching session-condition cell, take the mean absolute difference between candidate and reference Randomised probabilities over **every** source test row. Both probability vectors are in [0,1], so the error is in [0,1]. The full task error is the arithmetic mean of the **34** cell errors: each session has weight 1/17 and each condition within it has weight 1/2. A 143-row cell has the same cell weight as a 144-row cell. Lower is better. Report every cell error, support status and row count; there is no rounding, clipping, dropped cell, or numerical pass threshold.

This scores agreement with the declared reconstruction, not raw predictive accuracy. Replacing probabilities with exposed true labels or optimizing toward AUC 1 is not inherently beneficial. The reference vector is withheld from candidate mounts, but released public data and possible prior exposure prevent a guarantee of outcome blindness or protected generalization.

## Complete secondary diagnostics

For each comparable cell, derive the class at Randomised probability >=.5 and compute the confusion matrix and accuracy directly. Compute fixed Randomised-positive AUC as the mean of `I(p_positive>p_negative) + .5*I(equal)` over all positive/negative pairs. Both classes are present in the declared support. Independently derive source-auto orientation using the public median rule, not by maximizing AUC. The new grader must implement this computation independently of candidate claims; the existing reference admission's join to a worker-written `independent_audit` is not sufficient for arbitrary candidates.

Report fixed-AUC and source-auto absolute errors in AUC units [0,1]; accuracy absolute error and signed differences in percentage points; prediction disagreement fraction; and signed candidate-minus-reference values. For each session also report ON−OFF AUC/accuracy contrasts and their discrepancy from reference contrasts (AUC contrast absolute error can reach 2; accuracy contrast absolute error can reach 200 percentage points). Report individual values and equal-cell macro means. Do not combine reproduction agreement with an improvement reward.

Using all 17 comparable pairs, report the complete candidate and reference source-auto/fixed AUC vectors, ON−OFF descriptions, zero/tie diagnostics and nominal session tests. The statistical definitions are the held R 4.3.1 protocol: primary exact=NULL/correct=TRUE; sensitivities exact=FALSE with and without continuity correction; exact=TRUE/correct=FALSE only when eligible; and fixed Randomised-positive AUC with default exact=NULL/correct=TRUE. Preserve warnings, undefined results, all-zero status, and unavailable reasons. Accuracy has no hypothesis test. If any cell is not comparable, full17 paired statistics are `not_computed_incomplete_fixed_support`; do not drop it and test the remaining sessions. The candidate-derived metric envelope must retain candidate provenance rather than pretending to be the root's reference join.

The published P=.008 is contextual information, never a target, ranking term or acceptance threshold. Exact author test settings and published AUC vectors remain unknown. Pointwise pROC intervals, if emitted, are diagnostic and must retain their method and dependence limitations; they do not affect the primary score.

## Required qualification controls

Before any task-readiness claim, execute the source-reviewed grader on invented exact-probability/tie cases, malformed and nonfinite outputs, wrong partition/count cases, missing sessions, and support mismatches. Verify public rejection performs zero private reads, matching-reference fixture gives zero error, inverted probabilities retain a valid nonzero discrepancy despite possible auto-direction compensation, and true-label probabilities are not given an AUC1 bonus. Test all34-cell aggregation, the143-row OFF cell, all-zero and tied paired-test cases, and full-size report caps. These are planned controls, not completed evidence.

Then run one genuinely independent paper+data candidate through the full17 ordinary lifecycle and an actual valid constant-probability control, with separate source/grants and preserved costs. A reference replay fixture establishes grader arithmetic, not independent candidate performance. Optional source-assisted code access follows a separately frozen equal-budget arm and cannot retroactively change the paper+data program. One candidate pair is not a systematic causal estimate of the benefit of code access.

Numerical exceptional case: valid nonzero discrepancies that underflow during cell averaging or the34-cell macro are reported as null with an explicit destructive-float-underflow reason. All cells remain in the record; no exact-agreement credit, ranking, or dropped-cell mean is assigned. Secondary full-cohort means are available only with all34 fixed supports comparable.

Primary-document caveat: Table S1 explicitly names the four observed second UUID tokens as mice and lists three additional names for Figure3C; the main legend says four animals. These sources do not fully reconcile the per-session map or explain the extra names. Keep the17-session reconstruction unchanged and do not infer independent animal replication.
