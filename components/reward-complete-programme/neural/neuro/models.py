"""Independent small dense matched spline/ridge reference; no source-trained state.

Implementation exercise is permitted only on invented controls in this phase.
Actual fitting, adequacy of the model family and solver qualification remain gates.
"""
import math
from collections import defaultdict
from .base import finite, require, ContractError

GRID = (3, 5, 7)
PENALTIES = (1e-4, 1e-2, 1., 1e2, 1e4)


def mean(x):
    require(bool(x), 'empty_mean')
    return math.fsum(x) / len(x)


def animal_weights(rows):
    counts = defaultdict(float)
    for row in rows:
        weight = finite(row.get('weight', 1.))
        require(weight > 0, 'positive_training_weight')
        counts[row['animal']] += weight
    require(counts, 'no_training_animals')
    return [r.get('weight', 1.) / (len(counts) * counts[r['animal']]) for r in rows]


def solve(matrix, rhs):
    n = len(rhs)
    a = [list(row) + [rhs[i]] for i, row in enumerate(matrix)]
    scale = max(abs(v) for row in matrix for v in row)
    require(scale > 0, 'zero_normal_equations')
    tolerance = math.ulp(scale) * max(1, n) * 8
    for col in range(n):
        pivot = max(range(col, n), key=lambda i: abs(a[i][col]))
        require(abs(a[pivot][col]) > tolerance, 'singular_normal_equations')
        a[col], a[pivot] = a[pivot], a[col]
        factor = a[col][col]
        a[col] = [v / factor for v in a[col]]
        for row in range(n):
            if row == col: continue
            factor = a[row][col]
            a[row] = [x - factor * y for x, y in zip(a[row], a[col])]
    return [finite(row[-1], 'coefficient') for row in a]


def quantile(values, p):
    ordered = sorted(values)
    at = p * (len(ordered) - 1)
    left = int(at)
    frac = at - left
    return ordered[left] * (1 - frac) + ordered[min(left + 1, len(ordered) - 1)] * frac


def spline_knots(values, dimensions):
    require(len(set(values)) >= dimensions + 1, 'unsupported_spline_dimension')
    knots = [quantile(values, i / dimensions) for i in range(dimensions + 1)]
    require(all(b > a for a, b in zip(knots, knots[1:])), 'duplicate_spline_knots')
    return knots


def spline(x, knots):
    """Natural cubic basis: one linear plus m-2 constrained cubic terms."""
    last, penultimate = knots[-1], knots[-2]
    def d(k):
        return (max(x - k, 0.) ** 3 - max(x - last, 0.) ** 3) / (last - k)
    return [x] + [d(k) - d(penultimate) for k in knots[:-2]]


def build_encoder(rows, axes, dimension, nuisance):
    require(rows, 'empty_training')
    allowed = set.intersection(*(set(r['features']) for r in rows))
    require(set(axes) <= allowed, 'missing_axis_no_backfill')
    nums = [x for x in ('day', 'preceding_interval', 'baseline_lick_rate',
                        'concurrent_lick_rate') if x in allowed and x in nuisance]
    nums += sorted(x for x in allowed & set(nuisance) if x.startswith('protocol_'))
    cats = {x: sorted({str(r['features'][x]) for r in rows})
            for x in ('condition', 'sex', 'hardware') if x in allowed and x in nuisance}
    knots = {}
    for axis in axes:
        values = []
        for r in rows:
            x = finite(r['features'][axis], axis)
            require(axis == 'tau' or x >= 0, 'negative_E_N')
            values.append(x if axis == 'tau' else math.log1p(x))
        knots[axis] = spline_knots(values, dimension)
    imputation = {}
    weights = animal_weights(rows)
    for name in nums:
        observed = [(r['features'][name], w) for r, w in zip(rows, weights)
                    if r['features'][name] is not None]
        imputation[name] = (math.fsum(finite(v) * w for v, w in observed) /
                            math.fsum(w for _, w in observed)) if observed else 0.
    return {'axes': list(axes), 'dimension': dimension, 'numeric': nums, 'imputation': imputation,
            'categorical': cats, 'knots': knots}


