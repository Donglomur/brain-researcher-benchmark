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

## Later local initialized-row forward and gradient — 2026-11-19 UTC

A separately admitted local operation completed one initialized **training-row forward pass**, followed by **masked, site-summed L1 loss and its gradient**. Independent saved scientific and runtime reviews accepted that limited result and closure of the recorded owned scope. This is distinct from the public input-source package and its prospective hosted generated-control profile; it does not transfer local runtime admission to either.

| Local initialized-row observation | Accepted result |
| --- | --- |
| Predictions / observed sites | **147 / 10** |
| Connection columns | **287** |
| Finite gradient leaves / parameter scalars | **15 / 607** |
| Masked L1 value | **13.509893028590039** |
| Optimizer updates / test-target access | **0 / none** |
| Native wall time / worker-reported time | **263.324 s / 252.876 s** |
| Reported process maximum RSS | **7,168,084 KiB (about 6.836 GiB)** |

The loss is a value for one initialized training row, **not a held-out, paper or benchmark score**. Finite-output claims follow the bound worker success predicates and independent saved metadata/source review; reviewers did not decode or rerun the numerical arrays. No row identity, source case, prediction array, target, parameter or gradient values are released. The process maximum RSS is neither a container peak measurement nor a forecast of full-fit or batch memory, and these timings are not extrapolated to training.

The exact prospective local runtime used **29 wheels and 15 admitted Python modules plus `pyproject.toml`**. It is not a proven historical author installation. Source-loader advisories were retained; no change to the numerical programme or task size is claimed. Whole-record preprocessing before the source-default split remains a limitation.

There was no optimizer update, full training, trained baseline, native LLM reasoning result, replication, improvement or SOTA result. Protected competitor isolation and suite readiness are not established. Full-fit runtime/dependency closure and fair held-out evaluation remain outstanding. The earlier diagnostic, input qualification and hosted-control limitations above remain intact.

| Saved first-row metadata | Bytes | SHA-256 |
| --- | ---: | --- |
| Final scoped handoff | 23,480 | `98c261068950cf9c508590517770b2c54eee765eb2b61fc50480eb8198347036` |
| Saved scientific review | 28,007 | `eb6fea8d5bbc4f564e89655a506ae9451b323456a3942afc5492ef5d316176e1` |
| Saved runtime review | 50,032 | `d7cda69ef02500c693554a98d7ef5e53fd8d05989b72e568abdfdd9dd54b7c0f` |

## Later import/backend qualification and held-out scoring contract — 2026-11-19 UTC

A separate offline operation successfully installed and checked the prospective full-fit dependency stack, then completed **56 explicit imports in one verifier process** and small generated CPU backend checks. The installed inventory contains **73 distributions** after admission of **67 wheel archives**. TensorFlow **2.15.0**, JAX/JAXlib **0.4.28** and Optax **0.2.4** operated together. The operation exited successfully after **21.131 seconds**, and the recorded process/container scope was closed.

This qualifies installation, imports and generated backend operations. It includes no retinal data, neuronal model construction, full training batch, validation selection or held-out score. The initialized-row result above used **JAX/JAXlib 0.4.35**; it does not establish model behavior or memory requirements under the newly checked 0.4.28 stack. A full fit remains a separate operation.

The existing [held-out scorer](../implementations/retinal-heldout/score.py) accepts the final fit's prediction format directly. Its primary comparison is the **unweighted mean of 147 site-wise Pearson correlations**, using each site's field mask and the same **128 held-out row identities** for the author and candidate. It aligns both row and site identities, retains undefined sites, and returns no all-site mean if any site is undefined. It does not replace this endpoint with a pooled or support-weighted correlation.

The private operator packet is derived from the preserved observed targets and frozen site/split metadata, using the serialization bridge qualified below. The existing input programme's `operator_packet` function selects only the test rows; participant inputs contain no test-target member. The prospective fit selects parameters by validation performance before producing its final test predictions. The private packet construction below is qualified separately; complete model fits and prediction custody remain necessary before the scorer can produce an evaluation result. No held-out score, reproduction, improvement, SOTA result or readiness promotion is reported here.

