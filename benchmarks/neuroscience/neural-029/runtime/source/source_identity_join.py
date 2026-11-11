"""Complete metadata inverse for the existing N029 raw projection.

This validates an operator-selected index, not its biological truth. No arrays,
files, random identities, scientific fits or scores are consumed here. Global
registered-cell components remain operator-private; public IDs stay unchanged.
"""
import math
import re


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def positive(value):
    return type(value) is int and value > 0


def cells(value):
    # MATLAB jsonencode serializes a one-element numeric vector as a scalar.
    value = [value] if positive(value) else value
    need(type(value) is list and value and all(positive(x) for x in value), 'positive cell indices')
    need(len(set(value)) == len(value), 'one-to-one cell identities')
    return value


def validate_source_index(index):
    keys = {'schema', 'source_record', 'complete_selected_cohort', 'source_part_count',
            'source_session_count', 'selected_target_session_indices1', 'cohort_dispositions', 'pairs',
            'scientific_fits', 'scientific_scores'}
    need(type(index) is dict and set(index) == keys, 'exact raw index')
    need(index['schema'] == 'neural029-raw-projection-v2' and index['source_record'] == '21645651'
         and index['complete_selected_cohort'] is True, 'declared complete source projection')
    need(type(index['source_part_count']) is int and index['source_part_count'] == 2
         and all(type(index[k]) is int and index[k] == 0 for k in ('scientific_fits', 'scientific_scores')),
         'two parts and no scientific execution in source projection')
    ns = index['source_session_count']; need(positive(ns), 'source session count')
    selected = index['selected_target_session_indices1']; pairs = index['pairs']
    need(type(selected) is list and selected and all(positive(s) and s <= ns for s in selected)
         and selected == sorted(set(selected)), 'complete unique ordered target-session list')
    need(type(pairs) is list and len(pairs) == len(selected), 'complete declared pair roster')
    census = index['cohort_dispositions']
    need(type(census) is list and len(census) == ns, 'every source session has a disposition')
    selected_from_census = []
    for ordinal, session in enumerate(census, 1):
        need(type(session) is dict and set(session) == {'session_index1', 'is_grc', 'delay_s',
             'has_chronic_green', 'disposition'} and session['session_index1'] == ordinal
             and type(session['session_index1']) is int and type(session['is_grc']) is bool
             and type(session['has_chronic_green']) is bool and type(session['delay_s']) in (int, float)
             and math.isfinite(session['delay_s']), 'complete ordered session census')
        expected = ('outside_GrC_scope' if not session['is_grc'] else
                    'not_two_second_target' if session['delay_s'] != 2 else
                    'no_chronicGreen_registration' if not session['has_chronic_green'] else
                    'required_registered_target')
        need(session['disposition'] == expected, 'source-backed structural session disposition')
        if expected == 'required_registered_target':
            selected_from_census.append(ordinal)
    need(selected_from_census == selected, 'all and only structurally selected target sessions')
    required = {'pair_index1', 'source_session_index1', 'target_session_index1', 'mouse_id',
                'reward_type', 'source_cells_index1', 'target_cells_index1', 'source_shape',
                'target_shape', 'source_time_seconds', 'target_time_seconds', 'source_file', 'target_file',
                'registration_rows_source_target'}
    session_context = {}; session_support = {}; links = []; total = 0; units = []; files = set()
    for ordinal, row in enumerate(pairs, 1):
        need(type(row) is dict and set(row) == required, 'exact raw pair fields')
        need(type(row['pair_index1']) is int and row['pair_index1'] == ordinal, 'exact exporter pair order')
        source, target = row['source_session_index1'], row['target_session_index1']
        need(positive(source) and positive(target) and source <= ns and target <= ns and source != target
             and target == selected[ordinal - 1], 'source/target session inverse')
        mouse, reward = row['mouse_id'], row['reward_type']
        need(type(mouse) is str and mouse and reward in ('DAT', 'MFB'), 'declared mouse/reward identity')
        registered = {}
        for side, session, delay in [('source', source, 1), ('target', target, 2)]:
            context = (mouse, reward, delay)
            need(session not in session_context or session_context[session] == context, 'consistent repeated-session biological role')
            session_context[session] = context
            c = cells(row[side + '_cells_index1']); shape = row[side + '_shape']
            need(type(shape) is list and len(shape) == 3 and all(positive(x) for x in shape)
                 and shape[1] == len(c) and shape[2] >= 2, 'full trial/cell/time dimensions')
            need(shape[0] >= (5 if side == 'source' else 1), 'existing whole-trial minimum')
            clock = row[side + '_time_seconds']
            need(type(clock) is list and len(clock) == shape[2]
                 and all(type(x) in (int, float) and math.isfinite(x) for x in clock)
                 and all(a < b for a, b in zip(clock, clock[1:]))
                 and clock[0] <= 0 and clock[-1] >= 3, 'original neural clock and full support')
            support = (shape[0], tuple(clock))
            need(session not in session_support or session_support[session] == support,
                 'repeated session has identical full trial and native clock support')
            session_support[session] = support
            need(census[session - 1]['is_grc'] and census[session - 1]['delay_s'] == delay,
                 'pair roles agree with complete session census')
            desc = row[side + '_file']; extent = 8 * shape[0] * shape[1] * shape[2]
            need(type(desc) is dict and set(desc) == {'path', 'bytes', 'sha256'}
                 and desc['path'] == f'pair{ordinal:04d}_{side}.f64'
                 and type(desc['bytes']) is int and desc['bytes'] == extent
                 and type(desc['sha256']) is str and re.fullmatch('[0-9a-f]{64}', desc['sha256']) is not None,
                 'exact original exporter file/extent binding')
            need(desc['path'] not in files, 'unique source projection file')
            files.add(desc['path']); total += extent
            need(total <= 150000000, 'existing full projection cap before identity allocation')
            registered[side] = c
        need(len(registered['source']) == len(registered['target']), 'registered axis length equality')
        registration = row['registration_rows_source_target']
        need(type(registration) is list and registration and all(type(edge) is list and len(edge) == 2
             and all(type(c) is int and c >= 0 for c in edge) for edge in registration),
             'all original oriented registration rows including zero-sided rows')
        for axis in (0, 1):
            positive_ids = [edge[axis] for edge in registration if edge[axis] > 0]
            need(len(set(positive_ids)) == len(positive_ids), 'unique positives in full registration')
        matched_rows = [i for i, edge in enumerate(registration, 1) if all(edge)]
        need([registration[i - 1][0] for i in matched_rows] == registered['source'] and
             [registration[i - 1][1] for i in matched_rows] == registered['target'],
             'retain exactly every positive registered row in source order')
        pair_links = []
        for axis, (s, t) in enumerate(zip(registered['source'], registered['target']), 1):
            left, right = (source, s), (target, t)
            links.append((left, right)); pair_links.append({'axis_index1': axis, 'source': list(left), 'target': list(right)})
        units.append({'pair_index1': ordinal, 'mouse_id': mouse, 'reward_type': reward,
                      'source_session_index1': source, 'target_session_index1': target,
                      'registered_axes': pair_links,
                      'registration_rows_source_target': registration,
                      'matched_registration_rows_index1': matched_rows,
                      'structurally_unmatched_registration_rows_index1': [i for i, edge in enumerate(registration, 1) if not all(edge)],
                      'source_shape': row['source_shape'], 'target_shape': row['target_shape'],
                      'native_clock_support_seconds': {side: [row[side + '_time_seconds'][0], row[side + '_time_seconds'][-1]] for side in ('source', 'target')},
                      'source_trial_indices1': list(range(1, row['source_shape'][0] + 1)),
                      'target_trial_indices1': list(range(1, row['target_shape'][0] + 1)),
                      'event_alignment': 'movement_end', 'event_clock_field': 'tmpx_right',
                      'sample_ticks': {'start': 0, 'stop_inclusive': 60, 'ticks_per_second': 20}})
    need(total <= 150000000, 'existing full projection cap; no cohort reduction')
    parent = {node: node for edge in links for node in edge}
    def find(node):
        while parent[node] != node:
            node = parent[node]
        return node
    for left, right in links:
        a, b = find(left), find(right)
        parent[max(a, b)] = min(a, b)
    groups = {}
    for node in sorted(parent):
        groups.setdefault(find(node), []).append(node)
    components = []
    node_component = {}
    for number, nodes in enumerate(groups.values(), 1):
        need(len({n[0] for n in nodes}) == len(nodes), 'registration cannot equate distinct cells in one session')
        need(len({session_context[n[0]][0] for n in nodes}) == 1, 'registered cell cannot cross mice')
        components.append({'component_index1': number, 'session_cell_indices1': [list(n) for n in nodes]})
        node_component.update({n: number for n in nodes})
    for row in units:
        for axis in row['registered_axes']:
            axis['component_index1'] = node_component[tuple(axis['source'])]
    return {'schema': 'neural029_private_identity_inverse_v2', 'pairs': units,
            'cohort_dispositions': census, 'source_session_count': ns,
            'registered_components': components, 'declared_raw_bytes': total,
            'source_truth_verified': False,
            'limit': 'Exact inverse of selected source index only; complete MAT/biological/clock qualification remains required.'}


