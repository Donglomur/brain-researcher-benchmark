"""NEURAL081 independent R2 equations; pure numerical qualification source.

No I/O, cross-call cache, executable model state, RNG, or sklearn invocation.
Every allocation estimate is logical ndarray/Python state, not measured RSS.
"""
import math
import numpy as np

CLASS_IDS = (1, 2, 3, 4, 11, 12, 13, 14, 21, 22, 23, 24)
PEOPLE = ('P01', 'P04', 'P05', 'P06', 'P07', 'P09', 'P11', 'P12', 'P13', 'P14')
FAMILIES = ('BP_LDA', 'TM_LDA', 'RBF_KRR')
TEMPERATURES = (1.0, 0.25, 4.0, 0.0625, 16.0, 0.015625, 64.0)
EPS = 2.0 ** -52
MODEL_KEYS = frozenset(('schema', 'family', 'configuration', 'class_ids', 'n_train',
                        'n_features', 'temperature', 'scaler_mean', 'scaler_scale',
                        'parameters', 'diagnostics'))


class NumericalError(ValueError):
    """Malformed support, nonfinite arithmetic, or a failed numerical check."""


class ResourceError(NumericalError):
    """The complete operation exceeds a prospective logical allocation cap."""


def _limits(limits):
    names = {'max_array_bytes', 'max_workspace_bytes', 'max_output_bytes'}
    if type(limits) is not dict or set(limits) != names:
        raise ResourceError('limits must contain exactly the three byte ceilings')
    if any(type(v) is not int or v <= 0 for v in limits.values()):
        raise ResourceError('limits must be positive nonboolean integers')
    return limits


def _reserve(limits, arrays, workspace, output):
    for amount in arrays:
        if type(amount) is not int or amount < 0 or amount > limits['max_array_bytes']:
            raise ResourceError('planned array exceeds max_array_bytes')
    if workspace > limits['max_workspace_bytes'] or output > limits['max_output_bytes']:
        raise ResourceError('complete planned workspace/output exceeds limit')


def _array(a, ndim, limits, *, shape=None, integer=False, single=False):
    if type(a) is not np.ndarray or a.ndim != ndim:
        raise NumericalError('exact primitive ndarray with expected dimensions required')
    permitted = a.dtype.kind in 'iu' if integer else a.dtype in (
        (np.dtype('float32'), np.dtype('float64')) if single else (np.dtype('float64'),))
    if not permitted or not a.dtype.isnative or a.dtype.fields is not None:
        raise NumericalError('invalid primitive dtype')
    if shape is not None and a.shape != shape:
        raise NumericalError('array shape differs from complete declared support')
    _reserve(limits, (a.nbytes, a.size), a.nbytes + a.size, 0)
    if not np.isfinite(a).all():
        raise NumericalError('array contains nonfinite values')
    return a


def _finite(a, message='nonfinite numerical intermediate'):
    if not np.isfinite(a).all():
        raise NumericalError(message)
    return a


def _number(value, *, positive=False):
    if type(value) not in (float, int):
        raise NumericalError('finite nonboolean scalar required')
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise NumericalError('finite nonboolean scalar required')
    if positive and value <= 0:
        raise NumericalError('positive scalar required')
    return float(value)


def _class_counts(labels, n, limits):
    _array(labels, 1, limits, shape=(n,), integer=True)
    counts = [0] * 12
    for y in labels:
        value = int(y)
        if value not in CLASS_IDS:
            raise NumericalError('label is not a canonical class ID')
        counts[CLASS_IDS.index(value)] += 1
    if min(counts) == 0:
        raise NumericalError('all twelve classes must be present')
    return counts


def configuration_grid():
    answer = []
    for family in FAMILIES[:2]:
        for j, shrinkage in enumerate((0.01, 0.1, 0.5, 'AUTO')):
            answer.append(dict(id=family + '_' + str(j), family=family,
                               shrinkage=shrinkage, alpha=None, gamma=None))
    for alpha in (0.01, 0.1, 1.0, 10.0):
        for gamma in (1.0 / 1280.0, 1.0 / 320.0, 4.0 / 320.0):
            answer.append(dict(id='RBF_KRR_' + str(len(answer) - 8), family='RBF_KRR',
                               shrinkage=None, alpha=alpha, gamma=gamma))
    return answer


