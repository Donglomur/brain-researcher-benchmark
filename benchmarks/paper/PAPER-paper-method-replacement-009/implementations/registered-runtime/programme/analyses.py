"""Full-paper diagnostic sources. Every call is post-capture; no invocation in construction."""
from .domain import Refusal, MissingDefinition, closed

def pca_ari(barrier, neural, labels, rank, seed):
    from .publication import require_result_barrier
    require_result_barrier(barrier)
    from sklearn.decomposition import PCA
    from sklearn.cluster import KMeans
    from sklearn.metrics import adjusted_rand_score
    x=neural.reshape(len(neural),-1)
    projected=PCA(n_components=rank,random_state=seed).fit_transform(x)
    clusters=KMeans(n_clusters=2,n_init=10,random_state=seed).fit_predict(projected)
    return {'projection':projected,'clusters':clusters,'ari':float(adjusted_rand_score(labels,clusters)),
            'scope':'retrospective descriptive query geometry; never a train-time feature'}

def rrr_projection_ari(barrier, neural, learned_u, labels, seed):
    from .publication import require_result_barrier
    require_result_barrier(barrier)
    import numpy as np
    from sklearn.cluster import KMeans
    from sklearn.metrics import adjusted_rand_score
    if neural.ndim!=3 or learned_u.ndim!=2 or neural.shape[2]!=learned_u.shape[0]: raise Refusal('U projection axes')
    trajectories=np.einsum('ktn,nr->ktr',neural,learned_u)
    clusters=KMeans(n_clusters=2,n_init=10,random_state=seed).fit_predict(trajectories.reshape(len(neural),-1))
    return {'trajectories':trajectories,'clusters':clusters,'ari':float(adjusted_rand_score(labels,clusters)),
            'scope':'post-capture projection; original flattening/seed compatibility requires qualification'}

def refit_pruning(barrier, learned_u, train_x, train_y, validation_x, validation_y,
                  query_x, query_y, penalty_grid, seed):
    from .publication import require_result_barrier
    require_result_barrier(barrier)
    from .references import fit_linear,predict_linear
    from .scoring import metric
    rows=[]
    for strategy in ('least','most','random'):
        for point in neuron_pruning(barrier,learned_u,strategy,seed):
            kept=point['kept']
            if len(kept)==0: raise Refusal('pruning empty neural population')
            model,selection=fit_linear(train_x[:,:,kept],train_y,validation_x[:,:,kept],validation_y,'choice',penalty_grid,seed)
            prediction=predict_linear(model,query_x[:,:,kept],'choice')
            rows.append({'strategy':strategy,'fraction':point['fraction'],'kept':kept,
                         'metrics':metric('choice',query_y,prediction),'selection':selection})
    return rows

def conditional_residual(barrier, truth, prediction, conditions, train_truth, train_conditions):
    from .publication import require_result_barrier
    require_result_barrier(barrier)
    import numpy as np
    if len(conditions)!=len(truth) or len(train_conditions)!=len(train_truth): raise Refusal('conditional support')
    means={tuple(k): train_truth[np.all(train_conditions==k,axis=1)].mean(axis=0)
           for k in np.unique(train_conditions,axis=0)}
    if any(tuple(k) not in means for k in conditions): raise Refusal('query condition absent from training')
    template=np.stack([means[tuple(k)] for k in conditions])
    return {'train_condition_mean':template, 'truth_residual':truth-template,
            'prediction_residual':prediction-template,'scope':'descriptive privileged post-capture; no participant input'}

def smoothing(barrier, prediction):
    from .publication import require_result_barrier
    require_result_barrier(barrier)
    from scipy.signal import savgol_filter
    if len(prediction)<17: raise Refusal('original Savitzky-Golay17 support')
    return savgol_filter(prediction,17,3,axis=0)

def fourier(barrier, behavior, sampling_hz):
    from .publication import require_result_barrier
    require_result_barrier(barrier)
    import numpy as np
    if sampling_hz<=0: raise Refusal('actual behavior sampling clock')
    centered=behavior-behavior.mean(axis=-1,keepdims=True)
    spectrum=np.fft.rfft(centered,axis=-1)
    return {'frequency':np.fft.rfftfreq(behavior.shape[-1],1/sampling_hz),
            'power':abs(spectrum)**2/behavior.shape[-1]}

def neuron_pruning(barrier, weights, strategy, seed):
    from .publication import require_result_barrier
    require_result_barrier(barrier)
    import numpy as np
    if weights.ndim!=2: raise Refusal('original neuron-by-rank U')
    importance=np.abs(weights[:,0])
    if strategy=='least': order=np.argsort(importance,kind='stable')
    elif strategy=='most': order=np.argsort(-importance,kind='stable')
    elif strategy=='random': order=np.random.default_rng(seed).permutation(len(weights))
    else: raise Refusal('three original pruning strategies')
    # Returns full retained-unit schedules. Refit caller must use training/validation only.
    return [{'fraction':step/20,'kept':order[int(step*len(order)/20):]} for step in range(20)]

def region_timing(barrier, basis, time_axis, convention):
    from .publication import require_result_barrier
    require_result_barrier(barrier)
    # Paper peak/90%-width alone does not identify sign/gauge or disconnected-peak convention.
    raise MissingDefinition('exact region timing sign/gauge/width convention and original producer required')

def original_bootstrap_diagnostic(barrier, differences, draws, seed):
    from .publication import require_result_barrier
    require_result_barrier(barrier)
    import numpy as np
    if draws!=10000: raise Refusal('original10000 bootstrap draws')
    rng=np.random.default_rng(seed); d=np.asarray(differences)
    samples=np.empty(draws)
    for i in range(draws): samples[i]=rng.choice(d,size=len(d),replace=True).mean()
    observed=float(d.mean())
    return {'samples':samples,'observed':observed,
            'original_uncentered_tail_fraction':float((abs(samples)>=abs(observed)).mean()),
            'valid_zero_effect_null_test':False,
            'reason':'uncentered empirical bootstrap does not impose the null; reproduction-only diagnostic'}

def full_output_roster(plan):
    """Every main/supplement output has an explicit pending/failed/complete occurrence."""
    rows=[]
    for panel in plan.panels:
        rows.append({'panel_id':panel['panel_id'],'obligation':panel['obligation'],
                     'cases':panel['case_ids'],'jobs':panel['job_ids'],
                     'state':'pending' if panel['availability']=='available' else 'unavailable',
                     'reason':panel['reason'],'products':[],'raw_first':None,'secondary':[]})
    return rows

def resolve_panel(rows, panel_id, captures, output_store, failure=None):
    row=next((x for x in rows if x['panel_id']==panel_id),None)
    if row is None or row['state']!='pending': raise Refusal('panel occurrence/retry')
    # Consume this occurrence before fallible admission, without publishing success.
    row['state']='attempted'
    def error(exc):return {'type':type(exc).__name__,'message':str(exc)[:4096]}
    row.setdefault('raw_first',None);row.setdefault('secondary',[])
    if failure is not None:row['raw_first']=error(failure)
    try:
        products=[output_store.require_capture(x).document() for x in captures]
        if failure is None and not products:raise Refusal('complete panel without actual product')
    except BaseException as exc:
        if row['raw_first'] is None:row['raw_first']=error(exc)
        else:row['secondary'].append(error(exc))
        row['state']='failed';row['reason']=row['raw_first'];row['products']=[]
        raise
    row['products']=products
    row['reason']=row['raw_first']
    row['state']='failed' if failure is not None else 'complete'
