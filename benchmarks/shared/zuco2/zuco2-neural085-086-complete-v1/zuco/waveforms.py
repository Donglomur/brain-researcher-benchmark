"""Independent prospective waveform features; not author Hilbert power reproduction."""
from .io import need,Refusal
from .constants import BAND_HZ

def stretches(mask):
    start=None
    for i,x in enumerate(list(mask)+[False]):
        if x and start is None:start=i
        if not x and start is not None:yield start,i;start=None

def segment_features(s):
    import numpy as np
    from scipy.signal import welch
    a=np.asarray(s["values"],float);mask=np.asarray(s["valid"],bool)&np.isfinite(a);need(a.ndim==2 and a.shape[1]==105 and mask.shape==a.shape,"waveform105")
    v=[]
    for c in range(105):
        good=a[mask[:,c],c];v.extend([float(np.mean(good)),float(np.var(good))] if len(good) else [np.nan,np.nan])
        for inds in np.array_split(np.arange(len(a)),10):
            x=a[inds,c][mask[inds,c]];v.extend([float(np.mean(x)),float(np.var(x))] if len(x) else [np.nan,np.nan])
        spectra=[]
        for lo,hi in stretches(mask[:,c]):
            x=a[lo:hi,c]
            if len(x)<2:continue
            n=min(250,len(x));f,p=welch(x,fs=500.,window="hann",nperseg=n,noverlap=n//2,nfft=n,detrend="constant",scaling="density")
            bands=[]
            for low,high in BAND_HZ:
                ok=(f>=low)&(f<=high);bands.append(float(np.trapz(p[ok],f[ok])) if np.count_nonzero(ok)>=2 else np.nan)
            spectra.append((len(x),np.asarray(bands)))
        for k in range(8):
            rows=[(n,z[k]) for n,z in spectra if np.isfinite(z[k])];v.append(np.log1p(sum(n*x for n,x in rows)/sum(n for n,x in rows)) if rows else np.nan)
    both=mask.all(axis=1);cov=None
    if both.sum()>=2:
        x=a[both];c=np.cov(x,rowvar=False,ddof=1);cov=.9*c+.1*np.trace(c)/105*np.eye(105)
    return np.asarray(v),cov,int(mask.sum()),len(a)

def spd(a):
    import numpy as np
    if a is None or not np.isfinite(a).all():return False
    v=np.linalg.eigvalsh(a);return bool(v[-1]>0 and v[0]>v[-1]*1e-12)
def tangent(c,g):
    import numpy as np
    if not spd(c) or not spd(g):return None
    val,vec=np.linalg.eigh(g);root=(vec*(val**-.5))@vec.T;m=root@c@root;d,u=np.linalg.eigh((m+m.T)/2)
    if d[0]<=d[-1]*1e-12:return None
    log=(u*np.log(d))@u.T;i,j=np.triu_indices(105);return log[i,j]*np.where(i==j,1.,np.sqrt(2.))
class WaveFeatures:
    def fit(self,rows,weights):
        import numpy as np
        cs=[]
        for segments,w in zip(rows,weights):
            covs=[(n,c) for s in segments for _,c,_,n in [segment_features(s)] if spd(c)]
            if covs:cs.append((w,sum(n*c for n,c in covs)/sum(n for n,c in covs)))
        need(cs,"training_covariance_reference_unavailable");self.g=sum(w*c for w,c in cs)/sum(w for w,c in cs);need(spd(self.g),"training_tangent_origin_unavailable")
    def transform(self,rows):
        import numpy as np
        out=[];n_features=105*30;cov_n=105*106//2
        for segments in rows:
            summaries=[];covs=[];valid=0;total=0
            for s in segments:
                v,c,n,N=segment_features(s);summaries.append((N,v));t=tangent(c,self.g)
                if t is not None:covs.append((N,t))
                valid+=n;total+=N*105
            if summaries:
                vals=np.stack([v for n,v in summaries]);ww=np.asarray([n for n,v in summaries])[:,None];ok=np.isfinite(vals);num=np.where(ok,vals,0)*ww;den=(ok*ww).sum(axis=0);a=np.divide(num.sum(axis=0),den,out=np.full(n_features,np.nan),where=den>0)
            else:a=np.full(n_features,np.nan)
            c=sum(n*t for n,t in covs)/sum(n for n,t in covs) if covs else np.full(cov_n,np.nan)
            out.append(np.r_[a,c])
        return np.asarray(out)
