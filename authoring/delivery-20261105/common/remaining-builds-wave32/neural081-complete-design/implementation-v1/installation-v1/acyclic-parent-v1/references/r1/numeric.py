"""Independent R1 numerical source for the adopted NEURAL081 V4 equations.

Pure array computation. No operand, model, provider, filesystem or process I/O.
Historical native imports occur only inside the explicitly invoked historical path.
Source construction and invented controls do not establish scientific competence.
"""
import functools
import math

import numpy as np

CLASSES = (1, 2, 3, 4, 11, 12, 13, 14, 21, 22, 23, 24)
PEOPLE = ("P01", "P04", "P05", "P06", "P07", "P09", "P11", "P12", "P13", "P14")
FAMILIES = ("BP_LDA", "TM_LDA", "RBF_KRR")
TEMPERATURES = (1.0, 0.25, 4.0, 0.0625, 16.0, 0.015625, 64.0)
_EPS = 2.0 ** -52
_SCHEMA = "neural081_numeric_model_v1"
_LIMIT_KEYS = {"max_array_bytes", "max_workspace_bytes", "max_output_bytes"}
_MODEL_KEYS = {"schema", "family", "configuration", "class_ids", "n_train", "n_features",
               "temperature", "scaler_mean", "scaler_scale", "parameters", "diagnostics"}
_HIST = {"id": "HISTORICAL_BP_LDA", "family": "HISTORICAL_BP_LDA", "shrinkage": "AUTO",
         "alpha": None, "gamma": None}


class NumericalError(ValueError):
    """Invalid numerical input, recipe state or finite result."""


class ResourceError(NumericalError):
    """A prospective allocation exceeds its explicitly supplied ceiling."""


def _guard(fn):
    @functools.wraps(fn)
    def wrapped(*args, **kwargs):
        try:
            with np.errstate(over="raise", divide="raise", invalid="raise", under="ignore"):
                return fn(*args, **kwargs)
        except (FloatingPointError, OverflowError, ZeroDivisionError, np.linalg.LinAlgError) as exc:
            raise NumericalError("nonfinite arithmetic or declared linear solve failed") from exc
    return wrapped


def _limits(limits):
    if type(limits) is not dict or set(limits) != _LIMIT_KEYS:
        raise ResourceError("limits must have exactly the three numerical ceilings")
    if any(type(x) is not int or x <= 0 for x in limits.values()):
        raise ResourceError("limits must be positive nonboolean integer bytes")
    return limits


def _bytes(shape, itemsize=8):
    size = itemsize
    for dim in shape:
        if type(dim) is not int or dim < 0:
            raise ResourceError("invalid allocation dimension")
        size *= dim
    return size


def _plan(limits, arrays=(), workspace=0, output=0):
    """Python integer arithmetic precedes every dimension-dependent allocation."""
    _limits(limits)
    for size in arrays:
        if type(size) is not int or size < 0 or size > limits["max_array_bytes"]:
            raise ResourceError("planned array exceeds max_array_bytes")
    if workspace < 0 or workspace > limits["max_workspace_bytes"]:
        raise ResourceError("planned live numerical workspace exceeds max_workspace_bytes")
    if output < 0 or output > limits["max_output_bytes"]:
        raise ResourceError("planned result exceeds max_output_bytes")


def _array_header(x, name, ndim, kinds, shape=None):
    if type(x) is not np.ndarray or x.dtype.kind not in kinds or x.ndim != ndim:
        raise NumericalError(name + " must be an exact primitive ndarray with the declared type/rank")
    if x.dtype.hasobject or x.dtype.fields is not None or x.dtype.subdtype is not None:
        raise NumericalError(name + " cannot carry objects or structured fields")
    if x.dtype.kind == "f" and x.dtype not in (np.dtype("float32"), np.dtype("float64")):
        raise NumericalError(name + " must have native binary32/binary64 storage")
    if shape is not None and x.shape != shape:
        raise NumericalError(name + " has the wrong complete shape")
    return x


def _array(x, name, ndim, kinds, limits, shape=None):
    _array_header(x, name, ndim, kinds, shape)
    nbytes = int(x.nbytes)
    _plan(limits, (nbytes, int(x.size)), workspace=nbytes + int(x.size))
    if not bool(np.isfinite(x).all()):
        raise NumericalError(name + " contains nonfinite values")
    return x


def _float64(x, name, ndim, limits, shape=None):
    _array(x, name, ndim, "f", limits, shape)
    if x.dtype != np.dtype("float64"):
        raise NumericalError(name + " must be binary64")
    return x


def _labels(labels, n, limits, all_classes=True):
    _array(labels, "labels", 1, "iu", limits, (n,))
    found = set()
    for value in labels:
        label = int(value)
        if label not in CLASSES:
            raise NumericalError("label is not a canonical class ID")
        found.add(label)
    if all_classes and found != set(CLASSES):
        raise NumericalError("complete twelve-class support is required")
    return labels


