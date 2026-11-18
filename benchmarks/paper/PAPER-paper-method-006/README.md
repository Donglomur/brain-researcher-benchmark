# Spike sorting with Kilosort4

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-006`
- **Track:** Paper research
- **Registration:** Original canonical specification
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

**Disposition:** source\_unresolved. The original sorting problem has an ordered recovery endpoint, but the exact published Kilosort4 score vectors, publication invocation and metric implementation are unresolved. The paper checks 40 neighboring units whereas v4.0.2 bench.py checks 20; the registered exhaustive one-to-one prospective policy changes the comparison and cannot certify a paper win.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 55908 bytes; SHA-256 `a75c674c7f073564cc994ad6178db6052ad36f243c7f4a8fcc95de2b18aef390`.
- [Preserved legacy runtime declaration](implementations/registered-runtime/manifest.json)
- [Legacy declaration package](implementations/registered-runtime)

This preserved declaration is lineage, not current execution qualification. Its historical paths may describe the source snapshot.

## Implementation artifacts

- [Registered runtime](implementations/registered-runtime) — Calibration only.
  Scope: This is the source package currently selected by the published catalog; current does not assert executable/scientific qualification. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Original threshold sweep v1](implementations/original-threshold-sweep-v1) — Reviewed source component.
  Scope: Reviewed additive source component for the existing task. The package documentation and source contracts define its scope; source enrollment does not establish authentic-data execution or scientific qualification.
- [Original panel reducer v1](implementations/original-panel-reducer-v1) — Reviewed source component.
  Scope: Original recovery-panel reducer. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://doi.org/10.25378/janelia.25298815.v1)
- [Code](https://github.com/MouseLand/Kilosort)
- [Code](https://github.com/MouseLand/Kilosort/blob/v4.0.2/kilosort/bench.py)
- [Code](https://github.com/MouseLand/Kilosort/blob/v4.0.2/kilosort/run_kilosort.py)
- [Code](https://github.com/MouseLand/Kilosort/blob/v4.0.2/kilosort/simulation.py)
- [Code](https://ibl.flatironinstitute.org/public/)
- [Code](https://raw.githubusercontent.com/MouseLand/Kilosort/0e07514c16fc1162f6470ecbad25be9c7e256306/LICENSE)
- [Code](https://raw.githubusercontent.com/MouseLand/Kilosort/0e07514c16fc1162f6470ecbad25be9c7e256306/README.md)
- [Code](https://rdr.ucl.ac.uk/articles/dataset/Recording_with_a_Neuropixels_probe/25232962/1)
- [Code](https://www.nature.com/articles/s41592-024-02232-7)
- [Code](https://zenodo.org/api/records/10863771)
- [Code](https://zenodo.org/api/records/10863771/files/MouseLand/Kilosort-v4.0.2.zip/content)
- [Paper](https://www.nature.com/articles/s41592-024-02232-7)
- [Source](https://figshare.com/articles/dataset/25232962)
- [Source](https://figshare.com/articles/dataset/25298815)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
