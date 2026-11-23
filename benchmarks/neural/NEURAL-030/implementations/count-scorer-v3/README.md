# Representable contact-count scores

This successor preserves the NEURAL-030 count target, primary MSE, secondary
Poisson deviance and mean floor, complete trial checks, paired-gain direction,
and equal-trial/session/mouse weighting from `count-scorer-v2`.

A nonzero residual such as `1e-200` against a zero target squares to zero in
float64. Version 2 therefore returns a perfect primary MSE for an imperfect
prediction. Version 3 raises `ValueError` if a trial's computed MSE is zero
while at least one prediction differs from its target. It does not clamp that
loss to an invented positive number. Exact prediction equality still scores
zero MSE, and representable subnormal losses remain valid.

The hierarchy now accumulates the supplied binary-float metrics exactly with
standard-library `Fraction`, divides by the number of units, and converts once
to float. This prevents divide-before-sum from erasing a representable mean:
two trial MSEs of `2**-1074` must still average to `2**-1074`. An exact nonzero
aggregate that rounds to zero is explicitly unrepresentable and is refused;
exact cancellation of signed paired gains remains a valid zero. Other floating
roundoff in per-trial calculations is not claimed to be eliminated.

The operator API remains `score_predictions(expected, predictions,
baseline_predictions=..., mouse_binding=...)`. Arrays, results, and biological
identity bindings remain operator-private. This package is an in-memory scorer,
not an executable participant or an authentic-data result.

`test_score.py` adds four generated regression methods. They compare the
preserved v2 counterexample, exercise candidate and comparator refusals, retain
subnormal losses through unequal hierarchy levels, and retain exact-zero and
ordinary small paired gains. Run `python -I -B test_score.py` with the existing
NumPy environment. During private source staging only, `NEUROBENCH_SOURCE_ROOT`
may identify the read-only repository containing the preserved predecessor.

The active [cerebellar executor](../cerebellar-executor/README.md) now adopts these
exact scorer bytes with a revised captured-source binding and relevant generated
controls. Earlier standalone scorer bodies and the historical four-cell execution
package remain unchanged. This source adoption does not qualify authentic execution
or revise previously recorded scores.
[The preserved v2 documentation](../count-scorer-v2/README.md) retains the source
provenance and unresolved data, identity, and scientific qualification limits.
No original observations, model, native run or neural-understanding result was
used or produced by this repair.
