# Same-task paper improvement

Every current paper task requires surpassing the source-paper result on the same
original scientific task. Reproduction is a calibration prerequisite and cannot
earn active paper success. The original 116 registrations are retained; their
current eligibility and readiness are counted separately in the
[paper catalog](../../../benchmarks/catalog/paper.md).

Each task has a versioned `improvement.v1.json` with paper-specific evidence,
original-task anchors, comparison rules, iteration and evaluation requirements,
and unresolved facts. Current `task.json` binds that contract by byte length and
SHA-256. Original task bytes remain in `historical/task.pre-improvement.v1.json`;
the prior registry and all old implementations remain available as historical
calibration evidence.

| Disposition | Meaning |
| --- | --- |
| `improvement_ready` | The source-matched contract, explicit comparison policy, budgets and qualified evaluation route meet admission requirements. This is not an observed improvement. |
| `design_ready` | An ordered original source task is defensible, but comparison or execution gates remain. |
| `source_unresolved` | The original task identity, baseline, source recipe or comparator cannot yet be recovered sufficiently. |
| `ineligible` | The reviewed source has no defensible ordered performance endpoint for this task, or the proposed comparison is scientifically incompatible. Historical materials remain available. |

Eligibility counts combine `improvement_ready` and `design_ready`. They do not
count source-unresolved or ineligible entries as active improvement-ready tasks.
Unresolved facts are explicit nulls and blockers, never fabricated scores.

## Scientific comparison

The original target, dataset version, cohort, split, allowed inputs, preprocessing,
metric formula, direction and aggregation must match. A new split, smaller cohort,
changed endpoint or easier information condition is an extension and cannot count
as a source-paper victory. Published paper scores and rerun author baselines are
distinct; an agent-written local baseline cannot replace either. A current-SOTA
claim needs separately verified primary sources and a matched comparison.

Iteration uses declared training/validation feedback. The candidate method and
comparison policy are frozen before final evaluation. A paper win must exceed the
paper endpoint by a scientifically justified effect and satisfy the predeclared
uncertainty rule using valid independent units. Stronger significance alone is
not improved scientific performance. There is no invented universal margin,
alpha, independent sample count, or resource allocation.

## Public commands

```sh
python3 -I -S -B scripts/neurobench.py status
python3 -I -S -B scripts/neurobench.py list --track paper
python3 -I -S -B scripts/neurobench.py paper-contract PAPER-paper-method-034
python3 -I -S -B scripts/neurobench.py compare-paper PAPER-paper-method-034 --result comparison.json
```

`compare-paper` checks aggregate evidence against the pinned current contract and
its explicit machine admission policy. It does not run a model, open hidden
targets, certify authorship of evidence, or establish a protected evaluation
boundary. Nonready contracts cannot admit paper wins. The
[schema](contract.schema.json) and
[comparison engine](../../../src/neurobench/paper_improvement.py) define the
machine fields and failure conditions.

Legacy `score` and `run` commands refuse paper adapters unless `--calibration` is
explicit. Their outputs retain their historical numerical meaning and cannot
establish the current success objective. Existing pilot results are preserved as
calibration, including failures and exposed development endpoints.

## Maintaining current bindings

Curate the paper-specific contract first, preserving primary source locators and
unknowns. Then run the deterministic binder and regenerate the catalog:

```sh
python3 -I -S -B scripts/maintenance/bind_paper_improvement.py
python3 -I -S -B scripts/catalog.py
python3 -I -S -B scripts/maintenance/bind_paper_improvement.py --check
python3 -I -S -B scripts/catalog.py --check
```

The binder preserves the original source identity and requires complete coverage
of the registered paper roster. Schema validation and metadata consistency tests
do not demonstrate empirical improvement. New qualified execution and review
must close the task-specific blockers before readiness can change.
