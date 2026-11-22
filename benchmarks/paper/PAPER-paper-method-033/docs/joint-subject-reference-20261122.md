# Joint-subject reference candidate: MindBridge Table 1

**Status: source-supported reference candidate, not an executed reproduction.** This note leaves the existing Table 2 / full-48 task, information conditions, scorer and readiness status unchanged. It adds no benchmark, measured score or readiness qualification.

## Original endpoint

In the author manuscript `arXiv:2404.07850v1`, Table 1's **MindBridge (Ours)** row uses one jointly trained model for subjects **1, 2, 5 and 7**. Its **94.7% CLIP two-way identification** result is the average across those four subjects. Evaluate each subject on its own **982-image gallery**, then average the four subject scores. The number is not a published subject-7 score. [Paper: Table 1 and Sections 3.1/4.1](https://arxiv.org/html/2404.07850v1)

Supplement B specifies **eight reconstructed candidates per case**, selecting the candidate with the highest CLIP similarity to the actual stimulus: a target-aware oracle selection rule. It also specifies **20 diffusion steps, guidance 5 and text-image ratio 0.5**. Preserve this generation budget and selection rule when comparing with the paper. [Paper: Supplement B](https://arxiv.org/html/2404.07850v1)

No quantitative subject-specific result for the jointly trained 1257 model was found in the inspected main paper and supplement. Figures 3/5 provide qualitative reconstructions. A subject-7-only run can be a component measurement; it cannot establish reproduction of the four-subject 94.7% average or substitute for Table 2's separate adaptation condition.

## Official checkpoint candidate

The [author README at code revision `2a3943ff5b619db6f85f16a5e7ff1331d25def55`](https://github.com/littlepure2333/MindBridge/blob/2a3943ff5b619db6f85f16a5e7ff1331d25def55/README.md) links pretrained weights for subjects 01/02/05/07. The [training recipe](https://github.com/littlepure2333/MindBridge/blob/2a3943ff5b619db6f85f16a5e7ff1331d25def55/scripts/train_bridge.sh) names `mindbridge_subj1257` and selects subjects `1 2 5 7`.

The [immutable author release](https://huggingface.co/littlepure2333/MindBridge/tree/1f2d5151fd96b42c6381146c21455402971e2432) lists:

- File: `mindbridge_subj1257/last.pth`
- Declared size: **3,814,945,315 bytes**
- Declared LFS SHA-256: `e18f292708b22925616956a3c24a5d2b36f7390d2a95ad76b1ad3a068e97f990`

These are release-metadata identities; the checkpoint body was not acquired or hashed in this inquiry. The model card and upload history do not explicitly bind that hash to the historical Table 1 scores, and the inspected release lists no training-split, configuration or result sidecars. The evidence supports an official reference candidate for the protocol, not proof of identical historical weights. [Pinned metadata](https://huggingface.co/api/models/littlepure2333/MindBridge/revision/1f2d5151fd96b42c6381146c21455402971e2432?blobs=true)

## Required invocation and remaining work

The [checked-in inference example](https://github.com/littlepure2333/MindBridge/blob/2a3943ff5b619db6f85f16a5e7ff1331d25def55/scripts/inference.sh) instead names `mindbridge_subj125`. A Table 1 reference invocation must explicitly select `mindbridge_subj1257`, `last`, and matching load/test subjects for each of 1/2/5/7. [Reconstruction code](https://github.com/littlepure2333/MindBridge/blob/2a3943ff5b619db6f85f16a5e7ff1331d25def55/src/recon.py) selects a subject-specific view and loads with `strict=False`. Compatibility checking must verify required selected-subject and shared parameters and their shapes; successful permissive loading alone is insufficient.

The existing target-7-only projection does not qualify subjects 1/2/5 or the four-subject aggregate. Remaining work includes checkpoint-body authentication, those three test-cohort preparations, original generation/CLIP weights and runtime, and exact evaluation binding. The [pinned evaluator](https://github.com/littlepure2333/MindBridge/blob/2a3943ff5b619db6f85f16a5e7ff1331d25def55/src/eval.py) specifies CLIP ViT-L/14 features and strict Pearson two-way comparison. Historical SSIM/SwAV bindings remain separate requirements for an eight-metric result.

Released-reference inference does not require the Table 2 4000-example adaptation step; it also does not replace training requirements for reproduction from scratch. **This proposed Table 1 endpoint remains unqualified for execution readiness, full-panel reproduction or improvement. No score has been measured.** The numeric source is explicitly author v1; the publisher page was unavailable during the inquiry.
