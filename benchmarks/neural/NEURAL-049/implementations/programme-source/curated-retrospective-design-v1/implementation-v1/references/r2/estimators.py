"""Full SVD ridge and independent frozen-bin/prefix-statistic boosting."""
import math
from .budget import require
from .contracts import numpy


def ridge(z, y, penalty, budget):
    np = numpy()
    n, p = z.shape
    m = min(n, p)
    budget.arrays(8*(4*n*p+4*(n+p)*m+8*m*m+4*p+4*n), 'complete SVD factor/workspace bound',
                  live=8*(6*n*p+6*(n+p)*m+12*m*m+8*p+8*n))
    budget.ops(32*(n*p*m+m**3)+16*p*m, 'full nontruncated SVD ridge')
    u, singular, vt = np.linalg.svd(z, full_matrices=False)
    require(singular.shape == (m,) and bool(np.isfinite(singular).all()), 'complete singular spectrum')
    beta = vt.T @ ((singular/(singular*singular+n*penalty))*(u.T@y))
    require(bool(np.isfinite(beta).all()), 'ridge finite coefficients')
    budget.tick('SVD ridge completed')
    return beta, singular


def freeze_bins(z, budget):
    np = numpy()
    n, p = z.shape
    budget.arrays(8*(n*p+64*p)+(n*p)*8, 'complete frozen thresholds and bin IDs', live=z.nbytes*4+1024*p)
    budget.ops(p*n*(int(math.ceil(math.log2(max(2, n))))+64), 'full quantile bins')
    thresholds = []
    indices = np.empty((n, p), dtype=np.int64)
    for f in range(p):
        budget.tick('freeze training thresholds')
        column = np.sort(z[:, f])
        chosen = sorted(set(float(column[(j*n+63)//64-1]) for j in range(1, 64)
                            if column[(j*n+63)//64-1] < column[-1]))
        thresholds.append(chosen)
        indices[:, f] = np.searchsorted(chosen, z[:, f], side='left')
    return thresholds, indices


def prefix_candidate(rows, residual, bins, thresholds, floor, l2, budget):
    """Bins reduce complete row support, then prefix counts/sums enumerate every split."""
    best = None
    parent_sum = math.fsum(float(residual[r]) for r in rows)
    parent_gain = parent_sum*parent_sum/(len(rows)+l2)
    p = bins.shape[1]
    budget.ops(p*(len(rows)*8+64*12), 'complete prefix split search')
    budget.charge('allocation_bytes', p*64*64, 'histogram/Python scalar allocation bound')
    for f, edges in enumerate(thresholds):
        budget.tick('histogram feature search')
        if not edges:
            continue
        counts = [0]*(len(edges)+1)
        sums = [0.]*(len(edges)+1)
        compensation = [0.]*(len(edges)+1)
        for r in rows:
            b = int(bins[r, f])
            counts[b] += 1
            # Neumaier bin reduction; no imported split routine.
            value = float(residual[r])
            total = sums[b]+value
            compensation[b] += ((sums[b]-total)+value if abs(sums[b]) >= abs(value)
                                else (value-total)+sums[b])
            sums[b] = total
        total_sum = math.fsum(sums[k]+compensation[k] for k in range(len(sums)))
        left_n = 0
        terms = []
        for k in range(len(edges)):
            left_n += counts[k]
            terms.append(sums[k]+compensation[k])
            right_n = len(rows)-left_n
            if left_n < floor or right_n < floor:
                continue
            left_sum = math.fsum(terms)
            right_sum = total_sum-left_sum
            gain = left_sum*left_sum/(left_n+l2)+right_sum*right_sum/(right_n+l2)-parent_gain
            require(math.isfinite(gain), 'nonfinite split gain')
            if gain > 0 and (best is None or (-gain, f, k) < (-best[0], best[1], best[2])):
                best = (gain, f, k)
    return best


def grow_tree(residual, bins, thresholds, max_leaves, l2, budget):
    n, p = bins.shape
    floor = max(2, (n+19)//20)
    budget.charge('allocation_bytes', (n*max_leaves+max_leaves*p*64)*64, 'complete tree row/candidate scalar bound')
    leaves = {'': list(range(n))}
    nodes = {}
    candidates = {}
    while len(leaves) < max_leaves:
        for path, rows in leaves.items():
            if path not in candidates:
                candidates[path] = prefix_candidate(rows, residual, bins, thresholds, floor, l2, budget)
        choices = [(-c[0], c[1], c[2], path) for path, c in candidates.items()
                   if path in leaves and c is not None]
        if not choices:
            break
        _, feature, rank, path = min(choices)
        rows = leaves.pop(path)
        left = [r for r in rows if bins[r, feature] <= rank]
        right = [r for r in rows if bins[r, feature] > rank]
        require(len(left) >= floor and len(right) >= floor, 'tree leaf floor')
        nodes[path] = {'feature': feature, 'threshold_rank': rank}
        leaves[path+'0'], leaves[path+'1'] = left, right
    for path, rows in leaves.items():
        value = math.fsum(float(residual[r]) for r in rows)/(len(rows)+l2)
        require(math.isfinite(value), 'tree leaf finite')
        nodes[path] = {'value': value, 'count': len(rows)}
    return nodes


def tree_values(nodes, thresholds, z, budget):
    np = numpy()
    n = z.shape[0]
    budget.arrays(n*8, 'tree predictions', live=z.nbytes+n*48)
    budget.ops(n*max(1, len(nodes)), 'complete tree traversal bound')
    out = np.empty(n, dtype=np.float64)
    for r in range(n):
        budget.tick('tree prediction row')
        path = ''
        while 'value' not in nodes[path]:
            node = nodes[path]
            f, k = node['feature'], node['threshold_rank']
            path += '0' if z[r, f] <= thresholds[f][k] else '1'
        out[r] = nodes[path]['value']
    return out


def boost(z, y, configuration, budget):
    np = numpy()
    n, p = z.shape
    thresholds, bins = freeze_bins(z, budget)
    initial = math.fsum(float(v) for v in y)/n
    budget.arrays(n*32, 'boost initial/residual vectors', live=z.nbytes*4+n*64+p*4096)
    prediction = np.full(n, initial, dtype=np.float64)
    trees = []
    for iteration in range(configuration['trees']):
        budget.tick('boost round')
        budget.arrays(n*24, 'boost residual and update temporaries', live=z.nbytes*4+n*128+p*4096)
        residual = y-prediction
        tree = grow_tree(residual, bins, thresholds, configuration['leaves'], configuration['l2'], budget)
        prediction += .05*tree_values(tree, thresholds, z, budget)
        trees.append(tree)
    require(bool(np.isfinite(prediction).all()), 'boost finite fitted outputs')
    return {'initial': initial, 'thresholds': thresholds, 'trees': trees, 'learning_rate': .05}


def boost_predict(model, z, budget):
    np = numpy()
    budget.arrays(len(z)*8, 'boost prediction vector', live=z.nbytes*3+len(z)*64)
    out = np.full(len(z), model['initial'], dtype=np.float64)
    for tree in model['trees']:
        budget.arrays(len(z)*16, 'boost inference update', live=z.nbytes*3+len(z)*64)
        out += model['learning_rate']*tree_values(tree, model['thresholds'], z, budget)
    return out