def _historical_configuration():
    return dict(id='HISTORICAL_BP_LDA', family='HISTORICAL_BP_LDA',
                shrinkage='AUTO', alpha=None, gamma=None)


def _configuration(configuration, historical=False):
    candidates = [_historical_configuration()] if historical else configuration_grid()
    if type(configuration) is not dict or any(type(v) is bool for v in configuration.values()):
        raise NumericalError('configuration must be an exact supported grid dictionary')
    for accepted in candidates:
        if configuration == accepted and all(
                (type(configuration[k]) in (int, float) if type(v) in (int, float)
                 else type(configuration[k]) is type(v)) for k, v in accepted.items()):
            return dict(accepted)
    raise NumericalError('unsupported or mistyped configuration')


def features(eeg, family, *, limits):
    limits = _limits(limits)
    if type(family) is not str or family not in (*FAMILIES, 'HISTORICAL_BP_LDA'):
        raise NumericalError('unknown feature family')
    _array(eeg, 3, limits, single=True)
    n = eeg.shape[0]
    if eeg.shape[1:] != (64, 512) or n < 1:
        raise NumericalError('EEG must have complete shape [positive n,64,512]')
    d = 1024 if family == 'TM_LDA' else 320
    outbytes = 8 * n * d
    # One trial at a time; FFT can use its complete input/output scratch.
    trial_workspace = 16 * 64 * 512 * 8 + 16 * 64 * 257 * 16 + 65536
    _reserve(limits, (outbytes, 8 * 64 * 512, 16 * 64 * 257),
             eeg.nbytes + outbytes + trial_workspace, outbytes)
    result = np.empty((n, d), dtype=np.float64)
    with np.errstate(over='raise', invalid='raise', divide='raise'):
        try:
            h = (1.0 - np.cos(2.0 * math.pi * np.arange(512, dtype=np.float64) / 511.0)) / 2.0
            for row in range(n):
                u = eeg[row].astype(np.float64, copy=True)
                u -= u.mean(axis=1, keepdims=True)
                _finite(u)
                if family == 'TM_LDA':
                    result[row] = u.reshape(64, 16, 32).mean(axis=2).reshape(1024)
                else:
                    spectrum = np.fft.rfft(u * h, axis=1)
                    power = (spectrum.real ** 2 + spectrum.imag ** 2) / 512.0
                    _finite(power)
                    bands = np.empty((64, 5), dtype=np.float64)
                    for j, (start, stop) in enumerate(((4, 16), (16, 32), (32, 52), (52, 80), (80, 120))):
                        bands[:, j] = np.log(np.maximum(power[:, start:stop].mean(axis=1), 1e-24))
                    result[row] = bands.reshape(320)
        except (FloatingPointError, OverflowError) as exc:
            raise NumericalError('feature arithmetic failed') from exc
    return _finite(result)


def _scaler(x):
    """Population mathematical moments; deliberately not a sklearn execution."""
    n = x.shape[0]
    mean = _finite(x.mean(axis=0))
    centered = _finite(x - mean)
    variance = _finite(np.mean(centered * centered, axis=0))
    if (variance < 0).any():
        raise NumericalError('negative variance')
    bound = _finite(n * EPS * variance + (n * mean * EPS) ** 2)
    constant = variance <= bound
    scale = np.sqrt(variance)
    scale[constant] = 1.0
    standardized = _finite(centered / scale)
    return mean, scale, standardized, constant


def _symmetric(a):
    # Copy one triangle, rather than relying on independent accumulation equality.
    for i in range(a.shape[0]):
        a[i + 1:, i] = a[i, i + 1:]
    return a


def _inf(a):
    value = float(np.max(np.sum(np.abs(a), axis=1))) if a.ndim == 2 else float(np.max(np.abs(a)))
    if not math.isfinite(value):
        raise NumericalError('nonfinite infinity norm')
    return value


