"""Exact source-derived full conversion. No original executable module loader."""
import ast,hashlib,logging
from pathlib import Path
from types import SimpleNamespace
import h5py,numpy as np,pandas as pd
from . import raw_primitives as prior
NTRAIN=1721;NVAL=574

def require(ok,message):
    if not ok: raise ValueError(message)

def window_plan(selected):
    require(len(selected)>0,'No selected windows')
    require(len({x['trial_id'] for x in selected})==len(selected),'Duplicate trial IDs')
    starts=np.asarray([x['start_ms'] for x in selected],dtype=np.int64)
    stops=np.asarray([x['stop_ms_exclusive'] for x in selected],dtype=np.int64)
    require(np.all(starts>=0) and np.all(starts%5==0) and np.all(stops-starts==700),'Invalid source grid/window')
    order=np.argsort(starts,kind='stable');a=starts[order];b=stops[order]
    require(np.all(a[1:]>=b[:-1]),'Overlapping window support')
    edges=np.unique((a[:,None]+np.arange(0,701,5,dtype=np.int64)).ravel())
    direct_cells=np.searchsorted(edges,(a[:,None]+np.arange(0,700,5,dtype=np.int64)).ravel())
    require(np.array_equal(edges[direct_cells+1]-edges[direct_cells],np.full(len(direct_cells),5)),'Histogram cell is not5ms')
    return {'starts':a,'stops':b,'chronological_order':order,'restore_order':np.argsort(order),
            'histogram_edges':edges,'histogram_cells':direct_cells}

def sparse_unit_counts(spike_seconds,plan):
    """Single sparse unit pass plus independently constructed global histogram.

    No full-session dense1ms vector. Sparse unique microbins preserve source1ms
    count aggregation; the independent histogram does not use these assignments.
    """
    spike=np.asarray(spike_seconds)
    require(spike.ndim==1 and spike.dtype.kind=='f' and np.isfinite(spike).all()
            and np.all(spike>=0) and np.all(np.diff(spike)>=0),'Invalid sparse spike vector')
    millis=np.round(spike.astype(np.float64,copy=False)*1000.0,6)
    require(np.all(millis<np.iinfo(np.int64).max),'Timestamp overflow')
    micro=millis.astype(np.int64)
    a,b=plan['starts'],plan['stops'];n=len(a)
    candidate=np.searchsorted(a,micro,side='right')-1
    valid=candidate>=0
    ix=np.flatnonzero(valid)
    valid[ix]=micro[ix]<b[candidate[ix]]
    rows=candidate[valid];offsets=micro[valid]-a[rows]
    flat_micro=rows*700+offsets
    unique,multiplicity=np.unique(flat_micro,return_counts=True)
    max_micro=int(multiplicity.max(initial=0))
    flat_coarse=(unique//700)*140+(unique%700)//5
    # Integer summation, no weighted floating-point bincount.
    coarse=np.zeros(n*140,dtype=np.int64)
    np.add.at(coarse,flat_coarse,multiplicity)
    coarse=coarse.reshape(n,140)
    # Histogram every source time in the outer window, including gap values.
    # Gap bins are then excluded solely by the frozen window-edge mapping.
    direct_values=millis[(millis>=a[0])&(millis<b[-1])]
    hist=np.histogram(direct_values,bins=plan['histogram_edges'])[0]
    direct=hist[plan['histogram_cells']].reshape(n,140)
    require(np.array_equal(coarse,direct),'Sparse source1ms→5ms and independent fractional5ms histograms differ')
    require(int(coarse.sum())==int(valid.sum())==int(direct.sum()),'Count conservation failed')
    require(int(coarse.max(initial=0))<=np.iinfo(np.uint16).max,'uint16 spike-count overflow')
    require(max_micro<=2048 and np.array_equal(coarse,coarse.astype(np.float16).astype(np.int64)),
            'Source float16 intermediate would lose selected integer counts')
    result=coarse[plan['restore_order']].astype(np.uint16)
    return result,{'selected_spikes':int(valid.sum()),'max_1ms_count':max_micro,
                   'max_5ms_count':int(coarse.max(initial=0)),'independent_histogram_equal':True}

def full_selection(trials,intervals,*,ntrain=NTRAIN,nval=NVAL):
    """Same frozen eligibility; all source rows required, never choose new ranks."""
    require(len(trials['trial_id'])==ntrain+nval,'Unexpected source trial count')
    require(trials['split'].count('train')==ntrain and trials['split'].count('val')==nval,'Unexpected official split counts')
    selected,info=prior.select_metadata(trials,intervals,ntrain,nval)
    require(not info['exclusions'] and info['eligible_counts']=={'train':ntrain,'val':nval},'All-source eligibility changed')
    require({x['trial_id'] for x in selected}==set(np.asarray(trials['trial_id']).tolist()),'Not all source IDs selected')
    info['selection_rule']='ALL source trials, train followed by val in original within-split order; no subsampling or balancing'
    return selected,info

def official_alignment_full(trials,selected,source_path):
    """Same pinned source method; group result once to avoid quadratic scans."""
    raw=Path(source_path).read_bytes();require(hashlib.sha256(raw).hexdigest()==prior.SOURCE_SHA,'Official source changed')
    tree=ast.parse(raw);cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='NWBDataset')
    fn=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='make_trial_data')
    space={'pd':pd,'np':np,'logger':logging.getLogger('nlb-full-trializer')}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])),'pinned:make_trial_data','exec'),space)
    frame=pd.DataFrame({k:v for k,v in trials.items() if k!='split'});frame['end_time']=frame.pop('stop_time')
    for col in frame:
        if col.endswith('_time'):frame[col]=pd.to_timedelta(frame[col],unit='s')
    clock=np.sort(np.concatenate([np.arange(x['start_ms'],x['stop_ms_exclusive'],5) for x in selected]))
    index=pd.to_timedelta(clock,unit='ms');index.name='clock_time'
    dummy=pd.DataFrame(np.zeros((len(clock),1)),index=index,columns=pd.MultiIndex.from_tuples([('spikes',0)],names=('signal_type','channel')))
    result=space['make_trial_data'](SimpleNamespace(bin_width=5,trial_info=frame,data=dummy),
        align_field='move_onset_time',align_range=(-250,450),ignored_trials=~np.isin(np.arange(len(frame)),[x['row'] for x in selected]))
    expected={x['trial_id']:x for x in selected};seen=set()
    for trial_id,group in result.groupby(('trial_id',''),sort=False):
        require(trial_id in expected and trial_id not in seen,'Unexpected/duplicate official trial');seen.add(trial_id)
        item=expected[trial_id]
        actual=group[('clock_time','')].to_numpy().astype('timedelta64[ns]').astype(np.int64)//1000000
        relative=group[('align_time','')].to_numpy().astype('timedelta64[ns]').astype(np.int64)//1000000
        require(np.array_equal(actual,np.arange(item['start_ms'],item['stop_ms_exclusive'],5)),'Official trial clock mismatch')
        require(np.array_equal(relative,np.arange(-250,450,5)),'Official relative grid mismatch')
    require(seen==set(expected),'Missing official trial IDs')
    return {'source_sha256':prior.SOURCE_SHA,'trial_count':len(seen),'clock_rows':len(clock),
            'exact_clock_and_relative_grid_parity':True,'method':'Pinned official AST trializer on selected5ms dummy rows; grouped comparison, not fullsession1msdense loader'}

