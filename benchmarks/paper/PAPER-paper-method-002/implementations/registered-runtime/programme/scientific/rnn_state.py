"""Actual full-state RNN evolution/JVP/Jacobian/PCA source.

All returned state entries are retained. The old notebook's ambiguous view
indexing, missing constructor alias and NaN-to-zero plotting are not treated as
complete-state proof. The explicit complete-returned-state profile is a source
extension and requires native-coordinate and method qualification.
"""
from copy import deepcopy
from runtime.strict import require,integer

def _codec(ctx,network,expected,params=None,external_inds=None):
    import numpy as np
    import jax
    import jax.numpy as jnp
    from jaxley.integrate import build_init_and_step_fn
    from importlib.metadata import version
    require(expected['solver_api']=='Jaxley_0.8.2_exact_init_step'and version('jaxley')=='0.8.2','explicit prospective solver ABI; not original-environment proof')
    require(not network.externals,'no unaccounted static stimulus/clamp in exact-step state route')
    network.to_jax()
    initialize,native_step=build_init_and_step_fn(network,voltage_solver='jaxley.stone',solver='bwd_euler')
    states,all_params=initialize([]if params is None else params,all_states=None,param_state=None,delta_t=.025)
    indices=network.external_inds.copy()if external_inds is None else external_inds
    all_keys=tuple(states)
    actual=[{'key':k,'shape':list(states[k].shape),'size':int(states[k].size)}for k in all_keys]
    require(actual==expected['state_coordinates'],'all actual returned state coordinates')
    require(all(np.asarray(states[k]).dtype.kind=='f'and np.isfinite(np.asarray(states[k])).all()for k in all_keys),'complete finite initial state; absent/nonfinite channels not silently removed')
    # The released full-state functions explicitly exclude extracellular calcium
    # and its fixed reversal context from dynamic tangent/PCA coordinates. Keep
    # those actual values in the state passed to every solver step and report
    # them separately; including constant directions changes Lyapunov exponents.
    fixed={k:states[k]for k in all_keys if k in('CaCon_e','eCa')}
    keys=tuple(k for k in all_keys if k not in fixed)
    shapes=[tuple(states[k].shape)for k in keys];sizes=[int(states[k].size)for k in keys]
    coordinates={'dynamic_coordinates':[r for r in actual if r['key']in keys],
                 'fixed_context':{k:np.asarray(v).tolist()for k,v in fixed.items()},
                 'complete_returned_state_coordinates':actual}
    def flatten(state):return jnp.concatenate([jnp.reshape(state[k],(-1,))for k in keys])
    def unflatten(vector):
        result=dict(fixed);offset=0
        for key,shape,size in zip(keys,shapes,sizes):result[key]=jnp.reshape(vector[offset:offset+size],shape);offset+=size
        return result
    def step(vector,externals=None):
        out=native_step(unflatten(vector),all_params,{}if externals is None else externals,external_inds=indices,delta_t=.025)
        return flatten(out)
    return flatten(states),jax.jit(step),flatten,unflatten,coordinates

def _allocation(ctx,*extents):
    require(sum(extents)<=ctx.limits['array_memory_bytes'],'complete declared scientific arrays exceed selected capacity')