def _ratio(numerator, denominator):
    if not math.isfinite(numerator) or not math.isfinite(denominator) or denominator < 0:
        raise NumericalError('undefined residual ratio')
    if denominator == 0:
        if numerator != 0:
            raise NumericalError('nonzero residual with zero denominator')
        return 0.0
    result = numerator / denominator
    if not math.isfinite(result) or result > 1e-10:
        raise NumericalError('residual tolerance exceeded')
    return result


def _minimum_norm(covariance, class_means):
    """Private dimension-generic primitive for tiny analytic controls."""
    u, singular, vh = np.linalg.svd(covariance, full_matrices=False)
    _finite(u); _finite(singular); _finite(vh)
    cutoff = EPS * float(singular[0]) if singular.size else 0.0
    keep = singular > cutoff
    projected = u.T @ class_means.T
    projected[keep] /= singular[keep, None]
    projected[~keep] = 0.0
    weights = _finite(vh.T @ projected)
    norm_s = _inf(covariance)
    norm_w = _inf(weights)
    normal = _finite(covariance.T @ (covariance @ weights - class_means.T))
    ratio = _ratio(_inf(normal), norm_s * (norm_s * norm_w + _inf(class_means.T)))
    discarded = vh[~keep] @ weights
    component = 0.0 if discarded.size == 0 else _inf(discarded) / max(1.0, norm_w)
    if not math.isfinite(component) or component > 1e-10:
        raise NumericalError('minimum-norm discarded component exceeded tolerance')
    return weights, dict(rank=int(keep.sum()), cutoff=float(cutoff),
                         normal_equation_residual=ratio, discarded_component=component)


def _auto_covariance(class_rows):
    _, scales, standardized, constant = _scaler(class_rows)
    v = _finite(standardized - standardized.mean(axis=0))
    n, d = v.shape
    empirical = _symmetric(_finite(v.T @ v / n))
    squared = _finite(v * v)
    a = squared.mean(axis=0)
    mu = float(a.sum() / d)
    dsquared = float(np.sum(empirical * empirical))
    # B = sum_i (sum_j V_ij^2)^2, with no n*d*d tensor.
    rowsquares = squared.sum(axis=1)
    big_b = float(np.sum(rowsquares * rowsquares))
    beta0 = (big_b / n - dsquared) / (d * n)
    delta = (dsquared - 2.0 * mu * float(a.sum()) + d * mu * mu) / d
    beta = min(beta0, delta)
    if not all(math.isfinite(vv) for vv in (mu, dsquared, big_b, beta0, delta, beta)):
        raise NumericalError('nonfinite Ledoit-Wolf reduction')
    if beta == 0.0:
        shrinkage = 0.0
    elif delta == 0.0:
        raise NumericalError('undefined Ledoit-Wolf shrinkage')
    else:
        shrinkage = beta / delta
    if not math.isfinite(shrinkage) or not 0.0 <= shrinkage <= 1.0:
        raise NumericalError('Ledoit-Wolf shrinkage outside [0,1]')
    covariance = empirical * (1.0 - shrinkage)
    covariance.flat[::d + 1] += shrinkage * mu
    covariance *= scales[:, None]
    covariance *= scales[None, :]
    return _symmetric(_finite(covariance)), shrinkage, scales, int(constant.sum())


def _lda(z, labels, shrinkage):
    n, d = z.shape
    means = np.empty((12, d), dtype=np.float64)
    pooled = np.zeros((d, d), dtype=np.float64)
    strengths, scales, constants = [], [], []
    for k, class_id in enumerate(CLASS_IDS):
        subset = z[labels == class_id]
        means[k] = subset.mean(axis=0)
        if shrinkage == 'AUTO':
            cov, amount, scale, nconstant = _auto_covariance(subset)
            strengths.append(float(amount)); scales.append(scale.tolist()); constants.append(nconstant)
        else:
            residuals = _finite(subset - means[k])
            cov = _symmetric(_finite(residuals.T @ residuals / subset.shape[0]))
            target = float(np.trace(cov) / d)
            cov *= 1.0 - shrinkage
            cov.flat[::d + 1] += shrinkage * target
            strengths.append(float(shrinkage))
        pooled += cov / 12.0
    weights, diagnostics = _minimum_norm(_symmetric(_finite(pooled)), _finite(means))
    intercepts = _finite(-0.5 * np.sum(means * weights.T, axis=1) + math.log(1.0 / 12.0))
    diagnostics.update(class_shrinkages=strengths, covariance_class_priors=[1.0 / 12.0] * 12)
    if shrinkage == 'AUTO':
        diagnostics.update(classwise_scales=scales, classwise_constant_counts=constants)
    return dict(coefficients=np.ascontiguousarray(weights), intercepts=intercepts), diagnostics


