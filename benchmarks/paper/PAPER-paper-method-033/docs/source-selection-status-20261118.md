# MindBridge source selection: current implementation status

The original Table 2 selection and scoring source is implemented in this checkout.
The retained task and improvement contract still contain an earlier statement that
source-protocol scoring must be implemented. That statement predates the components
below and is superseded **only as a source-availability statement**. The exact task,
scientific contracts, outcome bindings and historical fingerprints remain unchanged.
No runtime, reproduction, improvement or submission readiness is promoted.

## The published evaluation rule

For each test image from target subject 7, the original procedure generates eight reconstruction candidates per stimulus
and chooses the one most similar to the true stimulus in the selection CLIP space.
This target-aware choice is part of the published evaluation protocol. It does not
measure deployment without access to the true stimulus. A fixed candidate index is
a separate condition and cannot substitute for this source-paper comparison.
See [supplement B](https://openaccess.thecvf.com/content/CVPR2024/supplemental/Wang_MindBridge_A_Cross-Subject_CVPR_2024_supplemental.pdf)
and the [pinned selection code](https://github.com/littlepure2333/MindBridge/blob/2a3943ff5b619db6f85f16a5e7ff1331d25def55/src/utils.py#L249).

Selection uses the flattened 257-by-768 projected hidden-token embeddings from
CLIP ViT-L/14, normalized before cosine ranking; the first maximum wins. Its
representation differs from final-metric CLIP `encode_image` features. One chosen
image supplies **all eight metrics**, without choosing a different winner per
metric. Final CLIP identification uses the original Pearson gallery comparison,
strict ties and the complete 982-image gallery (981 alternatives per image). Native rounding, invalid-value
behavior and near-tie parity retain the limits documented by the implementation.

The complete [main-paper Table 2](https://openaccess.thecvf.com/content/CVPR2024/papers/Wang_MindBridge_A_Cross-Subject_Brain_Decoding_Framework_CVPR_2024_paper.pdf)
contains Vanilla and MindBridge at 500, 1,500 and 4,000 calibration images, with
eight metrics each: **six conditions and 48 findings**. Preserve the full gallery of 982 stimulus images for target subject 7, source subjects 1, 2, and 5 for MindBridge, and the target-only Vanilla companion.
The 4,000-image CLIP primary endpoint is this benchmark's nomination, not a primary
endpoint designated by the paper. No average across metrics or budgets replaces
the original panel.

## Existing source to use

- [Source protocol](../implementations/source-protocol-v2/README.md): train-only
  lexicographic calibration prefixes and target-aware best-of-eight selection.
- [Original panel](../implementations/original-panel-v1/README.md): the common
  chosen image feeds all eight metrics and all six original conditions.
- [Selection features](../implementations/selection-features-v1/README.md): the
  distinct hidden-token feature producer, with declared runtime and weight limits.
- [Target-7 composition](../implementations/target7-composition-v1/README.md): the
  original metadata joins, preserving the complete gallery and condition support.
- [Author invocation evidence](../implementations/original-method-invocation-v1/README.md):
  recovered and missing historical launch recipes remain explicitly separated.

The [fixed-index evaluator](../implementations/initial-evaluator-v1/README.md)
remains available for its historical calibration scope. Its source and results
have not been replaced or relabelled.

## Remaining requirements

Before scientific use, authenticate the original stimulus and neural memberships,
all calibration prefixes, weights and exposure, native feature/metric execution,
historical SSIM/SwAV behavior, training/inference recipes and competent author
reference. Freeze all eight candidate images before the operator performs target-aware
selection. Do not expose true-target features or target-derived selected indices
to the participant during fitting or generation; generated declarations do not
enforce that boundary. Preserve all eight candidate images per case and the common chosen
image across metrics. Paired participant access, uncertainty and meaningful-effect
rules remain unqualified.

This update authenticates and describes existing source. It performs no original
input acquisition, feature extraction, inference, numerical replay or model study.

## Dependency provenance inspected on 2026-11-22

The [pinned author evaluator](https://github.com/littlepure2333/MindBridge/blob/2a3943ff5b619db6f85f16a5e7ff1331d25def55/src/eval.py)
and [requirements](https://github.com/littlepure2333/MindBridge/blob/2a3943ff5b619db6f85f16a5e7ff1331d25def55/requirements.txt)
confirm the metric calls described by the original-panel component. The requirements
fix torch 2.0.1 and torchvision 0.15.2 but leave scikit-image unpinned. They therefore
do not resolve which historical SSIM behavior produced the paper's values. Retain
the literal call and explicitly recorded backend; choosing a modern version does
not recover the author's environment.

SwAV's public source can be identified more precisely than the branch name alone.
The inspected upstream `main` resolves to commit
[`06b1b7cbaf6ba2a792300d79c7299db98b93b7f9`](https://github.com/facebookresearch/swav/commit/06b1b7cbaf6ba2a792300d79c7299db98b93b7f9),
dated 2021-09-21. Its
[`hubconf.py`](https://github.com/facebookresearch/swav/blob/06b1b7cbaf6ba2a792300d79c7299db98b93b7f9/hubconf.py)
is byte-identical to that file at the last file-changing commit,
[`9a2dc8073884c11de691ffe734bd624a84ccd96d`](https://github.com/facebookresearch/swav/blob/9a2dc8073884c11de691ffe734bd624a84ccd96d/hubconf.py)
dated 2021-04-02: 2,830 bytes, SHA-256
`b847cd9fb42479a0abbe457a6442b4dea9e56736e4683d99cbae393dd9c35e2b`.

That constructor defaults to pretrained standard ResNet-50 and names
[the 800-epoch SwAV checkpoint](https://dl.fbaipublicfiles.com/deepcluster/swav_800ep_pretrain.pth.tar).
Its loader removes the distributed-training key prefix and allows unmatched state
keys; the source embeds no checkpoint checksum. This establishes a public
constructor and weight route, not the bytes or cache used for the paper's run.
The checkpoint was not downloaded or opened in this inspection.

The remaining distinction is between this recovered source route and an
authenticated historical/native execution: original weight identity, historical
scikit-image version, device/batch behavior and numerical parity remain unresolved.
No scorer, target-aware best-of-eight rule, shared selected image, 982-image
gallery, six-condition panel or qualification status changes.
