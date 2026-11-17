"""Bounded primitive epoch reader. Called only inside the selected capsule."""
import io,zipfile
from pathlib import Path
from core import capture,need,integer

FIELDS={'lfp','lfp_region','spike_times','spike_offsets','unit_region'}

def load_epoch(root,row,budget,cap,regions):
    import numpy as np
    path=Path(root)/row['epoch']['path'];raw,_=capture(path,row['epoch']['pin'],cap,budget,readonly=True)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        info=z.infolist();need(len(info)==5 and {x.filename for x in info}=={x+'.npy' for x in FIELDS},'exact primitive epoch members')
        need(all(x.compress_type==zipfile.ZIP_STORED and not x.flag_bits&1 and x.file_size<=cap for x in info),'uncompressed ordinary epoch members')
        need(all(x.date_time==(1980,1,1,0,0,0) and not x.comment for x in info),'no creation-time or comment order proxy')
        need(sum(x.file_size for x in info)<=cap,'full decoded epoch bound before allocation')
        result={}
        for i in info:
            with z.open(i) as f:
                version=np.lib.format.read_magic(f);need(version in((1,0),(2,0)),'bounded NPY primitive header')
                shape,fortran,dtype=np.lib.format._read_array_header(f,version,max_header_size=1024)
                need(not fortran and dtype.kind in 'fi' and dtype.itemsize in(4,8) and len(shape)<=2,'no object, structured or higher-rank payload')
                elements=1
                for n in shape:integer(n,0,cap);elements*=n
                need(elements*dtype.itemsize<=cap,'primitive advertised extent before allocation')
            value=np.load(io.BytesIO(z.read(i)),allow_pickle=False,max_header_size=1024)
            need(np.isfinite(value).all(),'complete finite epoch; no numerical deletion');result[i.filename[:-4]]=value
    x=result['lfp'];lr=result['lfp_region'];st=result['spike_times'];so=result['spike_offsets'];ur=result['unit_region']
    need(x.ndim==2 and x.shape[1]==1000 and lr.shape==(x.shape[0],),'equal 1000-sample LFP/channel mapping')
    need(so.ndim==1 and len(so)==len(ur)+1 and so[0]==0 and so[-1]==len(st) and (np.diff(so)>=0).all(),'complete unit spike ragged map')
    need(st.ndim==1 and ((st>=0)&(st<2.5)).all(),'half-open 2.5 s spikes')
    for labels in(lr,ur):need(labels.dtype.kind=='i' and ((labels>=0)&(labels<len(regions))).all(),'fixed anatomical region indices')
    need(so.dtype.kind=='i','integer spike offsets')
    for lo,hi in zip(so[:-1],so[1:]):need((np.diff(st[lo:hi])>=0).all(),'sorted per-unit relative times')
    return result
