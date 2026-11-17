# Developmental relationships between the human alpha rhythm and intrinsic neural timescales are dependent on neural hierarchy

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-ROOT-ADD-021`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Ineligible
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Success:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule.

**Disposition:** ineligible. Ineligible for the registered developmental association task. Age/region effects in alpha frequency and intrinsic timescales are descriptive cross-sectional relationships. Increasing their R², significance or effect magnitude would not establish a better biological estimate; the local participant-held-out prediction scorer introduces a different task.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition (calibration only)](historical/task.pre-improvement.v1.json)

Existing reproduction graders and pilot scores remain calibration evidence. They cannot establish paper improvement. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 11535 bytes; SHA-256 `e0782275171190618dec483f1a09eb8d76456f6e228d2984a2a1dd99a4303ba9`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Processes supplied parameter tables with fit QC, grouped Gaussian smoothing, participant/region age and hierarchy statistics, and separate participant-held-out prediction errors. It leaves supplied INT unchanged; authentic 13-participant coverage, native ECoG/FOOOF fitting, historical fork identity, knee-to-INT and alpha-definition conflicts, source-code rights, protected assessment and scientific qualification remain open. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/jtmiles/PAF_INT_neurodev)
- [Paper](https://doi.org/10.1152/jn.00435.2025)
- [Source](https://zenodo.org/records/16954184)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
