"""Independent R1 two-pass transforms and complete masked periodogram features."""
from .contract import WINDOWS, BANDS


def batch_admit(np, batch, view, budget):
    keys={'schema','ids','axis','x','mask','offsets','context'}
    if type(batch) is not dict or set(batch)!=keys or batch['schema']!='neural049_numeric_batch_v1':
        budget.fail('exact primitive batch schema required')
    ids,axis=batch['ids'],batch['axis']
    if type(ids) is not list or any(type(v) is not str or not v for v in ids) or len(ids)!=len(set(ids)):
        budget.fail('complete unique ordered event IDs required')
    if type(axis) is not list or not axis or any(type(v) is not str or not v for v in axis) or len(axis)!=len(set(axis)):
        budget.fail('complete unique ordered channel axis required')
    n,c=len(ids),len(axis)
    def array(a,dtype,shape):
        return type(a) is np.ndarray and a.dtype==np.dtype(dtype) and a.shape==shape and a.flags.c_contiguous
    if not array(batch['mask'],'bool',(n,c,5000)) or not array(batch['offsets'],'float64',(n,)):
        budget.fail('mask/offset primitive dtype or shape')
    budget.reserve('batch-scan',allocation_bytes=max(1,n*c*5000*2+n*5000*24),
                   elements=max(1,n*c*10000+n*15000),work=max(1,n*c*5000*8),
                   live_bytes=max(1,n*c*5000*16+n*5000*24))
    if not np.isfinite(batch['offsets']).all() or not ((batch['offsets']>=0)&(batch['offsets']<0.002)).all():
        budget.fail('fractional source-grid offset')
    if view=='C':
        if batch['x'] is not None: budget.fail('C must not admit waveform magnitudes')
    else:
        x=batch['x']
        if not array(x,'float64',(n,c,5000)) or not np.isfinite(x).all(): budget.fail('waveform primitive contract')
        if np.any(x[~batch['mask']]!=0): budget.fail('masked input must be neutral zero')
    if view=='N':
        if batch['context'] is not None: budget.fail('N excludes timing predictors')
    else:
        if not array(batch['context'],'float64',(n,6)) or not np.isfinite(batch['context']).all():
            budget.fail('six timing predictors required')
    for i in range(n): window_indices(np,float(batch['offsets'][i]))
    budget.tick()
    return n,c


def window_indices(np, offset):
    r=-5.0+offset+np.arange(5000,dtype=np.float64)/500.0
    result=[]
    for lo,hi in WINDOWS:
        idx=np.flatnonzero((r>=lo)&(r<hi))
        if len(idx)!=int(round((hi-lo)*500)):
            raise ValueError('actual source-relative window membership mismatch')
        result.append(idx)
    return result


def two_pass(np, a):
    """Population column statistics; the caller pre-admits full allocation plan."""
    n=a.shape[0]
    if n==0: raise ValueError('empty statistics scope')
    mean=np.zeros(a.shape[1:],dtype=np.float64)
    for i in range(n): mean+=a[i]
    mean/=n
    ss=np.zeros_like(mean)
    for i in range(n): ss+=(a[i]-mean)**2
    scale=np.sqrt(ss/n)
    active=scale>0
    safe=np.where(active,scale,1.0)
    if not np.isfinite(mean).all() or not np.isfinite(safe).all(): raise ValueError('statistics overflow')
    return {'mean':mean,'scale':safe,'active':active}


def channel_fit(np,batch,view,budget):
    n,c=batch['mask'].shape[:2]
    mean=np.zeros(c,np.float64); scale=np.ones(c,np.float64); active=np.zeros(c,bool)
    if view=='C': return {'mean':mean,'scale':scale,'active':active}
    x,m=batch['x'],batch['mask']
    for k in range(c):
        budget.tick(); count=0; total=0.0
        for i in range(n):
            values=x[i,k][m[i,k]]; count+=len(values); total+=float(np.sum(values,dtype=np.float64))
        if not count: continue
        mean[k]=total/count; ss=0.0
        for i in range(n):
            values=x[i,k][m[i,k]]-mean[k]; ss+=float(np.sum(values*values,dtype=np.float64))
        s=float(np.sqrt(ss/count))
        if not np.isfinite(mean[k]) or not np.isfinite(s): budget.fail('channel statistics overflow')
        if s>0: scale[k]=s; active[k]=True
    return {'mean':mean,'scale':scale,'active':active}


