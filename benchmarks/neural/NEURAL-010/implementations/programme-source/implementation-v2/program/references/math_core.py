"""Normative binary64 reference mathematics; all observations retained."""
import hashlib
import math
from common import need,finite,canonical,numpy,GRID

def fsum(values):
    result=math.fsum(values);need(math.isfinite(result),'finite normative fsum');return result

def quantile(values,q):
    a=sorted(float(x) for x in values);need(a and all(math.isfinite(x) for x in a) and 0<=q<=1,'finite complete quantile')
    u=(len(a)-1)*q;lo=math.floor(u);hi=math.ceil(u);v=a[lo]+(u-lo)*(a[hi]-a[lo]);need(math.isfinite(v),'finite interpolated quantile');return v

def sigmoid(x):
    need(math.isfinite(x),'finite logit')
    if x>=0:return 1./(1.+math.exp(-x))
    v=math.exp(x);return v/(1.+v)

def softplus(x):
    need(math.isfinite(x),'finite softplus operand');return max(x,0.)+math.log1p(math.exp(-abs(x)))

def split_uniform(support,grid,tree,path,feature):
    material={'task':'NEURAL-010','design':'neural010-full-design-v1','support_sha256':support,'feature_schema':'neural010-feature-v1','grid_index':grid,'tree_index':tree,'node_path':path,'feature_index':feature,'purpose':'split_threshold'}
    q=int.from_bytes(hashlib.sha256(canonical(material)).digest()[:8],'big');k=q//2048
    u=float((k+.5)/(2**53))
    if u==1.:u=math.nextafter(1.,0.)
    need(0<u<1,'exact counter uniform interior');return u

def second_features(x):
    np=numpy();need(x.ndim==2 and x.shape[0]==256 and 0<x.shape[1]<=512 and bool(np.isfinite(x).all()),'complete calibrated second')
    hann=np.asarray([(1.-math.cos(2.*math.pi*n/256))/2. for n in range(256)],dtype=np.float64)
    energy=fsum(float(v)*float(v) for v in hann);per=[]
    for c in range(x.shape[1]):
        a=[float(v) for v in x[:,c]];mean=fsum(a)/256;z=[v-mean for v in a];need(all(math.isfinite(v) for v in z),'finite centered values')
        sd=math.sqrt(fsum(v*v for v in z)/256);rms=math.sqrt(fsum(v*v for v in a)/256)
        features=[math.log1p(fsum(abs(a[n]-a[n-1]) for n in range(1,256))/255),math.log1p(sd),math.log1p(max(a)-min(a)),math.log1p(rms)]
        v=np.asarray([float(hann[n])*z[n] for n in range(256)],dtype=np.float64)
        spectrum=np.fft.rfft(v);need(bool(np.isfinite(spectrum).all()),'finite exact256-point FFT')
        powers=[0.]
        for k in range(1,128):
            re,im=float(spectrum[k].real),float(spectrum[k].imag);pk=2.*(re*re+im*im)/(256.*energy);need(math.isfinite(pk) and pk>=0,'finite one-sided power');powers.append(pk)
        for lo,hi in ((1,4),(4,8),(8,13),(13,30),(30,46)):features.append(math.log1p(fsum(powers[lo:hi])))
        s=fsum(powers[1:46]);entropy=0. if s==0 else -fsum((p/s)*math.log(p/s) for p in powers[1:46] if p>0 and p/s>0)/math.log(45)
        crossings=0
        for n in range(1,256):
            product=z[n]*z[n-1];need(math.isfinite(product),'finite signed zero-crossing product');crossings+=product<0
        features.extend((entropy,crossings/255));need(all(math.isfinite(f) for f in features),'finite all11features');per.append(features)
    result=[]
    for j in range(11):
        v=[row[j] for row in per];result.extend((quantile(v,.5),quantile(v,.9),max(v)))
    return result

def weighted_scaler(matrix,weights,active):
    np=numpy();n,d=matrix.shape;need(len(weights)==n and len(active)==d,'weighted scaler dimensions');sw=fsum(float(w) for w in weights);need(sw>0,'positive weight mass')
    means=[];scales=[];constants=[]
    for j in range(d):
        if not active[j]:means.append(None);scales.append(None);constants.append(True);continue
        mu=fsum(float(weights[i])*float(matrix[i,j]) for i in range(n))/sw
        var=fsum(float(weights[i])*(float(matrix[i,j])-mu)**2 for i in range(n))/sw
        need(math.isfinite(mu) and math.isfinite(var) and var>=0,'finite nonnegative training population variance')
        means.append(mu);scales.append(math.sqrt(var) if var>0 else 0.);constants.append(var==0)
    return {'mean':means,'scale':scales,'constant':constants,'active':list(active),'weight_sum':sw,'reduction':'binary64_math_fsum_canonical_rows_v1'}