def _kernel(left, right, gamma, *, symmetric=False):
    """Complete direct differences in blocks; caller reserves every tensor size."""
    nl, d = left.shape
    nr = right.shape[0]
    result = np.empty((nl, nr), dtype=np.float64)
    # Square fit blocks permit mirrored entries. Query blocks need no symmetry.
    step = 16
    for lo in range(0, nl, step):
        for ro in range(lo if symmetric else 0, nr, step):
            a = left[lo:lo + step]
            b = right[ro:ro + step]
            differences = _finite(a[:, None, :] - b[None, :, :])
            squares = _finite(differences * differences)
            distance = _finite(squares.sum(axis=2))
            block = np.exp(_finite(-gamma * distance))
            if symmetric and lo == ro:
                _symmetric(block)
                np.fill_diagonal(block, 1.0)
            result[lo:lo + len(a), ro:ro + len(b)] = block
            if symmetric and lo != ro:
                result[ro:ro + len(b), lo:lo + len(a)] = block.T
    return _finite(result)


def _krr(z, labels, alpha, gamma):
    n = z.shape[0]
    gram = _kernel(z, z, gamma, symmetric=True)
    rowmean = _finite(gram.mean(axis=1))
    grand = float(rowmean.mean())
    centered = _finite(gram - rowmean[:, None] - rowmean[None, :] + grand)
    _symmetric(centered)
    y = np.zeros((n, 12), dtype=np.float64)
    for i, value in enumerate(labels):
        y[i, CLASS_IDS.index(int(value))] = 1.0
    class_mean = y.mean(axis=0)
    yc = y - class_mean
    centered.flat[::n + 1] += alpha
    # Cholesky establishes SPD; no jitter and no fallback to another solver.
    chol = np.linalg.cholesky(centered)
    dual = _finite(np.linalg.solve(chol.T, np.linalg.solve(chol, yc)))
    residual = _finite(centered @ dual - yc)
    ratio = _ratio(_inf(residual), _inf(centered) * _inf(dual) + _inf(yc))
    return dict(training_z=z.copy(order='C'), dual=dual, row_kernel_mean=rowmean,
                grand_kernel_mean=grand, class_mean=class_mean), dict(spd_rank=n, solve_residual=ratio)


