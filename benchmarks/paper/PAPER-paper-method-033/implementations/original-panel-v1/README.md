# Original MindBridge Table 2 evaluation

This component connects the source best-of-eight reconstruction choice to **all
48 original findings**: Vanilla and MindBridge, each at 500/1500/4000 calibration
images, each with eight metrics and the complete 982-image target-7 gallery.
It supplies numerical evaluation and an offline metric-transform producer. It
does not generate reconstructions, authenticate original NSD memberships or
weights, execute an AI attempt, or establish scientific qualification.

The existing fixed-index `initial-evaluator-v1` and its prospective control arms
remain unchanged. This component follows the original Table 2 conditions and
reuses the hash-pinned `source-protocol-v2` target-aware selection. That selection
reads the **true target** hidden-token embedding. All eight candidate images must
be frozen before those target features become available to the operator. A JSON
freeze declaration does not implement protected execution or prove its chronology.

## Numerical route

With an existing NumPy/SciPy/scikit-image environment, run:

```sh
python3 panel.py /operator/panel.json /operator/payloads /operator/result.json \
  --packet-sha256 EXACT_PACKET_SHA256 \
  --max-read-bytes APPROVED_CUMULATIVE_READ_BYTES \
  --max-array-bytes APPROVED_SINGLE_ARRAY_BYTES \
  --max-working-bytes APPROVED_ARRAY_WORKSPACE_BYTES
```

The output must not exist. All paths refer to independently provisioned
operator-owned inputs; no data or weights are bundled. The packet is read once
under a 128-MiB bound and explicit expected hash. Every payload is a relative,
hash-and-size-pinned C-order float32/float64 NPY file. The reader rejects pickles,
unsupported headers, trailing bytes, nonfinite values, links and changed files.
It conservatively charges payload extent plus one EOF/growth probe before I/O,
including refused reads. Single arrays are capped at 256 MiB.
The source's full correlation matrix is retained; the conservative workspace
check precedes the corresponding numerical materialization. This check is not an
OS memory limit or a CPU deadline. Authentic execution still needs an admitted
outer controller, resource allocation, natural-exit check and final-feedback policy.

`evaluate_panel(packet, load_array, max_working_bytes=...)` is the same numerical
entry point. Its injected loader is trusted operator infrastructure; only the CLI
provides the packaged file/hash checks. Generated controls can supply invented
arrays through a test loader. Production packets require exactly 982 images.
An explicit `generated_engineering_control` packet may use a smaller gallery and
is permanently labeled as engineering evidence in its result.

The packet fields are:

| Field | Meaning |
| --- | --- |
| `schema`, `task_id` | `mindbridge-original-panel/v1`, `PAPER-paper-method-033` |
| `source_kind` | `operator_prepared_source` or `generated_engineering_control` |
| `test_image_ids` | Unique ordered full gallery; used to align every condition |
| `target_subject`, `source_subjects` | Integer 7 and `[1,2,5]` |
| `calibration` | Keys `500`, `1500`, `4000`; exact-count, lexicographically sorted, nested train-only image prefixes, disjoint from test |
| `skimage_version` | Exact installed version for the literal source SSIM call |
| `feature_pipeline_sha256`, `image_prior_sha256` | Independently authenticated extraction and prior identities; strings alone do not establish them |
| `rows` | Exactly six unique `arm`/`budget` objects; arms `vanilla` and `mindbridge` |

Every row has a `freeze_receipt_sha256`,
`generation_frozen_before_target_selection: true`, and one `images` item per
gallery ID. Each item has `image_id`, `target`, and eight generation-ordered
`candidates`. Each target/candidate payload binds `image_sha256`,
`extraction_receipt_sha256`, a `selection` descriptor, an `rgb425` descriptor, and
six `features` descriptors. A descriptor has exactly `path`, `bytes`, `sha256`.
All six conditions must supply identical target descriptors for a given image.
All packet metadata and all six population/freeze declarations are checked before
any payload is opened. There is no per-metric candidate selection or image dropping.

