# NEURAL-061 participant endpoint delivery

This operator-side component delivers the currently registered participant
endpoint: signed wheel velocity BR mean squared error for every region, with
BC loss and paired reference competence alongside it. The preserved runtime's
`primary_family` is a reference-only regional Holm family; it is invariant to
participant answers. Its `programme_report` also includes the entire `scored`
object, including protected axis joins. Neither is a standalone participant
result artifact for the current registered primary.

`endpoint.py` produces a strict JSON artifact from the existing late-target
score and its original typed `Production`. It reuses the source
`paired_records` and `reduce_common` routines. It accepts complete six-reference
and two-participant arm losses on the same sealed support; missing, duplicate,
wrong-animal, wrong-axis, failed, nonfinite and selectively retained rows are
rejected. It neither opens target files nor computes a substitute target or
fits a model. The numerical source kernels and persistent-state package are
unchanged.

The output makes `candidate_BR_loss` primary and retains all six competence
quantities per region and animal. Degrading BC cannot improve the primary.
Every planned region, 13 animals and 29 sessions remains represented; absent
support yields null metrics rather than a zero or omitted region. One missing
required matching seed excludes that complete session for all operands.
The inherited order is equal timestamps within window, equal windows, all ten
seeds, equal eligible sessions within animal, then equal animals. The report
does not pool regions or rank their different biological support.

Detailed exclusion causes stay in the operator-owned `CommonSupport`; the
compact artifact keeps each unavailable seed/panel/arm location and all
session dispositions. Stable within-report animal/session aliases preserve
joins without copying source identities. They are not a privacy guarantee.
Targets, predictions, fitted state, source paths and private join objects are
not traversed or serialized. The report labels the separate operator reference
family explicitly; it does not convert that family's significance into a
participant score or score an interpretation response.

## Operator integration

Use Python 3.11+ with its standard library. First authenticate and load the
unchanged sibling [persistent-state package](../neural061-persistent-state/README.md)
through its documented captured-source loader. Then load `endpoint.py` as
operator code. Its `n061` imports must resolve to that accepted runtime.

After the existing production and late-target grading gates have completed:

```python
from endpoint import participant_report, report_bytes

# production and scored are the original operator-owned in-memory objects.
# scored was returned by n061.grading.score, not supplied by a participant.
summary = participant_report(production, scored)
body = report_bytes(production, scored)
# Store body only in the operator's explicitly selected external result path.
```

There is no JSON-to-score admission or CLI that accepts precomputed answer
tables. Type and support checks provide consistency; this projection does not
authenticate caller-created scores or grant native/target/publication
authority. It complements the full operator report, which retains exact
exclusion details and reference inference. Shared registration and operator
call-site enrollment remain integration work.

The endpoint follows [task.json](../../task.json) and
[understanding.v1.json](../../understanding.v1.json), which prospectively
selected the existing participant BR loss on 2026-11-16. The source cohort is
423 sessions/126 animals and the evaluation cohort is 29 sessions/13 animals;
all original regions, k=10, anatomy, ten seeds and A0/F/T0/repeat 0 remain fixed.
Upstream source revision remains
`brainbench-org/ibl-bwb@6fbd666fe8170a2165f5198c1f490911424a654d`.
No new external source was acquired for this component.

## Controls and limits

`test_endpoint.py` uses invented complete-count fixtures through the real
collection, support and reduction code. Its independent arithmetic separates
equal-animal weighting from pooled-session weighting, removes a whole session
when one reference seed is absent, keeps a completely unavailable region,
tests that BC degradation cannot earn primary credit, and poisons private
objects to detect accidental traversal. It rejects malformed/lost identities,
invalid loss values and a failed production collection. Run generated checks
through the workspace's shared test pool; they need no scientific data,
NumPy, dependency installation, model or native process.

This is endpoint software construction. Authentic input preparation, actual
atlas support, physical wheel-velocity units, source-reference competence,
native runtime qualification and late-target/publication authorities remain
unqualified. No scientific result or ready-benchmark increment follows from
these controls. The result remains a frozen-program condition: direct
observation and typed viewer delivery are absent, and adaptive/tool conditions
remain prospectively unselected.
