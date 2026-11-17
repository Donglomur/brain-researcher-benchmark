# Complete candidate score reconciliation

This component checks scientific arithmetic that the frozen candidate result
reconciler does not check. It preserves the existing four-action endpoint,
20 participants, 80 held sessions, 4,884 trials, 163,135 decisions, and the
original paired participant bootstrap. It introduces no new task or score.

`candidate_metrics.reconcile_candidate(score, historical, comparison, scoring)`
has the predecessor function's call signature. `scoring` must be the existing
authenticated runner module; the comparison still uses exactly its default
10,000 bootstrap draws and seed 20261114. Better, worse and null candidate
contrasts remain valid results. No improvement threshold is introduced.

The successor validates both complete score dictionaries, then checks:

- Confusion counts account for every eligible decision. Classes 3 and 4
  together account for exactly one terminal action per completed trial.
- The candidate and reference have identical true-action supports. Counts of
  predicted actions may differ freely.
- Accuracy, each action recall and macro recall agree with the confusion
  matrix. Absent-action recall stays undefined. Both stopping recalls remain
  explicit.
- NLLs are finite and nonnegative; rates and stopping Brier score are in
  `[0, 1]`. The decision-weighted loss is within the session-loss range,
  allowing eight floating-point ULPs for the scorer's separate summations.
- Exactly four sessions are averaged within each participant, and all
  20 participants are equally averaged for the primary result.

The terminal-action identity comes from the existing consumer's requirement
that the sole terminal action is the final scored decision in each trial. The
predecessor candidate test uses roughly 81,567 terminal decisions for 4,884
trials; the new controls preserve this as a rejected counterexample.

## Verification

Run `test_candidate_metrics.py` in isolated Python through the project's shared
test pool. The test authenticates the four exact predecessor modules before
executing their captured bytes. It imports only the Python standard library.
Eleven generated controls passed. Nine malformed results are demonstrated to
pass the predecessor's reconciliation but fail this successor. A separate
160-decision invented cohort exercises the real consumer and scorer to verify
the one-terminal-per-trial rule; the successor correctly refuses that reduced
cohort as a complete benchmark result. No authentic cases, labels, reference
values, predictions, model artifacts or private historical answers are read.

## Integration and limits

This is a source-delivered replacement reconciliation function. The existing
hash-locked runner, predecessor files and canonical task/understanding contract
are preserved. The function is **not yet enrolled in the protected runner**.
Integration must authenticate and bind this function at the existing outer
candidate reconciliation call and regenerate the selected source lock and
manifest before claiming the protected path uses it. Existing containment,
complete episode closure, candidate/source identity, result pinning, and
historical-reference replay parity checks must remain in place.

Summary checks cannot recover missing per-decision provenance or verify Brier
and trial-weighted losses from hidden predictions. Consistent confusion
supports do not prove identical case identities. These responsibilities remain
with the trusted scorer and authenticated delivery/recovery chain. This
component does not authorize or execute a replay, fit, candidate campaign, or
direct-model trial.

Neural native interpretation and creation/use of tools, models and pipelines
are separate first-class outcomes on matched cases. This component supports
the latter evaluation path; it supplies no evidence for native interpretation
and does not double the task count. Complete authentic protected replay,
general candidate training/export qualification, and matched direct/tool
participant transports remain unresolved. No biological result or scientific
qualification follows from these generated controls.