def _finite(x, name):
    if not bool(np.isfinite(x).all()):
        raise NumericalError(name + " is nonfinite")
    return x


def _number(x, name, positive=False):
    if type(x) not in (int, float) or not math.isfinite(x) or (positive and x <= 0):
        raise NumericalError(name + " must be a finite nonboolean number" + (" > 0" if positive else ""))
    return float(x)


def configuration_grid():
    result = []
    for family in FAMILIES[:2]:
        for i, shrinkage in enumerate((0.01, 0.1, 0.5, "AUTO")):
            result.append(dict(id=family + "_" + str(i), family=family, shrinkage=shrinkage,
                               alpha=None, gamma=None))
    for i, (alpha, gamma) in enumerate((a, g) for a in (0.01, 0.1, 1.0, 10.0)
                                      for g in (1.0 / 1280.0, 1.0 / 320.0, 4.0 / 320.0)):
        result.append(dict(id="RBF_KRR_" + str(i), family="RBF_KRR", shrinkage=None,
                           alpha=alpha, gamma=gamma))
    return result


def _configuration(configuration, historical=False):
    if type(configuration) is not dict or set(configuration) != set(_HIST):
        raise NumericalError("configuration has an unsupported schema")
    if type(configuration["id"]) is not str or type(configuration["family"]) is not str:
        raise NumericalError("configuration identity must be a string")
    for key in ("shrinkage", "alpha", "gamma"):
        value = configuration[key]
        if value is not None and not (type(value) is str and value == "AUTO"):
            _number(value, key)
    for entry in ([_HIST] if historical else configuration_grid()):
        if configuration == entry:
            return entry.copy()
    raise NumericalError("configuration is not in the complete declared recipe")


def _width(family):
    if type(family) is not str:
        raise NumericalError("family must be a plain string")
    if family == "TM_LDA":
        return 1024
    if family in ("BP_LDA", "RBF_KRR", "HISTORICAL_BP_LDA"):
        return 320
    raise NumericalError("unknown feature family")


@_guard
def features(eeg, family, *, limits):
    _array(eeg, "eeg", 3, "f", limits)
    if eeg.shape[1:] != (64, 512) or eeg.shape[0] <= 0:
        raise NumericalError("features require complete [n,64,512] trials")
    n = int(eeg.shape[0]); d = _width(family)
    raw = _bytes((n, 64, 512)); spec = _bytes((n, 64, 257), 16)
    output = _bytes((n, d))
    _plan(limits, (raw, spec, output), workspace=6 * raw + 3 * spec + output + 32768,
          output=output)
    centered = np.array(eeg, dtype=np.float64, order="C", copy=True)
    centered -= centered.mean(axis=2, keepdims=True)
    _finite(centered, "trial-local centered EEG")
    if family == "TM_LDA":
        return np.ascontiguousarray(_finite(centered.reshape(n, 64, 16, 32).mean(axis=3)
                                             .reshape(n, d), "temporal features"))
    hann = (1.0 - np.cos((2.0 * math.pi / 511.0) * np.arange(512, dtype=np.float64))) / 2.0
    centered *= hann
    spectrum = np.fft.rfft(centered, axis=2)
    power = (spectrum.real * spectrum.real + spectrum.imag * spectrum.imag) / 512.0
    _finite(power, "band power spectrum")
    result = np.empty((n, 64, 5), dtype=np.float64)
    for b, (lo, hi) in enumerate(((4, 16), (16, 32), (32, 52), (52, 80), (80, 120))):
        result[:, :, b] = np.log(np.maximum(power[:, :, lo:hi].mean(axis=2), 1e-24))
    return np.ascontiguousarray(_finite(result.reshape(n, d), "band power features"))


def _scale(x):
    """Low-dimensional pure primitive for independently expected toy controls."""
    n, _ = x.shape
    if n <= 0:
        raise NumericalError("empty scaler support")
    mean = x.mean(axis=0)
    delta = x - mean
    variance = np.mean(delta * delta, axis=0)
    _finite(variance, "population variance")
    if np.any(variance < 0):
        raise NumericalError("negative population variance")
    bound = n * _EPS * variance + (n * mean * _EPS) ** 2
    _finite(bound, "near-constant bound")
    constant = variance <= bound
    scale = np.sqrt(variance)
    scale[constant] = 1.0
    z = delta / scale
    _finite(mean, "scaler mean"); _finite(scale, "scaler scale"); _finite(z, "standardized rows")
    return mean, scale, z, int(np.count_nonzero(constant))


def _symmetrize(a):
    # Copy identical upper entries instead of independently recomputing lower entries.
    for i in range(a.shape[0]):
        a[i + 1:, i] = a[i, i + 1:]
    return a


def _infnorm(a):
    if a.size == 0:
        return 0.0
    value = float(np.max(np.sum(np.abs(a), axis=1))) if a.ndim == 2 else float(np.max(np.abs(a)))
    if not math.isfinite(value):
        raise NumericalError("matrix infinity norm is nonfinite")
    return value


