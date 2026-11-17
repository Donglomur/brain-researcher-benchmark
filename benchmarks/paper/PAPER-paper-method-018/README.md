# Identifying interactions across brain areas while accounting for individual-neuron dynamics with a Transformer-based variational autoencoder

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-018`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Success:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule.

**Disposition:** source\_unresolved. The paper reports an ordered Allen test-NLL result, but the split, metric normalization and model flags needed to reproduce that number disagree with the available code path. The local equal-session interaction-gain endpoint is prospective and cannot substitute for exceeding the published full-model task.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition (calibration only)](historical/task.pre-improvement.v1.json)

Existing reproduction graders and pilot scores remain calibration evidence. They cannot establish paper improvement. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 38435 bytes; SHA-256 `541a4d96a8edc6f04d39f3541c214d210ce2751481f03052482bd425b89e2cbf`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Prepared-artifact evaluator for the complete ten-session history-versus-interaction comparison, with source neural and latent loss components, matched identities/batches and prospective session-level gains. Target-conditioned latent reconstruction is not blind forecasting. Native Allen preprocessing and eligibility, author interface/layout discrepancies, missing anatomical/condition subpanels, authentic figure references, code/data rights, grouped improvement and protected qualification remain unresolved. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://arxiv.org/abs/2506.02263)
- [Code](https://github.com/Qi-Xin/GLM-Transformer)
- [Code](https://github.com/Qi-Xin/GLM-Transformer/blob/421b5eef321cac3d1c1279759e0f6b638068b021/DataLoader.py)
- [Code](https://github.com/Qi-Xin/GLM-Transformer/blob/421b5eef321cac3d1c1279759e0f6b638068b021/Reproduce_figures/Fig5.ipynb)
- [Code](https://github.com/Qi-Xin/GLM-Transformer/blob/421b5eef321cac3d1c1279759e0f6b638068b021/allen_env_full.yml)
- [Code](https://proceedings.neurips.cc/paper_files/paper/2025/file/ac643478c07baa8432690555e4702b65-Paper-Conference.pdf)
- [Code](https://raw.githubusercontent.com/Qi-Xin/GLM-Transformer/421b5eef321cac3d1c1279759e0f6b638068b021/README.md)
- [Paper](https://proceedings.neurips.cc/paper_files/paper/2025/file/ac643478c07baa8432690555e4702b65-Paper-Conference.pdf)
- [Source](https://portal.brain-map.org/explore/circuits/visual-coding-neuropixels)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