Selection uses the distinct `(257,768)` hidden-token CLIP representation. One
selected candidate supplies its RGB pixels and every final feature family.
Pixels must already follow the source shorter-edge-425 bilinear transform and
matching target dtype. PixCorr is per-image flattened RGB Pearson correlation.
Four final metrics (`alexnet2`, `alexnet5`, `inception`, `clip`) use float32
extracted features followed by the original full NumPy correlation matrix, strict
predicted-column comparison and denominator 981. Ties receive no credit.
`effnet_b` and `swav` retain their extracted floating dtype and call SciPy paired
correlation distance. Constant vectors and undefined metrics fail instead of
silently reducing the population. Each cell averages its complete image vector;
the component introduces no aggregate across calibration budgets or methods.

## SSIM runtime ambiguity

The author source converts resized RGB to grayscale and then calls SSIM with
`multichannel=True`, `gaussian_weights=True`, `sigma=1.5`,
`use_sample_covariance=False`, and `data_range=1.0`. Its requirements do not pin
scikit-image. In version 0.19.3, the legacy keyword treats the final grayscale
spatial axis as channels; in 0.20.0 it is unused, producing ordinary 2D SSIM.
Those calculations differ.

`image_pair_metrics` preserves the **literal source call** under an explicitly
recorded installed version and refuses a version mismatch. It does not silently
replace the call with `channel_axis=None` or claim the selected installed version
was the author's historical environment. Every result retains
`historical_SSIM_runtime_identity: unresolved`. Recovering that environment or
admitting a precisely named comparison remains necessary before a published-score
reproduction claim. No acceptance tolerance is inferred from printed precision.

## Offline source metric extraction

`native_features.extract_image(image, models, reconstruction=..., target_dtype=...)`
accepts one original CHW tensor and five **already loaded, operator-owned** feature
models. It requires the source-pinned torch 2.0.1 / torchvision 0.15.2, performs
the original bilinear shorter-edge resize with tensor antialiasing disabled,
normalizes, runs those supplied models in no-grad mode, and returns the six metric
vectors plus resized RGB. It never downloads, constructs or loads a model.

The model bank must contain AlexNet V1 features.4/features.11, Inception V3 V1
avgpool with `transform_input=True`, OpenAI CLIP ViT-L/14 `encode_image`,
EfficientNet B1 **V2** avgpool, and the source-selected SwAV ResNet50 avgpool.
The paper's SwAV `main` is not an immutable model pin. Actual architecture/weight
identity, model-state immutability and original exposure remain external checks.
Callable names and array shapes are not evidence of those identities.

All metric paths lack a center crop. Resize sizes are 256/342/224/255/224 for
AlexNet/Inception/CLIP/EfficientNet/SwAV. ImageNet normalization is used except
for CLIP's own mean/SD. Reconstruction clamp and dtype conversion precede the
transforms; the AlexNet reconstruction is cast to float32 before preprocessing.
Four identification features are cast to float32 after extraction; distance
features preserve model dtype. One-image extraction is numerically the source
evaluation-mode operation, but device/batch-shape rounding and native parity
still require validation. This producer does not make the selection embeddings;
those use the separate source Clipper hidden-state path.

## Scientific interpretation and remaining work

Outputs include all 48 identified means, complete per-image vectors and one
selected index per image/condition. They retain unknown reproduction/improvement
and `scientific_qualification: false`. Published targets are not submitted
computations, and the 4000-image CLIP nomination is a benchmark choice.

Remaining requirements include original target-7 train/test/calibration identity,
native neural-to-eight-image generation, authenticated weights and preprocessing,
the unpinned SSIM/SwAV dependencies, protected target-last evaluation, independently
competent author replay, and justified reproduction/superiority/uncertainty rules.
The common feature/pixel packets are compatible with both participant access
conditions, but this component does not itself deliver those participant packages.
No original scientific target, task count, registry readiness or prior evidence is
changed. Tests use generated inputs and explicit mocks where noted, never NSD
images, neural recordings, model weights or scientific scores.

`tests/test_panel.py` covers mathematical metrics, complete 982-image dispatch,
the shared selected image, cohort/calibration/image identities, bounded inputs and native
admission guards. Its full-gallery dispatch mocks selection/pixel operations;
separate tests exercise actual selection and NumPy/SciPy metrics. Literal SSIM
arguments and native-runtime admission are tested with explicit mocks locally.
`tests/test_ssim_backend.py` is a separate mandatory three-control suite for a
reviewed hosted scikit-image 0.25.2 environment. It fails if that version is absent
or different; it never silently skips. Its generated-image numerical check is
evidence for that declared modern backend only. No local real-SSIM or original
torch/torchvision extraction execution has occurred in this construction.
