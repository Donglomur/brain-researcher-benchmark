"""Complete per-point/case reference bundle with explicit shared intermediates."""
from .common import LEVELS,ScientificGate,require,result
from .catalog import PRIMARY_KEYS,UNCERTAINTY_RULES

def execute(payload):
    from .references import point
    from .uncertainty import sets
    req=payload['request'];p=payload['protocol'];a=payload['arrays'];key=next((k for k in PRIMARY_KEYS if k['id']==p['primary_key']),None)
    require(key is not None,'primary bundle key')
    point_req=req['point_request'];point_id=f"{key['id']}/{point_req['reference_id']}/{point_req['variant']}"
    require(point_req['reference_id'] in key['eligible_reference_ids_before_qualification'],'point not eligible for key')
    try:estimate=point(dict(payload,request=point_req))
    except ScientificGate as error:estimate=result(status=error.status,support=error.support,diagnostics={'reason':str(error)})
    outputs={};reuse=[]
    for rule,law in UNCERTAINTY_RULES.items():
        if key['family'] not in law['families'] or key['trial_view'] not in law['views']:continue
        for scale in ((1,) if rule=='U03_TWO_AXIS_PERCENTILE' else (1,1.25,1.5,2)):
            ident=f'{point_id}/{rule}/{scale}'
            provider=req['providers'].get(rule)
            failed=None;rule_arrays=dict(a);array_binding=None
            if not provider:failed='Required covariance/resampling/residual provider absent'
            elif not all(provider.get(k) for k in ('source_sha256','state_id','receipt_id','input_identity','qualification_id')):failed='Incomplete original shared-intermediate lineage'
            elif provider['input_identity']!=p['input_identity'] and rule!='U04_DEVELOPMENT_RESIDUAL':failed='Intermediate belongs to another exact case'
            elif provider.get('point_id')!=point_id:failed='Intermediate belongs to another point variant'
            if not failed:
                needed={'U01_FIELLER':'covariance','U02_LOG_DELTA':'covariance','U03_TWO_AXIS_PERCENTILE':'bootstrap_gamma','U04_DEVELOPMENT_RESIDUAL':'residuals'}[rule]
                if not (rule=='U04_DEVELOPMENT_RESIDUAL' and 'residual_quantiles' in provider):
                    bindings=provider.get('array_bindings',{})
                    array_binding=bindings.get(needed) if type(bindings) is dict else None
                    if type(array_binding) is not str or array_binding not in a:
                        failed='Required explicit per-rule admitted intermediate binding absent: '+needed
                    else:rule_arrays[needed]=a[array_binding]
            if failed:
                outputs[ident]=result({'sets':{str(c):{'status':'qualification_required','space':'gamma','intervals':[]} for c in LEVELS}},dict(rule=rule,scale=scale),diagnostics={'reason':failed},status='qualification_required');continue
            q=dict(req.get('uncertainty_request',{}),rule=rule,scale=scale,levels=list(LEVELS),A=estimate['outputs'].get('A'),B=estimate['outputs'].get('B'),gamma=estimate['outputs'].get('gamma'))
            proto=dict(p,uncertainty_structural_admitted=True)
            if rule in ('U01_FIELLER','U02_LOG_DELTA'):proto['covariance_qualification_id']=provider['qualification_id']
            elif rule=='U03_TWO_AXIS_PERCENTILE':proto['resampling_qualification_id']=provider['qualification_id']
            else:
                proto['residual_pool_ancestry_admitted']=provider.get('development_pool_admitted') is True
                if 'residual_quantiles' in provider:q['residual_quantiles']=provider['residual_quantiles'];q['residual_n']=provider['residual_n']
            try:
                if estimate['status']!='ok':
                    outputs[ident]=result({'sets':{str(c):{'status':estimate['status'],'space':'gamma','intervals':[]} for c in LEVELS}},dict(rule=rule,scale=scale),status=estimate['status'])
                else:outputs[ident]=sets(dict(payload,arrays=rule_arrays,protocol=proto,request=q))
            except ScientificGate as error:outputs[ident]=result({'sets':{str(c):{'status':error.status,'space':'gamma','intervals':[]} for c in LEVELS}},error.support,diagnostics={'reason':str(error)},status=error.status)
            outputs[ident]['support']['shared_provider_receipt']=provider['receipt_id'];reuse.append({'variant_id':ident,'provider_receipt':provider['receipt_id'],'array_binding':array_binding,'cost_attribution':'original shared provider cost plus this actual interval computation; controller closes costs'})
    missing=[k for k,v in outputs.items() if v['status']=='qualification_required']
    return result({'point_id':point_id,'point':estimate,'uncertainty':outputs},dict(uncertainty_variants=len(outputs),levels=4,shared_intermediate_reuse=reuse,required_unscorable_variants=missing),status='qualification_required' if missing or estimate['status']=='qualification_required' else 'ok')
