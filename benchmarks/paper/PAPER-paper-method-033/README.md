# MindBridge: A Cross-Subject Brain Decoding Framework

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-033`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 128582 bytes; SHA-256 `837cade4f9794be5e10e129d9c8244135f0841a25b3f42661728d04ee31722c6`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Task implementation.
  Scope: Prospective fixed-target MindBridge feature evaluator with source Pearson identification/correlation metrics, explicit paired calibration budgets, exposure/image/session declarations and neural controls. Target, primary metric and budget policy remain unfrozen; actual feature extraction/generation, NSD/weight/pretraining provenance, receipt authentication, protected replay, rights and scientific qualification remain held. Fixed candidate selection deliberately differs from the paper’s target-aware best-of-eight selection, so published-score reproduction is not claimed.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/littlepure2333/MindBridge)
- [Code](https://github.com/littlepure2333/MindBridge/blob/2a3943ff5b619db6f85f16a5e7ff1331d25def55/scripts/adapt_bridge.sh)
- [Code](https://github.com/littlepure2333/MindBridge/blob/2a3943ff5b619db6f85f16a5e7ff1331d25def55/scripts/inference.sh)
- [Code](https://github.com/littlepure2333/MindBridge/blob/2a3943ff5b619db6f85f16a5e7ff1331d25def55/scripts/train_bridge.sh)
- [Code](https://github.com/littlepure2333/MindBridge/blob/2a3943ff5b619db6f85f16a5e7ff1331d25def55/scripts/train_single.sh)
- [Code](https://huggingface.co/datasets/pscotti/naturalscenesdataset/tree/main/webdataset_avg_split)
- [Code](https://littlepure2333.github.io/MindBridge)
- [Code](https://littlepure2333.github.io/MindBridge/)
- [Code](https://openaccess.thecvf.com/content/CVPR2024/html/Wang_MindBridge_A_Cross-Subject_Brain_Decoding_Framework_CVPR_2024_paper.html)
- [Code](https://raw.githubusercontent.com/littlepure2333/MindBridge/2a3943ff5b619db6f85f16a5e7ff1331d25def55/README.md)
- [Paper](https://openaccess.thecvf.com/content/CVPR2024/html/Wang_MindBridge_A_Cross-Subject_Brain_Decoding_Framework_CVPR_2024_paper.html)
- [Source](https://huggingface.co/api/datasets/pscotti/naturalscenesdataset)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