def _lyapunov(ctx,spec,components):
    import numpy as np
    import jax
    from .rnn import _network,_identity
    require(spec['lyapunov_profile']in('source_two_2s_transients_per_ms','paper_single4s_per_step'),'explicit Lyapunov transient/unit convention')
    require(spec['constructor_alias_amendment']=='available_constructor_not_historical_alias','missing alias not silently equated')
    gains=[i*.00025 for i in range(13)]
    require(spec['gain_values']==gains and spec['gain_seeds']==[0]*13,'complete literal13-point gain sweep')
    expected=ctx.read_json('gain_state_identities');require(len(expected['gains'])==13,'full gain identity roster')
    state_rows=[];voltages=[];norms=[];counts=[];exponents=[]
    for index,gain in enumerate(gains):
        current=deepcopy(spec);current['network']['init_gain']=gain;current['network']['RNN_seed']=0
        network,conn,inp=_network(current,components)
        require(expected['gains'][index]['identity']==_identity(network,current['network']),'gain original graph identity')
        v,step,flatten,unflatten,coordinates=_codec(ctx,network,expected['gains'][index])
        initial=np.asarray(v);nstate=v.size;nv=unflatten(v)['v'].size
        _allocation(ctx,13*240000*nv*8,13*240000*8,13*3*nstate*8,nstate*nstate*8)
        rng=np.random.RandomState(integer(spec['direction_seed'],'Lyapunov direction seed',0)+index)
        q=rng.randn(nstate);qn=np.linalg.norm(q);require(np.isfinite(qn)and qn>0,'original finite direction');q=q/qn
        jvp=jax.jit(lambda x,q:jax.jvp(step,(x,),(q,)))
        if spec['lyapunov_profile']=='source_two_2s_transients_per_ms':
            for t in range(80000):
                if t%256==0:ctx.checkpoint()
                v=step(v)
            for t in range(80000):
                if t%256==0:ctx.checkpoint()
                v,q=jvp(v,q);length=float(np.linalg.norm(np.asarray(q)));require(np.isfinite(length)and length>0,'transient tangent collapse');q=q/length
        else:
            for t in range(160000):
                if t%256==0:ctx.checkpoint()
                v=step(v)
        after_transient=np.asarray(v);traces=np.empty((240000,nv),dtype=np.float64);lengths=np.empty(240000,dtype=np.float64)
        for t in range(240000):
            if t%256==0:ctx.checkpoint()
            v,q=jvp(v,q);length=float(np.linalg.norm(np.asarray(q)))
            require(np.isfinite(length)and length>0,'nonfinite/zero Lyapunov norm unavailable')
            q=q/length;lengths[t]=length;traces[t]=np.asarray(unflatten(v)['v']).reshape(-1)
        require(np.isfinite(traces).all(),'complete voltage trajectory finite')
        denominator=6000. if spec['lyapunov_profile']=='source_two_2s_transients_per_ms'else 240000.
        exponents.append(float(np.log(lengths).sum()/denominator));voltages.append(traces);norms.append(lengths)
        state_rows.append(np.stack([initial,after_transient,np.asarray(v)]))
        counts.append({'gain':gain,'state_coordinates':coordinates,'transient_steps':160000,'accumulation_steps':240000,'renormalization_steps':240000,
                       'tangent_transient_steps':80000 if spec['lyapunov_profile'].startswith('source_')else 0,
                       'units':'per_ms'if denominator==6000 else'per_solver_step','state_boundaries':['initial_native_return','after_full_transient','final']})
    ctx.emit_numeric('full_state',np.stack(state_rows));ctx.emit_numeric('voltage',np.stack(voltages));ctx.emit_numeric('Lyapunov_norms',np.stack(norms));ctx.emit_numeric('maximal_Lyapunov',np.asarray(exponents))
    ctx.emit_json('QR_step_counts',{'profile':spec['lyapunov_profile'],'runs':counts,'full_state_representation':'all variables at three stated boundaries; voltage and norm retain every accumulation step','historical_alias_parity':False})

def _jacobian(ctx,spec,network):
    import numpy as np
    import jax
    require(spec['jacobian_steps']==[1,2,4],'full1/2/4-step family')
    expected=ctx.read_json('state_identity');v,step,flatten,unflatten,coords=_codec(ctx,network,expected)
    _allocation(ctx,6*v.size*v.size*8,v.size*8)
    products=[]
    for n in (1,2,4):
        def advance(x):
            for _ in range(n):x=step(x)
            return x
        ctx.checkpoint();jac=np.asarray(jax.jacfwd(advance)(v));require(np.isfinite(jac).all(),'full finite Jacobian')
        products.append(jac)
    allj=np.stack(products);ctx.emit_numeric('full_Jacobian',allj);ctx.emit_numeric('Jacobian_sign',np.sign(allj))
    ctx.emit_json('all20_unit_state',{'state':np.asarray(v).tolist(),'coordinates':coords,'steps':[1,2,4],
                                    'zero_sign':0,'rendering_nan_replacement':False,'constructor':spec['constructor'],
                                    'historical_missing_alias_equivalence':False})

