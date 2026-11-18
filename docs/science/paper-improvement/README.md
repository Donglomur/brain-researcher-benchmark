# Same-task paper improvement

This guide describes the retained `improvement/v1` outcome: surpassing the
source-paper result on the same original scientific task. Within that outcome,
reproduction supplies calibration and does not establish improvement. Paper
reproduction is also an independent outcome, judged by its frozen original-finding
agreement rule; its success does not require improvement. The original 116
registrations are retained; their current eligibility and readiness are counted separately in the
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

The original target, dataset version, cohort, source-defined splitting protocol,
allowed inputs, metric formula, direction and aggregation must match. Historical
assignments must also match wherever the claimed comparison requires them. The
`same_task.preprocessing` anchor preserves comparability-critical data
preparation, quality control and observation constraints, and records the author
baseline recipe. It does not
require candidates to copy the author feature extractor, normalizer or model.
Train-only feature engineering and learned representations are allowed within
the same permitted inputs; dropping test rows, target-informed normalization or
adding observations changes the comparison. Changing the split unit, sampling
population, permitted information, endpoint or evaluation protocol changes the
comparison. A smaller cohort, changed endpoint or easier information condition
cannot count as a source-paper victory. Published paper scores and qualified
rerun author baselines remain distinct; an arbitrary local comparator cannot
replace either. A current-SOTA claim needs separately verified primary sources
and a matched comparison.

Distinguish the source evaluation protocol from its historical realized
assignments. Regenerating assignments under a sufficiently specified original
stochastic protocol can support a same-task comparison, provided the regeneration
is declared and frozen before candidate selection, and both the qualified
source-method rerun and candidate use identical protected evaluation cases.
An unrecovered original random seed remains an unresolved source fact; it does
not authorize a different held-animal split.

Such evidence supports "improvement over a qualified source-method rerun on
preregistered new folds." It does not recover historical author assignments,
establish reproduction of the published score, or establish superiority to a
published aggregate measured on different cases. Preserve the published
reference and its unresolved provenance separately. Qualification requires the
complete original endpoint and controls, a competent verified comparator,
permitted tuning and resource use, a justified effect criterion, and paired
uncertainty respecting biological dependence. Animal-aware inference must retain
the original endpoint weighting and aggregation; it does not authorize replacing
a session-weighted estimand with an equally weighted animal mean. Folds,
shuffles and restarts do not add independent animals.

This distinction does not change existing `improvement/v1` admission rules or
task dispositions. A task needs an explicitly reviewed comparison policy before
the scoped rerun claim can be admitted. Missing historical assignments remain
unresolved wherever historical reproduction requires them. A fresh-fold
comparison establishes no current-SOTA claim, and a new assignment does not erase
prior public-data exposure.

A contract may select a scientifically meaningful complete original endpoint or
panel, with its required controls and companion quality metrics. It must name the
result being surpassed. Success on that panel does not mean every result in the
paper was surpassed; unrelated figures need not become additional requirements.

Iteration uses declared training/validation feedback. The candidate method and
comparison policy are frozen before final evaluation. A paper win must exceed the
paper endpoint by a scientifically justified effect and satisfy the predeclared
uncertainty rule using valid independent units. Stronger significance alone is
not improved scientific performance. There is no invented universal margin,
alpha, independent sample count, or resource allocation.

Paper/data/official-code access must separate allowed training and validation
information from protected final labels. Author repositories may contain test
labels or cached predictions; participant delivery must remove forbidden target
material and record prior public-test exposure and contamination limits. Shared
host access rules are not isolation evidence. A published test endpoint does not
become untouched because its local filename is hidden. A new protected transfer
panel may supplement the original source comparison, but remains a separately
labelled extension.

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
machine fields and failure conditions. Admitted metadata returns
`comparison_admitted: true`, `paper_win: null` and verification `unverified`;
only a trusted evaluator and independent evidence review can establish an actual
paper win. Rejected or nonready comparison evidence returns exit status 2;
metadata admission returns 0.

Legacy `score` and `run` commands refuse paper adapters unless `--calibration` is
explicit. Their outputs retain their historical numerical meaning and cannot
establish the `improvement/v1` success objective or independently verified paper
reproduction. Existing pilot results are preserved as calibration, including
failures and exposed development endpoints.

## Explicit source-method rerun API

The same `paper_improvement.py` module provides an explicit
`paper-improvement/v2` contract and `paper-improvement-result/v2` result branch.
Its runtime schemas are `RERUN_CONTRACT_SCHEMA` and `RERUN_RESULT_SCHEMA`; the
public schema is [contract.v2.schema.json](contract.v2.schema.json). Supply the
original v1 source contract to both entry points:

```python
contract_validate(contract, source_contract=original_v1_contract)
compare(contract, result, source_contract=original_v1_contract)
```

Missing original-source evidence rejects admission. The explicit claim is
`same_task_author_method_improvement`; its published score is contextual and may
be null. This branch always leaves `paper_win` null and unverified.
`comparison_admitted` and `criterion_satisfied` describe declared metadata only;
`scientific_outcome` remains `unknown`. Trusted execution and independent
scientific verification remain necessary.

This branch covers one ordered scalar endpoint with required granular outputs
and source-qualified numeric bounded companion controls. Every required control
must pass for both candidate and baseline; controls never contribute gain. It
cannot represent vector-panel superiority, and a vector-panel task cannot
collapse its endpoints into a scalar to use this API.

The qualified author method may use author-released code or an independent
implementation of the paper method, with explicit primary-source and independent
qualification evidence. The required output map, source split recipe and source
blocker adjudications must bind the same qualification record. Paired evidence
must bind candidate and qualified source-method rerun to the same protected case
manifest, source identities and required outputs, with explicit assignment,
freeze and exposure provenance. The bound biological-unit roster and count
govern paired uncertainty; the source endpoint's weighting and aggregation remain
unchanged.

The current branch requires separate candidate and baseline executions, with
independent verification, inside the same final evaluation window. Cached
baseline reuse is not supported. Cumulative budgets cover both candidate and
baseline work, including tuning and failed attempts.

Existing v1 semantics and defaults remain unchanged. No task, CLI, catalog or
paired-outcome envelope is migrated or adopted by adding this API; it changes no
readiness, task or scientific-result count and establishes no SOTA claim.

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

The [source-grounded next-build shortlist](next-builds.md) identifies concrete
original endpoints with recovered numeric anchors and the smallest remaining
construction steps. It is a source-completeness judgment, not measured model
performance or a prediction of improvement.
