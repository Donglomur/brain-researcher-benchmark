# Learning produces an orthogonalized state machine in the hippocampus

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-FIND-REP-001`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** source\_unresolved. Whole-paper review identifies an original ordered prediction task: reward-symbol accuracy in Extended Data Fig. 9a, from models trained to predict the next sensory symbol in the 2ACDC sequence. Exact published scores, model-specific simulation manifests, prediction masks and native evaluation callers remain unrecovered. The legacy Fig. 2f descriptive scope does not limit this authorized source-native rebind; its learning curves remain calibration only.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 39487 bytes; SHA-256 `759b3f442819f938830d73bc305a625d1bb7b603b353311ff6b5f3071b875348`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Source-derived Figure 2f endpoint from prepared place-field binF exports: 46-by-46 near/far population correlations, six literal masks, normalized learning curves and equal-animal means/source SEM for the eleven-animal roster. Native fluorescence/Zarr export equivalence, authentic complete sessions and cell registration, independent numeric references/tolerances, direct cross-day stability, state-versus-position comparison and animal-held-out improvement remain unimplemented or unqualified. This is not a whole-paper grader. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Reward prediction v1](implementations/reward-prediction-v1) — Reviewed source component.
  Scope: Original 2ACDC reward-prediction arithmetic. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/sprustonlab/OSM_Paper_Figures)
- [Paper](https://doi.org/10.1038/s41586-024-08548-w)
- [Source](https://janelia.figshare.com/articles/dataset/Dataset_supporting_paper_Learning_produces_a_hippocampal_cognitive_map_in_the_form_of_an_orthogonalized_state_machine_/27273552)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
