"""Immutable questions, separate from the freely chosen participant algorithm."""
from .objects import canonical,digest
from .errors import require

CASE_KEYS=('id','family','dataset','method','configuration','metrics')
def case_identity(case):
    return digest(canonical({k:case[k] for k in CASE_KEYS}))

def validate_case_bindings(plan,scope):
    cases={r['id']:r for r in scope.panel['cases']}
    specs=plan['required_products'];jobs={out:j for j in plan['jobs'] for out in j['expected_outputs']}
    for group in plan['prediction_groups'].values():
        case=cases.get(group['case_id'])
        if case is None:continue
        identity=case_identity(case)
        require(group['dataset']==case['dataset'] and group['method']==case['method'],'original question dataset/method is immutable')
        require(group.get('scientific_identity')==identity,'original question configuration identity')
        for name in group['members']:
            spec=specs[name]
            require(spec.get('scientific_identity')==identity,'prediction original scientific question')
            state=specs[spec['state']]
            require(state['kind']=='state' and state.get('scientific_cases',{}).get(case['id'])==identity,'frozen state original scientific question lineage')
            job=jobs[spec['state']]
            require(job['payload'].get('scientific_cases')==state['scientific_cases'],'producer must receive exact immutable scientific cases')
            require(jobs[name]['payload'].get('scientific_identity')==identity,'query producer scientific identity')
    return True

def soup_union(plan,scope):
    """Every size x dataset x selected original profile x run, plus Base/TUEV10.
    Unavailable data/recipes leave these slots required; they cannot delete slots.
    """
    profiles=('R-paper','R-native','I-person','I-person-montage')
    require(set(profiles)<=set(plan['scientific_profiles']),'complete soup purposes')
    return {(p['id'],p['arm'],purpose,d['id'],size,run,count,'uniform_equal_weights_v1')
        for p in plan['programmes'] for purpose in profiles
        for d in scope.panel['datasets'] for size in ('Small','Base','Large')
        for run in plan['run_rosters'][p['id']]
        for count in ((5,10) if d['id']=='TUEV' and size=='Base' else (5,))}
