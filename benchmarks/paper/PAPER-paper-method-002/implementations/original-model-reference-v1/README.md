# Original-model reference v1

This is a portable source component for PAPER-paper-method-002. It contains the accepted prepared-input model entry and three authored siblings unchanged, the unchanged singleton-accumulation helper, and a separately versioned full-fit route. It contains no arrays, private targets, morphology bodies, mechanism package bodies, or private admission driver.

`streamed_model_operation.py` provides `fit_source_defaults_streamed_v1` and the CLI below. This route runs all original training updates and validation checks. Its source supports the same real-arithmetic batch objective; floating-point equivalence, native memory use, throughput and full-fit feasibility remain unqualified. It is not a completed baseline or a scored result.

## Inputs and invocation

Use an independently qualified model runtime and authenticate the whole input files before invocation. From this directory:

```sh
python -B streamed_model_operation.py \
  --mode fit-source-defaults-streamed-v1 \
  --arrays model_arrays.npz \
  --metadata model_metadata.json \
  --morphology-prefix data \
  --output streamed-fit-output
```

The output directory must not exist. The morphology is read from `data/morphologies/20161028_1.swc`. The original `model_operation.py` CLI remains available unchanged for its original first-row and vectorized full-fit modes; these modes are separate from the streamed route.

The prepared packet uses schema `jaxley-original-model-operation-input-v1` and exactly five arrays: `images`, `currents`, `mask`, `train_targets`, `val_targets`. It has 15,360 rows, 147 sites, the frozen 12,185/3,047/128 train/validation/test split, and 232 original ROI constituents. This streamed version requires exactly 287 current columns. Training and validation labels remain authorized development inputs; no TEST labels enter the packet or the model entry. Full calcium caches, operator targets and historical TEST feedback must stay outside participant mounts. Common preprocessing is whole-record preprocessing, as carried by the packet metadata, not a claim of training-only raw-data processing.

`load_packet` is the unchanged trusted-input loader. It loads NPZ arrays before applying its 3 GiB aggregate numeric check. Its per-array hashes and schema validation are not a pre-allocation memory sandbox or a substitute for external whole-file authentication, input-size admission and process/resource supervision. External owners must also handle startup failures, native kills and output custody.

## Exact scheduling boundary

The route slices each already-emitted TensorFlow batch in its original order. Parameters and fixed initial states stay identical across that batch. It sums all raw singleton losses and gradient leaves in their source dtype, divides once by actual batch size, then enters the unchanged group norm-to-power-0.99 normalization, parameter-count multipliers, basal/somatic factor 6, clipping/momentum/schedule and single optimizer update. It adds no epsilon, support denominator, skipped masked site or zero-gradient repair.

The helper supports training batches 153/256 and validation batches 999/1024 only. Validation predictions are restored in original 147-site row order before the unchanged complete-validation masked Pearson and strict-greater best-state selection. The final 128-by-147 TEST prediction remains the original vectorized call after the selected state and full budget; it is not passed through the helper and its memory use is unqualified.

The full route entails 255,885 singleton gradient calls, 63,987 singleton validation predictions, 1,008 optimizer updates and 21 global validation/selection checks, plus that final vectorized 128-row prediction. No completion promise follows from the private admission operation's 750-second envelope. A smaller traced leading dimension does not bound native caches, allocator residency, peak RSS or wall time. Sequential host sums change floating-point association/backend relative to full-batch XLA reductions; numerical qualification must compare raw loss, every gradient leaf, normalized updates, optimizer state and selected outputs under a separately admitted runtime and criterion.

## Outputs and provenance

The route retains validation-selected parameters and layout, selected validation predictions, validation history, final `prediction.json`, RNG evidence, and `operation_result.json`. It never computes a TEST score. Its result identifies the streamed component and explicitly retains unqualified floating-point/resource status. The optional callable `checkpoint(stage)` is an observation/cancellation seam; the CLI default is a no-op, not a deadline.

`FIT_SOURCE_DELTA.patch` and `FIT_SOURCE_INVERSE.json` identify the six reversible replacements of the original full-fit function. The original model entry, three authored siblings and helper have unchanged hashes in `SOURCE_MAP.json`. The private two-update diagnostic was not used as a full-fit entry, and no module globals are monkeypatched.

The copied authored source carries the upstream MIT notice in `LICENSE` (mackelab/jaxley_experiments, commit 5e7a86282adb9d4603b5546ac5d8dad59aec7cc0). External mechanism and dependency licenses remain separate. The ordinary `jaxley_mech` package, including its initializers, is required externally and is not redistributed here. `COMPONENT.json` records that dependency boundary and the lack of a qualified full-model public profile. Existing registered input runtimes and input modules are unchanged.

## Public source controls

The ordinary unittest entry has exactly nine methods and no fixtures or output artifacts:

```sh
python -I -S -B test_portable_reference.py -v
```

It reads four hash-bound source/JSON files beside itself. These stdlib controls cover the real CLI and prepared-call boundary, fresh-output source guard, exact fit inverse and final TEST route, helper shape refusals, fixed-state/order/global-mean accumulation, failure handling and complete ordered 147-site validation assembly. Recording objects and exact `Fraction` arithmetic exercise contracts; they do not emulate target libraries or qualify the model.

The underlying private 17-case campaign passed before this public projection was authored. This new nine-method wrapper has not been executed locally and awaits ordinary hosted CI. Its outcome must be reported separately; the private campaign is not a public nine-test result. `COMPONENT.json` contains the exact standard-runner argv and complete five-file test dependency list. The full-model runtime remains unqualified.
