"""Concrete whole-family RNN construction/training/evaluation consumers.

Literal released training, explicitly named source extensions, and paper method
alternatives are separate contracts. No unavailable cache or missing constructor
alias becomes a historical observation. Scientific libraries are lazy imports.
"""
from copy import deepcopy
from runtime.strict import require,integer,canonical_bytes,digest

GROUPS=('J20','J21','J22','J23','J24','J25','J33','J34')
ACTIONS={'J20':'rnn_model','J21':'rnn_lyapunov','J22':'evidence_integration_full',
         'J23':'evidence_long','J24':'dms_full','J25':'dms_state_pca',
         'J33':'rnn_full_jacobian','J34':'evidence_full_examples'}

def validate_spec(group,spec):
    require(group in GROUPS and type(spec)is dict,'RNN full group/spec')
    require(spec['schema']=='JAXLEY_RNN_SCIENTIFIC_SPEC_V1','RNN spec schema')
    require(type(spec['selection_id'])is str and spec['selection_id'],'explicit RNN method selection')
    require(spec['constructor']in('released_initialize_RNN','prospective_no_readouts_extension'),'explicit available constructor variant')
    p=spec['network'];require(type(p)is dict,'network profile')
    for k in ('RNN_seed','n_rec','n_inh','n_out'):integer(p[k],k,0)
    require(p['n_out']==(0 if group=='J33'else 2),'complete selected readout count')
    require(spec['constructor']==('prospective_no_readouts_extension'if group=='J33'else'released_initialize_RNN'),'no silent constructor substitution')
    require(0<p['n_inh']<p['n_rec'],'E/I support')
    require(spec['dt']==.025,'literal RNN timestep')
    require(spec['state_export']=='complete_returned_state','explicit complete-state export profile')
    if group in ('J22','J23','J34'):
        require(p['n_rec']==20 and p['n_inh']in(5,10),'complete EI units and explicit source E/I choice')
        require(p['rec_conn_prob']==.2 and p['in_conn_prob']==1 and p['out_conn_prob']==1,'literal EI connectivity')
    if group in ('J24','J25'):
        require(p['n_rec']==50 and p['n_inh']==10 and p['rec_conn_prob']==.05,'complete DMS units/connectivity')
        require(p['in_conn_prob']==.1 and p['out_conn_prob']==1,'literal DMS input/readout support')
    if group=='J21':require(p['n_rec']==50 and p['n_inh']==10 and p['rec_conn_prob']==.2,'full untrained gain family')
    if group=='J33':
        # The source Jacobian notebook uses a different missing constructor and
        # n_out=0. Calling the available two-readout constructor is not parity.
        require(spec['constructor_alias_amendment']=='explicit_no_readout_normalization_extension',
                'J33 missing initialise_DMS_RNN requires an explicit nonhistorical constructor selection')
        require(p['n_rec']==20 and p['n_inh']==5,'all20 Jacobian recurrent units')
    return spec

def _libraries():
    import numpy as np
    import jax
    import jax.numpy as jnp
    import jaxley as jx
    from .rnn_components import components
    require(jax.config.read('jax_enable_x64'),'RNN original x64 installation')
    return np,jax,jnp,jx,components()

def _record_voltage(network,p):
    network.delete_recordings()
    for i in range(p['n_rec']):network.cell(i).branch(1).comp(0).record(verbose=False)
    for i in range(p['n_out']):network.cell(p['n_rec']+i).branch(0).comp(0).record(verbose=False)

def _network(spec,components):
    p=deepcopy(spec['network'])
    network,connectivity,inputs=components['initialize_RNN'](p)
    _record_voltage(network,p)
    return network,connectivity,inputs

def _wire_params(params):
    import numpy as np
    return [{k:np.asarray(v).tolist()for k,v in p.items()}for p in params]

