# Processed dopamine-response prediction — NEURAL-046

Both local interfaces are qualified: submit one complete prediction artifact, or submit one frozen Python program for execution across 13 isolated source-animal folds. The shared benchmark command has passed a full-score parity check. See [PROGRAM.md](PROGRAM.md) for the program interface and its resource limits.

The task predicts 2,795 fixed cue-evoked processed-fluorescence responses from event features. Scores include equal-source-animal MSE, MAE and signed bias, full coverage, per-animal/condition diagnostics, and descriptive comparisons with five frozen regularized baselines. There is no scientific pass threshold. Keep the complete score.

Nine developer panels exercised 117 isolated program invocations, including 26 known-source fits, with zero new model-service calls. Original and fixed altered-training predictions matched their verified references exactly. Malformed, abstaining, timeout and extra-output controls preserved all outcomes. A disclosed stale copier received a valid ordinary score while failing the separate known-procedure recomputation comparison. These controls establish local task execution, not independent model performance.

All 13 animals and their development outcomes are exposed. The training-fold union contains every assessment target; per-fold file isolation does not certify unseen-animal generalization or prevent prior memorization. The target is released processed fluorescence, not native/no-tools raw-signal comprehension. Upstream whole-session preprocessing and declared all-event feature vocabularies remain; only the stated model transforms are fitted on each training fold. SD/SE are descriptive, with overlapping training folds, not inferential confidence intervals or p-values.

Anatomical, missing-lick and lifetime-history provenance, canonical licking controls, condition holdout, redistribution rights and external expert review remain separate requirements. Penalized-baseline differences do not isolate conditional elapsed-time/count information because correlated added columns can redistribute shrinkage. The broader research contract and submission readiness remain unqualified.

Use `python3 tools/neurobench.py run NEURAL-046 --program FILE.py --output NEW_DIRECTORY --review REVIEW.json --other-reserve-bytes 102000000`, or the existing `score` command with `--submission FILE`. Each attempt requires an explicit bounded operator allocation. Neither command starts an LLM.
