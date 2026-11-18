# Figure 5i original split-support audit

The existing cosine scorer binds a split-receipt digest but does not inspect
the receipt. This component joins that digest to complete real-label and
spike-shuffle training memberships for all 61 sessions and ten folds.
It checks support consistency; historical authenticity still requires external
operator review of the underlying source evidence.

The pinned [author Figure 5 notebook](https://raw.githubusercontent.com/GiocomoLab/Herber2024/1a9dd3040c9f77662caf26a34c9452403579087a/Figure%205.ipynb),
cell `84b679a9`, partitions the downsampled test sequence into ten consecutive
blocks and draws each training set from its complement. The spatial-cell
fitting cell invokes this operation separately for real and shuffled activity.
Those draws may coincide. Requiring different draws, copying a missing shuffle
realization, or generating a replacement seed would alter historical evidence.

## Operator API

```python
report = audit_support(reference, support, admitted_support_sha256)
```

The operator supplies the existing `figure5i-reference/v1` object and an
independently admitted canonical support commitment. A participant cannot choose
the admitted digest. The support object contains:

```text
schema: figure5i-original-split-support/v1
task_id: PAPER-FIND-039
source_revision: 1a9dd3040c9f77662caf26a34c9452403579087a
realization: historical_original
cohort_receipt_sha256, preprocessing_receipt_sha256
realization_evidence:
  original_downsampling: <evidence SHA256>
  original_test_partition: <evidence SHA256>
  original_real_training: <evidence SHA256>
  original_spike_shuffle_training: <evidence SHA256>
sessions: [
  {mouse_id, session_id, age_group, optimal_k, source_onemap,
   spatial_cell_ids, downsampled_observation_ids,
   folds: [{repeat, test_observation_ids, real_train_observation_ids,
            spike_shuffle_train_observation_ids}]}]
```

`support_digest` uses finite JSON, sorted keys, compact separators and ASCII
escaping. The existing reference's `split_receipt_sha256` must equal that
commitment. It is not the existing scorer's reference digest: including the
reference digest in support would create a circular dependency. Exact field
sets prevent unexamined target or override fields. Session/fold list order may
vary, but biological identities, cell/downsampled order, test order and original
real training order must match the reference. The original shuffle membership
must independently have the correct size, unique IDs and no test overlap.

The source-pinned scorer validates the 34-young/27-aged panel, original declared
eligibility and ten source test partitions before this additional join.
The dependency is loaded from its sibling `figure5i-score-v1/score.py` only
after verifying its bytes. Deploying elsewhere requires an explicit trusted
`scorer_path`; the same content pin still applies.

## Limits and integration

This supplies no original data, source receipt, RNG history, smoothing
adjudication, author replay, prediction, uncertainty threshold, paper win or
participant sandbox. Invented receipts with matching hashes remain invented.
An accepted structural audit cannot promote scientific admission. New-seed
reruns need their separately defined claim rather than this historical label.
Canonical task contracts and registration stay unchanged.

Generated tests exercise complete-panel coverage, unequal observation support,
real/shuffle distinction, coincident draws, leakage, source rebinding, stale
dependencies and fail-closed fields. They import the existing score fixture but
do not rerun its suite. Proposed CI command after component enrollment:

```text
python3 -B -m unittest discover -s benchmarks/paper/PAPER-FIND-039/implementations/figure5i-support-v1/tests -p 'test_*.py'
```

Current wave execution uses the existing shared two-slot generated-test pool.
No authentic run or current CI enrollment is claimed.
