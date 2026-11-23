# Figure 5A choice prediction-record audit

This operator-side component closes a specific construction gap between a supplied
choice-panel roster and the existing numerical AUC diagnostics. It joins every
submitted continuous probability to a typed original-trial identifier, validates
the complete submitted roster, and only then requests protected labels. It emits
the complete case-level AUC profile, including undefined single-class cases.

It does **not** authenticate the original paper cohort or reproduce the published
panel. The current task still lacks original input/release authentication,
method-by-session/region incidence, original class orientation and score protocol,
complete author reference vectors, native producer qualification, and an admitted
full-profile improvement rule. A checksum supplied by the caller is a commitment,
not proof of source authenticity or earlier freezing.

## Source relationship

The selected task is original Figure 5A choice decoding: ten sessions, the five
regions PO/LP/DG/CA1/VISa, and every actually applicable author condition. This
component requires those declared axes but accepts only an explicit case list;
it never expands a ten-by-five-by-method Cartesian product. Original session IDs,
animal IDs, condition membership and trial masks must come from a separately
qualified operator source. It does not supply those missing biological records.

The existing `figure5-metric-diagnostics-v1/metrics.py` is hash-bound and reused.
Its probability AUC tie handling and explicit undefined single-class output
remain diagnostics. They are not asserted to be the paper's historical undefined
policy. The retained author `eval_utils.py` converts classification predictions
to hard labels and evaluates accuracy; that released route cannot by itself
calibrate the original continuous-score AUC panel. No author model is modified
or run here. Figures 5B–D and the inactive prospective full programme are outside
this component.

## Interface

Call `audit_choice_profile(support_bytes, prediction_bytes, load_protected_labels,
expected_support_sha256=...)`. All documents are captured JSON bytes, each at most
64 MiB. There is no file-loading CLI, fitting, model dispatch, or label discovery.
The callback is operator-owned and returns one captured protected-label document.

The support document uses schema `figure5a-choice-support/v1`, the exact task ID,
an explicit `positive_class` identity, a `source_protocol_sha256`, ten
`sessions` (`session`, `animal`) and an explicit list of `cases`. Each case has
`case_id`, `session`, `region`, `condition`, and ordered `trial_ids`. Every declared
session and region must occur. Cases are unique by ID and by session/region/
condition. Trial IDs are nonempty literal strings or nonnegative integers within
the exact JSON integer range; string `"0"` and integer `0` are distinct.

The prediction document uses schema `figure5a-choice-predictions/v1`, the matching
support digest and class identity, and one `cases` record per expected case.
Each record contains `case_id` and `predictions`, each with `trial_id` and a finite
`positive_probability` in `[0,1]`. Cases and trials may arrive in any order; joins
use typed identities, and the audit restores operator order. Missing, extra,
duplicate, nonfinite, boolean, out-of-range or target-bearing records are rejected.
Hard-label output cannot be distinguished from legitimately exact 0/1 probability
output by values alone; producer qualification remains necessary.

The protected document uses schema `figure5a-choice-labels/v1`, matching support
digest and class identity, and `sessions` records with `session` and `labels`.
Each label record has `trial_id` and an integer `label` of 0 or 1. Its support must
equal the union of declared query trials for that session. A trial shared across
conditions has one label record, preventing contradictory per-condition targets.
No label or probability values are copied into the returned profile.

All prediction fields and the pinned metric implementation are checked before
the label callback is called once. This is program call ordering, **not** an OS
isolation boundary, a protected submission service, a timing attestation, or a
participant runner. Reports contain private source identities and commitments;
the operator must control their release. The component materializes JSON objects
in memory, and the document byte limit is not a hard RAM limit.

The report retains all cases, animal/session identities, trial denominators and
undefined reasons. `panel_aggregate` and `paper_win` remain null;
`scientific_outcome` remains `unknown`. There is no averaging, best-method
selection, win count, confidence interval or significance threshold. Auditing
author and candidate outputs separately does not establish a paired scientific
comparison without the unresolved source/competence/inference gates.

## Building a submission from continuous model outputs

`build_choice_predictions(support_bytes, logit_bytes,
expected_support_sha256=...)` returns captured `figure5a-choice-predictions/v1`
JSON bytes accepted directly by `audit_choice_profile`. It needs no labels and
does not call the protected-label loader. The supplied support is checked using
the same contract as the audit, including explicit original case incidence.

The source [author evaluator](https://github.com/yzhang511/neural_decoding/blob/1508b1ac5a95af2f8627f0c304ee0a750cb36e77/src/utils/eval_utils.py#L47-L79)
applies softmax and then argmax for classification in reduced-rank, MLP and LSTM
paths. Its returned hard labels cannot recover the continuous score ordering
needed by AUC. Capture the two output logits **before** that conversion and carry
each original trial ID alongside its output. Do not infer IDs from returned row
positions: the current source-loader coverage remains unqualified. This helper
accepts those captured outputs; it does not run or patch the author evaluator,
change model training, or provide a linear/state-space decoder adapter.

The input document is:

```json
{
  "schema": "figure5a-choice-logits/v1",
  "support_sha256": "<the exact supplied support SHA256>",
  "cases": [
    {
      "case_id": "<a declared case>",
      "class_order": ["<negative class identity>", "<support positive_class>"],
      "batches": [
        {"trial_ids": [0, "0"], "logits": [[0.0, -2.0], [0.0, -1.0]]},
        {"trial_ids": [2], "logits": [[0.0, 0.5]]}
      ]
    }
  ]
}
```

The abbreviated example shows one case; a real document must supply every case
and trial in the support. Every row must contain exactly two finite numeric
logits. Each case explicitly names its two distinct output classes, including
the support's positive class. Reversed class-column order is supported; an
unstated, unknown or unqualified historical mapping must not be guessed. The
helper checks the declared mapping's structure, not its biological authenticity.

Cases, batches and rows may arrive in any order. The returned document restores
support case/trial order using typed identities. Duplicate, missing, foreign or
misaligned rows fail, including a dropped final partial batch. A stable softmax
converts logits into positive probabilities without exponent overflow; binary64
rounding can still tie very extreme scores at 0 or 1. Hard-label vectors are
rejected by shape, but a caller could misrepresent a two-column hard-label array
as logits; producer qualification remains necessary. There is no imputation,
threshold selection, aggregation or paper-win decision. The helper shares the
audit's 64 MiB input/output document bound and materializes records in memory.

## Validation

`test_choice_records.py` uses generated heterogeneous ten-session support with
13 declared cases and 49 trial predictions. It exercises the actual pinned AUC
code and rejection paths, including a failure in the last case before labels
are read, shuffled typed identifiers, repeated labels, changed commitments,
orientation conflicts, dropped panel axes, duplicate JSON keys, and altered metric
pins. This is an engineering control, not an authentic 13-case source census.
The same module tests the logit builder through the actual AUC audit: continuous
scores retain a generated AUC of 0.75 where argmax would produce 0.5, shuffled
typed IDs and reversed class columns give the same submission, partial batches
remain complete, and malformed/incomplete outputs fail. These numbers describe
generated controls only, not decoder performance on original observations.

Run the focused test module through the existing shared generated-test pool.
The intended public test command is `python3 -B test_choice_records.py` from this
directory. New component enrollment is an integrator action; source presence
does not establish that hosted CI has run. No authentic recordings, fit, AI run,
published score, reproduction, improvement, or readiness promotion is claimed.
