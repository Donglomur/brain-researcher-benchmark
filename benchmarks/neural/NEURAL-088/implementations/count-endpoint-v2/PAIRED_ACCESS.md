# Complete paired direct/program count assessment

`paired_access.py` adds an operator-only comparison of two candidate attempts, `direct_observation` and `frozen_program`, on the same declared complete historical panel. This addresses a different question from the existing candidate-versus-fixed-reference score: whether the direct and program attempts differ when the supplied case universe and declared information are matched. It does not deliver observations, execute either participant, or enforce tool restrictions.

The comparison preserves the current revised count endpoint in `scorer.py`: a frozen positive floor, positive sampling weights within each presynaptic neuron, equal weighting of presynaptic neurons, absolute anatomy-plus-in-vivo Poisson deviance primary, independent fixed-reference contrasts, and a descriptive candidate self-contrast. It does not recover or replace the absent historical grader. The 6,691 pairs and 21 presynaptic units are required cardinalities from the historical declaration; **matching those counts cannot authenticate the original identities**. The operator must separately recover and freeze the actual historical roster, materialization, functional mapping, eligibility and split. Arbitrary generated rosters passing these controls are not empirical panels.

## Operator interface

`compare(protocol, submissions, load_private_counts)` is the Python entry point. The protocol contains exactly `rows`, `rate_floor`, `fixed_reference_views` (all with the unchanged `scorer.py` schemas) and `information_bindings`. The latter is an operator-supplied record of information available to each attempt:

```json
{
  "direct_observation": {
    "anatomy": {"query_observations_sha256": "<64 lowercase hex characters>", "fit_validation_exposure_sha256": "<64 lowercase hex characters>"},
    "anatomy_plus_in_vivo": {"query_observations_sha256": "<64 lowercase hex characters>", "fit_validation_exposure_sha256": "<64 lowercase hex characters>"}
  },
  "frozen_program": {
    "anatomy": {"query_observations_sha256": "<same anatomy observation digest>", "fit_validation_exposure_sha256": "<same anatomy exposure digest>"},
    "anatomy_plus_in_vivo": {"query_observations_sha256": "<same joint observation digest>", "fit_validation_exposure_sha256": "<same joint exposure digest>"}
  }
}
```

These placeholders are not accepted digests. Freeze the query observation bytes and the complete permitted fit/validation information—including demonstration labels and instructions that disclose scientific information—before attempts. A digest must identify the complete payload or a canonical manifest with content hashes and order, not a filename alone. Each mode must have the same two bindings for a given information view. Anatomy and joint information views may differ. Receipts are trusted operator declarations, not participant assertions; this evaluator does not hash payloads, verify delivery logs, detect hidden information, establish freeze chronology, or audit that those payloads exclude targets and endpoint IDs. The report explicitly labels matching bindings `operator_declared_equal_not_delivery_attested`. Equal hashes alone never establish a fair experimental comparison.

`submissions` maps the exact two mode names to the ordinary complete paired-view prediction object. No endpoint IDs, targets, programme source or information receipts belong in participant prediction rows. Both views from both modes must have one finite nonnegative mean for every roster edge. Both modes are validated before the target callback runs once; a malformed mode produces `invalid_submission`, zero private reads and no scores for either mode. Operator input errors raise. The targets are then shared in memory across both ordinary endpoint evaluations; the nested `private_callback_invocations` fields refer to these in-memory callbacks, while the outer count records actual private loader calls.

The result retains both absolute endpoint reports and reports `direct_minus_program` for each information view and presynaptic neuron. A positive difference means lower program loss; negative and zero results remain signed. The joint-view primary difference compares the unchanged joint-view primary endpoints. This is a paired descriptive contrast within one selected mouse, not a confidence interval or animal-level replication. If either mode has unsupported arithmetic, the comparison is `valid_unscorable_arithmetic` and all cross-mode contrasts are null; no successful subset is ranked.

```sh
python3 -I -B paired_access.py --protocol /operator/paired-protocol.json \
  --submissions /operator/direct-and-program.json --targets /operator/counts.json \
  --output /operator/paired-report.json
```

All paths are placeholders; keep real protocols, identities, references, targets and reports outside participant mounts and public Git. Exit 0 means arithmetic completed; exit 2 denotes invalid submission or unsupported arithmetic. `scorer.py` remains a required sibling dependency pinned in `PAIRED_SOURCES.json`. Canonical protocol hashing identifies supplied settings but does not certify a pre-query freeze.

## Generated controls and remaining limits

Run `NEURAL088_TEST_TMP=/owned/parent/scratch python3 -I -B test_paired_access.py` in this directory. The owned parent must already exist; the test creates the scratch leaf if absent and rejects a symlink leaf. Its path is passed explicitly to the generated CLI fixture's temporary directory, because some host Python launchers override `TMPDIR`. The control logs its actual task-local fixture directory and removes that fixture on exit; the explicit scratch leaf remains available to the owner. Hosted CI should bind `NEURAL088_TEST_TMP` to its owned artifact directory. Controls construct 6,691 generated pairs across 21 generated presynaptic IDs. They exercise hand-calculated positive, negative and null contrasts, unequal group sizes/weights, shuffled key order, malformed mode outputs, whole-panel requirements, mismatched observation/exposure bindings, a single private read, target support errors, unsupported arithmetic, and the real CLI's refusal to open an absent target file for invalid modes. They establish software behavior, not a scientific result.

Actual observation preparation, direct response collection, program building/execution, no-tools enforcement, equal compute budgets, independent reference fitting, historical cohort identity, source eligibility and leakage review remain unresolved. A measured functional correlation is processed neural information, not raw-neural interpretation. No authentic neural inputs, private targets, models or scientific runs were used to develop these controls.
