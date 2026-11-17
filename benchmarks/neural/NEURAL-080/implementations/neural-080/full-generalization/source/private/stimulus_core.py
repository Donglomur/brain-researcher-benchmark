"""Prospective low-level controls from explicitly decoded audiovisual packets.

These features do not claim to exhaust acoustic/ocular/motion information or
isolate high-level visual semantics. Authentic clip identity and presentation
clock bindings are required upstream and currently absent.
"""
import numpy as np


def need(ok,msg):
    if not ok:raise ValueError(msg)


def spatial_cells(frame):
    """All pixels, native aspect ratio,8×8 spatial cell means,RGB/255."""
    a=np.asarray(frame)
    need(a.dtype==np.dtype('uint8') and a.ndim==3 and a.shape[2]==3 and min(a.shape[:2])>=8,'Decoded native RGBuint8 frame')
    h,w=a.shape[:2];ys=np.arange(9)*h//8;xs=np.arange(9)*w//8
    return np.asarray([[a[ys[i]:ys[i+1],xs[j]:xs[j+1]].mean((0,1))/255. for j in range(8)] for i in range(8)])


def appearance(cells,starts,ends):
    """Duration-weighted30×100ms appearance bins using actual frame intervals."""
    x=np.asarray(cells,float);a=np.asarray(starts,float);b=np.asarray(ends,float)
    need(x.ndim==4 and x.shape[1:]==(8,8,3) and 1<=len(x)<=1000 and a.shape==b.shape==(len(x),),'Bounded frame-cell/clock geometry')
    need(np.isfinite(x).all() and (x>=0).all() and (x<=1).all() and np.isfinite(a).all() and np.isfinite(b).all(),'Finite RGBcells and timestamps')
    need((b>a).all() and a[0]<=0 and b[-1]>=3 and np.allclose(b[:-1],a[1:],atol=1e-9,rtol=0),'Continuous explicit frame support over[0,3), no guessed frame rate')
    out=[]
    for i in range(30):
        weights=np.maximum(0.,np.minimum(b,(i+1)/10)-np.maximum(a,i/10))
        need(abs(weights.sum()-.1)<=1e-8,'Complete100ms frame coverage')
        anchor=x[np.flatnonzero(weights>0)[0]]
        out.append(anchor+np.tensordot(weights/weights.sum(),x-anchor,axes=(0,0)))
    out=np.asarray(out).reshape(30,192);need(np.isfinite(out).all(),'Finite duration-weighted appearance')
    return out


def video_features(appearance_bins):
    x=np.asarray(appearance_bins,float);need(x.shape==(30,192) and np.isfinite(x).all(),'All30 appearance bins')
    delta=x-x[0];center=delta.mean(0);dynamic=delta-center
    pooled=np.r_[x[0]+center,np.sqrt(np.mean(dynamic*dynamic,axis=0))]
    luminance_proxy=x.reshape(30,64,3).mean(-1)
    motion=np.vstack((np.zeros((1,64)),np.abs(np.diff(luminance_proxy,axis=0))))
    return {'static':pooled,'motion':motion,'dynamic':dynamic}


def acoustic(samples,rate,first_sample_s):
    """30×10 controls: per-channel power/zero crossings and8spectral bands.

    No resampling, per-clip fitting, model inference or silent absent audio. A
    silent authenticated audio track is valid; no track is a provisioning gap.
    """
    x=np.asarray(samples,float)
    need(x.ndim==2 and 1<=x.shape[1]<=8 and type(rate) is int and 8000<=rate<=192000,'Decoded audio samples×channels and explicit rate')
    need(np.isfinite(x).all() and (np.abs(x)<=1.000001).all() and np.isfinite(first_sample_s),'Normalized decoded audio and explicit presentation origin')
    t=first_sample_s+np.arange(len(x))/rate
    need(len(t)>1 and t[0]<=0 and t[-1]+1/rate>=3-1e-9,'Explicit audio support throughout[0,3)')
    out=[]
    for i in range(30):
        lo,hi=np.searchsorted(t,[i/10,(i+1)/10],side='left');s=x[lo:hi]
        need(len(s)>=2 and abs(len(s)/rate-.1)<=1/rate+1e-9,'Native audio samples for each100ms interval')
        rms=np.sqrt(np.mean(s*s));cross=np.mean((s[1:]>0)!=(s[:-1]>0))
        window=np.hanning(len(s))[:,None];spectrum=np.abs(np.fft.rfft(s*window,axis=0))**2
        frequencies=np.fft.rfftfreq(len(s),1/rate);edges=np.linspace(0,rate/2,9)
        bands=[]
        for j in range(8):
            take=(frequencies>=edges[j])&((frequencies<edges[j+1]) if j<7 else (frequencies<=edges[j+1]))
            need(take.any(),'Nonempty acoustic band')
            bands.append(np.log1p(spectrum[take].mean()/len(s)**2))
        out.append([rms,cross,*bands])
    result=np.asarray(out);need(np.isfinite(result).all(),'Finite acoustic features');return result
