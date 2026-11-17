"""Closed one-session projections and complete query vectors; no private read."""
import copy
import math
from io_utils import need

ARMS = ('context_handle', 'grc', 'cf', 'joint')
MODES = ('frozen_program', 'case_adaptive_equal_inputs_tools_compute')
TRIAL = {'trial_id', 'session_id', 'trial_order', 'delay_s', 'stage',
         'neural_time', 'grc', 'cf', 'handle_time', 'handle'}
GROUPS = {'one_second_expert': (1., 5), 'two_second_novice': (2., 5),
          'two_second_expert': (2., 6)}


def validate(public):
    need(type(public) is dict and set(public) == {'schema', 'cases', 'view_scope', 'query_target_feedback'}, 'Closed public packet')
    need(public['schema'] == 'neural030_cerebellar_public_v1' and
         public['view_scope'] == 'retrospective_processed_within_session_calibration' and
         public['query_target_feedback'] is False, 'Accepted public contract')
    need(type(public['cases']) is list and len(public['cases']) == 16, 'All16 sessions required')
    sessions = set(); trials = set(); groups = dict.fromkeys(GROUPS, 0)
    for case in public['cases']:
        need(type(case) is dict and set(case) == {'session_id', 'condition', 'delay_s', 'train', 'development', 'query'}, 'Closed session')
        sid = case['session_id']
        need(type(sid) is str and sid and sid not in sessions, 'Unique session'); sessions.add(sid)
        need(case['condition'] in GROUPS and type(case['delay_s']) in (int, float) and
             case['delay_s'] == GROUPS[case['condition']][0], 'Accepted condition/delay')
        groups[case['condition']] += 1; order = 0
        for split in ('train', 'development', 'query'):
            need(type(case[split]) is list and case[split], 'Every split nonempty')
            for trial in case[split]:
                need(type(trial) is dict and set(trial) == (TRIAL if split == 'query' else TRIAL | {'counts'}), 'Exact permitted public trial fields')
                tid = trial['trial_id']; need(type(tid) is str and tid and tid not in trials, 'Unique trial'); trials.add(tid)
                need(trial['session_id'] == sid and trial['delay_s'] == case['delay_s'] and
                     trial['stage'] == case['condition'] and type(trial['trial_order']) is int and
                     trial['trial_order'] > order, 'Unmodified case and chronological trial binding')
                order = trial['trial_order']
    need(all(groups[k] == v[1] for k, v in GROUPS.items()), 'Full5/5/6 groups')
    return public


def project(case, arm):
    need(arm in ARMS, 'Prespecified arm')
    result = copy.deepcopy(case)
    for split in ('train', 'development', 'query'):
        for trial in result[split]:
            if arm not in ('grc', 'joint'):
                del trial['grc']
            if arm not in ('cf', 'joint'):
                del trial['cf']
            if arm == 'context_handle':
                del trial['neural_time']
    return {'schema': 'neural030-candidate-case-v1', 'arm': arm, 'case': result}


def predictions(value, case):
    need(type(value) is list and len(value) == len(case['query']), 'Complete query population')
    expected = {t['trial_id']: int(round(t['delay_s'] / .1)) for t in case['query']}
    found = set()
    for row in value:
        need(type(row) is dict and set(row) == {'trial_id', 'counts'}, 'Exact submission row')
        tid = row['trial_id']; need(tid in expected and tid not in found, 'Complete unique query identities'); found.add(tid)
        values = row['counts']; need(type(values) is list and len(values) == expected[tid] and
            all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in values), 'Complete finite nonnegative count vector')
    need(found == set(expected), 'All query trials required')
    return value