def normalized(np,batch,view,stats):
    shape=batch['mask'].shape
    if view=='C': return np.zeros(shape,np.float64)
    y=(batch['x']-stats['mean'][None,:,None])/stats['scale'][None,:,None]
    y=np.where(batch['mask']&stats['active'][None,:,None],y,0.0)
    if not np.isfinite(y).all(): raise ValueError('normalized waveform overflow')
    return y


def longest_false(mask):
    best=run=0
    for v in mask:
        run=0 if bool(v) else run+1
        best=max(best,run)
    return best


def spectrum(np,x,mask):
    """Component primitive also used for tiny selected analytic controls."""
    L=len(x)
    if L<2 or mask.shape!=x.shape: raise ValueError('spectrum shape')
    w=0.5-0.5*np.cos(2*np.pi*np.arange(L,dtype=np.float64)/(L-1))
    v=w*mask
    vv=float(np.sum(v*v,dtype=np.float64))
    if vv==0: return np.zeros(9,np.float64),False
    center=float(np.sum(v*x,dtype=np.float64)/np.sum(v,dtype=np.float64))
    z=v*(x-center)
    transformed=np.fft.rfft(z)
    p=(transformed.real**2+transformed.imag**2)/(500.0*vv)
    if L%2==0: p[1:-1]*=2
    else: p[1:]*=2
    freq=np.arange(len(p),dtype=np.float64)*500.0/L
    out=np.empty(9,np.float64)
    for b,(lo,hi) in enumerate(BANDS):
        keep=(freq>=lo)&((freq<=hi) if b==8 else (freq<hi))
        out[b]=np.log(float(np.sum(p[keep],dtype=np.float64))*500.0/L+1e-12)
    if not np.isfinite(out).all(): raise ValueError('periodogram overflow')
    return out,True


def raw_features(np,batch,view,channel,budget,temporal=False):
    n,c=batch['mask'].shape[:2]
    wave=normalized(np,batch,view,channel)
    masks=np.empty((n,c,12,4),np.float64)
    neural=None if temporal else np.zeros((n,c,117),np.float64)
    for i in range(n):
        budget.tick(); windows=window_indices(np,float(batch['offsets'][i]))
        for k in range(c):
            supports=[]; powers=[]
            for j,idx in enumerate(windows):
                m=batch['mask'][i,k,idx]; L=len(idx)
                w=0.5-0.5*np.cos(2*np.pi*np.arange(L,dtype=np.float64)/(L-1))
                positive=bool(np.any(m&(w>0)))
                masks[i,k,j]=(float(np.sum(m))/L,longest_false(m)/L,float(np.any(m)),float(positive))
                if not temporal:
                    if view=='C': power,ok=np.zeros(9,np.float64),False
                    else: power,ok=spectrum(np,wave[i,k,idx],m)
                    neural[i,k,j*9:(j+1)*9]=power; supports.append(ok); powers.append(power)
            if not temporal and supports[10] and supports[11]: neural[i,k,108:117]=powers[11]-powers[10]
    context=np.zeros((n,6),np.float64) if view=='N' else batch['context']
    structural=np.concatenate((context,masks.reshape(n,48*c)),axis=1)
    if temporal: return {'wave':wave,'structural':structural}
    # Exact column order: timing6, channel-major (12window×9band +9contrast),
    # then channel-major 12window×4mask. No hidden feature filtering.
    return np.concatenate((context,neural.reshape(n,117*c),masks.reshape(n,48*c)),axis=1)


def apply_stats(np,a,s):
    result=np.where(s['active'],(a-s['mean'])/s['scale'],0.0)
    if not np.isfinite(result).all(): raise ValueError('scalar normalization overflow')
    return result


def feature_transform(batch,view,budget,environment,statistics=None,temporal=False):
    from .contract import numpy_checked
    from .budget import dimensions
    np=numpy_checked(environment)
    n,c=batch_admit(np,batch,view,budget)
    dimensions(n,c,'F',{},budget,training=statistics is None,native_workspace=environment['native_workspace_bytes'])
    if statistics is None:
        if n==0: budget.fail('empty training feature scope')
        channel=channel_fit(np,batch,view,budget)
    else: channel=statistics['channel']
    raw=raw_features(np,batch,view,channel,budget,temporal)
    values=raw['structural'] if temporal else raw
    scalar=two_pass(np,values) if statistics is None else statistics['scalar']
    scaled=apply_stats(np,values,scalar)
    budget.tick()
    result={'wave':raw['wave'],'structural':scaled} if temporal else scaled
    return result,{'channel':channel,'scalar':scalar}
