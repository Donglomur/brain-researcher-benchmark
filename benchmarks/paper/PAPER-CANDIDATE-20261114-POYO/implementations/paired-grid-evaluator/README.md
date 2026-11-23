# Paired POYO submitted-grid comparison

This component fills the previously documented missing both-submissions-before-target
barrier for the prospective POYO grid consumer. It accepts one owner-frozen design
and two complete prediction grids labeled `paper_data` and
`paper_data_author_code`. Both grids must pass the unchanged protected evaluator's
complete public admission before the trusted target loader is invoked once. The
returned target bytes are frozen in memory and reused for both scoring calls.

The existing [protected grid evaluator](../protected-grid-evaluator/README.md)
retains its current arithmetic, global trial protection, timestamp stitching,
complete method/case support, and qualification limits. `compare.py` authenticates
its source SHA256 and executes that same byte snapshot. No source, split, metric,
or threshold in that component is changed.

The report preserves both complete arm reports and adds matched session/dimension
and summary differences, with author-code minus paper-data direction. Differences
subtract the represented binary64 report values exactly before conversion back to
binary64; they are not differences of the original unrounded rational reductions.
There is no new win rule, uncertainty procedure, or pooled cross-budget endpoint.

## Use

The callable is `evaluate_pair(design_body, design_pin, paper_data_body,
paper_data_author_code_body, target_loader)`. It trusts the owner-supplied loader;
the CLI additionally authenticates returned target bytes against the owner's
expected extent and SHA256. All paths and identities must be supplied by the
trusted operator. Reports, including target identities, remain evaluator-private.

Run from this component directory with Python 3.11 and standard library only:

```sh
python3 -I -S -B compare.py \
  --design OWNER_GRID.json --design-bytes N --design-sha256 SHA256 \
  --paper-data PAPER_DATA_SUBMITTED.json \
  --paper-data-author-code ASSISTED_SUBMITTED.json \
  --targets OWNER_TARGETS.json --targets-bytes N --targets-sha256 SHA256 \
  --output NEW_PRIVATE_COMPARISON.json
```

The protected evaluator's bounded, non-following regular-file input reader and
exclusive output creation are retained. The scorer dependency must remain at
`../protected-grid-evaluator/evaluator.py`. Input parsing and rational reductions
repeat per scoring call; source correctness does not establish resource adequacy
for an authentic complete grid. The 64 MiB per-operand ceiling is not a total
memory or execution-time bound.

## Scientific scope

Condition names label two submitted grids. This consumer cannot establish separate
AI authorship, denied author-code access, interaction histories, matched compute,
certified methods, or competent fixed references. It does not enforce a limit on
evaluations across separate invocations. The four methods remain submitter-supplied
tables, as explained in the original
[mandatory scope clarification](../frozen-grid-evaluator/SCOPE_CLARIFICATION.md).

The prospective 158-member corpus ABI remains separate from recovery of the
original 158 pretraining sessions and the distinct historical transfer populations.
Original data joins, transfer rosters, adaptation budgets, source metric lineage,
historical references and tolerances remain unresolved. Every original per-arm
qualification flag remains false, and the paired report also marks condition
isolation, independent authorship and matched resource budgets unverified.

Generated controls exercise paired public admission, a single shared target load,
unchanged scoring, descriptive alignment, identity binding, CLI behavior and scorer
source authentication. They use invented values and do not produce an authentic
paper reproduction, improvement, benchmark episode or SOTA result.
