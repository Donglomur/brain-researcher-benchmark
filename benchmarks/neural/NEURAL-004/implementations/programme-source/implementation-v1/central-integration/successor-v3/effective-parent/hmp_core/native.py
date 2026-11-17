"""Actual fixed-source PCA, HMP and same-group evaluation. Imports are deferred."""
import warnings
from .binding import mass_function, traced_em
from .schedule import need


def row_key(person, epoch):
    if hasattr(epoch, 'item'): epoch = epoch.item()
    need(type(epoch) in (int, str), 'ordinary private source epoch identity')
    return [str(person), epoch]


def trial_rows(trials, admission, people):
    import numpy as np
    actual = [row_key(p, e) for p,e in zip(trials.xrdurations.participant.values, trials.xrdurations.epoch.values)]
    expected = [[p,r['epoch']] for p in people for r in admission['rows'][p]]
    need(actual == expected and len(actual) == int(trials.n_trials), 'complete unchanged private trial support/order')
    sizes = [r['sample_count'] for p in people for r in admission['rows'][p]]
    need(np.array_equal(trials.durations, np.asarray(sizes)), 'exact retained native sample support')
    return actual


def normalization(epoch_data, weights, session):
    """Retain the source per-trial centers and per-person/component normalization.

    This is additional extraction work, not an extra PCA fit. Arrays are never
    silently used as alternative preprocessing for the actual source call.
    """
    import numpy as np
    data = epoch_data.data.transpose('participant', 'epoch', 'channel', 'sample')
    session.live(int(data.values.nbytes) * 3, 'normalization extraction arrays')
    session.tick(); centers = np.nanmean(data.values, axis=-1)
    centered = data.copy(deep=True); centered.values = data.values - centers[..., None]
    projected = (centered @ weights).transpose('participant', 'epoch', 'sample', 'component')
    result = []
    for i,person in enumerate(data.participant.values):
        component = []
        for c in range(projected.sizes['component']):
            values = projected.values[i,:,:,c]; valid = values[~np.isnan(values)]
            need(len(valid) > 0 and bool(np.isfinite(valid).all()), 'finite complete component support')
            mean = float(valid.mean()); sd = float(valid.std())
            need(np.isfinite(mean) and np.isfinite(sd) and sd > 0, 'positive source component scale; no variance floor')
            component.append({'mean':mean, 'sd':sd, 'count':int(len(valid))})
        for j,epoch in enumerate(data.epoch.values):
            if bool(np.isnan(data.values[i,j]).all()): continue
            need(bool(np.isfinite(centers[i,j]).all()), 'complete finite source channel centers')
            result.append({'person':str(person), 'epoch':row_key(person,epoch)[1],
                           'centering':centers[i,j].tolist(), 'components':component})
    session.tick(); return result


def preprocess(epoch_data, held, admission, hmp, recipe, store, session):
    import numpy as np
    training_people = [p for p in admission['people'] if p != held]
    training = epoch_data.sel(participant=training_people)
    query = epoch_data.sel(participant=[held])
    session.charge('pca_fits',1,'pca/'+held); session.tick()
    train_pre = hmp.preprocessing.Standard(training,n_comp=15,apply_zscore='participant',copy=True)
    session.tick()
    query_pre = recipe.project_held(query,train_pre.weights,hmp.preprocessing.Standard)
    session.tick()
    pattern = hmp.patterns.HalfSine.create_expected(sfreq=512,width=25)
    train = hmp.trialdata.TrialData.from_preprocessed(preprocessed=train_pre,pattern=pattern.template)
    test = hmp.trialdata.TrialData.from_preprocessed(preprocessed=query_pre,pattern=pattern.template)
    train_rows = trial_rows(train,admission,training_people); held_rows = trial_rows(test,admission,[held])
    model = train_pre.preprocessing_model
    pca = {'weights':store.array('pca-'+held+'-weights.bin',train_pre.weights.values,('channel','component'),'linear spatial coefficient'),
           'state':{},'training_people':training_people,'channel_order':list(admission['channel_order']),
           'components':15,'source_recipe':'Standard(n_comp=15,apply_zscore=participant,copy=True)'}
    for name in ('components_','mean_','explained_variance_','explained_variance_ratio_','singular_values_'):
        arr=np.asarray(getattr(model,name));pca['state'][name]=store.array('pca-'+held+'-'+name+'.bin',arr,tuple('axis'+str(i)for i in range(arr.ndim)),'source PCA state')
    norms={'train':normalization(training,train_pre.weights,session),'held':normalization(query,train_pre.weights,session)}
    need([[x['person'],x['epoch']]for x in norms['train']]==train_rows and [[x['person'],x['epoch']]for x in norms['held']]==held_rows,'normalization joins all admitted trial rows')
    pca['normalization']=store.json('pca-'+held+'-normalization.json',norms)
    pca['pattern']=store.array('pca-'+held+'-template.bin',np.asarray(pattern.template),('sample',),'source half-sine template')
    pca['status']='complete';pca['fit_count']=1
    return train,test,pattern,pca,store.json('pca-'+held+'.json',pca)


