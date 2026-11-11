"""Admitted numeric projections; no pickle, downloads, guessing of original schemas."""
import io
from .custody import need, read_pin
from .guard import integer, real, RequiredUnscorable
from .numerics import matrix, zscore

def read_npz(root, binding, shapes, budget, cap):
    """Only called after evidence/role admission; exact numeric schema is mandatory."""
    import numpy as np
    import zipfile
    raw=read_pin(root,binding,cap,budget)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        members=z.infolist()
        need(len(members)==len(shapes) and len({m.filename for m in members})==len(members),'exact archive member census')
        need({m.filename for m in members}=={k+'.npy' for k in shapes},'exact npz schema; no hidden or pickle members')
        need(all(not m.is_dir() and m.flag_bits & 1 == 0 for m in members),'ordinary unencrypted members')
        # Authenticate bounded NPY headers before NumPy can allocate anything.
        # Do not use np.load here: a small ZIP can declare an enormous array.
        import ast, math
        headers={};payload_total=0
        for member in members:
            name=member.filename[:-4];spec=shapes[name]
            need(type(spec)is dict and set(spec)=={'shape','dtype'},'exact numeric leaf schema')
            shape=spec['shape'];need(type(shape)is list and len(shape)<=32,'bounded numeric rank')
            for n in shape:integer(n,0)
            dtype=np.dtype(spec['dtype'])
            need(dtype.kind in 'biufc'and dtype.str==spec['dtype'],'canonical nonobject numerical dtype')
            count=math.prod(shape);size=count*dtype.itemsize
            need(size<=budget.array_cap,'single decoded array fits selected logical allowance')
            with z.open(member)as stream:
                prefix=stream.read(8)
                need(prefix[:6]==b'\x93NUMPY'and prefix[6:]in (b'\x01\x00',b'\x02\x00',b'\x03\x00'),'supported ordinary NPY version')
                width=2 if prefix[6:]==b'\x01\x00'else 4
                raw_length=stream.read(width);need(len(raw_length)==width,'complete NPY header length')
                length=int.from_bytes(raw_length,'little');need(0<length<=4096,'bounded NPY header before decode')
                raw_header=stream.read(length);need(len(raw_header)==length,'complete bounded NPY header')
                header=ast.literal_eval(raw_header.decode('utf8'if prefix[6:]==b'\x03\x00'else'latin1'))
                need(type(header)is dict and set(header)=={'descr','fortran_order','shape'},'ordinary NPY header keys')
                need(header['descr']==dtype.str and type(header['shape'])is tuple and list(header['shape'])==shape
                     and all(type(n)is int for n in header['shape'])and type(header['fortran_order'])is bool,'exact preallocation header/schema')
                offset=8+width+length
                need(member.file_size==offset+size,'exact declared uncompressed extent before allocation')
                headers[name]=(member,offset,size,dtype,shape,header['fortran_order'])
            payload_total+=size
        expanded=3*payload_total;budget.reserve_array(expanded)
        try:
            out={}
            for name,(member,offset,size,dtype,shape,fortran)in headers.items():
                with z.open(member)as stream:
                    need(len(stream.read(offset))==offset,'complete admitted header')
                    payload=stream.read(size+1)
                    need(len(payload)==size and stream.read(1)==b'','complete exact bounded numerical payload')
                x=np.frombuffer(payload,dtype=dtype).reshape(shape,order='F'if fortran else'C')
                need(np.isfinite(x).all(),'finite nonobject numerical source')
                out[name]=x.copy()
            return out,expanded
        except BaseException:
            budget.release_array(expanded);raise

def calcium(spikes,x,y,*,crop_start,figure):
    import numpy as np
    a=matrix(spikes);integer(crop_start,0,a.shape[1]-1)
    need(figure in ('figure2','figure3'),'explicit crop convention')
    x=np.asarray(x);y=np.asarray(y)
    need(x.shape==y.shape==(a.shape[0],) and np.isfinite(x).all() and np.isfinite(y).all(),'complete ROI geometry')
    if figure=='figure2':a=a[:,crop_start:]
    return {'activity':zscore(a),'x':x,'y':y,'rate_hz':22.0,'crop_start':crop_start if figure=='figure2' else 0,
            'unit_indices':np.arange(len(a))}

