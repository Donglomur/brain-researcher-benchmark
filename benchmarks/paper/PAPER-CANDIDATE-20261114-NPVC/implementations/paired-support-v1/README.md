# Paired NPvC support verification

This operator component checks that two supplied NPvC/GLM operand bundles cover
exactly the same separately declared neuron/epoch and trial/frame observations.
It then invokes the existing [FDE equations component](../fde-equations-v1) to
recompute both full vectors. It does **not** decide whether a candidate surpasses
the paper or authenticate the declaration as the original study population.

The existing equation evaluator intentionally accepts partial supplied support.
Comparing its two output files alone could therefore compare different neurons,
frames, folds, observed activities or activity coordinates. This additional
component rejects those mismatches. The declaration is a third operator input;
it is never inferred from whichever submission happens to contain fewer rows.

## Inputs and use

```sh
python3 -B paired.py --support /operator/declared-support.json \
  --author /operator/author-operands.json \
  --candidate /operator/candidate-operands.json \
  --output /operator/fresh-paired-report.json
```

All three inputs and the report belong to the evaluator. The support includes
observed activities and must not become a participant-facing development input.
The component does not create a filesystem or network sandbox.

The support document has schema `npvc-declared-support-v1` and a nonempty `units`
list. Each unit has the same `identity`, `activity_bounds` and `observations`
structure as `npvc-fde-operands-v1`, except observations contain only `trial_id`,
`frame_id`, `fold_id`, `trial_type` and `activity`. The two operand documents use
the existing equation evaluator's input schema. Every declared unit and
observation must occur exactly once in each bundle. Unit/observation ordering
may differ; scoring follows declaration order. Unexpected fields, duplicate
JSON keys, nonfinite values and changed equation dependency are refused.
Correspondence uses validated original numeric values, so unequal integers
above2^53 cannot become equal through float rounding. Numerically equal1 and1.0
remain equivalent. The pinned equation component retains its existing floating
point arithmetic; exact input correspondence does not make that arithmetic exact.

The declaration does not choose a new fold assignment unit. It checks supplied
fold IDs within each neuron/epoch, without assuming whole-trial folds or shared
folds across neurons. No cohort size, missing epoch, trial-type subset or source
membership becomes valid merely because the three files agree.

The output retains every declared unit, both recomputed results and separate
NPvC/GLM FDE differences. Undefined operands produce a null difference without
dropping the unit. Negative FDE and values above one remain visible. No neuron
mean, pooled win count, selected subgroup, significance test or threshold is
introduced. Model-specific null and saturated likelihood totals are preserved;
their differences are explicitly flagged rather than silently replacing them
with common denominators.

Each input is limited to64MiB. This is a per-file parsing limit, **not** an
authenticated full-study capacity estimate or an admitted memory envelope.
The existing equation file is checked against its reviewed SHA256 before use.
Updating that dependency requires review and a corresponding pin update.

## Scientific boundary and remaining work

The original Figure2 comparison concerns held-out neural prediction with NPvC
and GLM and reports a neuronwise FDE distribution. The official pinned README
describes NPvC/GLM software and simulation workflows; it does not supply the
missing empirical Figure2 producer. See the [paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC12672379/)
and [pinned author README](https://github.com/houman1359/Triplets/blob/68d9f18993f7a33c5c1df21b5fe392f857aed4fa/README.md).

The two supplied bundles here both use the existing NPvC/GLM operand interface.
This is not an admission interface for arbitrary new prediction model families.
Genuine source fitting, complete original support, source-conformant folds,
protected exposure, density/normalizer admissibility and the full-panel
superiority policy remain unresolved. File hashes establish input identity,
not any of those scientific facts. Output fields therefore retain
`paper_win: null`, `scientific_outcome: unknown`,
`source_membership_authenticated: false`, `complete_source_cohort: null` and
`readiness_promoted: false` even when all numerical differences are positive.

The next source step is recovery of the real-data fit caller and an explicit
release-to-eligible-observation mapping. The paired guard can then be bound to
that independently authenticated declaration. A paper-result improvement claim
still needs a separately justified comparison policy; this component does not
choose one to turn a diagnostic difference into a win.

## Checks

`python3 -B test_paired.py` contains18 generated checks, including dropped and
substituted support, altered targets/folds/conditions/coordinates, duplicate
records, undefined denominators, out-of-range FDE, normalizer differences,
fresh-output enforcement and changed equation binding. The first15 checks
passed once; after binding execution to the exact hash-verified bytes, the
affected dependency-refusal check and one new no-reopen check passed separately.
Independent review then identified rounding of large integer correspondence
values. Two targeted regressions passed after preserving original numeric
identities; these also cover a target just outside its raw upper bound.
No full18-check final suite execution is claimed by that construction history.
The small fixtures are
explicitly generated partial declarations, not original study data. The checks
establish component behavior only. No authentic-data or AI execution is claimed.