def inspect_metadata(f):
    """Same field-only schema gate as frozen25trial converter; no spike values."""
    identity={k:prior.text(f[k][()]) for k in ['/general/subject/subject_id','/general/subject/species','/session_start_time']}
    require(identity=={'/general/subject/subject_id':'Jenkins','/general/subject/species':'Macaca mulatta','/session_start_time':'2009-09-25T00:00:00-07:00'},'Unexpected biological identity')
    for key,(shape,kind) in prior.EXPECTED.items():prior.dataset(f,key,shape,kind)
    units=f['/units/id'][:];heldout=f['/units/heldout'][:]
    require(len(set(units.tolist()))==182 and int(heldout.sum())==45 and int((~heldout).sum())==137,'Unit count/partition changed')
    slo,shi=prior.ragged_bounds(f['/units/spike_times_index'][:],len(f['/units/spike_times']))
    olo,ohi=prior.ragged_bounds(f['/units/obs_intervals_index'][:],len(f['/units/obs_intervals']))
    observations=f['/units/obs_intervals'][:]
    require(np.isfinite(observations).all() and np.all(observations[:,1]>observations[:,0]),'Invalid observation intervals')
    groups=[]
    for mask in [~heldout,heldout]:
        indices=np.flatnonzero(mask);ref=observations[olo[indices[0]]:ohi[indices[0]]]
        require(np.all(np.diff(ref[:,0])>=0),'Unordered observation intervals')
        for unit in indices:require(np.array_equal(ref,observations[olo[unit]:ohi[unit]]),'Observation-mask differences within group')
        groups.append(ref)
    trials={}
    for key,kind in [('id','i'),('split','O'),('start_time','f'),('stop_time','f'),('move_onset_time','f'),('trial_type','i'),('trial_version','i')]:
        a=prior.dataset(f,'/intervals/trials/'+key,(2295,),kind)[:]
        trials['trial_id' if key=='id' else key]=[prior.text(v) for v in a] if key=='split' else a
    require(set(trials['split'])=={'train','val'} and len(set(trials['trial_id'].tolist()))==2295,'Invalid source trial IDs/splits')
    require(np.isfinite(trials['start_time']).all() and np.isfinite(trials['stop_time']).all() and np.all(trials['stop_time']>trials['start_time']),'Invalid trial timing')
    return identity,units,heldout,slo,shi,trials,groups
