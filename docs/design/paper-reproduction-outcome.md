# Paper reproduction and improvement as independent outcomes

The scientific questions are **can an AI recreate the original findings?** and
**can an AI exceed them on the same original task?** Each has two information
conditions: paper+data and paper+data+author-code. These are four assessment cells
within one registered paper task, not four tasks. Reproduction is a first-class
outcome; operator replay of the author's method remains baseline calibration.

This additive implementation is in `src/neurobench/paper_reproduction.py`. It does
not migrate existing tasks, change `improvement.v1.json`, enroll new runtime
components, run a solver, or relabel historical results. The existing eight
historical solver attempts keep their original scope and evidence. No new
scientific reproduction or improvement result is established by this change.

## Three metadata contracts

| Contract | Purpose | Public runtime schema |
| --- | --- | --- |
| `paper-reproduction/v1` | Original findings, source fidelity, independent eligibility, tolerances and uncertainty | `CONTRACT_SCHEMA` |
| `paper-outcomes/v1` | One original task; digests of the separate reproduction and existing improvement contracts; matched protocols for each outcome | `OUTCOMES_SCHEMA` |
| `paper-outcome-receipt/v1` | One newly executed AI attempt, one outcome, one information condition, frozen artifacts and final evaluation provenance | `RECEIPT_SCHEMA` |

`RESULT_SCHEMA` describes reproduction measurements inside a receipt. An
improvement receipt instead carries the unchanged `paper-improvement-result/v1`
payload. All schemas are JSON-compatible dictionaries. The module exports
`contract_digest`, `load_contract` and `loads_contract`, using the existing strict
JSON reader and canonical JSON SHA256. Duplicate keys, unknown fields, nonfinite
numbers and Python-only values are rejected. Raw-file hashes and canonical JSON
digests are different concepts and must not be substituted for each other.

The four entry points are:

```python
contract_validate(reproduction_contract, task_id=None)
outcomes_validate(outcomes, reproduction_contract, improvement_contract)
admit_outcome(outcomes, reproduction_contract, improvement_contract, receipt)
summary(outcomes, reproduction_contract, improvement_contract, receipts=())
```

These functions do not read artifacts or authenticate paper interpretations,
cohorts, actual exposure, AI activity, evaluator execution or budget accounting.
They validate consistency of supplied declarations. `scientific_outcome` is
always `unknown`; `metadata_admitted` and `criterion_satisfied` must never be
displayed as verified scientific success. The downstream operator must verify
the actual immutable execution and scientific evidence before assigning any
scientific outcome. Such a trusted scoring path is not implemented here.

## Independent reproduction eligibility

Reproduction eligibility is `eligible`, `design_ready`, `source_unresolved` or
`ineligible`, with a reason and explicit blockers. It is not copied from
improvement disposition. An original descriptive finding may have a defensible
reproduction endpoint while lacking a meaningful superiority direction.
`eligible` means the source-grounded endpoint and its admission policy are fully
specified. It does not establish a prepared dataset, enforceable participant
boundary, runnable benchmark or successful AI performance.

An eligible reproduction contract requires:

- The original target, dataset, cohort, split, inputs, preprocessing, metrics and
  aggregation, plus explicit full-panel and permitted-observation anchors.
- Every required original finding and companion control, with source evidence,
  units and aggregation. The final receipt must contain exactly that set, without
  omissions, duplicates, added post-hoc endpoints or selective averaging.
- A pinned evaluator and immutable identity manifests for the ordered cohort,
  split, complete panel, permitted observations, metrics and aggregation.
- A source-grounded computation policy: submitted-analysis interface, authentic
  data manifest, independent verification program and required granular outputs
  covering every finding and companion control.
- Source-grounded expected values and justified evaluation criteria, with no
  unresolved scientific blocker. The validator cannot itself determine whether
  the declared panel is complete or the source interpretation is correct; those
  are mandatory scientific-review responsibilities.

Findings may be scalar scientific effects, errors, correlations or other source
quantities; they need not be prediction accuracy. They may also be categorical
scientific findings with a frozen vocabulary and exact expected category. A
categorical direction cannot replace a required numerical magnitude, uncertainty
estimate or companion analysis. Those remain separate required findings.

For a scalar, no default tolerance is supplied. Its nonnegative absolute
tolerance needs an explicit rationale and evidence: source precision,
source-grounded variability or a justified preregistered scientific criterion.
The underlying expected finding itself needs primary paper/code/data evidence;
a registration citation cannot invent a source result. The manifest does not
verify the truth or timing of cited justifications. Independent source review and
trusted pre-execution freezing remain necessary.

