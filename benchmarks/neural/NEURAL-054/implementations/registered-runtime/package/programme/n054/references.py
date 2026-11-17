"""Fixed accepted scientific kernels. Authored only; NOT imported/executed by inert controls.
Numerical/native equivalence remains G09/G14. No candidate-selected comparator.
"""
import math
from .common import need
from .spec import FAMILIES, DIMS


def _np():
    import numpy as np
    return np


def validate_training(parts, labels):
    np = _np(); y = np.asarray(labels, dtype=float)
    need(y.ndim == 2 and y.shape[1] == 27 and y.shape[0] > 2 and np.isin(y, [0, 1]).all(), '27 binary training labels')
    need(((y.sum(0) > 0) & (y.sum(0) < len(y))).all(), 'Both classes in every training label')
    for name, values in parts.items():
        x = np.asarray(values, dtype=float)
        need(x.shape == (len(y), DIMS[name]) and np.isfinite(x).all(), 'Exact finite family matrix')
    return y


def standardize_fit(parts):
    np = _np()
    from sklearn.preprocessing import StandardScaler
    output = {}; states = {}
    for name, values in parts.items():
        x = np.array(values, dtype=float, copy=True)
        fill = []
        if name == 'ocular':
            need(((x[:, 12:] >= 0) & (x[:, 12:] <= 1)).all(), 'Finite fractions')
            for j in range(12):
                good = x[:, j + 12] > 0
                value = float(np.median(x[good, j])) if good.any() else 0.
                x[~good, j] = value; fill.append(value)
        scaler = StandardScaler().fit(x)
        output[name] = scaler.transform(x)
        states[name] = {'mean': scaler.mean_.tolist(), 'scale': scaler.scale_.tolist(), 'fill': fill}
    return output, states


def standardize_apply(parts, states):
    np = _np(); out = {}
    need(set(parts) == set(states), 'Exact permitted family set')
    for name, values in parts.items():
        x = np.asarray(values, dtype=float).copy()
        need(x.ndim == 2 and x.shape[1] == DIMS[name] and np.isfinite(x).all(), 'Finite query family')
        s = states[name]
        if name == 'ocular':
            need(((x[:, 12:] >= 0) & (x[:, 12:] <= 1)).all(), 'Query finite fractions')
            for j, fill in enumerate(s['fill']): x[x[:, j + 12] <= 0, j] = fill
        out[name] = (x - np.asarray(s['mean'])) / np.asarray(s['scale'])
    return out


def pca_fit(x):
    np = _np()
    from sklearn.decomposition import PCA
    model = PCA(n_components=8, whiten=False, svd_solver='full').fit(x)
    sv = model.singular_values_
    need(len(sv) == 8 and np.isfinite(sv).all() and sv[0] > 0 and sv[7] > sv[0] * 1e-10,
         'Strict PCA8 rank; no reduced-capacity fallback')
    return model.transform(x), {'mean': model.mean_.tolist(), 'components': model.components_.tolist(),
                                'singular_values': sv.tolist()}


def pca_apply(x, state):
    np = _np()
    return (x - np.asarray(state['mean'])) @ np.asarray(state['components']).T


def representation_fit(parts, kind):
    np = _np(); z, scales = standardize_fit(parts)
    state = {'order': list(parts), 'scales': scales, 'kind': kind}
    if kind == 'raw':
        return np.concatenate(list(z.values()), axis=1), state
    if kind == 'total8':
        weighted = [z[n] / math.sqrt(DIMS[n] * len(z)) for n in z]
        x, pca = pca_fit(np.concatenate(weighted, axis=1)); state['pca'] = pca
        return x, state
    need(kind == 'block8', 'Representation kind')
    from sklearn.preprocessing import StandardScaler
    blocks = []; state['blocks'] = {}
    for n in z:
        block, pca = pca_fit(z[n]); scaler = StandardScaler().fit(block)
        blocks.append(scaler.transform(block) / math.sqrt(8))
        state['blocks'][n] = {'pca': pca, 'mean': scaler.mean_.tolist(), 'scale': scaler.scale_.tolist()}
    return np.concatenate(blocks, axis=1), state


