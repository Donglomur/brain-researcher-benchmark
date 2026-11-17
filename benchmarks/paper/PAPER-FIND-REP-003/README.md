# Mouse sensorimotor cortex reflects complex kinematic details during reaching and grasping

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-FIND-REP-003`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Success:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule.

**Disposition:** source\_unresolved. Figure 5 defines a defensible original 24-joint decoding task and author code fixes its variance-explained calculation, but the published per-joint/per-mouse numerical baseline has not been recovered or rerun. The current scorer compares to a newly authored phase template and aggregates differently from the paper; beating that template is not beating the paper.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition (calibration only)](historical/task.pre-improvement.v1.json)

Existing reproduction graders and pilot scores remain calibration evidence. They cannot establish paper improvement. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 24331 bytes; SHA-256 `fbb0ea2cdb36c8ee7f4b16175c1a156da26e82fe691c8cf6933c0a39a591ceec`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Authentic delivery v1](implementations/authentic-delivery-v1) — Calibration only.
  Scope: Calibration/preparation only; never active same-task paper-improvement success. Delivers all 3304 released trials from two mice/eight sessions in distinct paper/data and official-code conditions, independently checks literal Figure 1H source arithmetic, and admits/freezes/grades complete JSON or MATLAB submissions. Physical cue origin and article-percentage reconciliation remain unresolved; no custom mean-delay substitute, whole-paper/decoding completion, improvement result or scientific qualification is claimed. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Calibration/preparation only; not active same-task paper-improvement success. Retains normalized decoding for ten declared M1/S1 sessions and the literal optogenetic source histogram. Added independent exact-file admission verifies all 3304 optogenetic trials and native event-minus-waterTime identities without reanchoring. Physical cue-clock interpretation, native ten-session neural/PCA/ROI model parity, protected provisioning, intervention trajectories and full-paper/scientific qualification remain unresolved. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/kaufmanlab/GSK26-public)
- [Paper](https://doi.org/10.7554/eLife.106270.3)
- [Source](https://figshare.com/articles/dataset/Data_from_Mouse_sensorimotor_cortex_reflects_complex_kinematic_details_during_reaching_and_grasping_eLife_2025/28326998)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
