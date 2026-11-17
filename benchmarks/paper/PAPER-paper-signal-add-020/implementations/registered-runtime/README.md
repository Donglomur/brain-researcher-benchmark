# Conditional reward/emotion ERP numerical scorer

**Zero coefficient error can coexist with an incorrect covariance or p-value report.** The qualified wrong-covariance and wrong-tail controls both returned primary error `0.0` while `reported_P3b_arithmetic_consistent` was false. The wrong covariance also had a positive covariance discrepancy. Read those diagnostics alongside the primary error; this component provides no joint scientific-success score.

This local scorer accepts one UTF-8 JSON summary for the specified conditional FRN, P3a and P3b models in *Separable neural signals for reward and emotion prediction errors* (2025). Its primary metric is equal-model coefficient RMSE in reference standard-error units, with lower values indicating closer numerical reconstruction. Covariance discrepancies, retained-row compatibility and independently recomputed P3b contrast arithmetic are reported separately. A `scored` status means these numerical outputs were calculated; it does not mean every reporting check passed.

The contract retains 6,403 source rows and 41 participants. Terms, covariance axes and row order may be rearranged. A declared alternative analysis receives `needs_adjudication`. Malformed summaries, incompatible rows/uncertainty and unsupported finite-extreme arithmetic receive explicit null outcomes. There is no positive-effect requirement or manufactured success threshold. Optional interpretation prose is unscored, and submitted code is not executed.

Use `public_contract.json` for exact fields, formulas, row selection and arithmetic definitions. For example, from the project root:

```bash
python3 benchmarks/neuroscience/paper-signal-add-020-reward-emotion-erp/score.py --submission /absolute/path/submission.json --output artifacts-build/erp-summary-score-new --other-reserve-bytes 147000000
```

The output directory must be fresh. The 60-second outer wrapper reserves 12 MB and checks current disk limits. The other-reservation argument must include all active work; the common manifest currently uses a conservative 147 MB. Runtime execution uses the existing local image and workspace assets, so this package is not yet portable.

Qualification passed 18 scoring controls, eight generated boundary checks and an actual interrupted-wrapper test. All 18 worker containers and three activated process groups were verified absent. Existing scientific fits were reused; no new data, fit or LLM attempt was added.

The scorer covers a fixed-model numerical component of one existing paper assignment. Positional ERP/behavior row correspondence remains assumed. Open scientific alternatives, free-text scientific reasoning, complete paper reproduction and independent improvement remain unqualified. The actual provenance and receipts are under `authoring/reward-emotion-erp/scoring-adapter-v1/execution-001`.
