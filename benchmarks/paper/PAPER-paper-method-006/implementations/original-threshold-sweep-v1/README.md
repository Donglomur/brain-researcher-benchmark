# Original medium-drift threshold sweep

This component fills the complete score-table to threshold-choice step for the Kilosort4 benchmark. It accepts every predeclared threshold, all600 original single-unit target identities, and two supplied score tables. It derives counts using strict binary64 score>0.8, refuses missing or substituted support, and requires agreement for every target. Equal aggregate counts cannot conceal disagreement. The historical registered runtime remains unchanged.

`selector.select_sweep(manifest, exports, max_score_rows=...)` is a pure standard-library function. The generated `fixture()` in `test_selector.py` is an executable schema example. It does not contain biological data or paper results. The manifest binds the medium-drift case, R_paper40 score-policy identity, original input identity, declared threshold order, each parameter-setting identity, grid provenance, and an explicit tie rule. Unknown ties refuse; first/last-declared selection must be frozen in the manifest. The function checks a caller-selected finite logical score-row budget before traversing scores; it never truncates the grid. File admission and whole-process memory/time limits are external.

The output preserves complete threshold counts, both bank identities, the frozen order, ties, selected ID and input hashes. Signed zero is numerically equal when comparing binary64 values. Scores remain within[-1,1]; booleans, nonfinite values, nonnumeric values, out-of-range values, duplicate identities and background MUA roles are rejected. The report makes no inferential claim from the600 nested units.

The [primary paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC11093732/) describes medium-drift threshold tuning under “Spike-sorting algorithm parameters.” Exact dependencies and source-access limitations are recorded in SOURCE.json. The prior count-only selector is in `registered-runtime/payload/k4programme/comparators.py`; the already-reviewed main-panel reducer establishes the complete target denominator and recovery boundary.

Two agreeing tables and hash strings do not prove source authenticity or independent computation. The complete historical grid, parameter bodies, original sorter/wrapper versions and publication invocation remain unresolved. Declaring R_paper40 does not recover its unresolved matching semantics. Historical threshold tuning is not held-out improvement evidence. Scientific decisions remain null, historical equivalence false, and no canonical task, mode, runtime or readiness status is changed. This component does not run a sorter or satisfy other paper obligations.

Validation:15 generated regression methods passed in one shared-pool run, covering complete support, ties, near-threshold rounding, bank disagreement, identity substitution, malformed scores, logical resource refusal and prohibited held-out tuning. No authentic score/data arrays were read or generated. Public CI enrollment is still required; intended command:

```sh
python3 -I -S -B benchmarks/paper/PAPER-paper-method-006/implementations/original-threshold-sweep-v1/test_selector.py
```