def _unwire_params(wire):
    import jax.numpy as jnp
    require(type(wire)is list and wire,'complete parameter state')
    require(all(type(p)is dict and len(p)==1 for p in wire),'parameter key roster')
    return [{k:jnp.asarray(v,dtype=jnp.float64)for k,v in p.items()}for p in wire]

def _identity(network,p):
    return {'network':p,'edges':[{'pre':int(r['pre_cell_index']),'post':int(r['post_cell_index']),
                                'type':str(r['type'])}for _,r in network.edges.iterrows()],
            'compartments':len(network.nodes),'synapses':len(network.edges)}

def _require_identity(ctx,network,spec):
    expected=ctx.read_json('rnn_identity')
    actual=_identity(network,spec['network'])
    require(actual==expected['identity'],'actual full network graph differs from selected original coordinate identity')
    return actual

def _ei_simulator(network,p,task,levels):
    import numpy as np
    import jax
    import jax.numpy as jnp
    import jaxley as jx
    def simulate(physical,stim):
        inp=physical[0]['input_weights'];syn=physical[1:];data=None
        for i,w in zip(range(p['n_rec']),inp):
            data=network.cell(i).branch(2).comp(0).data_stimulate(stim*w/(task['dt']*10),data_stimuli=data)
        checkpoints=[int(np.ceil(stim.shape[0]**(1/levels)))for _ in range(levels)]
        return jx.integrate(network,delta_t=task['dt'],params=syn,data_stimuli=data,solver='bwd_euler',checkpoint_lengths=checkpoints)
    return jax.jit(simulate)

def _ei_train(ctx,spec,network,conn,inp,components):
    import numpy as np
    import jax
    import jax.numpy as jnp
    import optax
    from jaxley.optimize.transforms import ParamTransform
    from jaxley.optimize.utils import l2_norm
    p=spec['network'];task=spec['task'];train=spec['training']
    require(task=={'dt':.025,'loss':'CE','response_length':20,'response_time':500,'total_time':520,
                   'stim_freq_max':2500,'stim_mean':[-.005,.005],'stim_mean_std':.0002,'stim_std':.05,'target_pol':0},'literal EI stimulus contract')
    require(train['batch_size']==4 and train['epochs']==2000 and train['lr']==.01 and train['checkpoint_levels']==3,'full EI training')
    require(train['profile']in('literal_2001_updates','paper_2000_updates_source_filter'),'explicit source/paper update variant')
    integer(train['train_seed'],'training seed',0)
    network.delete_trainables();network.IonotropicSynapse('all').make_trainable('IonotropicSynapse_gS')
    initial=inp+network.get_parameters()
    require(sum(v.size for x in initial for v in x.values())==109,'original109 parameter support unresolved')
    transform=ParamTransform({'input_weights':-.2,'IonotropicSynapse_gS':1e-10},
                             {'input_weights':.2,'IonotropicSynapse_gS':float(np.max(abs(conn))*3)})
    z=transform.inverse(initial);simulate=_ei_simulator(network,p,task,3)
    def loss_one(z,stim,label,mask):
        voltage=simulate(transform.forward(z),stim)[-2:,1:]
        response=jnp.mean(mask*voltage,axis=1)
        exp=jnp.exp(response-jnp.max(response));probs=exp/jnp.sum(exp)
        return -jnp.sum(label*jnp.log(probs))
    batched=jax.vmap(loss_one,in_axes=(None,0,0,0))
    gradient=jax.jit(jax.value_and_grad(lambda z,s,y,m:jnp.mean(batched(z,s,y,m))))
    optimizer=optax.adam(.01);state=optimizer.init(z)
    first=components['gen_stim_batch'](task,4);value,g=gradient(z,*first)
    desired=l2_norm(g)*.01
    require(np.isfinite(float(value))and 0<float(desired),'finite nonzero original normalization')
    history=[{'kind':'initial_norm_evaluation','loss':float(value),'gradient_norm':float(desired/.01)}]
    np.random.seed(train['train_seed'])
    for epoch in range(2000):
        for kind in (('timing_update','regular_update')if epoch==0 and train['profile']=='literal_2001_updates'else('regular_update',)):
            ctx.checkpoint();stim,label,mask=components['gen_stim_batch'](task,4)
            value,g=gradient(z,stim,label,mask);norm=l2_norm(g)
            require(np.isfinite(float(value))and np.isfinite(float(norm))and float(norm)>0,'EI gradient/zero policy')
            g=jax.tree_util.tree_map(lambda x:x/norm**.8*desired,g)
            update,state=optimizer.update(g,state);z=optax.apply_updates(z,update)
            history.append({'epoch':epoch,'kind':kind,'loss':float(value),'gradient_norm':float(norm),
                            'stimulus_sha256':digest(np.asarray(stim,dtype='<f8').tobytes()),'labels':np.asarray(label).tolist()})
    return transform.forward(z),simulate,{'initial':_wire_params(initial),'final':_wire_params(transform.forward(z)),
                                         'history':history,'updates':len(history)-1,'scientific_profile':train['profile'],
                                         'filter':'source Butterworth order6 cutoff5 fs2500; not literal2500Hz paper cutoff',
                                         'logit_reduction':'mean(mask*readout) over fulltrial, no masked-duration renormalization'}