def apply_scaler(matrix,scaler):
    np=numpy();out=np.empty_like(matrix,dtype=np.float64)
    for j in range(matrix.shape[1]):
        if not scaler['active'][j] or scaler['constant'][j]:out[:,j]=0.
        else:out[:,j]=(matrix[:,j]-scaler['mean'][j])/scaler['scale'][j]
    need(bool(np.isfinite(out).all()),'finite standardized complete matrix');return out

def logistic_values(u,y,w,theta,lam,hessian=False):
    np=numpy();n,d=u.shape;sw=fsum(float(x) for x in w);need(sw>0 and bool(np.isfinite(theta).all()),'finite objective state')
    logits=[float(theta[0])+fsum(float(u[i,j])*float(theta[j+1]) for j in range(d)) for i in range(n)]
    probabilities=[sigmoid(z) for z in logits]
    loss=fsum(float(w[i])*(softplus(logits[i])-int(y[i])*logits[i]) for i in range(n))/sw + lam/2*fsum(float(v)*float(v) for v in theta[1:])
    need(math.isfinite(loss),'finite exact scaled objective')
    residual=[float(w[i])*(probabilities[i]-int(y[i])) for i in range(n)]
    grad=np.empty(d+1,dtype=np.float64);grad[0]=fsum(residual)/sw
    for j in range(d):grad[j+1]=fsum(residual[i]*float(u[i,j]) for i in range(n))/sw+lam*float(theta[j+1])
    need(bool(np.isfinite(grad).all()),'finite full-support gradient')
    if not hessian:return loss,grad,None
    curv=[float(w[i])*probabilities[i]*(1-probabilities[i]) for i in range(n)];h=np.empty((d+1,d+1),dtype=np.float64)
    for j in range(d+1):
        for k in range(j,d+1):
            v=fsum(curv[i]*(1. if j==0 else float(u[i,j-1]))*(1. if k==0 else float(u[i,k-1])) for i in range(n))/sw
            if j==k and j>0:v+=lam
            h[j,k]=h[k,j]=v
    need(bool(np.isfinite(h).all()),'finite complete Hessian');return loss,grad,h

def backward_error(h,delta,g):
    n=len(g);need(all(finite(float(v)) for row in h for v in row) and all(finite(float(v)) for v in delta) and all(finite(float(v)) for v in g),'finite signed linear system')
    residual=max(abs(fsum(float(h[i][j])*float(delta[j]) for j in range(n))-float(g[i])) for i in range(n))
    hn=max(fsum(abs(float(v)) for v in row) for row in h);dn=max(abs(float(v)) for v in delta);gn=max(abs(float(v)) for v in g)
    product=hn*dn;denominator=product+gn;need(all(finite(v) and v>=0 for v in (residual,hn,dn,gn,product,denominator)),'finite nonnegative backward-error norms')
    need(denominator>0 or residual==0,'zero backward-error denominator with nonzero residual')
    error=residual/denominator if denominator else 0.;need(finite(error) and error<=1e-10,'normwise backward error <=1e-10')
    return error

def logistic_fit(u,y,w,lam):
    np=numpy();theta=np.zeros(u.shape[1]+1,dtype=np.float64);history=[]
    for step in range(201):
        loss,g,_=logistic_values(u,y,w,theta,lam);norm=max(abs(float(v)) for v in g)
        if norm<=1e-7:return {'kind':'logistic','lambda':lam,'theta':theta.tolist(),'steps':step,'objective':loss,'gradient_infinity_norm':norm,'solve_history':history}
        need(step<200,'complete logistic fit failed final200-step gradient convergence')
        loss,g,h=logistic_values(u,y,w,theta,lam,True)
        chol=np.linalg.cholesky(h);need(bool(np.isfinite(chol).all()) and bool((np.diag(chol)>0).all()),'positive finite binary64 Cholesky pivots')
        delta=np.linalg.solve(chol.T,np.linalg.solve(chol,g));err=backward_error(h,delta,g);gd=fsum(float(g[j])*float(delta[j]) for j in range(len(g)));need(gd>0,'strict descent direction')
        chosen=None
        for k in range(60):
            alpha=math.ldexp(1.,-k);candidate=theta-alpha*delta
            if not bool(np.isfinite(candidate).all()):continue
            try:newloss,_,_=logistic_values(u,y,w,candidate,lam)
            except (ValueError,OverflowError):continue
            rhs=loss-1e-4*alpha*gd
            if math.isfinite(rhs) and newloss<=rhs:chosen=(alpha,candidate,newloss);break
        need(chosen is not None,'all60 Armijo steps failed; no fallback')
        alpha,theta,newloss=chosen;history.append({'accepted_step':step+1,'alpha':alpha,'objective':newloss,'backward_error':err})
    raise AssertionError('unreachable')

