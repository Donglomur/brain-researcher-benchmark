# Figure 4D paired information-condition comparison

This operator component composes the existing prediction scorer and shared-draw
validator across `paper_data` and `paper_data_author_code`, separately for
`reproduction` and `improvement`. Previously the paired-draw entrypoint accepted
one author/candidate pair. Scoring four such panels separately did not require
the same source population, draw ledger, targets or author predictions across
information conditions. Here one shared operator panel binds all four submissions
to the same original 25 sessions, 100 repetitions and five comparison arms.

This is a complete-panel arithmetic capability, not a scientific decision rule.
The original conditional-context endpoint, companion global/shuffle comparisons,
equal weighting of conditioning groups, repeated bootstrap occurrences and
unresolved scientific criteria remain unchanged. No new data preparation,
classifier, split, historical seed, reference score or tolerance is introduced.

## Operator inputs

Run from an installed repository layout with both hash-bound sibling components:

```sh
python3 -I -S -B compare.py /operator/comparison-panel.json > /operator/diagnostics.json
```

The manifest has exactly `schema: hierarchy-figure4d-condition-comparison/v1` and
`sessions`. Each of the 25 sessions has exactly these fields:

| Field | Contents |
| --- | --- |
| `animal`, `date` | Literal original source identities from the existing scorer's roster. |
| `source` | One descriptor for operator source PV metadata. |
| `ledger` | One descriptor for the shared original-protocol draw ledger. |
| `reference` | Five arm descriptors for the common author reference predictions. |
| `submissions` | Both outcome names, each containing both information-condition names, each containing all five arm descriptors. |

An arm descriptor contains exactly `path`, `bytes`, and lowercase `sha256`.
The arm names are `global`, `global_context_shuffle`, `conditional`,
`conditional_context_shuffle`, and `conditional_position_shuffle`. Descriptor
paths are operator-controlled and resolve relative to the manifest. Distinct
exports are required for every reference/submission/arm/session; identical
prediction values are allowed. Reference predictions are supplied once and reused
mathematically in all four candidate comparisons.

The [shared-draw input specification](../figure4d-paired-draws-v1/README.md)
defines the source metadata, 70/30 partitions, within-partition replacement draws
and six-field prediction CSV. This entrypoint uses those unchanged validators.
Every submission must join every declared held occurrence exactly once, including
repeated PV identities, and agree with the operator's context/condition labels.
Rows may arrive in different orders. All four submissions use a single source and
ledger by construction; the schema has no per-condition override.

The original [source audit](../figure4d-prediction-scoring-v1/SOURCE_AUDIT.md)
retains the author-code defects and unresolved original input and metric questions.
`SOURCE_BINDINGS.json` records the local contracts/dependencies used here. It does
not replace their historical pins. The numerical scorer and draw checker are
loaded from captured, hash-verified source bodies; dependency edits require review.

## Diagnostics and interpretation

The report keeps each session's unchanged author and submission score reports,
draw-support counts and input body hashes. Within each outcome it also emits:

- `candidate_minus_author`, separately for each information condition and arm;
- `author_code_minus_paper_data`, separately for every arm.

Each contrast contains both exact-match-accuracy and normalized-absolute-error
differences for every repetition and conditioning group, plus the existing
descriptive equal-repeat summary difference. Positive accuracy difference and
negative error difference describe opposite signs of the same binary calculation;
neither selects the unresolved published ordinate or means a paper win. The
information-condition contrast subtracts candidate scores directly, rather than
pooling reproduction and improvement submissions. Candidate-minus-author arithmetic
does not replace reproduction's missing paper targets or improvement's missing
meaningful-effect rule. There is no cross-outcome gain calculation.

Missing conditioning-group support stays undefined: the conditional score and
its difference are `null`, while an available global score remains defined.
No session or group is dropped, no bootstrap occurrence is deduplicated, and no
cross-session aggregate or biological uncertainty is invented. All 25 source
sessions are required, and their five-rat structure stays explicit.

The operator must independently establish observation lineage, speed equalization,
original condition resolution, actual fitting on declared training draws, valid
shuffle construction, code-only exposure and matched cumulative budgets. Supplied
hashes or schemas establish none of these. All scientific outcomes remain unknown,
`paper_win` remains null, and this component does not activate the registered task.

## Generated controls

```sh
python3 -I -S -B test_compare.py
```

Controls check the full 25-session composition using the existing scorer, the
real file hash reader for one generated session, positive and negative paired
differences, equal-condition versus pooled weighting, independent outcome records,
reordered prediction rows, source-identity/target substitution, omitted comparison
members, export reuse and undefined conditional scores. Generated metadata and
CSV rows contain no neural data and do not demonstrate authentic reproduction,
information-condition enforcement or improvement.
