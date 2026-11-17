# EEGPT: Pretrained Transformer for Universal and Reliable Representation of EEG Signals

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-023`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** source\_unresolved. The complete original PhysioP300 Table 4 comparison panel is the selected same-task scope. Its published scores are recoverable, but the released preprocessing and training scripts disagree about subject membership and epoch boundaries, and the reporting/selection reduction is not sufficiently reconciled for a calibrated comparison. The broader S8 programme is preserved as history, without requiring unrelated downstream datasets for a PhysioP300 win.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 22023 bytes; SHA-256 `3d630bf75ec67ddaaefc02364c730213eaa2ad57c84932770ad826a2601f36b9`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Implementation artifacts

- [Paper paper method 023](implementations/paper-paper-method-023) — Calibration only.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/BINE022/EEGPT)
- [Code](https://proceedings.neurips.cc/paper_files/paper/2024/hash/4540d267eeec4e5dbd9dae9448f0b739-Abstract-Conference.html)
- [Code](https://raw.githubusercontent.com/BINE022/EEGPT/ea7282f698c406cd423ccbedbe9960853761144c/LICENSE)
- [Code](https://raw.githubusercontent.com/BINE022/EEGPT/ea7282f698c406cd423ccbedbe9960853761144c/README.md)
- [Paper](https://proceedings.neurips.cc/paper_files/paper/2024/hash/4540d267eeec4e5dbd9dae9448f0b739-Abstract-Conference.html)
- [Source](https://physionet.org/content/erpbci/1.0.0/)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
