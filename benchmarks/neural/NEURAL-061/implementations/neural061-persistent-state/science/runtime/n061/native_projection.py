"""Source-owned original-data projection. Numerical/native functions are unexecuted.

Caller supplies a qualified same-open, full-hash captured torch-brain Data object,
never an arbitrary participant mapping. The missing actual capture/launcher
implementation is a named admission gate in NATIVE_CONTRACT.md.
"""
from .contracts import need, Unit, units, HEADS, CLASSES,ScientificUnavailable

def joined_units(data, original_row, ontology, training_domain, tick):
    import numpy as np
    # Use raw Data before IBLBrainWideBench2026's namespacing; never guess a prefix.
    need(str(data.session.id) == original_row['session'] and str(data.subject.id) == original_row['animal'], 'actual raw session/subject join')
    probe_ids = tuple(str(x) for x in data.probes.id)
    need(set(probe_ids) == set(original_row['probes']) and len(set(probe_ids)) == len(probe_ids), 'all original probe insertions')
    n = len(data.units); st = np.asarray(data.spikes.timestamps); si = np.asarray(data.spikes.unit_index)
    need(st.ndim == si.ndim == 1 and len(st) == len(si) and si.dtype.kind in 'iu', 'original spike index axis')
    need(np.isfinite(st).all() and np.all((si >= 0) & (si < n)), 'all spike rows map to actual unit table')
    starts = np.asarray(training_domain.start); ends = np.asarray(training_domain.end)
    need(starts.ndim == ends.ndim == 1 and len(starts) == len(ends) and len(starts), 'training-only rate domain')
    need(np.isfinite(starts).all() and np.isfinite(ends).all() and np.all(ends > starts) and np.all(starts[1:] >= ends[:-1]), 'disjoint finite calibration intervals')
    mask = np.zeros(len(st), dtype=bool)
    for a, b in zip(starts, ends, strict=True): tick(); mask |= (st >= a) & (st < b)
    exposure = float(np.sum(ends-starts)); counts = np.bincount(si[mask], minlength=n)
    need(exposure > 0 and len(counts) == n, 'full rate numerator and denominator')
    table = data.units
    fields = ('id', 'cluster_id', 'probe_id', 'region_beryl', 'qc_neural', 'qc_neural_alignment', 'label')
    need(all(len(getattr(table, f)) == n for f in fields), 'original complete metadata column extents')
    result = []
    for i in range(n):
        tick(); p = str(table.probe_id[i]); raw_region=table.region_beryl[i]
        region='<MISSING>' if raw_region is None or isinstance(raw_region,(float,np.floating)) and np.isnan(raw_region) else str(raw_region)
        need(p in probe_ids, 'unit probe_id is actual raw probes.id')
        j = probe_ids.index(p)
        need(str(table.qc_neural[i]) == str(data.probes.qc_neural[j]) and str(table.qc_neural_alignment[i]) == str(data.probes.qc_neural_alignment[j]), 'probe QC copied from same insertion')
        need(np.asarray(table.cluster_id).dtype.kind in 'iu','original integer cluster IDs, no coercion')
        label=float(table.label[i]);need(not np.isinf(label),'finite or explicitly missing unit quality')
        result.append(Unit(i, str(table.id[i]), int(table.cluster_id[i]), p, original_row['session'], original_row['animal'], region, float(counts[i]/exposure), str(table.qc_neural[i]), str(table.qc_neural_alignment[i]), None if np.isnan(label) else label))
    return units(tuple(result), original_row['session'], original_row['animal'], probe_ids, ontology), {'rate_domain': tuple(zip(starts.tolist(), ends.tolist())), 'rate_seconds': exposure, 'rate_spikes': int(mask.sum()), 'full_session_firing_rate_not_used': True}

def count_features(window, unit_indices, tick):
    """Exact common window; all original spikes, original bin exposure retained."""
    import numpy as np
    t = np.asarray(window['spike_times']); u = np.asarray(window['spike_units']); edges = np.asarray(window['edges'])
    need(len(edges) == 51 and np.isfinite(edges).all() and np.all(np.diff(edges) > 0), 'fixed 50-bin original one-second window')
    need(np.allclose(np.diff(edges), .02, rtol=0, atol=1e-12), '20ms bin construction')
    need(t.shape == u.shape and t.ndim == 1 and u.dtype.kind in 'iu', 'original spike shape')
    need(np.all((t >= edges[0]) & (t < edges[-1])), 'same emitted neural window')
    exposure = np.asarray(window['exposure'], dtype=float)
    need(exposure.shape == (50,) and np.all((exposure >= 0) & (exposure <= .02+1e-12)), 'full original neural-domain exposure')
    counts = np.zeros((len(unit_indices), 50)); indices = {v:i for i,v in enumerate(unit_indices)}
    for time, index in zip(t, u, strict=True):
        tick()
        if int(index) in indices: counts[indices[int(index)], int(np.searchsorted(edges,time,side='right')-1)] += 1
    need(np.all(counts[:, exposure == 0] == 0), 'no spikes outside original neural support')
    rates = np.zeros_like(counts); keep = exposure > 0
    rates[:, keep] = np.log1p(.02*counts[:, keep]/exposure[keep])
    return rates, exposure

