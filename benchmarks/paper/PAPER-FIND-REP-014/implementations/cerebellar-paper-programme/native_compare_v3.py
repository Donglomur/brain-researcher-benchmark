"""Source-typed metadata guard for the three original Figure 6 IO branches.

Numerical calibration only. This successor does not execute submitted analysis,
authenticate biological identities, set scientific tolerances, or activate a run.
All original numeric roots and v2 numerical comparison rules remain required.
"""
import math

from core import BRANCHES, need
import native_compare_v2 as previous


REVIEWED_BRANCHES = frozenset((
    'IOChRmine', 'learningCurves_IOChRmine', 'IOChRmine_imaging',
))
_EXPERT_KEYS = frozenset((
    'n_io', 'n_control', 'source_group_labels',
    'native_iodats_size', 'native_ctl_size',
))
_IMAGING_KEYS = frozenset(('native_sessions', 'session_cell_counts'))
_MOUSE_KEYS = frozenset((
    'source_mouse_ordinal', 'trainingDirs', 'normTime', 'days', 'group',
))
_DAY_KEYS = frozenset((
    'source_day_ordinal', 'n_movements', 'completed_mask', 'dtb',
))
_OPTIONAL_MASKS = frozenset(('good_movement_mask', 'rewarded_mask'))


def _discrete(value, path, *, boolean=False):
    """Validate storage-independent source counts, ordinals, sizes and masks."""
    if type(value) is list:
        for index, item in enumerate(value):
            _discrete(item, f'{path}/{index}', boolean=boolean)
        return
    if boolean:
        need(type(value) is bool, 'Source logical mask at ' + path)
    else:
        need(type(value) in (int, float) and math.isfinite(value)
             and value >= 0 and value == int(value),
             'Nonnegative integral source metadata at ' + path)


def _exact(reference, candidate, path, *, boolean=False):
    _discrete(reference, 'reference/' + path, boolean=boolean)
    _discrete(candidate, 'candidate/' + path, boolean=boolean)
    # V2 subsequently retains exact JSON type/shape rules too. An integer-valued
    # MATLAB double remains discrete, independent of its JSON numeric spelling.
    need(reference == candidate, 'Exact source metadata differs at ' + path)


def _record(value, required, optional=()):
    need(type(value) is dict and required <= set(value)
         and set(value) <= required | set(optional),
         'Reviewed source metadata keys')


def guard_metadata(reference, candidate, branch):
    """Fail on unreviewed selected-branch metadata or changed discrete values.

    This guard covers only the three IO branches selected for Figure 6d-l.
    Other historical branches retain their v2 behavior, without a new metadata
    exactness claim. Equality is to a supplied reference, not biological truth.
    """
    if branch not in REVIEWED_BRANCHES:
        return
    if branch in ('IOChRmine', 'IOChRmine_imaging'):
        keys = _EXPERT_KEYS if branch == 'IOChRmine' else _IMAGING_KEYS
        for value in (reference, candidate):
            _record(value, keys)
        fields = keys - {'source_group_labels'}
        for field in sorted(fields):
            _exact(reference[field], candidate[field], field)
        return

    need(type(reference) is list and type(candidate) is list
         and len(reference) == len(candidate), 'Complete source mouse metadata')
    for index, (ref_mouse, got_mouse) in enumerate(zip(reference, candidate)):
        for mouse in (ref_mouse, got_mouse):
            _record(mouse, _MOUSE_KEYS)
            need(type(mouse['days']) is list, 'Complete source day metadata')
        prefix = f'mouse/{index}'
        _exact(ref_mouse['source_mouse_ordinal'],
               got_mouse['source_mouse_ordinal'], prefix + '/source_mouse_ordinal')
        need(len(ref_mouse['days']) == len(got_mouse['days']),
             'Complete source day support')
        for day_index, (ref_day, got_day) in enumerate(
                zip(ref_mouse['days'], got_mouse['days'])):
            for day in (ref_day, got_day):
                _record(day, _DAY_KEYS, _OPTIONAL_MASKS)
            need(set(ref_day) == set(got_day), 'Complete optional source masks')
            day_prefix = f'{prefix}/day/{day_index}'
            for field in ('source_day_ordinal', 'n_movements'):
                _exact(ref_day[field], got_day[field], day_prefix + '/' + field)
            for field in sorted({'completed_mask'} | (_OPTIONAL_MASKS & set(ref_day))):
                _exact(ref_day[field], got_day[field], day_prefix + '/' + field,
                       boolean=True)


def compare(reference, candidate, branch):
    need(branch in BRANCHES, 'Original source branch')
    for tree in (reference, candidate):
        need(type(tree) is dict and 'metadata' in tree, 'Bound native metadata')
    guard_metadata(reference['metadata'], candidate['metadata'], branch)
    result = previous.compare(reference, candidate, branch)
    result['metadata_policy'] = (
        'fig6_source_discrete_metadata_exact_v1' if branch in REVIEWED_BRANCHES
        else 'historical_v2_metadata_unchanged')
    return result


def grade(payload, store):
    """Preserve the private comparison interface; no activation is implied."""
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
