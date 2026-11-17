# Stabilizing brain-computer interfaces through alignment of latent dynamics

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-add-001`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Design ready
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Separate paper outcomes

The current definition supports two independent outcomes: recreate the original findings and exceed them on the same task. Each uses matched paper+data and paper+data+author-code conditions. Contract eligibility and declared protocol availability do not establish a delivered runtime or scientific result.

- [Original-finding reproduction contract](reproduction.v1.json)
- [Paired outcome protocols](outcomes.v1.json)
- [Preserved definition before dual outcomes](historical/task.pre-outcomes.v1.json)

| Outcome | Information condition | Endpoint eligibility | Protocol status | Declared availability | Scientific outcome |
| --- | --- | --- | --- | --- | --- |
| Reproduction | Paper data | source\_unresolved | unresolved | unresolved | Unknown |
| Reproduction | Paper data author code | source\_unresolved | unresolved | unresolved | Unknown |
| Improvement | Paper data | design\_ready | unresolved | unresolved | Unknown |
| Improvement | Paper data author code | design\_ready | unresolved | unresolved | Unknown |

Author-baseline replay and historical reconstruction attempts retain their original scopes. They are not promoted to qualified AI reproductions or improvements by these contracts.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** design\_ready. The original offline stability comparison has ordered, published task-specific medians: isometric force R²=0.91 across 380 Jango pairs and reaching cursor-velocity R²=0.78 across 132 Chewie pairs. This grounds a complete source-task design, not readiness. Original partitions/preprocessing, author replay, metric/CV correspondence, source rights, uncertainty and budgets remain unresolved. The illustrated Day0→Day95 R²0.88 is calibration evidence and cannot establish the complete original task.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 35204 bytes; SHA-256 `7b85c99f4eb7e2bf364e42e37b01d972a0397a0d0c9009b8980531468a644f89`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Implementation artifacts

- [Recovered operators](implementations/recovered-operators) — Calibration only.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Publisher panel metadata v1](implementations/publisher-panel-metadata-v1) — Reviewed source component.
  Scope: Original NoMAD monkey-panel metadata. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://datadryad.org/dataset/doi:10.5061/dryad.q83bk3jtp)
- [Code](https://doi.org/10.5061/dryad.cvdncjt7n)
- [Code](https://github.com/snel-repo/nomad)
- [Code](https://github.com/snel-repo/nomad/blob/aa3c8faadf053d0b22160458854c076dcb13eb7e/demo/demo.ipynb)
- [Code](https://github.com/snel-repo/nomad/blob/aa3c8faadf053d0b22160458854c076dcb13eb7e/demo/utils.py)
- [Code](https://github.com/snel-repo/nomad/blob/aa3c8faadf053d0b22160458854c076dcb13eb7e/lfads_tf2/train_lfads.py)
- [Code](https://github.com/snel-repo/nomad/blob/aa3c8faadf053d0b22160458854c076dcb13eb7e/nomad/run_align.py)
- [Code](https://raw.githubusercontent.com/snel-repo/nomad/aa3c8faadf053d0b22160458854c076dcb13eb7e/LICENSE)
- [Code](https://raw.githubusercontent.com/snel-repo/nomad/aa3c8faadf053d0b22160458854c076dcb13eb7e/README.md)
- [Code](https://www.nature.com/articles/s41467-025-59652-y)
- [Paper](https://www.nature.com/articles/s41467-025-59652-y)
- [Source](https://datadryad.org/api/v2/versions/257783/files)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
