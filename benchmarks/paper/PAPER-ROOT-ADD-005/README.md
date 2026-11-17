# Distributed representations of behaviour-derived object dimensions in the human visual system

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-ROOT-ADD-005`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Separate paper outcomes

The current definition supports two independent outcomes: recreate the original findings and exceed them on the same task. Each uses matched paper+data and paper+data+author-code conditions. Contract eligibility and declared protocol availability do not establish a delivered runtime or scientific result.

### Current selected paper endpoint

**Disposition:** source\_unresolved.

This version selects an exact author-reported computational result as the primary benchmark endpoint. The broader biological finding and prior contracts retain their original scope. The source selection does not establish runnable delivery, an AI evaluation, reproduction or improvement; both access conditions remain uninstantiated.

- [Selected current improvement contract](primary-endpoint-v1/improvement.v1.json)
- [Authenticated endpoint selection](primary-endpoint-v1/selection.v1.json)
- [Reviewed endpoint selection authority](../../../docs/provenance/paper-primary-endpoint-selections.v2.json)

**Remaining reproduction/source limits:**

- Authenticate original participant, repeated-trial, image, row/session, voxel and mask identities and complete artifact hashes. The 8740 unique images per participant are not the number of response rows.
- Prove original unshuffled 12-fold source row blocks equal twelve complete original sessions without sorting or repairing their order. Original folds, repetitions and full masks cannot be replaced by new category or image-family holdouts.
- Recover the original complete author per-fold prediction and correlation maps, source permutation identities/null outputs and Figure 2 noise-ceiling transformation/mask. Do not substitute pooled correlation, signed SSE/SST R2 or Figure 6 attribution medians.
- Authenticate the strongest relevant author comparator under the same 66-feature input task. Pinned intercept OLS is the recovered author route; numerical baseline, original run parity and any stronger same-endpoint author branch are not yet qualified.
- Freeze source-grounded map-level numerical agreement and a meaningful, complete-support improvement comparison with participant/session/stimulus dependence. No across-voxel scalar, universal margin, selective voxel subset or numerical tolerance is invented.
- Complete source-native production and independent verification of all original folds. The delivered archive scorer does not authenticate training exclusion, source provenance, Figure 2 conversion, permutation generation or submitted fitting.
- Authenticate common input/exposure manifests, official-code manifest, independently enforced paired execution and existing required resource/access accounting. Pairing protocols remain unresolved; no source/runtime/results are qualified.

- [Selected-endpoint reproduction contract](primary-endpoint-v1/reproduction.v2.json)
- [Paired outcome protocols](primary-endpoint-v1/outcomes.v1.json)
- [Preserved definition before dual outcomes](historical/task.pre-outcomes.v1.json)

| Outcome | Information condition | Endpoint eligibility | Protocol status | Declared availability | Scientific outcome |
| --- | --- | --- | --- | --- | --- |
| Reproduction | Paper data | source\_unresolved | unresolved | unresolved | Unknown |
| Reproduction | Paper data author code | source\_unresolved | unresolved | unresolved | Unknown |
| Improvement | Paper data | source\_unresolved | unresolved | unresolved | Unknown |
| Improvement | Paper data author code | source\_unresolved | unresolved | unresolved | Unknown |

Author-baseline replay and historical reconstruction attempts retain their original scopes. They are not promoted to qualified AI reproductions or improvements by these contracts.

## Retained predecessor improvement policy

This original contract preserves the predecessor scientific instructions and source scope. The selected primary policy above governs current improvement.

**Disposition:** source\_unresolved. The original ordered encoding task and author evaluation route are identifiable, but a comparable numerical source baseline with exact voxel masks, row/session alignment and aggregation has not been recovered. The existing nested image-family ridge evaluator changes the source split and cannot establish a same-task paper win.

- [Retained original improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 27596 bytes; SHA-256 `6a7daa8f8a142b48ba45c1947d8f832fa23744158af41d8843f8c044dc967193`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)
- [Pre-scope reproduction source role](docs/provenance/reproduction.pre-scope.role.json)
- [Preserved pre-scope reproduction declaration](docs/provenance/reproduction.pre-scope.v1.json)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Binds exact stimulus/voxel identities for all three declared THINGS-fMRI participants and runs prospective nested grouped ridge comparisons across 66 dimensions, category and shape predictors, reporting signed held-out metrics and predictive commonality. Native 12-session encoding / 30-dimension residual partition, exact category/shape recipes, authentic grouping/arrays, protected execution, rights and full-cohort resource/scientific qualification remain unresolved. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Source session scorer v1](implementations/source-session-scorer-v1) — Reviewed source component.
  Scope: Original session encoding score component. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/ViCCo-Group/dimension_encoding)
- [Paper](https://www.nature.com/articles/s41562-024-01980-y)
- [Source](https://figshare.com/articles/dataset/20492835)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
