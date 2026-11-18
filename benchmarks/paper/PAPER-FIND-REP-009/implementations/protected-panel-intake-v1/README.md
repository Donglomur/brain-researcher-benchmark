# Protected Figure 3C prediction-family intake

This component implements the missing target-free admission step required by
`primary-endpoint-v1/granular-evidence.v1.json`. It consumes complete prediction
artifacts for the selected 17-session × 2-condition Figure 3C result. It leaves
the historical exposed-label, probability-reconstruction grader unchanged.

It is **source construction, not a qualified predictive benchmark or scorer**.
No authentic support manifest, source fit, protected execution or AI attempt is
included. The original splits, session/animal mapping, shuffle recipe, source
pROC direction and complete-panel scientific comparison remain unresolved.

## Operator interface

`admit(manifest_raw, expected_manifest_sha256, panel_blobs, operator_closures)`
accepts immutable UTF-8 JSON byte bodies. `admit_then_derive` additionally calls
one trusted private derivation **after every panel and closure record passes**.
The module never loads labels, runs participant code, fits a model, derives AUC,
combines cells into an aggregate, or decides superiority. Callback failure
propagates without a retry.

The operator supplies a frozen `thalamus_3c_protected_support_v1` manifest:

- The original 3C workspace and author-script SHA-256 identities already
  recorded by the task, and one of the two information conditions.
- Explicit references to independently qualified original assignments,
  figure/session/animal joins, neural input membership, shuffle recipe,
  metric policy, full-panel comparison and protected execution policy.
- All six source tone identities, the four reported animals after their
  mapping is resolved, and 34 ordered support cells: OFF then ON for each of
  17 unique sessions. Each cell retains its actual source trial IDs, tone IDs,
  training/held membership and observation identity. Both partitions and all
  six tones are required across the cell's source trials; each held partition
  is **not** forced to contain every tone or an invented fixed row count.
- The precommitted candidate program, competent author program and complete
  original shuffle output family, with explicit producer and control identities.
  The original number of shuffle outputs must be recovered externally; there
  is no default repeat count. Repeated control identities and a shared producer
  are retained when declared by the source, rather than deduplicated.

Every prediction body uses `thalamus_3c_protected_predictions_v1`, commits to
the same manifest and its precommitted program, and contains all 34 cells with
the exact ordered held-trial IDs and finite Randomised probabilities. Candidate
labels, scores, extra fields, omitted cells, changed order and selective support
are rejected. Candidate and author probabilities need not agree. Complete
submissions are detached into immutable tuples, preserving each trial and panel.

`operator_closures` is a trusted operator argument, never a contestant claim.
Each record binds the named producer, successful observed closure, exit code,
full output digest and a closure-receipt digest. This module checks that binding;
it does **not** observe operating-system processes or authenticate receipt
contents. The operator must establish actual producer closure separately.

The private callback receives the admitted immutable family. The receipt keeps
`paper_win`, source-auto AUC and predictive AUC null and marks scientific
qualification `not_established`. Callback output remains separate and is not
automatically a paper result. All author/control outputs and private derivations
are evaluator-only; contestants receive only their permitted inputs and output
instructions, not this complete operator bundle or protected labels.

## Scientific and delivery limits

Hash strings are required references, not proof that a scientific question has
been resolved. No caller-supplied manifest, closure flag or passing generated
test qualifies original source support. In particular, the previously exposed
full workspace and reconstruction predictions cannot become protected test
data merely by wrapping them in this interface. Source preparation, exposure
disclosure and protected delivery need separate qualification.

The four-animal requirement reflects the selected source claim; it does not
resolve the reported Table S1 discrepancy or interpret UUID tokens as animals.
The module cannot fabricate missing joins. It makes no independent-animal
statistical assumption and chooses no AUC orientation, effect threshold,
uncertainty method, global mean or win count. Its intake receipt is not a
replacement for the pending full-panel comparison protocol.

Finite implementation limits are 4 MiB per manifest, 8 MiB per output panel,
64 MiB total output bytes, at most 64 panels and 100,000 trials per cell.
These are resource bounds, not recovered scientific counts. A source family
outside them requires a reviewed implementation extension, never truncation.
Memory/thread/process isolation and a deployed runner are not supplied here.

## Validation and integration

Run `python3 -I -S -B test_intake.py` from this directory. Eighteen generated
controls exercise the full 34-cell shape, both information conditions, omitted
late shuffle output, exact trial alignment, label rejection, invalid numerics,
immutable output, closure/hash failures, original support guards, and one-call
private derivation ordering. The small trial identities/probabilities in tests
are invented protocol fixtures, not neural data or paper references.

The existing `thalamus17-artifact-delivery-source` workflow checks only the
historical fixed-reference package. This new command needs explicit component
enrollment by the sole integrator; it is not automatically covered by that job.
No canonical task contract, central policy, published readiness or legacy source
pin is changed by this additive component.
