"""Concrete full reference fit/predict, with no selection or target-reader callback."""
import math
from .budget import dimensions
from .contract import config_admit, scope_admit, numpy_checked, projection
from .features import batch_admit, feature_transform, two_pass
from . import ridge, boost, temporal


def labels_admit(np,labels,n,endpoint,budget):
    if type(labels) is not np.ndarray or labels.dtype!=np.dtype('float64') or labels.shape!=(n,) or not labels.flags.c_contiguous:
        budget.fail('training label primitive contract')
    if not np.isfinite(labels).all(): budget.fail('nonfinite training labels')
    if endpoint=='angle' and not ((labels>=-90)&(labels<=90)).all(): budget.fail('angle outside released domain')
    if endpoint!='angle' and not (labels>=0).all(): budget.fail('negative released magnitude/speed')


def fit(scope,batch,labels,configuration,budget):
    config=config_admit(configuration)
    scope_admit(scope,batch,config)
    np=numpy_checked(scope['environment'])
    n,c=batch_admit(np,batch,scope['view'],budget)
    if n==0: budget.fail('no training support')
    labels_admit(np,labels,n,scope['endpoint'],budget)
    plan=dimensions(n,c,config['family'],config,budget,True,scope['environment']['native_workspace_bytes'])
    features,transforms=feature_transform(batch,scope['view'],budget,scope['environment'],temporal=config['family']=='T')
    target=two_pass(np,labels[:,None]); mu=float(target['mean'][0]); scale=float(target['scale'][0])
    constant=bool(np.all(labels==labels[0]))
    standardized=(labels-mu)/scale
    if constant:
        model={'constant':float(labels[0])}; disposition='completed_constant_analytic'
    elif config['family']=='R': model=ridge.solve(np,features,standardized,config['lambda']); disposition='completed_fit'
    elif config['family']=='B': model=boost.fit_boost(np,features,standardized,config,budget); disposition='completed_fit'
    else: model=temporal.train(np,features,batch['mask'],standardized,scope,config,budget); disposition='completed_fit'
    budget.tick()
    return {'schema':'neural049_r1_state_v1','meta':{'scope':scope,'configuration':config,
            'training_count':n,'channels':c,'target_mean':mu,'target_scale':scale,
            'disposition':disposition,'feature_order':'timing,channel-window-band+contrast,channel-window-mask',
            'temporal_order':'source_index,bin-major(mean,max),timing,channel-window-mask'},
            'transforms':transforms,'model':model,'work':{'plan':plan,'budget':budget.snapshot()}}


