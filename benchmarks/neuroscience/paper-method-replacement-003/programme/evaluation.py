"""Complete-denominator probability products and target-last comparison.

These functions are scientific source only. Calling them requires separately
qualified target access after predictions have been captured immutably.
"""
from dataclasses import dataclass
from .cohort import CLASSES, SupportError, validate_transfer_ensemble

@dataclass(frozen=True)
class Prediction:
    units: tuple
    classes: tuple
    probabilities: object
    source_identity: str
    model_identity: tuple
    member_support: object = None

def validate_member_support(units, models, support):
    """Bind tensor columns to the full roster without interpreting identity as data.

    Global transfer and composite grouped predictions use every roster member.
    Unit LOO uses exactly ten members per row, indexed into the complete fitted
    roster; the repeat and held-unit identities must match that row and column.
    """
    units=tuple(units);models=tuple(models)
    if type(support) is not dict or set(support)!={'layout','row_model_indices'}:
        raise SupportError('explicit capture member-support schema required')
    if not models:raise SupportError('complete model roster required')
    if support['layout']=='global_members':
        if support['row_model_indices'] is not None:
            raise SupportError('global members cannot carry a row subset')
        return len(models)
    if support['layout']!='unit_loo_10':raise SupportError('unsupported capture member layout')
    if not units or len(set(units))!=len(units) or len(models)!=10*len(units):
        raise SupportError('LOO requires unique units and the complete ten-repeat roster')
    expected={(repeat,unit) for repeat in range(10) for unit in units}
    tokens=[]
    for model in models:
        if type(model) not in (tuple,list) or len(model)!=2 or type(model[0]) is not int or not 0<=model[0]<10:
            raise SupportError('LOO model repeat/held-unit identity malformed')
        if model[1] not in units:raise SupportError('LOO model held unit outside complete support')
        tokens.append((model[0],model[1]))
    if len(set(tokens))!=len(tokens) or set(tokens)!=expected:
        raise SupportError('LOO model roster missing or duplicated a repeat/held pair')
    rows=support['row_model_indices']
    if type(rows) not in (tuple,list) or len(rows)!=len(units):
        raise SupportError('LOO row-member mapping must cover every ordered unit')
    seen=set()
    for unit,indices in zip(units,rows):
        if type(indices) not in (tuple,list) or len(indices)!=10:
            raise SupportError('LOO row must carry all ten ordered repetitions')
        for repeat,index in enumerate(indices):
            if type(index) is not int or not 0<=index<len(models) or tokens[index]!=(repeat,unit):
                raise SupportError('LOO row/repeat does not match its fitted-model identity')
            if index in seen:raise SupportError('LOO model index reused across rows or repeats')
            seen.add(index)
    if seen!=set(range(len(models))):raise SupportError('LOO mapping omitted a fitted model')
    return 10

def loo_prediction(ensemble, source_identity):
    import numpy as np
    validate_transfer_ensemble(ensemble.folds, ensemble.fitted)
    result=np.empty((len(ensemble.unit_order),5,10),dtype=float)
    seen=set();row_indices=[[None]*10 for _ in ensemble.unit_order]
    for ordinal,model in enumerate(ensemble.fitted):
        token=(model.held,model.repeat)
        if token in seen:raise SupportError('duplicate held-unit prediction')
        seen.add(token)
        value=np.asarray(model.held_probability)
        if value.shape!=(1,5):raise SupportError('LOO prediction extent mismatch')
        row=ensemble.unit_order.index(model.held)
        result[row,:,model.repeat]=value[0]
        row_indices[row][model.repeat]=ordinal
    if len(seen)!=10*len(ensemble.unit_order):raise SupportError('incomplete held-unit repetitions')
    models=tuple((m.repeat,m.held) for m in ensemble.fitted)
    support={'layout':'unit_loo_10','row_model_indices':tuple(tuple(row) for row in row_indices)}
    validate_member_support(ensemble.unit_order,models,support)
    return Prediction(ensemble.unit_order,CLASSES,result.mean(axis=2),source_identity,models,support),result

def validate_prediction(prediction, expected_units):
    import numpy as np
    if prediction.units!=tuple(expected_units) or prediction.classes!=CLASSES:
        raise SupportError('prediction/target ordered identity mismatch')
    p=np.asarray(prediction.probabilities)
    if p.shape!=(len(expected_units),5) or not np.isfinite(p).all() or np.any(p<0) or np.any(p>1):
        raise SupportError('invalid full probability matrix')
    if not np.allclose(p.sum(axis=1),1,rtol=0,atol=1e-6):raise SupportError('probabilities do not sum to one')
    if not prediction.source_identity or not prediction.model_identity:
        raise SupportError('prediction has no captured producer identity')
    return p