def _relative(numerator, denominator):
    if not math.isfinite(numerator) or not math.isfinite(denominator) or denominator < 0:
        raise NumericalError("undefined residual")
    if denominator == 0:
        if numerator != 0:
            raise NumericalError("nonzero residual with zero denominator")
        return 0.0
    value = numerator / denominator
    if not math.isfinite(value) or value > 1e-10:
        raise NumericalError("declared residual exceeds 1e-10")
    return value


def _lda_diagnostics(covariance, target, coefficients, u, s, vh):
    cutoff = _EPS * float(s[0]) if s.size else 0.0
    keep = s > cutoff
    covnorm = _infnorm(covariance); wnorm = _infnorm(coefficients)
    residual = covariance.T @ (covariance @ coefficients - target)
    normal = _relative(_infnorm(residual), covnorm * (covnorm * wnorm + _infnorm(target)))
    discarded = vh[~keep] @ coefficients
    discarded_ratio = _relative(_infnorm(discarded), max(1.0, wnorm))
    return dict(rank=int(np.count_nonzero(keep)), cutoff=cutoff,
                normal_equation_residual=normal, discarded_component_residual=discarded_ratio)


def _least_squares(covariance, target):
    u, s, vh = np.linalg.svd(covariance, full_matrices=False)
    _finite(s, "singular values")
    cutoff = _EPS * float(s[0]) if s.size else 0.0
    keep = s > cutoff
    if np.any(keep):
        coefficients = (vh[keep].T / s[keep]) @ (u[:, keep].T @ target)
    else:
        coefficients = np.zeros_like(target, dtype=np.float64)
    _finite(coefficients, "minimum-norm coefficients")
    diagnostics = _lda_diagnostics(covariance, target, coefficients, u, s, vh)
    return coefficients, diagnostics


def _auto_cov(z):
    n, d = z.shape
    _, scales, w, constant_count = _scale(z)
    v = w - w.mean(axis=0)
    empirical = _symmetrize((v.T @ v) / n)
    diagonal = np.sum(v * v, axis=0) / n
    mu = float(diagonal.sum()) / d
    dsum = float(np.einsum("ij,ij->", empirical, empirical))
    row_squares = np.sum(v * v, axis=1)
    bsum = float(np.dot(row_squares, row_squares))
    beta0 = (bsum / n - dsum) / (d * n)
    delta = (dsum - 2.0 * mu * float(diagonal.sum()) + d * mu * mu) / d
    beta = min(beta0, delta)
    shrinkage = 0.0 if beta == 0 else beta / delta
    if not math.isfinite(shrinkage) or not 0 <= shrinkage <= 1:
        raise NumericalError("classwise Ledoit-Wolf shrinkage outside [0,1]")
    empirical *= 1.0 - shrinkage
    empirical.flat[::d + 1] += shrinkage * mu
    empirical *= scales[:, None]
    empirical *= scales[None, :]
    _symmetrize(empirical)
    _finite(empirical, "restored class AUTO covariance")
    return empirical, shrinkage, scales, constant_count


def _lda(z, labels, shrinkage):
    n, d = z.shape
    means = np.empty((12, d), dtype=np.float64)
    covariance = np.zeros((d, d), dtype=np.float64)
    class_shrinkages = []; class_scales = []; constant_counts = []; counts = []
    for k, label in enumerate(CLASSES):
        rows = z[labels == label]
        counts.append(int(rows.shape[0]))
        means[k] = rows.mean(axis=0)
        if shrinkage == "AUTO":
            local, amount, scales, count = _auto_cov(rows)
            class_scales.append(scales.tolist()); constant_counts.append(count)
        else:
            residual = rows - means[k]
            local = _symmetrize((residual.T @ residual) / rows.shape[0])
            mu = float(np.trace(local)) / d
            local *= 1.0 - shrinkage
            local.flat[::d + 1] += shrinkage * mu
            amount = float(shrinkage)
        class_shrinkages.append(float(amount))
        covariance += local / 12.0
    _finite(covariance, "class-uniform covariance"); _symmetrize(covariance)
    coefficients, diagnostics = _least_squares(covariance, means.T)
    intercepts = -0.5 * np.einsum("ij,ji->i", means, coefficients) + math.log(1.0 / 12.0)
    _finite(intercepts, "LDA intercepts")
    diagnostics.update(class_counts=counts, class_shrinkages=class_shrinkages,
                       class_scales=class_scales, class_constant_features=constant_counts)
    return dict(coefficients=np.ascontiguousarray(coefficients), intercepts=np.ascontiguousarray(intercepts)), diagnostics


