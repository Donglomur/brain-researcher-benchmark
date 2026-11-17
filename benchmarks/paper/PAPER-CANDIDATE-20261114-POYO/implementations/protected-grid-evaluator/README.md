# Protected POYO adaptation grid

This successor repairs cross-budget leakage in the existing prospective output
consumer. The predecessor checks trial separation only within a single
`(budget_id, session_id)` case. Consequently a trial can supply final-test targets
in one budget and adaptation or development labels in another budget while the
whole artifact is accepted. That violates the current improvement contract's
requirement to keep transfer evaluation segments outside training and selection.

The successor executes three additional checks:

1. Within each session, collect every final-test trial in the submitted grid and
   refuse its use for adaptation or development in **any** budget. A violation is
   refused before the private target callback runs.
2. Within each session, require repeated absolute evaluation timestamps to retain
   the same trial identity. This detects contradictory support declarations,
   including renaming a repeated physical sample across budgets. Integer clocks
   remain exact above 2^53; clocks and trial IDs in different sessions are distinct.
3. After the one target read and complete target admission, pool target occurrences
   by timestamp using the existing arithmetic, and require overlapping physical
   session samples to have identical normalized targets across budgets. This
   prevents the same recording's target from changing with adaptation budget.

These checks do not require nested adaptation sets, equal budget rosters, or
identical test-support arrays across budgets. They do not impose a new adaptation
count or infer unpublished trial membership. Distinct occurrence values are still
permitted when their pooled target is identical. Exact target equality is suitable
for repeated extraction from one frozen normalized recording; independently rounded
or differently normalized targets require reconciliation before submission.

The prospective R² calculation, normalization declaration, complete-grid checks,
four-method contrasts, equal-session summaries, file boundary, and target-last
admission remain unchanged. `test_valid_grid_preserves_all_numerical_results`
compares every numerical and qualification field with the predecessor. This is a
prospective support policy, not recovery of the 2023 evaluation protocol. Sources
with overlapping closed trial boundaries must reconcile sample/trial ownership
before using this policy; no historical equivalence is inferred.

## Interface

`evaluator.py` is standalone Python 3.11 standard-library source. The callable is
`evaluate(design_body, design_pin, prediction_body, target_loader)`. Its design
schema is `poyo_protected_grid_v2`; all other design fields use the predecessor's
ABI. The prediction schema remains `poyo_predictions_v1`, the target schema remains
`poyo_targets_v1`, and the numerical policy remains
`poyo-stitch-uniform-r2-tm1.9-prospective-v1`.

Reports use `poyo_protected_grid_scores_v2` and include
`support_policy: poyo-session-global-held-support-v2`. A legacy design is rejected
until its owner explicitly opts into the successor; do not automatically relabel
historical artifacts. The CLI flags are unchanged:

```sh
python3 -I -S -B evaluator.py \
  --design OWNER_GRID.json --design-bytes N --design-sha256 SHA256 \
  --predictions SUBMITTED.json \
  --targets OWNER_TARGETS.json --targets-bytes N --targets-sha256 SHA256 \
  --output NEW_PRIVATE_REPORT.json
```

The trusted owner supplies paths and identities. The callable trusts its target
loader; the CLI authenticates target bytes before parsing. Reports remain private.
The existing 64 MiB per-file cap is not a CPU or memory guarantee, and rational
arithmetic remains unqualified for a full authentic grid.

## Source, controls, and remaining gaps

This code is derived from the preserved `../frozen-grid-evaluator/evaluator.py`,
SHA-256 `bb4f284fb5514425f9942b785647f2c06d20a43ca516f0dffaf9df4c94f429e1`.
Its primary-source context and numerical-policy limits remain in that component's
`PROVENANCE.json` and `README.md`. The current `../../improvement.v1.json` supplies
the requirement to keep all final transfer segments outside training/selection.
No new source downloads or authentic data inspection were needed for this repair.

The generated tests construct counterexamples that the predecessor actually accepts,
then exercise the successor's public target-read barrier and private consistency
check. They also compare full valid-grid outputs, pooled-target equivalence, session
scoping, and large exact timestamps. The test module reuses the preserved generated
fixture; production source has no sibling dependency. Run generated controls only
through the project test pool. Test execution receipts are external to this package.

This remains an unqualified construction component. Declared IDs cannot establish
their biological identity, and renamed adaptation trials without authentic clock
joins can still conceal exposure. These checks also cannot prove isolation across
separate evaluations, candidate histories, or producer processes. The missing 158
pretraining-session/source joins, separate historical transfer rosters, adaptation
budgets, original R², source masks, normalization, panel aggregation, trained author
baseline, and competent matched references remain unresolved. This source repair
does not change the legacy corpus ABI or establish that its union matches the
original pretraining and held-session roles.

All four method tables remain submitter supplied. Contrasts are therefore
submitted-method contrasts: they do not certify the named methods, reference
competence, paired access, or equal resources. A separately authenticated producer
and original-paper evaluation are still required. No authentic run, scientific
improvement, finished benchmark, or current-SOTA result is claimed.

Canonical task, contract, registry, shared source, and predecessor files are
unchanged. Integration may list this successor as a scoped source repair; it must
not replace the historical implementation or raise scientific readiness.
