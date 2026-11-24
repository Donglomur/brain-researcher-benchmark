# Comparing two frozen programmes on the complete panel

`paired_programs.compare_programs(panel, plan, commits, outputs, protected_reader, numpy)`
adds an operator comparison between two frozen programmes. `commits` and
`outputs` each contain exactly `reference` and `candidate`, with the same
four-arm commitment and captured-prediction formats accepted by
`scorer.score_study`. The operator supplies one authenticated panel and plan for
both methods. These bind the same fitting/validation/query packet bytes, all
39 sessions, 10 mice, 2,042 query cases per arm, and protected target mappings.
Both programmes must declare the same reviewed tuning-policy and budget hash.
Their source and recipe hashes may differ: improving the programme is the
comparison's intended intervention.

Both complete 156-output submissions pass validation before the first protected
target callback. Inputs are copied before that callback. Each of the 39 target
mappings is captured once; both original scorers use those exact bytes. Missing
cases, a changed query-manifest commitment, a malformed final output in either
method, or mismatched tuning-policy identity stops the comparison before target
access. The caller still owns target custody and authentication; matching hashes
and chronology Booleans from a participant do not establish either.

The result keeps both complete original scores and adds paired per-session and
per-mouse method differences for all four arms and all three original metrics.
Queries are averaged within sessions, sessions equally within mice, then the
ten mice equally. For log loss and sum-of-three Brier, improvement is reference
minus candidate; for accuracy it is candidate minus reference. The comparison
endpoint is the difference in absolute joint-arm natural-log loss, preserving
the current task's primary endpoint. Neither session pooling nor trial pooling
replaces equal-mouse weighting.

The joint-arm comparison includes a descriptive paired-mouse interval using
10,000 PCG64 draws, seed 20261102, and linear 2.5/97.5 percentiles. These are the
existing numerical bootstrap parameters applied to the new method contrast;
the historical neural-increment interval remains separately reported for each
programme. The new interval is conditional on already fitted programmes and
does not include training randomness. True-class zero probability retains
infinite loss; an undefined paired difference or interval is never repaired by
dropping mice, clipping probabilities, or selecting cases.

This is the frozen-program comparison route. It does not deliver a no-tools
participant interface, prove direct neural interpretation, enforce matching
compute, authenticate real programme freezing, or qualify a runtime. A future
direct-observation condition needs its own reviewed observation/response
transport and access-boundary enforcement. Source equality here means equality
of the provided authenticated packet plan, not evidence that an untrusted
participant actually saw only those bytes. No authentic panel, candidate,
reference model, or protected target was executed during this construction.

Generated controls: `python -I -B test_paired_programs.py` in this directory,
using the existing NumPy environment. The eight methods exercise the complete
generated cohort shape, target-call ordering and reuse, unequal nesting weights,
policy and packet mismatch, immutable input capture, nonfinite losses, target
hash failure, and metric-direction reversal. They provide software evidence,
not biological performance. Integrators must enroll this command in the
explicit component CI inventory and update current source bindings as required;
historical recovered modules and their pins remain unchanged.
