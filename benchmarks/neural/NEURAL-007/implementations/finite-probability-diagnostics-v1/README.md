# Finite sleep probability diagnostics

This operator scoring component implements the probability-diagnostic endpoint
identified in `understanding.v1.json`. It uses the complete existing finite panel:
development-001 has 2,780 whole-clock epochs and development-002 has 2,670. It
requires both fixed YASA and RF probability files. It does not reinterpret this
panel as the planned 78-person/153-night study.

The predecessor adapter is loaded only after checking its exact 14,326 bytes and
SHA256. Candidate and both comparators must pass its unchanged identity, archive,
five-class, simplex and complete-coverage validation before the trusted operator
target loader runs once. Missing predictions for privately unscored epochs still
fail. The primary fixed-five-class macro-F1, supported balanced accuracy, person
rows and comparator differences use the predecessor's original functions.
Historical code, predictions and target files are unchanged.

The additional metrics operate on actual eligible probability rows:

- Natural-log loss is the mean of `-log(p[true_stage])`. A zero probability of
  the true stage produces infinite loss. JSON encodes this with a null mean,
  `log_loss_is_infinite=true`, and the zero count; no epsilon, clipping or
  normalization changes submitted probabilities. Finite terms are separately
  retained as a sum, never substituted for the total loss.
- Multiclass Brier is the mean of `sum_k (p[k] - 1[k=true_stage])**2`, with no
  division by five. The range for an exact probability simplex is zero to two.
- Top-label calibration uses ten prespecified confidence bins `[0,.1)`,
  `[.1,.2)`, ..., `[.9,1]`. Exact internal edges go in the upper bin. The predicted
  label uses first-index ties in W,N1,N2,N3,R. ECE is the sum of bin frequency
  times absolute confidence-minus-accuracy. Empty-bin values are null. This is
  a descriptive calibration diagnostic, not a proper scoring rule or evidence
  that one model understands sleep physiology.

Each metric first combines all eligible epochs of one finite person, then gives
the two people equal weight. Calibration bins are computed separately per person;
their ECE values are averaged, not pooled across people. The returned per-person
counts expose support. Candidate-minus-comparator differences are lower-is-better.
Infinite log-loss comparisons explicitly distinguish positive infinity, negative
infinity and undefined infinity-minus-infinity. JSON never uses NaN or Infinity.

Use the Python `evaluate(submission_path, submission_lock, target_loader,
comparators)` API inside the trusted scoring realm. Each freeze is an operator
retained `{bytes, sha256}` object; `comparators` maps `YASA` and `RF` to `(path,
freeze)` tuples. `target_loader` is the same trusted no-argument target callback
contract as the predecessor. Do not expose it to candidate code. The API itself
does not supply a sandbox, locate private assets or prove producer provenance.
Central CLI/Docker enrollment is an integration proposal, not delivered here.

`test_diagnostics.py` uses generated arrays only, including the full 5,450-row
identity geometry. Tests distinguish probability quality even when argmax/F1 is
unchanged, check unequal person supports and masked rows, preserve infinite loss,
and prove that invalid candidate/reference files fail before the target callback.
No authentic targets, model predictions, fitting or solver trials were used.
The two people remain exposed development cases; no population inference,
direct/viewer interpretation or scientific qualification is established.
