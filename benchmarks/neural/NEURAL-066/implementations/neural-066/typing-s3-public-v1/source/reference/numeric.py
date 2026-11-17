"""Training-only numerical transforms and exact public linear reference recipe."""
from . import core

def training_flat(train, rows, dimensions):
    import numpy as np
    core.need(type(dimensions) is int and dimensions > 0, 'Positive exact feature dimension')
    core.need(train.ndim == 2 and train.shape[1] == dimensions + 2 and (train.dtype == np.dtype('<f4')) and train.flags.c_contiguous and np.isfinite(train).all(), 'Exact complete finite float32 matrix')
    core.layout(rows, len(train), True)
    labels = train[:, -2]
    weights = train[:, -1]
    core.need(np.equal(labels, np.floor(labels)).all() and ((labels >= 0) & (labels < 29)).all() and (weights > 0).all(), 'Mapped integer labels and positive original weights')
    expected = np.asarray(core.weights(rows), dtype='float64') * len(train)
    core.need(np.allclose(weights, expected, rtol=1e-06, atol=1e-08), 'Original Ntrain/(P*S_person*L_sentence) scale, not unit-sum regularization')
    return (train[:, :dimensions], labels.astype('int64'), weights)

def training(train, rows, channels):
    import numpy as np
    core.need(type(channels) is int and channels in (61, 306), 'complete selected modality channels')
    core.need(train.ndim == 2 and train.shape[1] == channels * 25 + 2 and (train.dtype == np.dtype('<f4')) and train.flags.c_contiguous and np.isfinite(train).all(), 'exact finite C-order float32 training matrix')
    core.layout(rows, len(train), True)
    labels = train[:, -2]
    weights = train[:, -1]
    core.need(np.equal(labels, np.floor(labels)).all() and ((labels >= 0) & (labels < 29)).all() and (weights > 0).all(), 'integer labels and positive original weights')
    return (train[:, :channels * 25].reshape(len(train), channels, 25), labels.astype('int64'), weights)

def fit_normalization(features, rows, ids):
    import numpy as np
    chosen = core.subset(rows, ids)
    weights = core.weights(chosen)
    core.need(features.ndim == 3 and features.shape[2] == 25 and np.isfinite(features).all(), 'complete finite channel/time features')
    channels = features.shape[1]
    mean = np.zeros(channels, dtype='float64')
    offset = 0
    for sentence in chosen:
        n = sentence['n_keys']
        w = np.asarray(weights[offset:offset + n], dtype='float64')
        x = np.asarray(features[sentence['begin']:sentence['begin'] + n], dtype='float64')
        mean += np.sum(x * w[:, None, None] / 25, axis=(0, 2), dtype='float64')
        offset += n
    variance = np.zeros(channels, dtype='float64')
    offset = 0
    for sentence in chosen:
        n = sentence['n_keys']
        w = np.asarray(weights[offset:offset + n], dtype='float64')
        x = np.asarray(features[sentence['begin']:sentence['begin'] + n], dtype='float64')
        variance += np.sum((x - mean[None, :, None]) ** 2 * w[:, None, None] / 25, axis=(0, 2), dtype='float64')
        offset += n
    core.need(np.isfinite(mean).all() and np.isfinite(variance).all() and (variance >= 0).all(), 'finite training-only population moments')
    scale = np.sqrt(variance)
    scale[scale == 0] = 1
    return {'mean': mean, 'scale': scale, 'variance': variance}

def transform(features, state):
    import numpy as np
    core.need(set(state) == {'mean', 'scale', 'variance'}, 'complete normalized transform state')
    mean, scale = (state['mean'], state['scale'])
    core.need(features.ndim == 3 and features.shape[2] == 25 and (mean.shape == scale.shape == (features.shape[1],)) and np.isfinite(features).all() and np.isfinite(mean).all() and np.isfinite(scale).all() and (scale > 0).all(), 'finite supported transform')
    result = ((features.astype('float64') - mean[None, :, None]) / scale[None, :, None]).astype('float32')
    core.need(np.isfinite(result).all(), 'finite float32 normalized model input')
    return result

def fit_r0(train, rows, dimensions):
    import numpy as np
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LogisticRegression
    _, labels, weights = training_flat(train, rows, dimensions)
    core.need(len(set(labels.tolist())) >= 2, 'R0 requires at least two training classes')
    scaler = StandardScaler()
    x = scaler.fit_transform(train[:, :dimensions], sample_weight=weights)
    model = LogisticRegression(C=1, solver='lbfgs', max_iter=2000, tol=1e-06, random_state=65)
    model.fit(x, labels, sample_weight=weights)
    core.need(max(model.n_iter_) < 2000, 'R0 convergence failure is incomplete')
    arrays = {'mean': scaler.mean_, 'scale': scaler.scale_, 'variance': scaler.var_, 'classes': model.classes_.astype('int64'), 'coef': model.coef_, 'intercept': model.intercept_, 'n_iter': model.n_iter_.astype('int64')}
    core.need(all((np.isfinite(a).all() for a in arrays.values())), 'finite complete R0 state')
    return ({'kind': 'R0', 'n_features': dimensions, 'class_policy': 'absent output1e-12 then normalize'}, arrays)

def predict_r0(config, arrays, features):
    import numpy as np
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LogisticRegression
    core.need(set(arrays) == {'mean', 'scale', 'variance', 'classes', 'coef', 'intercept', 'n_iter'}, 'complete inert R0 state')
    d = config['n_features']
    classes = arrays['classes']
    core.need(features.ndim == 2 and features.shape[1] == d and np.isfinite(features).all() and (classes.ndim == 1) and (2 <= len(classes) <= 29) and (classes.dtype.kind == 'i') and np.array_equal(classes, np.unique(classes)) and ((classes >= 0) & (classes < 29)).all(), 'R0 exact feature/classes')
    expected_coef = 1 if len(classes) == 2 else len(classes)
    core.need(arrays['coef'].shape == (expected_coef, d) and arrays['intercept'].shape == (expected_coef,) and all((arrays[k].shape == (d,) for k in ('mean', 'scale', 'variance'))) and (arrays['scale'] > 0).all(), 'R0 exact parameter shapes')
    core.need(all((np.isfinite(v).all() for v in arrays.values())), 'finite R0 state')
    core.need(arrays['n_iter'].dtype.kind == 'i' and arrays['n_iter'].ndim == 1 and (len(arrays['n_iter']) > 0) and (arrays['n_iter'] >= 0).all() and (arrays['n_iter'] < 2000).all(), 'Original converged iteration state, no constant-proxy rejection')
    scaler = StandardScaler()
    scaler.mean_ = arrays['mean']
    scaler.scale_ = arrays['scale']
    scaler.var_ = arrays['variance']
    scaler.n_features_in_ = d
    model = LogisticRegression(C=1, solver='lbfgs', max_iter=2000, tol=1e-06, random_state=65)
    model.classes_ = classes
    model.coef_ = arrays['coef']
    model.intercept_ = arrays['intercept']
    model.n_iter_ = arrays['n_iter']
    model.n_features_in_ = d
    prob = np.full((len(features), 29), 1e-12)
    prob[:, classes] = model.predict_proba(scaler.transform(features))
    prob /= prob.sum(axis=1, keepdims=True)
    core.probabilities(prob.tolist(), len(features))
    return prob
