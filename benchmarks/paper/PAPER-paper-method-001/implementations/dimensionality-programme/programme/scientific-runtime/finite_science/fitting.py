"""Independent reference state construction from exact disjoint development pools."""
import math
from .common import LEVELS,require,result
from .catalog import REFERENCE_BANK,PRIMARY_KEYS

def pool(payload, residual=False):
    req=payload['request'];p=payload['protocol'];reference_id=req['reference_id'];variant=req['variant']
    definition=next((x for x in REFERENCE_BANK if x['id']==reference_id),None)
    require(definition is not None and variant in definition['variants'],'exact reference fit identity')
    require(p.get('fit_pool_ancestry_admitted') is True and p.get('stage')==('uncertainty_residual_fit' if residual else 'point_fit'),'only disjoint designated development groups may fit reference state','qualification_required')
    compatible=[x for x in PRIMARY_KEYS if reference_id in x['eligible_reference_ids_before_qualification'] and x['target_class']==p['target'] and x['protocol']==p['protocol_id'] and x['trial_view']==p['trial_view']]
    # Diagnostic prior has no primary eligible key, but uses all keys for its
    # matching target/protocol/view, never any held/calibration outcomes.
    if reference_id=='REF16_PRIOR_CONSTANT':compatible=[x for x in PRIMARY_KEYS if x['target_class']==p['target'] and x['protocol']==p['protocol_id'] and x['trial_view']==p['trial_view']]
    require(compatible,'no compatible development key')
    expected=req['expected_worlds'];records=req['records'];by={x['world_id']:x for x in records};roster={x['world_id']:x for x in expected}
    require(len(roster)==len(expected) and len(by)==len(records) and set(by)==set(roster),'exact complete development pool')
    required={(k['id'],cell) for k in compatible for cell in k['cells']}
    actual={(x['key_id'],x['cell']) for x in expected}
    require(actual==required and all(sum((x['key_id'],x['cell'])==pair for x in expected)==20 for pair in required),'exact20 designated development worlds per compatible cell/key')
    values=[];bad=[]
    for w,expect in roster.items():
        row=by[w]
        for key in ('key_id','cell','input_identity','allocation'):
            require(row[key]==expect[key],'development '+key+' mismatch')
        require(expect['allocation']==p['stage'],'wrong disjoint allocation')
        truth=expect['truth'];require(math.isfinite(truth) and truth>0,'development identified truth')
        if residual:
            require(row['reference_id']==reference_id and row['variant']==variant and row['point_state_id']==req['point_state_id'] and row['point_source_sha256']==req['point_source_sha256'],'residual point method/state/source mismatch')
            value=row.get('gamma');valid=row['status']=='ok' and type(value) in (float,int) and math.isfinite(value) and value>0
            values.append(abs(math.log(value)-math.log(truth)) if valid else None)
            if not valid:bad.append(w)
        else:values.append(math.log(truth))
    return values,list(roster),bad

def fit(payload):
    req=payload['request'];p=payload['protocol'];ref=req['reference_id']
    require(any(x['id']==ref and req['variant'] in x['variants'] for x in REFERENCE_BANK),'reference fit identity')
    if ref!='REF16_PRIOR_CONSTANT':
        require(p.get('reference_definition_presealed') is True,'presealed stateless method definition')
        return result({'state':{'kind':'no_fit','reference_id':ref,'variant':req['variant'],'target':p['target'],'protocol_id':p['protocol_id'],'trial_view':p['trial_view']}},dict(training_worlds=0,fit_executed=False))
    values,worlds,bad=pool(payload)
    state=dict(kind='point_fit_log_prior',reference_id=ref,variant=req['variant'],prior_log_mean=math.fsum(values)/len(values),target=p['target'],protocol_id=p['protocol_id'],trial_view=p['trial_view'],training_world_ids=worlds)
    return result({'state':state},dict(training_worlds=len(worlds),fit_executed=True))

def residual_fit(payload):
    values,worlds,bad=pool(payload,True);req=payload['request'];p=payload['protocol'];ordered=sorted(math.inf if v is None else v for v in values);quantiles={}
    for level in LEVELS:
        k=math.ceil((len(values)+1)*level);radius=ordered[k-1] if k<=len(values) else math.inf
        quantiles[str(level)]={'order_index':k,'radius':radius if math.isfinite(radius) else None,'unbounded':not math.isfinite(radius)}
    state=dict(kind='development_absolute_log_residual',reference_id=req['reference_id'],variant=req['variant'],point_state_id=req['point_state_id'],point_source_sha256=req['point_source_sha256'],target=p['target'],protocol_id=p['protocol_id'],trial_view=p['trial_view'],training_world_ids=worlds,quantiles=quantiles)
    return result({'state':state,'residuals':values},dict(worlds=len(worlds),invalid_worlds=bad),['Invalid development predictions are retained as unbounded residuals; no guarantee under held-family shift.'])
