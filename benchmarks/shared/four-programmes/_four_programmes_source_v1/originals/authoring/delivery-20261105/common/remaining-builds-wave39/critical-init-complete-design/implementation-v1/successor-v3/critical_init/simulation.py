"""Independent explicit stochastic models. Unknown original grids/seeds stay gated."""
from .custody import need
from .guard import integer,real
from .numerics import matrix,zscore

def connectivity(*,n,distribution,parameters,symmetry,max_real,seed,structure,positions=None):
    import numpy as np
    integer(n,2);integer(seed);real(symmetry,0,1);real(max_real,0,1);need(max_real<1,'stable continuous linear target')
    rng=np.random.Generator(np.random.PCG64(seed))
    if distribution=='uniform':a=rng.uniform(parameters['low'],parameters['high'],(n,n))
    elif distribution=='gaussian':a=rng.normal(parameters['mean'],parameters['sd'],(n,n))
    elif distribution=='bernoulli':a=rng.binomial(1,parameters['probability'],(n,n)).astype('float64')
    elif distribution=='exponential':a=rng.exponential(parameters['scale'],(n,n))
    elif distribution=='truncated_gaussian':
        from scipy.special import ndtr,ndtri
        mu=real(parameters['mean']);sd=real(parameters['sd'],0);need(sd>0,'positive gaussian scale')
        lo=ndtr((parameters['low']-mu)/sd);hi=ndtr((parameters['high']-mu)/sd);need(hi>lo,'nondegenerate truncation')
        a=mu+sd*ndtri(rng.uniform(lo,hi,(n,n)))
    else:raise ValueError('unknown explicitly selected distribution')
    kind=structure['kind']
    if kind!='dense':
        if kind=='sparse':p=np.full((n,n),real(structure['probability'],0,1))
        elif kind=='cluster':
            size=integer(structure['cluster_size'],1);need(n%size==0,'complete equal clusters')
            same=np.arange(n)[:,None]//size==np.arange(n)[None,:]//size
            p=np.where(same,real(structure['within'],0,1),real(structure['floor'],0,1))
        elif kind=='local_torus':
            pos=matrix(positions);need(pos.shape==(n,2),'complete source positions')
            side=real(structure['side'],0);decay=real(structure['decay'],0);need(side>0 and decay>0,'positive torus geometry')
            need((pos>=0).all()and(pos<side).all(),'positions inside declared torus')
            delta=np.abs(pos[:,None,:]-pos[None,:,:]);delta=np.minimum(delta,side-delta)
            d=np.sqrt((delta*delta).sum(axis=-1))
            p=np.maximum(real(structure['peak'],0,1)*np.exp(-d/decay),real(structure['floor'],0,1))
        else:raise ValueError('unknown connectivity structure')
        a=(rng.random((n,n))<p).astype('float64')
    # Explicit independent interpolation; original coupling/symmetrization remains G08.
    if symmetry:a=(1-symmetry)*a+symmetry*(a+a.T)/2
    centering=structure['centering'];need(centering in ('empirical_mean','declared_mean'),'explicit centering order')
    a-=a.mean()if centering=='empirical_mean'else real(structure['declared_mean'])
    np.fill_diagonal(a,0)
    eigen=np.linalg.eigvals(a);edge=float(eigen.real.max());need(edge>0,'positive maximum real eigenvalue')
    a*=max_real/edge
    return {'connectivity':a,'eigenvalues':np.linalg.eigvals(a),'rng':'PCG64','seed':seed,
            'normalization':'largest_real_part','original_native_parity':False}

def ou_theory(connectivity,*,tau,noise_covariance,lag):
    import numpy as np
    from scipy.linalg import solve_continuous_lyapunov,expm
    a=matrix(connectivity);need(a.shape[0]==a.shape[1],'square connectivity')
    q=matrix(noise_covariance);need(q.shape==a.shape and np.allclose(q,q.T),'symmetric noise covariance')
    need(np.linalg.eigvalsh(q).min()>=-1e-12,'positive semidefinite noise covariance')
    real(tau,0);real(lag,0);need(tau>0,'positive integration time')
    m=(a-np.eye(len(a)))/tau;ev=np.linalg.eigvals(m);need(ev.real.max()<0,'strict stationary stability')
    sigma=solve_continuous_lyapunov(m,-q)
    residual=m@sigma+sigma@m.T+q
    propagator=expm(m*lag)
    return {'drift':m,'stationary_covariance':sigma,'covariance_eigenvalues':np.linalg.eigvalsh(sigma)[::-1],
            'lyapunov_relative_residual':float(np.linalg.norm(residual)/max(np.linalg.norm(q),np.finfo(float).tiny)),
            'full_state_propagator':propagator,'full_state_eigenvalues':np.linalg.eigvals(propagator),
            'longest_decay_seconds':float(-1/ev.real.max()),'stable':True}

