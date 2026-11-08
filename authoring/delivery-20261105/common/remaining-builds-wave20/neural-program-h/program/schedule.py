"""Complete fixed programme schedule; no convenient scope reduction."""
from core import encoded, integer, need, pin

MODES = ('frozen_program', 'case_adaptive_equal_inputs_tools_compute')
REPLICATES = ('replicate-01', 'replicate-02', 'replicate-03')
ROLES = ('nuisance', 'joint')
ARMS = ('nuisance', 'joint', 'joint_test_shift10')
FAMILIES = ('linear', 'trees', 'fourier')


def candidate_phases(sessions):
    need(type(sessions) is list and len(sessions) == 29, 'whole29 ordered sessions')
    phases = []
    for mode in MODES:
        for replicate in REPLICATES:
            for session in sessions:
                ordinal = session['ordinal']
                for kind, role, arm in (('fit', 'nuisance', None), ('infer', 'nuisance', 'nuisance'),
                                        ('fit', 'joint', None), ('infer', 'joint', 'joint'),
                                        ('infer', 'joint', 'joint_test_shift10')):
                    phases.append({'mode': mode, 'replicate': replicate, 'ordinal': ordinal,
                                   'session_id': session['session_id'], 'kind': kind, 'role': role, 'arm': arm})
    need(len(phases) == 870, 'complete candidate870 phase schedule')
    return phases


def author_episodes(sessions):
    result = []
    for mode in MODES:
        for replicate in REPLICATES:
            for role in ROLES:
                slots = ('global',) if mode == 'frozen_program' else tuple(row['ordinal'] for row in sessions)
                result.extend((mode, replicate, role, slot) for slot in slots)
    need(len(result) == 180 and sum(x[3] == 'global' for x in result) == 6, 'six global plus174 adaptive contexts')
    return result


def references(sessions):
    result = []
    for session in sessions:
        for role in ROLES:
            result.append({'ordinal': session['ordinal'], 'session_id': session['session_id'],
                           'kind': 'reference_fit', 'role': role, 'arm': None})
            for arm in (('nuisance',) if role == 'nuisance' else ('joint', 'joint_test_shift10')):
                result.append({'ordinal': session['ordinal'], 'session_id': session['session_id'],
                               'kind': 'reference_infer', 'role': role, 'arm': arm})
    need(len(result) == 145, '58 reference selection/refit processes and87 three-family inference processes')
    return result


def full(sessions):
    body = {'schema': 'neural060_full_schedule_v1', 'author_episodes': author_episodes(sessions),
            'candidate_phases': candidate_phases(sessions), 'reference_phases': references(sessions),
            'constituent_reference_fits': 928, 'constituent_reference_family_inferences': 261,
            'candidate_panels': 18, 'reference_family_panels': 9}
    return body, pin(encoded(body))


def disposition(expected, entered, completed, failed):
    integer(expected); integer(entered); integer(completed); integer(failed)
    need(completed+failed <= entered <= expected, 'disjoint phase disposition counts')
    return {'expected': expected, 'completed': completed, 'failed': failed,
            'entered_incomplete': entered-completed-failed, 'unentered': expected-entered}