For uncertain numerical reproduction, both the estimate and its entire declared
confidence interval must lie inside the source-target tolerance band. Interval
overlap and failure to reject a difference are insufficient. The independent unit,
minimum number of independent units, interval method and confidence level are
frozen. Numerical subtraction uses declared decimal values to avoid inventing a
boundary failure or success through binary floating-point rounding.

Categorical inference may use a predeclared source-finding significance or
posterior rule. A p-value rule must be an upper bound in `(0,1)`; a posterior rule
must be a lower threshold above `0.5`. The frozen evaluator must test the actual
source finding and direction, not an unrelated null. Nonrejection cannot count as
evidence of reproduction. Source-justified deterministic findings are also
supported and do not claim independent statistical replication. Unsupported
inferential designs stay unresolved rather than being forced into these rules.

A complete, structurally valid result that misses a frozen criterion is retained
as a **declared mismatch**, with per-finding matches and `criterion_satisfied`
false. A missing, malformed or ineligible result has a null criterion, not a failed
scientific score. Both keep the scientific outcome unknown until independently
authenticated. Existing improvement comparison errors retain their prior
semantics; this module does not reinterpret them as verified negative results.

## Computational reproduction is more than copying the paper

The paper is an allowed input. Its printed values, tables and categorical claims
are therefore known answers. Matching them alone does not demonstrate that the
AI reconstructed and executed the analysis. An executable program that merely
prints those known aggregates is also insufficient.

The computation policy names source-grounded granular outputs: for example,
observation-level predictions, source-native masks, time courses, coefficients
or derived contrasts, with original identities, units and required controls.
Each required finding must be covered by a declared output. The policy has no
universal output choice and does not require the author's code or an identical
numerical implementation. Independent implementations and justified numerical
techniques must preserve the scientific model, estimand and method defining each
claimed source finding. An unrelated method matching a printed score does not
reproduce that method-specific finding; permitted method changes are assessed
separately as improvement. The policy must provide enough task-specific evidence
to distinguish calculation using the
authentic data from copying the published aggregates. There are no invented
hidden perturbations or changed-task checks.

An AI receipt must include a runnable submitted-analysis entrypoint, exact
candidate/interface/input/data/author-code identities, runtime and invocation
manifests, and independent operator execution. A separate source-grounded
verification record binds that execution, every required granular output and
the final reported findings. Its timestamps lie inside the final evaluation,
after candidate freeze. Missing analysis, missing verification, self-reported
verification, mismatched authentic inputs, omitted outputs and unverified
outputs cannot be admitted. These controls also apply to the new paired
improvement envelope without changing improvement/v1.

Hashes, role labels and a declared `verified` status cannot prove that an analysis
used the data. A trusted operator must inspect/rerun the submitted program and
independently check source-native outputs and their derivation of the reported
findings. This module only checks the resulting metadata for consistency and
never turns it into verified science. A categorical match has no exemption.
When only published aggregates can be checked, the computation policy records
`published_aggregate_only`; the endpoint cannot be eligible for computational
reproduction. Report that limitation rather than replacing the source task or
promoting copied claims to an AI result.

## One original task and two information conditions

The outcome bundle binds the original task hash and the exact digests of both
contracts. It additionally requires the same source-paper URL and identical
descriptions of every original `same_task` anchor already represented by
improvement/v1. Evidence IDs and verification statuses may differ; eligibility
remains independent. The `objective` fields express the two questions, while the
`target` anchor identifies the same original scientific target in both.

This description check is a conservative bridge because improvement/v1 lacks
immutable per-anchor execution identities. Scientifically equivalent but
differently worded descriptions fail closed until a reviewer aligns the factual
source descriptions. Do not rewrite facts merely to satisfy the validator. When
both paired protocols are specified, their ordered cohort, split, full-panel,
observation, metric and aggregation identity hashes must also match. Evaluator
implementations and decision criteria can differ between the two questions.

Current paired bundles require matching split manifests across reproduction and
improvement protocols. They cannot represent historical replay and a different
fresh-fold evaluation as the same split. This check remains unchanged. An
explicitly selected rerun-improvement policy must distinguish source-assignment
provenance from the evaluation manifest while retaining identical evaluation
cases within each admitted comparison. It cannot resolve missing historical
assignments or populate an original-result reproduction claim merely by using
new folds.

Each outcome has its own pairing status and frozen protocol. Within a pair,
common input manifest, evaluator, original scientific identity, exposure policy
and cumulative access/resource budgets are identical. The code manifest is the
only permitted information addition. Separate run, AI trace, exposure, freeze,
evaluation, analysis-execution and output-verification receipts identify the
independent condition executions. Candidate, runtime and static invocation
artifact hashes need not differ: independently recreating the same algorithm is
valid, and an AI in the +code condition may use the supplied author code.
A lifecycle report retains the same raw identity if its role label changes;
reusing it across conditions is rejected even under a different lifecycle role.

