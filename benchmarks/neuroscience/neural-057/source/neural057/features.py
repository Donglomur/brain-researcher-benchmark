"""Prospective deterministic image/EEG feature producers. Never run during construction."""
from .domain import need

def image_features(image_bytes):
    import io
    import numpy as np
    from PIL import Image
    with Image.open(io.BytesIO(image_bytes)) as im:
        need(im.mode=='RGB' and im.width>=8 and im.height>=8,'qualified original RGB image without conversion')
        need(im.getexif().get(274,1)==1,'no implicit orientation change')
        a=np.asarray(im,dtype=np.float64)/255.0
    need(a.ndim==3 and a.shape[2]==3 and np.isfinite(a).all(),'finite RGB pixels')
    y=.2126*a[:,:,0]+.7152*a[:,:,1]+.0722*a[:,:,2]
    gx=(y[:-2,2:]+2*y[1:-1,2:]+y[2:,2:])-(y[:-2,:-2]+2*y[1:-1,:-2]+y[2:,:-2])
    gy=(y[2:,:-2]+2*y[2:,1:-1]+y[2:,2:])-(y[:-2,:-2]+2*y[:-2,1:-1]+y[:-2,2:])
    magnitude=np.hypot(gx,gy);bins=np.floor((np.arctan2(gy,gx)+np.pi)*(8/(2*np.pi))).astype(int)%8
    colors=[];edges=[]
    for r in range(4):
        for c in range(4):
            block=a[r*a.shape[0]//4:(r+1)*a.shape[0]//4,c*a.shape[1]//4:(c+1)*a.shape[1]//4]
            colors.extend(block.mean(axis=(0,1)).tolist())
            sl=(slice(r*gx.shape[0]//4,(r+1)*gx.shape[0]//4),slice(c*gx.shape[1]//4,(c+1)*gx.shape[1]//4))
            n=magnitude[sl].size
            edges.extend(float(magnitude[sl][bins[sl]==b].sum()/n) for b in range(8))
    v=np.asarray(colors+edges,dtype='<f8');need(v.shape==(176,) and np.isfinite(v).all(),'fixed 48 RGB +128 Sobel features')
    return v

def mean_eeg(array, repeats, windows):
    import numpy as np
    need(type(array) is np.ndarray and array.dtype.kind=='f' and array.shape[1:]==(repeats,17,100),'exact released epoch axes')
    need(np.isfinite(array).all(),'finite original EEG')
    mean=array.mean(axis=1,dtype=np.float64)
    return {k:np.ascontiguousarray(mean[:,:,ids].reshape(len(array),-1),dtype='<f8') for k,ids in windows.items()}

def panel_features(image, eeg, panel):
    import numpy as np
    need(panel in ('IMAGE','PRE','BASE','LATE'),'closed panel')
    parts={'IMAGE':(image,),'PRE':(eeg['PRE'],),'BASE':(image,eeg['PRE']),'LATE':(image,eeg['PRE'],eeg['LATE'])}[panel]
    need(all(type(x) is np.ndarray and x.ndim==2 and x.shape[0]==image.shape[0] and np.isfinite(x).all() for x in parts),'complete matched rows')
    return np.ascontiguousarray(np.concatenate(parts,axis=1),dtype='<f8')