def fit_model(train, pattern, held, k, pca_descriptor, admission, bodies, hmp, np, store, session):
    source=bodies['hmp/models/event.py'];em=traced_em(source,np,warnings.warn)
    class RetainedEvent(hmp.models.EventModel):
        EM=em
        def _retain_em(self,iteration,likelihood,channel,time):
            session.tick()
            count=int(likelihood.nbytes+channel.nbytes+time.nbytes)
            session.live(self._retained_bytes+count*2,'all retained EM copies plus next update')
            self._retained.append({'iteration':int(iteration),'likelihood':likelihood.copy(),
                                   'channel':channel.copy(),'time':time.copy()})
            self._retained_bytes+=count
            session.tick()
    model=RetainedEvent(pattern,n_events=k,tolerance=1e-4,max_iteration=1000,min_iteration=1,starting_points=1)
    model._retained=[];model._retained_bytes=0;failure=None
    session.charge('hmp_fits',1,f'fit/{held}/{k}')
    try:
        session.tick();model.fit(train,verbose=False,cpus=1);session.tick()
    except BaseException as exc:
        failure=exc
    prefix=f'fit-{held}-{k}'
    history=[]
    for row in model._retained:
        i=row['iteration'];entry={'iteration':i}
        for name,axes in [('likelihood',('group',)),('channel',('group','event','component')),('time',('group','stage','parameter'))]:
            entry[name]=store.array(f'{prefix}-em-{i}-{name}.bin',np.asarray(row[name]),axes,'source EM state',True)
        history.append(entry)
    state={'schema':'neural004_hmp_state_v1','held':held,'events':k,'pca':pca_descriptor,
           'training_people':[p for p in map(str,range(26))if p!=held],'history':history,'status':'failed'if failure else'complete',
           'failure':None if failure is None else type(failure).__name__,'fit_recipe':{'tolerance':1e-4,'max_iteration':1000,'min_iteration':1,'starting_points':1,'cpus':1,'location':True},
           'stop':None,'arrays':{},'grouping':{},'source_version':'1.0.0b2',
           'dataset_pin':admission['dataset_pin'],'source_binding':admission['source_binding'],
           'fit_support':trial_rows(train,admission,[p for p in admission['people']if p!=held])}
    if failure is None:
        arrays={'channel_pars':(model.channel_pars,('group','event','component')),'time_pars':(model.time_pars,('group','stage','parameter')),
                'traces':(model.traces,('initial_and_update','group')),'time_pars_dev':(model.time_pars_dev,('initial_and_update','group','stage','parameter')),
                'channel_map':(model.channel_map,('group','event')),'time_map':(model.time_map,('group','stage')),
                'group':(model.group,('training_trial',)),'likelihoods':(model.lkhs,('group',))}
        for name,(arr,axes)in arrays.items():state['arrays'][name]=store.array(prefix+'-'+name+'.bin',np.asarray(arr),axes,'source fitted state',True)
        n=len(model.traces);updates=n-1
        reason='iteration_cap'if updates>=1000 else'nonfinite'if not np.isfinite(model.traces).all()else'signed_relative_change_below_tolerance'
        relative=None if n<2 or float(np.asarray(model.traces[-2]).sum())==0 else float((np.asarray(model.traces[-1]).sum()-np.asarray(model.traces[-2]).sum())/abs(np.asarray(model.traces[-2]).sum()))
        state['stop']={'updates':updates,'trace_rows':n,'reason':reason,'convergence_proven':False,
                       'last_relative_change':relative if relative is not None and np.isfinite(relative)else None}
        state['grouping']={'dictionary':model.grouping_dict,'location_samples':int(model.location)}
        if n>1000 or not all(np.isfinite(x).all()for x in(model.traces,model.channel_pars,model.time_pars)):
            state.update(status='failed',failure='source_finite_stop_refused')
    descriptor=store.json(prefix+'.json',state)
    if failure is not None:session.context.fail(f'fit/{held}/{k}',type(failure).__name__)
    return model if state['status']=='complete'else None,state,descriptor


