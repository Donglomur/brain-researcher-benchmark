# Complete-person prior comparisons

The production grader now emits `neural_minus_uniform` and
`neural_minus_training_prior` for each of the two existing program modes and
three author replications. These balanced Top-1 comparisons were required by
the participant task but previously appeared only as separate prior scores.
Each comparison retains all four person differences, their equal-person mean,
and the existing exhaustive 256-resample descriptive interval.

The priors are numerically equal under this task's complete equal-class
training support. Each has Top-1 accuracy `1 / classes` on every person's
exactly two held images per class with the existing lower-class tie rule.
Neither comparator is fitted or selected using query responses. They remain
separate named outputs so consumers can identify both registered controls.
No probabilities are clipped, normalized, or regenerated, and missing or
invalid prediction panels still fail before target access. Missing class
support cannot produce a prior comparison.

This changes reporting on the existing complete panel; it adds no mode,
participant, query, fit, or scientific run. Source bindings for the changed
grader must be refreshed before any new production admission. Historical
V4 control receipts retain their original source-specific meaning. Full
input, reference, provider, resource and scientific qualification remain
absent. These generated controls establish software arithmetic and refusal
behavior only; they establish no neural interpretation or model competence.

Focused generated controls: `python -m unittest -v test_prior_comparisons_v1`.
The test imports the existing explicitly invented three-class full-panel
fixture and exercises all 160 matrices. No authentic observation, private
target, provider, model or Docker process is used.