def _dms_pca(ctx,spec,network,components,identity):
    import numpy as np
    import jax
    import jax.numpy as jnp
    import jaxley as jx
    from scipy import signal,ndimage
    from sklearn.decomposition import PCA
    from .rnn import _unwire_params
    checkpoint=ctx.read_json('dms_checkpoint')['final_checkpoint']
    require(checkpoint['identity']==identity,'actual same DMS checkpoint parent')
    network.delete_trainables()
    network.IonotropicSynapse('all').make_trainable('IonotropicSynapse_gS')
    network.IonotropicSynapse('all').make_trainable('IonotropicSynapse_k_minus')
    params=_unwire_params(checkpoint['parameters']);inp=params[0]['input_weights'];syn=params[1:]
    require(spec['pca_profile']in('source_hann1000_samples','paper_hann40ms'),'explicit25ms-source versus40ms-paper window')
    require(spec['pca_normalization']=='center_per_coordinate_then_pool_std_per_state_key','source normalization choice')
    require(spec['pca_fit_support']=='all_three_complete_trajectories','no selected time/cell subset')
    require(spec['pca_export_profile']=='complete_state_source_pulses_and_all_unforced_segments','explicit nonhistorical complete-state extension')
    require(spec['pca_trajectories']==['A_pulse','B_pulse','unforced'],'original stimulus ordering')
    require(spec['pca_horizon_steps']==[40000,40000,400000],'full1s/1s/10s trajectories; no omitted segments')
    from jaxley.integrate import add_stimuli
    data=None
    for i in range(50):data=network.cell(i).data_stimulate(jnp.zeros(1),data_stimuli=data)
    _,indices=add_stimuli({},network.external_inds.copy(),data)
    expected=ctx.read_json('state_identity');base,step,flatten,unflatten,coords=_codec(ctx,network,expected,params=syn,external_inds=indices)
    nstate=base.size;total_steps=480000
    _allocation(ctx,4*total_steps*nstate*8,3*total_steps*8,nstate*3*8)
    traces=[];segments=[];offset=0
    for name,nsteps,channel in zip(spec['pca_trajectories'],spec['pca_horizon_steps'],(0,1,None)):
        v=base;trace=np.empty((nstate,nsteps),dtype=np.float64)
        for t in range(nsteps):
            if t%256==0:ctx.checkpoint()
            amplitude=inp[:,channel]if channel is not None and 800<=t<2800 else jnp.zeros(50)
            v=step(v,{'i':amplitude});trace[:,t]=np.asarray(v)
        require(np.isfinite(trace).all(),'complete finite state trajectory; no nan_to_num substitution')
        traces.append(trace);segments.append({'name':name,'start':offset,'stop':offset+nsteps,'pulse_ms':[20,70]if channel is not None else None});offset+=nsteps
    raw=np.concatenate(traces,axis=1);length=1000 if spec['pca_profile']=='source_hann1000_samples'else 1600
    window=signal.windows.hann(length)
    # Smooth each independent trajectory before concatenation, so boundaries do
    # not exchange observations across independently initialized runs.
    smoothed=np.concatenate([ndimage.convolve1d(a,window,axis=1)for a in traces],axis=1)
    combined=smoothed.copy();combined-=np.mean(combined,axis=1)[:,None]
    offset=0;normal=np.empty_like(combined);normalization=[]
    for row in coords['dynamic_coordinates']:
        stop=offset+row['size'];block=combined[offset:stop];mean=float(np.mean(block));std=float(np.std(block))
        require(np.isfinite(std)and std>0,'zero-dispersion state key needs explicit scientific selection; not dropped')
        normal[offset:stop]=(block-mean)/std;normalization.append({'key':row['key'],'start':offset,'stop':stop,'mean':mean,'std':std});offset=stop
    pca=PCA(n_components=3);projection=pca.fit_transform(normal.T)
    ctx.emit_numeric('full_ion_gate_state',raw);ctx.emit_numeric('Hann40ms_smoothed',smoothed)
    ctx.emit_numeric('normalized_state',normal);ctx.emit_numeric('PCA_projection',projection)
    ctx.emit_json('PCA_basis',{'components':pca.components_.tolist(),'explained_variance':pca.explained_variance_.tolist(),
                             'mean':pca.mean_.tolist(),'normalization':normalization,'window_samples':length,'window_ms':length*.025,
                             'legacy_product_name':'Hann40ms_smoothed; literal1000-sample profile is25ms and cannot satisfy paper40ms equivalence',
                             'state_coordinates':coords,'segments':segments,'native_parity':False,
                             'solver_api':'Jaxley_0.8.2_exact_init_step',
                             'source_last_repeat_only':'superseded by complete10s trajectory export; PCA support changes explicitly'})

def run_state(ctx,spec,network,conn,inp,components,identity):
    if ctx.group=='J21':return _lyapunov(ctx,spec,components)
    if ctx.group=='J33':return _jacobian(ctx,spec,network)
    if ctx.group=='J25':return _dms_pca(ctx,spec,network,components,identity)
    raise ValueError('No partial or unknown state group')
