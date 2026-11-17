"""Actual complete-support waveform consumers; historical caller is separate.

These functions receive preprocessed voltage and genuine pyKilosort estimates.
They do not infer raw preprocessing, estimated events, source identities or clocks.
All array operations are definitions only in BUILD.
"""
from .common import require, Unavailable


def waveform_depth_means(voltage, sample_indices, unit_indices, event_depths,
                         unit_ids, channel_indices, depth_edges, waveform_offsets,
                         *, edge_policy, count_boundary, budget):
    import numpy as np
    require(voltage.ndim == 2, 'voltage-sample-channel-axes')
    require(len(sample_indices) == len(unit_indices) == len(event_depths), 'event-axis-join')
    require(len(depth_edges) == 21 and np.all(np.diff(depth_edges) == 2), 'twenty-2um-depth-bins')
    require(edge_policy in {'left-closed-right-open', 'left-closed-final-inclusive'},
            'unselected-depth-boundary-policy')
    require(count_boundary in {'greater-than-50','greater-or-equal-50'},'unselected-count-boundary')
    require(len(set(unit_ids)) == len(unit_ids) and len(unit_ids) > 0, 'unit-support')
    require(sample_indices.dtype.kind in 'iu' and unit_indices.dtype.kind in 'iu', 'integer-event-indices')
    require(np.all(np.diff(sample_indices) >= 0), 'unsorted-original-events')
    require(np.all((unit_indices >= 0) & (unit_indices < len(unit_ids))), 'unit-index-outside-roster')
    require(len(waveform_offsets) > 0 and np.all(np.diff(waveform_offsets) == 1), 'contiguous-waveform-support')
    require(np.all(np.isfinite(event_depths)), 'undefined-event-depth')
    require(len(channel_indices)==len(unit_ids) and len({len(row) for row in channel_indices})==1,
            'per-unit-channel-support')
    n, t, c = len(unit_ids), len(waveform_offsets), len(channel_indices[0])
    require(c>0 and all(len(set(row))==c and min(row)>=0 and max(row)<voltage.shape[1]
                        for row in channel_indices),'channel-support')
    budget.charge('array', n * 20 * t * c * 8 + n * 20 * 8)
    sums = np.zeros((n, 20, t, c), dtype='float64')
    counts = np.zeros((n, 20), dtype='int64')
    # No favorable edge-event pruning: any selected event lacking support refuses.
    bins = np.searchsorted(depth_edges, event_depths, side='right') - 1
    if edge_policy == 'left-closed-final-inclusive':
        bins[event_depths == depth_edges[-1]] = 19
    require(np.all((bins >= 0) & (bins < 20)), 'event-outside-selected-depth-support')
    for time, unit, depth in zip(sample_indices, unit_indices, bins):
        lo, hi = int(time)+int(waveform_offsets[0]), int(time)+int(waveform_offsets[-1])+1
        require(0 <= lo < hi <= len(voltage), 'event-window-outside-recording')
        budget.charge('operations', t*c)
        snippet = voltage[lo:hi, channel_indices[unit]]
        require(np.all(np.isfinite(snippet)), 'nonfinite-waveform-source')
        sums[unit, depth] += snippet
        counts[unit, depth] += 1
    eligible = np.all(counts >= 50, axis=1) if count_boundary=='greater-or-equal-50' else np.all(counts>50,axis=1)
    # Complete roster and all counts survive; only Methods-declared eligibility
    # controls waveform averaging, not an outcome-dependent benchmark exclusion.
    means = np.full(sums.shape, np.nan, dtype='float64')
    for unit in np.flatnonzero(eligible):
        means[unit] = sums[unit] / counts[unit, :, None, None]
    return {'unit_ids': tuple(unit_ids), 'means': means, 'counts': counts,
            'eligible': eligible, 'boundary_policy': edge_policy,'count_boundary':count_boundary,
            'historical_equivalence': False}