def _ei_parameters(ctx,spec,network,inp):
    import numpy as np
    wire=ctx.read_json('trained_rnn_parameters')['checkpoint']
    require(wire['identity']==_identity(network,spec['network']),'same original trained-network parent')
    network.delete_trainables();network.IonotropicSynapse('all').make_trainable('IonotropicSynapse_gS')
    params=_unwire_params(wire['parameters'])
    require(list(params[0])==['input_weights']and params[0]['input_weights'].shape==(20,),'all20 inputs')
    require(list(params[1])==['IonotropicSynapse_gS']and params[1]['IonotropicSynapse_gS'].size==len(network.edges),'alloriginal synapses')
    require(all(np.isfinite(np.asarray(v)).all()for p in params for v in p.values()),'finite complete learned state')
    return params

def _ei_full(ctx,spec,network,conn,inp,components,identity):
    import numpy as np
    p=spec['network'];params,simulate,history=_ei_train(ctx,spec,network,conn,inp,components)
    integer(spec['trial_seed'],'test seed',0);np.random.seed(spec['trial_seed'])
    voltages=[];logits=[];labels=[];trials=[]
    for trial in range(1000):
        ctx.checkpoint();stim,label,mask=components['gen_stim'](spec['task'])
        v=np.asarray(simulate(params,stim));response=np.mean(mask*v[-2:,1:],axis=1)
        require(v.shape==(22,20801)and np.isfinite(v).all(),'complete1000-trial voltage support')
        voltages.append(v);logits.append(response);labels.append(label)
        trials.append({'trial':trial,'stimulus_sha256':digest(np.asarray(stim,dtype='<f8').tobytes()),
                       'prediction':int(np.argmax(response)),'target':int(np.argmax(label))})
    # The released psychometric generation is commented source, with a cache
    # subsequently read. This is an explicit executable source reconstruction.
    psych=[]
    for mean in np.arange(-.005,.005,.0005):
        task={**spec['task'],'stim_mean':[float(mean),float(mean)]};choices=[]
        for trial in range(100):
            ctx.checkpoint();stim,label,mask=components['gen_stim'](task);v=np.asarray(simulate(params,stim))
            response=v[-2:,int(task['response_time']/.025):int((task['response_time']+20)/.025)]
            choices.append(int(np.argmax(np.mean(response,axis=1))==0))
        fraction=float(np.mean(choices));psych.append({'mean':float(mean),'choices':choices,'fraction':fraction,'descriptive_binomial_SE':float(np.sqrt(fraction*(1-fraction)/100))})
    full=np.zeros((22,22));gs=np.asarray(params[1]['IonotropicSynapse_gS'])
    for index,(_,row)in enumerate(network.edges.iterrows()):
        pre=int(row['pre_cell_index']);post=int(row['post_cell_index']);full[pre,post]=gs[index]*(-1 if pre<p['n_inh']else 1)
    ctx.emit_numeric('test_logits',np.asarray(logits));ctx.emit_numeric('trial_labels',np.asarray(labels));ctx.emit_numeric('voltage_readout',np.stack(voltages))
    ctx.emit_numeric('input_weights',np.asarray(params[0]['input_weights']));ctx.emit_numeric('recurrent_weights',full[:20,:20]);ctx.emit_numeric('output_weights',full[:20,20:])
    ctx.emit_json('psychometric_responses',{'trials':trials,'psychometric':psych,'training':history,
                                          'checkpoint':{'identity':identity,'parameters':_wire_params(params)},
                                          'cache_equivalence':False,'test_vs_training_independence':'separate explicit RNG seed; source historical seed unrecovered'})

