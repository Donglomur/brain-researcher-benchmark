"""Adopted A05 fitting-support-only deterministic permutation, no RNG."""
import hashlib, json
from . import core

def mapping(rows, fit_ids, private_groups, context, grid, cell):
    selected = core.subset(rows, fit_ids)
    core.need(type(private_groups) is dict and set(private_groups) == {r['id'] for r in rows}, 'Full source-private group census')
    groups = {}
    for row in selected:
        g = private_groups[row['id']]
        core.need(type(g) is dict and set(g) == {'person', 'alias', 'session'} and (type(g['person']) is str) and (type(g['alias']) is str) and (type(g['session']) in (int, str)), 'Exact original private person/alias/session')
        key = (g['person'], g['alias'], g['session'])
        groups.setdefault(key, []).extend(range(row['begin'], row['begin'] + row['n_keys']))
    result = []
    for group, indices in groups.items():
        target = sorted(indices)

        def order(i):
            value = ['NEURAL066-inner-fit-shuffle-v1', context['generation'], context['case'], grid, *cell, *group, i]
            raw = json.dumps(value, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
            return (hashlib.sha256(raw).hexdigest(), i)
        source = sorted(target, key=order)
        core.need(len(target) > 1, 'A05 each group must support nontrivial movement; no reroll')
        result.append({'private_group': list(group), 'target_ordinals': target, 'source_ordinals': source})
    expected = set(core.row_indices(selected))
    targets = [i for r in result for i in r['target_ordinals']]
    sources = [i for r in result for i in r['source_ordinals']]
    core.need(any((r['source_ordinals'] != r['target_ordinals'] for r in result)), 'A05 refuses an all-identity permutation; no alternate seed')
    core.need(len(targets) == len(set(targets)) and set(targets) == set(sources) == expected, 'Exact fit-only ordinal bijection')
    return {'schema': 'neural066_inner_shuffle_v1', 'context': context, 'grid_index': grid, 'cell': cell, 'fit_sentences': fit_ids, 'groups': result, 'labels_used': False, 'validation_modified': False}

def apply(features, plan):
    """Only source-owned numerical realm calls this after full reservation."""
    result = features.copy()
    for group in plan['groups']:
        result[group['target_ordinals']] = features[group['source_ordinals']]
    return result
