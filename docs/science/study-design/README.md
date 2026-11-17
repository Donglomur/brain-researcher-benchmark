# Freeze a paired neuroscience study

Use the [paper template](paper.template.json) to plan paper-plus-data versus paper-plus-data-plus-code comparisons, or the [neural template](neural.template.json) to plan frozen-program versus live-investigation comparisons with explicit tool access. Copy a template into a new study directory and bind it to the complete scientific task contract. Preserve this source template unchanged.

These templates remain unbound planning documents. A [companion description validator](../../../src/neurobench/study_binding_validator/README.md) now checks a normalized binding format with an exported schema, complete assignments, matched budget declarations and endpoint-specific denominators. It accepts the companion format, not these raw templates, and never opens referenced artifacts. Neither the templates nor a passing description check supply data, measured budgets, statistical defaults, scientific qualification or execution authority.

The [scientific task-scope policy](../task-scope.md) defines task granularity and qualification. The [current construction status](../../provenance/status-snapshots/CONSTRUCTION_STATUS_20261115.md) reports programme readiness and counts; historical counts in the scope document do not override it. Conditions and comparisons do not add benchmark registrations.

## Bind before evaluation

1. Attach exact task revisions and the complete scientific endpoint, including all required cohorts, comparisons and controls. Freeze corpus selection, exclusions and a source-family/biological/stimulus overlap graph across both suites. Keep future RL training and outer evaluation separated by this graph.
2. Bind every artifact ID to an immutable metadata document with a locator, byte count and SHA256. The source template contains no real participant identifiers, target values, credentials or signed URLs. Held-label maps and exposure details remain in evaluator-controlled storage; reference their authenticated metadata. Do not traverse or publish private locators merely because they appear in a template.
3. Freeze the assignment manifest before outcomes: all tasks, pairs, arm IDs, model/scaffold versions, repeat indices, case manifests and randomized condition order. Do not assume an API supports reproducible seeds. Use independent contexts/workspaces/caches and preserve exact served-model identity where observable. Repeated agent runs estimate agent variability; they do not increase biological or paper sample size.
4. Complete source-qualified budget profiles from measured references. Record wall time, CPU/GPU time, peak memory, calls, tokens and money separately, including currency and pricing date. An identical budget-profile ID means the same actual limits and hardware for the intended contrast. Declaration alone is not enforcement.
5. Freeze primary and exploratory contrasts, estimands, all assigned denominators, metric direction, scientifically meaningful effect, unit-level aggregation and paired uncertainty. Specify the family of multiplicity-controlled claims and exact rule; no universal p-value threshold is supplied. Bind executable analysis and its independent review.
6. Freeze candidate selection, repeat allocation, retry limits and stopping rules before assessment. Use development observations for selection. A fixed allocation needs a measured precision/power rationale; a sequential allocation additionally needs a prespecified valid monitoring rule. Do not repeatedly inspect results until they become positive.
7. Establish authentic input-to-reference-to-evaluator evidence, contamination/exposure review, calibrated scientific-judgment criteria and independent complete admission. A metadata-complete manifest does not establish these facts. Only a separately authorized actual operation may run.

Required decision fields must be bound or explicitly inapplicable with a scientifically reviewed reason. An unused branch, such as sequential boundaries in a fixed-allocation study, may remain null only when the chosen design and that exception are explicit. Primary contrasts cannot be left unspecified. An unresolved required field keeps state DRAFT_UNBOUND_NOT_EXECUTABLE. There is intentionally no command that flips this state or launches a task.

## Paper access and improvement

paper.template.json has the two required access arms. The same paper/data/features/environment/library, evaluation and stage budgets must be used; sanitized official code is the intended information difference. Validate that offline retrieval, dependencies, prefit artifacts, notebook outputs and setup assistance do not reintroduce answers or the withheld implementation. Keep the scientific specification sufficient in both arms. Record repairs instead of hiding unequal assistance.

