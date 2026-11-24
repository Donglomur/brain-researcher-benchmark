# Validate the complete reference bank before opening choices

NEURAL-094's standalone `score_cohort` previously checked each session's trusted
reference after loading that session's protected choices. A missing, stale or
malformed reference in session 39 could therefore expose choices from all 39
sessions before grading refused. The registered failure policy requires every
candidate and reference table to validate before the first protected choice read.

This additive scorer authenticates and validates all 39 four-view reference
tables after the 78 candidate tables, then retains their normalized probability
matrices for scoring. A reference loader is called exactly once per session.
Only a complete bank reaches the private-target callbacks. The unchanged
candidate preflight still precedes both kinds of loader. Reference output is
operator-owned: this ordering does not turn caller assertions into trusted
closure evidence or prove process isolation.

The successor starts from `stable-loss-v2/score_adapter.py`, pinned at
`d88210d05247d95ca6ac244fadf549b07c4ff2889d4ed475639c5aa3b342db78`.
Its probability validation, nonfinite semantics, stable paired reductions,
original first 100 ms final-choice endpoint, competent nuisance primary and
trial → session → equal-mouse weighting are unchanged. The complete 39-session,
10-mouse scalar interface and all required predictions are preserved. This is
a repair to the standalone whole-population scorer; the full regional grader
already prevalidates its complete prediction bank and is not altered. The
regional scope remains 73 literal labels, 2,628 pairs and five fixed seeds.

Run the generated controls with an existing NumPy environment:

```sh
python3 -I -B benchmarks/neural/NEURAL-094/implementations/reference-preflight-v1/test_reference_preflight.py
```

The test loads the actual published manifest validator and metric core and
constructs an invented complete 39-session/10-mouse interface in memory. It
reproduces the predecessor's 39 private callbacks on a malformed final reference,
checks zero private callbacks for malformed, missing, stale and nonnormalized
late references, checks candidate failure before any loader, and verifies exact
score parity on the valid full cohort. It uses no authentic neural recordings,
estimator fits, candidate models, provider calls or scientific outcomes.
`NEURAL094_TASK_ROOT` may point to the enclosing read-only task directory during
source construction; normal repository execution needs no override.

`SOURCE.json` records component pins. Existing closed source/runtime manifests,
the stable-loss runtime recipe and historical source bodies remain unchanged.
The integration owner must explicitly bind this successor and its affected test
in current registration/CI. Using this scorer in a closed native runtime requires
a new independently authenticated numerical/runtime composition; the old
`stable-loss-runtime-v1` recipe still identifies its existing scorer. No runtime
or registry selection is performed by importing this component.

All authentic custody, data and reference qualification, complete native
execution, and direct-observation delivery remain unresolved. Source checks do
not establish neural understanding, equal exposure, no-tools enforcement,
causality, submission readiness or a scientific performance improvement.
