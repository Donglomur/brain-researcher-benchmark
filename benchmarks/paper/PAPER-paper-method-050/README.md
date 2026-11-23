# Density-based longitudinal neuron tracking in high-density electrophysiological recordings

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-050`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Design ready
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
| Improvement | Paper data | design\_ready | unresolved | unresolved | Unknown |
| Improvement | Paper data author code | design\_ready | unresolved | unresolved | Unknown |

Author-baseline replay and historical reconstruction attempts retain their original scopes. They are not promoted to qualified AI reproductions or improvements by these contracts.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** design\_ready. The source provides a numerical original tracking-duration endpoint and independent matching-quality checks, supporting an improvement design. Exact Figure5 population/session identities, native method parity, quality-reference artifacts and a justified decision rule remain incomplete. Longer tracks alone can be produced by over-merging and never suffice for success.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 31438 bytes; SHA-256 `7fbb6cc86518cf911a0556a5040b4bd7175e37fb38f6ca00571e26ca42b41d9f`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Converts pinned spikeInfo HDF5 references into numeric arrays and computes paired full-population tracking-yield/PETH diagnostics with complete declared unit and animal accounting. Native schema/time units, real animal grouping, UnitMatch half-waveforms, PETH exclusion from every matching path, Figure 5 day/rate/three-method comparisons, true identity labels, protected lineage and scientific qualification remain open. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Figure5 joint sort v1](implementations/figure5-joint-sort-v1) — Reviewed source component.
  Scope: Figure 5H/I joint-sort fidelity computation over complete full-session tracking assignments, preserving source-included unit pairs and separate precision and recall. Joint-sort agreement is an indirect reference; authentic population identity, original executions, ambiguous mapping, statistical parity, reproduction and improvement remain unresolved.
- [Figure5 peth v2](implementations/figure5-peth-v2) — Reviewed source component.
  Scope: Figure 5E PETH fidelity component. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://doi.org/10.1016/j.patter.2026.101590)
- [Code](https://doi.org/10.5281/zenodo.20019488)
- [Code](https://doi.org/10.6084/m9.figshare.30596258.v2)
- [Code](https://github.com/jiumao2/pyDANT)
- [Code](https://github.com/jiumao2/pyDANT/blob/96060c1dd816181f32f089aaa686801aeae821bb/pyDANT/Preprocess.py)
- [Code](https://pmc.ncbi.nlm.nih.gov/articles/PMC13494646/)
- [Code](https://raw.githubusercontent.com/jiumao2/pyDANT/96060c1dd816181f32f089aaa686801aeae821bb/LICENSE)
- [Code](https://raw.githubusercontent.com/jiumao2/pyDANT/96060c1dd816181f32f089aaa686801aeae821bb/README.md)
- [Paper](https://doi.org/10.1016/j.patter.2026.101590)
- [Source](https://zenodo.org/records/20019488)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
