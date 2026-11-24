# Figure 5 complete-group descriptive companions

This source component fills the missing connection from the existing keyed
Figure 5 fit export to the notebook's group mean/SEM companions (cells 15–16).
It accepts `fit_export.export_panel(...)["exports"]` and recalculates the pinned
coefficient diagnostic before summarizing every supplied cell in both activated
and suppressed groups. It does not accept an independently supplied diagnostic
or summary, fit models, read original data files, or infer cell identities.

For each group it retains the ordered cell IDs, complete value vectors, full
precision mean and sample SEM, and the source's two-decimal display values.
The operators are `numpy.mean`, `scipy.stats.sem` with the source default `ddof=1`
and propagation of missingness, and `numpy.round(..., decimals=2)`. The upstream
diagnostic rejects nonfinite coefficients and covariates; no complete-case
selection occurs. A singleton supplied roster retains its mean and explicitly
undefined SEM. Limits refuse the whole panel rather than selecting fewer cells.

The notebook's literal intercept and the conditional-model intercept remain
separate named companions. This component selects neither interpretation and
preserves the full underlying diagnostic. It does not resolve the historical
pymer4 coefficient semantics or authenticate the supplied roster, factor map,
original R model frame or baseline values. Counts are relative to the supplied
rosters, not proof of the published 96 activated and 82 suppressed identities.

The descriptive unit is the equally weighted cell, as in source cells 15–16.
These SEMs are not independent-animal uncertainty or a measurement-noise test.
S13 permutation/refit policy, original animal/experiment joins, fit defaults,
source population and primary same-result improvement criteria remain unresolved.
No new p-value, score, tolerance, comparison margin or acceptance decision is
introduced. Numerical runtime versions are recorded; historical arithmetic
equivalence and scientific readiness remain unqualified.

```python
companion = summarize_panel(
    fit_export_result["exports"],
    limits={"max_cells": 1000, "max_trial_rows": 100000, "max_output_bytes": 1000000},
)
```

The example limits are caller-selected engineering bounds, not scientific cohort
sizes. The pinned diagnostic is the adjacent `fig5-coefficient-alignment-v1`
source. NumPy and SciPy must already be available. Integration may use:

```sh
python3 -I -B benchmarks/paper/PAPER-FIND-ADD-015/implementations/fig5-group-summary-v1/test_group_summary.py
```

`--alignment-source` allows the same exact pinned source at an explicit path for
staged controls. All test observations are invented and no model fitting occurs.
Tests establish this descriptive boundary only, not original-data performance,
complete primary reproduction, improvement or a measured code-access advantage.
