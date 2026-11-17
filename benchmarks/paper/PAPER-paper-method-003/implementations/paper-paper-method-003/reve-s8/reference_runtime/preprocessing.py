"""Actual physical-unit epoch preparation for selected canonical array sources.

Raw EDF/BDF/MAT decoding and biological alias proofs remain trusted ingest, never
inferred here. This actor consumes the authorized canonical continuous arrays.
"""
import numpy as np
from .catalog import need,canonical

def canonical_epochs(signal,sampling_hz,unit,start_stop,channel_indices):
    from scipy.signal import butter,sosfiltfilt,resample_poly
    from fractions import Fraction
    need(signal.ndim==2 and np.isfinite(signal).all(),'finite channels x time recording')
    need(unit in ('V','mV','uV') and type(sampling_hz)in(int,float) and sampling_hz>199,'declared physical rate/units')
    factor={'V':1000.,'mV':1.,'uV':.001}[unit];x=signal[np.asarray(channel_indices)]*factor
    # Explicit prospective 4th-order zero-phase bandpass. No guessed historical filter.
    upper=min(99.5,sampling_hz/2-.01);sos=butter(4,[.5,upper],btype='band',fs=sampling_hz,output='sos');x=sosfiltfilt(sos,x,axis=-1)
    ratio=Fraction(200/sampling_hz).limit_denominator(10000);x=resample_poly(x,ratio.numerator,ratio.denominator,axis=-1)
    windows=[]
    for a,b in start_stop:
        need(type(a)is type(b)is int and 0<=a<b<=x.shape[-1],'complete admitted window; no boundary padding');windows.append(x[:,a:b])
    need(len({w.shape for w in windows})==1,'homogeneous epoch shapes');return np.stack(windows).astype('<f4')

def prepare_products(io,c,ref):
    if 'corpus_preprocessing' in io.r['payload']:
        need('physical_preprocessing' not in io.r['payload'],'one scientific preparation route')
        from .corpus_preprocessing import prepare_corpus
        return prepare_corpus(io,c)
    recipe=io.r['payload']['physical_preprocessing'];need(set(recipe)=={'recording','sampling_hz','unit','windows','channels','positions','support','events','classes','rights','geometry_qualification'},'complete physical preparation selection')
    need(recipe['rights'] and recipe['geometry_qualification']==c['geometry_qualification'],'qualified raw rights/geometry')
    x=io.array(recipe['recording']);geometry=io.array(recipe['positions']);indices=recipe['channels'];need(len(indices)==len(set(indices)) and all(type(i)is int and 0<=i<len(x) for i in indices),'actual selected channels')
    epochs=canonical_epochs(x,recipe['sampling_hz'],recipe['unit'],recipe['windows'],indices)
    for name,s in io.r['expected_outputs'].items():
        need(s['kind']=='preprocessing','physical preparation output');sig=io.write_array(name+'.epochs.npy',epochs);geo=io.write_array(name+'.positions.npy',geometry[indices])
        io.emit(name,{'raw_support':recipe['support'],'epoch_support':recipe['events'],'unit_projection':{'physical':'mV','sampling_hz':200,'signal':sig,'positions':geo},'clock_mapping':recipe['windows'],'fitted_dependencies':[],'recipe':{'id':'S7-prospective-canonical-epoch-filter-v1','band':[.5,99.5],'order':4,'phase':'zero','historical_qualified':False},'state':None,'exclusions':{'padding':False,'channels_not_selected':sorted(set(range(len(x)))-set(indices))}},[sig,geo])


def corpus_windows(recording,sampling_hz,unit,session_bounds):
    """Explicit prospective session statistic projection; no cross-session window."""
    windows=[];records=[]
    for session,(start,stop) in enumerate(session_bounds):
        need(type(start)is type(stop)is int and 0<=start<stop<=recording.shape[-1],'qualified session boundary')
        raw=recording[:,start:stop];length=int((stop-start)*200/sampling_hz)
        if length<2000:
            records.append({'session':session,'disposition':'excluded_shorter_than10seconds','samples':length});continue
        # Filter/resample the complete authorized session before fitting its own
        # unlabeled statistics; downstream exclusion is independently required.
        transformed=canonical_epochs(raw,sampling_hz,unit,[(0,length)],list(range(len(raw))))[0].astype('float64')
        anchor=transformed[:,:1];center=(transformed-anchor).mean(-1,keepdims=True)+anchor;scale=transformed.std(-1,keepdims=True);constant=scale==0;scale[constant]=1.
        z=np.clip((transformed-center)/scale,-15,15);z[np.repeat(constant,z.shape[-1],axis=1)]=0.
        starts=list(range(0,length-2000+1,2000))
        windows.extend(z[:,a:a+2000].astype('<f4') for a in starts)
        records.append({'session':session,'disposition':'included','starts_200Hz':starts,'discarded_tail':length-(starts[-1]+2000),'normalizer_mean':center.tolist(),'normalizer_scale':scale.tolist(),'constant_channels':constant[:,0].tolist()})
    return windows,records