def reference_features(window, arm_indices, head, tick):
    import numpy as np
    need(head in HEADS, 'declared readout')
    x, exposure = count_features(window, arm_indices, tick)
    pooled = np.concatenate((x.mean(axis=0), x.var(axis=0))) if len(x) else np.zeros(100)
    base = np.concatenate((pooled, exposure/.02, (exposure>0).astype(float)))
    # No stimulus, reward, choice, trial outcomes, anatomy labels, or identities are predictors.
    times = np.array([0.0]) if head in CLASSES else np.asarray(window['target_times'],dtype=float)
    return np.column_stack((np.broadcast_to(base,(len(times),len(base))), times, times**2))

def project_windows(data, role, head, tick):
    """Full original C=1 intersection and trailing target; no implicit truncation.

    Canonical N061 keeps physical readout units; publisher normalization is not
    silently inherited. This function is the trusted preparation producer and
    sees labels; candidate projections remove every evaluation label later.
    """
    import numpy as np
    from torch_brain.samplers import TrialSampler
    from ibl_bwb_eval.tasks import get_ts1_readout_spec
    need(head in HEADS and role in ('source', 'evaluation'), 'fixed preparation scope')
    spec = get_ts1_readout_spec('wheel_speed' if head == 'wheel_velocity' else head)
    value_key = 'wheel.wheel_vel' if head == 'wheel_velocity' else spec.value_key
    task = data.get_nested_attribute(spec.interval_key)
    starts = np.asarray(task.start); ends = np.asarray(task.end); trials = np.asarray(task.trial_index)
    need(len(starts) == len(ends) == len(trials), 'whole task interval inverse')
    if spec.mask_counts_key is not None:
        task = task.select_by_mask(data.get_nested_attribute(spec.mask_counts_key)>0)
    splits = ('pretrain_train_domain','pretrain_val_domain') if role == 'source' else ('ts1_test_domain',)
    original_a0 = float(data.absolute_start); output = []
    for split in splits:
        support = data.task_aligned_intervals.domain & getattr(data,split) & task & data.get_nested_attribute(spec.domain_key)
        sampler = TrialSampler(sampling_intervals={'recording':support},shuffle=False)
        for emitted in sampler:
            tick(); a,b = float(emitted.start),float(emitted.end)
            hits = np.flatnonzero((starts<=a)&(ends>=b))
            need(len(hits)==1 and a<b, 'unique original emitted interval')
            i=int(hits[0]); origin=float(starts[i]); need(float(ends[i])-origin==1.0, 'original one-second task window')
            sample=data.slice(a,b); end=float(sample.domain.end[-1]); margin=end-1.0
            target=sample.slice(margin,end) if margin>1e-6 else sample
            y=np.asarray(target.get_nested_attribute(value_key))
            if y.dtype==np.float64:y=y.astype(np.float32)
            if head=='licking_rate':y=np.round(y/50.0).astype(np.int32)
            y=y.reshape(-1)
            if head in CLASSES:
                need(y.shape==(1,) and y.dtype.kind in 'iu' and 0<=int(y[0])<CLASSES[head], 'original class index')
                times=np.array([0.0]);mask=np.ones(1,dtype=bool)
            else:
                times=np.asarray(target.get_nested_attribute(spec.timestamp_key),dtype=float)+float(target.absolute_start)-original_a0-origin
                mask=np.ones(len(times),dtype=bool) if spec.mask_key is None else np.asarray(target.get_nested_attribute(spec.mask_key))
                need(mask.dtype.kind=='b' and mask.shape==times.shape==y.shape and np.all(np.diff(times)>0), 'exact timestamps and original mask')
                need(np.isfinite(times).all() and np.all((times>=a-origin)&(times<b-origin)), 'targets within emitted support')
            need(np.isfinite(y[mask]).all(), 'finite scored original target values')
            local_t=np.asarray(sample.spikes.timestamps,dtype=float)+float(sample.absolute_start)-original_a0-origin
            local_u=np.asarray(sample.spikes.unit_index)
            need(np.isfinite(local_t).all() and local_t.shape==local_u.shape and np.all((local_t>=a-origin)&(local_t<b-origin)), 'full common neural support')
            edges=np.arange(51)*.02;exposure=np.zeros(50)
            sa=np.asarray(sample.spikes.domain.start)+float(sample.absolute_start)-original_a0-origin
            sb=np.asarray(sample.spikes.domain.end)+float(sample.absolute_start)-original_a0-origin
            need(len(sa)==len(sb) and np.all(sb>sa) and np.all(sa[1:]>=sb[:-1]), 'disjoint original neural domain')
            covered=np.zeros(len(local_t),dtype=bool)
            for left,right in zip(sa,sb,strict=True):
                exposure+=np.maximum(0,np.minimum(np.minimum(edges[1:],b-origin),right)-np.maximum(np.maximum(edges[:-1],a-origin),left))
                covered|=(local_t>=left)&(local_t<right)
            need(covered.all(), 'every original spike belongs to original domain')
            output.append({'source_split':split,'original_trial':int(trials[i]),'original_interval':(a,b),
                           'window_ordinal':len(output),'original_a0':original_a0,'task_origin':origin,
                           'head':head,'edges':edges,'exposure':exposure,'spike_times':local_t,
                           'spike_units':local_u,'target_times':times,'mask':mask,'values':y})
    if not output:raise ScientificUnavailable('no_original_target_windows',{'head':head,'role':role})
    return output
