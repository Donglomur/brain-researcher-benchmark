# MARBLE: interpretable representations of neural population dynamics using geometric deep learning

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-034`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Success:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule.

**Disposition:** source\_unresolved. Figure 5d has a genuine ordered mean-position-error endpoint, but the paper and pinned author notebooks disagree on preprocessing/support and checkpoint training provenance is missing. A four-rat clean/half-neuron evaluation, median error or1,999 query rows cannot replace the original 2,000-observation within-rat comparison.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition (calibration only)](historical/task.pre-improvement.v1.json)

Existing reproduction graders and pilot scores remain calibration evidence. They cannot establish paper improvement. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 24251 bytes; SHA-256 `c6c566362e7927b81c82fa879e615da9bc18521dd847f8f99c05e8fbd29a166f`.
- [Preserved legacy runtime declaration](implementations/registered-runtime/manifest.json)
- [Legacy declaration package](implementations/registered-runtime)

This preserved declaration is lineage, not current execution qualification. Its historical paths may describe the source snapshot.

## Implementation artifacts

- [Registered runtime](implementations/registered-runtime) — Calibration only.
  Scope: This is the source package currently selected by the published catalog; current does not assert executable/scientific qualification. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Fit closed comparator](implementations/fit-closed-comparator) — Calibration only.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Paper improvement episode v1](implementations/paper-improvement-episode-v1) — Calibration only.
  Scope: Source-matched MARBLE comparator recovery and explicit prospective-extension diagnostics. Original Figure5d support and paper/code preprocessing conflicts remain unresolved; this component cannot establish same-task paper improvement or current SOTA. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://arxiv.org/abs/2304.03376)
- [Code](https://github.com/Dynamics-of-Neural-Systems-Lab/MARBLE)
- [Code](https://github.com/Dynamics-of-Neural-Systems-Lab/MARBLE/blob/09491ec077bf153b7dece8518cc65ddaa20eb26d/examples/rat_hippocampus/decoding.ipynb)
- [Code](https://github.com/Dynamics-of-Neural-Systems-Lab/MARBLE/blob/09491ec077bf153b7dece8518cc65ddaa20eb26d/examples/rat_hippocampus/run_marble_and_cebra.ipynb)
- [Code](https://raw.githubusercontent.com/Dynamics-of-Neural-Systems-Lab/MARBLE/09491ec077bf153b7dece8518cc65ddaa20eb26d/LICENSE)
- [Code](https://raw.githubusercontent.com/Dynamics-of-Neural-Systems-Lab/MARBLE/09491ec077bf153b7dece8518cc65ddaa20eb26d/README.md)
- [Code](https://www.nature.com/articles/s41592-024-02582-2)
- [Paper](https://www.nature.com/articles/s41592-024-02582-2)
- [Source](https://dataverse.harvard.edu/api/access/datafile/7609512)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