def observed_predictor(drift,covariance,observation,*,lag,ridge):
    import numpy as np
    from scipy.linalg import expm
    m=matrix(drift);s=matrix(covariance);h=matrix(observation);real(lag,0);real(ridge,0)
    need(m.shape==s.shape and m.shape[0]==m.shape[1]and h.shape[1]==len(m),'complete observation model')
    f=expm(m*lag);g=h@s@h.T;cross=h@f@s@h.T
    b=np.linalg.solve(g+ridge*np.eye(len(h)),cross.T).T
    closure=np.linalg.norm(h@f-b@h)/max(np.linalg.norm(h@f),np.finfo(float).tiny)
    return {'observed_operator':b,'observed_eigenvalues':np.linalg.eigvals(b),'closure_residual':float(closure),
            'full_state_spectrum_identified':bool(h.shape==m.shape and np.linalg.matrix_rank(h)==len(m)and ridge==0),
            'phase_aliasing_remains':True}

def integrate(connectivity,*,dt,tau,steps,discard,bin_steps,traces,noise_amplitude,seed,nonlinearity,initial,drive):
    """Euler-Maruyama with declared Brownian amplitude; drive is time×neuron."""
    import numpy as np
    a=matrix(connectivity);need(a.shape[0]==a.shape[1],'square dynamics')
    real(dt,0);real(tau,0);need(dt>0 and tau>0,'positive dt/tau')
    integer(steps,1);integer(discard,0,steps-1);integer(bin_steps,1);integer(traces,1);integer(seed);real(noise_amplitude,0)
    need(nonlinearity in ('linear','relu'),'declared dynamics')
    x=matrix(initial).copy();need(x.shape==(len(a),traces),'full initial conditions')
    u=matrix(drive);need(u.shape==(steps,len(a)),'complete time-indexed input; no hidden default drive')
    keep=(steps-discard)//bin_steps;need(keep>0,'complete retained bins')
    out=np.empty((traces,len(a),keep));acc=np.zeros_like(x);count=0;dest=0
    rng=np.random.Generator(np.random.PCG64(seed))
    for step in range(steps):
        state=np.maximum(x,0)if nonlinearity=='relu'else x
        x+=dt/tau*(-x+a@state+u[step,:,None])+noise_amplitude*np.sqrt(dt)*rng.normal(size=x.shape)
        need(np.isfinite(x).all(),'nonfinite integration is failure, not dropped trial')
        if step>=discard:
            acc+=x;count+=1
            if count==bin_steps:
                out[:,:,dest]=(acc/bin_steps).T;dest+=1;acc.fill(0);count=0
                if dest==keep:break
    return {'activity':out,'discarded_tail_steps':(steps-discard)%bin_steps,'seed':seed,
            'noise_convention':'noise_amplitude dW; independent PCG64 draws; native coupling unqualified'}

def imaging_noise(activity,*,dt,rate,calcium_tau,amplitude,offset,shot_mean,snr_scale,seed):
    import numpy as np
    x=matrix(activity);real(dt,0);real(rate,0);real(calcium_tau,0);real(amplitude,0);real(shot_mean,0);real(snr_scale,0);integer(seed)
    need(dt>0 and calcium_tau>0,'positive sampling times')
    rng=np.random.Generator(np.random.PCG64(seed));positive=np.maximum(x,0)
    scale=positive.mean(axis=1,keepdims=True);need((scale>0).all(),'nonzero positive input rates')
    spikes=rng.poisson(positive/scale*rate*dt)
    decay=np.exp(-dt/calcium_tau);fluor=np.zeros_like(x);state=np.zeros(len(x))
    for t in range(x.shape[1]):state=decay*state+spikes[:,t];fluor[:,t]=state
    snr=rng.exponential(snr_scale,(len(x),1))+.001
    signal=amplitude*fluor+offset
    need((signal>=0).all(),'nonnegative fluorescence')
    # This declared independent shot-noise model is not asserted to be the missing source model.
    observed=signal+rng.normal(size=x.shape)*np.sqrt(shot_mean*signal)/snr
    return {'spike_counts':spikes,'fluorescence':observed,'ground_truth':x,
            'new_deconvolution_status':'required_unscorable_G06','native_measurement_parity':False}