def _ei_examples(ctx,spec,network,inp,components):
    import numpy as np
    params=_ei_parameters(ctx,spec,network,inp);task={**spec['task'],'total_time':3020,'response_time':3000}
    simulate=_ei_simulator(network,spec['network'],task,3)
    np.random.seed(integer(spec['trial_seed'],'example seed',0));voltage=[];inputs=[]
    for sign in (1,-1):
        ctx.checkpoint();stim,label,mask=components['gen_stim']({**task,'stim_mean':[sign*.002,sign*.002]})
        inputs.append(np.asarray(stim));voltage.append(np.asarray(simulate(params,stim)))
    if ctx.group=='J23':
        ctx.emit_numeric('positive_trial_readout',voltage[0][-2:]);ctx.emit_numeric('negative_trial_readout',voltage[1][-2:])
        ctx.emit_json('three_second_timecourses',{'clock_ms':(np.arange(voltage[0].shape[1])*.025).tolist(),
                                                'input':np.stack(inputs).tolist(),'full_voltage':np.stack(voltage).tolist(),
                                                'source_plot_timecuts':'not applied to full output;20ms ramp retained'})
    else:
        require(spec['raster_profile']=='released_occupancy_minus50_all_units','explicit source occupancy raster; no display sorting/cropping')
        v=np.stack(voltage);raster=(v[:,:20]>-50.).astype('uint8')
        ctx.emit_numeric('input',np.stack(inputs));ctx.emit_numeric('readout',v[:,-2:]);ctx.emit_numeric('raster',raster);ctx.emit_numeric('full_voltage_both_classes',v)

