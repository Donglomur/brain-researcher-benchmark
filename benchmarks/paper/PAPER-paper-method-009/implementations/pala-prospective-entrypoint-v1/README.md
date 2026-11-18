# Corrected Pala prospective entrypoint

The historical evaluator command calls its own loader, which labels source
volts as millivolts. The separately reviewed `pala-source-adapter-v2` corrects
that boundary, but was not connected to an executable analysis route. This
entrypoint connects its authenticated, V-to-mV converted recording to the
unchanged prospective evaluator. It never calls the historical loader.

```sh
python benchmarks/paper/PAPER-paper-method-009/implementations/pala-prospective-entrypoint-v1/entrypoint.py --mat /approved/data.mat --plan /approved/plan.json --output /approved/new-report.json
```

This is **prospective calibration source**, not an original Fig. 3 reproduction
runner or improvement scorer. No authentic input, fitted analysis or empirical
result has been run through it. In particular it does not resolve the original
eight-neuron/five-mouse identities, twenty-segment mapping, 25/50 ms bin conflict,
voltage-spline policy or mathematical definition of the published 23% discrepancy.
The retained evaluator still requires its explicit held-trial prospective plan,
runs both voltage-bin choices and reports its original holds. Its biological
fractions are not optimized or relabeled as performance scores.

The entrypoint verifies the exact corrected adapter, evaluator and unchanged
upstream estimator/package/license before import. A fresh Python interpreter
with NumPy and SciPy already installed is required. It authenticates the original
MAT through the corrected adapter, validates that loader's original full-row and
unit-conversion receipt, and passes those same trial objects to `evaluate`.
Original payload size, MD5 and observed SHA-256 accompany the report. These
checks do not prove cohort identity, biological validity, historical runtime
parity, source immutability during execution or OS process isolation.

Plans reject duplicate keys, nonfinite JSON numbers and more than 256 KiB.
Every cell's split structure and disjoint trial IDs are checked before loading
recordings. The pinned population audit then establishes the complete eligible
source roster, and every cell's trial coverage is checked before `evaluate` can
fit any cell. This prevents a valid first cell from being fitted before an
invalid later-cell split is discovered. The unchanged evaluator repeats its
population audit and checks, so this adds a full source scan; no empirical cost
or runtime qualification is claimed. Output must be a new file in an existing
directory. A finite report (at most 16 MiB) is published through an exclusive
same-directory link; an existing or concurrently created destination is never
replaced. Failures do not leave a partial report at the requested destination.
No execution resource admission is implied by these serialization bounds.

Tests exercise source-pin refusal before import, corrected-loader dispatch and
trial-object identity, plan/receipt failures before evaluation, preservation of
prospective claims, and exclusive complete report publication. Generated stubs
test orchestration; they are not authenticated MAT inputs, fitted results or
evidence for the unresolved Fig. 3 endpoint. One test imports the five actual
pinned source members without reading recordings or fitting a model.
