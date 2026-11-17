# Stabilizing brain-computer interfaces through alignment of latent dynamics

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-add-001`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Design ready
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Success:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule.

**Disposition:** design\_ready. The original offline stability comparison has ordered, published task-specific medians: isometric force R²=0.91 across 380 Jango pairs and reaching cursor-velocity R²=0.78 across 132 Chewie pairs. This grounds a complete source-task design, not readiness. Original partitions/preprocessing, author replay, metric/CV correspondence, source rights, uncertainty and budgets remain unresolved. The illustrated Day0→Day95 R²0.88 is calibration evidence and cannot establish the complete original task.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition (calibration only)](historical/task.pre-improvement.v1.json)

Existing reproduction graders and pilot scores remain calibration evidence. They cannot establish paper improvement. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 35630 bytes; SHA-256 `01c8e1107897c06d31968b2752d26dde3898c08946d5e5f8d22046a48dbedffc`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Implementation artifacts

- [Recovered operators](implementations/recovered-operators) — Calibration only.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

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
