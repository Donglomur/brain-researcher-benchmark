"""Exact selected ordinary mathematical source from vendor/nystrom.py.
No CLI/file/provider entrypoint; imported only inside separately authorized methods.
Native/numerical equivalence remains unqualified. Original source and notices
remain in the immutable vendor closure. See SOURCE_EXTRACTIONS.json.
"""
import hashlib
import numpy as np
from scipy import linalg, ndimage
from scipy.spatial.distance import pdist
from sklearn.kernel_approximation import Nystroem


SEED = 20261030

KERNEL_SEED = 20261104

ALPHAS = (0.003, 0.03, 0.3)

WEIGHTS = (0.25, 0.5, 0.75, 1.0)

SCALES = (6.0, 18.0, None)

FLOOR = 1e-6

BLOCK = 5

LANDMARKS = 512

GAMMA_MULTIPLIERS = (0.25, 1.0, 4.0)

TRANSFORM_ROWS = 4096

def smooth(a, sigma=10.0, fixed=False):
    """Zero outside each trial, with exact convolution-of-ones edge correction."""
    if fixed:
        k = np.exp(-0.5 * ((np.arange(60) - 29.5) / 10.0) ** 2)
        k /= k.sum()
        def conv(v):
            # origin=-1 matches numpy.convolve(..., mode='same') for even kernels.
            return ndimage.convolve1d(v, k, axis=1, mode="constant", origin=-1)
    else:
        def conv(v):
            return ndimage.gaussian_filter1d(v, sigma, axis=1,
                                            mode="constant", truncate=3.0)
    den = conv(np.ones((1, a.shape[1], 1), dtype=a.dtype))
    return conv(a) / den

