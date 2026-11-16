# NEURAL-090: structured numerical investigation claims

This additive evaluator checks a submitted numerical interpretation of the existing complete `n090-broad-point-report-v1`. Scientific investigation grading includes numerical consistency, narrative reasoning and provenance; this component implements only numerical consistency. This component closes the numerical-consistency part only. It does not replace the original prediction scorer, controller, or scientific protocol, and does not qualify an experiment.

## Exact callable boundary

`claims.grade(artifact_bytes, trusted_reference_loader)` is the task-local entry point. The trusted evaluator supplies one loader for its already closed point report. The complete, bounded submission is parsed and frozen before that callback is invoked once. Candidates must not choose the callback, reference path, or report. The module performs no file, network, model, or native-library access. There is no new execution owner or model adapter.

The existing scorer returns lists. A trusted adapter may instead expose the same rows as iterators; cardinality and duplicate checks still cover every row. That adaptation is not implemented here. Loading an authentic full JSON report, caller resource ownership, custody, and candidate feedback timing remain the operator's responsibility. This component's small streaming-fixture memory measurement does not establish the memory cost of holding the existing report lists. The grade includes expected scalars and must remain evaluator-private until the selected experiment permits feedback; it is not a participant tool.

## Submission and complete denominator

The UTF-8 JSON body is at most 262,144 bytes and has exactly five fields:

- `schema`: `n090-numerical-investigation-v1`.
- `inference_scope`: `finite_cohort_point_estimates_only`.
- `assertions`: exactly the six keys in `claims.UNSUPPORTED`, all boolean false. These are explicit structured scope declarations, not a certification that free text obeys them.
- `narrative`: nonempty strings for `estimand`, `uncertainty`, `alternative_explanations`, and `executable_evidence`, each at most 2,048 characters. Presence is checked; meaning, scientific quality, executable evidence, and causal or population claims in prose remain ungraded and require human review.
- `claims`: exactly the 348 unique `{id, value, unit}` rows returned by `claims.claim_schema()`. Values are finite numbers or JSON null. Null is an explicit undefined/abstained submitted value, scores inconsistent, and remains in the 348 denominator. It does not mean an original report estimand is undefined. Missing, duplicate, unknown, boolean, nonfinite, or wrongly unit-labelled claims are rejected before loading the reference.

There are 240 arm means (120 conditions × log loss and fixed-39-class macro F1), 96 neural-versus-control loss contrasts, and 12 candidate-neural-versus-reference contrasts. These are scalar claims within one existing benchmark, not 348 benchmarks, independent samples, or 348 scientific discoveries. `claim_schema()` is the executable exact ID/unit specification; the generated fixture in `test_claims.py` illustrates the envelope without authentic values.

## Preserved scientific semantics

The existing [Broad protocol](../native-controller-v6/runtime/broad090/protocol.py) fixes six axis/budget combinations, two execution modes, candidate/reference tracks, five arms, ten seeds, 32 people and chapters 11 and 12. The evaluator checks all 76,800 chapter rows, 1,200 complete person/seed vectors, 120 ten-seed means, 61,440 paired-control rows, and 7,680 candidate/reference rows. Exact bounded identities plus rejection of duplicates and missing rows establish this report-level support. The 384 cases and 38,400 paired slots remain the original denominators.

The existing [scoring.report](../native-controller-v6/runtime/broad090/scoring.py) averages chapters equally within each person, then people equally, then all ten seeds equally. This evaluator reconstructs those arithmetic summaries and signed contrasts; it never weights people by query-row counts or selects the best seed. Log loss and loss differences are in natural-log nats per prediction. Fixed-39 macro F1 is a fraction, preserving the original absent-class convention, including exact zero F1 whenever true class support is zero. Positive neural gain is control loss minus neural loss; positive candidate gain is reference loss minus candidate loss. Negative improvements are valid numerical answers, not invalid results.

`held_chapter` and `joint_person_held_chapter` stay primary. `exposed_person` stays secondary. Time-shifted neural and timing controls remain protected; acoustic and transcript comparisons remain stimulus-exposed diagnostics. Their values are still checked, but this consumer cannot promote them into protected evidence.

The original scorer checks exact matched private support before constructing its report. This consumer has no support keys, probabilities, labels, recordings, or execution provenance. It checks the report's class-count shapes and numerical consistency; it cannot independently reconstruct confusion matrices, prove the original paired row identities, or establish honest report generation. The caller must preserve the accepted original scorer and custody. Structured false assertions and numeric agreement do not prove scientific understanding, novelty, SOTA, causal effects, population generalization, independent-visit generalization, or statistical significance.

## Numerical tolerance and output

Comparison is `abs(submitted - expected) <= 1e-12 + 1e-12 * max(abs(submitted), abs(expected))`. This is an engineering roundoff allowance, not a statistical confidence interval, effect-size threshold, or scientifically meaningful improvement requirement. The unchanged scorer's smoothing floor bounds chapter log loss above by `ln(39 / 1e-6)` (about 17.48 nats) and F1 by one. Its summaries use short binary64 sums over 2, 32, and 10 terms. This allowance conservatively covers their rounding differences from this module's `math.fsum` reconstruction, including subtraction near zero; it is fixed independently of submitted or authentic outcomes. It does not justify rounding answers to fewer decimal places. Full precision should be submitted.

Output preserves every claim's expected value, submission, absolute error, unit, undefined marker, and roundoff consistency. Counts report defined and numerically consistent claims over all 348. There is no mixed-unit numerical average, scientific pass threshold, campaign qualification, or readiness/count promotion. All provenance and qualitative-review flags are explicitly false.

## Source checks and integration limit

From the repository root, run the generated-only source checks:

```text
python3 -I -S -B benchmarks/neuroscience/neural-090/investigation-claims-v1/test_claims.py
```

These use invented complete scalar reports, not neural recordings or empirical targets. They cover full support, equal-person weighting with unequal query counts, signed contrasts, null abstentions, invalid public syntax, nonfinite values, unsupported structured assertions and the zero-support/F1 invariant. Source engineering checks do not establish authentic task performance or runtime qualification.

The consumer and tests preserve the independently reviewed numerical component’s executable syntax; this public copy removes one redundant final newline from each Python file. It does not alter the prediction scorer or automatically run after it. The trusted operator must explicitly supply an already closed complete point report and a committed submission. This callable is usable ordinary source, not a qualified model campaign or an implementation of the remaining scientific narrative/provenance obligations. No readiness flag or benchmark count changes.
