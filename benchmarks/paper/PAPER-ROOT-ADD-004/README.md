# Respiration shapes the neural dynamics of successful remembering in humans

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-ROOT-ADD-004`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** source\_unresolved. The source contains a genuine object-versus-scene decoding task (localizer-trained classifiers applied to retrieval EEG), but an exact final-article AUC comparator and complete native protocol are not recovered. Published remembered/nonremembered significance, effect size and respiration-memory correlation do not supply a decoding-performance baseline. The repository implementation explicitly changes preprocessing and time grids, so its results cannot establish a same-task paper win.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 19162 bytes; SHA-256 `a163da4d208b7d4edd3d0d35fa741d951c8319789a620daedeac44e817f0240f`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Prospective normalized-epoch recipe for localizer-to-retrieval decoding, respiration at confidence maxima and exhalation-aligned confidence–alpha/beta coupling across the pinned 18-participant roster. Native MAT extraction and complete trial/channel admission, article/archive/source discrepancies, authentic reference agreement, timing and artifact controls, participant-held-out improvement, rights and protected assessment remain unresolved. Observational coupling does not establish a causal breathing effect. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Native trial admission v1](implementations/native-trial-admission-v1) — Reviewed source component.
  Scope: Native retrieval metadata admission. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://data.ub.uni-muenchen.de/596/5/code.zip)
- [Paper](https://doi.org/10.1523/JNEUROSCI.1221-25.2025)
- [Source](https://data.ub.uni-muenchen.de/596/)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
