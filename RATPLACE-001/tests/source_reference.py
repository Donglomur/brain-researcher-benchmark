"""Independent private primitive reconstruction; no solution/kernel imports.

Generic authenticated-byte/HDF5 safety and libraries are disclosed shared.
Tracking bin/interval assembly, unit handling and integer histograms below are
independently composed. No scalar spatial-information endpoints are produced.
"""
import math
import numpy as np
import source_io as io


def prepare_tracking(times,position,window,max_gap):
    time=np.array(times,dtype='f8',copy=True);q=np.array(position,dtype='f8',copy=True)
    io.need(time.ndim==1 and q.shape==(time.size,2) and time.size>1,'tracking_shape')
    io.need(np.isfinite(time).all() and np.all(time[1:]>time[:-1]),'tracking_clock')
    lower=np.maximum(time[:-1],window[0]);upper=np.minimum(time[1:],window[1])
    keep=(upper>lower)&((time[1:]-time[:-1])<=max_gap)
    keep &= np.isfinite(q[:-1]).all(axis=1)&np.isfinite(q[1:]).all(axis=1)
    io.need(np.any(keep),'no_valid_observation')
    limits=np.array([(q[:-1,axis][keep].min(),q[:-1,axis][keep].max()) for axis in (0,1)])
    io.need(np.all(limits[:,1]>limits[:,0]),'degenerate_coordinate_axis')
    edges=[np.linspace(*limits[axis],num=n+1,dtype=np.float64) for axis,n in enumerate((4,5))]
    labels=np.full(time.size-1,-1,dtype='i8')
    x=np.digitize(q[:-1,0][keep],edges[0],right=False)-1
    y=np.digitize(q[:-1,1][keep],edges[1],right=False)-1
    x[q[:-1,0][keep]==limits[0,1]]=3;y[q[:-1,1][keep]==limits[1,1]]=4
    io.need(np.all((0<=x)&(x<4)&(0<=y)&(y<5)),'grid_bounds')
    labels[keep]=x*5+y
    dwell=upper-lower
    occupancy=np.asarray([math.fsum(float(x) for x in dwell[keep&(labels==b)]) for b in range(20)])
    return time,lower,upper,keep,labels,occupancy,[e.tolist() for e in edges]


def histogram(spike_times,tracking):
    time,lower,upper,valid,labels=tracking[:5]
    s=np.asarray(spike_times,dtype='f8')
    cells=np.digitize(s,time,right=False)-1
    candidates=np.flatnonzero((cells>=0)&(cells<valid.size))
    selected=cells[candidates]
    eligible=valid[selected]&(s[candidates]>=lower[selected])&(s[candidates]<upper[selected])
    return np.histogram(labels[selected[eligible]],bins=np.arange(21))[0].astype('i8')


