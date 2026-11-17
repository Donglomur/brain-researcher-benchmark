# MindEye2: Shared-Subject Models Enable fMRI-To-Image With 1 Hour of Data

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-032`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Design ready
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Success:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule.

**Disposition:** design\_ready. The original one-session retrieval/reconstruction task and corrected published retrieval score are recoverable. Native feature/reference parity, full reconstruction evaluation, exact historical preprocessing and sample manifests, a meaningful effect rule, and measured episode budgets remain unqualified; the feature-only component cannot admit an improvement win.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition (calibration only)](historical/task.pre-improvement.v1.json)

Existing reproduction graders and pilot scores remain calibration evidence. They cannot establish paper improvement. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 185699 bytes; SHA-256 `f259756e7d34b45c589ca7500c16a127f1758f7e0465ac8bd333d85be3385d8e`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Scores identity-bound MindEye2 retrieval embeddings with corrected image/brain directions and 30 frozen 300-candidate pools, plus reconstruction feature kernels, post-model repeat averaging and exposure-ledger audits. Complete native adaptation/reconstruction, authentic four-subject/trial identities, paper/notebook orientation and historical RNG parity, checkpoint/image exposure, rights and protected scientific qualification remain unresolved. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://arxiv.org/abs/2403.11207)
- [Code](https://github.com/MedARC-AI/MindEyeV2)
- [Code](https://github.com/MedARC-AI/MindEyeV2/blob/76a2609243ba1bacb450e47e3dc78de1f78a9c00/src/Train.ipynb)
- [Code](https://github.com/MedARC-AI/MindEyeV2/blob/76a2609243ba1bacb450e47e3dc78de1f78a9c00/src/final_evaluations.ipynb)
- [Code](https://github.com/MedARC-AI/MindEyeV2/blob/76a2609243ba1bacb450e47e3dc78de1f78a9c00/src/recon_inference.ipynb)
- [Code](https://github.com/MedARC-AI/MindEyeV2/blob/76a2609243ba1bacb450e47e3dc78de1f78a9c00/src/setup.sh)
- [Code](https://huggingface.co/datasets/pscotti/mindeyev2)
- [Code](https://proceedings.mlr.press/v235/scotti24a.html)
- [Code](https://raw.githubusercontent.com/MedARC-AI/MindEyeV2/76a2609243ba1bacb450e47e3dc78de1f78a9c00/LICENSE)
- [Code](https://raw.githubusercontent.com/MedARC-AI/MindEyeV2/76a2609243ba1bacb450e47e3dc78de1f78a9c00/README.md)
- [Paper](https://proceedings.mlr.press/v235/scotti24a.html)
- [Source](https://huggingface.co/api/datasets/pscotti/mindeyev2)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
