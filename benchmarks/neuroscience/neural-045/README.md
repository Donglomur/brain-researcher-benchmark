# NEURAL-045: native fluorescence transfer

A bounded reference predicts released fluorescence trajectories across the 60-second and 600-second reward-spacing source cohorts. It covers 2,691 native-time trajectories from all 13 selected source IDs; 106 clock-truncated windows remain explicit exclusions. The native observed spans are scored without resampling, padding or query-target normalization.

Four fixed diagnostic predictors completed the same protocol. Adding elapsed and reward-count history to the reward-aligned time template produced a mean source-ID-relative prediction skill of **0.0296349352**, improving 11 source IDs and worsening two. This metric is the mean of within-ID relative MSE reductions, not ordinary R². All 24 numerical controls passed; independent root aggregation matched all 256 saved aggregate values exactly. See the [results and limitations](../../../authoring/reward-fluorescence-transfer-v1/native-reference-v1/RESULTS.md).

This is an exposed retrospective reference, not an independent AI study or SOTA result. Spacing and source identity change together; biological pairing across naming families and anatomical exclusions remain unresolved. Source data and previous outcomes overlap NEURAL-046 and PAPER-FIND-044.

The reference component is registered. Arbitrary-program execution, standalone grading, full-contract completion and research/submission admission remain unavailable. The source specification remains at [NEURAL-045](../../manifests/neural/NEURAL-045.json). No candidate run can be dispatched through this reference-only manifest.
