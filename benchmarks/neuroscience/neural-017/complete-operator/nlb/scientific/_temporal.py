"""Exact selected ordinary mathematical source from vendor/temporal.py.
No CLI/file/provider entrypoint; imported only inside separately authorized methods.
Native/numerical equivalence remains unqualified. Original source and notices
remain in the immutable vendor closure. See SOURCE_EXTRACTIONS.json.
"""
import numpy as np
from scipy import linalg, ndimage


SEED = 20261030

BIN_COUNT = 140

BLOCK = 5

LAG = 6

ALPHAS = (0.03, 0.3, 3.0)

GLOBAL_BLENDS = (0.25, 0.5, 0.75, 1.0)

LOCAL_BLENDS = (0.0, 0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1.0)

LOCAL_PENALTY_NATS = 20.0

RATE_FLOOR = np.float32(1e-6)

CONTEXTS = ((10, 1.0), (0, .25), (0, 1.0), (0, 4.0),
            (5, .25), (5, 1.0), (5, 4.0), (10, .25), (10, 4.0),
            (20, .25), (20, 1.0), (20, 4.0), (None, None))

def require(condition, message):
    if not bool(condition):
        raise ValueError(message)

def split_trials(conditions):
    """Whole trials; retain a fitting trial even for a singleton condition."""
    rng = np.random.default_rng(SEED)
    validation = []
    for condition in np.unique(conditions):
        rows = np.flatnonzero(conditions == condition)
        if len(rows) > 1:
            n = min(len(rows) - 1, max(1, int(round(.2 * len(rows)))))
            validation.extend(rng.permutation(rows)[:n].tolist())
    validation = np.asarray(sorted(validation), dtype=np.int64)
    mask = np.ones(len(conditions), dtype=bool)
    mask[validation] = False
    fit = np.flatnonzero(mask)
    require(len(fit) > 0 and len(validation) > 0, "Whole-trial selection needs both subsets")
    return fit, validation

def profile_statistics(targets, conditions):
    names, inverse, counts = np.unique(conditions, return_inverse=True, return_counts=True)
    sums = np.stack([targets[inverse == j].sum(axis=0, dtype=np.float64)
                     for j in range(len(names))])
    mu = (targets.sum(axis=(0, 1), dtype=np.float64) + .5) / (targets.shape[0] * BIN_COUNT + 1)
    return names, counts, sums, mu

def context_model(statistics, specification):
    names, counts, sums, mu = statistics
    sigma, kappa = specification
    if sigma is None:
        values = np.broadcast_to(mu, sums.shape).copy()
    else:
        values = (sums + kappa * mu[None, None, :]) / (counts[:, None, None] + kappa)
        if sigma:
            length = 6 * sigma
            positions = np.arange(length, dtype=np.float64) - (length - 1) / 2
            weights = np.exp(-.5 * (positions / sigma) ** 2)
            weights /= weights.sum()
            # origin=-1 equals np.convolve(...,mode='same') for these even kernels.
            numerator = ndimage.convolve1d(values, weights, axis=1, mode="constant", origin=-1)
            denominator = ndimage.convolve1d(np.ones(BIN_COUNT, dtype=np.float64),
                                             weights, mode="constant", origin=-1)
            values = numerator / denominator[None, :, None]
    require(np.isfinite(values).all() and (values > 0).all(), "Finite positive context profiles")
    return names, values.astype(np.float32), mu.astype(np.float32)

def context_prediction(model, conditions):
    names, profiles, fallback = model
    mapping = {str(label): index for index, label in enumerate(names)}
    result = np.empty((len(conditions), BIN_COUNT, len(fallback)), dtype=np.float32)
    for row, condition in enumerate(conditions):
        index = mapping.get(str(condition))
        result[row] = fallback if index is None else profiles[index]
    require(np.isfinite(result).all() and (result > 0).all(), "Finite positive context before prescribed floor")
    return np.maximum(result, RATE_FLOOR)

def unit_log_likelihood(targets, rates):
    require(targets.shape == rates.shape and np.isfinite(rates).all() and (rates > 0).all(),
            "Full aligned finite positive likelihood support")
    # Float64 products/reduction; omitted count-factorials are common to all choices.
    result = np.sum(targets.astype(np.float64) * np.log(rates.astype(np.float64))
                    - rates, axis=(0, 1), dtype=np.float64)
    require(np.isfinite(result).all(), "Finite complete per-unit likelihoods")
    return result

def select_context(targets, conditions, fit, validation):
    statistics = profile_statistics(targets[fit], conditions[fit])
    rows, best = [], None
    for index, specification in enumerate(CONTEXTS):
        model = context_model(statistics, specification)
        predictions = context_prediction(model, conditions[validation])
        ll = float(unit_log_likelihood(targets[validation], predictions).sum(dtype=np.float64))
        rows.append({"index": index, "sigma_bins": specification[0],
                     "pseudotrials": specification[1], "ll": ll})
        if best is None or ll > rows[best]["ll"]:
            best = index
    # Reconstruct the winning inner-fit profile, with no validation-label refit.
    model = context_model(statistics, CONTEXTS[best])
    return best, context_prediction(model, conditions[validation]), rows