An unavailable author-code manifest is represented as null. This leaves the
paper+data condition available when otherwise specified, but prevents admission
of the +code condition and prevents a completed paired comparison. Availability
is distinct from endpoint eligibility and actual runtime readiness. If the common
protocol itself is unresolved, neither condition receives a result. There is no
fallback to invented code, smaller data, altered splits or relaxed observations.

A receipt binds its task, outcome, condition, pair, candidate, final result,
delivery and evaluator to the frozen bundle. The AI run starts before candidate
freeze; freeze precedes final evaluation; completion follows evaluation start.
Budgets cover the cumulative episode, not just the successful final call.
Author-baseline calibration, software controls and historical attempts are
explicit roles and cannot be admitted as AI receipts. Arbitrarily relabeling a
record cannot establish authenticity; the module cannot detect forged evidence.

`summary` emits four separate cells and a task count of one for a valid bundle.
Missing cells stay unknown. It rejects duplicate cell receipts rather than
selecting a favorable attempt, and rejects reuse of run/trace/exposure/freeze/
evaluation provenance across information conditions. `paired_metadata_admitted`
requires admissible receipts for both conditions, but is still not a scientific
success score. Repeated-run aggregation and contamination assessment require a
separately frozen protocol; this version does not invent such an analysis.

## Reviewed adoption contract

The integration owner can adopt this additively, one reviewed task at a time:

1. Preserve its task ID, all historical task files, `improvement.v1.json`, existing
   baseline calibration and provenance, exposed-data history and scientific
   holds. Reinspect the current original scientific target and its complete
   required finding panel. Do not automatically promote old reconstruction
   scores or infer tolerance from an existing loose grader.
2. Author `reproduction.v1.json` using the independent reproduction schema. Copy
   original factual anchors only when verified by the current source review.
   Preserve unknown values as null and unresolved criteria as unresolved. A new
   reproduction contract does not require declaring an improvement endpoint
   eligible. A source or execution hold applies wherever it is scientifically
   relevant, regardless of outcome name.
3. Author `outcomes.v1.json` with the unchanged task identity, exact reproduction
   and improvement digests, and separately specified or unresolved pairing
   protocols. Use authentic immutable manifest hashes only. No existing contract
   is assumed to supply a complete paired participant boundary merely because
   its software checks pass.
4. Add optional registry/catalog descriptors for these two new files under the
   existing task. Keep the current improvement descriptor intact. Store outcome
   eligibility, condition availability, source preparation, executable runtime,
   software controls, author calibration and AI performance as separate fields.
   Register substantive evaluator/program components under the same task;
   contract descriptors are not extra components or benchmark counts.
5. Update a later CLI/reporting surface to validate the new contracts and display
   four cells with unknown outcomes before genuine runs. Enroll these bounded
   tests through the framework's normal test discovery. No bulk historical result
   conversion is authorized by this implementation.
6. Only a subsequently authorized authentic AI execution can produce a new
   receipt. Verify complete original data/panel, allowed observations, trace,
   actual candidate freeze, runnable submitted analysis, independent execution,
   granular source-native outputs, actual evaluator output and cumulative usage
   outside this metadata layer. Preserve the raw result, provenance and any
   failure. Printed table or categorical claim agreement alone is insufficient.

This is intentionally separate from the current PR179 source integration. It
adds no registry/catalog/CLI edits and migrates none of the 117 paper tasks.
Existing improvement/v1 remains truthful and its scalar limitations remain
visible. In particular, SMC-RNN's two original proposal arms and all their
required companion metrics must not be collapsed into a single winning scalar.
A future reproduction contract would represent the full required vector as
distinct findings; any still unresolved dataset linkage, tolerance, uncertainty
or temporal-access enforcement remains a blocker. An operator author calibration
for that task never populates either AI condition.

## Verification boundary

`tests/framework/test_paper_reproduction.py` uses explicitly invented fixtures
only. It exercises independent eligibility, one-task/four-cell reporting,
cross-paper and cross-target splicing, full-panel omission, invalid units and
aggregation, decimal tolerance boundaries, interval containment, categorical
uncertainty, provenance/condition/freeze/budget mismatches, missing code, duplicate
receipts, aggregate-copy refusals, independent analysis/output verification and
historical/calibration rejection. The numerical controls include a tiny-target
case that would incorrectly match if absolute Decimal differences were rounded
by the ambient precision context. These are software controls; no
authentic data, scientific inference or model run is performed.
