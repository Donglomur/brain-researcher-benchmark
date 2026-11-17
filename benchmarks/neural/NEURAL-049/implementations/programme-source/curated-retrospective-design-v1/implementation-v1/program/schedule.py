"""Complete lazy source-owned graph, with exact reference-only fit reuse."""
from itertools import combinations
from contracts import PEOPLE, ENDPOINTS, CONFIGS, FAMILIES, VIEWS, cells, identity, roster
from core import need


def cases(table):
    roster(table)
    for person in PEOPLE:
        days = [x['day'] for x in table[person]]
        for held in days:
            yield {'person': person, 'held': held, 'training': [x for x in days if x != held],
                   'id': identity(['case', person, held])}


def support(table, person, days):
    rows = {x['day']: x for x in table[person]}
    need(days == sorted(set(days)) and set(days) <= set(rows), 'exact assigned day support')
    return [event for day in days for event in rows[day]['ids']]


def reference_graph(table, selected, cache):
    """Yield all fits and all ordered consumers. Cache never crosses impl/view."""
    need(type(cache) is bool, 'explicit separately qualified cache plan')
    roster(table)
    views = list(VIEWS) + (['NC_D'] if 'D' in selected else [])
    for implementation in ('r1', 'r2'):
        for endpoint in ENDPOINTS:
            for view in views:
                for person in PEOPLE:
                    days = [x['day'] for x in table[person]]
                    for excluded in combinations(days, 2):
                        training = [x for x in days if x not in excluded]
                        for config in CONFIGS:
                            roles = [None] if cache else list(excluded)
                            for role in roles:
                                key = [implementation, endpoint, view, person, list(excluded), config, role]
                                fit = identity(['inner-fit', key])
                                yield {'kind': 'reference_fit', 'id': fit, 'implementation': implementation,
                                       'endpoint': endpoint, 'view': view, 'person': person, 'training': training,
                                       'configuration': config, 'excluded': list(excluded), 'cache_role': role}
                            for outer, validation in (excluded, tuple(reversed(excluded))):
                                role = None if cache else outer
                                fit = identity(['inner-fit', [implementation, endpoint, view, person, list(excluded), config, role]])
                                yield {'kind': 'reference_inner_predict', 'id': identity(['inner-predict', fit, outer, validation]),
                                       'fit': fit, 'implementation': implementation, 'endpoint': endpoint, 'view': view,
                                       'person': person, 'outer': outer, 'query': [validation], 'configuration': config}
                    for held in days:
                        selection = identity(['selection', implementation, endpoint, view, person, held])
                        yield {'kind': 'reference_select', 'id': selection, 'implementation': implementation,
                               'endpoint': endpoint, 'view': view, 'person': person, 'outer': held}
                        for family in FAMILIES:
                            fit = identity(['final-fit', implementation, endpoint, view, person, held, family])
                            yield {'kind': 'reference_final_fit', 'id': fit, 'selection': selection,
                                   'implementation': implementation, 'endpoint': endpoint, 'view': view, 'person': person,
                                   'outer': held, 'training': [x for x in days if x != held], 'family': family}
                            yield {'kind': 'reference_outer_predict', 'id': identity(['outer-predict', fit]), 'fit': fit,
                                   'selection': selection, 'implementation': implementation, 'endpoint': endpoint,
                                   'view': view, 'person': person, 'outer': held, 'query': [held], 'family': family}


def tool_graph(table, selected):
    if 'T1' not in selected:
        return
    for case in cases(table):
        for endpoint in ENDPOINTS:
            for axis in ('training', 'query'):
                yield {'kind': 'tool_bank', 'id': identity(['tool-bank', case['person'], case['held'], endpoint, axis]),
                       'person': case['person'], 'outer': case['held'], 'endpoint': endpoint, 'axis': axis,
                       'query': case['training'] if axis == 'training' else [case['held']],
                       'selection': identity(['selection', 'r1', endpoint, 'NC', case['person'], case['held']]),
                       'in_sample': axis == 'training'}


def actor_graph(table, selected):
    rows = cells(selected)
    for policy in dict.fromkeys(x['policy'] for x in rows):
        selected = next(x for x in rows if x['policy'] == policy)
        yield {'kind': 'global_author', 'id': identity(['author', policy]), 'policy': policy,
               'mode': policy.split('_')[0], 'source_only': True,'view':selected['view'],'tool':selected['tool']}
    for cell in rows:
        for case in cases(table):
            yield {'kind': 'actor_case', 'id': identity(['actor-case', cell['id'], case['person'], case['held']]),
                   'cell': cell, **case, 'case_id': case['id'],
                   'id': identity(['actor-case', cell['id'], case['person'], case['held']])}


def graph(table, selected, cache):
    for job in actor_graph(table, selected):
        if job['kind'] == 'global_author': yield job
    yield from reference_graph(table, selected, cache)
    yield from tool_graph(table, selected)
    for job in actor_graph(table, selected):
        if job['kind'] != 'global_author': yield job


def census(table, selected, cache):
    roster(table)
    e = sum(len(x['ids']) for p in PEOPLE for x in table[p])
    j = sum((len(table[p]) - 1) * sum(len(x['ids']) for x in table[p]) for p in PEOPLE)
    d = 'D' in selected
    # No generation of model results or a reduced scientific schedule.
    return {'people': 12, 'days': 55, 'inner_consumers_per_config': 202, 'unique_inner_training_sets': 101,
            'events': e, 'inner_consumer_events': j, 'candidate_cases': 55 * len(cells(selected)),
            'candidate_scalar_outputs': 3 * e * len(cells(selected)),
            'reference_fit_calls': 2 * 3 * (4 if d else 3) * ((101 if cache else 202) * 25 + 55 * 3),
            'reference_inner_scalar_outputs': (600 if d else 450) * j,
            'reference_outer_scalar_outputs': (72 if d else 54) * e,
            'tool_training_scalar_outputs': 3 * j if 'T1' in selected else 0,
            'tool_query_scalar_outputs': 3 * e if 'T1' in selected else 0,
            'global_author_realizations': 8 if 'T1' in selected else 6,
            'D_policy_bindings': 2 if d else 0, 'cache_selected': cache}
