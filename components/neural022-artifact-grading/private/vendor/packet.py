"""Trusted array projection only; no training, refitting, or new reference prediction."""
import re
import numpy as np

METHODS = ('active_neural', 'passive_neural', 'active_mean', 'passive_mean',
           'active_direction', 'passive_direction', 'zero')


def need(ok, why):
    if not ok:
        raise ValueError(why)


def identifiers(x, n):
    need(x.shape == (n,) and x.dtype == np.dtype('<U24') and len(set(x.tolist())) == n
         and all(re.fullmatch('[a-f0-9]{24}', v) for v in x.tolist()), 'Exact unique opaque identities')


def counts(x, n):
    need(x.shape == (n, 390) and x.dtype == np.dtype('<i8') and (x >= 0).all(),
         'All65 units by six bins as nonnegative raw integer counts')


def velocity(x, n):
    need(x.shape == (n, 2) and x.dtype == np.dtype('<f8') and np.isfinite(x).all(),
         'Complete finite two-component nominal velocity')


def sanitize(active, query, target, references):
    need(set(active) == {'ids', 'counts', 'velocity', 'source_rows', 'directions'}
         and set(query) == {'ids', 'counts', 'directions', 'modes'}
         and set(target) == {'ids', 'velocity'} and set(references) == {'ids', *METHODS},
         'Exact original fitted-output schemas; no additional source channel')
    identifiers(active['ids'], 141); identifiers(query['ids'], 92)
    identifiers(target['ids'], 92); identifiers(references['ids'], 92)
    need(not set(active['ids'].tolist()) & set(query['ids'].tolist()), 'Disjoint official train/query identities')
    need(np.array_equal(query['ids'], target['ids']) and np.array_equal(query['ids'], references['ids']),
         'Saved query/target/all-reference identities agree in order')
    counts(active['counts'], 141); counts(query['counts'], 92)
    velocity(active['velocity'], 141); velocity(target['velocity'], 92)
    need(active['source_rows'].shape == (141,) and active['source_rows'].dtype == np.dtype('<i8')
         and (np.diff(active['source_rows']) > 0).all(), 'Original active chronology retained privately')
    for values, n in ((active['directions'], 141), (query['directions'], 92)):
        need(values.shape == (n,) and values.dtype == np.dtype('<i8')
             and set(values.tolist()) == set(range(0, 360, 45)), 'All eight commanded directions')
    need(query['modes'].shape == (92,) and query['modes'].dtype == np.dtype('<U7')
         and set(query['modes'].tolist()) == {'active', 'passive'}, 'Declared query modes')
    rows = [{'id': i, 'mode': m, 'direction': int(d)} for i, m, d in
            zip(query['ids'].tolist(), query['modes'].tolist(), query['directions'].tolist())]
    for mode, n in (('active', 52), ('passive', 40)):
        selected = [r for r in rows if r['mode'] == mode]
        need(len(selected) == n and {r['direction'] for r in selected} == set(range(0, 360, 45)),
             'Full92 query roster; no subset or direction drop')
    for name in METHODS:
        velocity(references[name], 92)
    # No source-row/event coordinates, passive training data, support masks or target summaries.
    public_training = {k: active[k].copy() for k in ('ids', 'counts', 'velocity', 'directions')}
    public_queries = {k: query[k].copy() for k in ('ids', 'counts', 'directions', 'modes')}
    private = {'ids': target['ids'].copy(), 'velocity': target['velocity'].copy(),
               **{m: references[m].copy() for m in METHODS}}
    return public_training, public_queries, {'schema': 'neural022_public_cases_v1', 'cases': rows}, private


def private_lists(value):
    need(set(value) == {'ids', 'velocity', *METHODS}, 'Exact sealed private output members')
    identifiers(value['ids'], 92); velocity(value['velocity'], 92)
    for m in METHODS:
        velocity(value[m], 92)
    return {'ids': value['ids'].tolist(), 'velocity': value['velocity'].tolist(),
            'references': {m: value[m].tolist() for m in METHODS}}