def state_admit(np,state,batch,budget):
    if type(state) is not dict or set(state)!={'schema','meta','transforms','model','work'} or state['schema']!='neural049_r1_state_v1':
        budget.fail('unrecognized complete state')
    meta=state['meta']; config=config_admit(meta['configuration']); scope=meta['scope']
    # Recheck fit-only scope without admitting any new training data/targets.
    scope_admit(scope,{'ids':scope['training_ids'],'axis':scope['axis']},config)
    if scope['axis']!=batch['axis'] or meta['channels']!=len(batch['axis']) or type(meta['training_count']) is not int or meta['training_count']!=len(scope['training_ids']) or meta['training_count']<1:
        budget.fail('state training/axis mismatch')
    c=meta['channels']; p=6+48*c if config['family']=='T' else 6+165*c
    for name,size in (('channel',c),('scalar',p)):
        stats=state['transforms'][name]
        if type(stats) is not dict or set(stats)!={'mean','scale','active'}: budget.fail('transform state')
        for key,dtype in (('mean','float64'),('scale','float64'),('active','bool')):
            a=stats[key]
            if type(a) is not np.ndarray or a.dtype!=np.dtype(dtype) or a.shape!=(size,): budget.fail('transform dimensions')
        if not np.isfinite(stats['mean']).all() or not np.isfinite(stats['scale']).all() or not (stats['scale']>0).all(): budget.fail('transform finite scale')
    if any(type(meta[k]) not in (int,float) or not math.isfinite(meta[k]) for k in ('target_mean','target_scale')) or meta['target_scale']<=0:
        budget.fail('target training transform')
    model=state['model']
    if meta['disposition']=='completed_constant_analytic':
        if set(model)!={'constant'} or not math.isfinite(model['constant']): budget.fail('constant state')
    elif meta['disposition']!='completed_fit': budget.fail('incomplete fitted state')
    elif config['family']=='R':
        a=model['beta']
        if type(a) is not np.ndarray or a.dtype!=np.dtype('float64') or a.shape!=(p,) or not np.isfinite(a).all() or model['intercept']!=0.0: budget.fail('ridge coefficients')
    elif config['family']=='B':
        if model['completed_trees']!=config['trees'] or len(model['trees'])!=config['trees'] or len(model['thresholds'])!=p or model['learning_rate']!=.05:
            budget.fail('boost schedule/state')
        for tree in model['trees']:
            if type(tree) is not dict or '' not in tree or len(tree)>2*config['leaves']-1: budget.fail('tree structure')
            visited=set(); pending=['']
            while pending:
                path=pending.pop()
                if path in visited or path not in tree: budget.fail('tree missing/cyclic edge')
                visited.add(path); node=tree[path]
                if set(node)=={'value','count'}:
                    if type(node['count']) is not int or node['count']<1 or not math.isfinite(node['value']): budget.fail('invalid leaf')
                elif set(node)=={'feature','threshold','left','right'}:
                    if type(node['feature']) is not int or not 0<=node['feature']<p or not math.isfinite(node['threshold']) or node['left']!=path+'0' or node['right']!=path+'1': budget.fail('invalid split')
                    pending.extend((node['left'],node['right']))
                else: budget.fail('tree node fields')
            if visited!=set(tree): budget.fail('unreachable tree node')
    else:
        shapes=temporal.shapes(c,config['width'])
        for bank in ('parameters','adam_first','adam_second'):
            if set(model[bank])!=set(shapes): budget.fail('temporal tensor inventory')
            for name,shape in shapes.items():
                a=model[bank][name]
                if type(a) is not np.ndarray or a.dtype!=np.dtype('float32') or a.shape!=shape or not np.isfinite(a).all(): budget.fail('temporal tensor primitive')
        expected=config['epochs']*((meta['training_count']+min(32,meta['training_count'])-1)//min(32,meta['training_count']))
        if model['optimizer_steps']!=expected or model['planned_steps']!=expected or model['completed_epochs']!=config['epochs']:
            budget.fail('incomplete temporal schedule')
    return scope,config


def predict(state,batch,budget):
    # Parent authenticates state/source identity before this process; numerical
    # schema admission still checks all learned operands before inference.
    np=numpy_checked(state['meta']['scope']['environment'])
    scope,config=state_admit(np,state,batch,budget)
    n,c=batch_admit(np,batch,scope['view'],budget)
    dimensions(n,c,config['family'],config,budget,False,scope['environment']['native_workspace_bytes'])
    features,_=feature_transform(batch,scope['view'],budget,scope['environment'],statistics=state['transforms'],temporal=config['family']=='T')
    model=state['model']; meta=state['meta']
    if meta['disposition']=='completed_constant_analytic': raw=np.full(n,model['constant'],np.float64)
    else:
        if config['family']=='R': z=ridge.infer(np,model,features)
        elif config['family']=='B': z=boost.infer(np,model,features,budget)
        else: z=temporal.infer(np,features,batch['mask'],model,scope,config,budget)
        raw=np.asarray(z*meta['target_scale']+meta['target_mean'],dtype=np.float64)
    projected=projection(np,raw,scope['endpoint'])
    budget.tick()
    return {'schema':'neural049_r1_predictions_v1','ids':list(batch['ids']),
            'raw':raw,'projected':projected,'fully_masked':~np.any(batch['mask'],axis=(1,2)),
            'endpoint':scope['endpoint'],'required_rows':n,'all_required_rows_returned':True}
