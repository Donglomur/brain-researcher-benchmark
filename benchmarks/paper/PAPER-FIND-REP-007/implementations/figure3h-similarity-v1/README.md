# Figure 3h coding-direction similarity component

This component closes a missing reduction after `coding-direction-v1`: it derives
leaf2 similarity indices from the complete supplied projection reports and
summarizes the four source conditions. It implements the separately named
`pinned_fig3h_absolute_distance_leaf2_similarity` variant. It does not adjudicate
the paper/code or figure-specific similarity definitions, authenticate the
original cohort, grade a reproduction or establish an improvement.

The immutable source is Zhong et al., *Unsupervised pretraining in biological
neural networks*, author revision `ba64ac697f5d9914926baac79399e80707a5f3a6`:

- [`utils.py:load_coding_direction`, lines 349–364](https://github.com/MouseLand/zhong-et-al-2025/blob/ba64ac697f5d9914926baac79399e80707a5f3a6/utils.py#L349)
  subtracts second-population projection from first-population projection, averages
  the 40 texture positions in each trial, then averages trials per source record.
- [`fig3.py:SI_train2_after_learning`, lines 237–255](https://github.com/MouseLand/zhong-et-al-2025/blob/ba64ac697f5d9914926baac79399e80707a5f3a6/fig3.py#L237)
  computes `(abs(leaf2 - circle1) - abs(leaf2 - leaf1)) / abs(leaf1 - circle1)`.
  Positive values indicate similarity to leaf1. This absolute-distance definition
  is preserved; no generic correlation or other figure's formula replaces it.
- [`utils.py:Get_coding_direction`, lines 513–517](https://github.com/MouseLand/zhong-et-al-2025/blob/ba64ac697f5d9914926baac79399e80707a5f3a6/utils.py#L513)
  retains repeated sessions under suffixed record names. Figure 3h averages those
  supplied records, with sample SEM (`ddof=1`), rather than reweighting animals.

`record_similarity(projection_report)` consumes the existing projection schema,
requiring the pinned leaf1/circle1 reference `[2,0]`, percentile 5, all four areas,
both projection populations and all seven stimulus slots. Trial identity and
length must agree between the two populations. It preserves every supplied trial
and returns their 40-position mean contrasts before the record-level ratio.
Positions `10:50` include texture positions `0:40`; the previous ten positions and
the later gray positions are excluded. Missing or nonfinite texture values and
empty trial sets propagate to undefined output. Zero reference separation is
explicitly undefined. No undefined trial or record is dropped; no `nanmean` or
favorable finite-only mean is used. Absent unrelated stimuli remain labeled.

The standard-library reduction is mathematically equivalent to the pinned NumPy
mean/sample-SEM recipe for finite input. It is not a verified authentic numerical
parity claim. Nonfinite states use JSON `null`, preserving the record and trial
counts; this reporting policy is distinct from the author's runtime behavior.

## Complete declared panel

Use the CLI to bind safe JSON projection reports by SHA-256:

```sh
python3 -I -B benchmarks/paper/PAPER-FIND-REP-007/implementations/figure3h-similarity-v1/similarity.py panel.json --output report.json
```

The panel is a JSON object with `schema_version: 1`,
`task_id: "PAPER-FIND-REP-007"`, nonempty `population_evidence`,
`expected_record_ids`, and `records`. `expected_record_ids` maps each of these
four source experiments to its complete ordered list of unique record IDs:

- `naive_test1`
- `test1_after_grating`
- `unsup_train2_after_learning`
- `sup_train2_after_learning`

Each `records` entry contains `record_id`, `animal_id`, `experiment`,
`projection_path` (relative to the panel, or absolute) and `sha256`. Animal IDs
may repeat for repeated recordings and need not occur in other conditions. The
source record IDs must be globally unique, and every declared record must occur
exactly once with its declared experiment. Reusing identical projection bytes as
distinct records is rejected. The result retains the ordered records, their
animal IDs, input hashes and panel hash, and reports each condition's equal-record
mean/sample SEM. A single-record condition has undefined sample SEM.

The declared inventory is an owner-supplied completeness boundary. It cannot
establish that the inventory or animal/session joins are the authentic source
population. No source dictionaries are unpickled, data acquired, animal selected,
records excluded or cross-condition universal cohort imposed by this component.
Original data preparation, all-cell provenance, authentic source parity, exact
population joins, scientific tolerances, inferential controls, participant access
comparison and same-result improvement criteria remain unresolved. Reports retain
`original_cohort_verified: false`, `scientific_qualification: "unknown"`,
`full_contract_complete: false` and `scientific_improvement_assessed: false`.
The canonical task, reproduction/improvement contracts and historical evidence
are unchanged. A larger biological contrast is not an improvement criterion.

## Generated controls

```sh
python3 -I -B benchmarks/paper/PAPER-FIND-REP-007/implementations/figure3h-similarity-v1/tests/test_similarity.py
```

Fourteen generated controls cover the absolute-distance oracle, negative and
positive ends, outlying leaf2 responses, two-population subtraction, exact texture
window, ratio after trial averaging, absent/undefined stimuli, zero separation,
overflow, identity/shape failures, four-condition inventory, repeated-record
weighting and SEM, missing-record propagation, content tampering and CLI binding.
These are engineering controls only. No author code or authentic data is executed.
