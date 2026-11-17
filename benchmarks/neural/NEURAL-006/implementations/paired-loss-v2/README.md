# Independent paired ERP loss evaluator

`paired_loss.score_case` independently evaluates the current NEURAL-006 processed-amplitude prediction endpoint. It reconstructs the behavior-complete query and paired FRN/P3b target mask from all 180 private projected rows, checks every candidate query prediction, and recomputes equal-person training means and variances from training rows. Distinct bootstrap fit clusters retain equal mass even when an original person is sampled more than once. Raw MSE, MAE and training-variance-normalized MSE preserve separate components and original exported amplitude units; no physical unit is inferred.

The existing `broker-controls-v4/runtime/analysis.py` scorer accepts an already selected truth dictionary and a supplied reference variance. Its caller performs a reference audit, but the scoring function cannot detect a mistakenly dropped eligible truth row. This implementation takes the complete private projected trajectory instead. It rejects truncated trajectories, changed behavior-query support, duplicate or boolean row identities, inconsistent bootstrap copies, held rows/people in training, modified normalizers, incomplete arms or modes, and nonfinite values. Predictions remain mandatory on behavior-complete rows whose paired targets are unavailable.

Use it only in the trusted operator after predictions are committed:

```python
score = score_case(case, private_projected_rows, reference, candidates)
# Frozen33/test8 queries use their separately retained common training projection:
score = score_case(query_case, private_projected_rows, reference, candidates,
                   training_case=common_training_case)
```

The returned `participant`, `paired_scored_rows` and `components` shape is compatible with the predecessor's full-cohort aggregation. The module does not import that scorer, read files, run R, fit models or call candidates. It does not independently refit or establish competence of N/R/V/J. The generated controls compare valid-input results to the predecessor and independently calculate unequal-person and bootstrap-copy examples.

This is an operator scorer component, not a new benchmark definition or an automatically selected runtime. The pinned predecessor, its selectors and current scientific contract are unchanged. Integration must retain the complete private projected held rows until scoring, call this evaluator after the existing reference audit and immutable prediction commitment, and qualify a newly pinned runtime closure before use. Source hashes and full cohort/split validation remain the acquisition/projection owner's responsibility; structurally valid substituted values or a falsified missingness field cannot be authenticated by arithmetic. Nothing here resolves independent raw-event alignment, preprocessing or physical units.

Source basis: the current task-local `understanding.v1.json`, predecessor `runtime/projection.py`, `runtime/analysis.py` and `runtime/protocol.py`; author [processed export source](https://github.com/jpheffne/2025_epe_eeg/tree/4f5767df1516e0ec3c234d51ba36e4b741eb60e8/data/clean) at commit `4f5767df1516e0ec3c234d51ba36e4b741eb60e8`. No new source data were acquired or opened. No genuine-data preparation, scientific qualification, model trial, or direct/viewer neural-interpretation result is established.

Run `python -m unittest discover -s benchmarks/neural/NEURAL-006/implementations/paired-loss-v2 -p 'test_*.py'` only through the authorized shared generated-test pool. Controls use invented values and standard-library arithmetic.