def reconstruct(data_dir='/app/data/ratplace',documents='/app',*,pilot=False):
    io.need(type(pilot) is bool,'pilot_boolean')
    authority=io.authenticate(data_dir,documents);method=authority['method'];expected=method['source']
    io.need(np.__version__==method['runtime']['numpy'],'numpy_version')
    root='/processing/behavior/AnimalPosition/Position'
    with io.open_h5(authority['raw']) as h5:
        io.need(io.text(h5.attrs['nwb_version'])==expected['nwb_version'],'nwb_version')
        position=io.direct(h5,root+'/data');timestamps=io.direct(h5,root+'/timestamps')
        io.need(position.shape==(expected['n_positions'],2) and timestamps.shape==(expected['n_positions'],),'tracking_source_shape')
        io.need(position.dtype.kind=='f' and timestamps.dtype.kind=='f','tracking_dtype')
        declaration={name:(io.text(position.attrs[name]) if name=='unit' else float(position.attrs[name]))
                     for name in ('unit','conversion','offset')}
        io.need(declaration==expected['position_metadata'] and io.text(timestamps.attrs['unit'])=='seconds','position_metadata')
        t=np.array(timestamps[()],dtype='f8');q=np.array(position[()],dtype='f8')
        window=expected['window_seconds']
        io.need(float(t[0])==window[0] and float(t[-1])==window[1],'camera_window')
        tracking=prepare_tracking(t,q,window,method['tracking']['max_gap_seconds'])
        id_values=io.direct(h5,'/units/id')[()]
        io.need(id_values.dtype.kind in 'iu' and id_values.shape==(expected['n_units'],),'unit_ids')
        io.need(len({int(x) for x in id_values})==len(id_values),'unit_ids')
        labels=[io.text(x) for x in io.direct(h5,'/units/cell_area')[()]]
        classes=[io.text(x) for x in io.direct(h5,'/units/cell_type')[()]]
        ragged=io.direct(h5,'/units/spike_times_index');end=[int(x) for x in ragged[()]]
        all_spikes=io.direct(h5,'/units/spike_times')
        io.need(ragged.dtype.kind in 'iu' and ragged.shape==(len(id_values),) and all_spikes.dtype.kind=='f','spike_dtype')
        io.need(all_spikes.shape==(expected['n_spikes'],) and len(end)==len(labels)==len(classes)==len(id_values),'unit_shapes')
        begin=[0,*end[:-1]]
        io.need(end[-1]==expected['n_spikes'] and all(a>=0 and a<=b<=end[-1] for a,b in zip(begin,end)),'ragged_indices')
        io.need(h5[ragged.attrs['target']].id==all_spikes.id,'ragged_reference')
        sorted_rows=sorted(range(len(id_values)),key=lambda row:int(id_values[row]))
        pilot_row=next((row for row in sorted_rows if labels[row]=='CA1'),None)
        io.need(not pilot or pilot_row is not None,'pilot_without_CA1')
        interval_length=window[1]-window[0];minimum=method['null']['min_shift_seconds']
        io.need(interval_length>minimum*2,'short_shift_window')
        observed_duration=math.fsum(float(v) for v in tracking[5])
        table=[];ids=[];original=[];surrogates=[];offset_rows=[]
        for unit_index,row_index in enumerate(sorted_rows):
            entry=dict(unit_id=str(int(id_values[row_index])),source_row=row_index,cell_area=labels[row_index],
                       cell_type=classes[row_index],stored_spike_count=end[row_index]-begin[row_index])
            if pilot and row_index!=pilot_row:
                entry.update(window_spike_count=None,observed_spike_count=None,eligible=None,reason='not_pilot_unit')
                table.append(entry);continue
            vector=np.array(all_spikes[begin[row_index]:end[row_index]],dtype='f8')
            io.need(np.isfinite(vector).all() and np.all(vector[1:]>=vector[:-1]),'spike_clock')
            first=np.searchsorted(vector,window[0],side='left')
            last=np.searchsorted(vector,window[1],side='left')
            retained=vector[first:last]
            raw=histogram(retained,tracking);count=sum(int(v) for v in raw);rate=count/observed_duration
            if labels[row_index]!=method['selection']['region']:reason='non_CA1'
            elif count<method['selection']['min_spikes']:reason='insufficient_spikes'
            elif rate<=method['selection']['rate_lower_exclusive']:reason='rate_not_above_lower'
            elif rate>=method['selection']['rate_upper_exclusive']:reason='rate_not_below_upper'
            else:reason='included'
            entry.update(window_spike_count=int(last-first),observed_spike_count=count,eligible=reason=='included',reason=reason)
            table.append(entry)
            if reason!='included' and not pilot:continue
            stream=np.random.Generator(np.random.PCG64(np.random.SeedSequence([method['null']['seed'],unit_index,0])))
            offsets=stream.uniform(minimum,interval_length-minimum,size=method['null']['draws'])
            null_counts=np.empty((len(offsets),20),dtype='i8')
            for draw,offset in enumerate(offsets):
                shifted=window[0]+((retained-window[0]+offset)%interval_length)
                null_counts[draw]=histogram(shifted,tracking)
            ids.append(entry['unit_id']);original.append(raw);surrogates.append(null_counts);offset_rows.append(offsets)
        source_observed=dict(nwb_version=expected['nwb_version'],position_path=root,position_metadata=declaration,
            reference_frame=io.text(io.direct(h5,root+'/reference_frame')[()]),n_positions=len(t),
            n_units=len(id_values),n_spikes=expected['n_spikes'],clock_unit='seconds',
            physical_calibration_conflict=True,physical_units_used_for_analysis=False,
            upstream_interpolation_flags_certified=False)
    io.recheck(authority)
    count=len(ids);draws=method['null']['draws']
    arrays=dict(unit_ids=np.asarray(ids,dtype='U32'),bin_ids=np.arange(20,dtype='i8'),
        draw_ids=np.arange(draws,dtype='i8'),occupancy_seconds=tracking[5],
        raw_counts=np.asarray(original,dtype='i8').reshape(count,20),
        shifted_counts=np.asarray(surrogates,dtype='i8').reshape(count,draws,20),
        shift_offsets_seconds=np.asarray(offset_rows,dtype='f8').reshape(count,draws))
    arrays['shift_defined']=np.sum(arrays['shifted_counts'],axis=2)>0
    return dict(status='resource_pilot' if pilot else 'complete',arrays=arrays,all_units=table,
        source_observed=source_observed,pins=authority['pins'],
        analysis=dict(window_seconds=list(window),grid_shape=[4,5],grid_edges_raw=tracking[6],
            valid_pair_count=int(tracking[3].sum()),invalid_pair_count=int((~tracking[3]).sum()),
            valid_observed_seconds=observed_duration,physical_speed_filter=False))
