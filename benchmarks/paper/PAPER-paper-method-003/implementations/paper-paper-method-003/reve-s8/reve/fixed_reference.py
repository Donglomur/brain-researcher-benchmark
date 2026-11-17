"""Bind independent reference jobs to the retained closed scientific implementation."""
from .objects import canonical,digest
from .errors import require

def validate_reference_case_configuration(c,scope):
    from .scientific_identity import case_identity
    known={case['id']:case for case in scope.panel['cases']}
    for key,fingerprint in c['scientific_cases'].items():
        if key not in known:continue # Additional prospective cases are separately specified.
        case=known[key]
        require(fingerprint==case_identity(case),'fixed reference original case identity')
        require(c['recipe']['method']==case['method'] and c['recipe']['dataset']==case['dataset'],'fixed reference original method and dataset')
        require(c['ablation']==case['configuration'],'fixed reference original condition cannot be relabelled')
    return True

def validate_fixed_reference_plan(plan,scope):
    from reference_actor import selected,OUTPUT_KINDS
    source=scope.fixed_reference
    programmes={p['id']:p for p in plan['programmes']}
    owners={name:job for job in plan['jobs'] for name in job['expected_outputs']}
    for policy in plan['reference_policies']:
        require(policy['source']==source['source_id'],'reference policy must select actual fixed source')
        from reference_runtime.catalog import recipe
        require(policy['search_policy']==recipe(policy['method'],policy['dataset']),'fixed prospective search recipe identity')
    for job in plan['jobs']:
        if programmes[job['programme']]['role']!='reference' or scope.stage[job['stage']]['actor']!='participant_or_reference':continue
        require(job['source']==source['source_id'],'independent reference job fixed source')
        ref,c=selected({'schema':'reve-actor-request-v1','stage':job['stage'],'payload':job['payload']})
        if job['stage']=='S08':
            producer=owners.get(ref['views']['pretrain'])
            require(producer is not None and producer['stage']=='S22' and 'corpus_preprocessing' in producer['payload'],'S08 actual registered full-session S22 input producer')
        if c['recipe']['method']=='REVE-Base-XFT' and job['stage'] in ('S15','S17'):
            producer=owners.get(ref['parent_state']);required_stage='S10' if job['stage']=='S15' else 'S15'
            require(producer is not None and producer['stage']==required_stage,'XFT actual fit/calibration/query producer chain')
        if job['stage'] in ('S09','S10','S11','S15','S17'):validate_reference_case_configuration(c,scope)
        require({plan['required_products'][n]['kind'] for n in job['expected_outputs']}<=OUTPUT_KINDS[job['stage']],'fixed reference stage has actual product implementations')
        if c['recipe']['base'] in ('REVE-Base','CBraMod') and not c['recipe']['method'].endswith('_noPT') and job['stage'] in ('S09','S11','S17'):
            require(c['initialization']!='scratch' and c['pretraining_identity'],'foundation reference cannot substitute an untrained backbone')
        for name in job['expected_outputs']:
            spec=plan['required_products'][name]
            if spec['kind']=='prediction':
                require(c['recipe']['method']==spec['method'] and c['recipe']['dataset']==spec['dataset'],'actual model and question must agree for fixed references')
                require(len(spec['classes'])==c['recipe']['classes'],'actual model class ontology')
    return True

def validate_fixed_registered(source,scope):
    selected=scope.fixed_reference
    require(source['manifest']==selected['files'] and source['source_id']==selected['source_id'] and source['entrypoint']==selected['entrypoint'],'fixed reference original registered source/entrypoint')