def representation_apply(parts, state):
    np = _np(); z = standardize_apply(parts, state['scales'])
    order = state['order']
    if state['kind'] == 'raw': return np.concatenate([z[n] for n in order], axis=1)
    if state['kind'] == 'total8':
        x = np.concatenate([z[n] / math.sqrt(DIMS[n] * len(z)) for n in order], axis=1)
        return pca_apply(x, state['pca'])
    blocks = []
    for n in order:
        b = state['blocks'][n]
        blocks.append((pca_apply(z[n], b['pca']) - np.asarray(b['mean'])) / np.asarray(b['scale']) / math.sqrt(8))
    return np.concatenate(blocks, axis=1)


def lda_fit(x, y, ridge, direct=False):
    """Exact accepted unbiased pooled covariance, equal priors, rank-one correction.
    Direct mode is an explicit separately budgeted fallback/parity route, never silent.
    """
    np = _np()
    from scipy.linalg import cho_factor, cho_solve
    n, d = x.shape; centered = x - x.mean(0); g = centered.T @ centered
    need(n > 2 and np.isfinite(g).all(), 'Finite covariance')
    a = g / (n - 2) + ridge * np.eye(d)
    need(np.allclose(a, a.T, rtol=1e-12, atol=1e-12), 'Symmetric total covariance')
    need(np.linalg.cond(a) <= 1e12, 'LDA condition bound; no unchecked repair')
    factor = cho_factor(a, lower=True, check_finite=True)
    weights = []; intercepts = []; diagnostics = []
    for j in range(27):
        yes = y[:, j] == 1; n1 = int(yes.sum()); n0 = n - n1
        need(n0 > 0 and n1 > 0, 'LDA class support')
        mu1 = x[yes].mean(0); mu0 = x[~yes].mean(0); delta = mu1 - mu0
        if direct:
            # Independent class-centered formation, not the common-factor formula.
            x0 = x[~yes] - mu0; x1 = x[yes] - mu1
            sw = (x0.T @ x0 + x1.T @ x1) / (n - 2) + ridge * np.eye(d)
            w = cho_solve(cho_factor(sw, lower=True), delta)
            denominator = None; residual = np.linalg.norm(sw @ w - delta)
            bound = 1e-10 * (np.linalg.norm(sw) * np.linalg.norm(w) + np.linalg.norm(delta) + 1)
        else:
            v = cho_solve(factor, delta, check_finite=True)
            residual = np.linalg.norm(a @ v - delta)
            bound = 1e-10 * (np.linalg.norm(a) * np.linalg.norm(v) + np.linalg.norm(delta) + 1)
            kappa = n0 * n1 / (n * (n - 2))
            denominator = float(1 - kappa * (delta @ v))
            need(math.isfinite(denominator) and denominator > 1e-12, 'Unstable/nonpositive rank-one denominator')
            w = v / denominator
        need(np.isfinite(w).all() and residual <= bound, 'LDA solve residual')
        weights.append(w.tolist()); intercepts.append(float(-.5 * ((mu1 + mu0) @ w)))
        diagnostics.append({'n0': n0, 'n1': n1, 'denominator': denominator, 'residual': float(residual)})
    return {'weights': weights, 'intercepts': intercepts, 'ridge': ridge, 'equal_priors': [.5, .5],
            'solve': 'direct' if direct else 'common_factor_rank_one', 'diagnostics': diagnostics}


def family_preparation(name, values):
    np = _np()
    from sklearn.preprocessing import StandardScaler
    z, scales = standardize_fit({name: values})
    pc, pca = pca_fit(z[name]); scaler = StandardScaler().fit(pc)
    return {'name': name, 'scale': scales[name], 'pca': pca,
            'pc_mean': scaler.mean_.tolist(), 'pc_scale': scaler.scale_.tolist()}


def prepared_representation(parts, kind, prepared):
    np = _np(); need(set(parts) == set(prepared), 'Complete independent family preparation')
    scales = {name: prepared[name]['scale'] for name in parts}
    z = standardize_apply(parts, scales)
    state = {'order': list(parts), 'scales': scales, 'kind': kind}
    if kind == 'raw': return np.concatenate(list(z.values()), axis=1), state
    if kind == 'total8':
        x, pca = pca_fit(np.concatenate([z[n] / math.sqrt(DIMS[n] * len(z)) for n in z], axis=1))
        state['pca'] = pca; return x, state
    state['blocks'] = {}; blocks = []
    for n in z:
        p = prepared[n]; b = {'pca': p['pca'], 'mean': p['pc_mean'], 'scale': p['pc_scale']}
        state['blocks'][n] = b
        blocks.append((pca_apply(z[n], b['pca']) - np.asarray(b['mean'])) / np.asarray(b['scale']) / math.sqrt(8))
    return np.concatenate(blocks, axis=1), state


