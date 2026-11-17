# Fixed integration

Run inside the existing private evaluator after its source/runtime/resource
admission and producer teardown. Reuse its already authenticated public IDs,
private-loader closure and exact six-arm reference score structure. Bind this
component's source freeze alongside the unchanged canonical sources.

```python
scored = evaluate_submission(
    frozen_submission_path,
    expected_ids_by_case,
    private_loader,
    reference_scores,
    canonical_source_directory,
    submission_pin=committed_submission_pin,
    condition="observed_signal",
)
```

`scored` has the same canonical result keys and values plus one additive field:

```text
supplemental_metrics.per_person[0/1].roc_auc
supplemental_metrics.per_person[0/1].balanced_accuracy_at_0_2
supplemental_metrics.per_person[0/1].confusion_at_0_2
supplemental_metrics.participant_macro_roc_auc
supplemental_metrics.participant_macro_balanced_accuracy_at_0_2
```

The NPZ remains exactly `trial_ids` plus `target_probability`, with the same full
400-ID union. Private vectors must remain the same two 200-row, 40-target vectors
joined by the existing loader. This component refuses any other cohort or support.
Original canonical reference AUC values do not exist in the saved six-arm grade;
this evaluator does not fabricate them or backfill historical reports.

The component does not add a second private grader, change the original command,
or silently install itself. Root must select its reviewed callable in the actual
grader operation and freeze that complete worker/runtime before execution. This
is an implementation of the missing supplemental arithmetic and composition;
real NumPy/NPZ integration, authentic input revalidation and isolated end-to-end
operation remain unexecuted in this source-only phase. Any failure prevents a
complete augmented score; a valid canonical score from some separate earlier run
is not retroactively relabelled as this augmented operation.

Known canonical identities are embedded in `evaluator.py`: validator.py, 9,277
bytes, SHA256 5483d1b04e6f81d048351ca202c13a7c4183988469b88ca0274874b4714346a2;
metrics.py, 8,557 bytes, SHA256 e053d4dbf7237b0e630a8b9f097ce4fb5bb3cd3f547e892b4aa425a736f6a99f.
The unchanged metrics source is scalar arithmetic with NumPy-based input checks.
The existing isolated runtime enforces its dependency/image identity; this module
does not install dependencies, create containers, dispatch jobs or contact APIs.
