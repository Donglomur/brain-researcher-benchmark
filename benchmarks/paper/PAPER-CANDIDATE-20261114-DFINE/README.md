# Causal and noncausal latent inference under missing neural observations

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-CANDIDATE-20261114-DFINE`
- **Track:** Paper research
- **Registration:** Expansion draft
- **Declared specification status:** Source unresolved
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
| Improvement | Paper data | source\_unresolved | unresolved | unresolved | Unknown |
| Improvement | Paper data author code | source\_unresolved | unresolved | unresolved | Unknown |

Author-baseline replay and historical reconstruction attempts retain their original scopes. They are not promoted to qualified AI reproductions or improvements by these contracts.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** source\_unresolved. The original grid-reaching missing-observation experiment has an ordered behavior-correlation endpoint, but its exact curve values, historical ratio grid, session-file/fold identities and masking realizations are not recovered. Methods resolves the retained-versus-dropped ambiguity: rho is retained observations. The existing numerical component and a newly grouped error curve cannot substitute for the Figure 7e and Extended Data 6e–f paper baseline.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 11335 bytes; SHA-256 `c6b1f4006189984a3212e70ce9db89278ff0e0a08fa60ac23bb754109a9b0548`.
- [Registration and provenance](../../../docs/provenance/registrations/expansion-20261114-v11/registry.json)

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Publication correction scope](docs/correction-status.md)
- [inference source evidence](docs/inference-source-evidence.json)
- [inference source reconciliation](docs/inference-source-reconciliation.md)

## Implementation artifacts

- [Missing observation](implementations/missing-observation) — Calibration only.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/ShanechiLab/torchDFINE)
- [Data](https://zenodo.org/records/3854034)
- [Paper](https://www.nature.com/articles/s41551-023-01106-1)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