def _kernel(left, right, gamma, symmetric=False):
    """Direct squared differences, at most one right-support by feature temporary."""
    kernel = np.empty((left.shape[0], right.shape[0]), dtype=np.float64)
    for i in range(left.shape[0]):
        first = i + 1 if symmetric else 0
        if symmetric:
            kernel[i, i] = 1.0
        if first < right.shape[0]:
            difference = right[first:] - left[i]
            difference *= difference
            distance = np.sum(difference, axis=1)
            _finite(distance, "direct squared kernel distance")
            values = np.exp(-gamma * distance)
            kernel[i, first:] = values
            if symmetric:
                kernel[first:, i] = values
    return _finite(kernel, "RBF kernel")


def _krr(z, labels, alpha, gamma):
    n, _ = z.shape
    matrix = _kernel(z, z, gamma, symmetric=True)
    row_mean = matrix.mean(axis=1)
    grand_mean = float(row_mean.mean())
    matrix -= row_mean[:, None]
    matrix -= row_mean[None, :]
    matrix += grand_mean
    _symmetrize(matrix)
    matrix.flat[::n + 1] += alpha
    y = np.zeros((n, 12), dtype=np.float64)
    for k, label in enumerate(CLASSES):
        y[:, k] = labels == label
    class_mean = y.mean(axis=0)
    yc = y - class_mean
    chol = np.linalg.cholesky(matrix)
    dual = np.linalg.solve(chol.T, np.linalg.solve(chol, yc))
    _finite(dual, "RBF dual")
    residual = _relative(_infnorm(matrix @ dual - yc),
                         _infnorm(matrix) * _infnorm(dual) + _infnorm(yc))
    return dict(training_z=np.ascontiguousarray(z), dual=np.ascontiguousarray(dual),
                row_kernel_mean=np.ascontiguousarray(row_mean), grand_kernel_mean=grand_mean,
                class_mean=np.ascontiguousarray(class_mean)), dict(rank=n, solve_residual=residual,
                absolute_gram_alpha=float(alpha), unpenalized_intercept=True)


def _fit_budget(n, d, family, limits):
    nd = _bytes((n, d)); dd = _bytes((d, d)); nc = _bytes((n, 12))
    if family == "RBF_KRR":
        nn = _bytes((n, n))
        output = nd + nc + _bytes((n,)) + _bytes((2 * d + 12,)) + 16384
        _plan(limits, (nd, dd, nn, nc), workspace=6 * nn + 8 * nd + 32 * dd + 8 * nc + output,
              output=output)
    else:
        output = _bytes((14 * d + 12,)) + 12 * d * 32 + 16384
        _plan(limits, (nd, dd, nc, _bytes((d, 12))), workspace=8 * nd + 32 * dd + 8 * nc + output,
              output=output)


def _model(configuration, n, d, mean, scale, parameters, diagnostics):
    return dict(schema=_SCHEMA, family=configuration["family"], configuration=configuration.copy(),
                class_ids=list(CLASSES), n_train=n, n_features=d, temperature=1.0,
                scaler_mean=np.ascontiguousarray(mean), scaler_scale=np.ascontiguousarray(scale),
                parameters=parameters, diagnostics=diagnostics)


@_guard
def fit(feature_matrix, labels, configuration, *, limits):
    config = _configuration(configuration)
    x = _array_header(feature_matrix, "feature_matrix", 2, "f")
    n, d = map(int, x.shape)
    if n <= 0 or d != _width(config["family"]):
        raise NumericalError("fit requires complete family width and nonempty rows")
    _array_header(labels, "labels", 1, "iu", (n,))
    _fit_budget(n, d, config["family"], limits)
    _float64(x, "feature_matrix", 2, limits)
    _labels(labels, n, limits)
    mean, scale, z, constants = _scale(x)
    if config["family"] == "RBF_KRR":
        parameters, diagnostics = _krr(z, labels, config["alpha"], config["gamma"])
    else:
        parameters, diagnostics = _lda(z, labels, config["shrinkage"])
    diagnostics["global_constant_features"] = constants
    diagnostics["method"] = "independent_R1_V4_equations"
    return _model(config, n, d, mean, scale, parameters, diagnostics)