def raw_features(row, encoder):
    f = row['features']
    result = []
    for key in encoder['numeric']:
        missing = f[key] is None
        result += [encoder['imputation'][key] if missing else finite(f[key]), float(missing)]
    for key, levels in encoder['categorical'].items():
        # Reference category = lexicographic first training level; unseen=allzero.
        result += [float(str(f[key]) == level) for level in levels[1:]]
    for axis in encoder['axes']:
        require(axis in f, 'missing_query_axis')
        value = finite(f[axis])
        require(axis == 'tau' or value >= 0, 'negative_query_axis')
        result += spline(value if axis == 'tau' else math.log1p(value), encoder['knots'][axis])
    return result


def fit(rows, axes=(), dimension=3, penalty=1., nuisance=()):
    require(all('target' in r for r in rows), 'missing_training_response')
    encoder = build_encoder(rows, axes, dimension, nuisance)
    weights = animal_weights(rows)
    raw = [raw_features(r, encoder) for r in rows]
    width = len(raw[0])
    centers = [math.fsum(w * r[j] for w, r in zip(weights, raw)) for j in range(width)]
    scales = [math.sqrt(max(0., math.fsum(w * (r[j] - centers[j]) ** 2
                                        for w, r in zip(weights, raw)))) for j in range(width)]
    design = [[1.] + [(v - mu) / sd if sd else 0.
                      for v, mu, sd in zip(r, centers, scales)] for r in raw]
    ys = [finite(r['target']) for r in rows]
    center_y = math.fsum(w * y for w, y in zip(weights, ys))
    scale_y = math.sqrt(math.fsum(w * (y - center_y) ** 2 for w, y in zip(weights, ys))) or 1.
    yy = [(y - center_y) / scale_y for y in ys]
    dim = width + 1
    gram = [[math.fsum(w * r[i] * r[j] for w, r in zip(weights, design))
             + (penalty if i == j and i else 0.) for j in range(dim)] for i in range(dim)]
    rhs = [math.fsum(w * r[i] * y for w, r, y in zip(weights, design, yy)) for i in range(dim)]
    coefficients = solve(gram, rhs)
    return {'schema': 'matched_neural_spline_model_v1', 'encoder': encoder,
            'centers': centers, 'scales': scales, 'coefficients': coefficients,
            'target_center': center_y, 'target_scale': scale_y, 'penalty': penalty,
            'training_animals': sorted({r['animal'] for r in rows})}


def predict(model, rows):
    predictions = {}
    for row in rows:
        raw = raw_features(row, model['encoder'])
        xx = [1.] + [(x - mu) / sd if sd else 0.
                      for x, mu, sd in zip(raw, model['centers'], model['scales'])]
        value = model['target_center'] + model['target_scale'] * math.fsum(
            x * b for x, b in zip(xx, model['coefficients']))
        predictions[row['id']] = finite(value, 'prediction')
    return predictions


def loss(rows, predictions):
    require(set(predictions) == {r['id'] for r in rows}, 'loss_identity')
    grouped = defaultdict(list)
    for r in rows:
        grouped[r['animal']].append((finite(predictions[r['id']]) - finite(r['target'])) ** 2)
    by_animal = {a: finite(mean(x)) for a, x in grouped.items()}
    return mean(list(by_animal.values())), by_animal


def select_pair(rows, nuisance, grid=GRID, penalties=PENALTIES):
    animals = sorted({r['animal'] for r in rows})
    require(len(animals) >= 2, 'inner_animal_validation_unsupported')
    attempts = []
    for dim in grid:
        for penalty in penalties:
            errors = []
            try:
                for animal in animals:
                    train = [r for r in rows if r['animal'] != animal]
                    query = [r for r in rows if r['animal'] == animal]
                    for axis in ('E', 'N'):
                        model = fit(train, (axis,), dim, penalty, nuisance)
                        errors.append(loss(query, predict(model, query))[0])
                attempts.append({'dimension': dim, 'penalty': penalty, 'loss': mean(errors),
                                 'status': 'valid'})
            except (ContractError, OverflowError, ArithmeticError) as error:
                attempts.append({'dimension': dim, 'penalty': penalty, 'status': 'unsupported',
                                 'reason': str(error)})
    valid = [x for x in attempts if x['status'] == 'valid']
    require(valid, 'no_supported_matched_spline_configuration')
    selected = min(valid, key=lambda x: (x['loss'], x['dimension'], -x['penalty']))
    return selected, attempts