Reproduction is locked before improvement. Keep stage budgets separate for the primary experiment; unused reproduction budget cannot silently become improvement budget. Audit every unit exposed by reproduction and development. Overlap or unresolved exposure prevents a protected-confirmation claim, even if a renamed file is hidden locally; retain the attempt as development-only. Historical public labels remain an exposure limitation even with correct runtime isolation.

Compare the locked candidate to the original method rerun on identical cases and resources. A changed cohort, split, metric or budget is a new comparison, not direct improvement over the paper's quoted number. Contemporary superiority and scientific novelty are stronger separate claims with their own comparators and review. A valid null or substantiated discrepancy can be scientifically valuable without counting as numerical improvement.

Retain every assigned project. Primary validated-improvement success includes absent, invalid and failed submissions in its assigned-project denominator. Numerical effects among valid submissions must disclose coverage and selection; they cannot silently replace the whole-study estimand. If a primary continuous endpoint requires a failure penalty or missing-data model, predeclare and justify it; this template supplies neither an arbitrary worst score nor complete-case deletion.

## Neural modes, controls and cost

neural.template.json defines frozen-program/live-investigation crossed with numerical/specialist tools. Both modes receive identical signals, representations, metadata, calibration, quality flags and allowed adaptation within a contrast. A frozen program may calibrate or adapt according to its frozen policy; it simply makes no new LLM calls during assessment. The investigator may choose actions within a case but may not update its global strategy from final labels or scores.

The controlled comparison matches development and numerical inference allowances while making live LLM cost explicit. It is not equal total expenditure. The cost view includes development amortized over a prespecified case count and measured inference cost; specialist pretraining/provisioning cost treatment must also be declared. A richer-input specialist reference may be informative but is not an equal-information access effect.

Decide which contrasts are primary before results. Report the two conditional mode effects separately unless a prespecified interaction/aggregation analysis justifies combining them. Shared cases and task families remain paired/dependent. Aggregate sessions within animal and trials within participant where appropriate; crossed stimulus dependence may require crossed rather than merely participant resampling. Restrict inference to a finite panel when population support is absent. Do not average unrelated physical metrics into one capability score.

Bind useful simple/model-only and context/nuisance controls. A signal-disruption transformation must preserve the nuisance structure required by its hypothesis, have a valid exchangeability or mechanistic rationale, and avoid creating label-revealing artifacts. A performance drop under an arbitrary destructive shuffle does not alone establish neural understanding.

The direct-signal extension is a separate unbound comparison, not the frozen-program cell. Freeze a sample/feature representation and identify its actual processing level; deterministic preprocessing is not equivalent to raw input by default. Match cases/calibration/representation for an access claim, disclose unequal reasoning/cost allowances, and enforce no-tools transport. Include context-only and scientifically valid disrupted-signal controls. No single score establishes a biological mechanism or replacement of a foundation model.

## Required review checks

- Every contrast names two distinct existing arms; all linked IDs resolve to pinned metadata.
- Cases, task revision, scoring, base information and intended matched budgets agree within a pair. Differences beyond the declared intervention are either corrected or explicitly change the estimand.
- All phase, exposure, biological/stimulus/family grouping and causal-time joins are evidenced, not inferred from file names.
- Repeat indices are not new biological units; family reuse cannot silently dominate weighting.
- Every assigned attempt remains in the ledger. Failure classification, bounded retries, retry budget, selection and stopping are outcome-independent and auditable.
- All required bindings, primary comparisons and decision rules are resolved before execution. Null/empty placeholders cannot be interpreted as zero cost or permission.
- The claim stays within actual evidence: no automatic qualification, uncontaminated-test, causal-mechanism, SOTA, novelty or submission-readiness promotion.

This checklist includes scientific and human review obligations beyond the companion validator. Its source checks enforce declared structure and joins; family-specific validation, artifact authentication, executable analysis and actual enforcement remain separate. No model campaign or scientific execution is selected by these documents.