@_guard
def fit_historical(feature_matrix, labels, *, limits):
    x = _array_header(feature_matrix, "feature_matrix", 2, "f")
    n, d = map(int, x.shape)
    if n <= 0 or d != 320:
        raise NumericalError("historical fit requires full band-power width")
    _array_header(labels, "labels", 1, "iu", (n,))
    _fit_budget(n, d, "HISTORICAL_BP_LDA", limits)
    _float64(x, "feature_matrix", 2, limits)
    _labels(labels, n, limits)
    # This literal production path is deliberately not exercised by construction controls.
    # Package strings are necessary guards, never substitutes for owner image/source qualification.
    if np.__version__ != "2.2.6":
        raise NumericalError("historical path requires NumPy 2.2.6")
    import scipy
    import sklearn
    if scipy.__version__ != "1.15.3" or sklearn.__version__ != "1.6.1":
        raise NumericalError("historical path requires SciPy 1.15.3 and scikit-learn 1.6.1")
    from sklearn.preprocessing import StandardScaler
    from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
    scaler = StandardScaler()
    z = scaler.fit_transform(x)
    estimator = LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto", priors=np.full(12, 1.0 / 12.0))
    estimator.fit(z, labels)
    if tuple(int(v) for v in estimator.classes_) != CLASSES:
        raise NumericalError("historical class-axis mismatch")
    mean = np.array(scaler.mean_, dtype=np.float64, copy=True)
    scale = np.array(scaler.scale_, dtype=np.float64, copy=True)
    _finite(mean, "historical scaler mean"); _finite(scale, "historical scaler scale")
    _finite(scaler.var_, "historical population variance"); _finite(z, "historical standardized rows")
    if np.any(scale <= 0) or np.any(scaler.var_ < 0):
        raise NumericalError("invalid historical scaler state")
    coefficients = np.array(estimator.coef_.T, dtype=np.float64, order="C", copy=True)
    intercepts = np.array(estimator.intercept_, dtype=np.float64, order="C", copy=True)
    _finite(coefficients, "historical coefficients"); _finite(intercepts, "historical intercepts")
    u, s, vh = np.linalg.svd(estimator.covariance_, full_matrices=False)
    diagnostics = _lda_diagnostics(estimator.covariance_, estimator.means_.T, coefficients, u, s, vh)
    amounts = []; scales = []; constants = []; counts = []
    for label in CLASSES:
        rows = z[labels == label]
        _, amount, local_scale, constant = _auto_cov(rows)
        amounts.append(amount); scales.append(local_scale.tolist()); constants.append(constant)
        counts.append(int(rows.shape[0]))
    diagnostics.update(method="literal_StandardScaler_sklearn_lsqr_auto_uniform",
                       numpy_version=np.__version__, scipy_version=scipy.__version__,
                       sklearn_version=sklearn.__version__, class_shrinkages=amounts,
                       class_scales=scales, class_constant_features=constants, class_counts=counts,
                       global_constant_features=int(np.count_nonzero(scaler.var_ <=
                           n * _EPS * scaler.var_ + (n * mean * _EPS) ** 2)))
    return _model(_HIST, n, d, mean, scale,
                  dict(coefficients=coefficients, intercepts=intercepts), diagnostics)


def _json_tree(value, depth=0):
    if depth > 8:
        raise NumericalError("diagnostic nesting exceeds numeric schema")
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float and math.isfinite(value):
        return
    if type(value) is list:
        for item in value:
            _json_tree(item, depth + 1)
        return
    if type(value) is dict and all(type(k) is str for k in value):
        for item in value.values():
            _json_tree(item, depth + 1)
        return
    raise NumericalError("diagnostics must be finite non-executable JSON values")


def _retained_state_bytes(value, ceiling, depth=0):
    """Conservative full non-executable state cost; no JSON serialization/copy.

    Includes Python scalar/list/dict/string storage, container pointer slots and
    ndarray payload/header allowances. Aliases are deliberately charged per
    occurrence. This logical estimate is not an allocator/RSS measurement.
    """
    if ceiling < 0 or depth > 8:
        raise ResourceError("retained model structure exceeds workspace bound")
    if type(value) is np.ndarray:
        size = int(value.nbytes) + 256
    elif value is None or type(value) is bool:
        size = 32
    elif type(value) is int:
        size = 64 + (value.bit_length() + 7) // 8
    elif type(value) is float and math.isfinite(value):
        size = 32
    elif type(value) is str:
        size = 80 + 4 * len(value)
    elif type(value) is list:
        size = 64 + 8 * len(value)
        if size > ceiling:
            raise ResourceError("retained model list exceeds workspace bound")
        for item in value:
            size += _retained_state_bytes(item, ceiling - size, depth + 1)
    elif type(value) is dict:
        size = 256 + 64 * len(value)
        if size > ceiling:
            raise ResourceError("retained model map exceeds workspace bound")
        for key, item in value.items():
            if type(key) is not str:
                raise NumericalError("retained model keys must be strings")
            size += _retained_state_bytes(key, ceiling - size, depth + 1)
            size += _retained_state_bytes(item, ceiling - size, depth + 1)
    else:
        raise NumericalError("retained model is not finite non-executable state")
    if size > ceiling:
        raise ResourceError("complete retained model exceeds max_workspace_bytes")
    return size


def _model_inventory(model, limits):
    _limits(limits)
    if type(model) is not dict or set(model) != _MODEL_KEYS:
        raise NumericalError("model schema mismatch")
    if type(model["parameters"]) is not dict:
        raise NumericalError("parameters must be a plain map")
    arrays = []
    for key in ("scaler_mean", "scaler_scale"):
        value = model[key]
        _array_header(value, key, 1, "f")
        arrays.append(int(value.nbytes))
    for key, value in model["parameters"].items():
        if type(value) is np.ndarray:
            if value.dtype != np.dtype("float64"):
                raise NumericalError("saved numerical arrays must be binary64")
            arrays.append(int(value.nbytes))
        elif type(value) not in (int, float):
            raise NumericalError("saved parameter is not a numeric scalar or array")
    size = _retained_state_bytes(model, limits["max_workspace_bytes"])
    _plan(limits, arrays, workspace=size + max(arrays, default=0))
    return size


