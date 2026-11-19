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

## Later complete-input qualification — 2026-11-19 UTC

A later, separately admitted operation completed the unchanged shared BC procedure over all **15 fields and 1,500 frames**. Independent saved-result review accepted complete original-source **pre-model input construction**. The operation exited successfully, and its recorded process/container scope was closed. The earlier 540-second failure above remains a historical result; it has not been relabeled as a success.

The full BC result was finite `float64` with shape **1,650 × 1,500**. The existing consumer then used the first **1,024 frames per field**, producing **15,360 rows**, **147 recording sites**, **287 connection columns** and **150,528 observed mask entries**. The shared implementation performed 1,500 frame convolutions and one fixed-normalizer convolution. This completion does not establish an algorithmic speedup; no sampled DIRECT or resident-JIT replacement was adopted.

This result qualifies the exact separately reviewed producer, consumer and composition sources identified in the [JSON summary](jaxley-original-data-diagnostic.v1.json). It does **not** qualify the repository's frozen `registered-runtime` preprocessing or model entry as an interchangeable implementation. That published snapshot has distinct input interfaces and remains unchanged. The accepted input programme's numerical arrays and complete operator receipts remain private; this diagnostic document publishes only aggregate metadata and source/evidence hashes.

Whole-record preprocessing and all-ROI delay selection still precede the source-default downstream split. Historical split/cache equivalence remains unestablished. No model initialization, forward/gradient qualification, fit, prediction score, paper-result reproduction, same-task improvement or benchmark-readiness promotion follows. An independently qualified model runtime and a separately selected model operation remain necessary.

| Saved completion metadata | Bytes | SHA-256 |
| --- | ---: | --- |
| Final input-construction handoff | 12,074 | `515bcaf5f992fa5800c916e905dcdf29bd68bb6f72f8aed15aa2f8dc7a6a3154` |
| Scientific result review | 42,760 | `1a0a6973e678314896047d38678ee0402f6740bae3cd4337dab091f253fa3489` |
| Runtime result review | 57,215 | `d50eed95f2e26c4912a5fbd1787f365ff6ee1eea35cf952247a169653b8ee16c` |

### Unchanged input-programme source delivery

The [original-input-programme-v1](../implementations/original-input-programme-v1/) component exposes the six exact source modules used by that accepted input construction: `portable_consumer.py`, `input_binding.py`, `camera_centers.py`, `bc_producer.py`, `author_kernels.py` and `input_composition.py`. Their numerical bodies and module names are unchanged. They are callable source functions, not a new standalone command or a replacement for `registered-runtime`'s Context API.

The reference functions retain their explicit **CPython 3.11.3 / NumPy 1.24.3 / pandas 1.5.3** guard. The separately admitted modern BC/composition environment used **NumPy 1.24.3, pandas 2.2.3, JAX/JAXlib 0.4.35**, with CPU and JAX x64 required by the producer. These are separate runtime profiles; the modules do not install or authorize either environment. Original geometry, camera/noise arrays, decoded metadata, frozen split and numeric-crossing receipts must be supplied by an independently admitted caller.

`camera_centers` receives the `portable_consumer` module; the reference portions of `input_composition` use that same collaborator, while its modern composition receives `input_binding`. The BC producer receives `author_kernels.make_author_kernels`, admitted geometry and a caller-owned checkpoint function. No private host orchestration, file loader, raw array or evaluator target is included. Existing [author-code license and attribution](../implementations/registered-runtime/programme/LICENSE-author-code.txt) remain applicable. Installing these files is not a newly observed execution and does not qualify the frozen full-paper model path.

### Portable generated-control entries and their limits

The same component also contains the separately reviewed [generated-control entries](../implementations/original-input-programme-v1/README.md), their bounded reporting helper and source descriptor, for **12 source files in total**. The two entries preserve **20 consumer/interface controls and 15 BC numerical controls**. They test generated inputs; they are not standalone authentic-data or model-execution entry points.

Their prospective hosted profile is **CPython 3.11.18 on Ubuntu 24.04 / x86_64**, with the explicitly listed scientific packages in the component README. It is distinct from the historical runtime that produced the accepted complete-input result above. In the generated camera-metadata context only, the boundary controls substitute the historical camera version gate. That substitution does not qualify legacy pandas pickle decoding, native reference grouping, the historical runtime or model readiness. The original six modules and their historical guards remain unchanged.

One separately reviewed **17-case stdlib reporting/transport campaign** passed. It exercised bounded artifacts, exact result validation, malformed/partial output and deadline handling; it executed **zero scientific controls**. The new hosted profile and both real suites (**20 + 15 controls**) remain unexecuted at this publication cutoff. Neither the transport result nor the earlier original-input qualification substitutes for those future hosted observations.

Each generated entry requires its exact source closure and a fresh artifact directory. Its declared two-GiB, one-CPU exposure is conservative accounting, not a measured RSS or CPU-affinity guarantee. The input-programme source handoff and reporting review are identified by **18,687 bytes / `820ae1d3ef7e190aaa0494dc87d508c731c0dfb937d696422969dd3668fa1818`** and **13,077 bytes / `1dde145395532aae49b08f41cc15c766019bb072077e65ac35866758d4a86640`**, respectively. No later model/first-row, score or readiness result is included here.
