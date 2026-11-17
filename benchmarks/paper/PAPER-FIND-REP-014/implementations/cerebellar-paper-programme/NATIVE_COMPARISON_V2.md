# Source-typed native reproduction comparison

`native_compare_v2.py` corrects the numerical comparison of the existing
nine-branch, 67-root reconstruction. Its `compare(reference, candidate, branch)`
and `grade(payload, store)` calls retain the existing interfaces and scoring
denominator. It does not produce or load author results. The original
`native_compare.py`, task definition, historical results and captured execution
manifests are unchanged; the successor is not yet selected by the programme's
worker or frozen runtime manifest.

Reproducing the original findings is a first-class benchmark outcome, separate
from exceeding the original result. This component supports that reproduction
outcome without claiming a completed authentic reproduction. The existing
paired paper-and-data versus paper-and-data-plus-author-code conditions remain
unchanged. The historical contract's improvement-only eligibility wording
requires a separate integration update under the latest user instruction.

The predecessor classifies every leaf beneath `GrCsChronInfo` and
`CFsChronInfo` as discrete. The pinned author `MainData.m` actually stores both
source identities and continuous neural measurements in these tables.
For example, `postrew` and `postomit` are mean response measurements, while
`sessionNum`, `cellNum` and `otherCellNum` are identity columns. The successor
allows the contract's `1e-8 + 1e-6 * abs(reference)` tolerance for the explicitly
reviewed continuous columns, while retaining exact comparison for identities,
counts, sort indices, membership masks and native integer classes. Unknown
chronic-table columns refuse comparison until their semantics are reviewed.

Conversely, source `nnz`/`length` counts (`antbysess`, `ncsbysess`) and cumulative
binary-event counts (`cumultrials`, `cumultrials_opto`) use MATLAB double
storage. The predecessor permits fractional changes within the continuous
tolerance. The successor compares these integer-valued source quantities
exactly. It does not round them, change their units or infer discreteness from
an observed value being numerically integral. Percentages, rates, response
amplitudes and times retain their existing continuous treatment. Integer
status codes must be actual JSON integers, preserving the distinct finite,
NaN, positive-infinity and negative-infinity representations.

All source roots, complete leaf support, class/shape requirements, zero
placeholders for nonfinite values, empty structures, metadata obligations,
branch matched fractions and the existing downstream equal-branch aggregation
remain in scope. This repair does not change any cohort, condition selector,
split, author statistic, participant observation or companion control.

## Source basis

The inspected code is the already cached original release associated with
[Zenodo 21645651](https://zenodo.org/records/21645651). No source or data was
downloaded for this repair. Exact source members, hashes and locators are in
`NATIVE_COMPARISON_V2_SOURCES.json`; the cached author files match the preexisting
`native/BINDINGS.json` pins.

The export helper's source was inspected, without opening any stored target
or prediction. It emits chronic-table leaves as
`GrCsChronInfo/{condition}/column` or `CFsChronInfo/{condition}/column`, preserving
the MATLAB source class. Empty cells and zero-width tables use structural
records without a source class. These formats determine the comparison path.

## Controls and qualification

`test_native_compare_v2.py` uses only small generated export trees. Controls
exercise the two predecessor counterexamples, continuous tolerance boundaries,
exact identity/count comparison, all nine branch root lists, missing support,
nonfinite status codes, empty structures and the private grade entry point.
The final shared-pool run passed all 11 tests (0.008 seconds inside unittest;
0.046751 measured child CPU seconds; 19,972,096-byte child peak RSS). An earlier
11-test pass preceded a correction to fixture root declarations; the comparator
code was unchanged. Two prior pool attempts were busy and launched no child.
Exact receipts are recorded in the external task handoff; generated controls
cannot establish native MATLAB parity or scientific reproduction.

The current canonical contract marks the finding **ineligible for same-task
paper improvement**; this does not exclude a source-faithful reproduction task.
The source variance-partition helper fits and evaluates condition averages
with ordinary in-sample R². The historical fivefold trial-MSE programme is a
separate prediction extension. Neither this comparator repair, reconstruction
agreement nor a larger biological effect constitutes paper superiority.
Authentic full-panel native execution, biological grouping, resource/image
qualification and empirical reconstruction remain unresolved.

Integration must independently review this successor and explicitly select it
in a newly pinned execution closure before any future campaign uses it. The
existing historical closure must remain available. This file does not activate
a candidate, inference or native analysis run.
