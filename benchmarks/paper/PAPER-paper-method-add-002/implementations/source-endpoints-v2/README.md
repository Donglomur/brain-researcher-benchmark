# Finite summaries for the source decoding endpoint

This successor preserves the original Fig.2 trial, fold, repeat, XY pooling and population-SD definitions. It changes only how already finite R² values are aggregated. The previous implementation could return infinite mean or SD when intermediate sums or squared deviations overflowed even though the requested answer was representable. Repeated-trial means had the same intermediate-sum problem.

The successor scales by the largest absolute score during each equal-weight reduction, then restores the original units. Repeated-occurrence means use a separate scale for each trial, so an extreme score on one trial cannot erase a small score on another. Every trial and repeat retains its original weight. A genuinely unrepresentable per-trial R² still fails; there is no clipping, favorable-subset selection, changed baseline or new success threshold. Explicit untested-trial NaNs retain their predecessor meaning. Ordinary scores remain equivalent within floating-point rounding.

The current standalone scoring route is this successor's entrypoint:

```sh
python3 -B benchmarks/paper/PAPER-paper-method-add-002/implementations/source-endpoints-v2/endpoints.py score-fig2 \
  --input /operator/frozen-predictions.npz --recipe source_code_ridge1 \
  --summary /operator/source-fig2-summary.json --private-details /operator/source-fig2-details.npz
```

Use the same `score-fig2` and `score-reconstruction` arguments described in the preserved [v1 operator interface](../source-endpoints-v1/README.md), substituting this directory's `endpoints.py`. The original [source map](../source-endpoints-v1/SOURCE_MAP.json), scientific definitions and unresolved paper/code discrepancies remain in force. The original v1 files and producer/bridge snapshots that pin v1 remain unchanged; these frozen bindings are not silently migrated by this addition.

`test_finite_summaries.py` contains three new generated regressions: representable extreme mean/SD, ordinary population weighting plus true R² overflow, and complete 20×5 source-fold/per-trial aggregation. They perform no fitting and read no original observations. Their pass/fail evidence is recorded separately by the selected source campaign. No authentic benchmark execution, reproduction, improvement or SOTA follows from these arithmetic checks.
