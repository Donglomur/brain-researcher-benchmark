"""Claim verification after sealed predictions; no favored anatomical story."""
from .contracts import need,finite

def programme_report(production,scored):
    from .catalogue import sensitivity_catalogue,exploratory_catalogue
    from .policy import tier_dispositions
    production.validate();cat=production.catalogue
    need(scored['support'] is production.support and scored['policy'] is cat.policy,'actual scored same-policy/common-support producer')
    return {'task':'NEURAL-061','selected_tier':cat.policy.tier.value,
            'claim_scope':scored['comparison_claim'],'tier_dispositions':tier_dispositions(cat.policy),
            'selected_disposition_count':len(production.collection.validate_seal()),
            'complete_prediction_count':sum(r.status.value=='complete' for r in production.collection.seal),
            'scientific_unavailable_count':sum(r.status.value=='scientific_unavailable' for r in production.collection.seal),
            'all_regions':cat.regions,'all_planned_animals':cat.animals,'all_planned_sessions':cat.evaluation,
            'common_support':scored['coverage'],'results':scored,
            'full_sensitivity_catalogue':sensitivity_catalogue(cat),'full_exploratory_catalogue':exploratory_catalogue(cat),
            'original_S1_reference_fits_coefficient_per_region':100440,
            'original_exploratory_hypotheses_coefficient_per_region':2808,
            'unselected_work_is_scientifically_unavailable':False,
            'open_gate_groups':15,'runtime_qualified':False,'native_capacity_measured':False,
            'resource_demand':production.operation_plan,'actual_resource_extents':'UNKNOWN',
            'reasoning_rubric':'UNAVAILABLE: native precommit evidence issuer and independently blinded rubric not supplied; external claims are not accepted as precommitted',
            'limitations':('observational anatomy and matching; no causal regional claim',
                           'public-data development and historical exposure not erased by server withholding',
                           '13 animals at most; ten match seeds are not independent animals',
                           'reference and candidate loss competence remain separate from favorable BC-minus-BR contrast')}

def verify_claims(claims,scored,tolerance=1e-8):
    need(type(claims) is list and len(claims)<=10000,'bounded precommitted scientific report')
    checked=[];seen=set()
    for c in claims:
        need(type(c) is dict and set(c)=={'panel','head','region','budget','realization','contrast','mean','n_animals','interpretation'},'closed evidence claim')
        key=(c['panel'],c['head'],c['region'],c['budget'],c['realization'])
        need((key,c['contrast']) not in seen,'no repeated claim');seen.add((key,c['contrast']))
        need(key in scored['animal_aggregates'],'claim belongs to frozen complete estimator family')
        truth=scored['animal_aggregates'][key];need(c['contrast'] in truth['means'],'declared contrast')
        value=truth['means'][c['contrast']]
        valid=(c['mean'] is None if value is None else abs(finite(c['mean'])-value)<=tolerance*max(1,abs(value)))
        valid=valid and type(c['n_animals']) is int and c['n_animals']==truth['n_animals']
        valid=valid and c['interpretation'] in ('observational_conditional','insufficient_support','inconclusive')
        checked.append({'key':key,'contrast':c['contrast'],'numerically_supported':valid,
                        'actual_mean':value,'actual_n_animals':truth['n_animals'],
                        'causal_or_population_claim_accepted':False})
    return {'claims':checked,'n_claims':len(checked),'supported':sum(r['numerically_supported'] for r in checked),
            'empty_report_is_complete_scientific_reasoning':False,'free_text_reasoning_requires_blinded_human_rubric':True}
