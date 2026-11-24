# Figure 5i paired source-assistance comparison

The original scorer evaluates one candidate against an author replay and a
spike-shuffle control. This operator component joins that calculation to the
existing original split-support audit and requires all four candidate packets:
reproduction and improvement, each under `paper_data` and
`paper_data_author_code`. A missing packet or incomplete session/fold panel is
an error. It cannot be replaced by the other outcome or condition.

All packets use one original reference, one independently admitted historical
support receipt, the same author replay and the same shuffle companion. The
component preserves all 61 sessions (34 young, 27 aged), their mouse identities,
ten fold scores and separate age summaries. It reports both complete candidate
versus author results and descriptive author-code-minus-paper-data differences
for each outcome, at fold, session and age-stratum levels. It does not pool ages,
drop failed sessions, weight by observation count, treat folds as independent,
or reward shuffle performance.

The numerical endpoint remains the pinned scorer's mean cosine angular score,
averaged equally across the ten folds within each session. The underlying
[author notebook](https://raw.githubusercontent.com/GiocomoLab/Herber2024/1a9dd3040c9f77662caf26a34c9452403579087a/Figure%205.ipynb)
and the selected `primary-endpoint-v1` contracts remain unchanged.

## Operator API and command

```python
report = compare_conditions(reference, support, admitted_support_sha256,
                            candidates, author, shuffle)
```

`reference`, `author`, `shuffle` and each candidate packet use the existing
`figure5i-score-v1` schemas. `support` and `admitted_support_sha256` use the
existing `figure5i-support-v1` API. The admitted support commitment comes from
independent operator admission, outside the participant submission. Neither
computing a matching digest nor passing this component authenticates history.

The exact candidate mapping is:

```text
paper_data:
  reproduction: <figure5i-predictions/v1 packet>
  improvement: <figure5i-predictions/v1 packet>
paper_data_author_code:
  reproduction: <figure5i-predictions/v1 packet>
  improvement: <figure5i-predictions/v1 packet>
```

Each slot requires its separately frozen upstream submission. Identical
prediction values are allowed; different values do not prove independent
freezing. Condition labels are declared inputs, not evidence that permitted
exposure, candidate independence or resource matching was enforced. Packet
digests in the report bind assessed content for later custody checks; they are
not admission receipts or signatures.

For JSON use a bundle with exactly `schema: figure5i-paired-input/v1`,
`task_id: PAPER-FIND-039`, `reference`, `support`, `candidates`, `author` and
`shuffle`. Keep this operator bundle and the resulting report protected:
they include held-out targets or answers and are not participant observations.

```text
python3 -B compare.py BUNDLE.json REPORT.json --admitted-support-sha256 OPERATOR_DIGEST
```

The support commitment is deliberately a separate command argument. The
default deployment uses sibling `figure5i-score-v1` and
`figure5i-support-v1` components, with immutable byte hashes checked before
loading. `--components-root` (or the API's `components_root`) selects a trusted
deployment location without relaxing those pins. Reports are computed directly
from complete predictions; submitted aggregate scores are never joined.

## Validation and remaining scientific work

The standard-library controls use only generated fixtures from the existing
components. They exercise all four slots, opposite effects across outcomes and
ages, unequal fold weighting, reordering, original receipt admission and leakage,
shared companions, shuffle-control isolation, dependency binding and the CLI.

```text
python3 -B -m unittest discover -s benchmarks/paper/PAPER-FIND-039/implementations/figure5i-paired-v1/tests -p 'test_*.py'
```

For an isolated candidate source tree, `FIGURE5I_COMPONENTS_ROOT` points tests
to the existing trusted sibling implementations; normal repository CI requires
no override. This new suite must be enrolled by the publication owner.

This is a complete-panel arithmetic comparison, not scientific qualification.
Original input custody, cohort and stochastic support recovery, preprocessing
adjudication, qualified author replay, protected execution, independent freezes,
exact exposure manifests and finite matched budgets remain external obligations.
Reproduction tolerances, meaningful improvement and mouse-dependent uncertainty
remain unresolved. Both outcomes are explicitly `not_assessed`, scientific
admission remains false, and no reproduction, improvement or SOTA is claimed.