def _fit(feature_matrix, labels, configuration, limits, historical):
    limits = _limits(limits)
    config = _configuration(configuration, historical)
    family = config['family']
    d = 1024 if family == 'TM_LDA' else 320
    _array(feature_matrix, 2, limits)
    n = feature_matrix.shape[0]
    if n < 12 or feature_matrix.shape[1] != d:
        raise NumericalError('complete family feature width and all-class support required')
    # Includes all classwise diagnostic lists conservatively at 40 bytes/scalar.
    output = (8 * n * d + 104 * n + 16 * d + 96 + 65536) if family == 'RBF_KRR' else (120 * d + 12 * d * 40 + 65536)
    block_tensor = 8 * min(16, n) ** 2 * d
    workspace = feature_matrix.nbytes + labels.nbytes if type(labels) is np.ndarray else feature_matrix.nbytes
    workspace += 96 * n * d + 256 * d * d + 65536 + output
    if family == 'RBF_KRR':
        workspace += 80 * n * n + 2048 * n + 4 * block_tensor
    _reserve(limits, (8 * n * d, 8 * d * d, 96 * n, block_tensor,
                      8 * n * n if family == 'RBF_KRR' else 96 * d), workspace, output)
    _class_counts(labels, n, limits)
    with np.errstate(over='raise', invalid='raise', divide='raise'):
        try:
            mean, scale, z, constant = _scaler(feature_matrix)
            if family == 'RBF_KRR':
                parameters, diagnostics = _krr(z, labels, config['alpha'], config['gamma'])
            else:
                parameters, diagnostics = _lda(z, labels, config['shrinkage'])
            diagnostics['global_constant_count'] = int(constant.sum())
            if historical:
                diagnostics['historical_implementation'] = 'independent_mathematical_AUTO_not_sklearn'
        except (FloatingPointError, OverflowError, np.linalg.LinAlgError) as exc:
            raise NumericalError('complete fit failed; no fallback') from exc
    return dict(schema='neural081_numeric_model_v1', family=family, configuration=config,
                class_ids=list(CLASS_IDS), n_train=n, n_features=d, temperature=1.0,
                scaler_mean=mean, scaler_scale=scale, parameters=parameters, diagnostics=diagnostics)


def fit(feature_matrix, labels, configuration, *, limits):
    return _fit(feature_matrix, labels, configuration, limits, False)


def fit_historical(feature_matrix, labels, *, limits):
    return _fit(feature_matrix, labels, _historical_configuration(), limits, True)


def _json_size(value, seen=None):
    """Validate diagnostics and conservatively reserve Python scalar/list storage."""
    if seen is None:
        seen = set()
    if type(value) in (dict, list):
        if id(value) in seen:
            raise NumericalError('cyclic or shared mutable diagnostic containers')
        seen.add(id(value))
    if type(value) is dict:
        if any(type(k) is not str for k in value):
            raise NumericalError('diagnostic keys must be strings')
        return 128 + sum(4 * len(k) + 64 + _json_size(v, seen) for k, v in value.items())
    if type(value) is list:
        return 64 + 8 * len(value) + sum(_json_size(v, seen) for v in value)
    if type(value) is str:
        return 64 + 4 * len(value)
    if value is None or type(value) is bool:
        return 32
    if type(value) in (int, float):
        _number(value)
        return 40
    raise NumericalError('diagnostic state must be finite nonexecutable JSON')


def _model(model, limits):
    if type(model) is not dict or set(model) != MODEL_KEYS or model['schema'] != 'neural081_numeric_model_v1':
        raise NumericalError('invalid model tree schema')
    family = model['family']
    config = _configuration(model['configuration'], family == 'HISTORICAL_BP_LDA')
    if family != config['family'] or type(model['class_ids']) is not list or model['class_ids'] != list(CLASS_IDS) or any(type(x) is not int for x in model['class_ids']):
        raise NumericalError('invalid model family or class axis')
    n, d = model['n_train'], model['n_features']
    if type(n) is not int or n < 12 or type(d) is not int or d != (1024 if family == 'TM_LDA' else 320):
        raise NumericalError('invalid complete model dimensions')
    _number(model['temperature'], positive=True)
    if type(model['diagnostics']) is not dict:
        raise NumericalError('diagnostics must be a JSON map')
    payload = 4096 + _json_size(model['diagnostics'])
    params = model['parameters']
    if type(params) is not dict:
        raise NumericalError('parameter map required')
    specs = {'training_z': (n, d), 'dual': (n, 12), 'row_kernel_mean': (n,), 'class_mean': (12,)} if family == 'RBF_KRR' else {'coefficients': (d, 12), 'intercepts': (12,)}
    if set(params) != set(specs) | ({'grand_kernel_mean'} if family == 'RBF_KRR' else set()):
        raise NumericalError('invalid model parameter keys')
    all_arrays = [model['scaler_mean'], model['scaler_scale']] + [params[k] for k in specs]
    if any(type(a) is not np.ndarray for a in all_arrays):
        raise NumericalError('model arrays must be exact ndarrays')
    payload += sum(a.nbytes for a in all_arrays)
    # Admit total saved state plus largest validation mask before testing finiteness.
    _reserve(limits, tuple(a.nbytes for a in all_arrays),
             payload + max(a.size for a in all_arrays), 0)
    for name in ('scaler_mean', 'scaler_scale'):
        _array(model[name], 1, limits, shape=(d,))
    if (model['scaler_scale'] <= 0).any():
        raise NumericalError('nonpositive saved scales')
    for key, shape in specs.items():
        _array(params[key], len(shape), limits, shape=shape)
    if family == 'RBF_KRR':
        grand = _number(params['grand_kernel_mean'])
        if not 0 <= grand <= 1 or np.any(params['row_kernel_mean'] < 0) or np.any(params['row_kernel_mean'] > 1):
            raise NumericalError('invalid saved kernel moments')
        _probability_rows(params['class_mean'].reshape(1, 12))
    _reserve(limits, (), payload, 0)
    return n, d, payload


