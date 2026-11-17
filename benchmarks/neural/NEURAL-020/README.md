# Somatosensory population co-smoothing

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-020`
- **Track:** Neural-data understanding
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 16329 bytes; SHA-256 `8b922ac0214da6a1cb1ca5c0320cab90aaf6dab0e51f8ce44a552b0ecfcc718a`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Task implementation.
  Scope: Prepares the complete declared 826-trial/65-unit Area2 training-asset tensor packet, scores active/perturbed Poisson co-bps, and provides training-mean and source-derived smoothing controls. Native NWB conversion, mask/condition authenticity, prospective condition-transfer scope, authentic reference performance and protected scientific admission remain unqualified; portable byte-pinned upstream metric tests are engineering evidence only.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Source](https://api.dandiarchive.org/api/assets/ded26b6c-418d-43f5-8a37-dfd072c2dbd4/)
- [Source](https://api.dandiarchive.org/api/dandisets/000127/versions/0.220113.0359/)
- [Source](https://dandiarchive.org/dandiset/000127/0.220113.0359)
- [Source](https://doi.org/10.7554/eLife.48198)
- [Source](https://github.com/neurallatents/nlb_tools)
- [Source](https://raw.githubusercontent.com/neurallatents/nlb_tools/42f8410b88e12db136910fa2f888b025ea0aa2ae/nlb_tools/evaluation.py)
- [Source](https://raw.githubusercontent.com/neurallatents/nlb_tools/42f8410b88e12db136910fa2f888b025ea0aa2ae/nlb_tools/make_tensors.py)
- [Source](https://raw.githubusercontent.com/neurallatents/nlb_tools/42f8410b88e12db136910fa2f888b025ea0aa2ae/nlb_tools/nwb_interface.py)
- [Source](https://raw.githubusercontent.com/neurallatents/nlb_tools/main/README.md)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
