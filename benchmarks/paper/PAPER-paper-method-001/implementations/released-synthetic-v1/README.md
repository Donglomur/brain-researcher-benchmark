# Released synthetic example calibration component

This component recovers and implements the complete released `examples/synthetic.py` recipe at [badooki/dimensionality revision f18de358](https://github.com/badooki/dimensionality/blob/f18de35818502744329f7c92bb17a80af8f48549/examples/synthetic.py). The exact original source is in `upstream/synthetic.py`; its Git blob and SHA-256 identities are recorded in `SOURCE.json`. The upstream MIT license accompanies the recovered code. No earlier implementation, policy, task definition, numerical reference or contract is changed.

`released_synthetic.py` supplies the original observation generator, all source case identities, an explicit call to the existing pinned author estimator, and the original per-point ordinary mean and SEM. It retains all 400 draw slots and 1,600 estimator records. It does not create a final-paper improvement criterion.

The exact source example uses latent dimension 50, `X @ W / 50`, independent entrywise additive noise with variance 0.2, and **one** observation matrix. It passes that matrix once to `participation_ratio(..., return_all=True)`. The two sweeps use sizes `[10,20,30,50,75,100,150,200,300,500]`, with Q fixed to 100 or P fixed to 200, and seeds 0–19 reset at every point. The four estimators share each observation. No pre-centering or second repeat is added. All 20 seeds remain in the ordinary mean and sample-SD/√20 SEM, including nonfinite values; the code does not use `nanmean`.

The P=200/Q=100 point appears in both panels and reuses the same 20 matrices. There are 400 source slots but only 380 distinct dimension/seed tuples. Reusing seed IDs at other dimensions also creates dependence across points. The source SEM is a within-point display statistic, not a pooled confidence interval or independent replication across all slots.

## Callable operations

- `cases()` returns the fixed complete source roster, without numerical work.
- `observation(case)` reproduces one source matrix with NumPy's `default_rng(seed)`. It returns the single allowed matrix; no latent X/W or latent target is returned.
- `author_case(case)` explicitly evaluates the unchanged author estimator after checking its current task-local source hashes. It records NumPy and opt_einsum versions and preserves nonfinite outputs or arithmetic failure. This operation is for separately authorized calibration work; it has not been run against the full source panel here.
- `summarize(records)` requires the full 400 distinct source slots and a common numerical environment. It preserves exact NaN/±Inf kinds and per-point failure counts. A thrown estimator makes that point's summary unavailable, rather than averaging its survivors. Negative finite estimates are retained and counted.

The component has no automatic runner, installation side effects, data acquisition or import-time numerical work. NumPy and opt_einsum are required for the author route. The two approved test interpreters have NumPy but lack opt_einsum; no dependency was installed. Source generation and summary controls are executable there, while the real author import remains unverified. The old programme's fixed BUILD_ONLY policy is unchanged. No numerical baseline, candidate, native JAX parity or scientific qualification is supplied by this component.

## Consequential source discrepancy

The source labels this script a Figure 1 reproduction. The [paper-improvement contract](../../improvement.v1.json) preserves finite-sample participation-ratio accuracy, the source two-repeat noise correction, and the complete original synthetic/biological conditions. A script label does not settle which final-paper panels its single-trial noisy output reproduces.

The recovered `legacy/synthetic/Linear_example.ipynb` cells, separately pinned in `SOURCE.json` and included as exact code-only projections, differ again: P=200, ten integer-cast logarithmic Q ordinals from 10 to 1,000, 200 iterations, no added noise, advancing JAX keys, and active calls to the older uncentered `getest_all0(Phi,Phi,P,Q)`. Its plotting cell reports ordinary MSE to the analytic dimension 50 and NaN-skipping curve summaries. Its MSE is a real source-defined quantity, but it is a **different released analysis** from the two-panel noisy example; copying that loss onto the latter would silently change the recipe. Neither source supplies an authenticated numeric final-paper estimation-risk baseline.

The final-paper comparison therefore remains unresolved: exact final Figure 1 grid/estimator/noise/reduction correspondence, final Figure 2 session and modality mapping, original biological draw counts, native backend qualification, meaningful effect, protected comparison and uncertainty remain open. The four biological branches and the existing full-programme obligations stay intact. This recovered source route is calibration only, not a smaller replacement benchmark or evidence of paper improvement.

## Software checks

`test_released_synthetic.py` compares generated matrices byte-for-byte with the exact upstream generator extracted through its AST, checks the reused cross-panel matrix, independently checks the source SEM arithmetic, and tests missing/duplicate cases, altered source identities, mixed environments, NaN/Inf and arithmetic failures. The author estimator and dependency version metadata are mocked when checking call shape. Missing dependencies must propagate as infrastructure errors. The real author import check is explicitly skipped when opt_einsum is absent; no real author estimation or full synthetic panel is run. Run this test only through the coordinated lightweight test pool in the repository's current work protocol.