def predict_scores(model, feature_matrix, *, limits):
    limits = _limits(limits)
    n, d, payload = _model(model, limits)
    _array(feature_matrix, 2, limits)
    q = feature_matrix.shape[0]
    if feature_matrix.shape[1] != d or q < 1:
        raise NumericalError('invalid complete query features')
    block = min(q, 256)
    tensor = 8 * min(16, block) * min(16, n) * d
    workspace = payload + feature_matrix.nbytes + 96 * q + 40 * block * d + 65536
    arrays = [96 * q, 8 * block * d]
    if model['family'] == 'RBF_KRR':
        workspace += 40 * block * n + 4 * tensor + 2048 * block
        arrays += [8 * block * n, tensor]
    _reserve(limits, arrays, workspace, 96 * q)
    output = np.empty((q, 12), dtype=np.float64)
    params = model['parameters']
    with np.errstate(over='raise', invalid='raise', divide='raise'):
        try:
            for start in range(0, q, 256):
                z = _finite((feature_matrix[start:start + 256] - model['scaler_mean']) / model['scaler_scale'])
                if model['family'] == 'RBF_KRR':
                    k = _kernel(z, params['training_z'], model['configuration']['gamma'])
                    kc = k - params['row_kernel_mean'][None, :] - k.mean(axis=1, keepdims=True) + params['grand_kernel_mean']
                    output[start:start + len(z)] = _finite(kc @ params['dual'] + params['class_mean'])
                else:
                    output[start:start + len(z)] = _finite(z @ params['coefficients'] + params['intercepts'])
        except (FloatingPointError, OverflowError) as exc:
            raise NumericalError('prediction arithmetic failed') from exc
    return _finite(output)


def _probability_rows(p):
    for row in p:
        if any(not math.isfinite(float(x)) or float(x) < 0 or float(x) > 1 for x in row):
            raise NumericalError('invalid probability range or finiteness')
        if abs(math.fsum(float(x) for x in row) - 1.0) > 1e-6:
            raise NumericalError('probability row fails canonical sum tolerance')


def probabilities(scores, temperature, *, limits):
    limits = _limits(limits)
    _array(scores, 2, limits)
    if scores.shape[1] != 12 or scores.shape[0] < 1:
        raise NumericalError('scores require positive rows and twelve class columns')
    t = _number(temperature, positive=True)
    size = scores.nbytes
    _reserve(limits, (size,), 2 * size + 4096, size)
    result = np.empty(scores.shape, dtype=np.float64)
    for i, row in enumerate(scores):
        high = max(float(x) for x in row)
        exponentials = []
        for value in row:
            shifted = (float(value) - high) / t
            if not math.isfinite(shifted):
                raise NumericalError('nonfinite divided softmax score')
            exponentials.append(math.exp(shifted))
        denominator = math.fsum(exponentials)
        if not math.isfinite(denominator) or denominator <= 0:
            raise NumericalError('invalid softmax denominator')
        result[i] = [value / denominator for value in exponentials]
    _probability_rows(result)
    return result