def _check_model(model, limits):
    if type(model) is not dict or set(model) != _MODEL_KEYS or model["schema"] != _SCHEMA:
        raise NumericalError("model schema mismatch")
    family = model["family"]
    if type(family) is not str:
        raise NumericalError("model family must be a plain string")
    config = _configuration(model["configuration"], historical=(family == "HISTORICAL_BP_LDA"))
    if family != config["family"] or type(model["class_ids"]) is not list or model["class_ids"] != list(CLASSES):
        raise NumericalError("model family or class-axis mismatch")
    if any(type(x) is not int for x in model["class_ids"]):
        raise NumericalError("model class IDs must be integers")
    n = model["n_train"]; d = model["n_features"]
    if type(n) is not int or n < 12 or type(d) is not int or d != _width(family):
        raise NumericalError("model counts/width are invalid")
    _number(model["temperature"], "model temperature", positive=True)
    mean = _float64(model["scaler_mean"], "scaler_mean", 1, limits, (d,))
    scale = _float64(model["scaler_scale"], "scaler_scale", 1, limits, (d,))
    if np.any(scale <= 0):
        raise NumericalError("model scales must be strictly positive")
    parameters = model["parameters"]
    if type(parameters) is not dict:
        raise NumericalError("parameters must be a plain map")
    if family == "RBF_KRR":
        if set(parameters) != {"training_z", "dual", "row_kernel_mean", "grand_kernel_mean", "class_mean"}:
            raise NumericalError("KRR parameter schema mismatch")
        for key, shape in (("training_z", (n, d)), ("dual", (n, 12)),
                           ("row_kernel_mean", (n,)), ("class_mean", (12,))):
            _float64(parameters[key], key, len(shape), limits, shape)
        _number(parameters["grand_kernel_mean"], "grand_kernel_mean")
        if not 0 <= parameters["grand_kernel_mean"] <= 1 or np.any(parameters["row_kernel_mean"] < 0) or np.any(parameters["row_kernel_mean"] > 1):
            raise NumericalError("invalid saved kernel means")
        _probability_row(parameters["class_mean"])
    else:
        if set(parameters) != {"coefficients", "intercepts"}:
            raise NumericalError("LDA parameter schema mismatch")
        _float64(parameters["coefficients"], "coefficients", 2, limits, (d, 12))
        _float64(parameters["intercepts"], "intercepts", 1, limits, (12,))
    if type(model["diagnostics"]) is not dict:
        raise NumericalError("diagnostics must be a plain map")
    _json_tree(model["diagnostics"])
    return config, n, d, mean, scale, parameters


@_guard
def predict_scores(model, feature_matrix, *, limits):
    state_bytes = _model_inventory(model, limits)
    _array_header(feature_matrix, "feature_matrix", 2, "f")
    _plan(limits, (int(feature_matrix.nbytes),), workspace=state_bytes + int(feature_matrix.nbytes) * 2)
    config, n, d, mean, scale, parameters = _check_model(model, limits)
    x = _float64(feature_matrix, "feature_matrix", 2, limits)
    q = int(x.shape[0])
    if q <= 0 or x.shape[1] != d:
        raise NumericalError("query shape must preserve full family width")
    out = _bytes((q, 12)); qd = _bytes((min(q, 256), d))
    state = state_bytes
    if config["family"] == "RBF_KRR":
        # One row at a time keeps exact full support while avoiding q*n*d or q*n retention.
        _plan(limits, (out, qd, _bytes((n, d)), _bytes((n,))),
              workspace=state + int(x.nbytes) + out + 3 * qd + 2 * _bytes((n, d)) + 8 * _bytes((n,)), output=out)
    else:
        _plan(limits, (out, qd), workspace=state + int(x.nbytes) + out + 3 * qd + 4 * _bytes((256, 12)), output=out)
    scores = np.empty((q, 12), dtype=np.float64)
    for first in range(0, q, 256):
        last = min(first + 256, q)
        z = (x[first:last] - mean) / scale
        _finite(z, "query standardized features")
        if config["family"] == "RBF_KRR":
            for offset, row in enumerate(z):
                kernel = _kernel(row[None, :], parameters["training_z"], config["gamma"])[0]
                query_mean = float(kernel.mean())
                kernel -= parameters["row_kernel_mean"]
                kernel -= query_mean
                kernel += parameters["grand_kernel_mean"]
                scores[first + offset] = parameters["class_mean"] + kernel @ parameters["dual"]
        else:
            scores[first:last] = z @ parameters["coefficients"] + parameters["intercepts"]
    return np.ascontiguousarray(_finite(scores, "prediction scores"))