def bind_public_identity(index, public, index_sha256):
    """Preserve an operator-private index and exact public axes for scorer validation."""
    inverse = validate_source_index(index)
    need(type(index_sha256) is str and re.fullmatch('[0-9a-f]{64}', index_sha256), 'source index hash')
    need(len(public['pairs']) == len(inverse['pairs']), 'complete public/private identity join')
    axes = []
    for raw, exposed in zip(inverse['pairs'], public['pairs'], strict=True):
        need(len(exposed['cell_ids']) == len(raw['registered_axes'])
             and len(exposed['query_ids']) == len(raw['target_trial_indices1'])
             and exposed['calibration_trials'] == 4 * len(raw['source_trial_indices1']) // 5
             and exposed['validation_trials'] == len(raw['source_trial_indices1']) - exposed['calibration_trials']
             and exposed['source_delay_seconds'] == 1 and exposed['target_delay_seconds'] == 2
             and exposed['reward_type'] == raw['reward_type'], 'complete public axis and planned-condition join')
        axes.append({k: exposed[k] for k in ('pair_id', 'cell_ids', 'query_ids',
                     'calibration_trials', 'validation_trials')})
    return {'schema': 'neural029-bound-identity-v2', 'source_index_sha256': index_sha256,
            'source_index': index, 'public_axes': axes, 'source_truth_verified': False}