def _people(people_order, nine=False):
    if type(people_order) is not list or not people_order or any(type(x) is not str for x in people_order):
        raise NumericalError('people_order must be a plain list of canonical persons')
    if len(set(people_order)) != len(people_order) or people_order != [x for x in PEOPLE if x in people_order]:
        raise NumericalError('people must be a canonical-order biological subset')
    if nine and len(people_order) != 9:
        raise NumericalError('selection requires exactly nine training people')


def _ids(ids, n):
    if type(ids) is not list or len(ids) != n or any(type(x) is not str or not x for x in ids):
        raise NumericalError('plain nonempty string IDs required')
    if len(set(ids)) != n:
        raise NumericalError('canonical IDs must be unique')


def _person_record(p, labels, ids, person, rows):
    counts, correct = [0] * 12, [0] * 12
    losses = []
    for i in sorted(rows, key=lambda j: ids[j]):
        k = CLASS_IDS.index(int(labels[i]))
        counts[k] += 1
        prediction = max(range(12), key=lambda j: float(p[i, j]))
        correct[k] += int(prediction == k)
        losses.append(-math.log(max(float(p[i, k]), 1e-12)))
    if min(counts) == 0:
        raise NumericalError('person has missing class support')
    recalls = [a / b for a, b in zip(correct, counts)]
    ba = math.fsum(recalls) / 12
    nll = math.fsum(losses) / len(rows)
    if not math.isfinite(ba) or not math.isfinite(nll):
        raise NumericalError('nonfinite metric reduction')
    return dict(person=person, rows=len(rows), class_counts=counts, correct_counts=correct,
                class_recalls=recalls, balanced_accuracy=ba, nll=nll)


def _aggregate(records):
    return dict(balanced_accuracy=math.fsum(r['balanced_accuracy'] for r in records) / len(records),
                nll=math.fsum(r['nll'] for r in records) / len(records), per_person=records)


def metrics(probabilities, labels, persons, canonical_ids, people_order, *, limits):
    limits = _limits(limits)
    _array(probabilities, 2, limits)
    n = probabilities.shape[0]
    if probabilities.shape != (n, 12) or n < 12:
        raise NumericalError('invalid probability shape')
    _people(people_order)
    metadata = 4 * sum(len(x) for x in canonical_ids if type(x) is str) if type(canonical_ids) is list else 0
    _reserve(limits, (), probabilities.nbytes + 256 * n + metadata + 4096 * len(people_order), 4096 * len(people_order) + 1024)
    _class_counts(labels, n, limits)
    _ids(canonical_ids, n)
    if type(persons) is not list or len(persons) != n or any(type(x) is not str or x not in people_order for x in persons):
        raise NumericalError('invalid row person list')
    if set(persons) != set(people_order):
        raise NumericalError('people roster differs from rows')
    _probability_rows(probabilities)
    return _aggregate([_person_record(probabilities, labels, canonical_ids, person,
                                     [i for i, p in enumerate(persons) if p == person])
                       for person in people_order])


def _oof_score(records, people_order, temperature, limits):
    per_person = []
    for person in people_order:
        record = records[person]
        p = record['probabilities_t1'] if temperature is None else probabilities(record['scores'], temperature, limits=limits)
        per_person.append(_person_record(p, record['labels'], record['canonical_ids'], person, range(len(record['labels']))))
    return _aggregate(per_person)


