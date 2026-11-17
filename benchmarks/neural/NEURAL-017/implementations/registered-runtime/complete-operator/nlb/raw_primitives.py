"""Exact source-derived conversion primitives. Future raw worker only."""
import h5py,numpy as np,pandas as pd
NTRAIN=20;NVAL=5
SOURCE_SHA='5f77fe3d25d120934c44c8ac1c26f07303eeec9db4821c69406726b141f66121'
EXPECTED={'/units/id':((182,),'i'),'/units/heldout':((182,),'b'),'/units/spike_times':((3642582,),'f'),'/units/spike_times_index':((182,),'u'),'/units/obs_intervals':((417690,2),'f'),'/units/obs_intervals_index':((182,),'u')}

def require(ok,message):
    if not ok: raise ValueError(message)

def text(value):
    if isinstance(value,bytes): return value.decode('utf8')
    require(isinstance(value,str),'Expected UTF8 metadata');return value

def dataset(f,key,shape,kind):
    require(isinstance(f.get(key,getlink=True),h5py.HardLink),'Non-hard HDF5 link: '+key)
    d=f[key];require(isinstance(d,h5py.Dataset) and d.shape==shape and d.dtype.kind==kind,'Unexpected dataset schema: '+key)
    require(not d.is_virtual and not d.external,'Virtual/external dataset forbidden')
    return d

def ragged_bounds(index,total):
    x=np.asarray(index,dtype=np.int64)
    require(x.ndim==1 and len(x)>0 and np.all(np.diff(x)>=0) and x[0]>=0 and x[-1]==total,'Invalid ragged end indices')
    return np.r_[0,x[:-1]],x

def integer_grid(onset_seconds):
    """Match source Pandas conversion and inclusive .loc endpoint minus1us."""
    onset=pd.to_timedelta(float(onset_seconds),unit='s')
    low=onset+pd.Timedelta(-250,unit='ms');high=onset+pd.Timedelta(450,unit='ms')-pd.Timedelta(1,unit='us')
    first=int(low.ceil('5ms').value//1000000)
    last=int(high.floor('5ms').value//1000000)
    grid=np.arange(first,last+1,5,dtype=np.int64)
    require(len(grid)==140 and np.array_equal(grid-int(onset.ceil('5ms').value//1000000),np.arange(-250,450,5)),
            'Alignment does not yield exact source-matched140bins')
    return grid

def observed(start_ms,stop_ms,intervals):
    # Same 1ms rounding/mask edges as official make_mask; require every 1ms
    # bin valid, stricter than resample's first-bin-only NaN propagation.
    left=np.ceil(np.round(intervals[:,0]*1000,6)).astype(np.int64)
    right=np.floor(np.round(intervals[:,1]*1000,6)).astype(np.int64)
    valid=np.zeros(stop_ms-start_ms,dtype=bool)
    for a,b in zip(left,right):
        if b<=start_ms or a>=stop_ms: continue
        valid[max(a,start_ms)-start_ms:min(b,stop_ms)-start_ms]=True
    return bool(valid.all())

def select_metadata(trials,group_intervals,ntrain=NTRAIN,nval=NVAL):
    """No spike/behavior values. Ranks fixed before opening spike timestamps."""
    n=len(trials['trial_id']);eligible={'train':[],'val':[]};exclusions={}
    starts=pd.to_timedelta(trials['start_time'],unit='s').asi8
    stops=pd.to_timedelta(trials['stop_time'],unit='s').asi8
    require(np.all(np.diff(starts)>0),'Trials not strictly chronological')
    for row in range(n):
        reason=None
        try:
            grid=integer_grid(trials['move_onset_time'][row]);a=int(grid[0]);b=a+700
            # More conservative than source: support inside own trial and before
            # immediate next trial start, including trials from the other split.
            if a*1000000<starts[row] or b*1000000>stops[row] or (row+1<n and b*1000000>starts[row+1]): reason='crosses_own_trial_or_next_start_boundary'
            elif not all(observed(a,b,x) for x in group_intervals): reason='incomplete_1ms_observation_support'
        except (ValueError,OverflowError): reason='noncanonical_alignment'
        if reason:
            exclusions[reason]=exclusions.get(reason,0)+1;continue
        eligible[trials['split'][row]].append({'row':row,'trial_id':int(trials['trial_id'][row]),
                'split':trials['split'][row],'start_ms':a,'stop_ms_exclusive':b,
                'move_onset_seconds':float(trials['move_onset_time'][row]),
                'condition':[int(trials['trial_type'][row]),int(trials['trial_version'][row])]})
    # Consecutive source trial starts already disjoint; also explicitly reject
    # overlap among any eligible grid supports (including cross-split supports).
    ordered=sorted(eligible['train']+eligible['val'],key=lambda x:x['start_ms'])
    require(all(x['stop_ms_exclusive']<=y['start_ms'] for x,y in zip(ordered,ordered[1:])),'Eligible source windows overlap')
    chosen=[]
    for split,k in [('train',ntrain),('val',nval)]:
        pool=eligible[split];require(len(pool)>=k,f'Insufficient eligible {split}: {len(pool)} < {k}')
        ranks=np.floor(np.arange(k)*(len(pool)-1)/max(k-1,1)).astype(int)
        chosen.extend(dict(pool[r],eligible_rank=int(r)) for r in ranks)
    return chosen,{'eligible_counts':{k:len(v) for k,v in eligible.items()},'exclusions':exclusions,
                   'selection_rule':'floor(i*(m-1)/(k-1)) within source split after timing/observation eligibility;20train5val; no count/success/behavior/condition balancing'}
