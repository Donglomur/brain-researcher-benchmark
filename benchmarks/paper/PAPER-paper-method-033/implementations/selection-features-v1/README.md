# MindBridge selection-feature producer

`selection_features.extract_selection_features` fills the missing offline
producer for the `(257,768)` hidden-token representation consumed by the existing
`source-protocol-v2` selector and `original-panel-v1` evaluator. It is distinct
from the final CLIP identification metric. Existing task contracts, components,
source files, readiness and scientific endpoints remain unchanged.

Supply one finite RGB CHW tensor in `[0,1]`, an already loaded/frozen/evaluation-mode
Hugging Face `CLIPVisionModelWithProjection`, an explicit `target` or `candidate`
role, the exact installed Transformers version and an input-pixel resource bound.
The encoder must have ViT-L/14 geometry and float32 parameters. The implementation
never constructs a model, loads a checkpoint, downloads a weight or generates an
image. The returned `selection` array can be serialized by an independently
admitted operator into the existing panel's pinned NPY descriptor.

The selected author path applies bicubic shorter-edge224 resize, center crop,
CLIP normalization, vision hidden states, post-layer normalization and visual
projection, followed by scaling every token by the CLS norm. Candidate pixels
are cast to float32 before extraction; target pixel dtype is preserved. No
`[-1,1]` conversion, final-metric `encode_image`, independent token normalization,
clamp or epsilon replacement is introduced. These operations are grounded in
[models.py](https://raw.githubusercontent.com/littlepure2333/MindBridge/2a3943ff5b619db6f85f16a5e7ff1331d25def55/src/models.py),
[recon.py](https://raw.githubusercontent.com/littlepure2333/MindBridge/2a3943ff5b619db6f85f16a5e7ff1331d25def55/src/recon.py),
and [utils.py](https://raw.githubusercontent.com/littlepure2333/MindBridge/2a3943ff5b619db6f85f16a5e7ff1331d25def55/src/utils.py).

Tensor transforms require the source-pinned torch2.0.1/torchvision0.15.2.
`antialias=None` is retained explicitly; for tensors this means no antialiasing
in that torchvision version. See the
[versioned Resize implementation](https://raw.githubusercontent.com/pytorch/vision/v0.15.2/torchvision/transforms/transforms.py).
Transformers was not pinned by the author. The caller must declare the exact
installed version, and results always retain its historical identity as
unresolved. Matching model classes/configurations and array shapes do not
authenticate weights or establish original-device numerical parity.

This is an operator utility, not an isolation boundary. All eight candidate
images and generation inputs must be irreversibly frozen before any target
feature or target-derived index is exposed. A caller role or returned status
does not establish that chronology. The function performs no selection or
scoring and cannot make an image bank, split, baseline or complete benchmark
ready. The original full982-image, two-arm, three-budget,48-cell panel is retained.

Generated tests use NumPy-backed tensor/model/transform doubles. They exercise
call ordering, candidate casting, shared CLS normalization, invalid-data and
runtime/model guards. They do **not** execute Torch transforms, Hugging Face
inference, original images, native model weights or a scientific evaluation.
No generated-control result is a native extraction parity claim.

Run the necessary checks through the existing approved two-slot pool with
`python3 -I -B tests/test_selection_features.py`. They require NumPy only;
no dependency installation or network is performed. A separate admitted
source-runtime/native validation remains necessary before actual extraction.
