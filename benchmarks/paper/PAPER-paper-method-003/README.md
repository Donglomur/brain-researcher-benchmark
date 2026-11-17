# REVE: A Foundation Model for EEG – Adapting to Any Setup with Large-Scale Pretraining on 25,000 Subjects

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-003`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Design ready
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Success:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule.

**Disposition:** design\_ready. The original four-class PhysioNet-MI endpoint, participant split and numeric REVE-Base result are recoverable. A same-task design is defensible, but historical preprocessing, run aggregation and checkpoint/recipe parity remain unresolved; the extensive local source proposal is not an executed author baseline.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition (calibration only)](historical/task.pre-improvement.v1.json)

Existing reproduction graders and pilot scores remain calibration evidence. They cannot establish paper improvement. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 16187 bytes; SHA-256 `44b9f1a10706dfdc0ea888b9016750df86d23fd58fd12ccb35a95948065f609a`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Implementation artifacts

- [Paper paper method 003](implementations/paper-paper-method-003) — Calibration only.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Original physionet](implementations/original-physionet) — Original panel preparation and scoring.
  Scope: Original 109-participant PhysioNet acquisition/preparation, full-panel pooled balanced-accuracy/kappa/weighted-F1 scoring and strict author checkpoint adapter. Preparation and fixed software controls do not establish source classifier, historical seed roster, filter/checkpoint parity, paired candidate execution, same-task superiority or current SOTA.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://arxiv.org/abs/2510.21585)
- [Code](https://github.com/elouayas/reve_eeg)
- [Code](https://huggingface.co/brain-bzh/reve-base)
- [Code](https://huggingface.co/datasets/brain-bzh/reve-dataset)
- [Code](https://physionet.org/content/eegmmidb/1.0.0/)
- [Code](https://proceedings.neurips.cc/paper_files/paper/2025/hash/20a917f77773ac0fa8bea2bdd6606b66-Abstract-Conference.html)
- [Code](https://raw.githubusercontent.com/elouayas/reve_eeg/06a7059a07c3dabd80aee60c3dbc1eca4bdbe1c7/LICENSE)
- [Code](https://raw.githubusercontent.com/elouayas/reve_eeg/06a7059a07c3dabd80aee60c3dbc1eca4bdbe1c7/README.md)
- [Paper](https://proceedings.neurips.cc/paper_files/paper/2025/hash/20a917f77773ac0fa8bea2bdd6606b66-Abstract-Conference.html)
- [Source](https://physionet.org/content/eegmmidb/1.0.0/)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
