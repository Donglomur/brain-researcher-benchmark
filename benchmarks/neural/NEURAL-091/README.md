# Visual tuning prediction in Neuropixels recordings

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-091`
- **Track:** Neural-data understanding
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 11330 bytes; SHA-256 `b42c6803c1aede42efe4f65e422494247b355b2dd2799e5817ef61d759cc2445`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Task implementation.
  Scope: Prepares exposure-aware Neuropixels exports with stimulus-family/repeat/time guards, computes train-only rate/state controls, and scores exact predictions with mouse-macro Poisson bits per spike. Authentic recording/presentation identity, SDK/NWB and clock compatibility, complete allowed stimulus inputs, protected execution, competent stimulus-transfer references, rights and scientific qualification remain held.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Source](https://brain-map.org/our-research/circuits-behavior/visual-coding)
- [Source](https://github.com/AllenInstitute/AllenSDK)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