def _dms(ctx,spec,network,conn,inp,components,identity):
    import numpy as np
    import jax
    import jax.numpy as jnp
    import jaxley as jx
    import optax
    from jaxley.optimize.utils import l2_norm
    p=spec['network'];t=deepcopy(spec['task']);tr=spec['training']
    require(tr['profile']=='literal_source_1250_sd001','DMS paper noise/epochs alternative not silently selected')
    require(t=={'stim_onset':[800],'stim_len':2000,'delay':[2000,6000],'response_onset':0,'response':2000,'stim_amp':1,'stim_noise_sd':.01,'batch_size':64},'literal complete DMS task')
    require(tr['epochs']==1250 and tr['lr']==.001 and tr['lr_end']==.0001 and tr['delay_step']==4000 and tr['checkpoint_levels']==2,'literal DMS optimizer/curriculum')
    require(tr['gradient_clipping']is False and tr['reinitialize_optimizer']is False,'literal DMS optimization choices')
    network.delete_trainables();network.IonotropicSynapse('all').make_trainable('IonotropicSynapse_gS');network.IonotropicSynapse('all').make_trainable('IonotropicSynapse_k_minus')
    initial=inp+network.get_parameters();nonzero=np.abs(conn.ravel()[np.nonzero(conn.ravel())]);require(len(nonzero)>0,'original connected graph')
    transform=components['ParamTransform']({'input_weights':0,'IonotropicSynapse_gS':0,'IonotropicSynapse_k_minus':.05,'v':-120},
                                          {'input_weights':4,'IonotropicSynapse_gS':None,'IonotropicSynapse_k_minus':2.,'v':0},
                                          {'IonotropicSynapse_gS':1/float(np.mean(nonzero))})
    z=transform.inverse(initial);task=components['DMS'](t)
    def simulate(z,stim):
        phys=transform.forward(z);data=None
        for i,w in zip(range(50),phys[0]['input_weights']):data=network.cell(i).data_stimulate(jnp.inner(stim,w),data_stimuli=data)
        cp=[int(np.ceil(stim.shape[0]**.5))]*2
        return jx.integrate(network,delta_t=.025,params=phys[1:],data_stimuli=data,solver='bwd_euler',checkpoint_lengths=cp)
    def one(z,stim,label,mask):
        pred=simulate(z,stim)[-2:].T;exp=jnp.exp(pred-jnp.max(pred));prob=exp/exp.sum(axis=1)[:,None];prob=jnp.clip(prob,1e-8,1-1e-8)
        ce=-jnp.sum(mask*(label*jnp.log(prob)+(1-label)*jnp.log(1-prob)))/mask.sum()
        d1=jnp.sum(mask[:,0]*(pred[:,1]>pred[:,0]));d0=jnp.sum(mask[:,0]*(pred[:,1]<pred[:,0]))
        acc=((d1>d0)==jnp.argmax(jnp.mean(label,axis=0))).astype(int)
        return ce,acc
    batch=jax.vmap(one,in_axes=(None,0,0,0))
    def loss(z,s,y,m):
        value,acc=batch(z,s,y,m);return jnp.mean(value),jnp.mean(acc)
    grad=jax.jit(jax.value_and_grad(loss,has_aux=True))
    schedule=optax.exponential_decay(init_value=.001,transition_steps=1,decay_rate=.995,end_value=.0001)
    opt=optax.chain(optax.scale_by_adam(),optax.scale_by_schedule(schedule),optax.scale(-1.));state=opt.init(z)
    history=[];selected=[];lowest=10.;highest=0.
    for epoch in range(1250):
        ctx.checkpoint();stim,label,mask=task.gen_batch();(value,acc),g=grad(z,stim[:,1:],label,mask)
        require(np.isfinite(float(value))and np.isfinite(float(acc)),'DMS nonfinite failure is unavailable, not shortened success')
        row={'epoch':epoch,'loss':float(value),'accuracy':float(acc),'delay':list(task.params['delay']),
             'stimulus_sha256':digest(np.asarray(stim,dtype='<f8').tobytes())}
        if value<.65 and acc>.95 and task.params['delay'][1]<19000:
            selected.append({'epoch':epoch,'delay':list(task.params['delay']),'parameters':_wire_params(transform.forward(z))})
            task.params['delay'][0]+=4000;task.params['delay'][1]+=4000;row['update_applied']=False
        else:
            if task.params['delay'][1]>19000 and value<.65 and acc>.95 and value<=lowest and acc>=highest:
                selected.append({'epoch':epoch,'delay':list(task.params['delay']),'parameters':_wire_params(transform.forward(z))});lowest=float(value);highest=float(acc)
            updates,state=opt.update(g,state);z=optax.apply_updates(z,updates);row['update_applied']=True
        history.append(row)
    require(task.params['delay']==[18000,22000],'complete450-550ms curriculum not reached; whole DMS unavailable')
    params=transform.forward(z);stim,label,mask=task.gen();v=np.stack([np.asarray(simulate(z,s[1:]))for s in stim])
    require(v.shape[0:2]==(4,52)and np.isfinite(v).all(),'allfour DMS patterns and50cells2readouts')
    require(spec['raster_profile']=='released_occupancy_minus50_all_units','explicit source occupancy raster; repeated readout-row removal is not preserved')
    raster=(v[:,:50]>-50.).astype('uint8');pred=v[:,-2:]
    logits=np.stack([np.mean(mask[i,:,0]*pred[i],axis=1)for i in range(4)])
    ctx.emit_numeric('pattern_delay_logits',logits);ctx.emit_numeric('trial_labels',label);ctx.emit_numeric('complete_voltage',v);ctx.emit_numeric('raster',raster);ctx.emit_numeric('readout',pred)
    ctx.emit_json('curriculum_loss',{'history':history,'all_selected_checkpoints':selected,'initial':_wire_params(initial),
                                    'final_checkpoint':{'identity':identity,'parameters':_wire_params(params),'task':task.params},
                                    'trial_order':['AA','AB','BA','BB'],'stimulus':stim.tolist(),'mask':mask.tolist(),
                                    'paper_459_or542_parameter_equivalence':False})

