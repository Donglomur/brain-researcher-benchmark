"""Declared discrete metadata in the six historical non-IO source branches.

Additive calibration comparator, not selected by the programme worker. V3's
three IO guards and all V2 numerical roots, tolerances and scores are retained.
MainData.dirTable types remain unreviewed; this is no biological truth check.
"""
from core import BRANCHES, need
import native_compare_v3 as previous


REVIEWED_BRANCHES = frozenset((
    'MainData', 'learningCurves_DA', 'CF_novice', 'passiveMFB', 'gtacr1',
    'learningCurves_gtacr1',
))
# MainData.m 49-124: each value is find(...) or a subset of those row indices.
MAIN_GROUPS = frozenset('''
    CF_DA CF_gcamp CF_gcamp_VTA CF_rcamp CFs_MFB CFs_VTA CFs_haswater
    CFs_haswater_MFB CFs_haswater_VTA CFs_haswater_matched CFs_waterfirst
    DA1s_grcs DA1s_grcs_dat DA1s_grcs_haswater DA1s_grcs_haswater_dat
    DA1s_grcs_haswater_matched DA1s_grcs_haswater_matched_mfb
    DA1s_grcs_haswater_mfb DA1s_grcs_haswater_waterfirst DA1s_grcs_mfb
    DA1s_haswater DA1s_waterfirst DA2s_grcs DA2s_grcs_dat DA2s_grcs_mfb
    GrCs_CF GrCs_MFB GrCs_VTA GrCs_all MFB VTA VTA_250 female
    grcs_1s_has2smatch grcs_2s_has1smatch grcs_2s_has1smatch_mfb male
'''.split())
_RECORD_KEYS = {
    'MainData': frozenset((
        'dirTable', 'native_mname', 'groups', 'n_native_sessions',
        'source_conditions', 'GrC_clock', 'CF_clock',
    )),
    'CF_novice': frozenset((
        'native_sessions', 'session_cell_counts', 'condition',
    )),
    'passiveMFB': frozenset((
        'native_sessions', 'source_clock_last_session', 'condition',
    )),
    'gtacr1': frozenset((
        'native_group_counts', 'source_group_labels', 'group_collections',
    )),
}
_MOUSE_KEYS = frozenset((
    'source_mouse_ordinal', 'trainingDirs', 'normTime', 'days',
))
_DAY_KEYS = frozenset((
    'source_day_ordinal', 'n_movements', 'completed_mask', 'dtb',
))
_OPTIONAL_MASKS = frozenset(('good_movement_mask', 'rewarded_mask'))


def _positive(value, path):
    if type(value) is list:
        for index, item in enumerate(value):
            _positive(item, f'{path}/{index}')
    else:
        need(value > 0, 'Positive source ordinal/index at ' + path)


def _numeric(reference, candidate, path, *, scalar=False, positive=False):
    if scalar:
        need(type(reference) in (int, float) and type(candidate) in (int, float),
             'Scalar source count/ordinal at ' + path)
    previous._exact(reference, candidate, path)
    if positive:
        # _exact already validates both sides as finite, nonnegative integers.
        _positive(reference, 'reference/' + path)
        _positive(candidate, 'candidate/' + path)


