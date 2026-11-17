# Developmental relationships between the human alpha rhythm and intrinsic neural timescales are dependent on neural hierarchy

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-ROOT-ADD-021`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 13586 bytes; SHA-256 `a3e6b717fe4a94de97c1c87686e4cc37c696d1f457331cc6995faeea96987213`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Task implementation.
  Scope: Processes supplied parameter tables with fit QC, grouped Gaussian smoothing, participant/region age and hierarchy statistics, and separate participant-held-out prediction errors. It leaves supplied INT unchanged; authentic 13-participant coverage, native ECoG/FOOOF fitting, historical fork identity, knee-to-INT and alpha-definition conflicts, source-code rights, protected assessment and scientific qualification remain open.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/jtmiles/PAF_INT_neurodev)
- [Paper](https://doi.org/10.1152/jn.00435.2025)
- [Source](https://zenodo.org/records/16954184)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
