"""Concrete F -> mask+E -> G -> H -> waveform reconstruction path.

No model is executed on import. make_reconstructor uses the captured official
Barista class; it does not accept an arbitrary H or latent-producing callback.
Authentic weights/data are future inputs, not bundled or read by this source.
"""
from .design import ReferenceConfig, model_scales
from copy import deepcopy


def sanitize_context(x, channel_mask):
    """Mask raw targets BEFORE calling any tokenizer or model component.

    x: batch x6144xchannels, channel_mask: batch xchannels bool. A cloned context
    prevents in-place modification of held targets used only after prediction.
    """
    import torch
    if x.ndim != 3 or x.shape[1] != 6144 or x.shape[2] < 2:
        raise ValueError('Complete batch x6144xchannels waveform required')
    if channel_mask.shape != (x.shape[0], x.shape[2]) or channel_mask.dtype != torch.bool:
        raise ValueError('Explicit per-example boolean channel mask required')
    if not bool(channel_mask.any(dim=1).all()) or not bool((~channel_mask).any(dim=1).all()):
        raise ValueError('Each example needs masked targets and observed context')
    if x.dtype not in (torch.float32, torch.float64) or x.device != channel_mask.device:
        raise ValueError('Finite real waveforms and same-device boolean mask required')
    if not bool(torch.isfinite(x).all()):
        raise ValueError('Nonfinite waveform support cannot be dropped')
    context = x.clone()
    context.masked_fill_(channel_mask[:, None, :], 0.0)
    return context


def reconstruction_loss(predicted, observed, targets, mask, alpha):
    """Paper E.3: sum of squared512-sample errors / token count, each branch.

    predicted/observed/targets are batch x12xchannels x512; mask is batch xchannels.
    Observed predictions use F tokens directly, targets use H(G(mask+E,context)).
    Never mean across the512 waveform samples; no R2 is computed here.
    """
    import torch
    if predicted.shape != targets.shape or observed.shape != targets.shape:
        raise ValueError('Predicted/observed/target support must match exactly')
    if targets.ndim != 4 or targets.shape[1] != 12 or targets.shape[-1] != 512:
        raise ValueError('Full twelve512-sample patch support required')
    if mask.shape != (targets.shape[0], targets.shape[2]) or mask.dtype != torch.bool:
        raise ValueError('Exact boolean channel mask required')
    if not 0 <= alpha <= 1:
        raise ValueError('Auxiliary loss weight must be in[0,1]')
    expanded = mask[:, None, :].expand(-1, 12, -1)
    if not bool(expanded.any()) or not bool((~expanded).any()):
        raise ValueError('Nonempty masked and observed token supports required')
    target_loss = ((predicted - targets).square().sum(dim=-1))[expanded].mean()
    observed_loss = ((observed - targets).square().sum(dim=-1))[~expanded].mean()
    total = target_loss + alpha * observed_loss
    if not bool(torch.isfinite(total)):
        raise ValueError('Nonfinite loss; no support filtering')
    return total, target_loss, observed_loss


