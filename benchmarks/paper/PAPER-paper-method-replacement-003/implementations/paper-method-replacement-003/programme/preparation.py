"""Actual HDF5 spike/template producer and author-method preprocessing.

Derivative integration of NeuroPyxels 703a10f; GPL-3.0, modified 2026-11-11.
No HDF5, NumPy, Torch or author module is imported until a scientific call.
Invocation requires a separately qualified input/native owner; this module
does not turn paths or a source-census dictionary into that authority.
"""
from c4_distribution.import_guard import require_bound_source as _c4_require_source
from dataclasses import dataclass
from .cohort import Population, SupportError, UnitKey

@dataclass(frozen=True)
class RawUnit:
    key: UnitKey
    source_role: str
    group: str
    sampling_rate: float
    spike_indices: object
    sane_mask: object
    quality_mask: object
    multichannel_template: object
    channel_map: object
    layer: str
    original_dataset_id: str
    original_neuron_id: str

@dataclass(frozen=True)
class PreparedUnit:
    key: UnitKey
    source_role: str
    group: str
    source_spike_sampling_rate: float
    spikes_30khz: object
    source_spikes: object
    waveform: object
    multichannel_template: object
    acg_log_full: object
    layer: str
    disposition: str

def _text(value):
    value = value.item() if hasattr(value, 'item') else value
    return value.decode('utf-8') if isinstance(value, bytes) else str(value)

def load_raw_unit(source_path, member, *, external_quality_policy):
    """Read the exact source group, keeping all aligned operands and identity.

    `external_quality_policy` must explicitly name the release's all-spikes
    Lisberger convention. It is not evidence of automatic monkey QC parity.
    Labels are deliberately not read here: transfer prediction cannot inspect
    expert targets. Original animal/session bindings remain a source-census gate.
    """
    import h5py
    import numpy as np
    member.validate()
    with h5py.File(source_path, 'r') as h:
        g = h[member.h5_group]
        fs = float(g['sampling_rate'][()].item())
        spikes = np.asarray(g['spike_indices'][()]).reshape(-1)
        template = np.asarray(g['mean_waveform_preprocessed'][()])
        channels = np.asarray(g['channelmap'][()])
        dataset = _text(np.asarray(g['dataset_id'][()]).reshape(-1)[0])
        id_field = 'neuron_id' if member.key.species == 'macaque' else 'neuron_relative_id'
        unit = _text(np.asarray(g[id_field][()]).reshape(-1)[0])
        if dataset != member.key.recording or unit != member.key.unit:
            raise SupportError('original HDF5 unit/recording does not match typed source census')
        if member.key.species == 'macaque':
            if external_quality_policy != 'release_lisberger_all_spikes_curator_qc_required':
                raise SupportError('monkey curator/QC policy must be explicit')
            sane = np.ones(len(spikes), dtype=bool)
            quality = np.ones(len(spikes), dtype=bool)
            layer_field = 'human_layer'
        else:
            sane = np.asarray(g['sane_spikes'][()]).reshape(-1)
            quality = np.asarray(g['fn_fp_filtered_spikes'][()]).reshape(-1)
            layer_field = 'phyllum_layer'
        layer = _text(g[layer_field][()])
    if not np.isfinite(fs) or fs <= 0 or spikes.ndim != 1:
        raise SupportError('invalid source clock')
    if spikes.dtype.kind not in 'iu' or np.any(spikes < 0) or np.any(np.diff(spikes) < 0):
        raise SupportError('source spike indices must be ordered nonnegative integers')
    if sane.dtype.kind != 'b' or quality.dtype.kind != 'b' or sane.shape != spikes.shape or quality.shape != spikes.shape:
        raise SupportError('source spike/QC masks are not exactly aligned')
    if template.ndim not in (1, 2) or not np.isfinite(template).all():
        raise SupportError('complete finite source template required')
    return RawUnit(member.key, member.source_role, member.h5_group, fs, spikes,
                   sane, quality, template, channels, layer, dataset, unit)

def prepare_unit(raw, *, spike_clock_policy, single_channel_policy):
    """Actual author cropping/conformation and full log-ACG recomputation.

    Original release ACG augmentation assumes 30 kHz. Only the 30 kHz training
    population can use that path. Transfer ACGs retain their original clock.
    Input templates are source-provided *preprocessed* mean waveforms. This is
    not a producer for missing raw-voltage drift matching or hardware filtering.
    """
    _c4_require_source()
    import numpy as np
    _c4_require_source()
    from npyx import datasets, corr
    selected = raw.spike_indices[raw.sane_mask & raw.quality_mask]
    if len(selected) < 2:
        raise SupportError('insufficient QC-retained spikes; keep unit disposition')
    if spike_clock_policy != 'literal_source_clock':
        raise SupportError('unselected spike clock transformation')
    spikes = selected.copy() if raw.sampling_rate == 30000 else None
    waveform = np.asarray(raw.multichannel_template)
    if waveform.ndim == 1:
        if single_channel_policy != 'release_tile_single_channel':
            raise SupportError('single-channel tiling policy must be explicit')
        waveform = np.tile(waveform, (10, 1))
    elif waveform.shape[0] > waveform.shape[1]:
        waveform = waveform.T
    if waveform.shape[0] < 10:
        if single_channel_policy != 'release_tile_single_channel':
            raise SupportError('insufficient channels; release decay-padding not selected')
        waveform = datasets.pad_matrix_with_decay(waveform, 10)
    peak = np.argmax(np.ptp(waveform, axis=1))
    conformed = datasets.preprocess_template(waveform[peak], raw.sampling_rate,
                                            output_sampling_rate=30000, peak_sign='negative')
    source_window = int(120 * raw.sampling_rate / 30000)
    cropped, _ = datasets.crop_original_wave(waveform, source_window, 10)
    if raw.sampling_rate != 30000:
        # Matches the release's image-resize route for augmentation templates;
        # conformed peak wave above uses the independent author resample route.
        import torch
        from torchvision.transforms import Resize
        cropped = Resize((10, 120))(torch.as_tensor(cropped).reshape(1, 10, source_window)).numpy()[0]
    _, acg = corr.crosscorr_vs_firing_rate(selected, selected, fs=raw.sampling_rate,
                                         win_size=2000, bin_size=1)
    acg, _ = corr.convert_acg_log(acg, 1, 2000)
    if conformed.shape != (90,) or cropped.shape != (10, 120) or acg.shape != (10, 201):
        raise SupportError('source representation extent mismatch')
    if not all(np.isfinite(x).all() for x in (conformed, cropped, acg)):
        raise SupportError('undefined preprocessing output; cannot replace with invented features')
    return PreparedUnit(raw.key, raw.source_role, raw.group, raw.sampling_rate,
                        spikes, selected, conformed, cropped, acg * 10,
                        raw.layer, 'eligible_source_prepared')

def source_training_matrix(prepared, *, waveform_augmentation):
    """Retain raw spike trains and multi-channel templates into augmentation."""
    import numpy as np
    if len({u.key for u in prepared}) != len(prepared):
        raise SupportError('duplicate prepared unit')
    if waveform_augmentation and any(u.spikes_30khz is None for u in prepared):
        raise SupportError('released training augmentation requires actual 30 kHz spike clocks')
    matrix = np.stack([np.concatenate((u.acg_log_full.ravel(),
                      u.multichannel_template.ravel() if waveform_augmentation else u.waveform))
                       for u in prepared])
    return matrix, [u.spikes_30khz for u in prepared], tuple(u.key for u in prepared)
