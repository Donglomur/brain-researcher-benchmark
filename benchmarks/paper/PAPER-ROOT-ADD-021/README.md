# Developmental relationships between the human alpha rhythm and intrinsic neural timescales are dependent on neural hierarchy

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-ROOT-ADD-021`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Ineligible
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Separate paper outcomes

The current definition supports two independent outcomes: recreate the original findings and exceed them on the same task. Each uses matched paper+data and paper+data+author-code conditions. Contract eligibility and declared protocol availability do not establish a delivered runtime or scientific result.

- [Original-finding reproduction contract](reproduction.v1.json)
- [Paired outcome protocols](outcomes.v1.json)
- [Preserved definition before dual outcomes](historical/task.pre-outcomes.v1.json)

| Outcome | Information condition | Endpoint eligibility | Protocol status | Declared availability | Scientific outcome |
| --- | --- | --- | --- | --- | --- |
| Reproduction | Paper data | source\_unresolved | unresolved | unresolved | Unknown |
| Reproduction | Paper data author code | source\_unresolved | unresolved | unresolved | Unknown |
| Improvement | Paper data | ineligible | unresolved | unresolved | Unknown |
| Improvement | Paper data author code | ineligible | unresolved | unresolved | Unknown |

Author-baseline replay and historical reconstruction attempts retain their original scopes. They are not promoted to qualified AI reproductions or improvements by these contracts.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** ineligible. Ineligible for the registered developmental association task. Age/region effects in alpha frequency and intrinsic timescales are descriptive cross-sectional relationships. Increasing their R², significance or effect magnitude would not establish a better biological estimate; the local participant-held-out prediction scorer introduces a different task.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 12293 bytes; SHA-256 `a8b753ca5acc78fac04263768ab751fe93be8d9f229b6a930b54802aa8c0b6e0`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Processes supplied parameter tables with fit QC, grouped Gaussian smoothing, participant/region age and hierarchy statistics, and separate participant-held-out prediction errors. It leaves supplied INT unchanged; authentic 13-participant coverage, native ECoG/FOOOF fitting, historical fork identity, knee-to-INT and alpha-definition conflicts, source-code rights, protected assessment and scientific qualification remain open. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Spectral smoothing v1](implementations/spectral-smoothing-v1) — Reviewed source component.
  Scope: Paired spectral smoothing. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/jtmiles/PAF_INT_neurodev)
- [Paper](https://doi.org/10.1152/jn.00435.2025)
- [Source](https://zenodo.org/records/16954184)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
