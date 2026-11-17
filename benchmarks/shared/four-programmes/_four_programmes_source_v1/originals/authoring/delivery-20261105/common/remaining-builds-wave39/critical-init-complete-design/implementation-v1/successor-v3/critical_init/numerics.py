"""Independent numerical algorithms; caller must supply admitted complete support.

These implementations are paper/corrected variants. Author-source parity is
separate and requires the complete native source and numerical qualification.
No module import triggers fitting or numerical work.
"""
import math
from .guard import real,integer,RequiredUnscorable
from .custody import need

def matrix(value):
    import numpy as np
    x=np.asarray(value)
    need(x.ndim==2 and x.size and x.dtype.kind in 'fiu' and np.isfinite(x).all(),'finite nonempty real matrix')
    return x.astype('float64',copy=False)

def zscore(value,eps=0.0,ddof=0):
    import numpy as np
    x=matrix(value);real(eps,0);integer(ddof,0,1)
    scale=x.std(axis=1,ddof=ddof,keepdims=True)
    need(np.all(scale+eps>0),'undefined zero-variance source unit')
    return (x-x.mean(axis=1,keepdims=True))/(scale+eps)

def spatial_split(x,y,spacing):
    import numpy as np
    x=np.asarray(x,dtype='float64');y=np.asarray(y,dtype='float64');real(spacing,0)
    need(spacing>0 and x.ndim==y.ndim==1 and x.shape==y.shape and np.isfinite(x).all()and np.isfinite(y).all(),'aligned geometry')
    mask=((x%(2*spacing)<spacing).astype('int64')+(y%(2*spacing)<spacing).astype('int64'))%2==0
    need(mask.any()and (~mask).any(),'nonempty spatial halves')
    return mask

def spectra(value,mask,train_times=None,test_times=None):
    import numpy as np
    x=matrix(value);mask=np.asarray(mask)
    need(mask.dtype.kind=='b' and mask.shape==(x.shape[0],)and mask.any()and(~mask).any(),'complete neuron split')
    direct=np.linalg.eigvalsh(x@x.T/x.shape[1])[::-1]
    cross=x[mask]@x[~mask].T
    unnormalized=np.linalg.svd(cross,compute_uv=False)
    undefined=list(range(len(unnormalized),int(mask.sum())))
    unnormalized=np.pad(unnormalized,(0,len(undefined)))
    output={'covariance':direct,'svca2':unnormalized}
    output['algebraically_undefined_svca_components']=undefined
    if train_times is not None or test_times is not None:
        tr=np.asarray(train_times);te=np.asarray(test_times)
        need(tr.ndim==te.ndim==1 and tr.dtype.kind in 'iu' and te.dtype.kind in 'iu' and len(tr)and len(te),'complete declared temporal split')
        need(min(tr.min(),te.min())>=0 and max(tr.max(),te.max())<x.shape[1]and not set(tr)&set(te),'disjoint valid train/test times')
        need(len(set(tr))==len(tr)and len(set(te))==len(te),'no repeated train/test observations')
        u,_,vh=np.linalg.svd(x[mask][:,tr]@x[~mask][:,tr].T,full_matrices=False)
        a=u.T@x[mask][:,te];b=vh@x[~mask][:,te]
        output['svca']=(a*b).mean(axis=1)
        output['svca_variance']=(a*a+b*b).mean(axis=1)/2
    return output

def exponent(values,first_rank,last_rank,weight):
    import numpy as np
    a=np.asarray(values,dtype='float64');integer(first_rank,2);integer(last_rank,first_rank)
    need(a.ndim==1 and len(a)>=last_rank and np.isfinite(a).all(),'full fit rank support')
    values=a[first_rank-1:last_rank]
    need(np.all(values!=0),'undefined zero in log-absolute fit')
    r=np.arange(first_rank,last_rank+1,dtype='float64')
    need(weight in ('inverse_rank','inverse_log_rank'),'explicit source/paper fit variant')
    w=1/r if weight=='inverse_rank' else 1/np.log(r)
    design=np.column_stack((-np.log(r),np.ones(len(r))))
    coef=np.linalg.solve(design.T@(w[:,None]*design),design.T@(w*np.log(np.abs(values))))
    prediction=np.exp(-coef[0]*np.log(np.arange(1,len(a)+1))+coef[1])
    need(np.isfinite(coef).all()and np.isfinite(prediction).all(),'finite weighted fit')
    return {'alpha':float(coef[0]),'fit_rank1_scale':float(math.exp(coef[1])),'prediction':prediction,
            'first_rank':first_rank,'last_rank':last_rank,'weight':weight,'absolute_value_fit':True}

