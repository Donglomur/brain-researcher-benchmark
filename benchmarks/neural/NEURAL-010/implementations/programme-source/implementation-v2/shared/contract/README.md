# Campaign exposure claims

This additive operator validator checks explicit exposure/freshness/generalization claims before a campaign is selected. It never launches a task, creates an RL split, merges task IDs or promotes readiness. The inspected central `tools/neurobench.py`, `tools/neurobench_condition.py` and shared seven-fold scheduler have no campaign-history/task-set admission. Existing exposure tooling builds a typed metadata index and warning documents. This is a scoped finding, not a claim about every external/task-specific execution service. Existing dispatchers are unchanged and do not automatically invoke this companion; the operator must explicitly use its result before selection.

The validator consumes the exact existing `exposure_audit.json` (466 typed edges, 70 cross-suite pairs, 200 canonical identities). It does not rebuild that index or treat its mixed relations as biological equivalence. Four selected task declarations add the two concrete checks that the generic graph alone cannot justify:

* NEURAL-023 public assessment neural counts are NEURAL-024 private future observations. Prior NEURAL-023 access contradicts a NEURAL-024 fresh-target claim. Concurrent NEURAL-023 inputs while executing NEURAL-024 are forbidden even when the claim is only exposed development. This is directional; no reverse velocity-target exposure is asserted.
* NEURAL-095 and NEURAL-096 share the exposed Haydn20161211 recording. A new-session/new-animal claim across them is contradicted.096 expressly excludes produced intervals and Go times; sharing neural observations is not asserted to reveal NEURAL-095’s behavioral targets. Both task identities remain distinct.

All four selected declarations explicitly concern exposed development material. A request for fresh targets is therefore contradicted, even if its declared task-access list is empty. Other tasks and other relations have incomplete evidence. Absence of an edge, a different URL, a shared paper, a stimulus-family label, or a connected path is never evidence of biological independence. Unsupported affirmative claims return `unresolved` and a nonzero status. The source has no affirmative independent-cohort certificate mechanism.

## Request ABI

An operator-authored strict JSON object has exactly `schema` and `evaluations`. Schema is `campaign_exposure_request_v1`. Each of 1–200 unique canonical task records has exactly:

```json
{
  "task_id": "NEURAL-024",
  "prior_access": ["NEURAL-023"],
  "concurrent_inputs": [],
  "claims": [{"kind": "fresh_targets", "against": []}]
}
```

The two access lists mean public task materials already available in this operator context, or proposed as concurrent inputs. They are not independently verified histories of a person, agent, model or checkpoint; a candidate-authored declaration is not an exposure attestation. Do not omit known exposure or invent a fresh context by relabeling it. Use separate requests only for genuinely separate, independently documented contexts; validation itself does not establish that separation. Own permitted task inputs are implicit, so the same task cannot occur in its concurrent-input list. Prior same-task access may be recorded.

Claim kinds are:

| Kind | Required comparison | Behavior |
|---|---|---|
| `development_only` | empty `against`; sole claim | Compatible only with a development interpretation and no known forbidden concurrent inputs. It certifies no freshness, causal access or readiness. |
| `fresh_targets` | empty `against` | Uses declared prior/concurrent access and exposed-task declarations. Never treats mere comparison as an actual access event. Unknown freshness remains unresolved. |
| `new_animal`, `new_session`, `independent_acquisition` | explicit nonempty `against` task IDs | Known shared biological identity contradicts the claim; otherwise unresolved. |
| `new_stimuli` | explicit nonempty `against` | Typed stimulus links are evidence leads, not verified intersections or disjointness; unresolved. |
| `new_paper` | explicit nonempty `against` | An exact shared declared paper locator contradicts a new-paper claim; otherwise unresolved. No biological implication is drawn. |

Claims are unique per record. Unknown tasks/fields/kinds, duplicate JSON keys or task IDs, nonfinite values and malformed structures refuse admission. All requested tasks remain distinct. The same source can support multiple valid development tasks.

## Supported invocation

From the repository root, after authenticating the reviewed source manifest and an exact current WORK snapshot:

```text
python3 -I -B authoring/delivery-20261105/common/campaign-exposure-contract-v1/validate.py --repo ABSOLUTE_REPOSITORY --request ABSOLUTE_OPERATOR_REQUEST.json --source-sha256 REVIEWED_SOURCE_MANIFEST_SHA256 --work-sha256 CURRENT_WORK_SHA256
```

The CLI captures metadata only. It authenticates this source closure, the frozen typed audit/generator, the current WORK bytes, and the selected descriptors/declaration bodies relevant to evaluated tasks, prior/concurrent access or explicit comparisons. Only four task declarations are currently specialized. A relevant changed selected source path or pin requires a reviewed successor; no stale declaration is silently applied. Unrelated WORK path updates are accepted with a caller-supplied fresh snapshot hash. There is no frozen global WORK content digest in this source. Other tasks retain unknown declaration status. It does not read descriptor-listed datasets, targets, keys, predictions, checkpoints or article bodies. The prior exposure graph is a pinned, non-exhaustive metadata snapshot; it does not become current biological identity evidence merely because WORK was checked.

One bounded JSON report goes to stdout. Exit 0 means only `compatible_development_selection`; exit 2 means one or more contradictory/unresolved claims or forbidden concurrent inputs; exit 1 means malformed/unbound input or resource refusal. An exit 0 is not permission to execute a task or expand its input/mount allowlist. Every selected task still enforces its own permitted inputs; this companion checks the documented cross-task exposure claims, not all runtime input restrictions. The caller must observe the real exit and complete report; truncated output is not admission. No report or temporary file is created by the CLI. Maximum metadata read precharge 1,500,000 B, request 131,072 B and complete report 1,000,000 B; source capture uses ordinary unlinked single-link files and before/after identity checks, under immutable operator custody. These checks do not lock out future writers or prove completeness of declared history.

`EXAMPLES.json` contains illustrative requests only; it selects no evaluation. Generated checks use invented graph/files plus the pinned small task-declaration metadata. They execute no actual evaluation, candidate, neural/scientific code or target access.