def evaluate(model, trials, held, k, support, gain, state_descriptor, admission, bodies, hmp, np, store, session):
    import xarray as xr
    from pandas import MultiIndex
    prefix=f'eval-{held}-{k}-{support}-{gain}';people=[held]if support=='held'else[p for p in admission['people']if p!=held]
    roster=trial_rows(trials,admission,people)
    _,groups,_=model.group_constructor(trials,model.grouping_dict)
    source_mass=mass_function(bodies['hmp/models/event.py'],np)
    old_channel=model.channel_pars.copy();old_time=model.time_pars.copy()
    result={'schema':'neural004_hmp_evaluation_v1','held':held,'events':k,'support':support,'gain':gain,
            'state':state_descriptor,'source_version':'1.0.0b2','rows':roster,'groups':[],'status':'complete','failure':None,
            'offset':float(trials.offset),'sfreq':float(trials.sfreq),'location':False}
    joined=[];session.charge('hmp_evaluations',1,prefix)
    for group in np.unique(groups):
        mask=groups==group;indices=np.flatnonzero(mask);M=int(np.max(trials.durations[mask]));g=int(group)
        channels=model.channel_pars[g,model.channel_map[g,:]>=0,:]
        if gain=='zero':channels=np.zeros_like(channels)
        params=model.time_pars[g,model.time_map[g,:]>=0,:]
        # This conservative explicit-array lower bound is not complete RSS.
        session.live(8*(5*M*len(indices)*k+int(trials.n_samples)*k+M*(k+1)),'full group forward/backward and output arrays')
        session.charge('mass_extraction_calls',1,prefix+'/group/'+str(g));session.tick()
        likelihood,probs,masses,normalizers=source_mass(model,trials,channels,params,False,mask)
        session.tick();logs=np.log(masses)
        positive=bool(np.isfinite(masses).all()and(masses>0).all()and np.isfinite(normalizers).all()and(normalizers>0).all())
        finite=bool(np.isfinite(probs).all()and np.isfinite(logs).all()and np.isfinite(likelihood))
        raw_norm=np.asarray([model.distribution.pdf(np.arange(M),a,scale=b).sum()for a,b in params])
        status='complete'if positive and finite and bool(np.isfinite(raw_norm).all()and(raw_norm>0).all())else'failed'
        row={'id':g,'M':M,'location':False,'members':[roster[int(i)]for i in indices],'scalar_total':float(likelihood)if np.isfinite(likelihood)else None,
             'positive_finite_normalizers':positive,'status':status,'arrays':{}}
        for name,arr,axes,unit in [('marginals',probs,('trial','sample','event'),'probability'),('masses',masses,('trial',),'unnormalized path mass'),
             ('log_masses',logs,('trial',),'natural log mass'),('event_normalizers',normalizers,('trial','event'),'unnormalized event mass'),
             ('pmf_normalizers',raw_norm,('stage',),'sampled source density sum')]:
            row['arrays'][name]=store.array(prefix+'-g'+str(g)+'-'+name+'.bin',np.asarray(arr),axes,unit,True)
        result['groups'].append(row)
        if status!='complete':result.update(status='failed',failure='nonpositive_or_nonfinite_source_mass');continue
        need(float(np.sum(logs))==float(likelihood),'per-trial log masses sum to unchanged source scalar')
        parts=[roster[int(i)][0]for i in indices];epochs=[roster[int(i)][1]for i in indices]
        coords=xr.Coordinates.from_pandas_multiindex(MultiIndex.from_arrays([parts,epochs],names=('participant','epoch')),'trial')
        events=xr.DataArray(probs,dims=('trial','sample','event'),coords={'event':('event',np.arange(k)[model.channel_map[g,:]>=0]),'sample':('sample',range(M))})
        events=events.assign_coords(coords).assign_coords(group=('trial',groups[mask]));joined.append(events)
    need(np.array_equal(model.channel_pars,old_channel)and np.array_equal(model.time_pars,old_time),'evaluation cannot mutate fit')
    events=None
    if result['status']=='complete':
        events=xr.concat(joined,dim='trial');events.attrs['sfreq']=model.sfreq;events.attrs['event_width_samples']=model.event_width_samples
        times=hmp.utils.event_times(events,add_rt=True,as_time=True).transpose('trial','event').values
        intervals=hmp.utils.event_times(events,duration=True,add_rt=True,as_time=True).transpose('trial','event').values
        need(times.shape==(len(roster),k+1)and intervals.shape==(len(roster),k+1),'complete original timing shape')
        result['timing_rows']=[row_key(a,b)for a,b in zip(events.participant.values,events.epoch.values)]
        result['times_ms']=store.array(prefix+'-times.bin',times,('trial','event_and_endpoint'),'ms',True)
        result['intervals_ms']=store.array(prefix+'-intervals.bin',intervals,('trial','interval'),'ms',True)
        if k==5:
            sums=np.column_stack((intervals[:,1]+intervals[:,2],intervals[:,3]+intervals[:,4]))
            result['sums_ms']=store.array(prefix+'-sums.bin',sums,('trial','declared_sum'),'ms',True)
    session.tick();descriptor=store.json(prefix+'.json',result)
    return result,descriptor,events
