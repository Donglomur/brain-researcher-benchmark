# Reporting paper and code access comparisons

`tools/report_neuroscience_paired_study.py` produces a descriptive report from a prospectively assigned paper roster and trusted operator outcome records. It does not run a model, load neuroscience measurements, authenticate evidence, or adjudicate whether a reproduction is scientifically correct. It implements the reporting choices in this project's research experiment design: keep every assignment, report reproduction separately from improvement, and do not average incompatible scientific metrics.

```sh
python3 -I -S -B tools/report_neuroscience_paired_study.py \
  --plan study-plan.json --records operator-records.json > report.json
python3 -I -S -B tools/tests/test_paired_study_report.py
```

Freeze the plan before seeing outcomes. The CLI cannot establish when a plan was created; a post hoc roster remains a post hoc analysis. Both JSON documents are limited to 8 MiB. Output is written to stdout; the caller manages its destination. This source package contains only invented engineering tests, not new agent-study results.

## Plan

The two ordered arms are `paper_and_data` and `paper_data_official_code`. Assign each paper one family, one metric and direction, an explicit replicate roster, and the common assessment and budget identities. The contract identity must bind the selected endpoint, support, exposure rules and metric definition; the baseline identity must bind the same equally informed comparator. Those identities are assertions supplied by the operator, not automatically verified references.

```json
{
  "schema_version": 1,
  "study_id": "INVENTED-example",
  "arms": ["paper_and_data", "paper_data_official_code"],
  "tasks": [{
    "task_id": "INVENTED-paper",
    "family_id": "INVENTED-source-family",
    "contract_id": "reviewed-task-contract-v1",
    "common_inputs_id": "common-packet-v1",
    "baseline_id": "matched-reference-v1",
    "budget_profile_id": "matched-budget-v1",
    "metric": "mse",
    "direction": "minimize",
    "replicates": ["replicate-1"]
  }]
}
```

All identifiers are printable ASCII strings of 1–200 characters. Use `maximize` for metrics whose increase is better. This tool cannot check whether a proposed direction or metric measures the intended science. Use a separately frozen plan for a different model, budget, assessment or task revision. It accepts at most 1,000 papers, 1,000 replicates per paper and 10,000 pairs overall. These software bounds do not define a scientific sample size.

## Operator outcomes

The records document has `schema_version: 1`, the same `study_id`, and an `attempts` list. Every record has `task_id`, `replicate`, `arm`, all four common identity fields from the plan, an `operator_evidence_id`, `reproduction`, and `improvement`. For example:

```json
{
  "schema_version": 1,
  "study_id": "INVENTED-example",
  "attempts": [{
    "task_id": "INVENTED-paper",
    "replicate": "replicate-1",
    "arm": "paper_and_data",
    "contract_id": "reviewed-task-contract-v1",
    "common_inputs_id": "common-packet-v1",
    "baseline_id": "matched-reference-v1",
    "budget_profile_id": "matched-budget-v1",
    "operator_evidence_id": "INVENTED-reviewed-attempt",
    "reproduction": "failure",
    "improvement": {"status": "scored", "candidate": 4.0, "baseline": 5.0}
  }]
}
```

Reproduction statuses are `success`, `failure`, `abstained`, `infrastructure_error`, and `pending`. A scientific discrepancy may be a valid completed task if that is how its task-specific rubric defines success; do not label a defensible null conclusion a failure merely because it differs from a published result. Unrecorded assigned attempts appear as pending with `record_present: false`.

Improvement statuses are `scored`, `unavailable`, `abstained`, `infrastructure_error`, and `pending`. Only `scored` contains numeric `candidate` and `baseline` fields. A loss or tie is valid. Scoring can follow reproduction failure when the task protocol permits a common baseline or continuation; this reporter does not condition improvement on successful reproduction. Task-specific phase barriers must be enforced by the runner.

Duplicate `(task_id, replicate, arm)` records are rejected. Retrying cannot overwrite an unfavorable assigned outcome in this report. Any retry policy and selection of a terminal operator record must be prospective, with the complete trace retained separately. Unassigned records, inconsistent context identities, unequal paired baseline values, duplicate JSON keys, Boolean scores and nonfinite arithmetic are rejected. Integers must be exactly representable as finite Python floats; inexact integer conversion cannot silently hide a baseline difference or a gain. Decimal numbers use ordinary floating-point precision. Unknown fields are rejected so misspellings cannot silently alter a comparison.

## Interpretation

Reproduction success is one for `success` and zero for scientific `failure` or `abstained`. Infrastructure errors and pending attempts remain unknown in [0, 1]. For each assigned pair, the logical lower bound on code-minus-no-code success is `B_lower - A_upper`; the upper bound is `B_upper - A_lower`. These are missing-outcome bounds, **not confidence intervals**. The report gives no point estimate when those bounds differ. It separately retains the cause of each missing outcome.

Average first across the assigned replicates within a paper, then equally across papers. Also report the average within each declared source family and the equal-family average. Replicates and multiple tasks sharing a family do not silently receive extra weight in the corresponding summary. These family labels are declared overlap groups, not evidence of independent participants, laboratories or papers. Neither summary supplies inferential uncertainty.

For scored improvement pairs, orient both gains so positive means better than the same common baseline. Report code-minus-no-code gain within each paper and list every evaluated pair. The within-paper mean is explicitly conditional on both arms being scored; missing improvement outcomes have no assumed numeric range and are not imputed. Raw MSE, accuracy, correlation, bits/spike and other scientific units are never averaged across papers. There is no generic improvement threshold, overall SOTA indicator, p-value or scientific acceptance flag.

Matched identifiers do not prove equal actual compute, arm isolation, valid information use, independent grading or lack of pretraining exposure. Those are separate obligations of the task runner and study audit. The reporting output does not make an incomplete task ready for release.

## Engineering validation

Seventeen tests use explicitly invented records. They exercise all-assignment accounting, missing-outcome bounds, infrastructure classification, null/negative improvement, metric orientation, equal-paper and equal-family aggregation, no averaging of unlike metrics, duplicate/retry rejection, context/baseline mismatches, unknown assignments, finite arithmetic, exact integer conversion, JSON ambiguity and record-order invariance. No real study, candidate replay, neural input or protected outcome is used.