def make_reconstructor(model_config, metadata, model_name, config, *,
                       initialization, backbone_state=None, retained_h_state=None,
                       retained_mask=None):
    """Instantiate actual official F/G plus this explicit concrete H and linear head.

    initialization: random_all, pretrained_FG_fresh_H, or bound_FGH. State dicts
    must already be authenticated outside this function. No implicit file loader,
    network, missing-key fallback, or inferred checkpoint compatibility occurs.
    bound_FGH binds this configured architecture; it does NOT prove historical H.
    """
    config.validate()
    encoding_scale, _ = model_scales(model_name)
    permitted = ('random_all', 'pretrained_FG_fresh_H', 'bound_FGH')
    if initialization not in permitted:
        raise ValueError('Explicit initialization track required')
    if model_name.startswith('random_') != (initialization == 'random_all'):
        raise ValueError('Random controls and pretrained model labels cannot be swapped')
    if initialization == 'random_all' and backbone_state is not None:
        raise ValueError('Random control cannot receive pretrained F/G')
    if initialization != 'random_all' and backbone_state is None:
        raise ValueError('Pretrained F/G state required, without classifier fallback')
    if initialization == 'bound_FGH':
        if retained_h_state is None or retained_mask is None:
            raise ValueError('Bound-H track requires complete H and mask state')
    elif retained_h_state is not None or retained_mask is not None:
        raise ValueError('Fresh-H track cannot silently consume retained H/mask')
    # These literal spatial names are present in the official configuration and
    # metadata source. Caller must supply matching metadata, not relabel a model.
    expected_grouping = {'channels': 'coords', 'parcels': 'destrieux', 'lobes': 'lobes'}[encoding_scale]
    if model_config.tokenizer.spatial_grouping != expected_grouping:
        raise ValueError('Encoding scale must match the official tokenizer configuration')
    if (model_config.backbone.d_hidden != 64
            or model_config.backbone.num_layers != 12
            or model_config.backbone.num_heads != 4
            or model_config.tokenizer.temporal_subsegment_len != 512
            or model_config.tokenizer.temporal_subsegment_step != 512
            or model_config.tokenizer.samp_frequency != 2048
            or model_config.tokenizer.num_seconds != 3
            or not model_config.tokenizer.add_spatial_encoding):
        raise ValueError('Original F/G and token geometry required')
    expected_backbone = {'d_input':64, 'd_out':64, 'mlp_ratio':4,
                         'norm':'rmsnorm', 'norm_eps':1e-8, 'activation':'gelu',
                         'max_position':1024, 'dropout':0.1}
    if any(getattr(model_config.backbone,k) != v for k,v in expected_backbone.items()):
        raise ValueError('The released12-layer G configuration is fixed in this track')
    expected_temporal = {'hidden_dims':5, 'depth':4, 'kernel_size':3, 'stride':1}
    if any(getattr(model_config.tokenizer.temporal_encoder,k) != v
           for k,v in expected_temporal.items()):
        raise ValueError('The released five-block temporal CNN configuration is fixed')
    import torch
    from torch import nn
    from barista.models.model import Barista

    class Reconstruction(nn.Module):
        def __init__(self):
            super().__init__()
            self.base = Barista(deepcopy(model_config), metadata)
            if backbone_state is not None:
                self.base.load_state_dict(backbone_state, strict=True)
            layers = []
            for i, (a, b) in enumerate(zip(config.h_widths, config.h_widths[1:])):
                layers.extend([nn.Linear(a, b, bias=config.h_bias), nn.GELU()])
                if i < len(config.h_widths) - 2:
                    layers.append(nn.Dropout(config.dropout))
            self.h = nn.Sequential(*layers)
            self.mask_token = nn.Parameter(torch.zeros(64))
            self.waveform_head = nn.Linear(64, 512, bias=config.head_bias)
            if initialization == 'bound_FGH':
                self.h.load_state_dict(retained_h_state, strict=True)
                if (tuple(retained_mask.shape) != (64,)
                        or not bool(torch.isfinite(retained_mask).all())):
                    raise ValueError('Finite bound mask token64 required')
                with torch.no_grad():
                    self.mask_token.copy_(retained_mask)
            self.reference_config = config
            self.model_name = model_name
            self.initialization = initialization
            self.history = []
            self.fitted_training_ids = None

        def forward(self, x, channel_mask, recording):
            context = sanitize_context(x, channel_mask)
            batch, _, channels = context.shape
            item = self.base.tokenizer([context], [recording] * batch,
                                       output_as_list=False,
                                       add_spatial_encoding_to_tokens=False)
            expected = (1, batch * 12 * channels, 64)
            if (tuple(item.tokens.shape) != expected
                    or tuple(item.spatial_embeddings.shape) != expected
                    or item.seq_lens != [12 * channels] * batch):
                raise ValueError('Official concatenated time-space token layout required')
            token_mask = channel_mask[:, None, :].expand(-1, 12, -1).reshape(1, -1, 1)
            mixed = torch.where(token_mask, self.mask_token.reshape(1, 1, 64), item.tokens)
            # E is added exactly once, including at masked positions.
            latent = self.base.backbone(x=mixed + item.spatial_embeddings,
                                        seq_lens=item.seq_lens,
                                        position_ids=item.position_ids)
            if tuple(latent.shape) != expected:
                raise ValueError('G must preserve all ordered token support')
            predicted_tokens = self.h(latent).reshape(batch, 12, channels, 64)
            predicted = self.waveform_head(predicted_tokens)
            observed = self.waveform_head(item.tokens).reshape(batch, 12, channels, 512)
            if not bool(torch.isfinite(predicted).all()) or not bool(torch.isfinite(observed).all()):
                raise ValueError('Nonfinite reconstruction; no partial output')
            return predicted, observed

    # fork_rng prevents building one cell from changing unrelated CPU RNG state.
    # Native GPU determinism remains a runtime property, not promised by seed alone.
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(config.seed)
        model = Reconstruction()
    return model
