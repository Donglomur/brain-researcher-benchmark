# Complete collection receipt commitment

The preceding completed-collection grader authenticates all phase receipts, but
its outer summary commits predictions and costs rather than every receipt byte.
A coherent change to an inference `REQUEST.input` and its `CLOSED.request` pin
can therefore preserve the original outer summary and numerical grade. The
generated counterexample is retained in this component's tests. It demonstrates
a provenance limitation, not score inflation or access to operator files.

`receipt_bound_grading.py` adds a new operator-only sealing and replay API. It
preserves the original source files, full45/27-training/9-development/9-query
session split, seven arms in both panels, token vocabulary, session-macro PER,
and separate protected-gold authority checks.

`seal_collection(selection, external, legacy_raw, c, bodies, read)` runs the
original complete collection admission and commits every distinct path and its
captured byte identity: selection, external closure, public manifest, complete
record, commitment, both programmes, all phase requests and native/closed
receipts, all model seals and models, raw predictions, and both output panels.
Repeated reads of the same path must agree. Its compact seal contains a digest
of the sorted full read set and the original joined summary. No private query
target or source array is opened. The public manifest retains its permitted
training/development/calibration labels. Runtime file paths live only in the
external seal/read-set digest.

The operator must independently retain the seal's byte/SHA-256 pin immediately
after the admitted closure and before later receipt changes. A seal created
after modification cannot establish the earlier state. This successor cannot
retrofit old closures with a historical commitment or authenticate a false
execution record. The returned bytes and trusted pin belong outside public Git.

`evaluate(request, seal_raw, seal_pin, legacy_raw, c, bodies, read)` checks that
trusted pin, repeats complete admission, and requires the identical commitment
before calling the unchanged predecessor grader. Every collection read in that
grading pass is bound to the verified pin, preventing a change between the
verification and scoring passes. The original grader still requires its input,
method, runtime, natural-exit and private-grading records and opens gold once.
The returned `grade` is exactly the original result; the enclosing record adds
the receipt-seal identity and file count. No score threshold or scientific
qualification is added.

The caller supplies `legacy_raw` as captured bytes of the pinned predecessor
`completed-collection-grading/grade_completed.py`; this component checks its
identity before execution. `c` and `bodies` must come from the existing reviewed
producer bootstrap and exact 25-member source manifest. This API deliberately
has no candidate-launch or native-execution command. Operator integration must
capture this new component itself and qualify its complete source closure and
resource envelope. Both verification and grading reads must use the **same**
budgeted reader; the additional full readback is real work, not covered by an
old measured runtime merely because that runtime was adequate for one pass.

The generated unittest controls use the existing invented full45-session,
54-row,164-phase collection and actual original admission/scoring functions.
They preserve the predecessor counterexample; verify unchanged grades, including
the unequal-session denominator example; reject coherent inference/adaptation
and native-receipt modifications; and reject late mutation, seal substitution,
private-target aliasing and unauthorized original grading. They establish
software behavior only.

Authentic86-member source preparation, trial-count reconciliation, retained
query support, feature/electrode provenance, runtime isolation and reference
competence remain unresolved. No authentic input, model, candidate, solver,
native process, direct interpretation or viewer result was executed here.

Scientific source lineage remains [Dryad v5](https://doi.org/10.5061/dryad.dncjsxm85)
and the [pinned official T15 source](https://github.com/Neuroprosthetics-Lab/nejm-brain-to-text/tree/980a5b7e96392210edf976d76bdb5d15d2e0e62b).
Those sources do not establish the compact reference's competence or this
component's execution qualification.
