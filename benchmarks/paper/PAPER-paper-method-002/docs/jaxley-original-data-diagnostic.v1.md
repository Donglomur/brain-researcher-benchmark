# Jaxley original-data preprocessing diagnostic

Task: [PAPER-paper-method-002](../README.md), **Jaxley: differentiable simulation enables large-scale training of detailed biophysical models of neural dynamics**.

One candidate-only preprocessing diagnostic on 2026-11-19 UTC reached its full **540-second science deadline** and failed before producing a complete candidate result. It reused **21 completed reference exports** from the earlier original-data reference stage; that stage was not rerun. This diagnostic contributes no AI benchmark attempt, model training, scientific score, paper reproduction, benchmark improvement or SOTA claim. Task readiness and the repository's 235 registrations are unchanged.

The bounded progress journal establishes the following:

| Observation | Recorded result |
| --- | --- |
| Morphology construction (`read_swc`) | Returned after **1.696078876 s** |
| Bipolar-cell (BC) field preparation | All **15** fields prepared |
| Full BC workload | **1,500** input frames |
| Completed frame iterations | At least **300**; exact last completed frame unobserved |
| Successive 100-frame intervals | **170.641614828**, **172.936242121**, **173.090426371 s** |
| Completed BC return or downstream candidate result | Not established |

The last marker, at 521.750148156 seconds, records entry into the next frame after 300 prior iterations; it does not establish completion of that next frame. The intervals cover whole frame-loop blocks, including existing sampling and normalization. They locate sustained work in the BC frame stage without measuring the cost of individual operations. Direct convolution is a source-level hypothesis for further profiling; its dominance and any speedup have not been demonstrated. No full-run completion time is extrapolated, and another timeout extension is not established as sufficient.

The reused reference stage retains its existing qualification limits: whole-record preprocessing precedes the source-default split, and equivalence to the authors' historical split is unestablished. There was no complete 1,500-frame BC output, downstream loader result, candidate numerical validation or model fit. See the [reference qualification and historical replay scope](reference-qualification-scope.v1.md).

The task already identifies the original retinal dataset as [Zenodo 3708064, v1.0](https://zenodo.org/records/3708064) and the author experiment revision as `5e7a86282adb9d4603b5546ac5d8dad59aec7cc0`. Public source context is available in the pinned [setup notebook](https://github.com/mackelab/jaxley_experiments/blob/5e7a86282adb9d4603b5546ac5d8dad59aec7cc0/nex/fig4_rgc/01_setup.ipynb), [morphology](https://github.com/mackelab/jaxley_experiments/blob/5e7a86282adb9d4603b5546ac5d8dad59aec7cc0/nex/fig4_rgc/data/20161028_1.swc) and [data utilities](https://github.com/mackelab/jaxley_experiments/blob/5e7a86282adb9d4603b5546ac5d8dad59aec7cc0/nex/fig4_rgc/utils/data_utils.py). These links identify the original source context; the saved diagnostic also pins its reviewed workload, progress instrumentation and BC producer in the [JSON evidence summary](jaxley-original-data-diagnostic.v1.json).

The summary is derived from the following saved metadata identities. Their hashes identify the reviewed evidence; complete private receipts and numerical payloads are not included in this publication.

| Saved metadata | Bytes | SHA-256 |
| --- | ---: | --- |
| Completed diagnostic handoff | 9,525 | `6736206628c200ed3c210e61a9e4e1bb20465ab40591da68cf391bfc261b47da` |
| Saved scientific review | 26,498 | `8fdbc72ddd83108d4eb88e3388a59e20ab2485a0faa617788571a13ee9e4f21f` |
| Bounded progress journal | 3,789 | `af41009ecf65edcbfec7f0e5c2fcb976f6fb27bc6dcd4074379cfdd67261639f` |
