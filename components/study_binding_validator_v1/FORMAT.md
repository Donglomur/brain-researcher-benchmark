# Binding format v1

All object fields in [binding.schema.json](binding.schema.json) are required; unexpected fields, duplicate JSON keys/IDs, nonfinite numbers and common unresolved placeholders are rejected. `null` is accepted only for explicitly inapplicable branches. The exported schema describes shape; `validate_study.py` also implements ID/reference, pin, design, budget, exposure and denominator constraints. Its small schema checker supports only the vocabulary in its own schema, not arbitrary third-party schemas. The `x-bound-text` extension rejects unresolved placeholders.

The envelope uses `format: neurobench.paired-study-binding.v1`, `state: BOUND_DESCRIPTION_NOT_EXECUTABLE`, `track: paper|neural`, and `record_kind: study_description|generated_control`. Execution selection, scientific qualification and submission readiness must all be false; task count delta must be zero. A generated-control declaration must never be relabeled as empirical evidence.

Source template pins:

| Track | Source template | SHA-256 |
| --- | --- | --- |
| paper | `docs/neuroscience-benchmarks/study-design-v1/paper.template.json` | `fc999a0090875b8b0ce07d2f503b8e4cace7070bda2c614f4528323be586c575` |
| neural | `docs/neuroscience-benchmarks/study-design-v1/neural.template.json` | `ebc306ef4ecbf65d418c58c0ad2b1ab8d7582aa47fbe1a85a5ba4d618ddc3e6e` |

## Collections and joins

| Section | Required meaning |
| --- | --- |
| `artifacts` | Map from artifact ID to role, locator/positive byte count/SHA-256, privacy and a declared distinct author/reviewer plus review-evidence pin. Locators are opaque URI strings; none are opened. |
| `tasks` | Task ID, pinned revision artifact, source family and individually named endpoints with metric, direction and units. Endpoint IDs are globally unique and not pooled across scales. |
| `case_manifests` | Exactly one complete inline roster per task and phase, with the task revision digest, case IDs, independent units, exposure units and dependence memberships. |
| `budget_profiles` | Named explicit hardware/measurement references; wall/CPU/GPU/memory/calls/input/output tokens; monetary cap, currency and pricing timestamp. Values are declarations, not enforced or estimated costs. |
| `arms` | Exact track-specific arms, common information and access policy, explicit code/tool/adaptation/frozen-policy roles and phase budget references. |
| `model_scaffolds` | Distinct model/scaffold revision pairs and identity-artifact references. |
| `assignments` | One row for every task × phase × model/scaffold × repeat × arm. Each row binds task/case revisions, pair ID, condition order and exactly its arm's phase budgets. A pair shares task, phase, case manifest, model/scaffold and repeat; condition order is a permutation. |
| `pairing` | Canonical assignment pin plus randomization, context/workspace/cache reset, model-identity, seed-limit and repeat-count-rationale declarations. Randomness itself is not verified. |
| `contrasts` | Intended ordered arm pairs, phase, explicit intervention, primary flag, all endpoint IDs and effect thresholds. The outer `assigned_pairs` is the all-task operational total for this phase. Each `endpoint_applicability` entry separately binds its owning `task_id`, contrast `phase`, exact applicable `assigned_pair_ids` and `assigned_pairs` denominator. Unrelated-task pairs are inapplicable, never failures for that endpoint. Missingness and analysis references must agree with global policies. |
| `analysis` | Complete primary/exploratory partition, independent units, exact case/group dependence membership, case→unit→task→family aggregation, separate endpoint reporting, uncertainty, multiplicity and review policies. Repeated runs are not independent units. |
| `corpus` | Prospective inclusion/exclusion, population and limitations, source families and explicit overlap edges/policy. At most one undirected edge per family pair; combine multiple relationships in its evidence declaration. Completeness of real-world overlaps is not established. |
| `exposure` | Inventory/access/overlap/training-history policies and exactly all declared exposure units. Protected confirmation requires final units declared unexposed and disjoint from earlier phases. Retrospective development permits exposed/unresolved units without a protected claim. |
| `failure_accounting` | All assigned runs retained; six fixed outcome classes; continuous missingness policy; blinded, bounded retry rules and explicit extra retry budget when applicable. Failure-class totals are not actual results. |
| `selection_and_stopping` | Frozen maximum attempt count, development-only candidate selection using the matched development budget, locked assessment, precision/safety/change policies; fixed design or explicit sequential rule/review and increasing looks ending at all primary pairs. |
| `track_policy` | Only the selected paper or neural branch is applicable; the other is null. Requires comparator/lock/cost/claim-policy references from the original design. |

Paper phases: `reproduction`, `improvement_development`, `improvement_confirmation`. The two required contrasts are `official_code_reproduction` and `official_code_end_to_end_improvement`. Each phase gets a distinct budget ID shared by both access arms; no unused reproduction allowance carries forward.

Neural phases: `development`, `assessment`. Required arms: `program_numerical`, `investigator_numerical`, `program_specialist`, `investigator_specialist`. Required contrasts: `live_given_numerical`, `live_given_specialist`, `specialist_given_program`, `specialist_given_investigator`. At least one mode contrast is primary. All cells share development and numerical assessment profile IDs. Numerical assessment allows zero LLM calls/input/output tokens; investigators additionally share a distinct positive LLM profile. Additional live cost is explicit, so this is not an equal-total-expenditure claim. Frozen policy and case-reset references do not themselves enforce isolation.

## Canonical inline pins

IDs require an exact ASCII token, hashes exactly 64 lowercase hexadecimal characters, currencies exactly three uppercase ASCII letters and timestamps exactly 20 ASCII characters. Trailing newlines or NUL characters are rejected by the executable shape checker and exported schema constraints. Opaque artifact locators require a URI scheme and nonempty whitespace-free suffix. This validates syntax, not the locator's existence or safety for another program.

For the generated two-task, two-repeat example, a contrast has four operational paired blocks, while each task-specific endpoint has exactly two applicable paired blocks. Every failure in those two stays in that endpoint's denominator; the other task's two blocks are not observations of that metric. All endpoint pair IDs, ownership, phases and counts are joined against the complete assignment matrix. Endpoint scales remain separate.

Use UTF-8 JSON with sorted object keys, no insignificant separators (`(',', ':')`), Unicode unescaped, finite numbers only, followed by one newline; preserve array order. `validate_study.canonical` implements this encoding. For each case manifest, hash exactly the object containing `task_id`, `task_revision_sha256`, `phase`, `cases`. For the assignment artifact, hash the complete `assignments` array. Store the encoded length and SHA-256 in the referenced artifact pin. This catches changed inline metadata, not altered external data. IDs in locators are not dereferenced or interpreted as filenames.

Failure classes are `infrastructure`, `invalid_submission`, `model_abstention`, `resource_exhaustion`, `scientifically_invalid`, `successful_valid_submission`, in that order. No failure disappears from the assigned denominator. Continuous missingness requires `predeclared_penalty`, `predeclared_model` or `bounds` with a policy reference. Any scientific choice of penalty/model/bounds, uncertainty, thresholds, primary claims or stopping rules must be made and reviewed independently of these generated controls.