def select(oof, people_order, *, limits):
    limits = _limits(limits)
    _people(people_order, nine=True)
    if type(oof) is not list or len(oof) != 180:
        raise NumericalError('selection requires exactly 180 complete observations')
    keys = {'configuration_id', 'person', 'canonical_ids', 'labels', 'scores', 'probabilities_t1'}
    grid = configuration_grid()
    lookup = {c['id']: {} for c in grid}
    # Reserve complete supplied numeric inputs, support joins, validation and output.
    total_input, total_rows, metadata, largest = 0, 0, 0, 0
    for record in oof:
        if type(record) is not dict or set(record) != keys:
            raise NumericalError('invalid OOF record schema')
        if type(record['canonical_ids']) is not list:
            raise NumericalError('invalid OOF canonical-ID list')
        for name in ('labels', 'scores', 'probabilities_t1'):
            a = record[name]
            if type(a) is not np.ndarray:
                raise NumericalError('invalid OOF array')
            total_input += a.nbytes
            largest = max(largest, a.nbytes)
        total_rows += len(record['canonical_ids'])
        metadata += sum(4 * len(x) + 128 for x in record['canonical_ids'] if type(x) is str)
    outsize = 4096 * 41 * 9 + 65536
    _reserve(limits, (largest,), total_input + 4 * largest + 256 * total_rows + metadata + outsize, outsize)
    support = {}
    all_ids = set()
    for record in oof:
        cid, person = record['configuration_id'], record['person']
        if type(cid) is not str or cid not in lookup or type(person) is not str or person not in people_order or person in lookup[cid]:
            raise NumericalError('unknown/duplicate OOF configuration-person pair')
        n = len(record['canonical_ids'])
        _ids(record['canonical_ids'], n)
        _class_counts(record['labels'], n, limits)
        _array(record['scores'], 2, limits, shape=(n, 12))
        _array(record['probabilities_t1'], 2, limits, shape=(n, 12))
        _probability_rows(record['probabilities_t1'])
        expected = probabilities(record['scores'], 1.0, limits=limits)
        if not np.array_equal(expected, record['probabilities_t1']):
            raise NumericalError('stored T1 probabilities do not equal deterministic source output')
        mapping = dict(zip(record['canonical_ids'], map(int, record['labels'])))
        if person in support:
            if mapping != support[person]:
                raise NumericalError('OOF configurations differ in canonical ID/label support')
        else:
            if all_ids.intersection(mapping):
                raise NumericalError('canonical support overlaps across people')
            support[person] = mapping
            all_ids.update(mapping)
        lookup[cid][person] = record
    if any(set(rows) != set(people_order) for rows in lookup.values()):
        raise NumericalError('incomplete OOF grid')
    setting_scores = []
    for config in grid:
        setting_scores.append(dict(configuration_id=config['id'], family=config['family'],
                                   **_oof_score(lookup[config['id']], people_order, None, limits)))
    selected_per_family, temperature_scores, selected_temperatures = [], [], []
    for family in FAMILIES:
        settings = [r for r in setting_scores if r['family'] == family]
        best = min(enumerate(settings), key=lambda pair: (-pair[1]['balanced_accuracy'], pair[1]['nll'], pair[0]))[1]
        selected_per_family.append({key: best[key] for key in ('family', 'configuration_id', 'balanced_accuracy', 'nll')})
        scanned = []
        for temperature in TEMPERATURES:
            scored = _oof_score(lookup[best['configuration_id']], people_order, temperature, limits)
            scanned.append(dict(family=family, configuration_id=best['configuration_id'], temperature=temperature, **scored))
        temperature_scores.extend(scanned)
        calibrated = min(enumerate(scanned), key=lambda pair: (pair[1]['nll'], pair[0]))[1]
        selected_temperatures.append({key: calibrated[key] for key in ('family', 'configuration_id', 'temperature', 'balanced_accuracy', 'nll')})
    strongest = min(enumerate(selected_temperatures), key=lambda pair: (-pair[1]['balanced_accuracy'], pair[1]['nll'], pair[0]))[1]['family']
    return dict(setting_scores=setting_scores, selected_per_family=selected_per_family,
                temperature_scores=temperature_scores, selected_temperatures=selected_temperatures,
                strongest_family=strongest)


def analytic_priors(labels, *, limits):
    limits = _limits(limits)
    if type(labels) is not np.ndarray or labels.ndim != 1:
        raise NumericalError('labels must be a primitive integer vector')
    _reserve(limits, (96,), labels.nbytes + 4096, 192)
    counts = _class_counts(labels, len(labels), limits)
    uniform = np.full(12, 1.0 / 12.0, dtype=np.float64)
    laplace = np.array([(count + 1) / (len(labels) + 12) for count in counts], dtype=np.float64)
    _probability_rows(uniform.reshape(1, 12)); _probability_rows(laplace.reshape(1, 12))
    return dict(uniform=uniform, laplace=laplace)