def pool(a):
    return a.reshape(a.shape[0], a.shape[1] // BLOCK, BLOCK, a.shape[2]).mean(2)

def condition_setup(c):
    names, inv, n = np.unique(c, return_inverse=True, return_counts=True)
    return names, inv, n

def group_sum(a, inv, n):
    return np.stack([a[inv == j].sum(axis=0, dtype=np.float64)
                     for j in range(len(n))])

def lookup(profiles, names, c, fallback):
    mapping = {str(v): i for i, v in enumerate(names)}
    out = np.empty((len(c),) + profiles.shape[1:], dtype=np.float32)
    for i, label in enumerate(c):
        j = mapping.get(str(label))
        out[i] = fallback if j is None else profiles[j]
    return out

def target_fit(y, c, need_residual=True):
    names, inv, n = condition_setup(c)
    mu = (y.sum(axis=(0, 1), dtype=np.float64) + 0.5) / (y.shape[0] * y.shape[1] + 1)
    profiles = smooth((group_sum(y, inv, n) + mu) / (n[:, None, None] + 1), fixed=True)
    residual = None
    if need_residual:
        own = smooth(y.astype(np.float32), fixed=True)
        # Leave the current trial out of its condition profile. The small global
        # prior uses all fitting trials; no validation targets enter this prior.
        loo = ((n[inv, None, None] + 1) * profiles[inv] - own) / n[inv, None, None]
        residual = pool(y.astype(np.float32) - loo.astype(np.float32)).reshape(-1, y.shape[2])
    return (names, profiles, mu), residual

def target_predict(state, c):
    names, profiles, mu = state
    return lookup(profiles, names, c, mu)

def feature_fit(x, c, families):
    names, inv, n = condition_setup(c)
    mu = (x.sum(axis=(0, 1), dtype=np.float64) + 0.5) / (x.shape[0] * x.shape[1] + 1)
    chunks = {f: [] for f in families}
    states = []
    for sigma in SCALES:
        if sigma is None:
            z = np.broadcast_to(x.mean(axis=1, keepdims=True, dtype=np.float32), x.shape).copy()
        else:
            z = smooth(x.astype(np.float32), sigma)
        if "direct" in chunks:
            chunks["direct"].append(pool(z))
        if "residual" in chunks:
            prof = (group_sum(z, inv, n) + mu) / (n[:, None, None] + 1)
            states.append(prof.astype(np.float32))
            # z minus a leave-one-trial-out observed condition/time expectation.
            z -= (((n[inv, None, None] + 1) * prof[inv] - z) / n[inv, None, None]).astype(np.float32)
            chunks["residual"].append(pool(z))
    out = {f: np.concatenate(v, axis=2).reshape(-1, x.shape[2] * len(SCALES))
           for f, v in chunks.items()}
    return out, (names, states, mu)

def feature_predict(x, c, state, families):
    names, profiles, mu = state
    chunks = {f: [] for f in families}
    for j, sigma in enumerate(SCALES):
        if sigma is None:
            z = np.broadcast_to(x.mean(axis=1, keepdims=True, dtype=np.float32), x.shape).copy()
        else:
            z = smooth(x.astype(np.float32), sigma)
        if "direct" in chunks:
            chunks["direct"].append(z.copy())
        if "residual" in chunks:
            z -= lookup(profiles[j], names, c, mu)
            chunks["residual"].append(z)
    return {f: np.concatenate(v, axis=2).reshape(-1, x.shape[2] * len(SCALES))
            for f, v in chunks.items()}

def ridge_path(x, y, alphas):
    xm = x.mean(axis=0, dtype=np.float64).astype(np.float32)
    xs = np.maximum(x.std(axis=0, dtype=np.float64), 1e-5).astype(np.float32)
    ym = y.mean(axis=0, dtype=np.float64).astype(np.float32)
    x -= xm
    x /= xs
    y = y.astype(np.float32) - ym
    gram = (x.T @ x).astype(np.float64) / len(x)
    cross = (x.T @ y).astype(np.float64) / len(x)
    eig, vec = linalg.eigh(gram, check_finite=False)
    projection = vec.T @ cross
    models = {}
    for alpha in alphas:
        coef = (vec @ (projection / (np.maximum(eig, 0)[:, None] + alpha))).astype(np.float32)
        # Fold standardization into coefficients for efficient full-bin inference.
        coef /= xs[:, None]
        intercept = ym - xm @ coef
        models[alpha] = (coef, intercept)
    return models

def raw_predict(x, model, shape):
    coef, intercept = model
    return (x @ coef + intercept).reshape(shape)

def combine(baseline, raw, family, weight):
    if family == "direct":
        out = baseline * (1 - weight) + raw * weight
    else:
        out = baseline + raw * weight
    return np.maximum(out, FLOOR).astype(np.float32)

def log_likelihood(y, p):
    # Constants cancel in paired Poisson comparisons. No private normalization.
    return float(np.sum(y * np.log(p) - p, dtype=np.float64))

def require(test, message):
    if not test:
        raise ValueError(message)

def finite_models(models):
    for coef, intercept in models.values():
        require(np.isfinite(coef).all() and np.isfinite(intercept).all(),
                "Finite fitted coefficients and intercepts")
    return models

def safe_combine(baseline, raw, family, weight):
    require(np.isfinite(baseline).all() and np.isfinite(raw).all(),
            "Reject nonfinite baseline/raw before rate flooring")
    mixed = (baseline * (1 - weight) + raw * weight if family == "direct"
             else baseline + raw * weight)
    require(np.isfinite(mixed).all(), "Reject nonfinite blend before rate flooring")
    return combine(baseline, raw, family, weight)

def training_split(conditions):
    """The existing reference's whole-trial rule, including singleton behavior."""
    rng = np.random.default_rng(SEED)
    selected = []
    for label in np.unique(conditions):
        members = np.flatnonzero(conditions == label)
        selected.extend(rng.permutation(members)[:max(1, int(round(0.2 * len(members))))])
    validation = np.sort(np.asarray(selected, dtype=np.int64))
    fit = np.setdiff1d(np.arange(len(conditions)), validation)
    require(len(fit) > 0 and len(validation) > 0, "Nonempty original fitting/validation folds")
    return fit, validation

def input_scaler(x):
    """Fit-only feature scales; unseen evaluation rows cannot alter these values."""
    require(x.ndim == 2 and len(x) >= LANDMARKS and np.isfinite(x).all(),
            "Finite complete fit features and at least512 landmarks")
    mean = x.mean(axis=0, dtype=np.float64)
    scale = np.maximum(x.std(axis=0, dtype=np.float64), 1e-5)
    require(np.isfinite(mean).all() and np.isfinite(scale).all(), "Finite feature scaling")
    return mean, scale

def standardized(x, scaler):
    mean, scale = scaler
    result = (np.asarray(x, dtype=np.float64) - mean) / scale
    require(np.isfinite(result).all(), "Finite standardized features")
    return result

def kernel_geometry(fit_x):
    scaler = input_scaler(fit_x)
    scaled = standardized(fit_x, scaler)
    indices = np.random.RandomState(KERNEL_SEED).permutation(len(scaled))[:LANDMARKS]
    distances = pdist(scaled[indices], metric="sqeuclidean")
    require(np.isfinite(distances).all(), "Finite landmark distances")
    positive = distances[distances > 0]
    require(len(positive) > 0, "Nondegenerate fit-only kernel geometry")
    median = float(np.median(positive))
    require(np.isfinite(median) and median > 0, "Positive finite kernel scale")
    return scaler, scaled, indices, median

def fit_map(scaled_fit_x, indices, median, multiplier):
    require(multiplier in GAMMA_MULTIPLIERS, "Declared gamma multiplier")
    mapper = Nystroem(kernel="rbf", gamma=multiplier / median,
                     n_components=LANDMARKS, random_state=KERNEL_SEED, n_jobs=1)
    mapper.fit(scaled_fit_x)
    require(np.array_equal(mapper.component_indices_, indices), "Exact fit-only landmark rule")
    require(np.isfinite(mapper.normalization_).all(), "Finite Nyström normalization")
    return mapper

def transform_rows(mapper, scaled_x):
    """A complete row stream; batching changes storage, never sample support."""
    for start in range(0, len(scaled_x), TRANSFORM_ROWS):
        block = mapper.transform(scaled_x[start:start + TRANSFORM_ROWS]).astype(np.float32)
        require(block.shape == (min(TRANSFORM_ROWS, len(scaled_x) - start), LANDMARKS)
                and np.isfinite(block).all(), "Finite full-support feature map")
        yield start, block

def fit_kernel_path(scaled_fit_x, mapper, response, alphas=ALPHAS):
    embedded = np.empty((len(scaled_fit_x), LANDMARKS), dtype=np.float32)
    for start, block in transform_rows(mapper, scaled_fit_x):
        embedded[start:start + len(block)] = block
    # The inherited ridge_path fit-centers and per-coordinate standardizes this
    # map, with floor1e-5. This is a standardized finite RBF-feature ridge,
    # deliberately not an assertion of unmodified RBF-kernel ridge equivalence.
    return finite_models(ridge_path(embedded, response, alphas))

def kernel_predict_many(features, scaler, mapper, models, shape):
    require(len(features) == int(np.prod(shape[:2])), "Full evaluation feature support")
    finite_models(models)
    result = {key: np.empty((len(features), shape[2]), dtype=np.float32) for key in models}
    # Standardize only a bounded complete block, using previously fitted state.
    for start in range(0, len(features), TRANSFORM_ROWS):
        scaled = standardized(features[start:start + TRANSFORM_ROWS], scaler)
        embedded = mapper.transform(scaled).astype(np.float32)
        require(np.isfinite(embedded).all(), "Finite deployment feature map")
        for key, (coef, intercept) in models.items():
            block = embedded @ coef + intercept
            require(np.isfinite(block).all(), "Finite deployment predictions")
            result[key][start:start + len(block)] = block
    return {key: value.reshape(shape) for key, value in result.items()}

def kernel_predict(features, scaler, mapper, model, shape):
    return kernel_predict_many(features, scaler, mapper, {"selected": model}, shape)["selected"]
