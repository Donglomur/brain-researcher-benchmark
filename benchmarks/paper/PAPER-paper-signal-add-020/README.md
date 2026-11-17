# Separable neural signals for reward and emotion prediction errors

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-signal-add-020`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Ineligible
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Success:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule.

**Disposition:** ineligible. The registered task estimates source ERP–prediction-error associations. Its coefficients and contrasts have no monotone scientific improvement direction. The existing coefficient-to-reference RMSE rewards numerical reconstruction; a proposed held-out choice log-loss task would change the endpoint and split.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition (calibration only)](historical/task.pre-improvement.v1.json)

Existing reproduction graders and pilot scores remain calibration evidence. They cannot establish paper improvement. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 14398 bytes; SHA-256 `a950ac57acff6e3dfe5d1952046a6a7808cc83b5e929ef3184dfdaa2d56f5179`.
- [Preserved legacy runtime declaration](implementations/registered-runtime/manifest.json)
- [Legacy declaration package](implementations/registered-runtime)

This preserved declaration is lineage, not current execution qualification. Its historical paths may describe the source snapshot.

## Implementation artifacts

- [Registered runtime](implementations/registered-runtime) — Calibration only.
  Scope: This is the source package currently selected by the published catalog; current does not assert executable/scientific qualification. This retained scoring facade requires 2 source or input dependencies absent from the public baseline. Correcting its repository locator does not make it runnable from this checkout alone. This limit does not apply automatically to sibling implementations of the task. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/jpheffne/2025_epe_eeg)
- [Paper](https://www.nature.com/articles/s41467-025-63135-5)
- [Source](https://github.com/jpheffne/2025_epe_eeg/tree/4f5767df1516e0ec3c234d51ba36e4b741eb60e8/data/clean)
- [Source](https://osf.io/ap4x7/)
- [Source](https://zenodo.org/records/15739722)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