def tree_node_bound(n,depth,min_leaf):return 256*(2*min(2**depth,max(1,n//min_leaf))-1)

def tree_fit(u,y,w,grid,support,max_nodes,active):
    np=numpy();cfg=GRID[grid];need(cfg['kind']=='trees','tree setting');n,d=u.shape
    need(max_nodes>=tree_node_bound(n,cfg['depth'],cfg['min_leaf']),'full worst-case tree node resource admission')
    ensemble=[];total=0;rounded=0
    def stats(indices):
        mass=fsum(float(w[i]) for i in indices);need(mass>0,'positive node weight');q=fsum(float(w[i])*int(y[i]) for i in indices)/mass;need(0<=q<=1 and finite(q),'finite weighted leaf probability');return mass,q,2*q*(1-q)
    for tree_index in range(256):
        nodes=[]
        def grow(indices,depth,path):
            nonlocal total,rounded
            mass,q,gini=stats(indices);idx=len(nodes);nodes.append({'feature':None,'threshold':None,'left':None,'right':None,'probability':q,'rows':len(indices),'weight':mass});total+=1;need(total<=max_nodes,'complete tree node cap; no truncated forest')
            if depth>=cfg['depth'] or all(int(y[i])==int(y[indices[0]]) for i in indices) or len(indices)<2*cfg['min_leaf']:return idx
            best=None
            for j in range(d):
                if not active[j]:continue
                lo=min(float(u[i,j]) for i in indices);hi=max(float(u[i,j]) for i in indices)
                if lo==hi:continue
                width=hi-lo;need(finite(width),'finite node feature span');tau=lo+split_uniform(support,grid,tree_index,path,j)*width;need(finite(tau),'finite threshold')
                if not lo<tau<hi:rounded+=1;continue
                left=[int(i) for i in indices if float(u[i,j])<=tau];right=[int(i) for i in indices if float(u[i,j])>tau]
                if min(len(left),len(right))<cfg['min_leaf']:continue
                wl,ql,gl=stats(left);wr,qr,gr=stats(right);gain=gini-(wl*gl+wr*gr)/mass;need(finite(gain),'finite weighted Gini gain')
                if gain>0 and (best is None or gain>best[0]):best=(gain,j,tau,left,right)
            if best is None:return idx
            gain,j,tau,left,right=best;li=grow(left,depth+1,path+'L');ri=grow(right,depth+1,path+'R');nodes[idx].update(feature=j,threshold=tau,left=li,right=ri,gain=gain);return idx
        grow(list(range(n)),0,'');ensemble.append(nodes)
    need(len(ensemble)==256,'all256 trees');return {'kind':'trees','grid_index':grid,'configuration':cfg,'trees':ensemble,'node_count':total,'rounded_endpoint_candidates':rounded,'support_sha256':support}

def predict_state(model,u):
    np=numpy();n,d=u.shape;out=np.empty(n,dtype=np.float64)
    if model['kind']=='logistic':
        theta=model['theta'];need(len(theta)==d+1,'full logistic coefficients')
        for i in range(n):out[i]=sigmoid(float(theta[0])+fsum(float(u[i,j])*float(theta[j+1]) for j in range(d)))
    else:
        need(model['kind']=='trees' and len(model['trees'])==256,'full256-tree ensemble')
        for i in range(n):
            predictions=[]
            for nodes in model['trees']:
                idx=0;visited=0
                while nodes[idx]['feature'] is not None:
                    node=nodes[idx];j=node['feature'];need(type(j) is int and 0<=j<d,'tree feature');idx=node['left'] if float(u[i,j])<=node['threshold'] else node['right'];visited+=1;need(type(idx) is int and 0<=idx<len(nodes) and visited<=32,'finite valid tree traversal')
                predictions.append(nodes[idx]['probability'])
            out[i]=fsum(predictions)/256
    need(bool(np.isfinite(out).all()) and bool(((out>=0)&(out<=1)).all()),'all finite probabilities');return out
