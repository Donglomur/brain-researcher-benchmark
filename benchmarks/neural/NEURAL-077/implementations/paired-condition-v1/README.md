# Complete paired condition comparison

`compare.py` adds the contract's missing same-query condition comparison to
NEURAL-077. It accepts two frozen 400-row probability NPZs, joins each by the
unchanged public trial identities, and reports A minus B within each person and
then with equal person weight. The target remains target/standard event identity
in the existing two exposed development people. It does not infer whether an
ideal P3 shape is present.

Both complete submissions, their byte/hash commitments, the fixed public roster
and the exact canonical source bodies are checked before any private-loader
call. The unchanged canonical validator consumes temporary snapshots of the
captured bytes, so a later replacement of an original submission pathname cannot
change the scored probabilities. Canonical scoring preserves the submitted
values, uses `p >= 0.5`, and clips only the temporary natural-log-loss argument at
`1e-15`. Both arms retain all six fixed reference comparisons. The original
private loader is called exactly once for each of the two people; four canonical
scorer requests use those same two cached vectors, retaining original dtypes.

The paired report adds target and non-target correctness tables with four counts:
both correct, A only correct, B only correct, neither correct. The signed recall
changes are averaged equally over classes to recover balanced-accuracy change.
Log-loss change is computed on the same paired trials. The evaluator checks both
macro differences against subtraction of the unchanged canonical scores. It
requires 200 trials, 40 targets and 160 standards for each person and returns no
partial report after a failure. It emits aggregate counts and scores, without
trial labels, probability arrays, source identities or filesystem paths.

Use the callable inside the separately admitted private grader, after both
producer processes have stopped and their complete delivery receipts have been
authenticated:

```python
report = compare_submissions(
    frozen_a_npz, frozen_b_npz, public_ids_by_person,
    authenticated_private_loader, frozen_six_arm_reference_scores,
    canonical_runtime_directory,
    a_pin=a_submission_pin, b_pin=b_submission_pin,
    a_condition="legacy_waveform_no_tools",
    b_condition="matched_waveform_programme",
    a_receipt_pin=a_producer_receipt_pin,
    b_receipt_pin=b_producer_receipt_pin,
)
```

Each pin is an exact `{"bytes": positive_integer, "sha256": lowercase_hex}`
object. The function binds producer receipt commitments into the report; it
does not read those receipts or prove the declared access from predictions.
The outer operator must check the producer's condition, full trial coverage,
first-final response policy, isolation and absence before private scoring.
The public ID commitment uses compact UTF-8 JSON of the sorted complete ID list
with a trailing newline, matching complete-direct-condition-v1.

Condition names preserve existing delivery names. The allowed records are:

| Condition | Access | Representation | Training labels |
| --- | --- | --- | ---: |
| `legacy_waveform_no_tools` | Direct observation | Numerical Cz/Pz waveform | 4 |
| `zero_shot` | Typed viewer | Visual waveform | 0 |
| `four_demo` | Typed viewer | Visual waveform | 4 |
| `tool_assisted_waveform` | Tool-assisted | Numerical waveform | 4 |
| `matched_waveform_programme` | Frozen program | Numerical waveform | 4 |
| `ordinary_feature_programme` | Frozen program | Feature bank | 1,200 |

The tool-assisted name supports future reporting; this component does not deliver
the missing adaptive controller. Label budget and representation stay explicit
for each arm. Equal budgets or source waveforms do not establish equal delivered
information, so the report never asserts that conclusion. Comparing zero-shot
and four-demo arms is a descriptive condition contrast, not a pooled arm. The
1,200-label feature program remains a separate richer-input comparison.

There is no population confidence interval, pooled-trial hypothesis test,
scientific pass threshold, new cohort or protected-holdout claim. Differences
between two exposed people remain descriptive. No human/model calls, fitting,
data downloads, authentic target access or new scientific score were performed.
This is an additive source component, not a change to task/contract, registered
runtime, earlier results or scientific qualification.

`test_compare.py` uses small generated NPZs and actual installed NumPy with the
unchanged pinned validator/metrics. It exercises hand-calculated class imbalance,
row permutations, arm reversal, exact primary-score preservation, probability
endpoints, malformed second submissions, private-label dtype/support failures,
source/prediction tampering, unequal label budgets and pathname replacement after
capture. Run only through the current shared lightweight test pool with one
thread, at most 1 GiB declared RAM and a 180-second deadline. Source-only tests
do not qualify an authentic paired study or its isolated grading runtime.
