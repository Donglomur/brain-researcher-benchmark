# Original phase endpoint binding

This repair prevents the existing MotorMINT recipe validator from silently
changing the original phase endpoint. The [registered source contract](../../improvement.v1.json)
requires circular means and distances for MC_Cycle phase. The previous
`validate_recipe` checked behavioral group names and column assignments but
accepted `circular_columns: []` for a bundle containing `phase:0`. It also
accepted a circular assignment for linear variables such as position.

This endpoint repair supports both original-finding reproduction and same-task
improvement as separate outcomes. Neither outcome is demonstrated by software
controls alone.

The active repair is in
[`bindings.py`](../paper-method-011/full-motormint-v1/runtime/mintbench/bindings.py).
Its exact predecessor is preserved in
[`historical/bindings.before-phase-repair.py`](historical/bindings.before-phase-repair.py).
The repair requires the circular-column list to match the phase dimensions in
the already validated original output schema. A phase period must be finite
and positive; a bundle without phase must have no period. The source factorial
linear-readout cells still omit phase, leaving their other 12 MC_Cycle variables
linear. Other original datasets remain linear.

The source units and numerical phase period remain externally specified.
Accepting a positive period does **not** authenticate radians, degrees, cycles,
branch cuts, original 5-ms phase aggregation, or historical MATLAB equivalence.
No numeric period is selected by this repair. Existing metric-bank arithmetic,
groups, splits, causal/acausal conditions, 17 modules, nine empirical datasets,
and scientific qualification requirements are unchanged.

The generated controls include a three-sample phase trace that crosses the
cycle boundary. Circular R2 is above 0.14 while linear R2 is below -0.50 for
the same values. The preserved validator accepts the wrong metric and the
repaired validator rejects it. This is a software counterexample, not a
measurement on neural data. The remaining controls cover wrong columns,
booleans and noninteger column indexes, invalid periods, all four primary
dataset schemas, the source linear-readout exclusion, and input immutability.

Run `test_phase_recipe.py` from a reviewed lightweight test-pool command. It
uses the standard library and the existing pinned numerical banks. No original
neural recordings, targets, models, or native MATLAB execution are needed.

The task is still **source unresolved**. This repair does not establish a
reproduced baseline, improvement readiness, source-paper superiority, or SOTA.
The existing historical manifests retain their original pins. Before enabling
the current inspection route on this changed runtime, the integration owner
must add the new `bindings.py` digest to the current source binding; the task
builder does not edit that shared binding.

Source basis: the paper's [Decoding R2 methods](https://pmc.ncbi.nlm.nih.gov/articles/PMC11790250/)
and the [retained source contract](../../improvement.v1.json), evidence
`mint-paper-metric`; the original dataset and factorial dimension mappings
remain in [`SCOPE.json`](../paper-method-011/full-motormint-v1/runtime/SCOPE.json)
and [`bindings.py`](../paper-method-011/full-motormint-v1/runtime/mintbench/bindings.py).
No paper fetch or new source-data acquisition was needed for this repair.