def support_report(bound, public):
    """Recompute the graph from bound ordinary metadata; no biological truth claim."""
    need(type(bound) is dict and set(bound) == {'schema', 'source_index_sha256', 'source_index',
         'public_axes', 'source_truth_verified'} and bound['schema'] == 'neural029-bound-identity-v2'
         and bound['source_truth_verified'] is False, 'exact private identity binding')
    need(bound == bind_public_identity(bound['source_index'], public, bound['source_index_sha256']),
         'bound private index and all public axes agree')
    inverse = validate_source_index(bound['source_index'])
    for raw, exposed in zip(inverse['pairs'], public['pairs'], strict=True):
        raw.update({k: exposed[k] for k in ('pair_id', 'cell_ids', 'query_ids',
                   'calibration_trials', 'validation_trials')})
    components = inverse['registered_components']
    for comp in components:
        appearances = [{'pair_id': p['pair_id'], 'axis_index1': axis['axis_index1']}
                       for p in inverse['pairs'] for axis in p['registered_axes']
                       if axis['component_index1'] == comp['component_index1']]
        comp['pair_appearances'] = appearances
        comp['appearance_count'] = len(appearances)
    sessions = []
    for session in sorted({p[side + '_session_index1'] for p in inverse['pairs'] for side in ('source', 'target')}):
        appearances = [(p, side) for p in inverse['pairs'] for side in ('source', 'target')
                       if p[side + '_session_index1'] == session]
        p, side = appearances[0]
        trials = p[side + '_trial_indices1']
        sessions.append({'session_index1': session, 'mouse_id': p['mouse_id'], 'role': side,
                         'trial_count': len(trials), 'trial_indices1': trials,
                         'pair_ids': [row['pair_id'] for row, _ in appearances],
                         'pair_appearance_count': len(appearances),
                         'repeated_trial_appearances_beyond_first': len(trials) * (len(appearances) - 1)})
    inverse.update({'schema': 'neural029-support-report-v2', 'source_index_sha256': bound['source_index_sha256'],
        'mice': sorted({p['mouse_id'] for p in inverse['pairs']}), 'sessions': sessions,
        'counts': {'mice': len({p['mouse_id'] for p in inverse['pairs']}),
                   'pairs': len(inverse['pairs']), 'selected_sessions': len(sessions),
                   'registered_components': len(components),
                   'cell_pair_appearances': sum(len(p['registered_axes']) for p in inverse['pairs']),
                   'recurrent_components': sum(c['appearance_count'] > 1 for c in components),
                   'source_unique_trials': sum(s['trial_count'] for s in sessions if s['role'] == 'source'),
                   'target_unique_trials': sum(s['trial_count'] for s in sessions if s['role'] == 'target'),
                   'source_repeated_trial_appearances_beyond_first': sum(s['repeated_trial_appearances_beyond_first'] for s in sessions if s['role'] == 'source'),
                   'structurally_unmatched_registration_rows': sum(len(p['structurally_unmatched_registration_rows_index1']) for p in inverse['pairs'])},
        'unsupported_required_pairs': [],
        'unsupported_pair_policy': 'Any required unsupported pair refuses the whole preparation; this report exists only for a complete declared index.',
        'outcome_or_response_exclusions': False,
        'all_declared_trials_and_positive_registered_cells_retained': True,
        'component_balanced_sensitivity': {'status': 'not_implemented',
            'reason': 'Primary uses a pooled pair scale; no unselected component-level normalization is invented.'},
        'scientific_execution_qualified': False})
    return inverse
