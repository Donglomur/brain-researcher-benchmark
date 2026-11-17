# Temporal integration in human auditory cortex is predominantly yoked to absolute time

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-FIND-024`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** source\_unresolved. Source-native rebinding identifies the original cross-split prediction of fixed untied integration-window estimates: tied predictor versus opposite-split untied target has reported Spearman correlation 0.668. Exact split identities, target arrays and aggregation are unresolved. Tied/tied reliability 0.716 is not truth accuracy and cannot be used when a candidate may alter both sides.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 18351 bytes; SHA-256 `4e5697aafca6c9418b8ee9d688db578f53baa3359ec4098ce16e01c0721a10f4`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Prospective segment-aligned cross-context correlations and repeated-presentation noise ceilings from electrode timecourses, with pinned NPZ input and descriptive participant-balanced summaries. Authentic MATLAB conversion/cohort identities, exact native TCI dependencies and numeric parity, gamma-window refitting, absolute-time-versus-structure inference, rights and protected references remain held. This is partial canonical coverage; scientific qualification is unknown. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/snormanhaignere/time-vs-structure)
- [Paper](https://www.nature.com/articles/s41593-025-02060-8)
- [Source](https://drive.google.com/drive/folders/1r7E4fQatSBvd5eGYgdr3s8E72dTuL568)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