def _probability_row(row):
    values = [float(x) for x in row]
    if any(not math.isfinite(x) or not 0 <= x <= 1 for x in values):
        raise NumericalError("probability outside finite [0,1]")
    if abs(math.fsum(values) - 1.0) > 1e-6:
        raise NumericalError("probability row sum outside canonical tolerance")


@_guard
def probabilities(scores, temperature, *, limits):
    scores = _float64(scores, "scores", 2, limits)
    if scores.shape[1] != 12 or scores.shape[0] <= 0:
        raise NumericalError("scores require nonempty [q,12]")
    temperature = _number(temperature, "temperature", positive=True)
    output = _bytes(tuple(map(int, scores.shape)))
    _plan(limits, (output,), workspace=2 * output + 4096, output=output)
    result = np.empty(scores.shape, dtype=np.float64)
    for i, row in enumerate(scores):
        maximum = max(float(x) for x in row)
        exponentials = []
        for value in row:
            adjusted = (float(value) - maximum) / temperature
            if not math.isfinite(adjusted):
                raise NumericalError("nonfinite maximum-subtracted divided score")
            exponentials.append(math.exp(adjusted))
        denominator = math.fsum(exponentials)
        if not math.isfinite(denominator) or denominator <= 0:
            raise NumericalError("invalid softmax denominator")
        for k in range(12):
            result[i, k] = exponentials[k] / denominator
        _probability_row(result[i])
    return result


def _string_list(values, name, length=None):
    if type(values) is not list or any(type(v) is not str or not v for v in values):
        raise NumericalError(name + " must be a plain list of nonempty strings")
    if length is not None and len(values) != length:
        raise NumericalError(name + " has unequal support length")


def _people_order(people_order, selection=False):
    _string_list(people_order, "people_order")
    if not people_order or (selection and len(people_order) != 9):
        raise NumericalError("people_order has incomplete biological support")
    if people_order != [p for p in PEOPLE if p in people_order]:
        raise NumericalError("people_order must be a unique canonical biological subset")


def _macro(per_person):
    count = len(per_person)
    return dict(balanced_accuracy=math.fsum(r["balanced_accuracy"] for r in per_person) / count,
                nll=math.fsum(r["nll"] for r in per_person) / count,
                per_person=per_person)


@_guard
def metrics(probabilities, labels, persons, canonical_ids, people_order, *, limits):
    probs = _array_header(probabilities, "probabilities", 2, "f")
    n = int(probs.shape[0])
    if n <= 0 or probs.shape[1] != 12:
        raise NumericalError("probabilities require complete [rows,12]")
    _array_header(labels, "labels", 1, "iu", (n,))
    _string_list(persons, "persons", n); _string_list(canonical_ids, "canonical_ids", n)
    _people_order(people_order)
    metadata = 4 * (sum(len(s) for s in canonical_ids) + sum(len(s) for s in persons)) + 256 * n
    output = 4096 * len(people_order)
    _plan(limits, (int(probs.nbytes),), workspace=int(probs.nbytes) + int(labels.nbytes) + metadata + output, output=output)
    _float64(probs, "probabilities", 2, limits)
    _labels(labels, n, limits)
    if len(set(canonical_ids)) != n or set(persons) != set(people_order):
        raise NumericalError("IDs must be unique and people roster exact")
    for row in probs:
        _probability_row(row)
    per_person = []
    for person in people_order:
        indices = sorted((i for i, who in enumerate(persons) if who == person), key=lambda i: canonical_ids[i])
        counts = [0] * 12; correct = [0] * 12; losses = []
        for i in indices:
            k = CLASSES.index(int(labels[i]))
            counts[k] += 1
            predicted = max(range(12), key=lambda c: float(probs[i, c]))
            correct[k] += int(predicted == k)
            losses.append(-math.log(max(float(probs[i, k]), 1e-12)))
        if any(c == 0 for c in counts):
            raise NumericalError("every biological person must contain every class")
        recalls = [right / count for right, count in zip(correct, counts)]
        per_person.append(dict(person=person, rows=len(indices), class_counts=counts,
                               correct_counts=correct, class_recalls=recalls,
                               balanced_accuracy=math.fsum(recalls) / 12.0,
                               nll=math.fsum(losses) / len(indices)))
    return _macro(per_person)


def _oof_metric(records, people_order, temperature, limits, stored=False):
    rows = []
    for person in people_order:
        item = records[person]
        probabilities_at_t = item["probabilities_t1"] if stored else probabilities(item["scores"], temperature, limits=limits)
        person_metric = metrics(probabilities_at_t, item["labels"], [person] * len(item["canonical_ids"]),
                                item["canonical_ids"], [person], limits=limits)
        rows.extend(person_metric["per_person"])
    return _macro(rows)