def _learning(reference, candidate, branch):
    need(type(reference) is list and type(candidate) is list
         and len(reference) == len(candidate), 'Complete source mouse metadata')
    required = _MOUSE_KEYS | ({'group'} if branch == 'learningCurves_gtacr1' else set())
    for index, (ref_mouse, got_mouse) in enumerate(zip(reference, candidate)):
        for mouse in (ref_mouse, got_mouse):
            # The shared exporter conditionally includes group. Only the gtacr1
            # author script requires it; the DA script never selects by group.
            previous._record(mouse, required, {'group'})
            need(type(mouse['days']) is list, 'Complete source day metadata')
        need(set(ref_mouse) == set(got_mouse), 'Complete optional source group')
        prefix = f'mouse/{index}'
        _numeric(ref_mouse['source_mouse_ordinal'], got_mouse['source_mouse_ordinal'],
                 prefix + '/source_mouse_ordinal', scalar=True, positive=True)
        need(len(ref_mouse['days']) == len(got_mouse['days']),
             'Complete source day support')
        for day_index, (ref_day, got_day) in enumerate(
                zip(ref_mouse['days'], got_mouse['days'])):
            for day in (ref_day, got_day):
                previous._record(day, _DAY_KEYS, _OPTIONAL_MASKS)
            need(set(ref_day) == set(got_day), 'Complete optional source masks')
            day_prefix = f'{prefix}/day/{day_index}'
            _numeric(ref_day['source_day_ordinal'], got_day['source_day_ordinal'],
                     day_prefix + '/source_day_ordinal', scalar=True, positive=True)
            _numeric(ref_day['n_movements'], got_day['n_movements'],
                     day_prefix + '/n_movements', scalar=True)
            for field in sorted({'completed_mask'} | (_OPTIONAL_MASKS & set(ref_day))):
                previous._exact(ref_day[field], got_day[field],
                                day_prefix + '/' + field, boolean=True)


def guard_metadata(reference, candidate, branch):
    if branch not in REVIEWED_BRANCHES:
        return
    if branch in ('learningCurves_DA', 'learningCurves_gtacr1'):
        _learning(reference, candidate, branch)
        return
    for value in (reference, candidate):
        previous._record(value, _RECORD_KEYS[branch])
    if branch == 'MainData':
        _numeric(reference['n_native_sessions'], candidate['n_native_sessions'],
                 'n_native_sessions', scalar=True)
        for value in (reference['groups'], candidate['groups']):
            previous._record(value, MAIN_GROUPS)
        for group in sorted(MAIN_GROUPS):
            _numeric(reference['groups'][group], candidate['groups'][group],
                     'groups/' + group, positive=True)
    elif branch in ('CF_novice', 'passiveMFB'):
        _numeric(reference['native_sessions'], candidate['native_sessions'],
                 'native_sessions', scalar=True)
        if branch == 'CF_novice':
            _numeric(reference['session_cell_counts'], candidate['session_cell_counts'],
                     'session_cell_counts')
    else:
        _numeric(reference['group_collections'], candidate['group_collections'],
                 'group_collections', scalar=True)
        _numeric(reference['native_group_counts'], candidate['native_group_counts'],
                 'native_group_counts')


def compare(reference, candidate, branch):
    need(branch in BRANCHES, 'Original source branch')
    for tree in (reference, candidate):
        need(type(tree) is dict and 'metadata' in tree, 'Bound native metadata')
    guard_metadata(reference['metadata'], candidate['metadata'], branch)
    result = previous.compare(reference, candidate, branch)
    if branch in REVIEWED_BRANCHES:
        result['metadata_policy'] = 'historical_source_declared_discrete_exact_v1'
        # No table schema/type is guessed from numeric JSON storage or equality.
        result['metadata_typing_holds'] = ['dirTable'] if branch == 'MainData' else []
    return result


def grade(payload, store):
    """Same private interface; both candidate arms use this successor guard."""
    need(type(payload) is dict and set(payload) == {
        'schema', 'branch', 'reference', 'A', 'B'}
        and payload['schema'] == 'paper_i_worker_native_grade_v1'
        and payload['branch'] in BRANCHES, 'Exact private branch grade')
    trees = {}
    for role in ('reference', 'A', 'B'):
        record = payload[role]
        need(type(record) is dict and set(record) == {'path', 'pin'},
             'Bound native JSON')
        trees[role] = store.json(record['path'], record['pin'])
    return {
        'schema': 'paper_i_native_branch_grade_v1', 'complete': True,
        'branch': payload['branch'],
        'arms': {role: compare(trees['reference'], trees[role], payload['branch'])
                 for role in ('A', 'B')},
        'biological_truth': False,
    }
