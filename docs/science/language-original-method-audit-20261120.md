# Language Figure 3b: method source and timing

This audit verifies the selected benchmark's source connection. It does not report a model run or establish numerical reproduction.

The exact C1 caller and shared functions from the [paper's recorded Zenodo archive](https://zenodo.org/api/records/20128462/files/analysis.zip/content) match the previously declared member SHA-256 values. The [structured report](language-original-method-audit-20261120.json) records both identities and the inspected benchmark commit. The whole archive checksum was not verified.

On the admitted finite, supplied-PCA input domain, the maintained code follows the inspected method: population mean, centered three-bin response smoothing, complete held-sentence exclusion, fresh `Ridge(alpha=0.01)` fits and pooled Pearson over stitched predictions. The selected endpoint uses layer 5 and lag indices 17–19; it averages those three scores within each session, then weights all 14 sessions equally. The full 224-array panel is a separate scope.

With `prior=20` and 100 ms bins, indices 17–19 are response centers at **−300, −200 and −100 ms relative to aligned feature time**. Away from recording edges, the −100 ms target averages response samples at −200, −100 and 0 ms. Negative centers therefore do not establish strictly pre-feature or causal prediction. Smoothing can also span sentence boundaries.

Remaining limits are substantive: original arrays and runtime were not tested; pandas versus Python CSV/float parsing may affect timing-bin boundaries; raw-feature PCA fallback is outside the selected branch; and supplied PCA does not establish train-only feature fitting. No scientific result or readiness status is promoted by this audit. See the [paper](https://www.nature.com/articles/s41586-026-10691-5) and structured report for scope.
