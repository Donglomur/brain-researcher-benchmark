# NeuroPictor bounded prepared-panel scoring

This package repairs the full-population memory problem in the [initial evaluator](../initial-evaluator-v1/README.md). A four-subject pixel tensor with 982 images per subject, three channels and 425 × 425 pixels requires **17,027,880,000 bytes** as float64 before the predecessor's per-subject copies and prediction tensor. Version 2 reads one image and at most 16 feature rows at a time. Every subject retains the complete distractor pool; it does not reduce image counts to fit memory.

The implementation reuses the predecessor's arithmetic, protocol validation, eight metric names and scientific limitations. It changes storage and iteration, not the task, cohort, units, subject weighting or comparator requirements. Original source remains [NeuroPictor at b676b5be320ebb1b12919afd4cf6152e2c45db5d](https://github.com/jingyanghuo/neuropictor/tree/b676b5be320ebb1b12919afd4cf6152e2c45db5d), especially `eval_metrics.py` lines 101–266. No upstream source, stimuli, weights or labels are vendored.

Reproduction of original findings and improvement beyond those findings are separate first-class outcomes. This component is shared arithmetic infrastructure for those outcomes; it establishes neither one. A complete source-faithful reproduction still needs native image generation/extraction, historical SSIM recovery and authenticated original membership. An improvement comparison additionally needs its frozen author baseline, effect and full-panel decision rule. Paired paper+data and paper+data+author-code participant conditions remain integration work; this operator scorer does not create or qualify those episodes. Existing task and historical files are preserved.

## Input and execution

Use an existing Python 3.10+ environment with NumPy and SciPy. There are no network calls, downloads, model calls, pickle loads or installations.

```sh
python3 benchmarks/paper/PAPER-paper-method-043/implementations/bounded-panel-v2/evaluator.py \
  /operator/manifest.json --output /operator/new-report.json
```

The `protocol` and all condition metadata follow the [existing specification](../../docs/initial-evaluator-v1.md). In particular, the paper scope requires the same 982 stimulus IDs in subjects 1, 2, 5 and 7; `declared_subjects` remains explicitly developmental. Input/session identity claims and exposure, extraction, training, encoder and budget receipts retain their original meaning. They require trusted operator preparation; arbitrary hashes do not establish provenance. Ground-truth images, captions and features must remain outside the candidate interface.

Replace each old NPZ bundle with a `npy-members-v1` bundle. Each array has its own **whole-file** SHA-256 and path, relative to the operator manifest or absolute. `samples` and `extraction` are identical in meaning to version 1. The `arrays` object must contain exactly these seven keys:

| Member | Required shape | Values |
| --- | --- | --- |
| `pixels425` | N × 3 × 425 × 425 | Prepared RGB in [0,1], source256-then425 route |
| `alexnet2`, `alexnet5`, `inception`, `clip` | N × D | Source-matched feature arrays; strict two-way Pearson identification |
| `effnet`, `swav` | N × D | Source-matched feature arrays; paired correlation distance |

The bundle structure is:

```json
{
  "format": "npy-members-v1",
  "samples": ["the existing ordered sample records go here"],
  "extraction": {"the existing extraction recipe goes here": "unchanged"},
  "arrays": {
    "pixels425": {"path": "real/pixels425.npy", "sha256": "actual whole-file SHA-256"},
    "alexnet2": {"path": "real/alexnet2.npy", "sha256": "actual whole-file SHA-256"},
    "alexnet5": {"path": "real/alexnet5.npy", "sha256": "actual whole-file SHA-256"},
    "inception": {"path": "real/inception.npy", "sha256": "actual whole-file SHA-256"},
    "clip": {"path": "real/clip.npy", "sha256": "actual whole-file SHA-256"},
    "effnet": {"path": "real/effnet.npy", "sha256": "actual whole-file SHA-256"},
    "swav": {"path": "real/swav.npy", "sha256": "actual whole-file SHA-256"}
  }
}
```

This is a schema illustration, not valid evidence. All three conditions (`pretrained`, `target_only`, `neural_free`) remain required. The target-only and neural-free controls do not replace the author reference for improvement claims. Native generation, source identity recovery and trusted feature extraction are not supplied here.

NPY inputs may use real integer or floating elements of at most eight bytes; object, complex and boolean arrays are rejected. Feature width must be 2–1,000,000. This is an explicit implementation bound, not a request to truncate native features. Unsupported widths must fail. Each file is hashed before admission and rehashed after scoring; identity, layout or byte changes fail. Complete reference/prediction shape and sample identities must match. Output uses exclusive creation and never overwrites a previous result.

## Metric and resource boundaries

Pixel correlation and prospective SSIM are computed one image at a time. Feature identification normalizes blocks of 16 real/predicted rows, compares every block against every other block within the subject, excludes self-comparisons, and counts strict `<` comparisons divided by N−1. A common contiguous feature-axis sum computes both matching and distractor correlations. This avoids BLAS matrix/vector reduction changes at short final blocks giving credit to identical-feature ties; no comparison tolerance or tie credit is added. The result reports per-stimulus values, per-subject means, equal-weight subject means and the same pretrained-minus-control differences. Negative distance deltas mean improvement. Reordering bundle rows cannot change their identity alignment.

Pearson normalization removes a row's offset before rescaling its variation. Scaling raw values first can distort an exactly translated feature vector and turn a strict identification tie into a false win. The shared arithmetic uses half-differences only when opposite finite extremes would overflow subtraction, so subnormal variation in other rows survives. Constant rows remain undefined and fail. This corrects the existing correlation endpoints; it does not change distractor counts, add tie credit, or establish historical numerical parity.

The historical grayscale `multichannel=True` SSIM call remains unresolved. The output is still named `ssim_2d_prospective`; passing these controls does **not** establish native SSIM parity. Undefined correlations and nonfinite values fail rather than disappearing from the population.

NPY mappings are opened for bounded reads and immediately closed, preventing touched mappings from accumulating over the full population. The row-wise dot products also use a temporary of at most 16 feature rows. Array data allocations are bounded by feature width and block size; small identity and result vectors still scale with N. The scorer hashes complete files and repeatedly reads feature blocks, trading extra I/O for lower resident data memory. No claim of faster runtime is made. Full native wall time, page-cache behavior and peak memory are unmeasured; an authentic run still requires a frozen resource protocol. Merely using memory mapping is not a resource reservation. Version 2 does not convert or stage large existing NPZ files automatically.

## Generated controls

```sh
python3 -B -m unittest discover \
  -s benchmarks/paper/PAPER-paper-method-043/implementations/bounded-panel-v2/tests -v
```

Run controls within the operator's active resource allocation. Controls include all 982 generated distractors with a tie at the last image, an independent scalar Pearson oracle across feature-block boundaries, reordered identities across two unequal subject cohorts, complete eight-metric parity with the predecessor, bounded reads with closed mappings, exact hashes and population checks, matched comparator requirements, mutation detection and an end-to-end CLI/no-overwrite check. Fixtures are generated software inputs, not NSD evidence or model results.

Remaining scientific gaps are unchanged: exact original image/session and all-eight-subject pretraining membership; native image and feature preparation and weights; historical SSIM semantics; encoder/checkpoint ancestry and exposure; component rights; author reproduction; paired participant delivery; and separate reproduction/improvement decision rules. No model inference, authentic preparation, candidate trial, reproduction success, improvement success or current-SOTA claim is established.
