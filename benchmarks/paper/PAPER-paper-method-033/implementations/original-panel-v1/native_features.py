"""Offline source metric transforms for already loaded, operator-owned models.

No network, model constructor, weight loading or generation is performed here.
Model architecture, complete weight hashes and exposure remain operator admission
requirements. The five supplied models must expose the outputs documented below.
"""
from __future__ import annotations

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)
CLIP_MEAN = (0.48145466, 0.4578275, 0.40821073)
CLIP_STD = (0.26862954, 0.26130258, 0.27577711)
MODEL_REQUIREMENTS = {
    'alexnet': 'torchvision AlexNet IMAGENET1K_V1; outputs features.4 and features.11',
    'inception': 'torchvision InceptionV3 IMAGENET1K_V1; transform_input=True; output avgpool',
    'clip': 'OpenAI CLIP ViT-L/14 encode_image; final projected embedding',
    'effnet': 'torchvision EfficientNetB1 IMAGENET1K_V2; output avgpool',
    'swav': 'source-selected SwAV ResNet50; immutable code/weights unresolved; output avgpool',
}


def require_source_runtime():
    import torch
    import torchvision
    # Local build suffixes describe packaging, not the source library version.
    if torch.__version__.split('+', 1)[0] != '2.0.1' or torchvision.__version__.split('+', 1)[0] != '0.15.2':
        raise ValueError('source metric transforms require torch2.0.1 and torchvision0.15.2')
    return torch, torchvision


def extract_image(image, models, *, reconstruction, target_dtype):
    """Produce the six final metric vectors and 425-shorter-edge pixel tensor.

    ``image`` is one CHW floating tensor; ``models`` contains five already loaded,
    evaluation-mode callables on the same device. AlexNet/Inception/EfficientNet/
    SwAV are feature extractors; CLIP is its encode_image bound callable. This is
    the *metric* pipeline, never the 257x768 hidden-state selection pipeline.

    The caller must authenticate that these are the declared source architectures
    and weights. A callable or returned shape cannot establish model identity.
    """
    torch, torchvision = require_source_runtime()
    from torchvision import transforms
    if set(models) != set(MODEL_REQUIREMENTS) or type(reconstruction) is not bool:
        raise ValueError('complete source model bank and explicit image role required')
    for model in models.values():
        owner = getattr(model, '__self__', model)
        if getattr(owner, 'training', False):
            raise ValueError('source feature models must already be in evaluation mode')
    if (not isinstance(image, torch.Tensor) or image.ndim != 3 or image.shape[0] != 3
            or not image.is_floating_point() or not bool(torch.isfinite(image).all())
            or target_dtype not in (torch.float32, torch.float64)):
        raise ValueError('one finite floating RGB image and original target dtype required')
    # Source casts/clamps only reconstructions. Reference values are not clamped
    # or silently recast here; admission establishes original [0,1] stimuli.
    if reconstruction:
        image = image.to(target_dtype).clamp(0, 1)
    elif image.dtype != target_dtype:
        raise ValueError('reference image dtype must equal original target dtype')
    if bool((image < 0).any()) or bool((image > 1).any()):
        raise ValueError('source stimulus/processed reconstruction must be in [0,1]')

    def resize(size, value=None):
        # torchvision0.15.2's omitted antialias maps to False for tensor inputs.
        # Integer size preserves aspect ratio; there is no metric center crop.
        return transforms.Resize(size, interpolation=transforms.InterpolationMode.BILINEAR,
                                 antialias=False)(image if value is None else value)

    def normalized(size, mean=IMAGENET_MEAN, std=IMAGENET_STD, value=None):
        return transforms.Normalize(mean=mean, std=std)(resize(size, value)).unsqueeze(0)

    with torch.no_grad():
        pixels = resize(425).detach().cpu().numpy()
        # Source explicitly casts the AlexNet reconstruction input to float32.
        alex_input = normalized(256, value=image.float() if reconstruction else image)
        alex = models['alexnet'](alex_input)
        inception = models['inception'](normalized(342))
        clip = models['clip'](normalized(224, CLIP_MEAN, CLIP_STD))
        effnet = models['effnet'](normalized(255))
        swav = models['swav'](normalized(224))
        outputs = {'alexnet2': alex['features.4'], 'alexnet5': alex['features.11'],
                   'inception': inception['avgpool'], 'clip': clip,
                   'effnet_b': effnet['avgpool'], 'swav': swav['avgpool']}
        result = {}
        for metric, tensor in outputs.items():
            if (not isinstance(tensor, torch.Tensor) or tensor.ndim < 2 or tensor.shape[0] != 1
                    or not tensor.is_floating_point() or not bool(torch.isfinite(tensor).all())):
                raise ValueError('finite one-image feature output required for ' + metric)
            if metric in ('alexnet2', 'alexnet5', 'inception', 'clip'):
                tensor = tensor.float()
            result[metric] = tensor.detach().reshape(-1).cpu().numpy()
    return {'rgb425': pixels, 'features': result,
            'runtime': {'torch': torch.__version__, 'torchvision': torchvision.__version__},
            'source_weight_identity_verified_by_this_function': False}