def denoise_depth_waveforms(means, *, variation_rule, budget):
    import numpy as np
    require(means.ndim == 4 and means.shape[1] == 20 and means.shape[3] > 4,
            'depth-waveform-shape')
    require(np.all(np.isfinite(means)), 'eligible-waveforms-must-be-finite')
    require(variation_rule in {'literal-relative-squared-0.5', 'paper-euclidean-0.25'},
            'unselected-depth-variation-rule')
    budget.charge('array', means.size * 32)
    # Same temporal-by-channel rank-three reconstruction as the captured code.
    u, s, vh = np.linalg.svd(means, full_matrices=False)
    require(s.shape[-1] >= 3, 'rank-three-waveform-support')
    reconstructed = (u[..., :3] * s[..., None, :3]) @ vh[..., :3, :]
    norm = np.sqrt((reconstructed**2).sum(axis=(-2, -1))).mean(axis=1)
    require(np.all(np.isfinite(norm) & (norm > 0)), 'undefined-average-waveform-norm')
    reconstructed /= norm[:, None, None, None]
    difference = reconstructed[:, 0, :, 4:] - reconstructed[:, -1, :, :-4]
    if variation_rule == 'literal-relative-squared-0.5':
        numerator = (difference**2).sum(axis=(-2,-1))
        denominator = (reconstructed[:, 0, :, 4:]**2).sum(axis=(-2,-1))
        require(np.all(denominator > 0), 'zero-depth-comparison-norm')
        variation = numerator / denominator
        retained = variation < .5
    else:
        variation = np.sqrt((difference**2).sum(axis=(-2,-1)))
        retained = variation <= .25
    return {'waveforms': reconstructed, 'variation': variation,
            'retained': retained, 'variation_rule': variation_rule,
            'historical_equivalence': False}


def kriging_depth_grid(waveforms, original_positions, target_positions, *, budget):
    import numpy as np
    require(waveforms.ndim == 4 and waveforms.shape[1] == 20, 'twenty-depths-required')
    units, depth, time, channels = waveforms.shape
    require(original_positions.shape == (depth, channels, 2)
            and target_positions.shape == (depth*100, channels, 2), 'ups100-position-support')
    require(np.all(np.isfinite(original_positions)) and np.all(np.isfinite(target_positions)),
            'nonfinite-probe-geometry')
    x = original_positions.reshape(-1,2)
    y = target_positions.reshape(-1,2)
    budget.charge('array', (len(x)**2 + len(y)*len(x) + units*len(y)*time)*8)
    def kernel(a,b):
        distance = ((a[:,None,:]-b[None,:,:])**2).sum(axis=2)
        return np.exp(-distance/(2*20**2))
    # No inferred probe interpolation or aligned/staggered geometry.
    system = kernel(x,x) + .01*np.eye(len(x))
    weights = np.linalg.solve(system, kernel(y,x).T).T
    result = np.einsum('yx,uxt->uyt', weights,
                       waveforms.transpose(0,1,3,2).reshape(units,len(x),time))
    result = result.reshape(units,depth*100,channels,time).transpose(0,1,3,2)
    norms = np.sqrt((result**2).sum(axis=(-2,-1))).mean(axis=1)
    require(np.all(np.isfinite(norms) & (norms > 0)), 'upsampled-waveform-norm')
    return result/norms[:,None,None,None]


def assemble_eleven(records, expected_recording_ids, *, expected_waveforms=597,
                    expected_isi_sources=1497):
    """Join full source-unit IDs; never pad, resample or truncate to paper counts."""
    from .common import unique
    require(len(expected_recording_ids) == len(set(expected_recording_ids)) == 11,
            'eleven-original-recordings-required')
    rows = unique(records, 'recording_id')
    require(set(rows) == set(expected_recording_ids), 'incomplete-eleven-source-roster')
    waveform_rows, isi_rows = [], []
    for identity in expected_recording_ids:
        row = rows[identity]
        require(row['source_sorter'] == 'pyKilosort' and row['source_version']
                and row['clock_binding'] and row['whitening_binding'], 'original-source-lineage-open', identity)
        for name, output in [('waveforms',waveform_rows),('isi_sources',isi_rows)]:
            units = unique(row[name], 'source_unit_id')
            require(bool(units), 'empty-original-unit-support', identity)
            for unit in units.values(): output.append({'recording_id':identity, **unit})
    require(len(waveform_rows) == expected_waveforms and len(isi_rows) == expected_isi_sources,
            'original-source-count-mismatch', {'waveforms':len(waveform_rows),'isi_sources':len(isi_rows)})
    return {'waveforms':waveform_rows,'isi_sources':isi_rows,
            'native_and_authentic_lineage_qualified':False}