def ephys(times,clusters,y,probe,*,bin_seconds,overflow,eligibility_bin_seconds=1/22):
    import numpy as np
    real(bin_seconds,0);need(bin_seconds>0,'positive sampling interval')
    need(overflow in ('literal_uint8','corrected_int64'),'explicit aggregation variant')
    t=np.asarray(times,dtype='float64');c=np.asarray(clusters)
    need(t.ndim==c.ndim==1 and len(t)==len(c)>0 and c.dtype.kind in 'iu' and c.min()>=0 and np.isfinite(t).all(),'complete spike event arrays')
    n=int(c.max())+1;t=t-t.min();y=np.asarray(y);probe=np.asarray(probe)
    need(y.shape==probe.shape==(n,) and np.isfinite(y).all() and np.isfinite(probe).all(),'full source unit map')
    def count(dt):
        b=np.rint(t/dt).astype('int64')
        a=np.zeros((n,int(b.max())+1),dtype='int64');np.add.at(a,(c,b),1)
        wrap=int((a>255).sum())
        return (a.astype('uint8').astype('float64') if overflow=='literal_uint8' else a.astype('float64')),wrap
    eligibility,_=count(eligibility_bin_seconds)
    keep=eligibility.mean(axis=1)>0.01*eligibility_bin_seconds
    a,wrapped=count(bin_seconds)
    need(keep.any(),'no eligible original units')
    return {'activity':zscore(a[keep]),'raw_counts':a[keep],'unit_indices':np.flatnonzero(keep),
            'x':probe[keep].astype('float64')*0,'y':y[keep],'rate_hz':1/bin_seconds,
            'overflow_cells':wrapped,'overflow_variant':overflow,'eligibility_bin_seconds':eligibility_bin_seconds}

def time_chunks(n,*,fraction,pad,fold):
    """Literal held NumPy RandomState law, returned state for shuffle coupling."""
    import numpy as np
    integer(n,20);integer(pad);integer(fold);real(fraction,0,1)
    segments=int(min(40,n/4));length=int(np.floor(n/segments))-pad
    ntest=int(np.floor(segments*fraction));need(length>0 and ntest>0,'valid original split geometry')
    split=segments//ntest;need(fold<split,'valid source fold')
    starts=np.linspace(0,n-length-5,segments).astype('int64')
    rng=np.random.RandomState(0);which=rng.randint(0,split,segments)==fold
    train=(starts[~which,None]+np.arange(length)).ravel()
    test=(starts[which,None]+np.arange(length)).ravel()
    need(len(train) and len(test) and min(train.min(),test.min())>=0 and max(train.max(),test.max())<n,'complete temporal fold')
    return train,test,rng.get_state()

def shuffle_schedule(value,half_indices,shifts):
    """Exact disclosed source draws; never substitute NumPy for Torch randperm."""
    import numpy as np
    a=matrix(value).copy();ids=np.asarray(half_indices);s=np.asarray(shifts)
    need(ids.ndim==2 and ids.dtype.kind in 'iu' and ids.shape[1]==len(a)//2 and s.shape==(len(ids),) and s.dtype.kind in 'iu','complete shuffle schedule')
    need(len(ids)==500 and ids.min()>=0 and ids.max()<len(a) and s.min()>=0 and s.max()<a.shape[1],'all500 valid source shuffle operations')
    for ix,shift in zip(ids,s):
        need(len(set(ix))==len(ix),'without replacement half-neuron draw')
        a[ix]=np.roll(a[ix],int(shift),axis=1)
    return a

def subsample(value,x,y,*,neuron_fraction=None,time_keep=None):
    import numpy as np
    a=matrix(value);x=np.asarray(x);y=np.asarray(y)
    need(x.shape==y.shape==(len(a),),'aligned original geometry')
    need((neuron_fraction is None)!=(time_keep is None),'one declared perturbation per cell')
    if neuron_fraction is not None:
        real(neuron_fraction,0,1);n=int(len(a)*neuron_fraction);need(n>1,'insufficient original neuron count')
        return a[:n],x[:n],y[:n]
    integer(time_keep,1,4000);selected=np.arange(a.shape[1])%4000<time_keep
    return zscore(a[:,selected],1e-3),x,y

def behavioural_states(value,run_flags,*,minimum_fraction,dmd_minimum_seconds,sampling_hz):
    import numpy as np
    a=matrix(value);f=np.asarray(run_flags)
    need(f.dtype.kind=='b' and f.shape==(a.shape[1],),'source time aligned state vector')
    real(minimum_fraction,0,.5);real(dmd_minimum_seconds,0);real(sampling_hz,0);need(sampling_hz>0,'positive sample rate')
    run=np.flatnonzero(f);still=np.flatnonzero(~f);n=min(len(run),len(still))
    eligible=n>=minimum_fraction*a.shape[1]
    # Both original endpoint sets are retained even when not scientifically eligible.
    return {'run':run[:n],'still':still[:n],'all_run':run,'all_still':still,
            'spectrum_eligible':bool(eligible),'dmd_eligible':bool(eligible and n/sampling_hz>=dmd_minimum_seconds),
            'minimum_fraction':minimum_fraction,'minimum_seconds':dmd_minimum_seconds}

def fluorescence_bin(value,factor):
    import numpy as np
    a=matrix(value);integer(factor,1);n=a.shape[1]//factor
    need(n>1,'full fluorescence bin support')
    return a[:,:n*factor].reshape(len(a),n,factor).mean(axis=2)

def missing_projection(role):
    gates={'new_deconvolution':'G06','legacy_matlab_projection':'G05','external_task_projection':'G07','rastermap_original_display':'G09'}
    need(role in gates,'named original source projection')
    raise RequiredUnscorable(gates[role],'Original projection source/runtime/schema is not present; no substituted adapter is claimed',{'role':role})

