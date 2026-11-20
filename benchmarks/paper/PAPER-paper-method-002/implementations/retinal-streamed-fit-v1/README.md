# Complete streamed retinal author-reference fit

This source component connects the frozen Jaxley initializer, TensorFlow loader and original optimizer transition to a complete streamed fit. It is for `PAPER-paper-method-002`, the retinal within-cell, repeated-stimulus endpoint. It is a constructed source component; native completion, numerical equivalence across a complete fit, participant transport, paper reproduction and improvement are **not established**.

The public entry runs 21 epochs. Every epoch processes 47 batches of 256 TRAIN rows and a final 153-row batch, giving 1,008 optimizer updates. The original TensorFlow seed sequence and shuffled-loader iteration remain intact. Singleton gradients are materialized and summed in row order, divided by the actual batch size, and passed once through the original normalization and optimizer transition. Parameters and optimizer states carry across updates; neuronal initial states remain fixed for independent stimuli.

Each epoch predicts all 3,047 VAL rows in chunks of 1,024, 1,024 and 999. It concatenates those predictions before computing the original masked Pearson correlation for all 147 sites. The mean must be finite; no sites are dropped. A snapshot replaces the current best only on a strictly greater mean, preserving the first tie. The selected parameter leaves are copied. After all epochs, the selected snapshot produces predictions for the 128 feature-only TEST rows. This component never computes a TEST score and has no TEST-calcium input member.

The raw somatic `opt[2][0]['Na_gNa']` coordinate remains the exact canonical float64 negative infinity produced by the frozen inverse transform. This is the one explicitly bound parameter-coordinate representation. The unchanged forward transform must give its finite clipped boundary image. All other raw state and all computed losses, gradients, normalized gradients, proposals, predictions and optimizer state must remain finite. Zero normalization norms cause a failed run; the source calculation is not replaced with an epsilon rule.

## Running a separately admitted operation

Use the exact Linux/aarch64 scientific runtime specified in `RUNTIME_REQUIREMENTS.v1.json`, including Python 3.11.3 and the pinned JAX/Jaxley/Optax/TensorFlow versions and installed-source hashes. This component does not install a runtime, acquire resources, enforce physical read-only mounts, or authorize an actual operation. A future operator must admit those separately.

Create an operator-controlled input directory with exactly the scientific files named by an input manifest:

- `model_arrays.npz`: `images`, `currents`, `mask`, `train_targets`, `val_targets` only.
- `model_metadata.json`: the frozen `jaxley-original-model-operation-input-v1` metadata, split, site and numerical-array commitments.
- `morphologies/20161028_1.swc`: the admitted source morphology.

The manifest schema is `jaxley-streamed-fit-input-files-v1`; its `files` maps these relative names to exact `{ "bytes": integer, "sha256": string }` descriptors. The file manifest is a supplied commitment, not evidence that the supplied data was scientifically selected. The future operator must bind it to the approved original data and source preprocessing. ZIP names, duplicates, metadata fields and the absence of TEST targets are checked before any array member is materialized. The frozen numerical validator then validates accepted arrays. The structural mask is public/derivable; observed TEST calcium remains private.

```sh
python full_fit.py --input-manifest /admitted-inputs/INPUT_FILES.json \
  --output /separate-output/fresh-fit --seconds 1800000
```

The deadline is a resource bound, not a shortened scientific profile. There is no epoch, split, update-count or batch-size CLI override. The example deadline is not a duration prediction. Cooperative checks surround singleton operations; an external owner must enforce hard process and memory limits, because a compiling or executing native call can outlast a check.

The output root must be absent, with ordinary directory ancestry, and disjoint from sources and inputs. Complete output includes immutable epoch records, selected and last parameter packets, final optimizer state, context commitments, global validation history, selected VAL predictions, RNG provenance, and the legacy `jaxley-retinal-prediction-v1` TEST submission. `RESULT.json` distinguishes a complete fresh reference fit from failed or partial work. Complete counters are 255,885 training singletons, 63,987 validation singletons, 128 test singletons, 1,008 gradient batches and 63 validation chunks. Partial work is not a complete benchmark result and is not a resume checkpoint.

## Scope and verification

The component is primarily fresh **author-reference** execution. Publishing source does not authorize handing the pinned author implementation to arm A (paper plus data). The paired A/B episode must separately enforce its approved exposures; this component does not qualify physical transport or scientific assessment. Visible validation targets also do not create an enforceable 21-query candidate limit; 21 checks describe the reference program.

`fit_loop.run_production` fixes the full schedule. The private `_run_loop` and explicit primitive arguments of `fit_runtime.streamed_step` support generated analytical controls. They are not exposed through the production CLI. Those controls can verify orchestration and arithmetic on generated values, but do not establish native JAX equivalence, complete-fit stability, resource sufficiency, paper reproduction or improvement.

`frozen/` preserves seven exact source bodies. `source_bootstrap.py` copies the original fit initialization/loader/optimizer span and appends an observational return bundle. `source_transition.py` is the unchanged function extracted from the accepted numerical source. `SOURCE_CLOSURE.v1.json` records all component file pins and exact source anchors. Source and runtime paths are component-relative, with no private evidence-tree loader.

Streaming changes floating-point accumulation order. Earlier accepted short numerical comparisons are limited evidence, not a proof for all 1,008 updates. No full-fit execution is claimed here. Sustained memory use, compiler residency and wall time remain unmeasured for this complete program; the prior gradient-only extrapolation is not an execution guarantee.