def smoothed_counts(counts, sigma):
    values = np.asarray(counts, dtype=np.float32)
    numerator = ndimage.gaussian_filter1d(values, sigma, axis=1, mode="constant", truncate=3.0)
    denominator = ndimage.gaussian_filter1d(np.ones(BIN_COUNT, dtype=np.float32),
                                            sigma, mode="constant", truncate=3.0)
    numerator /= denominator[None, :, None]
    return numerator

def temporal_change(smoothed):
    """0.5*(z[t+6]-z[t-6]); indices clamp inside the same140-bin trial."""
    result = np.empty_like(smoothed)
    np.subtract(smoothed[:, 2 * LAG:], smoothed[:, :-2 * LAG], out=result[:, LAG:-LAG])
    np.subtract(smoothed[:, LAG:2 * LAG], smoothed[:, :1], out=result[:, :LAG])
    np.subtract(smoothed[:, -1:], smoothed[:, -2 * LAG:-LAG], out=result[:, -LAG:])
    result *= np.float32(.5)
    return result

def reduced(values, blocked):
    if blocked:
        return values.reshape(len(values), BIN_COUNT // BLOCK, BLOCK, values.shape[2]).mean(axis=2, dtype=np.float32)
    return values

def feature_matrix(counts, blocked):
    """Four source-unit-ordered blocks; no condition/target/query adaptation."""
    n, bins, units = counts.shape
    require(bins == BIN_COUNT, "Exact original bin grid")
    length = BIN_COUNT // BLOCK if blocked else BIN_COUNT
    features = np.empty((n, length, 4 * units), dtype=np.float32)
    short = smoothed_counts(counts, 6.0)
    features[:, :, :units] = reduced(short, blocked)
    change = temporal_change(short)
    features[:, :, 3 * units:] = reduced(change, blocked)
    del change, short
    long = smoothed_counts(counts, 18.0)
    features[:, :, units:2 * units] = reduced(long, blocked)
    del long
    features[:, :, 2 * units:3 * units] = counts.mean(axis=1, keepdims=True, dtype=np.float32)
    require(np.isfinite(features).all(), "Finite complete features")
    return features.reshape(n * length, 4 * units)

def ridge_models(features, targets, alphas):
    center = features.mean(axis=0, dtype=np.float64).astype(np.float32)
    scale = np.maximum(features.std(axis=0, dtype=np.float64), 1e-5).astype(np.float32)
    output_center = targets.mean(axis=0, dtype=np.float64).astype(np.float32)
    features -= center
    features /= scale
    target_centered = targets.astype(np.float32) - output_center
    gram = (features.T @ features).astype(np.float64) / len(features)
    cross = (features.T @ target_centered).astype(np.float64) / len(features)
    require(np.isfinite(gram).all() and np.isfinite(cross).all(), "Finite ridge statistics")
    eigenvalues, eigenvectors = linalg.eigh(gram, check_finite=False)
    projection = eigenvectors.T @ cross
    models = {}
    for alpha in alphas:
        coefficients = (eigenvectors @ (projection / (np.maximum(eigenvalues, 0)[:, None] + alpha))).astype(np.float32)
        coefficients /= scale[:, None]
        intercept = output_center - center @ coefficients
        require(np.isfinite(coefficients).all() and np.isfinite(intercept).all(), "Finite fitted ridge model")
        models[alpha] = coefficients, intercept
    return models

def ridge_prediction(features, model, shape):
    coefficients, intercept = model
    result = (features @ coefficients + intercept).reshape(shape)
    require(np.isfinite(result).all(), "Finite complete neural prediction before flooring")
    return result

def blend_prediction(baseline, neural, blend):
    result = baseline + (neural - baseline) * blend
    require(np.isfinite(result).all(), "Finite blended rates before prescribed floor")
    return np.maximum(result, RATE_FLOOR)

def local_blends(targets, baseline, neural, global_blend):
    """Validation stacking with a fixed quadratic regularizer; not a confidence interval."""
    weights = np.full(targets.shape[2], global_blend, dtype=np.float32)
    best = unit_log_likelihood(targets, blend_prediction(baseline, neural, global_blend))
    rows = []
    for weight in LOCAL_BLENDS:
        ll = unit_log_likelihood(targets, blend_prediction(baseline, neural, weight))
        penalized = ll - LOCAL_PENALTY_NATS * (weight - global_blend) ** 2
        improved = penalized > best
        weights[improved] = weight
        best[improved] = penalized[improved]
        rows.append({"weight": weight, "raw_pooled_ll": float(ll.sum()),
                     "penalty_per_unit": LOCAL_PENALTY_NATS * (weight - global_blend) ** 2})
    return weights, rows