def fit(parts, labels, family, solve='common', prepared=None):
    np = _np(); y = validate_training(parts, labels)
    need(family in ('R0', 'R1', 'R2', 'R4', 'R5'), 'Fixed reference family')
    state = {'family': family, 'training_rows': len(y), 'classes': 27, 'families': list(parts)}
    if family == 'R4': state['probabilities'] = [.5] * 27; return state
    if family == 'R5': state['probabilities'] = ((y.sum(0) + 1) / (len(y) + 2)).tolist(); return state
    kind = {'R0': 'total8', 'R1': 'raw', 'R2': 'block8'}[family]
    x, representation = (prepared_representation(parts, kind, prepared) if prepared is not None else representation_fit(parts, kind)); state['representation'] = representation
    if family == 'R0':
        from sklearn.linear_model import LogisticRegression
        models = []
        for j in range(27):
            model = LogisticRegression(C=1., class_weight='balanced', solver='liblinear', max_iter=2000,
                                       tol=1e-4, random_state=0).fit(x, y[:, j])
            need(int(model.n_iter_.max()) < 2000, 'R0 convergence cap reached')
            models.append({'coef': model.coef_[0].tolist(), 'intercept': float(model.intercept_[0]),
                           'iterations': int(model.n_iter_.max())})
        state['models'] = models
    else:
        need(solve in ('common', 'direct'), 'Prospectively selected LDA solve')
        state['lda'] = lda_fit(x, y, .1 if family == 'R1' else .0125, direct=solve == 'direct')
    return state


def predict(parts, state):
    np = _np()
    from scipy.special import expit
    n = len(next(iter(parts.values())))
    need(n == 1, 'One-query inference')
    if state['family'] in ('R4', 'R5'): return state['probabilities']
    x = representation_apply(parts, state['representation'])
    if state['family'] == 'R0':
        logits = [float(x[0] @ np.asarray(m['coef']) + m['intercept']) for m in state['models']]
    else:
        lda = state['lda']; logits = x @ np.asarray(lda['weights']).T + np.asarray(lda['intercepts'])
    return expit(np.asarray(logits).reshape(27)).tolist()


def summary_fit(parts, labels):
    np = _np(); y = validate_training(parts, labels)
    x, representation = representation_fit(parts, 'total8')
    classes = []
    for j in range(27):
        pair = []
        for c in (0, 1):
            sub = x[y[:, j] == c]
            pair.append({'count': len(sub), 'mean': [format(float(v), '.17g') for v in sub.mean(0)],
                         'variance': [format(float(v), '.17g') for v in sub.var(0, ddof=0)]})
        classes.append(pair)
    return {'representation': representation, 'summary': classes}


def summary_query(parts, state):
    x = representation_apply(parts, state['representation'])
    need(x.shape == (1, 8), 'One PCA8 query')
    return {'classes': state['summary'], 'query': [format(float(v), '.17g') for v in x[0]]}


def summary_predict(payload, family):
    np = _np()
    from scipy.special import expit
    need(family in ('DG_DIAGONAL_GAUSSIAN', 'DC_NEAREST_CENTROID'), 'Summary control family')
    query = np.asarray([float(v) for v in payload['query']]); need(query.shape == (8,), 'PCA8 query')
    out = []
    for pair in payload['classes']:
        scores = []
        for c in pair:
            mu = np.asarray([float(v) for v in c['mean']]); variance = np.asarray([float(v) for v in c['variance']])
            need(mu.shape == variance.shape == (8,) and c['count'] > 0 and (variance >= 0).all(), 'Complete summary')
            if family == 'DG_DIAGONAL_GAUSSIAN':
                v = np.maximum(variance, 1e-8)
                scores.append(float(-.5 * (np.log(2 * np.pi * v) + (query - mu) ** 2 / v).sum()))
            else:
                scores.append(float(-np.linalg.norm(query - mu)))  # Euclidean, temperature1, not squared distance.
        out.append(float(expit(scores[1] - scores[0])))
    return out
