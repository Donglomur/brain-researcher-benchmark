# Original optogenetic row-to-classification seam

`lineage.bind_native_exports(inputs, expected_sha256, mice)` reconstructs the
released row-selection path and binds native table statistics to the existing
`opto-linear-aggregation-v1` input schema. It consumes five operator-pinned CSV
byte bodies named `source`, `first_timing`, `later_timing`, `first_export`, and
`later_export`, plus the independently declared nine-mouse roster. Their actual
source filenames and pinned code locations are recorded in SOURCE_EVIDENCE.json.

The bridge preserves original table coordinates and first-then-later pooling.
Control fields can legitimately appear in both branches and keep distinct IDs.
Every native export row must match every original source cell in the expected
position, allowing exact decimal reformatting and explicit missing-value tokens.
The raw regression inputs retain lap gaps and the full selected window. The
15-lap saved matrix is a different object. Only the native `COM_slope` and
`COM_pval` columns feed classification; interpolated statistics and `shiftDir`
are deliberately not substitutes.

The released density guard has no failure branch when an interpolated span is
at least 15 laps but its `find(COMtraj)` count is too small. Such a row is marked
PFopto without a corresponding matrix row. The bridge raises
`source_alignment_hole`; it does not choose a repaired selection rule. The source
find-count includes missing entries, unlike a count of observed nonzero values.

This is a strict CSV subset: UTF-8, rectangular rows, the original first 21
metadata positions, at least 44 positional lap columns, exact named metadata
and appended native-statistic columns. Ambiguous MATLAB import renaming,
unsupported numeric/missing tokens, rounding changes, or shape changes require
source admission, not guessing. Original file headers/arrays have not been read
in this construction phase. Expected hashes bind supplied bytes; they do not
establish provenance or completeness of the original dataset.

For downstream use, pass `result['derived_rows']` and `result['roster']` to the
reviewed aggregation component. Its pooled all-row and per-mouse classified
denominators remain unchanged. The new bridge emits each retained source row's
raw observed lap coordinates, centered centimeters, window span, branch and
mouse, as well as all row exclusions. It does not recompute MATLAB regression,
verify native p-values, inspect saved MAT arrays, bootstrap, infer a biological
effect, or establish reproduction/improvement. Scientific outcomes remain
unknown. Full empirical and mechanistic paper endpoints remain required.

Generated tests require only Python's standard library and the reviewed old
aggregation file SHA256
`c5f2e396c10309aa12bd488666ebfc496f280882ce087e66e34c6e932775d1fb`.
After both additive components are integrated as sibling directories, run
`python3 -B test_lineage.py` from this directory. Before integration, use
`python3 -B test_lineage.py --aggregation /absolute/path/to/aggregation.py`.
Maintained CI enrollment belongs to the sole integrator. No shared file changes
or original scientific pipeline execution are part of this package.

Next admission: authenticate the three original CSVs and their MATLAB import
schema; retain native exports from the pinned two producers; compare the exact
row map and raw regression inputs before authorizing a native numerical parity
check. If an alignment hole occurs, retain its original row and obtain an
explicit accepted source correction before proceeding.