def dmd(value,*,lag,ridge,components,block,valid_times=None,normalization):
    """Concrete lag estimator with separately selected source or conventional weights."""
    import numpy as np
    x=matrix(value);n,t=x.shape;integer(lag,1);integer(components,1);integer(block,1);real(ridge,0)
    need(t>lag and components<=n,'complete DMD geometry')
    need(normalization in ('held_source_blocks','conventional_pairs'),'declared ridge normalization')
    if components<n:
        # A source-equivalent PCA subspace in exact arithmetic, not backend-bit parity.
        if n<t:
            cov=x@x.T/t
            _,u=np.linalg.eigh(cov@cov.T);x=u[:,-components:].T@x
        else:
            cov=x.T@x/t;_,u=np.linalg.eigh(cov.T@cov)
            x=np.sqrt(((u.T@x.T)**2).sum(axis=1))[:,None]*u.T
            x=x[-components:]
    valid=None
    if valid_times is not None:
        valid=set(int(k)for k in valid_times)
        need(all(0<=k<t for k in valid),'valid source time indices')
    gxx=np.zeros((x.shape[0],x.shape[0]));gxy=gxx.copy();total=0;pair_count=0
    if normalization=='held_source_blocks':
        chunks=max(1,(t-lag)//block);width=min(block,t-lag)
        for j in range(chunks):
            inds=np.arange(j*width,j*width+width-lag)
            if valid is not None:inds=np.asarray([k for k in inds if k in valid and k+lag in valid],dtype='int64')
            nt0=len(inds)if valid is not None else width
            if nt0>50:
                xx=x[:,inds];yy=x[:,inds+lag];gxx+=xx@xx.T/t*nt0;gxy+=xx@yy.T/t*nt0;total+=nt0;pair_count+=len(inds)
        need(total>0,'no admitted source DMD block pairs');gxx*=t/total;gxy*=t/total
    else:
        inds=np.arange(t-lag)
        if valid is not None:inds=np.asarray([k for k in inds if k in valid and k+lag in valid],dtype='int64')
        need(len(inds)>0,'no complete DMD pairs');pair_count=len(inds)
        xx=x[:,inds];yy=x[:,inds+lag];gxx=xx@xx.T/len(inds);gxy=xx@yy.T/len(inds)
    operator=np.linalg.solve(gxx+ridge*np.eye(x.shape[0]),gxy).T
    eigen=np.linalg.eigvals(operator)
    need(np.isfinite(operator).all()and np.isfinite(eigen).all(),'finite observed DMD')
    return {'operator':operator,'eigenvalues':eigen,'pair_count':pair_count,
            'normalization':normalization,'ridge':ridge,'lag':lag,
            'interpretation':'observed truncated regularized lag predictor; not identified full-state dynamics'}

def pc_crosscorrelation(value,mask,*,blocks,lags,smoothing):
    import numpy as np
    x=matrix(value);integer(blocks,2);integer(lags,1);real(smoothing,0)
    mask=np.asarray(mask);need(mask.shape==(x.shape[0],)and mask.dtype.kind=='b'and mask.any()and(~mask).any(),'aligned nonempty spatial halves')
    width=x.shape[1]//blocks;need(width>=lags,'complete lag/block support')
    effective_blocks=x.shape[1]//width
    data=x[:,:width*effective_blocks].reshape(x.shape[0],effective_blocks,width)
    data=data-data.mean(axis=2,keepdims=True);data/=1e-3+np.sqrt((data**2).mean(axis=2,keepdims=True))
    train=data[:,::2].reshape(x.shape[0],-1)
    covtrain=train
    if smoothing:
        kernel=np.exp(-np.arange(-20,21,dtype='float64')**2/(2*smoothing*smoothing))
        need(train.shape[1]>=len(kernel),'source convolution support')
        covtrain=np.stack([np.convolve(row,kernel,mode='valid')for row in train])
    cov=covtrain[mask]@covtrain[~mask].T/covtrain.shape[1]
    _,u=np.linalg.eigh(cov@cov.T);v=cov.T@u;norm=np.sqrt((v*v).sum(axis=0))
    need(np.all(norm>0),'undefined singular-vector normalization');v/=norm
    if smoothing:
        raw=train[mask]@train[~mask].T/train.shape[1]
        order=np.argsort(((u*(raw@v))**2).sum(axis=0));u=u[:,order];v=v[:,order]
    test=data[:,1::2];a=u[:,-1000:].T@test[mask].reshape(int(mask.sum()),-1)
    b=v[:,-1000:].T@test[~mask].reshape(int((~mask).sum()),-1)
    a=zscore(a,1e-3)/math.sqrt(width);b=zscore(b,1e-3)/math.sqrt(width)
    a=a.reshape(len(a),-1,width);b=b.reshape(len(b),-1,width)
    corr=np.fft.ifft(np.fft.fft(a,axis=-1)*np.conj(np.fft.fft(b,axis=-1)),axis=-1).real.mean(axis=1)
    return corr[::-1,:lags]

def rotation_summary(eigenvalues,*,cutoff,filter_kind,mode):
    import numpy as np
    need(filter_kind in ('modulus','real_part')and mode in ('held_author_source','stable_principal'),'explicit rotation semantics')
    real(cutoff,0)
    z=np.asarray(eigenvalues,dtype='complex128');need(z.ndim==1 and np.isfinite(z).all(),'finite full eigenvalues')
    eligible=(np.abs(z)>cutoff if filter_kind=='modulus'else z.real>cutoff)&(z.imag>=0)
    z=z[eligible];values=[];dispositions=[]
    for item in z:
        radius=abs(item)
        if radius==0 or radius==1:dispositions.append({'value':[float(item.real),float(item.imag)],'reason':'zero_or_unit_modulus'});continue
        if radius>1 and mode=='stable_principal':dispositions.append({'value':[float(item.real),float(item.imag)],'reason':'unstable_no_decay'});continue
        values.append(float(np.angle(item)/(2*np.pi)/-np.log10(radius)))
    need(all(math.isfinite(v)for v in values),'finite rotations')
    return {'values':values,'quantiles':np.quantile(values,[.05,.25,.5,.75,.95]).tolist()if values else None,
            'dispositions':dispositions,'filter_kind':filter_kind,'mode':mode,
            'continuous_frequency_identified':False,'principal_phase_aliasing':True}

