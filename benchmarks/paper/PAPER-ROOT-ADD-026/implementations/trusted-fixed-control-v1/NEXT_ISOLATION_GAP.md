# Next isolation gap for the frozen-program lane

The next concrete delivery gap is an enforced boundary around one candidate
coordinate. The existing `DeliverySession` orders observations and commits
outputs; it does not isolate candidate execution. Training responses from one
fold include another fold's query responses. Carrying candidate state between
coordinates would therefore expose held-out answers.

This note selects one bounded next construction step. It is not a claim that
participant delivery has otherwise been completely assessed or implemented.

## Proposed boundary

Freeze the complete method bundle before any observations arrive: candidate
code, dependencies, pretrained weights, configuration and the execution recipe.
Record their identities. For every original coordinate, start a fresh, confined
candidate process tree with one authorized observation and accept one validated
prediction or explicit failure. The source coordinate, column branch, method
identity and ordered prediction rows must remain bound to the existing collector.

Private scratch space within one coordinate is allowed. It must disappear from
the next coordinate's accessible state. Enforce the boundary across files,
caches, inherited descriptors, environment, shared services, descendant processes
and network access. The original input bank, evaluator targets, scorer and other
coordinates' artifacts must be inaccessible to the candidate. Merely launching a
new subprocess does not enforce these restrictions.

The trusted controller must keep the current complete support: all 79 electrodes,
both original 2,054-coordinate branches, and the exact accepted fold allocations.
Every CV coordinate still receives 66 training conditions and six response-free
queries. Full-data jobs remain explicitly exposed outputs. All CV predictions
must freeze before full-data observations within each branch; both complete
panels must commit before metric evaluation.

## Small concrete acceptance exercise

Use invented observations and canary values to test the boundary before proposing
any new authentic-data execution. Demonstrate that a deliberately persistent
candidate can recover a prior coordinate's canary when isolation is absent, then
show the confined runner rejects the same carryover paths. Cover filesystem and
cache paths, inherited handles/environment, background descendants, shared
services and network attempts. Include a positive candidate that uses permitted
within-coordinate scratch and returns a correctly bound output.

The controller must reject missing, duplicate, reordered and foreign coordinate
or row-identity metadata, preserve timeouts and explicit failures, and demonstrate
that rejected or missing commitments cannot open evaluator targets. Incorrect
predictions with valid identities remain scoring errors. Tests of these probes qualify only
the boundary and paths they exercise. They do not establish universal isolation.

No sandbox implementation or execution backend is selected by this note. A
future implementation needs an explicit enforceable mechanism, bounded resource
contract and independent review before it can claim a qualified frozen-program
runtime. The successful fixed-zero control does not satisfy that requirement.

## Separate open requirements

Provider sessions and interactive agent contexts need their own state controls;
the proposed process boundary cannot qualify them. Eligible paper/material
exposure also remains to be defined. The accepted folds are a prospective replay
of the original loop, not recovered historical author assignments. Original
category selection, Figure 4–9 downstream recipes, author-method reproduction
and candidate-improvement evaluation remain separate work.
