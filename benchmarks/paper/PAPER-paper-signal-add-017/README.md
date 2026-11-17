# EEG-based brain-computer interface enables real-time robotic hand control at individual finger level

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-signal-add-017`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** source\_unresolved. The registration scopes recorded offline decoding, which is ordered, but its exact source-paper offline baseline and original folds/session mapping are unrecovered. The published online fine-tuned human-control headline is incompatible with replay scoring and cannot be the offline victory threshold.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 15633 bytes; SHA-256 `74380d9eadbd39670727702cdfe2e6a76d1336ac8c94605be0f680e488db65e8`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Complete frozen selected numeric-export roster to source-aligned finger-EEG trials/windows, chronological calibration routing, target-free packets, a train-only prospective spectral reference and hard-vote trial/participant metrics with paired uncertainty. Authentic MAT conversion and complete source population, native TensorFlow EEGNet preprocessing/fine-tuning, protected numerical references, artifact controls, source rights/resources and scientific qualification remain held. Recorded replay does not reproduce closed-loop human feedback adaptation. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/bfinl/Finger-BCI-Decoding)
- [Paper](https://www.nature.com/articles/s41467-025-61064-x)
- [Source](https://figshare.com/articles/dataset/29104040)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
