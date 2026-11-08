"""Full original scientific keys and symbolic workload, never a subset selector."""
from common import TASK, STRATA, VARIANTS, ACCESS, need, integer, token, require_pin, pin

EVENT_ORDER = {'offer_CPIn': 0, 'reward_SideOff': 1, 'side_on': 2, 'opt_out': 3}

def validate_study(study):
    need(type(study) is dict and study.get('task') == TASK, 'fixed task')
    need(set(study) == {'task', 'animals', 'paired_animals', 'sessions', 'queries',
                       'admission_evidence', 'eligible_sessions', 'feature_schema_pin'}, 'study schema')
    animals, paired = study['animals'], study['paired_animals']
    need(type(animals) is list and animals == sorted(set(animals)) and len(animals) == 16,
         'original expected full16 identity; contradictions require design review')
    need(type(paired) is list and paired == sorted(set(paired)) and len(paired) == 4 and
         set(paired) <= set(animals), 'independently proved simultaneous4 identity required')
    for animal in animals:
        token(animal)
    require_pin(study['feature_schema_pin'])
    evidence = study['admission_evidence']
    required = {'original_members', 'producer_fields', 'biological_identity', 'session_trial_identity',
                'channel_grid', 'absolute_clocks', 'target_aliases', 'logical_history', 'full_support'}
    need(type(evidence) is dict and set(evidence) == required, 'all independent admission evidence descriptors')
    for value in evidence.values():
        require_pin(value)
    # Pins are references to required independent evidence, not authentication of
    # its issuer, semantics or original MAT contents. Runtime qualification is external.
    sessions = study['sessions']
    need(type(sessions) is dict and set(sessions) == set(animals), 'complete animal sessions')
    for values in sessions.values():
        need(type(values) is list and values and len(values) == len(set(values)), 'unique chronological sessions')
        for value in values:
            token(value)
    need(type(study['queries']) is list and study['queries'], 'complete query ledger')
    ids, targets, physical_targets, support = set(), {}, {}, {a: {k: set() for k in STRATA} for a in animals}
    for row in study['queries']:
        need(set(row) == {'id', 'animal', 'session', 'stratum', 'trial', 'target_key',
                         'target_kind', 'target_trial', 'observation_end_ns', 'target_available_ns',
                         'channel_mask', 'grid_pin', 'alias_pin'}, 'query schema')
        query_id = token(row['id']); need(query_id not in ids, 'unique full query key'); ids.add(query_id)
        a, s, k = row['animal'], row['session'], row['stratum']
        need(a in animals and s in sessions[a] and k in STRATA, 'admitted query identity')
        integer(row['trial']); integer(row['target_trial']); integer(row['observation_end_ns']); integer(row['target_available_ns'])
        token(row['target_key'])
        need(row['target_kind'] == ('SLRT' if k == 'side_on' else 'next_ITI'), 'source target kind')
        mask = row['channel_mask']; need(type(mask) is list and len(mask) == 2 and
              all(type(v) is int and v in (0, 1) for v in mask) and any(mask), 'natural channel availability')
        need(mask != [1, 1] or a in paired, 'simultaneous values only in authenticated paired animals')
        for key in ('grid_pin', 'alias_pin'):
            require_pin(row[key])
        identity = (a, s, row['target_trial'], row['target_kind'], row['target_available_ns'])
        physical=(a,s,row['target_trial'],row['target_kind'])
        declaration=(row['target_key'],row['target_available_ns'])
        need(physical not in physical_targets or physical_targets[physical]==declaration,
             'one canonical target key and release clock per physical target identity')
        physical_targets[physical]=declaration
        if row['target_key'] in targets:
            need(targets[row['target_key']] == identity, 'shared target alias identity')
        targets[row['target_key']] = identity
        support[a][k].add(s)
    expected = study['eligible_sessions']
    need(type(expected) is dict and set(expected) == set(animals), 'complete eligible session declaration')
    for a in animals:
        need(type(expected[a]) is dict and set(expected[a]) == set(STRATA), 'all four strata')
        for k in STRATA:
            values = expected[a][k]
            need(type(values) is list and values == sorted(set(values)) and values and
                 set(values) == support[a][k], 'exact nonempty animal/stratum/session support')
    for animal in paired:
        for stratum in STRATA:
            need(any(q['animal'] == animal and q['stratum'] == stratum and q['channel_mask'] == [1, 1]
                     for q in study['queries']), 'complete simultaneous diagnostic support')
    return pin(study)

def cohort_sets(study):
    return {'full': tuple(study['animals']), 'paired': tuple(study['paired_animals'])}

def cohort_queries(study, cohort, animal=None):
    need(cohort in ('full', 'paired'), 'cohort')
    allowed = set(cohort_sets(study)[cohort])
    return [q for q in study['queries'] if q['animal'] in allowed and
            (animal is None or q['animal'] == animal) and
            (cohort == 'full' or q['channel_mask'] == [1, 1])]

def panel_key(actor, cohort, animal, variant, realization='observed'):
    need(actor in (*ACCESS, 'operator'), 'known actor')
    need(cohort in ('full', 'paired') and variant in VARIANTS, 'cohort/variant')
    return '|'.join((token(realization), actor, cohort, token(animal), variant))

def compile_plan(study, null_ids=()):
    study_pin = validate_study(study)
    need(type(null_ids) in (list, tuple) and len(set(null_ids)) == len(null_ids) and
         'observed' not in null_ids, 'unique selected null realizations')
    for value in null_ids:
        token(value)
    null_ids=sorted(null_ids)
    panels, fits, inner_cells = {}, [], []
    for realization in ('observed', *null_ids):
        for cohort, animals in cohort_sets(study).items():
            for animal in animals:
                training = [a for a in animals if a != animal]
                query_ids = [q['id'] for q in cohort_queries(study, cohort, animal)]
                for variant in VARIANTS:
                    for actor in (*ACCESS, 'operator'):
                        key = panel_key(actor, cohort, animal, variant, realization)
                        panels[key] = {'actor': actor, 'cohort': cohort, 'animal': animal,
                            'variant': variant, 'realization': realization, 'training_animals': training,
                            'query_ids': query_ids, 'heads': list(STRATA),
                            'inner_animals': training, 'bundle_fit_id': key + '|final'}
                        fits.append(key + '|final')
                    for inner in training:
                        for stratum in STRATA:
                            inner_cells.append({'panel': panel_key('operator', cohort, animal, variant, realization),
                                                'inner': inner, 'stratum': stratum})
    r, p = len(study['animals']), len(study['paired_animals'])
    factor = 1 + len(null_ids)
    regularized = factor * 4 * 4 * (r * (20 * (r-1) + 1) + p * (20 * (p-1) + 1))
    return {'schema': 'ach_complete_scientific_plan_v1', 'study_pin': study_pin,
            'feature_schema_pin': study['feature_schema_pin'],
            'panels': panels, 'final_bundle_ids': fits, 'reference_inner_cells': inner_cells,
            'counts': {'realizations': factor, 'candidate_final_bundles': factor*2*4*(r+p),
                       'reference_final_bundles': factor*4*(r+p),
                       'reference_regularized_head_fits': regularized,
                       'reference_inner_head_fits': factor*4*4*20*(r*(r-1)+p*(p-1)),
                       'reference_final_head_fits': factor*4*4*(r+p),
                       'candidate_inner_fits': 'algorithm-defined; complete bounded ledger required',
                       'native_jobs': 111, 'native_roots': 37, 'author_contexts': 4},
            'null_plan_admitted': False, 'runtime_qualified': False, 'scientific_qualified': False}
