"""Consumer checks against frozen declarations; checks do not issue membership.
Broader catalogue and secondary source memberships require separate authenticated
outside originals and a real owner. Neither has been admitted in this build.
"""
from .design import CATALOGUE,SECONDARY,ROLE_NAMES

def require_population_shape(catalogue,secondary):
    for population,declared in ((catalogue,CATALOGUE),(secondary,SECONDARY)):
        records=population['records'];ids=[str(r['ophys_experiment_id']) for r in records]
        if len(ids)!=len(set(ids)) or len(ids)!=declared['declared_experiments']:raise ValueError('complete declared experiment membership differs')
        if len({str(r['mouse_id']) for r in records})!=declared['declared_mice']:raise ValueError('complete declared mouse membership differs')
        if 'declared_sessions' in declared and len({str(r['ophys_session_id']) for r in records})!=declared['declared_sessions']:raise ValueError('declared source-session count differs')
        if 'declared_containers' in declared and len({str(r['ophys_container_id']) for r in records})!=declared['declared_containers']:raise ValueError('declared selected-container count differs')
        if not population.get('source_membership_binding'):raise ValueError('missing source binding consumer input')
    all_ids={str(r['ophys_experiment_id']) for r in catalogue['records']}
    if not {str(r['ophys_experiment_id']) for r in secondary['records']}<=all_ids:raise ValueError('secondary outside original catalogue')
    assignments=secondary['mouse_assignments']
    if set(assignments)!={str(r['mouse_id']) for r in secondary['records']}:raise ValueError('source assignments incomplete')
    if {role:sum(v==role for v in assignments.values()) for role in ROLE_NAMES}!=SECONDARY['roles']:raise ValueError('original whole-mouse role counts differ')
    for row in secondary['records']:
        if row['split']!=assignments[str(row['mouse_id'])] or row['experience_level'] not in ('Novel 1','Novel >1'):raise ValueError('selected phase or split changed')
    return True
