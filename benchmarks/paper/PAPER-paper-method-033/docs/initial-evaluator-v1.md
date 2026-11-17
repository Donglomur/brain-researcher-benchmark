# MindBridge initial feature evaluator

This is a complete numerical evaluator for paired reconstruction features and a fixed-target calibration curve. It takes protected real-image features and candidate reconstruction features, verifies the declared evaluation population and access receipts, computes the pinned source's identification/correlation endpoints, and reports single-versus-bridge and neural-control comparisons at every budget. It performs no model training, image generation, feature extraction, NSD acquisition or scientific qualification. The canonical task remains unchanged and scientific qualification remains **unknown**.

The contract does not freeze a target participant, primary metric or calibration budget. Every input protocol must therefore say `prospective_unqualified`, select those fields explicitly, and bind all packets by canonical JSON SHA256. Supplying a protocol does not constitute owner approval of a scientific policy. No numeric success threshold or binary reward is introduced.

## Source and material distinctions

[MindBridge, CVPR 2024](https://openaccess.thecvf.com/content/CVPR2024/papers/Wang_MindBridge_A_Cross-Subject_Brain_Decoding_Framework_CVPR_2024_paper.pdf), section 3.1, reports subjects 1, 2, 5, 7, 982 common test images and 8,859 distinct training images per subject. Table 2 adapts from subjects 1/2/5 to subject 7 at 500/1,500/4,000 images. These historical settings inform the interface; they are not frozen here as a new benchmark population. The [supplement](https://openaccess.thecvf.com/content/CVPR2024/supplemental/Wang_MindBridge_A_Cross-Subject_CVPR_2024_supplemental.pdf) describes session-wise z-scored GLMSingle betas, random single training repeats and test averaging over up to three same-image repeats.

Crucially, supplement B chooses the best of eight reconstructions using CLIP similarity **to the true stimulus**. The present prospective interface instead fixes a candidate index before evaluation. All candidate feature arrays and a generation execution receipt are required; the selected index is identical for every image/arm/budget. This cannot reproduce the paper's target-aware selected scores. Comparison to its published numbers remains held.

The independent implementation follows the numerical definitions of [pinned eval.py](https://github.com/littlepure2333/MindBridge/blob/2a3943ff5b619db6f85f16a5e7ff1331d25def55/src/eval.py), revision `2a3943ff5b619db6f85f16a5e7ff1331d25def55`. No upstream implementation is redistributed. Source reads and content hashes are recorded in the adjacent `source-provenance.json`. Upstream redistribution licensing, NSD agreement, image and model rights remain separate unresolved gates.

## Computation

For `alexnet2`, `alexnet5`, `inception` and `clip`, real feature vectors form rows and reconstructed vectors form columns of the Pearson correlation matrix. For each predicted image j, its score is the fraction of the other N−1 real images whose correlation with prediction j is **strictly less** than the true-image correlation. Ties fail. This is all-pairs two-way identification; it is neither cosine similarity nor top-1 retrieval. The full NumPy `corrcoef` path is deliberate: an optimized normalization path changed exact affine ties during independent review and was removed. Zero-variance/nonfinite/overflow-undefined vectors are rejected prospectively instead of producing silent NaNs.

`effnet_b` and `swav` use paired correlation distance, 1−Pearson r, with lower scores better. `pixcorr` uses paired Pearson r of supplied flattened, already preprocessed image arrays. PixCorr inputs must represent the source's resize-to-425 bilinear path, not unprocessed pixels. The feature provenance receipt binds the extractor/preprocessing/model/weights and representation. The evaluator checks receipt consistency, not their truth. The source's SSIM/native preprocessing is not implemented; it is explicitly excluded rather than replaced by a generic similarity score. SwAV source refers to a moving `main`; its complete native weight/version identity remains held.

Each arm reports per-image values and their mean. Paired benefits orient all metrics so positive means bridge improves over single/control. A bootstrap samples focal unique image IDs, preserving the same draw across arms and budgets **while keeping the original full gallery fixed**. Its percentile interval is conditional on the target subject, fitted models, reconstruction seeds and fixed gallery; it does not estimate subject, training or gallery-sampling variability. A normalized trapezoidal integral of bridge-minus-single primary-metric benefit against unique-image budget summarizes the adaptation curve. Both bootstrap and integral are prospective reporting choices, with no acceptance threshold. They are not attributed to the paper.

## Inputs and trust boundary

The CLI accepts three JSON files and writes one JSON report. Python 3 and NumPy are the only runtime dependencies; no dependency is installed or downloaded by this package.

```
python3 evaluator.py protocol.json reference.json submission.json report.json --bootstrap-samples 2000 --seed 0
python3 -m unittest discover -s tests -v
```

The function `tests/test_evaluator.py:fixture()` provides a complete tiny **generated engineering example**, including all nested fields. Its arrays do not represent authentic CLIP/EffNet or brain observations and must not be used as scientific evidence.

The operator controls and protects `protocol.json` and `reference.json`; they must not be passed to a contestant together with hidden reference features. There is no candidate sandbox or replay service in this package. The report includes canonical protocol, reference and submission SHA256 digests. Hashes bind declared bytes, not biological authenticity.

Protocol fields:

| Field | Meaning |
| --- | --- |
| `schema_version`, `task_id`, `status` | `1`, `PAPER-paper-method-033`, `prospective_unqualified` |
| `target_subject` | One fixed canonical subject identity |
| `test_image_ids` | Complete ordered unique globally canonical NSD identities, at least two |
| `test_measurements` | Complete rows of `subject_id`, `session_id`, `image_id`, globally unique `measurement_id`; all test images covered |
| `metrics`, `primary_metric` | Nonempty subset of supported names; explicit primary among them |
| `selection` | `mode: fixed_candidate_index`, positive `candidate_count`, valid `candidate_index`, and nonempty `freeze_receipt` |
| `access_manifest_sha256`, `image_prior_sha256` | Receipts for equal available inputs and image priors, matched across all arms |
| `feature_provenance` | Exactly one object per metric with `extractor_receipt_sha256` and `representation`; the external receipt must identify preprocessing, model, weights and all transforms |
| `noncalibration_exposures` | Complete declared membership ledger: `stage` (`shared_training`, `development`, `image_prior_training`), `source`, `subject_id`, unique `image_ids`, `membership_receipt_sha256` |
| `budgets` | At least two increasing positive unique-image budgets, each with `budget` and `calibration` rows |

Each calibration row has `subject_id`, `image_id`, and unique `measurement_ids`. Budgets must be nested in both images and measurements, without changing measurement-to-image assignments. Repeated measurements are counted separately and never inflate the unique-image budget. Test images must be absent from all calibration and **every** declared noncalibration stage, regardless of subject. Test measurements cannot be reused for calibration. A nonempty shared-subject training membership is required; an image-prior membership entry is required even when explicitly empty. Unknown/unverifiable model-prior membership cannot be converted to an empty list to claim admission: complete authentic exposure remains an explicit gate.

The reference packet contains `protocol_sha256`, `target_subject`, `image_ids`, identical `feature_provenance`, and `features[metric]` as an N×D array. Reference features are trusted operator inputs, not contestant-owned attestations.

The submission contains `protocol_sha256` and `runs`. Exactly four arms at every budget are required: `single`, `bridge`, `neural_free`, `shuffled_neural`. Every run supplies `budget`, `arm`, `target_subject`, `test_measurements_sha256`, matching `access_manifest_sha256`, `image_prior_sha256`, `calibration_sha256`, `noncalibration_exposures_sha256`, identical `selection`, `execution_receipt_sha256`, `image_ids`, `feature_provenance`, and `features[metric]` as N×candidate_count×D arrays. IDs are joined explicitly, so reordered rows are safe; missing/extra/duplicate images, runs, features, target changes and nonfinite candidates reject the entire comparison.

Required `intervention` strings are `exposure_matched_single_subject_decoder`, `bridge_neural`, `no_neural_input`, and `within_target_image_derangement`, respectively. The shuffled-neural arm additionally provides `neural_donor_image_ids` aligned with its output image IDs, a permutation with no fixed points. This is an upstream neural-input intervention receipt, not permission to shuffle output features and call that a neural control. Execution receipt authentication and independent replay remain held.

The `single` arm is an **exposure-matched single-subject decoder comparator**, not a claim that the paper's target-only vanilla model automatically meets the canonical equal-shared-exposure rule. All runs must declare the same complete shared exposure ledger, same target calibration measurements and same image priors. Mere matching declarations cannot establish actual matching or compute equivalence. An authentic qualification must inspect available and actually used data separately, model execution and generation costs for all candidates; mismatched actual exposure cannot be accepted under this prospective endpoint.

## What remains held

No target, primary metric or budget policy has been approved for the canonical task. No authentic NSD payload or full cohort was acquired, no source preprocessing/model/native reference ran, and no protected replay or baseline competence was established. Correct image/subject/session mapping, all pretraining exposure including NSD overlap across tasks, complete source/weights, rights and independent scientific qualification remain unresolved. Source construction tests establish evaluator behavior only. The implementation returns `scientific_qualification: unknown` and `full_contract_complete: false` on every successful engineering evaluation.
