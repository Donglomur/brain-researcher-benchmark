# Encoding of cerebellar dentate neuron activity during visual attention in rhesus macaques

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-FIND-ADD-005`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 14145 bytes; SHA-256 `2c5c8595ac6e80527bbab09f8780b38923c008bfc45c738fe034dd3b80daa841`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Task implementation.
  Scope: Prospective within-cell dentate encoding from exported spike/event/eye/history trials through source-informed binning and event kernels, paired ridge Poisson models, nested contiguous trial-block fitting and held-out likelihoods. The implemented contrast is gap-direction encoding conditional on event/eye/history/saccade terms; direct attention and behavioral decoding remain unresolved. Authentic MAT/population reconciliation, native hierarchical MATLAB model parity, figure targets, protected evaluation and scientific qualification remain held.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/sakoay/ErasmusAttn_2020)
- [Paper](https://elifesciences.org/articles/99696)
- [Source](https://datadryad.org/dataset/doi:10.5061/dryad.1rn8pk14s)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
