"""Paper-grounded inference primitive, not the missing BaRISTA token producer.

Appendix E.3 maps *predicted masked* d=64 tokens through a linear L=512
head. This module consumes already-produced tokens and trained head parameters;
it neither replaces H/G with a callback nor treats classifier latents as H.
Authentic generation, training, query isolation and historical parity are separate.
"""
from dataclasses import dataclass


TOKEN_DIM = 64
PATCH_SAMPLES = 512
PATCHES_PER_SEGMENT = 12
SAMPLES_PER_SEGMENT = 6144


@dataclass(frozen=True)
class MaskedTokenLayout:
    """An ordered one-channel tensor layout, not an authenticity credential."""
    recording: str
    channel_id: str
    segment_ids: tuple
    token_origin: str
    temporal_patch_indices: tuple

    def validate(self):
        if (not isinstance(self.recording, str) or not self.recording
                or not isinstance(self.channel_id, str) or not self.channel_id):
            raise ValueError('Explicit recording and masked channel are required')
        if (type(self.segment_ids) is not tuple or not self.segment_ids
                or any(type(s) is not str or not s for s in self.segment_ids)
                or len(set(self.segment_ids)) != len(self.segment_ids)):
            raise ValueError('Complete unique ordered native segment IDs required')
        if self.token_origin != 'predicted_masked':
            raise ValueError('Observed/classifier tokens cannot be reconstruction targets')
        if (type(self.temporal_patch_indices) is not tuple
                or any(type(i) is not int for i in self.temporal_patch_indices)
                or self.temporal_patch_indices != tuple(range(PATCHES_PER_SEGMENT))):
            raise ValueError('All twelve contiguous native temporal patches required')
        return (len(self.segment_ids), PATCHES_PER_SEGMENT, TOKEN_DIM)


def validate_head_shapes(layout, token_shape, weight_shape, bias_shape, *, use_bias):
    """Check exact source geometry before importing a native tensor library."""
    if type(layout) is not MaskedTokenLayout or type(use_bias) is not bool:
        raise ValueError('Exact layout and explicitly selected head bias are required')
    expected = layout.validate()
    shapes = [token_shape, weight_shape] + ([] if bias_shape is None else [bias_shape])
    if any(type(s) is not tuple or any(type(i) is not int or i <= 0 for i in s)
           for s in shapes):
        raise ValueError('Positive integer tensor shapes required')
    if token_shape != expected or weight_shape != (PATCH_SAMPLES, TOKEN_DIM):
        raise ValueError('Expected complete segment x12x64 tokens and512x64 head')
    if bias_shape != ((PATCH_SAMPLES,) if use_bias else None):
        raise ValueError('Bias presence must match explicit source selection')
    return (len(layout.segment_ids), SAMPLES_PER_SEGMENT)


def project_masked_tokens(tokens, weight, bias, layout, *, use_bias,
                          max_known_tensor_bytes):
    """Apply supplied linear head then concatenate twelve ordered patches.

    No smoothing, normalization, observed-token fallback or fitted state is
    introduced here. Bias is explicit because the supplied source does not
    establish its historical setting. This is inference only. The byte bound
    admits known tensors and finite-check masks, not a native peak/RAM claim.
    """
    if type(max_known_tensor_bytes) is not int or max_known_tensor_bytes <= 0:
        raise ValueError('Explicit known-tensor capacity required')
    if type(layout) is not MaskedTokenLayout:
        raise ValueError('Exact masked token layout required')
    layout.validate()
    # No data/model loading and no arbitrary producer callback are allowed here.
    import torch
    import torch.nn.functional as functional

    values = (tokens, weight) if bias is None else (tokens, weight, bias)
    if any(type(v) not in (torch.Tensor, torch.nn.Parameter) for v in values):
        raise ValueError('Ordinary tensors/parameters are required; no producer proxies')
    output_shape = validate_head_shapes(
        layout, tuple(tokens.shape), tuple(weight.shape),
        None if bias is None else tuple(bias.shape), use_bias=use_bias)
    if any(v.dtype not in (torch.float32, torch.float64) for v in values):
        raise ValueError('Real float32/64 head and token tensors required')
    if any(v.dtype != tokens.dtype or v.device != tokens.device for v in values):
        raise ValueError('All head/token tensors must share dtype and device')
    if any(not v.is_contiguous() for v in values):
        raise ValueError('Contiguous declared tensor layout required')
    input_elements = sum(v.numel() for v in values)
    output_elements = output_shape[0] * output_shape[1]
    # Output reshape is a view; reserve an extra output-sized tensor in case a
    # future backend materializes it. All isfinite masks are conservatively held.
    known_bytes = ((input_elements + 2 * output_elements) * tokens.element_size()
                   + input_elements + output_elements)
    if known_bytes > max_known_tensor_bytes:
        raise ValueError('Known tensor/mask reservation exceeded before projection')
    if any(not bool(torch.isfinite(v).all()) for v in values):
        raise ValueError('No nonfinite token/head values or support filtering')
    with torch.no_grad():
        patches = functional.linear(tokens, weight, bias)
        if tuple(patches.shape) != (output_shape[0], 12, 512):
            raise ValueError('Native head did not preserve full patch support')
        if not bool(torch.isfinite(patches).all()):
            raise ValueError('Nonfinite full-support head output')
        waveform = patches.reshape(output_shape)
    return waveform


def historical_reconstruction_producer():
    """Fail explicitly instead of repurposing the released classifier."""
    raise NotImplementedError(
        'Original H weights/architecture, masked-token generation, training '
        'source and exact reconstruction split identities remain unavailable')


def historical_r2(*args, **kwargs):
    """Rounded Table3 cells cannot determine denominator/flattening rules."""
    raise NotImplementedError('Original reconstruction R2 implementation unavailable')