def rank_diagnostics(rows, nuisance):
    """Weighted orthogonal projections; exact rank test, not a biological cutoff."""
    require(all('E' in r['features'] and 'N' in r['features'] for r in rows),
            'joint_identifiability_missing_axis')
    enc = build_encoder(rows, (), 3, nuisance)
    weights = animal_weights(rows)
    raw = [[1.] + raw_features(r, enc) for r in rows]
    def standardized(values, intercept=False):
        center = 0. if intercept else math.fsum(w * v for w, v in zip(weights, values))
        scale = 1. if intercept else math.sqrt(math.fsum(w * (v - center) ** 2
                                                         for w, v in zip(weights, values)))
        return [math.sqrt(w) * (v - center) / scale if scale else 0.
                for w, v in zip(weights, values)]
    columns = [standardized([r[j] for r in raw], j == 0) for j in range(len(raw[0]))]
    E = standardized([math.log1p(finite(r['features']['E'])) for r in rows])
    N = standardized([math.log1p(finite(r['features']['N'])) for r in rows])
    def basis(cols):
        out = []
        norms = []
        for column in cols:
            v = list(column)
            original = math.sqrt(math.fsum(x * x for x in v))
            for _ in range(2):
                for b in out:
                    projection = math.fsum(x * y for x, y in zip(v, b))
                    v = [x - projection * y for x, y in zip(v, b)]
            norm = math.sqrt(math.fsum(x * x for x in v))
            tolerance = 64 * math.ulp(max(original, 1.)) * max(len(rows), len(cols))
            norms.append({'original': original, 'residual': norm, 'tolerance': tolerance})
            if norm > tolerance: out.append([x / norm for x in v])
        return out, norms
    z, _ = basis(columns)
    zn, _ = basis(columns + [N])
    ze, _ = basis(columns + [E])
    all_basis, diagnostics = basis(columns + [E, N])
    independent = len(all_basis) == len(z) + 2
    def residual(column, orthogonal):
        v = list(column)
        for _ in range(2):
            for b in orthogonal:
                projection = math.fsum(x * y for x, y in zip(v, b))
                v = [x - projection * y for x, y in zip(v, b)]
        return math.sqrt(math.fsum(x * x for x in v))
    # Singular values of the weighted covariate matrix via symmetric Jacobi rotations.
    cols = columns + [E, N]
    gram = [[math.fsum(x * y for x, y in zip(a, b)) for b in cols] for a in cols]
    n = len(gram)
    converged = False
    for _ in range(100 * max(n * n, 1)):
        if n < 2:
            converged = True; break
        i, j = max(((i, j) for i in range(n) for j in range(i + 1, n)),
                   key=lambda ij: abs(gram[ij[0]][ij[1]]))
        off = gram[i][j]
        scale = max(abs(gram[k][k]) for k in range(n))
        if abs(off) <= 64 * math.ulp(max(scale, 1.)) * n:
            converged = True; break
        angle = .5 * math.atan2(2 * off, gram[j][j] - gram[i][i])
        cs, sn = math.cos(angle), math.sin(angle)
        aa, bb = gram[i][i], gram[j][j]
        gram[i][i] = cs * cs * aa - 2 * cs * sn * off + sn * sn * bb
        gram[j][j] = sn * sn * aa + 2 * cs * sn * off + cs * cs * bb
        gram[i][j] = gram[j][i] = 0.
        for k in range(n):
            if k in (i, j): continue
            x, y = gram[k][i], gram[k][j]
            gram[k][i] = gram[i][k] = cs * x - sn * y
            gram[k][j] = gram[j][k] = sn * x + cs * y
    singular_values = sorted([math.sqrt(max(0., gram[i][i])) for i in range(n)], reverse=True)
    return {'rank_Z': len(z), 'rank_Z_E': len(ze), 'rank_Z_N': len(zn),
            'matrix_scaling': 'equal_animal_weighted_center_unit_variance_nonintercept',
            'rank_Z_E_N': len(all_basis), 'column_residual_norms': diagnostics,
            'weighted_design_singular_values': singular_values, 'spectral_solver_converged': converged,
            'residual_E_after_Z_N': residual(E, zn), 'residual_N_after_Z_E': residual(N, ze),
            'status': 'numerically_independent_not_biologically_qualified' if independent
                      else 'not_identifiable',
            'practical_estimability': 'requires_independent_precision_power_and_overlap_qualification'}


