"""Unthresholded analytic enrichment geometry and four Gao contexts.

Scientific dependencies are imported only inside a separately selected call.
The 48 historical finite-shuffle views are retained separately, not mixed with
these 16 analytic views or counted as independent evidence.
"""
import math
from conditional_kernel import adjusted_rand, enrich, need, pair


def analyse(case, packet, tick=lambda: None):
    import numpy as np
    from scipy.cluster.hierarchy import linkage, fcluster
    from scipy.spatial.distance import pdist
    from scipy.stats import pearsonr
    emats = [enrich(f) for f in case['families']]
    contexts, hierarchy = {}, {}
    for context in packet['contexts']:
        tick()
        key = context['key']
        raw = [emats[context['family']][i] for i in context['indices']]
        undefined = sum(v is None or not math.isfinite(v) for row in raw for v in row)
        state = {'enrichment': raw, 'undefined_cells': undefined, 'geometry': None}
        if undefined == 0 and len(raw) >= 2:
            X = np.asarray(raw, dtype='float64')
            distances = pdist(X, metric='euclidean')
            norms = np.linalg.norm(X, axis=1)
            normalized = np.divide(X, norms[:,None], out=np.zeros_like(X), where=norms[:,None] != 0)
            cosine = normalized @ normalized.T
            Z = linkage(distances, method='ward', optimal_ordering=True)
            grid = list(range(2, min(8, len(raw)//2)))
            state['geometry'] = {'distances': distances.tolist(), 'cosine': cosine.tolist(),
                                 'partitions': {str(k): fcluster(Z,k,'maxclust').tolist() for k in grid}}
        contexts[key] = state
        if context['hierarchy'] is not None:
            # Exactly the source hierarchy-NaN mask; do not drop nonfinite y
            # or infinite hierarchy coordinates to manufacture a correlation.
            keep = [i for i,x in enumerate(context['hierarchy']) if x != 'NaN']
            xs = [context['hierarchy'][i] for i in keep]
            values = []
            for category in range(8):
                ys = [raw[i][category] for i in keep]
                valid = len(xs) >= 2 and all(type(v) in (int,float) and math.isfinite(v) for v in xs+ys)
                valid = valid and len(set(xs)) > 1 and len(set(ys)) > 1
                value = float(pearsonr(xs,ys).statistic) if valid else None
                values.append(value if value is not None and math.isfinite(value) else None)
            hierarchy[key] = values
    need(len(contexts) == 16 and len(hierarchy) == 4, 'complete analytic context roster')
    return {'contexts': contexts, 'hierarchy': hierarchy}


def error_vector(left, right):
    need(len(left) == len(right), 'complete numeric comparison shape')
    bad = sum(a is None or b is None or not math.isfinite(a) or not math.isfinite(b)
              for a,b in zip(left,right))
    mismatch = sum((a is None) != (b is None) for a,b in zip(left,right))
    return {'coordinates':len(left), 'undefined_coordinates':bad, 'undefined_state_mismatches':mismatch,
            'mean_absolute_error':math.fsum(abs(a-b) for a,b in zip(left,right))/len(left)
                if left and not bad else None,
            'max_absolute_error':max(abs(a-b) for a,b in zip(left,right)) if left and not bad else None}


def compare(left, right):
    need(set(left['contexts']) == set(right['contexts']), 'same complete sixteen contexts')
    out = {}
    for key, expected in right['contexts'].items():
        got = left['contexts'][key]
        row = {'enrichment':error_vector([v for r in got['enrichment'] for v in r],
                                        [v for r in expected['enrichment'] for v in r])}
        g, r = got['geometry'], expected['geometry']
        row['geometry_defined'] = {'candidate':g is not None, 'reference':r is not None}
        if g is not None and r is not None:
            need(set(g['partitions']) == set(r['partitions']), 'complete fixed Ward cut grid')
            row.update(distances=error_vector(g['distances'],r['distances']),
                       cosine=error_vector([v for a in g['cosine'] for v in a],[v for a in r['cosine'] for v in a]),
                       partition_adjusted_rand={k:pair(adjusted_rand(g['partitions'][k],r['partitions'][k]))
                                                for k in r['partitions']})
        out[key] = row
    return {'contexts':out, 'hierarchy_errors':{k:error_vector(left['hierarchy'][k],r)
            for k,r in right['hierarchy'].items()}}
