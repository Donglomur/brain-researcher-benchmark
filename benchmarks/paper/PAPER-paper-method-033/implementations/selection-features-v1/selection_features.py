"""Offline MindBridge selection tokens from an already loaded vision encoder.

This is the target-aware SELECTION representation, not final-metric CLIP.
It does not construct/download models, load checkpoints, generate candidates,
authenticate weights, or enforce a protected target-last evaluation boundary.
"""
from __future__ import annotations

TASK_ID = "PAPER-paper-method-033"
CLIP_MEAN = (0.48145466, 0.4578275, 0.40821073)
CLIP_STD = (0.26862954, 0.26130258, 0.27577711)
TOKEN_SHAPE = (1, 257, 768)


class SelectionFeatureError(ValueError):
    """The supplied operator inputs do not implement the declared source path."""


def require_runtime(expected_transformers_version):
    """Require source-pinned tensor transforms and an explicit HF runtime choice.

    The author did not pin Transformers. An exact caller-declared installed
    version is recorded, never presented as the historical author version.
    """
    if (type(expected_transformers_version) is not str
            or not expected_transformers_version.strip()
            or len(expected_transformers_version) > 128):
        raise SelectionFeatureError("an explicit Transformers version is required")
    import torch
    import torchvision
    import transformers
    if (torch.__version__.split("+", 1)[0] != "2.0.1"
            or torchvision.__version__.split("+", 1)[0] != "0.15.2"):
        raise SelectionFeatureError("requires torch2.0.1 and torchvision0.15.2")
    if transformers.__version__ != expected_transformers_version:
        raise SelectionFeatureError("installed Transformers version differs from declaration")
    if torch.is_autocast_enabled() or torch.is_autocast_cpu_enabled():
        raise SelectionFeatureError("source extraction does not use autocast")
    return torch, torchvision, transformers


def _finite_tensor(torch, value, expected_shape, name):
    if (not isinstance(value, torch.Tensor)
            or tuple(value.shape) != expected_shape
            or not value.is_floating_point()
            or value.dtype not in (torch.float32, torch.float64)
            or not bool(torch.isfinite(value).all())):
        raise SelectionFeatureError(name + " has an unsupported shape, dtype or value")


def extract_selection_features(image, encoder, *, image_role,
                               expected_transformers_version, max_input_pixels):
    """Produce one (257,768) selection-token array without loading any model.

    ``image`` is an RGB CHW tensor in [0,1]. ``encoder`` must already be a frozen
    evaluation-mode Hugging Face CLIPVisionModelWithProjection with the source
    ViT-L/14 geometry. A model class/configuration does not authenticate weights.

    All eight candidate images must be frozen by a separately admitted operator
    before target-image extraction or selection. This per-image utility neither
    receives nor certifies that chronology. Target dtype is preserved; candidate
    input is cast to float32, as the source reconstruction selector does.

    max_input_pixels is an explicit operator admission bound, not a new source
    image size or an OS memory limit. No resize is used to evade this bound.
    """
    if image_role not in ("target", "candidate") or type(image_role) is not str:
        raise SelectionFeatureError("explicit target or candidate role required")
    if type(max_input_pixels) is not int or max_input_pixels <= 0:
        raise SelectionFeatureError("a positive integer input-pixel bound is required")
    torch, torchvision, transformers = require_runtime(expected_transformers_version)
    if (not isinstance(image, torch.Tensor) or image.ndim != 3
            or image.shape[0] != 3 or image.shape[1] <= 0 or image.shape[2] <= 0
            or image.shape[1] * image.shape[2] > max_input_pixels
            or not image.is_floating_point() or not bool(torch.isfinite(image).all())):
        raise SelectionFeatureError("one bounded finite floating RGB CHW image required")
    if image_role == "target" and image.dtype not in (torch.float32, torch.float64):
        raise SelectionFeatureError("target float32/float64 dtype must be preserved")
    if bool((image < 0).any()) or bool((image > 1).any()):
        raise SelectionFeatureError("image must already be in [0,1]; no silent clamp/rescale")
    if not isinstance(encoder, transformers.CLIPVisionModelWithProjection):
        raise SelectionFeatureError("a preloaded CLIPVisionModelWithProjection is required")
    config = encoder.config
    expected = {"image_size": 224, "patch_size": 14, "hidden_size": 1024,
                "projection_dim": 768}
    if any(type(getattr(config, key, None)) is not int or getattr(config, key) != value
           for key, value in expected.items()):
        raise SelectionFeatureError("encoder configuration does not match ViT-L/14")
    if any(module.training for module in encoder.modules()):
        raise SelectionFeatureError("all encoder modules must already be in evaluation mode")
    parameters = list(encoder.parameters())
    if not parameters or any(parameter.requires_grad for parameter in parameters):
        raise SelectionFeatureError("encoder parameters must already be frozen")
    device = parameters[0].device
    if any(parameter.device != device for parameter in parameters):
        raise SelectionFeatureError("encoder parameters span multiple devices")
    # from_pretrained in the selected author source has no dtype override.
    if any(parameter.dtype != torch.float32 for parameter in parameters):
        raise SelectionFeatureError("source vision encoder parameters must be float32")

    transforms = torchvision.transforms
    with torch.no_grad():
        pixels = image.float() if image_role == "candidate" else image
        pixels = pixels.to(device).unsqueeze(0)
        pixels = transforms.Resize(224, interpolation=transforms.InterpolationMode.BICUBIC,
                                   antialias=None)(pixels)
        pixels = transforms.CenterCrop((224, 224))(pixels)
        pixels = transforms.Normalize(mean=CLIP_MEAN, std=CLIP_STD)(pixels)
        output = encoder(pixels)
        hidden = getattr(output, "last_hidden_state", None)
        _finite_tensor(torch, hidden, (1, 257, 1024), "vision hidden state")
        normalized = encoder.vision_model.post_layernorm(hidden)
        _finite_tensor(torch, normalized, (1, 257, 1024), "post-layernorm hidden state")
        projected = encoder.visual_projection(normalized)
        _finite_tensor(torch, projected, TOKEN_SHAPE, "projected vision tokens")
        cls_norm = torch.norm(projected[:, 0], dim=-1)
        if not bool(torch.isfinite(cls_norm).all()) or bool((cls_norm <= 0).any()):
            raise SelectionFeatureError("CLS norm is zero or nonfinite")
        # Divide EVERY token by the single CLS norm. This is deliberately not
        # independent per-token normalization and has no epsilon substitution.
        tokens = projected / cls_norm.reshape(-1, 1, 1)
        _finite_tensor(torch, tokens, TOKEN_SHAPE, "CLS-scaled selection tokens")
        result = tokens[0].detach().cpu().numpy().copy()
    return {
        "schema": "mindbridge-selection-features/v1",
        "task_id": TASK_ID,
        "image_role": image_role,
        "selection": result,
        "runtime": {"torch": torch.__version__, "torchvision": torchvision.__version__,
                    "transformers": transformers.__version__},
        "historical_transformers_runtime_identity": "unresolved",
        "model_weight_identity_verified": False,
        "generation_freeze_or_target_isolation_verified": False,
        "scientific_qualification": False,
    }
