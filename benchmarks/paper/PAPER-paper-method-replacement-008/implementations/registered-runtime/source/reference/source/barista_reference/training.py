"""Actual20-epoch training caller and isolated one-channel inference caller.

These functions are future scientific execution, not an instruction to run now.
No private target is accepted by predict_channel. fit_cell accepts training only.
"""
import random
from .design import (ARMS, NATIVE_SESSIONS, choose_group_mask, epoch_schedule,
                     model_scales, validate_session)
from .producer import reconstruction_loss


def optimizer_groups(model):
    """Partition each trainable parameter exactly once; H/mask belong with F/G."""
    config = model.reference_config
    config.validate()
    upstream = [*model.base.parameters(), *model.h.parameters(), model.mask_token]
    head = list(model.waveform_head.parameters())
    all_params = upstream + head
    if (len({id(p) for p in all_params}) != len(all_params)
            or {id(p) for p in model.parameters()} != {id(p) for p in all_params}
            or any(not p.requires_grad for p in all_params)):
        raise ValueError('Every F/G/H/mask/head parameter must be trained exactly once')
    return [{'params': upstream, 'lr': config.pretrained_lr, 'name': 'FGH_mask'},
            {'params': head, 'lr': config.head_lr, 'name': 'waveform_head'}]


def _validate_model_session(model, session):
    validate_session(session)
    native = NATIVE_SESSIONS[session['person']]
    sizes = model.base.metadata.get_subject_session_d_input()
    if sizes.get(native) != len(session['channels']):
        raise ValueError('Official metadata session/channel support must agree')
    for scale, name in (('parcels', 'destrieux'), ('lobes', 'lobes')):
        native_groups = model.base.metadata.get_spatial_grouping(native, name)
        if (native_groups is None or tuple(str(g) for g in native_groups.group_ids)
                != session['groups'][scale]):
            raise ValueError('Mask groups must match the supplied official metadata')
    return native


def fit_cell(model, session, train_waveforms, train_segment_ids, *, arm):
    """Full training split only; no validation/test arrays are accepted or selected.

    Select last epoch, not best test/validation outcome. Each example receives a
    seeded whole-group mask. Losses are diagnostics, not scientific benchmark
    scores. Batch size32 and fresh H/mask choices are declared in the config.
    """
    import torch
    native = _validate_model_session(model, session)
    if arm not in ARMS or train_segment_ids != session['splits']['train']:
        raise ValueError('Explicit access arm and exact ordered training identities required')
    if tuple(train_waveforms.shape) != (len(train_segment_ids), 6144, len(session['channels'])):
        raise ValueError('Full training waveform support required')
    if model.fitted_training_ids is not None:
        raise ValueError('Do not reuse fitted state across cells or arms')
    config = model.reference_config
    config.validate()
    _, masking_scale = model_scales(model.model_name)
    groups = session['groups'][masking_scale]
    optimizer = torch.optim.AdamW(optimizer_groups(model), lr=config.pretrained_lr,
                                 betas=config.adam_betas, eps=config.adam_eps,
                                 weight_decay=config.weight_decay)
    # Seed dropout and shuffling explicitly; this loop owns its training RNG.
    torch.manual_seed(config.seed)
    rng = random.Random(config.seed)
    model.history = []
    model.train()
    for epoch in range(config.epochs):
        schedule = epoch_schedule(epoch, config)
        for group, rate in zip(optimizer.param_groups,
                               (schedule['pretrained_lr'], schedule['head_lr'])):
            group['lr'] = rate
        indices = list(range(len(train_segment_ids)))
        rng.shuffle(indices)
        loss_sum = 0.0
        masked_channels = 0
        for start in range(0, len(indices), config.batch_size):
            batch_ids = indices[start:start + config.batch_size]
            batch = train_waveforms[batch_ids]
            masks = [choose_group_mask(groups, rng.randrange(2**32)) for _ in batch_ids]
            mask = torch.tensor(masks, dtype=torch.bool, device=batch.device)
            optimizer.zero_grad(set_to_none=True)
            predicted, observed = model(batch, mask, native)
            # Only after forward has received sanitized context do targets enter
            # the loss. Layout exactly inverts original (batch,time,channel) data.
            targets = batch.reshape(len(batch_ids), 12, 512, batch.shape[-1]).permute(0, 1, 3, 2)
            loss, _, _ = reconstruction_loss(predicted, observed, targets, mask,
                                              schedule['alpha'])
            loss.backward()
            if any(p.grad is not None and not bool(torch.isfinite(p.grad).all())
                   for p in model.parameters()):
                raise ValueError('Nonfinite gradient; no optimizer step or output')
            optimizer.step()
            loss_sum += float(loss.detach().cpu()) * len(batch_ids)
            masked_channels += sum(sum(m) for m in masks)
        model.history.append({'epoch': epoch, **schedule,
                              'training_loss': loss_sum / len(indices),
                              'realized_masked_token_fraction': masked_channels /
                                  (len(indices) * len(session['channels']))})
    # Assign only after all20 epochs complete. An interrupted model cannot predict.
    model.fitted_training_ids = tuple(train_segment_ids)
    model.fitted_cell = (arm, model.model_name, session['person'])
    model.eval()
    return tuple(model.history)


def predict_channel(model, session, observed_waveforms, observed_channel_ids,
                    test_segment_ids, target_channel_id, *, arm):
    """Yield ordered batch predictions for one masked channel, without its values.

    Input contains C-1 observed channels, never the held target waveform. Only
    the fixed test split can be queried; no fit/update/loss call exists here.
    Output batches concatenate to test_segments x6144, the existing MSE contract.
    """
    import torch
    native = _validate_model_session(model, session)
    channels = session['channels']
    if target_channel_id not in channels:
        raise ValueError('Exact target channel identity required')
    target_index = channels.index(target_channel_id)
    expected_observed = tuple(c for c in channels if c != target_channel_id)
    if observed_channel_ids != expected_observed or test_segment_ids != session['splits']['test']:
        raise ValueError('Exact ordered test and observed channel identities required')
    if (model.fitted_training_ids != session['splits']['train']
            or getattr(model, 'fitted_cell', None) != (arm, model.model_name, session['person'])):
        raise ValueError('This exact cell must finish training before test prediction')
    if tuple(observed_waveforms.shape) != (len(test_segment_ids), 6144, len(expected_observed)):
        raise ValueError('Complete C-1 observed waveform support required')
    if (observed_waveforms.dtype not in (torch.float32, torch.float64)
            or not bool(torch.isfinite(observed_waveforms).all())):
        raise ValueError('Finite observed waveform support required')
    model.eval()
    observed_indices = [i for i in range(len(channels)) if i != target_index]
    with torch.no_grad():
        for start in range(0, len(test_segment_ids), model.reference_config.batch_size):
            observed = observed_waveforms[start:start + model.reference_config.batch_size]
            full = observed.new_zeros((observed.shape[0], 6144, len(channels)))
            full[:, :, observed_indices] = observed
            mask = torch.zeros((observed.shape[0], len(channels)), dtype=torch.bool,
                               device=observed.device)
            mask[:, target_index] = True
            predicted, _ = model(full, mask, native)
            yield predicted[:, :, target_index, :].reshape(observed.shape[0], 6144)
