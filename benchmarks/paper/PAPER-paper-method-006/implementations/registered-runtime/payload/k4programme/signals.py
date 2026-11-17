"""Full-support signal assembly after separately admitted stochastic/source inputs.

No random generator, seed, spike-process rule, noise spectrum, or sample rounding
is silently selected. Realized event/depth/noise inputs and their original
producer remain mandatory. This implements their actual downstream consumption.
"""
from .common import require,unique


def inject_signal(background,waveforms,events,channel_map,amplitudes,*,unit_roles,
                  waveform_offsets,kind,sampling_frequency,duration_seconds,budget):
    import numpy as np
    require(kind in {'synthetic','hybrid'},'unknown-signal-construction')
    roles=unique(unit_roles,'unit_id')
    expected={'single-unit-target':600,'multi-unit-background':600} if kind=='synthetic' else {'single-unit-target':100}
    require({k:sum(r['role']==k for r in roles.values()) for k in expected}==expected
            and len(roles)==sum(expected.values()),'complete-signal-unit-roles')
    require(background.ndim==2 and np.all(np.isfinite(background)),'signal-background-axes')
    require(sampling_frequency>0 and duration_seconds>0
            and len(background)==sampling_frequency*duration_seconds,'full-signal-duration')
    if kind=='synthetic':require(duration_seconds==2700,'forty-five-minute-simulation')
    n=len(roles)
    require(waveforms.ndim==4 and waveforms.shape[0]==n and amplitudes.shape==(n,),
            'waveform-unit-support')
    require(channel_map.shape==(n,waveforms.shape[3]) and channel_map.dtype.kind in 'iu',
            'waveform-channel-map')
    require(np.all((channel_map>=0)&(channel_map<background.shape[1])),'waveform-channel-range')
    require(all(len(set(row.tolist()))==len(row) for row in channel_map),'duplicate-waveform-channel')
    require(len(waveform_offsets)==waveforms.shape[2] and all(type(v) is int for v in waveform_offsets)
            and all(b-a==1 for a,b in zip(waveform_offsets,waveform_offsets[1:])),
            'full-waveform-time-support')
    require(events.ndim==2 and events.shape[1]==3 and events.dtype.kind in 'iu',
            'events-require-unit-sample-depth-integer-columns')
    require(np.all(np.isfinite(waveforms)) and np.all(np.isfinite(amplitudes))
            and np.all(amplitudes>0),'nonfinite-waveform-amplitude')
    require(np.all((events[:,0]>=0)&(events[:,0]<n)),'event-unit-range')
    require(np.all((events[:,2]>=0)&(events[:,2]<waveforms.shape[1])),'event-depth-grid-range')
    require(np.all(np.diff(events[:,1])>=0),'event-time-order')
    budget.charge('array',background.size*8+events.nbytes)
    output=background.astype('float64',copy=True)
    counts=np.zeros(n,dtype='int64')
    for unit,sample,depth in events:
        lo=int(sample)+waveform_offsets[0];hi=lo+len(waveform_offsets)
        require(0<=lo<hi<=len(output),'whole-event-window-outside-signal')
        budget.charge('operations',waveforms.shape[2]*waveforms.shape[3])
        output[lo:hi,channel_map[unit]]+=amplitudes[unit]*waveforms[unit,depth]
        counts[unit]+=1
    require(np.all(np.isfinite(output)),'nonfinite-assembled-signal')
    # Empty trains remain in the role/denominator table; never silently remove units.
    return {'signal':output,'events':events.copy(),'unit_ids':list(roles),
            'unit_roles':unit_roles,'event_counts':counts,'sampling_frequency':sampling_frequency,
            'duration_seconds':duration_seconds,'historical_equivalence':False,
            'stochastic_producer':'external original or separately selected policy still required'}


def eligible_depth_selection(means,counts,unit_ids,*,minimum_count,boundary_rule,budget):
    """Apply a named source eligibility rule while retaining every input disposition."""
    import numpy as np
    require(minimum_count==50 and boundary_rule in {'greater-than','greater-or-equal'},
            'unselected-waveform-count-boundary')
    require(means.ndim==4 and counts.shape==means.shape[:2] and len(unit_ids)==len(means)
            and means.shape[1]==20,'depth-selection-support')
    require(len(set(unit_ids))==len(unit_ids) and counts.dtype.kind in 'iu' and np.all(counts>=0),
            'depth-selection-counts')
    selected=np.all(counts>50,axis=1) if boundary_rule=='greater-than' else np.all(counts>=50,axis=1)
    require(np.any(selected),'no-eligible-source-waveform')
    budget.charge('array',means[selected].nbytes+selected.nbytes)
    return {'means':means[selected].copy(),'selected_ids':[u for u,keep in zip(unit_ids,selected) if keep],
            'all_dispositions':[{'unit_id':u,'eligible':bool(keep),'counts':row.tolist()}
                                for u,keep,row in zip(unit_ids,selected,counts)],
            'boundary_rule':boundary_rule,'historical_equivalence':False}


def hybrid_waveform_means(voltage,event_samples,event_units,*,unit_ids,channels,
                          offsets,baseline_indices,contaminations,budget):
    import numpy as np
    require(len(unit_ids)==len(set(unit_ids))==100 and len(contaminations)==100,
            'one-hundred-hybrid-sources')
    require(all(0<=x<.1 for x in contaminations),'hybrid-SU-contamination-support')
    require(voltage.ndim==2 and event_samples.dtype.kind in 'iu' and event_units.dtype.kind in 'iu'
            and len(event_samples)==len(event_units),'hybrid-event-axes')
    require(len(channels)==100 and len(offsets)>0 and all(b-a==1 for a,b in zip(offsets,offsets[1:])),
            'hybrid-waveform-support')
    require(baseline_indices and len(set(baseline_indices))==len(baseline_indices)
            and min(baseline_indices)>=0 and max(baseline_indices)<len(offsets),
            'unselected-hybrid-baseline')
    require(len({len(c) for c in channels})==1 and all(len(set(c))==len(c) and c
            and min(c)>=0 and max(c)<voltage.shape[1] for c in channels),'hybrid-channel-support')
    require(np.all((event_units>=0)&(event_units<100)),'hybrid-event-unit-range')
    budget.charge('array',100*len(offsets)*len(channels[0])*16)
    sums=np.zeros((100,len(offsets),len(channels[0])),dtype='float64');counts=np.zeros(100,dtype='int64')
    for sample,unit in zip(event_samples,event_units):
        lo=int(sample)+offsets[0];hi=lo+len(offsets)
        require(0<=lo<hi<=len(voltage),'hybrid-event-window-unavailable')
        block=voltage[lo:hi,channels[unit]]
        require(np.all(np.isfinite(block)),'hybrid-nonfinite-source')
        sums[unit]+=block;counts[unit]+=1;budget.charge('operations',block.size)
    require(np.all(counts>0),'empty-hybrid-source-unit')
    means=sums/counts[:,None,None]
    means-=means[:,baseline_indices,:].mean(axis=1,keepdims=True)
    return {'waveforms':means,'counts':counts,'unit_ids':unit_ids,
            'baseline_indices':baseline_indices,'historical_equivalence':False}
