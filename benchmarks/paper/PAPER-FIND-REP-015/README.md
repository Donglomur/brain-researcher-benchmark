# Cerebellar neural populations orchestrate dopamine reward signaling with single-trial precision

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-FIND-REP-015`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Success:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule.

**Disposition:** source\_unresolved. The source paper includes an ordered trial-held-out SVM reward-outcome classification task (Supplementary Fig. 9 and Methods), which the authorized overhaul can adopt as the original reward-detection comparison route. Exact split identities, per-unit/cohort aggregation and published numeric SVM results remain unrecovered. The existing literal F2/F3 reconstruction metric is incompatible with an improvement reward, but that does not disqualify the source-native SVM task.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition (calibration only)](historical/task.pre-improvement.v1.json)

Existing reproduction graders and pilot scores remain calibration evidence. They cannot establish paper improvement. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 58721 bytes; SHA-256 `70768796c90406b86b49c0cf38128a55ffe08aa4f1de64ba184a9fffb00b89ba`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Implementation artifacts

- [Full reconstruction](implementations/full-reconstruction) — Calibration only.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://zenodo.org/records/19331923)
- [Paper](https://www.nature.com/articles/s41467-026-75371-4)
- [Source](https://zenodo.org/records/19345221)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
