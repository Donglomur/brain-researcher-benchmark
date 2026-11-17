# Neuroformer: Multimodal and Multitask Generative Pretraining for Brain Data

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-replacement-013`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Success:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule.

**Disposition:** source\_unresolved. Behavioral and neural prediction are ordered tasks, but the exact published run, evaluated support and baseline version are unresolved. The source reports conflicting lateral speed correlations; current full-support protected components amend the historical first-200 support. These cannot certify surpassing the source task.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition (calibration only)](historical/task.pre-improvement.v1.json)

Existing reproduction graders and pilot scores remain calibration evidence. They cannot establish paper improvement. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 33493 bytes; SHA-256 `3ac5ebe881993a87c6ece842ab33c9001f4789d6ec6c063a57533a8d801823c8`.
- [Preserved legacy runtime declaration](implementations/registered-runtime/manifest.json)
- [Legacy declaration package](implementations/registered-runtime)

This preserved declaration is lineage, not current execution qualification. Its historical paths may describe the source snapshot.

## Implementation artifacts

- [Registered runtime](implementations/registered-runtime) — Calibration only.
  Scope: This is the source package currently selected by the published catalog; current does not assert executable/scientific qualification. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Scientific contract](implementations/scientific-contract) — Calibration only.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/a-antoniades/Neuroformer)
- [Code](https://proceedings.iclr.cc/paper_files/paper/2024/hash/b16e55ac49f93d33a4b87747d5121b64-Abstract-Conference.html)
- [Code](https://raw.githubusercontent.com/a-antoniades/Neuroformer/36ed94084628c253098d448048c980d3dea0050d/configs/Visnav/lateral/mconf_predict_all.yaml)
- [Code](https://raw.githubusercontent.com/a-antoniades/Neuroformer/36ed94084628c253098d448048c980d3dea0050d/configs/Visnav/lateral/mconf_pretrain.yaml)
- [Code](https://raw.githubusercontent.com/a-antoniades/Neuroformer/36ed94084628c253098d448048c980d3dea0050d/neuroformer/datasets.py)
- [Code](https://raw.githubusercontent.com/a-antoniades/Neuroformer/36ed94084628c253098d448048c980d3dea0050d/neuroformer/model_neuroformer.py)
- [Code](https://raw.githubusercontent.com/a-antoniades/Neuroformer/36ed94084628c253098d448048c980d3dea0050d/neuroformer_inference.py)
- [Code](https://raw.githubusercontent.com/a-antoniades/Neuroformer/36ed94084628c253098d448048c980d3dea0050d/neuroformer_train.py)
- [Paper](https://proceedings.iclr.cc/paper_files/paper/2024/hash/b16e55ac49f93d33a4b87747d5121b64-Abstract-Conference.html)
- [Source](https://drive.google.com/drive/folders/1bg0wQjPGmg2XyTFmc68HiIhzM0oLGcJJ)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
