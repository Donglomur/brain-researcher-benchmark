# EEG-based brain-computer interface enables real-time robotic hand control at individual finger level

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-signal-add-017`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 14860 bytes; SHA-256 `63d23b0d71a7dfceeaa48db2c0df2afe8b1097cfa3056e631285fe18cd63f8ce`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Task implementation.
  Scope: Complete frozen selected numeric-export roster to source-aligned finger-EEG trials/windows, chronological calibration routing, target-free packets, a train-only prospective spectral reference and hard-vote trial/participant metrics with paired uncertainty. Authentic MAT conversion and complete source population, native TensorFlow EEGNet preprocessing/fine-tuning, protected numerical references, artifact controls, source rights/resources and scientific qualification remain held. Recorded replay does not reproduce closed-loop human feedback adaptation.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/bfinl/Finger-BCI-Decoding)
- [Paper](https://www.nature.com/articles/s41467-025-61064-x)
- [Source](https://figshare.com/articles/dataset/29104040)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