def probability_products(prediction, expected_units, protected_targets, thresholds, *, threshold_rule):
    """Mean ensemble probabilities precede ratio/coverage; no unit filtering."""
    import numpy as np
    if threshold_rule not in ('released_prediction_ge','paper_survival_gt'):
        raise SupportError('explicit released-versus-paper confidence convention required')
    p=validate_prediction(prediction,expected_units)
    if set(protected_targets)!=set(expected_units):raise SupportError('incomplete protected target support')
    if any(protected_targets[k] not in CLASSES for k in expected_units):raise SupportError('unsupported target label')
    truth=np.asarray([CLASSES.index(protected_targets[k]) for k in expected_units])
    order=np.sort(p,axis=1);ratio=np.divide(order[:,-1],order[:,-2],out=np.full(len(p),np.inf),where=order[:,-2]!=0)
    predicted=p.argmax(axis=1);products=[]
    for threshold in thresholds:
        if threshold<0 or not np.isfinite(threshold):raise SupportError('invalid precommitted confidence threshold')
        eligible=ratio>=threshold if threshold_rule=='released_prediction_ge' else ratio>threshold
        matrix=np.zeros((5,5),dtype='int64')
        for target,guess,include in zip(truth,predicted,eligible):
            if include:matrix[target,guess]+=1
        denominators=np.bincount(truth,minlength=5)
        retained=np.bincount(truth[eligible],minlength=5)
        row_percent=np.divide(matrix*100,retained[:,None],out=np.full((5,5),np.nan),where=retained[:,None]!=0)
        coverage=np.divide(retained,denominators,out=np.full(5,np.nan),where=denominators!=0)
        products.append({'threshold':threshold,'threshold_rule':threshold_rule,'counts':matrix,
            'retained':retained,'total':denominators,'row_percent':row_percent,'coverage':coverage,
            'unclassified_units':tuple(k for k,ok in zip(expected_units,eligible) if not ok)})
    # Proper scores retain zero true-class probabilities as infinite log loss;
    # no clipping or favorable available-case removal.
    selected=p[np.arange(len(p)),truth]
    with np.errstate(divide='ignore'):logloss=-np.log(selected)
    brier=((p-np.eye(5)[truth])**2).sum(axis=1)
    return {'units':tuple(expected_units),'confidence_ratio':ratio,'threshold_products':products,
        'accuracy':float(np.mean(predicted==truth)),'per_unit_brier':brier,
        'per_unit_log_loss':logloss,'mean_brier':float(brier.mean()),
        'mean_log_loss':float(logloss.mean()),'target_semantics':'supplied protected ground-truth or expert label; never conflated'}

def capture_score_products(outputs,prefix,products):
    """Publish every array and explicit undefined scalar without favorable clipping."""
    import math
    import numpy as np
    sequence=[0]
    def visit(value):
        if isinstance(value,np.ndarray):
            sequence[0]+=1
            return {'array':outputs.array(prefix+f'-array-{sequence[0]:04d}.npy',value).__dict__}
        if isinstance(value,float) and not math.isfinite(value):
            return {'disposition':'undefined' if math.isnan(value) else 'infinite',
                    'value':'nan' if math.isnan(value) else 'positive_infinity' if value>0 else 'negative_infinity'}
        if hasattr(value,'__dataclass_fields__'):return visit(value.__dict__)
        if isinstance(value,dict):return {k:visit(v) for k,v in value.items()}
        if isinstance(value,(list,tuple)):return [visit(x) for x in value]
        return value
    return outputs.json(prefix+'-score.json',visit(products))

def feature_cosine(ground_truth_latents, transfer_latents, ground_truth_keys, transfer_keys):
    import numpy as np
    a=np.asarray(ground_truth_latents);b=np.asarray(transfer_latents)
    if a.shape!=(len(ground_truth_keys),20) or b.shape!=(len(transfer_keys),20):
        raise SupportError('full concatenated two-encoder representation required')
    an=np.linalg.norm(a,axis=1);bn=np.linalg.norm(b,axis=1)
    if np.any(an==0) or np.any(bn==0):raise SupportError('undefined zero-norm cosine; retain full support')
    return {'rows':tuple(ground_truth_keys),'columns':tuple(transfer_keys),
            'cosine':a@b.T/(an[:,None]*bn[None,:])}
