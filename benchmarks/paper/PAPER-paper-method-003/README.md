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

**Disposition:** design\_ready. The complete original PhysioNet-MI panel is authenticated and prepared: 654 imagery EDFs from all 109 participants yield 9,837 epochs on the original split, and the full-test numerical scorer/comparator has passed an authentic-data software control. This establishes source preparation and scoring, not an author baseline. Historical preprocessing, Table 12 classifier/checkpoint parity and seed/run aggregation remain unresolved.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition (calibration only)](historical/task.pre-improvement.v1.json)

Existing reproduction graders and pilot scores remain calibration evidence. They cannot establish paper improvement. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Recorded public evidence

Each record keeps the scope of its original report. It is not current runtime qualification.

- [Paper source preparation](../../../docs/status/reve-source-preparation-20261116.json): Complete authentic PhysioNet-MI source preparation under the released direct-200-Hz profile and a fixed-output full-test scorer/comparator software control. This is not trained REVE performance, author-baseline qualification, historical paper reproduction or same-task improvement.

Inspect conditions, metrics and limits with `python3 scripts/neurobench.py evidence PAPER-paper-method-003`. Programme evidence does not establish direct interpretation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 18420 bytes; SHA-256 `2325143fbf783f0810a84e4d4de71f40148c2c5a23eaed37b516c4cbac2ba816`.

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