def fit_comparison(rows, model_names, nuisance, grid=GRID, penalties=PENALTIES):
    allowed = set(model_names)
    require(allowed <= {'M0', 'ME', 'MN', 'MEN'}, 'model_names')
    # Outcome-independent audit is performed before any model/search sees a response.
    diagnostics = (rank_diagnostics(rows, nuisance) if {'ME', 'MN'} <= allowed else
                   {'status': 'not_assessable_missing_axis'})
    axes_for = {'M0': (), 'ME': ('E',), 'MN': ('N',), 'MEN': ('E', 'N')}
    if {'ME', 'MN'} <= allowed:
        selected, attempts = select_pair(rows, nuisance, grid, penalties)
    else:
        axis = 'E' if 'ME' in allowed else 'N' if 'MN' in allowed else None
        if axis is None:
            selected, attempts = {'dimension': 3, 'penalty': 1.}, []
        else:
            # Single-axis control selects only its admissible model, never a missing comparator.
            trials = []
            for dimension in grid:
                for penalty in penalties:
                    values = []
                    try:
                        for animal in sorted({r['animal'] for r in rows}):
                            tr = [r for r in rows if r['animal'] != animal]
                            va = [r for r in rows if r['animal'] == animal]
                            mod = fit(tr, (axis,), dimension, penalty, nuisance)
                            values.append(loss(va, predict(mod, va))[0])
                        trials.append({'dimension': dimension, 'penalty': penalty,
                                       'loss': mean(values), 'status': 'valid'})
                    except (ContractError, ArithmeticError) as error:
                        trials.append({'dimension': dimension, 'penalty': penalty,
                                       'status': 'unsupported', 'reason': str(error)})
            valid = [t for t in trials if t['status'] == 'valid']
            require(valid, 'unsupported_single_axis_reference')
            selected = min(valid, key=lambda t: (t['loss'], t['dimension'], -t['penalty']))
            attempts = trials
    models = {name: fit(rows, axes_for[name], selected['dimension'], selected['penalty'], nuisance)
              for name in model_names}
    joint_trials = []
    sensitivity = {}
    if 'MEN' in allowed:
        for dimension in grid:
            for penalty in penalties:
                try:
                    values = []
                    for animal in sorted({r['animal'] for r in rows}):
                        tr = [r for r in rows if r['animal'] != animal]
                        va = [r for r in rows if r['animal'] == animal]
                        mod = fit(tr, ('E', 'N'), dimension, penalty, nuisance)
                        values.append(loss(va, predict(mod, va))[0])
                    joint_trials.append({'dimension': dimension, 'penalty': penalty,
                                         'loss': mean(values), 'status': 'valid'})
                except (ContractError, ArithmeticError) as error:
                    joint_trials.append({'dimension': dimension, 'penalty': penalty,
                                         'status': 'unsupported', 'reason': str(error)})
        valid = [x for x in joint_trials if x['status'] == 'valid']
        require(valid, 'independently_tuned_joint_model_unsupported')
        joint = min(valid, key=lambda t: (t['loss'], t['dimension'], -t['penalty']))
        sensitivity['MEN_independently_tuned'] = fit(rows, ('E', 'N'), joint['dimension'],
                                                    joint['penalty'], nuisance)
    return {'models': models, 'selected': selected, 'inner_validation': attempts,
            'sensitivity_models': sensitivity, 'joint_inner_validation': joint_trials,
            'identifiability': diagnostics, 'covariate_support': covariate_support(rows),
            'scientific_qualification': False}


