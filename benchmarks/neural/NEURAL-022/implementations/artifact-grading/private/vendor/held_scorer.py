"""Private scalar scorer. Source-only; commit/release enforcement belongs to runtime."""
import math

METHODS = ('active_neural', 'passive_neural', 'active_mean', 'passive_mean',
           'active_direction', 'passive_direction', 'zero')
DIRECTIONS = tuple(range(0, 360, 45))


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def vectors(rows, expected_ids):
    need(type(rows) is list and len(rows) == 92, 'Full92 rows; no denominator reduction')
    need(all(type(row) is dict and set(row) == {'id', 'velocity'} for row in rows),
         'Exact prediction row schema')
    need([row['id'] for row in rows] == expected_ids and len(set(expected_ids)) == 92,
         'Exact unique ordered opaque IDs; no missing, extra, duplicate or reordered rows')
    values = [row['velocity'] for row in rows]
    need(all(type(v) is list and len(v) == 2 and all(type(a) in (int, float)
             and math.isfinite(a) for a in v) for v in values), 'Finite two-component velocities')
    return values


def score(private_manifest, truth, committed_predictions):
    """Caller must verify every immutable prediction commitment before this call."""
    need(type(private_manifest) is list and len(private_manifest) == 92,
         'Full fixed private query manifest')
    ids = [r['id'] for r in private_manifest]
    modes = [r['mode'] for r in private_manifest]
    directions = [r['direction'] for r in private_manifest]
    need(all(type(i) is str and 1 <= len(i) <= 128 for i in ids)
         and modes.count('passive') == 40 and modes.count('active') == 52
         and all(type(d) is int and d in DIRECTIONS for d in directions),
         'Exact40 passive primary and52 active secondary contexts')
    need(set(committed_predictions) == set(METHODS), 'All seven references required before scoring')
    target = vectors(truth, ids)
    predictions = {name: vectors(committed_predictions[name], ids) for name in METHODS}
    loss = {name: [math.fsum((p[j] - y[j]) ** 2 for j in range(2))
                   for p, y in zip(predictions[name], target)] for name in METHODS}
    need(all(math.isfinite(v) for row in loss.values() for v in row), 'Finite squared losses')
    aggregates = {}
    paired = {}
    for mode in ('passive', 'active'):
        selected = [i for i, m in enumerate(modes) if m == mode]
        aggregates[mode] = {name: math.fsum(loss[name][i] for i in selected) / len(selected)
                            for name in METHODS}
        paired[mode] = [loss['active_neural'][i] - loss['passive_neural'][i] for i in selected]
    by_direction = []
    for mode in ('passive', 'active'):
        for direction in DIRECTIONS:
            selected = [i for i, (m, d) in enumerate(zip(modes, directions))
                        if m == mode and d == direction]
            need(bool(selected), 'All declared direction strata retained')
            by_direction.append({'mode': mode, 'direction': direction, 'trials': len(selected),
                'losses': {name: math.fsum(loss[name][i] for i in selected) / len(selected)
                           for name in METHODS}})
    primary = math.fsum(paired['passive']) / 40
    return {'status': 'complete_fixed_query_scoring', 'units': '(m/s)^2',
            'primary_active_minus_passive_neural_loss': primary,
            'positive_primary_means': 'active-to-passive transfer cost',
            'losses': aggregates, 'direction_strata': by_direction,
            'private_paired_trial_differences': paired,
            'passive_neural_minus_passive_direction':
                aggregates['passive']['passive_neural'] - aggregates['passive']['passive_direction'],
            'active_neural_minus_passive_direction_on_passive':
                aggregates['passive']['active_neural'] - aggregates['passive']['passive_direction'],
            'independent_animals': 1, 'animal_level_inference': False}