def _all_models(ctx,document):
    require(document['schema']=='JAXLEY_RNN_THREE_PROFILES_V1','all three distinct architecture profiles')
    rows=document['profiles'];names=['untrained','EI','DMS']
    require([r['name']for r in rows]==names,'J20 cannot collapse distinct original network profiles')
    expected=ctx.read_json('rnn_identity')
    require([r['name']for r in expected['profiles']]==names,'three original coordinate identities')
    np,jax,jnp,jx,components=_libraries()
    from jaxley.integrate import build_init_and_step_fn
    from importlib.metadata import version
    require(document['solver_api']=='Jaxley_0.8.2_exact_init_step'and version('jaxley')=='0.8.2','explicit prospective initialization API')
    maps=[];states=[];connections=[];parameters=[]
    for row,reference,group in zip(rows,expected['profiles'],('J21','J22','J24')):
        spec=validate_spec(group,row['spec']);ctx.checkpoint()
        network,conn,inp=_network(spec,components);identity=_identity(network,spec['network'])
        require(identity==reference['identity'],'original complete profile graph identity')
        network.to_jax();initialize,_=build_init_and_step_fn(network,voltage_solver='jaxley.stone',solver='bwd_euler')
        initial,_=initialize(network.get_parameters(),all_states=None,param_state=None,delta_t=.025)
        maps.append({'name':row['name'],'identity':identity,'channels':list(network.channel_names),'constructor':spec['constructor']})
        states.append({'name':row['name'],'states':{k:np.asarray(v).tolist()for k,v in initial.items()}})
        connections.append({'name':row['name'],'shape':list(conn.shape),'values':np.asarray(conn).tolist()})
        parameters.append({'name':row['name'],'input':_wire_params(inp),'network_node_columns':list(network.nodes.columns),'network_edge_columns':list(network.edges.columns)})
    ctx.emit_json('network_mechanism_map',{'profiles':maps,'API_profile':'prospective_Jaxley_0.8.2_exact_initial_state'})
    ctx.emit_json('initial_state',{'profiles':states});ctx.emit_json('connectivity',{'profiles':connections})
    ctx.emit_json('parameter_map',{'profiles':parameters})

def run(ctx):
    require(ctx.group in GROUPS and ctx.action==ACTIONS[ctx.group],'RNN closed action')
    document=ctx.read_json('rnn_spec')
    if ctx.group=='J20':return _all_models(ctx,document)
    spec=validate_spec(ctx.group,document)
    np,jax,jnp,jx,components=_libraries();network,conn,inp=_network(spec,components);identity=_require_identity(ctx,network,spec)
    if ctx.group=='J22':_ei_full(ctx,spec,network,conn,inp,components,identity)
    elif ctx.group in('J23','J34'):_ei_examples(ctx,spec,network,inp,components)
    elif ctx.group=='J24':_dms(ctx,spec,network,conn,inp,components,identity)
    else:
        from .rnn_state import run_state
        run_state(ctx,spec,network,conn,inp,components,identity)