@_guard
def select(oof, people_order, *, limits):
    _limits(limits); _people_order(people_order, selection=True)
    if type(oof) is not list or len(oof) != 180:
        raise NumericalError("select requires exactly twenty by nine OOF records")
    grid = configuration_grid(); grid_ids = [c["id"] for c in grid]
    required = {"configuration_id", "person", "canonical_ids", "labels", "scores", "probabilities_t1"}
    total_bytes = 0; largest_rows = 0; metadata_bytes = 0
    for item in oof:
        if type(item) is not dict or set(item) != required:
            raise NumericalError("OOF record schema mismatch")
        if type(item["configuration_id"]) is not str or item["configuration_id"] not in grid_ids or type(item["person"]) is not str or item["person"] not in people_order:
            raise NumericalError("unknown OOF configuration/person")
        _string_list(item["canonical_ids"], "canonical_ids")
        n = len(item["canonical_ids"])
        _array_header(item["labels"], "labels", 1, "iu", (n,))
        _array_header(item["scores"], "scores", 2, "f", (n, 12))
        _array_header(item["probabilities_t1"], "probabilities_t1", 2, "f", (n, 12))
        total_bytes += int(item["scores"].nbytes + item["probabilities_t1"].nbytes + item["labels"].nbytes)
        metadata_bytes += 256 * n + 4 * sum(len(s) for s in item["canonical_ids"])
        largest_rows = max(largest_rows, n)
    output_bound = (20 * 9 + 3 * 7 * 9) * 4096 + 32768
    _plan(limits, (_bytes((largest_rows, 12)),), workspace=total_bytes + metadata_bytes + output_bound
          + _bytes((largest_rows, 12)) * 4, output=output_bound)
    lookup = {cid: {} for cid in grid_ids}; supports = {}; global_ids = set()
    for item in oof:
        cid = item["configuration_id"]; person = item["person"]; ids = item["canonical_ids"]
        _labels(item["labels"], len(ids), limits)
        _float64(item["scores"], "scores", 2, limits, (len(ids), 12))
        _float64(item["probabilities_t1"], "probabilities_t1", 2, limits, (len(ids), 12))
        if person in lookup[cid] or len(set(ids)) != len(ids):
            raise NumericalError("duplicate OOF pair or private support ID")
        mapping = {identity: int(label) for identity, label in zip(ids, item["labels"])}
        if person not in supports:
            if global_ids.intersection(mapping):
                raise NumericalError("OOF person support is not disjoint")
            global_ids.update(mapping); supports[person] = mapping
        elif supports[person] != mapping:
            raise NumericalError("OOF setting changes person ID-to-label support")
        actual = probabilities(item["scores"], 1.0, limits=limits)
        if not np.array_equal(actual, item["probabilities_t1"]):
            raise NumericalError("stored T1 probabilities disagree with this source")
        lookup[cid][person] = item
    if any(set(records) != set(people_order) for records in lookup.values()):
        raise NumericalError("incomplete OOF pair roster")
    settings = []
    for config in grid:
        value = _oof_metric(lookup[config["id"]], people_order, 1.0, limits, stored=True)
        settings.append(dict(configuration_id=config["id"], family=config["family"], **value))
    selected = []; scans = []; temperatures = []
    for family in FAMILIES:
        ranked = [(i, s) for i, s in enumerate(settings) if s["family"] == family]
        _, chosen = min(ranked, key=lambda pair: (-pair[1]["balanced_accuracy"], pair[1]["nll"], pair[0]))
        cid = chosen["configuration_id"]
        selected.append({key: chosen[key] for key in ("family", "configuration_id", "balanced_accuracy", "nll")})
        family_scans = []
        for temperature in TEMPERATURES:
            value = _oof_metric(lookup[cid], people_order, temperature, limits)
            record = dict(family=family, configuration_id=cid, temperature=temperature, **value)
            scans.append(record); family_scans.append(record)
        _, chosen_t = min(enumerate(family_scans), key=lambda pair: (pair[1]["nll"], pair[0]))
        temperatures.append({key: chosen_t[key] for key in ("family", "configuration_id", "temperature", "balanced_accuracy", "nll")})
    _, strongest = min(enumerate(temperatures), key=lambda pair: (-pair[1]["balanced_accuracy"], pair[1]["nll"], pair[0]))
    return dict(setting_scores=settings, selected_per_family=selected, temperature_scores=scans,
                selected_temperatures=temperatures, strongest_family=strongest["family"])


@_guard
def analytic_priors(labels, *, limits):
    if type(labels) is not np.ndarray or labels.ndim != 1:
        raise NumericalError("labels must be an exact integer vector")
    _labels(labels, int(labels.shape[0]), limits)
    _plan(limits, (_bytes((12,)),), workspace=int(labels.nbytes) + 4096, output=192)
    counts = [sum(int(v) == label for v in labels) for label in CLASSES]
    n = int(labels.shape[0])
    uniform = np.full(12, 1.0 / 12.0, dtype=np.float64)
    laplace = np.array([(count + 1.0) / (n + 12.0) for count in counts], dtype=np.float64)
    _probability_row(uniform); _probability_row(laplace)
    return dict(uniform=uniform, laplace=laplace)
