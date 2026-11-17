# NeuroPictor prepared-tensor evaluation, version 1

This is an independently implemented arithmetic evaluation package for `PAPER-paper-method-043`. It computes a complete reconstruction metric panel from operator-prepared tensors and compares pretrained, target-only, and neural-free conditions. It does not implement NeuroPictor training, diffusion inference, image resizing or neural-network feature extraction. It is not a qualified benchmark or a candidate submission interface. The canonical task and historical records are unchanged.

## Scientific boundary and provenance

The [ECCV paper](https://www.ecva.net/papers/eccv_2024/papers_ECCV/papers/06746.pdf), sections 4.1–4.3, describes a shared 982-image test pool for subjects 1, 2, 5 and 7, three-trial averaging, one generated reconstruction per stimulus, and averaging metrics over subjects. Its encoder initialization and multi-subject image-pretraining ablations are separate interventions. Exact stimulus/session membership and checkpoint ancestry have not been acquired or independently verified here. The optional `paper_four_subjects` scope checks those counts and shared IDs; passing the structural check is not proof of the authentic pool. `declared_subjects` supports explicitly scoped development pools without relabeling them as the paper population.

The arithmetic is derived from [`eval_metrics.py` at b676b5be320ebb1b12919afd4cf6152e2c45db5d](https://github.com/jingyanghuo/neuropictor/blob/b676b5be320ebb1b12919afd4cf6152e2c45db5d/eval_metrics.py), lines 101–266. Pixel correlation is paired Pearson correlation. AlexNet(2), AlexNet(5), Inception and CLIP use strict two-way Pearson identification; each prediction is compared against every other true stimulus in its subject pool. Ties fail. EfficientNet and SwAV use paired correlation distance. All eight families remain separate; no primary score, binary reward or paper-value tolerance is invented.

The source SSIM call combines grayscale input with a legacy `multichannel=True` argument. Its environment does not pin scikit-image. This package therefore names its endpoint `ssim_2d_prospective`: explicit 2D grayscale Gaussian SSIM with sigma 1.5, an 11-pixel window, population covariance, range 1, K1 .01 and K2 .03, and a five-pixel border crop. It does not claim numerical equivalence to that ambiguous historical call. Finite constant feature rows, which make Pearson correlation undefined, are rejected rather than silently counted as failures.

The [`dataset.py` source](https://github.com/jingyanghuo/neuropictor/blob/b676b5be320ebb1b12919afd4cf6152e2c45db5d/dataset/dataset.py) selects available validation labels and can truncate them. The [`reconstruction.py` source](https://github.com/jingyanghuo/neuropictor/blob/b676b5be320ebb1b12919afd4cf6152e2c45db5d/reconstruction.py) uses batch-based filenames. Neither is evidence of a complete protected image population. A trusted identity sidecar is required; filename order alone is insufficient.

## Interface

Run with an existing Python installation containing NumPy and SciPy:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  benchmarks/paper/PAPER-paper-method-043/implementations/initial-evaluator-v1/evaluator.py \
  /path/to/operator-manifest.json --output /path/to/panel.json
```

No package installation, network call, pickle loading, model download or subprocess execution occurs in the evaluator. Input manifest paths resolve relative to the manifest. The test fixture builder in `tests/test_evaluator.py` creates a complete executable example with generated tensors and fabricated receipt hashes explicitly for engineering checks.

The manifest has `protocol`, `reference` and three `conditions` objects. A protocol contains:

- `task_id`, `policy: "prospective-prepared-panel-v1"`, `scope: "declared_subjects"` or `"paper_four_subjects"`, and `generation_policy: "one_sample_per_subject_stimulus"`.
- `samples`: ordered records with nonempty string `sample_id`, `subject_id`, `stimulus_id`, and a nonempty unique string list `session_ids`. Subject IDs in paper scope are `"1"`, `"2"`, `"5"`, `"7"`. Each subject needs at least two distinct stimuli. A stimulus may occur in multiple subjects; repeated reconstructions within a subject are rejected.
- Lowercase SHA-256 receipt strings: `protected_pool_receipt_sha256`, `exposure_ledger_sha256`, `rights_review_sha256`.
- `extraction`: `pixel_policy: "source256_then425_rgb_chw_01"`, `ssim_policy: "explicit_2d_gaussian_v1"`, `preprocessing_sha256`, and one `<feature>_extractor_sha256` for each feature key below. These hashes must bind operator-reviewed recipes, runtime versions, weights and transforms, not merely model names.

Each bundle (`reference` or a condition's `bundle`) has `path`, SHA-256 of the actual NPZ bytes in `sha256`, its own ordered `samples`, and an `extraction` object identical to the protocol. Each NPZ must contain exactly:

| Key | Shape | Meaning |
| --- | --- | --- |
| `pixels425` | N × 3 × 425 × 425 | Prepared RGB pixels in [0,1], after the source's 256 then 425 resize path |
| `alexnet2`, `alexnet5` | N × D | Flattened AlexNet features.4 and features.11 |
| `inception`, `clip` | N × D | Flattened Inception avgpool and CLIP image encoding |
| `effnet`, `swav` | N × D | Flattened EfficientNet-B1 and SwAV avgpool |

Each feature D is at least two and must match the reference's D. All values are finite real numbers. Operator extraction starts from the source's 256-pixel image path, uses the source-specific resize and normalization per network, and separately produces the 425-pixel array. Model extraction is deliberately outside this numerical kernel. SwAV's mutable upstream branch, local CLIP weights and version-dependent resize behavior require pinned operator provenance before authentic use. Ground truth must stay under operator control; accepting candidate-supplied features would permit forgery. A hash proves byte identity, not trustworthy provenance.

Every condition has a unique `name`, role `pretrained`, `target_only` or `neural_free`, a `bundle`, `checkpoint_sha256`, and `initialization_exposure_sha256`. All three must share `target_training_membership_sha256`, `diffusion_prior_sha256`, `tuning_budget_sha256`, `generation_budget_sha256`, `encoder_initialization_sha256` and `encoder_route`. The latter is `released_encoder`, `raw_pretrained_encoder` or `random_init`. The pretrained condition declares `image_pretraining_route` as `raw_multi_subject` or `released_multi_subject_checkpoint`; the other two declare `none`. `neural_input` must be false for the neural-free condition and true for the others. The shared encoder hash identifies its initialization before the compared image-training procedures; final trained encoder weights may differ and are bound by each condition’s checkpoint hash. These declarations bind the comparison without conflating a released encoder with raw UKB pretraining. Their truth still requires independent exposure and resource auditing. The neural-free control recipe itself must be frozen in the supplied generation/exposure receipts; this package does not train it.

The report contains per-stimulus metric vectors, per-subject means, a macro average over subjects, and raw pretrained-minus-comparator differences. Negative distance differences mean improvement; positive differences improve the other metrics. No uncertainty interval is fabricated from shared stimuli, no best-of-samples selection occurs, and comparisons make no causal or blind-evaluation claim. The report always retains `research_qualified: false`, `native_equivalence_verified: false` and `full_contract_complete: false`.

## Validation, rights and resources

Run the generated controls:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s benchmarks/paper/PAPER-paper-method-043/implementations/initial-evaluator-v1/tests -v
```

The independent controls distinguish column from row identification, Pearson from cosine, strict ties from partial credit, paired distance direction, analytic SSIM offsets, identity alignment, exact population membership, comparator matching, and subject macro aggregation. The CLI test hashes actual NPZ files and evaluates all metric families. These controls establish arithmetic and interface behavior, not authentic reconstruction quality or baseline competence.

The implementation is original; no upstream code, images, weights or datasets are vendored. Mathematical semantics and source locators are attributed above. The upstream code reuse license was unresolved in the canonical record. Deposit license tags do not clear NSD/COCO, UKB, diffusion-prior or checkpoint rights; those gates remain open. Protected references, actual participant/session/stimulus overlap, primary grading policy, input extraction parity, independent native reference replay, candidate isolation, and full population qualification remain required.

The evaluator loads one full reference and one full condition at a time, converts arrays to float64 and makes per-subject intermediate copies. A four-subject pixel array alone is about 17 GB; native peak memory and full lifecycle storage have not been measured. Correlation distractors are processed in blocks of 128 without shrinking the population. Generated tests use three images, no accelerator, models, empirical data or scientific runs. Full-population runtime must be measured before operational admission.