| Saved runtime metadata | Bytes | SHA-256 |
| --- | ---: | --- |
| Import/backend operation handoff | 9,075 | `6bfc0ac6e15aeaa90015ca38b5b4bb5e8535f89f652e1bc1b0c08fa307bedb4a` |
| Independent runtime review | 17,317 | `4d27063dde8dd0b8f51f8763063a9bb9a809fda2ac50c309be7539b92e7c2f1c` |

## Accepted private target construction — 2026-11-19 UTC

The [serialization bridge](../implementations/heldout-target-binding-v1/target_binding.py) constructed an evaluator-private target packet for the frozen **128 held-out rows and 147 recording sites**. It authenticates the preserved observed-target sidecar and paired metadata, reconstructs the field-local mask, and reuses the existing input programme's `operator_packet` function. This operation used local Python **3.11.6** and NumPy **1.26.3**; it is separate from the model-runtime qualification above.

An independent standard-library reader checked every one of the **18,816 label positions and 18,816 mask positions** without executing the bridge or scorer. All **1,345 active target values** matched the canonical sidecar bit for bit after JSON round-trip, and all **17,471 inactive labels** were null. Row order, site order and the field mask matched the frozen metadata. For every site, its **4–16 selected target values** were finite and not all identical.

This qualifies the private target packet. No numerical variance, correlation, model fit, prediction quality or held-out score was computed. The packet and its target values remain evaluator-private. Complete source-default and candidate fits, validation selection, prediction custody and a matched comparison remain necessary before assessing reproduction or improvement. Whole-record preprocessing and the source-default split limitations remain unchanged.

| Saved construction evidence | Bytes | SHA-256 |
| --- | ---: | --- |
| Private target packet, not published | 278,759 | `b8bcc8aa1d4f856c35c1b24f11a8d0481bfdd748c5f74d9392f7a18c9c93b9ce` |
| Accepted operation and review handoff | 6,841 | `057e274d9899cbe3dab503937ed28e117d799979437a86a64f47ac8ef5e3dfb0` |
| Independent target/mask/identity review | 12,547 | `32e36c2c427684318f219f7d82bc1416bff593870d6fccc8273b71faecd6c0bb` |

## Failed original-data batch qualification — 2026-11-19 UTC

One separate representative batch-shape qualification used **TensorFlow 2.15.0 and JAX/JAXlib 0.4.28** with a **7 GiB container memory limit and one CPU**. Installation, runtime verification and generated backend smoke checks passed. The participant archive loaded, model initialization returned, and the loader and optimizer became ready. The first **256-row** update began at **epoch-batch position 0, optimizer-update index 0**.

The scientific child then returned **−9**, and the saved container inspection reported **`State.OOMKilled: true`**. No completed optimizer update or finite loss, gradient, prediction or optimizer-state result was established. The exact internal optimizer state at termination is unknown. Later batch shapes and validation were not reached in the saved source-ordered trace. Independent saved-result review accepted this as a failed representative-batch qualification; the exact recorded process/container scope was closed, with no numerical retry.

The tested resource profile does not establish a minimum memory requirement, the allocation responsible for the OOM event, or full-fit timing. The earlier successful **JAX/JAXlib 0.4.35 initialized-row** result and **0.4.28 import/backend-only** qualification remain separate observations. Neither establishes a completed original-data batch under this profile. Loading the whole participant archive included test-associated input rows, but private test targets were not mounted and no test numerical prediction or score was reached.

This operation establishes no completed epoch, validation-selected model, full fit, held-out score, AI benchmark attempt, paper reproduction, improvement, SOTA result or readiness promotion. Existing registration counts and the whole-record preprocessing/source-default split limitations remain unchanged.

| Saved failed-batch metadata | Bytes | SHA-256 |
| --- | ---: | --- |
| Independent accepted saved-result review | 30,151 | `d971f39afc3f9b853f18ab597d22c75daf109a20929ae56886cb88942e49e03d` |
| Container OOM witness | 1,556 | `b2d517400ac26fc56aef0ed56abffe6acc063707eba5a8000df641b4e67b45fc` |
| Bounded batch-progress journal | 667 | `ef2d094a9aab6fd03daa86bbe8be05d128c41f3eaad4b431feb2b6f66cc8a2b5` |
| Recorded-scope closure | 17,173 | `6ee7354318fc2cc85231ffb454ee8e3c14390bc45b9ad459363e86244b3c266e` |
