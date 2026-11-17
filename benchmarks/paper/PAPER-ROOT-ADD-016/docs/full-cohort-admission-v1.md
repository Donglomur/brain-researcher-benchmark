# Complete Salzburg input and reference preparation

The [operator preparation component](../implementations/full-cohort-admission-v1/README.md)
adds exact original-input admission, all six source-model prior/density preparations
and independent complete saved-draw summarization for the existing cardiac endpoint.

It preserves all 655 exposed development participants and the six separate
raw/standardized models. It adds no participant holdout, candidate grading rule or
new benchmark ID. Its summaries use the existing authenticated summary validator.

Use the component's `verify-source`, `inspect-input` and `review-reference`
commands from the linked guide. The original CSV, 30 complete private posterior
streams and producer/environment/execution evidence are operator-supplied inputs.
No data, fitted posterior or native runtime is included.

The generated summary is a **review artifact**, not an accepted private reference.
Fitting, independence, convergence, data dependence, rights, protected custody,
native feasibility and scientific qualification still require separate evidence.
The guide documents exact inputs, private outputs, meaningful source controls and
the remaining admission steps.
