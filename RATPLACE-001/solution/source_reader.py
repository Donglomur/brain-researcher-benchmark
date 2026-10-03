"""Oracle source reconstruction. No I/O on import, no endpoint computation."""
import math
import numpy as np
import source_io as io

POSITION='/processing/behavior/AnimalPosition/Position'


def geometry(t,xy,window,max_gap=.1):
    t=np.asarray(t,dtype=np.float64);xy=np.asarray(xy,dtype=np.float64)
    io.need(t.ndim==1 and xy.shape==(len(t),2) and len(t)>=2,'tracking_shape')
    io.need(np.isfinite(t).all() and np.all(np.diff(t)>0),'tracking_clock')
    left=np.maximum(t[:-1],window[0]);right=np.minimum(t[1:],window[1])
    valid=np.isfinite(xy).all(1)[:-1]&np.isfinite(xy).all(1)[1:]&(np.diff(t)<=max_gap)&(right>left)
    io.need(valid.any(),'no_valid_observation')
    q=xy[:-1][valid];lo=q.min(0);hi=q.max(0)
    io.need(np.all(hi>lo),'degenerate_coordinate_axis')
    edges=[np.linspace(lo[k],hi[k],n+1,dtype=np.float64) for k,n in enumerate((4,5))]
    cell=np.full(len(t)-1,-1,dtype=np.int64)
    coordinates=[]
    for k,n in enumerate((4,5)):
        b=np.searchsorted(edges[k],q[:,k],side='right')-1
        b[q[:,k]==hi[k]]=n-1
        io.need(np.all((b>=0)&(b<n)),'grid_bounds');coordinates.append(b)
    cell[valid]=5*coordinates[0]+coordinates[1]
    duration=right-left
    occupancy=np.array([math.fsum(float(d) for d,b,v in zip(duration,cell,valid) if v and b==j)
                        for j in range(20)],dtype=np.float64)
    return dict(t=t,left=left,right=right,valid=valid,bins=cell,occupancy_seconds=occupancy,
                grid_edges_raw=[e.tolist() for e in edges])


def counts(spikes,g):
    spikes=np.asarray(spikes,dtype=np.float64)
    indices=np.searchsorted(g['t'],spikes,side='right')-1
    keep=(indices>=0)&(indices<len(g['valid']))
    pos=indices[keep];values=spikes[keep]
    keep2=g['valid'][pos]&(values>=g['left'][pos])&(values<g['right'][pos])
    return np.bincount(g['bins'][pos[keep2]],minlength=20).astype(np.int64)


