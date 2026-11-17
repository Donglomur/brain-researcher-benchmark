# UMBRAE: Unified Multimodal Brain Decoding

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-042`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Design ready
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** design\_ready. The source v2 Table 2 provides a complete ordered grounding endpoint for all four original subjects. This design preserves that per-subject result vector, rather than an invented pooled paper score. Native annotation/order, author-scoring parity, baseline execution and a valid improvement decision are not yet admitted.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 127257 bytes; SHA-256 `d262914ca9dd79f88836c23ac5182d5e5d39ea0ff4df94e010913f46198e2e68`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Prospective BrainHub referring-expression grounding scoring with per-subject All-category accuracy at strict IoU greater than 0.5, secondary salience summaries, paired controls and shared-image uncertainty. Authentic annotation/order membership, model/reference execution, actual exposure and intervention fidelity, rights and protected isolation remain held. Captioning, transfer and subject adaptation are outside this component; scientific qualification is unknown. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://arxiv.org/abs/2404.07202)
- [Code](https://github.com/weihaox/UMBRAE)
- [Code](https://github.com/weihaox/UMBRAE/blob/8c1795c434a41cdd38ce6628b7e1a774f31d9483/umbrae/download_data.sh)
- [Code](https://github.com/weihaox/UMBRAE/blob/8c1795c434a41cdd38ce6628b7e1a774f31d9483/umbrae/inference.py)
- [Code](https://github.com/weihaox/UMBRAE/blob/8c1795c434a41cdd38ce6628b7e1a774f31d9483/umbrae/train.py)
- [Code](https://github.com/weihaox/UMBRAE/blob/8c1795c434a41cdd38ce6628b7e1a774f31d9483/umbrae/train_brainx.py)
- [Code](https://huggingface.co/datasets/pscotti/naturalscenesdataset/tree/main/webdataset_avg_split)
- [Code](https://raw.githubusercontent.com/weihaox/UMBRAE/8c1795c434a41cdd38ce6628b7e1a774f31d9483/LICENSE.txt)
- [Code](https://raw.githubusercontent.com/weihaox/UMBRAE/8c1795c434a41cdd38ce6628b7e1a774f31d9483/README.md)
- [Code](https://raw.githubusercontent.com/weihaox/UMBRAE/main/umbrae/download_data.sh)
- [Code](https://weihaox.github.io/UMBRAE)
- [Paper](https://arxiv.org/abs/2404.07202)
- [Source](https://huggingface.co/api/datasets/pscotti/naturalscenesdataset)
- [Source](https://huggingface.co/datasets/weihaox/brainx/resolve/main/all_images.pt)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