def covariate_support(rows):
    """Raw within-group joint support; correlations never become arbitrary pass gates."""
    result = {}
    for grouping in ('condition', 'animal', 'session'):
        grouped = defaultdict(list)
        for row in rows: grouped[row.get(grouping, 'unavailable')].append(row)
        records = {}
        for key, group in grouped.items():
            if not all(r['features'].get('E') is not None and r['features'].get('N') is not None for r in group):
                records[key] = {'status': 'missing_axis', 'rows': len(group)}; continue
            e = [finite(r['features']['E']) for r in group]
            n = [finite(r['features']['N']) for r in group]
            ec, nc = mean(e), mean(n)
            vee = math.fsum((x - ec) ** 2 for x in e)
            vnn = math.fsum((x - nc) ** 2 for x in n)
            cross = math.fsum((x - ec) * (y - nc) for x, y in zip(e, n))
            records[key] = {'rows': len(group), 'E_range': [min(e), max(e)],
                            'N_range': [min(n), max(n)], 'slope_N_on_E': cross / vee if vee else None,
                            'correlation': cross / math.sqrt(vee * vnn) if vee and vnn else None,
                            'status': 'descriptive_covariates_not_estimability_qualification'}
        result[grouping] = records
    return result


def overlap(training, query):
    result = {}
    for axis in ('E', 'N'):
        if not all(axis in r['features'] for r in training + query):
            result[axis] = {'status': 'missing_axis'}; continue
        values = [finite(r['features'][axis]) for r in training]
        lo, hi = min(values), max(values)
        result[axis] = {'training_min': lo, 'training_max': hi,
                        'query_outside_count': sum(not lo <= r['features'][axis] <= hi for r in query),
                        'query_count': len(query)}
    return result


def audit_models(public, artifacts, return_evidence=False):
    """Recompute fixed mandatory comparison from permitted labels only, before targets.

    This source audit prevents degrading MN to enlarge Delta. It is not an
    independent scientific validation of the solver; that qualification stays open.
    """
    from .contracts import available_models
    from .base import digest
    names = available_models(public['cell_id'])
    if not names:
        require(set(artifacts) == {'P'}, 'prior_model_artifact')
        require(artifacts['P']['schema'] == 'unfitted_prior_v1' and
                artifacts['P']['training_labels_seen'] is False, 'prior_training_backfill')
        finite(artifacts['P']['constant'])
        predictions = {'P': {r['id']: artifacts['P']['constant'] for r in public['query']}}
        evidence = {'model_class': 'unfitted_prior', 'identifiability': {'status': 'no_neural_training_evidence'},
                    'sensitivity_predictions': {}, 'scientific_qualification': False}
        return (predictions, evidence) if return_evidence else predictions
    nuisance = set.intersection(*(set(r['features']) for r in public['training'])) - {'E', 'N'}
    expected = fit_comparison(public['training'], names, nuisance)
    require(set(artifacts) == set(names), 'audited_model_names')
    for name in names:
        require(digest(artifacts[name]) == digest(expected['models'][name]),
                'mandatory_model_deviates_from_registered_reference')
    predictions = {name: predict(artifacts[name], public['query']) for name in names}
    evidence = {k: v for k, v in expected.items() if k not in ('models', 'sensitivity_models')}
    evidence['overlap'] = overlap(public['training'], public['query'])
    evidence['sensitivity_models'] = expected['sensitivity_models']
    evidence['sensitivity_predictions'] = {k: predict(v, public['query'])
                                         for k, v in expected['sensitivity_models'].items()}
    return (predictions, evidence) if return_evidence else predictions