def reconstruct(data_dir='/app/data/ratplace',documents='/app',*,pilot=False):
    io.need(type(pilot) is bool,'pilot_boolean')
    context=io.authenticate(data_dir,documents);m=context['method'];src=m['source']
    window=src['window_seconds'];draws=m['null']['draws'];minimum=m['null']['min_shift_seconds']
    io.need(np.__version__==m['runtime']['numpy'],'numpy_version')
    with io.open_h5(context['raw']) as f:
        io.need(io.text(f.attrs['nwb_version'])==src['nwb_version'],'nwb_version')
        pos=io.direct(f,POSITION+'/data');clock=io.direct(f,POSITION+'/timestamps')
        io.need(pos.shape==(src['n_positions'],2) and clock.shape==(src['n_positions'],),'tracking_source_shape')
        io.need(pos.dtype.kind=='f' and clock.dtype.kind=='f','tracking_dtype')
        attrs=dict(unit=io.text(pos.attrs['unit']),conversion=float(pos.attrs['conversion']),offset=float(pos.attrs['offset']))
        io.need(attrs==src['position_metadata'] and io.text(clock.attrs['unit'])=='seconds','position_metadata')
        t=np.asarray(clock[()],dtype=np.float64);xy=np.asarray(pos[()],dtype=np.float64)
        io.need([float(t[0]),float(t[-1])]==window,'camera_window')
        g=geometry(t,xy,window,m['tracking']['max_gap_seconds'])
        ids=io.direct(f,'/units/id')[()]
        io.need(ids.shape==(src['n_units'],) and ids.dtype.kind in 'iu' and len(set(map(int,ids)))==len(ids),'unit_ids')
        areas=[io.text(x) for x in io.direct(f,'/units/cell_area')[()]]
        types=[io.text(x) for x in io.direct(f,'/units/cell_type')[()]]
        index=io.direct(f,'/units/spike_times_index');stops=[int(x) for x in index[()]]
        spikes=io.direct(f,'/units/spike_times')
        io.need(index.dtype.kind in 'iu' and index.shape==(len(ids),) and spikes.dtype.kind=='f','spike_dtype')
        io.need(len(areas)==len(types)==len(stops)==len(ids) and spikes.shape==(src['n_spikes'],),'unit_shapes')
        starts=[0]+stops[:-1]
        io.need(all(0<=a<=b<=src['n_spikes'] for a,b in zip(starts,stops)) and stops[-1]==src['n_spikes'],'ragged_indices')
        io.need(f[index.attrs['target']].id==spikes.id,'ragged_reference')
        order=sorted(range(len(ids)),key=lambda i:int(ids[i]))
        first=next((i for i in order if areas[i]=='CA1'),None)
        io.need(not pilot or first is not None,'pilot_without_CA1')
        ledger=[];eligible=[];raw_counts=[];shifts=[];offsets=[]
        total=math.fsum(map(float,g['occupancy_seconds']));duration=window[1]-window[0]
        io.need(duration>2*minimum,'short_shift_window')
        for rank,i in enumerate(order):
            row=dict(unit_id=str(int(ids[i])),source_row=i,cell_area=areas[i],cell_type=types[i],
                     stored_spike_count=stops[i]-starts[i])
            if pilot and i!=first:
                row.update(window_spike_count=None,observed_spike_count=None,eligible=None,reason='not_pilot_unit')
                ledger.append(row);continue
            s=np.asarray(spikes[starts[i]:stops[i]],dtype=np.float64)
            io.need(np.isfinite(s).all() and np.all(np.diff(s)>=0),'spike_clock')
            s=s[(s>=window[0])&(s<window[1])]
            c=counts(s,g);n=sum(map(int,c));rate=n/total
            reason=('non_CA1' if areas[i]!='CA1' else 'insufficient_spikes' if n<m['selection']['min_spikes']
                    else 'rate_not_above_lower' if not rate>m['selection']['rate_lower_exclusive']
                    else 'rate_not_below_upper' if not rate<m['selection']['rate_upper_exclusive'] else 'included')
            row.update(window_spike_count=len(s),observed_spike_count=n,eligible=reason=='included',reason=reason)
            ledger.append(row)
            # Pilot includes its one chosen CA1 primitive even if it is ineligible.
            if reason!='included' and not pilot:continue
            eligible.append(row['unit_id']);raw_counts.append(c)
            rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence([m['null']['seed'],rank,0])))
            off=rng.uniform(minimum,duration-minimum,size=draws);offsets.append(off)
            shifts.append(np.stack([counts(window[0]+np.remainder(s-window[0]+d,duration),g) for d in off]))
        observed=dict(nwb_version=src['nwb_version'],position_path=POSITION,position_metadata=attrs,
            reference_frame=io.text(io.direct(f,POSITION+'/reference_frame')[()]),n_positions=len(t),
            n_units=len(ids),n_spikes=src['n_spikes'],clock_unit='seconds',
            physical_calibration_conflict=True,physical_units_used_for_analysis=False,
            upstream_interpolation_flags_certified=False)
    io.recheck(context)
    arrays=dict(unit_ids=np.array(eligible,dtype='U32'),bin_ids=np.arange(20,dtype=np.int64),
        draw_ids=np.arange(draws,dtype=np.int64),occupancy_seconds=g['occupancy_seconds'],
        raw_counts=np.array(raw_counts,dtype=np.int64).reshape(len(eligible),20),
        shifted_counts=np.array(shifts,dtype=np.int64).reshape(len(eligible),draws,20),
        shift_offsets_seconds=np.array(offsets,dtype=np.float64).reshape(len(eligible),draws))
    arrays['shift_defined']=arrays['shifted_counts'].sum(2)>0
    return dict(status='resource_pilot' if pilot else 'complete',arrays=arrays,all_units=ledger,
        source_observed=observed,pins=context['pins'],
        analysis=dict(window_seconds=list(window),grid_shape=[4,5],grid_edges_raw=g['grid_edges_raw'],
            valid_pair_count=int(g['valid'].sum()),invalid_pair_count=int((~g['valid']).sum()),
            valid_observed_seconds=total,physical_speed_filter=False))
