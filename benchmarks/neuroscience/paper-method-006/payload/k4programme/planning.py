"""Full original input/arm requirements, before an isolated deployment exists."""
from .common import require,unique
from .catalog import check_plan
from .comparators import validate_comparison_matrix


def validate_full_support(selection,catalog):
    require(selection['canonical_id']=='PAPER-paper-method-006','canonical-identity')
    require(len(selection['drift_recording_ids'])==len(set(selection['drift_recording_ids']))==512,
            'full-512-source-roster')
    require(len(selection['waveform_recording_ids'])==len(set(selection['waveform_recording_ids']))==11,
            'full-eleven-source-roster')
    cases=unique(selection['cases'],'id')
    synthetic=[c for c in cases.values() if c['kind']=='synthetic']
    hybrid=[c for c in cases.values() if c['kind']=='hybrid']
    bio=[c for c in cases.values() if c['kind']=='biophysical']
    require(len(cases)==11 and len(synthetic)==6 and len(hybrid)==3 and len(bio)==2,'full-eleven-core-cases')
    require({c['condition'] for c in synthetic}=={'no-drift','medium','high','fast','step','aligned-step'},
            'six-original-simulation-conditions')
    for c in synthetic+hybrid:
        units=unique(c['unit_roles'],'unit_id')
        su=sum(r['role']=='single-unit-target' for r in units.values())
        mu=sum(r['role']=='multi-unit-background' for r in units.values())
        require((su,mu,len(units))==((600,600,1200) if c['kind']=='synthetic' else (100,0,100)),
                'complete-generator-and-target-denominators',c['id'])
    require({c['condition'] for c in bio}=={'normal','twice-speed'},'both-biophysical-clock-views')
    for c in bio:
        require(c['unit_roles'] and all(r['role']=='single-unit-target' for r in c['unit_roles']),
                'biophysical-complete-original-SU-roster')
        unique(c['unit_roles'],'unit_id')
    step=next(c for c in synthetic if c['condition']=='step')
    aligned=next(c for c in synthetic if c['condition']=='aligned-step')
    for role in ('drift_realization','unit_selection','event_realization','amplitude_realization','whitening'):
        require(step['paired_original_inputs'][role]==aligned['paired_original_inputs'][role],
                'aligned-step-pairing-lost',role)
    require(selection['additional_original_input_ids']
            and len(set(selection['additional_original_input_ids']))==len(selection['additional_original_input_ids']),
            'additional-real-other-probe-demonstration-inputs-required')
    # Actual identities/extent remain input admission facts, not established by
    # this schema. No presumed total 15/16-root cap or first-600 target slice.
    for scope in ('R_source20','R_paper40','I_bijective_full'):
        validate_comparison_matrix(selection['comparisons'][scope],list(cases),profile=scope)
    require(set(selection['ablation_names'])==set(catalog['scope']['six_ablations']),
            'all-six-original-ablations')
    require(selection['historical_additional_comparisons_complete'] is True
            and selection['historical_matrix_definition_pin'],'additional-original-comparator-grid-unresolved')
    return {'schema_valid':True,'authentic_input_admission':False,
            'cases':list(cases),'target_units':{k:len([u for u in c['unit_roles']
            if u['role']=='single-unit-target']) for k,c in cases.items()},
            'native_isolation':'unavailable','historical_equivalence':False}


def validate_arm_plans(plans,catalog):
    expected={(arm,scope) for arm in ('paper-data','paper-data-plus-author-code')
              for scope in ('R_source20','R_paper40','I_bijective_full')}
    keyed={(p['arm'],p['profile']):p for p in plans}
    require(len(keyed)==len(plans) and set(keyed)==expected,'complete-A-B-R-I-profile-coverage')
    for p in plans:check_plan(p,catalog)
    return {'plans':keyed,'canonical_tasks':1,'candidate_regimes':4,
            'R_source_paper_profiles_separate':True,'not_native_arm_isolation':True}
