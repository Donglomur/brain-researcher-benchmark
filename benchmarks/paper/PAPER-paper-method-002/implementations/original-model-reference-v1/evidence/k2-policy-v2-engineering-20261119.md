# Jaxley policy-v2 K2 engineering evidence

This accepted isolated workflow establishes numerical equivalence on **two TRAIN rows**, covering **294 predictions**, one loss and **15 raw-gradient leaves**, plus **two scratch optimizer proposals**. Each scratch proposal computes one source update from the same initial state; **zero updates were applied**. Full256 updates, full fits, test scores, paper-result reproductions and improvements are all **zero**. Existing component readiness remains **unknown**, and complete benchmark readiness remains **false**.

The paired JSON is the scalar evidence record. The public component is `paper-paper-method-002-original-model-reference-v1`, rooted here at source commit `e39a5217c031ac9c130c21c31891153bd39ded09`. The original scientific source, initializer, inverse and forward transforms, and numerical tolerance formulas are preserved. No original-computation replay occurred in this attempt.

## Accepted numerical results

All declared comparison criteria passed; there were zero failed criteria.

| Quantity | Result | Maximum absolute error | Maximum tolerance ratio |
| --- | --- | --- | --- |
| Predictions | 2 × 147 values | 8.268941087408166e-13 | 0.00923116666420737 |
| Loss | 46.89042015975354; byte equal | 0 | 0 |
| Raw gradients | 15 leaves | 3.810285420513537e-13 | 0.008079382805305681 |
| Scratch proposed update | Two proposals | 1.9080743929311694e-13 | 0.011044621527688737 |

## Explicit parameter-policy exception

Policy-v2 permits exactly the original scalar float64 negative-infinity latent coordinate `opt[2][0][Na_gNa]`. Its canonical raw negative-infinity bytes (`000000000000f0ff`) are unchanged in the initial state and both resulting branches. All other raw parameter coordinates remain finite and use the floating-leaf rule. This is a versioned criterion change: **the old all-finite raw-parameter contract is not claimed**.

The unchanged physical transform is finite: `0.05+(0.5-0.05)/(1+exp(20.0))`, evaluated in the frozen forward operation order with `save_exp` exponent clipping. The image is not literal `0.05`. Neither the initializer nor the inverse/forward transforms were changed to obtain this result.

## Unchanged comparison formulas

For each component of predictions and loss, `abs(a_i-b_i) <= 1e-12 + 1e-10*max(abs(a_i),abs(b_i))`.

For each entire raw-gradient leaf, define `S=max(abs(values in both operands))`; every component requires `abs(a_i-b_i) <= 1e-12*S + 1e-8*max(abs(a_i),abs(b_i))`. A zero-scale leaf requires exact zero difference.

For each entire floating leaf of normalized gradients, proposed updates, optimizer state and finite parameters, define the same leaf-wide `S`; every component requires `abs(a_i-b_i) <= 3e-12*S + 3e-8*max(abs(a_i),abs(b_i))`. The absolute term is source-scale weighted, not an unscaled `3e-12` tolerance. Nonfloating counters require exact equality.

Group checks require `difference_L2 <= relative_limit*min(norm_reference,norm_streamed)`: the limit is `1e-8` for five raw normalization groups, whose source norms must be strictly positive, and `3e-8` for five normalized groups and three optimizer-output groups.

## Isolation, resources and limits

The producer had no original-result reference mounts. A separate trusted comparator received those references only after complete producer closure and output sealing. Numerical computation stayed on two TRAIN rows, but the **complete frozen input archive was physically mounted**, including `val_targets` and TEST input/mask rows. There was no TEST-target member, validation/test numerical evaluation or test score. This is source-restricted TRAIN computation; it does not establish physical TRAIN-only input isolation.

The run used 4 CPUs and 8 GiB declared RAM, with a 7 GiB guest hard memory-and-swap limit. Native wall time was 538.916 seconds. Reported producer process-lifetime high-water was 5.3775787353515625 GiB; this is not instantaneous usage, a total container/process-tree peak or a minimum-RAM estimate.

The isolated K2 workflow completed where an earlier shared-process attempt ran out of memory. This establishes feasibility for this isolated workflow under these resources; it does not identify the earlier failure's cause or demonstrate a controlled memory reduction. Earlier failed attempts remain failed. A separately selected full256 one-update execution remains required. This record selects no execution and establishes no paper reproduction, improvement, SOTA or complete benchmark readiness.
