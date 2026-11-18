# Literal source-window and arm projection

This component restores the small projection stage missing from the current
NEURAL-036 checkout. It recovers the pinned historical finite-task window and
arm definitions; it does not reproduce a forecasting result from the source
paper. It performs no loading, fitting, scoring or automatic execution.

`windows.project(x, t, behavior, clock)` accepts a two-dimensional time-by-cell
neural array, its one-dimensional clock, a one-dimensional binary released
behavior proxy and its clock. The operator must already establish that both
clocks are seconds in the same reference frame. Inputs must be plain NumPy arrays
with real, finite, aligned values; masked/object/extended-precision float arrays
are rejected. The neural array must have at least one cell, and clocks must be
strictly increasing. Whole-session denoising and cell selection remain inherited.

All five blocks at origins 0, 60, 120, 180 and 240 seconds are retained. The
historical floating-point expressions are preserved exactly:

| Quantity | Grid within each block | Shape |
|---|---|---|
| Main neural and proxy history | `10.05 + 0.1*j`, `j=0..299` | `(5,300,C)` and `(5,300)` |
| Shifted neural | `0.05 + 0.1*j`, `j=0..299` | `(5,300,C)` |
| Target proxy | Mean at `50.05 + 0.1*j`, `j=0..99` | `(5,)` |
| Persistence diagnostic | Mean of the main proxy history | `(5,)` |

Every value comes from the last source sample at or before its grid point;
out-of-range grids fail. No interpolation, extrapolation, imputation, cell
selection, normalizing, clock rescaling or rounding is introduced. Outputs use
float64. Irregular sampling can reuse a sample; this is the historical definition,
not evidence of a physically correct time map.

The complete output dictionary is **operator-private** because it contains
target and persistence values. `views.project_view(arrays, role, arm)` selects
the original participant fields for `train` or `query` and the four arms:

* `joint`: main neural and proxy history;
* `history`: proxy history only;
* `reverse`: reverse each main neural window along time, with history unchanged;
* `shift`: earlier neural window, with original history unchanged.

Only training views read or return `target`. No view reads `persistence`, and a
query view does not even look up `target`. Outputs are separate copies to prevent
later output mutation changing the trusted operator arrays. The function checks
selected field geometry, finite float64 values, binary histories, and training
fractions in [0,1]. It deliberately does not inspect unselected fields. Different
sessions retain different cell axes; the caller must never stack them as though
neurons correspond.

This is a field-access boundary, **not process isolation or a viewer**. The
operator must serialize only the selected output into a fresh isolated case and
must not expose the operator mapping, original arrays, targets, source filenames
or cross-fold state. Complete seven-mouse/two-session-per-mouse preparation,
opaque identity generation, full28-context execution, source authentication,
matched fit budgets and independent scoring remain separate responsibilities.
The registered runtime is still unqualified and is not changed by this component.

The current scorer uses learned-history minus joint MAE as primary. Historical
public instructions used persistence minus joint; this projection supplies both
fields without changing either current score semantics or historical records.
Physical freezing polarity and per-animal clock lineage remain unresolved.
Controls are diagnostic comparisons, not exchangeable nulls or causal evidence.

`SOURCE_PINS.json` records the inspected source-text identities. Only source text
was opened. No authentic trace, behavior, SUPPORT, TARGETS, POOL, prediction or
model was read. `test_projection.py` uses generated arrays for predecessor lookup,
grid completeness, irregular clocks, no-lookahead, extrapolation refusal,
malformed geometry, exact arm transforms and target-access/mutation boundaries.
It requires an already installed NumPy; run through the existing lightweight
test pool, not a scientific workload. The accompanying numerical-CI discovery
shim at `tests/numerical/test_neural036_projection.py` loads these ten controls
through the existing `generated-numerical-regressions` job, which already fixes
NumPy2.4.6. Integration must register this component's source ownership; no CI
execution or published integration is claimed by the private construction.
