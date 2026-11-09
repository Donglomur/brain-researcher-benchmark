"""Independent r1 successor v2: explicit PCs and cached batched direct solves.

Source-only construction. NumPy/stdlib are shared primitives, not an independent
BLAS/LAPACK implementation. Production identity, physical memory and data
admission belong to the owner. No file, network, model or provider operations.
"""
from dataclasses import dataclass, fields, is_dataclass
from types import MappingProxyType
import hashlib
import json
import math
import numpy as np

EPS = 2.0 ** -52
TINY = np.finfo(np.float64).tiny
FRACTIONS = ("0.80", "0.95", "0.99", "all")
LAMBDAS = tuple("1e" + str(i) for i in range(-6, 4))
TEMPLATES = ("all17", "early7", "late10", "avgpool", "classifier")
MEMBERS = (tuple(range(17)), tuple(range(7)), tuple(range(7, 17)), (15,), (16,))
LIMIT_KEYS = ("max_rows", "max_query_rows", "max_columns", "max_matrix_elements", "max_live_float_slots")
IDENTITY_KEYS = ("source_id", "fit_id", "query_id", "columns_id")


class NumericError(ValueError):
    """Typed refusal; code remains stable in serialized error evidence."""
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


class UndefinedMetric(NumericError):
    pass


def _fail(code, text):
    raise NumericError(code, text)


def _array(x, name, ndim=2):
    if not isinstance(x, np.ndarray) or x.dtype != np.dtype("float64") or x.ndim != ndim:
        _fail("array_schema", name + " must be a real binary64 ndarray of the declared rank")
    if any(s <= 0 for s in x.shape):
        _fail("empty_support", name + " has an empty required axis")
    # Shape/type admission must not allocate a same-shape finite mask before
    # the operation's explicit extent guard.
    if any(not math.isfinite(float(v)) for v in x.flat):
        _fail("nonfinite", name + " contains a nonfinite value")
    return x


def _finite(x, name):
    if not np.isfinite(x).all():
        _fail("nonfinite_state", name + " is not finite")
    return x


def _bounds(limits, n, m, d, slots, matrices=()):
    if not isinstance(limits, dict) or set(limits) != set(LIMIT_KEYS):
        _fail("limits_schema", "five exact explicit positive extent limits are required")
    if any(type(limits[k]) is not int or limits[k] <= 0 for k in LIMIT_KEYS):
        _fail("limits_schema", "extent limits must be positive integers, not bool")
    if n > limits["max_rows"] or m > limits["max_query_rows"] or d > limits["max_columns"]:
        _fail("extent", "row/query/column extent exceeds its admitted ceiling")
    if any(z > limits["max_matrix_elements"] for z in matrices):
        _fail("extent", "an owned matrix exceeds its admitted ceiling")
    if slots > limits["max_live_float_slots"]:
        _fail("extent", "conservative owned live float-slot requirement exceeds its ceiling")


def required_elements(operation, rows, query_rows=0, columns=0):
    """Conservative owned binary64 slots; caller arrays/BLAS/Python excluded."""
    vals = (rows, query_rows, columns)
    if any(type(v) is not int or v < 0 for v in vals) or rows == 0:
        _fail("extent_schema", "nonnegative integer dimensions and positive rows required")
    n, m, d = vals
    formulas = {
        "moments": 8 * n * d + 8 * d,
        "standardize": 12 * (n + m) * d + 12 * d,
        "gram_pair": 4 * (n * n + m * n) + 2 * (n + m) * d,
        "spectrum": 18 * n * n + 12 * n,
        "prepare_grams": 100 * (n * n + n * m) + 100 * n,
        "prepare_setting": 16 * n * n + 10 * n * m + 16 * n,
        "predict_prepared": 16 * n * n + 12 * (n + m) * d + 10 * n * m + 16 * d,
        "metrics": 12 * n * d + 12 * d,
    }
    if operation not in formulas:
        _fail("operation_schema", "unknown extent operation")
    return {"operation": operation, "owned_float_slots": formulas[operation],
            "owned_float_bytes": 8 * formulas[operation],
            "excludes": "caller arrays, Python metadata, serialization, BLAS workspace, RSS"}


def _optional_bounds(limits, operation, n, m, d):
    if limits is not None:
        _bounds(limits, n, m, d, required_elements(operation, n, m, d)["owned_float_slots"],
                (n * d, m * d))


def _sum(values):
    try:
        value = math.fsum(float(v) for v in values)
    except (OverflowError, ValueError):
        _fail("arithmetic_range", "fixed-order compensated sum is not finite")
    if not math.isfinite(value):
        _fail("arithmetic_range", "fixed-order compensated sum is not finite")
    return value


def _mean(values):
    values = tuple(float(v) for v in values)
    if not values:
        _fail("empty_support", "mean needs nonempty support")
    z = max(abs(v) for v in values)
    return 0.0 if z == 0 else (_sum(v/z for v in values)/len(values))*z


def _norm_log(a):
    """Log Frobenius norm using scaled values; -inf denotes exact zero."""
    largest = float(np.max(np.abs(a))) if a.size else 0.0
    if largest == 0:
        return -math.inf
    root = 0.0
    for v in a.flat:
        root = math.hypot(root, float(v) / largest)
    return math.log(largest) + math.log(root)


def _ratio_logs(num, den):
    if num == -math.inf:
        return 0.0
    if den == -math.inf:
        _fail("arithmetic_range", "positive numerator with zero denominator")
    try:
        result = math.exp(num - den)
    except OverflowError:
        _fail("arithmetic_range", "required ratio overflows")
    if not math.isfinite(result) or result == 0:
        _fail("arithmetic_range", "required positive ratio overflows or underflows")
    return result


def _logadd(a, b):
    if a == -math.inf:
        return b
    if b == -math.inf:
        return a
    return max(a, b) + math.log1p(math.exp(-abs(a - b)))


def _readonly(a):
    a = np.asarray(a, dtype="<f8", order="C")
    return np.frombuffer(a.tobytes(order="C"), dtype="<f8").reshape(a.shape)


def _immutable(value):
    if isinstance(value, np.ndarray):
        return _readonly(value)
    if isinstance(value, dict):
        return MappingProxyType({k: _immutable(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_immutable(v) for v in value)
    return value


def moments(values, *, limits=None):
    x = _array(values, "values")
    n, d = x.shape
    _optional_bounds(limits, "moments", n, 0, d)
    mean, variance, scale = np.zeros(d), np.zeros(d), np.zeros(d)
    constant = np.zeros(d, dtype=np.bool_)
    max_abs = np.zeros(d)
    for j in range(d):
        col = x[:, j]
        lo, hi = float(np.min(col)), float(np.max(col))
        constant[j] = lo == hi
        z = max(abs(lo), abs(hi))
        max_abs[j] = z
        if constant[j]:
            mean[j] = lo
            continue
        normalized = col / z
        center = _sum(normalized) / n
        deviation = normalized - center
        root = math.hypot(*(float(v) for v in deviation)) / math.sqrt(n)
        sd = root * z
        var = sd * sd
        mu = center * z
        if not all(math.isfinite(v) for v in (sd, var, mu)) or sd <= 0 or var <= 0:
            _fail("moment_range", "nonconstant population variance/SD cannot be represented positively and finitely")
        mean[j], variance[j], scale[j] = mu, var, sd
    return {"mean": mean, "variance": variance, "scale": scale,
            "constant": constant, "max_abs": max_abs, "count": n, "ddof": 0}


def _transform(x, state, reject_constant):
    output = np.zeros(x.shape, dtype=np.float64)
    for j in range(x.shape[1]):
        if state["constant"][j]:
            if reject_constant:
                _fail("target_zero_sd", "every required target coordinate needs positive fitting SD")
            continue
        z = state["max_abs"][j]
        with np.errstate(all="ignore"):
            output[:, j] = (x[:, j] / z - state["mean"][j] / z) / (state["scale"][j] / z)
    return _finite(output, "standardized output")


def standardize(train, other, *, limits=None):
    x, q = _array(train, "train"), _array(other, "other")
    if x.shape[1] != q.shape[1]:
        _fail("shape_join", "train and other columns differ")
    _optional_bounds(limits, "standardize", x.shape[0], q.shape[0], x.shape[1])
    state = moments(x, limits=limits)
    return {"train": _transform(x, state, False), "other": _transform(q, state, False), "moments": state}


def target_transform(train, other, *, limits=None):
    result = standardize(train, other, limits=limits)
    if bool(np.any(result["moments"]["constant"])):
        _fail("target_zero_sd", "constant fitting target is undefined")
    return result


def aggregate_trials(values, video_ids, required_video_ids, *, limits=None):
    """Equal weight for every normalized retained trial, including across sessions."""
    x = _array(values, "normalized_trials")
    _optional_bounds(limits, "moments", x.shape[0], 0, x.shape[1])
    if not isinstance(video_ids, (tuple, list)) or len(video_ids) != x.shape[0]:
        _fail("trial_join", "one video identity per trial is required")
    if not isinstance(required_video_ids, (tuple, list)) or not required_video_ids:
        _fail("trial_join", "complete ordered video support is required")
    if any(type(v) is not str or not v for v in (*video_ids, *required_video_ids)):
        _fail("trial_join", "video identifiers must be nonempty strings")
    if len(set(required_video_ids)) != len(required_video_ids) or set(video_ids) != set(required_video_ids):
        _fail("trial_join", "duplicate/missing/extra required video support")
    if limits is not None:
        _bounds(limits, x.shape[0], len(required_video_ids), x.shape[1],
                required_elements("moments", x.shape[0], 0, x.shape[1])["owned_float_slots"],
                (x.shape[0]*x.shape[1], len(required_video_ids)*x.shape[1]))
    out = np.empty((len(required_video_ids), x.shape[1]), dtype=np.float64)
    counts = []
    for i, video in enumerate(required_video_ids):
        indices = [k for k, v in enumerate(video_ids) if v == video]
        counts.append(len(indices))
        for j in range(x.shape[1]):
            z = max(abs(float(x[k, j])) for k in indices)
            out[i, j] = 0.0 if z == 0 else (_sum(x[k, j] / z for k in indices) / len(indices)) * z
    with np.errstate(all="ignore"):
        canonical = out.astype("<f4")
    if not np.isfinite(canonical).all():
        _fail("canonical_range", "one-time canonical f32 conversion is nonfinite")
    zeroed = (out != 0) & (canonical == 0)
    subnormal = (canonical != 0) & (np.abs(canonical) < np.finfo(np.float32).tiny)
    quantization = {"rounding": "nearest_even", "nonzero_to_zero_count": int(np.count_nonzero(zeroed)),
                    "subnormal_output_count": int(np.count_nonzero(subnormal)),
                    "largest_abs_binary64_rounded_to_zero": float(np.max(np.abs(out[zeroed]))) if np.any(zeroed) else 0.0}
    return {"values": canonical, "video_ids": tuple(required_video_ids), "trial_counts": tuple(counts),
            "conversion_count": 1, "quantization": quantization}


def gram_pair(train, other, *, limits):
    x, q = _array(train, "train"), _array(other, "other")
    n, d = x.shape
    m = q.shape[0]
    if q.shape[1] != d:
        _fail("shape_join", "train/query feature columns do not match")
    _bounds(limits, n, m, d, required_elements("gram_pair", n, m, d)["owned_float_slots"], (n*n, m*n))
    with np.errstate(all="ignore"):
        k, c = x @ x.T, q @ x.T
    return {"train": _finite(k, "train Gram"), "cross": _finite(c, "cross Gram")}


def _neumaier(arrays):
    total = np.zeros_like(arrays[0])
    correction = np.zeros_like(total)
    for a in arrays:
        with np.errstate(all="ignore"):
            nxt = total + a
            correction += np.where(np.abs(total) >= np.abs(a), (total - nxt) + a, (a - nxt) + total)
        _finite(nxt, "Gram sum")
        _finite(correction, "Gram compensation")
        total = nxt
    return _finite(total + correction, "compensated Gram sum")


def _symmetric(k):
    if k.shape[0] != k.shape[1] or k.shape[0] <= 1:
        _fail("gram_shape", "a square Gram with n>1 is required")
    n = k.shape[0]
    scale = max(float(np.max(np.abs(k))), 1.0)
    # Scaled subtraction avoids overflow when opposite extreme signs occur.
    discrepancy_scaled = float(np.max(np.abs(k / scale - k.T / scale)))
    allowed_scaled = 4096 * EPS * n
    if discrepancy_scaled > allowed_scaled:
        _fail("gram_asymmetry", "Gram pairwise asymmetry exceeds the frozen bound")
    discrepancy = discrepancy_scaled * scale
    return _finite(k / 2 + k.T / 2, "symmetric Gram"), discrepancy, allowed_scaled * scale


def spectrum(gram, *, limits):
    k = _array(gram, "gram")
    n = k.shape[0]
    _bounds(limits, n, 0, 0, required_elements("spectrum", n)["owned_float_slots"], (n*n,))
    k, asymmetry, asymmetry_limit = _symmetric(k)
    g = k / (n - 1)
    try:
        eigenvalues, vectors = np.linalg.eigh(g)
    except np.linalg.LinAlgError as exc:
        raise NumericError("eigensolver", "symmetric eigensolver failed") from exc
    _finite(eigenvalues, "eigenvalues"); _finite(vectors, "eigenvectors")
    order = np.argsort(-eigenvalues, kind="stable")
    eigenvalues, vectors = eigenvalues[order], vectors[:, order]
    for j in range(n):
        pivot = int(np.argmax(np.abs(vectors[:, j])))
        if vectors[pivot, j] < 0:
            vectors[:, j] *= -1
    largest = float(eigenvalues[0])
    if largest <= 0:
        _fail("zero_rank", "Gram has no positive spectral support")
    tau = 64 * EPS * n * max(largest, 1.0)
    if float(eigenvalues[-1]) < -tau:
        _fail("negative_spectrum", "Gram contains an eigenvalue below -tau")
    keep = eigenvalues > tau
    if not bool(np.any(keep)):
        _fail("zero_rank", "no eigenvalue exceeds tau")
    with np.errstate(all="ignore"):
        residual = g @ vectors - vectors * eigenvalues
        ortho = vectors.T @ vectors - np.eye(n)
    _finite(residual, "eigen residual"); _finite(ortho, "orthogonality residual")
    error = _ratio_logs(_norm_log(residual), max(_norm_log(g), math.log(TINY)))
    orthogonality = _ratio_logs(_norm_log(ortho), math.log(max(n, 1)))
    threshold = 4096 * EPS * max(n, 1)
    if error > threshold or orthogonality > threshold:
        _fail("spectral_residual", "spectral backward error or orthogonality exceeds frozen threshold")
    positive = eigenvalues[keep]
    mass = _sum(positive)
    ranks, ties, gaps = {}, {}, {}
    for fraction in FRACTIONS:
        p = len(positive)
        if fraction != "all":
            threshold_mass = float(fraction) * mass
            for i in range(len(positive)):
                if _sum(positive[:i+1]) >= threshold_mass:
                    p = i + 1
                    break
        boundary = float(eigenvalues[p-1] - eigenvalues[p]) if p < n else None
        ranks[fraction], ties[fraction], gaps[fraction] = p, boundary is not None and boundary <= tau, boundary
    condition = largest / float(positive[-1])
    if not math.isfinite(condition):
        _fail("condition_range", "retained spectral condition estimate is not finite")
    return {"gram": k, "covariance": g, "eigenvalues": eigenvalues, "vectors": vectors,
            "positive_values": positive, "positive_vectors": vectors[:, keep], "rank": len(positive),
            "tau": tau, "discarded_count": int(n-len(positive)), "discarded_signed_mass": _sum(eigenvalues[~keep]),
            "minimum_gap": float(np.min(eigenvalues[:-1]-eigenvalues[1:])),
            "fraction_ranks": ranks, "boundary_ties": ties, "boundary_gaps": gaps,
            "residual": error, "orthogonality": orthogonality, "threshold": threshold,
            "condition": condition, "maximum_asymmetry": asymmetry, "asymmetry_threshold": asymmetry_limit}


def settings(family):
    if type(family) is not str:
        _fail("family_schema", "family must be a canonical string")
    if family == "R1":
        return [{"id": "R1/fraction=.95", "family": "R1", "fraction": "0.95", "lambda": "0"}]
    if family == "R2":
        return [{"id": f"R2/fraction={f}/lambda={l}", "family": family, "fraction": f, "lambda": l}
                for f in FRACTIONS for l in LAMBDAS]
    if family == "R3":
        return [{"id": f"R3/template={t}/lambda={l}", "family": family, "template": t, "lambda": l}
                for t in TEMPLATES for l in LAMBDAS]
    _fail("family_schema", "family must be R1, R2 or R3")


def _setting(family, setting):
    if not isinstance(setting, dict) or not any(setting == s for s in settings(family)):
        _fail("setting_schema", "setting must exactly equal one canonical full-grid setting")
    return tuple(sorted(setting.items()))


def _identity(identity):
    if not isinstance(identity, dict) or set(identity) != set(IDENTITY_KEYS):
        _fail("identity_schema", "identity requires exact source_id,fit_id,query_id,columns_id keys")
    if any(type(identity[k]) is not str or not identity[k] for k in IDENTITY_KEYS):
        _fail("identity_schema", "identity values must be nonempty strings")
    return tuple((k, identity[k]) for k in IDENTITY_KEYS)


def _digest(arrays):
    h = hashlib.sha256()
    for a in arrays:
        h.update(str(a.shape).encode("ascii"))
        # Canonical C order, little endian numeric bytes; no object/pickle data.
        h.update(np.asarray(a, dtype="<f8", order="C").tobytes())
    return h.hexdigest()


@dataclass(frozen=True)
class PreparedGrams:
    identity: tuple
    content_digest: str
    n: int
    m: int
    layers_train: tuple
    layers_cross: tuple
    layer_scales: tuple
    concat_train: np.ndarray
    concat_cross: np.ndarray
    concat_spectrum: object
    templates: tuple
    owned_slots: int


@dataclass(frozen=True)
class PreparedSetting:
    identity: tuple
    content_digest: str
    setting: tuple
    n: int
    m: int
    design: np.ndarray
    query_design: np.ndarray
    normal_matrix: np.ndarray
    factor: np.ndarray
    feature_scale: float
    selected_rank: int
    spectral_state: object
    condition: float
    owned_slots: int


def prepare_grams(train_grams, cross_grams, *, limits, identity):
    join = _identity(identity)
    if not isinstance(train_grams, (tuple, list)) or not isinstance(cross_grams, (tuple, list)) or len(train_grams) != 17 or len(cross_grams) != 17:
        _fail("layer_support", "exactly all17 ordered train/cross layer Grams are required")
    train = tuple(_array(k, "train Gram") for k in train_grams)
    cross = tuple(_array(k, "cross Gram") for k in cross_grams)
    n, m = train[0].shape[0], cross[0].shape[0]
    if any(k.shape != (n, n) for k in train) or any(k.shape != (m, n) for k in cross):
        _fail("shape_join", "all17 Gram row/column dimensions must align")
    reserve = required_elements("prepare_grams", n, m)["owned_float_slots"]
    _bounds(limits, n, m, 17, reserve, (n*n, n*m))
    raw_digest = _digest((*train, *cross))
    # Validate each raw layer and retain its exact values for reconstruction.
    # Aggregate/template admission below records the actual pre-average
    # discrepancy, instead of silently removing it before spectrum().
    for k in train:
        _symmetric(k)
    scales = tuple(_sum(np.diag(k)) / n for k in train)
    if any(not math.isfinite(s) or s <= 0 for s in scales):
        _fail("layer_scale", "every one of17 layer trace/n scales must be finite and positive")
    full_train, full_cross = _neumaier(train), _neumaier(cross)
    full_spectrum = spectrum(full_train, limits=limits)
    full_train = full_spectrum["gram"]
    templates = []
    for name, indices in zip(TEMPLATES, MEMBERS):
        with np.errstate(all="ignore"):
            kt = _neumaier(tuple(train[i] / scales[i] for i in indices)) / len(indices)
            kc = _neumaier(tuple(cross[i] / scales[i] for i in indices)) / len(indices)
        _finite(kt, "normalized template"); _finite(kc, "cross template")
        template_spectrum = spectrum(kt, limits=limits)
        templates.append((name, _readonly(template_spectrum["gram"]), _readonly(kc), _immutable(template_spectrum)))
    return PreparedGrams(join, raw_digest, n, m,
                         tuple(_readonly(k) for k in train), tuple(_readonly(k) for k in cross), scales,
                         _readonly(full_train), _readonly(full_cross), _immutable(full_spectrum), tuple(templates), reserve)


def _assert_prepared(obj, cls, identity):
    if type(obj) is not cls:
        _fail("prepared_schema", "prepared object must have the exact r1 class")
    if obj.identity != _identity(identity):
        _fail("identity_join", "prepared source/fit/query/column identity differs")


def prepare_setting(prepared, family, setting, *, limits, identity):
    _assert_prepared(prepared, PreparedGrams, identity)
    canonical = _setting(family, setting)
    n, m = prepared.n, prepared.m
    reserve = required_elements("prepare_setting", n, m)["owned_float_slots"]
    _bounds(limits, n, m, 17, reserve + prepared.owned_slots, (n*n, n*m))
    lam = float(setting["lambda"])
    if family in ("R1", "R2"):
        spec = prepared.concat_spectrum
        p = spec["fraction_ranks"][setting["fraction"]]
        u, e = spec["positive_vectors"][:, :p], spec["positive_values"][:p]
        with np.errstate(all="ignore"):
            roots = np.sqrt((n-1) * e)
            design = u * roots
            query = (prepared.concat_cross @ u) / roots
        scale = math.sqrt(_sum(np.diag(prepared.concat_train)) / n) if family == "R2" else 1.0
        if not math.isfinite(scale) or scale <= 0:
            _fail("global_scale", "fitting-only global PC scale must be finite positive")
        design, query = _finite(design / scale, "PC design"), _finite(query / scale, "query PCs")
        with np.errstate(all="ignore"):
            a = design.T @ design + (n * lam) * np.eye(p)
        condition = (float(e[0])*(n-1)/(scale*scale)+n*lam) / (float(e[-1])*(n-1)/(scale*scale)+n*lam)
    else:
        _, design, query, spec = next(t for t in prepared.templates if t[0] == setting["template"])
        p, scale = n, 1.0
        a = design + (n * lam) * np.eye(n)
        # Raw signed eigenvalues are preserved for R3's original admitted K.
        ev = spec["eigenvalues"] * (n-1) + n*lam
        if not np.isfinite(ev).all() or np.any(ev <= 0):
            _fail("regularized_spectrum", "R3 original-kernel regularized spectrum is not positive finite")
        condition = float(ev[0] / ev[-1])
    _finite(a, "normal matrix")
    if not math.isfinite(condition):
        _fail("condition_range", "regularized condition estimate is not finite")
    try:
        factor = np.linalg.cholesky(a)
    except np.linalg.LinAlgError as exc:
        raise NumericError("symmetric_solve", "direct positive symmetric factorization failed") from exc
    _finite(factor, "Cholesky factor")
    # Count the retained originating Gram preparation as well: callers commonly
    # keep it alive for further settings while using this prepared setting.
    return PreparedSetting(prepared.identity, prepared.content_digest, canonical, n, m,
                           _readonly(design), _readonly(query), _readonly(a), _readonly(factor),
                           scale, p, spec, condition, reserve + prepared.owned_slots)


def triangular_work(dimension, columns):
    """Exact substitution counts; vendor packing/workspace is separately admitted."""
    if any(type(v) is not int or v <= 0 for v in (dimension, columns)):
        _fail("extent_schema", "positive integer factor dimension and target columns required")
    p, q = dimension, columns
    return {"algorithm": "numpy_vector_row_substitution_v2", "python_row_iterations": 2*p,
            "compiled_vector_matrix_calls": 2*(p-1), "product_terms": p*(p-1)*q,
            "divisions": 2*p*q, "solver_owned_float_slots": 2*p*q+4*q,
            "residual_matmul_product_terms": p*p*q, "new_factorizations": 0,
            "excludes": "caller/factor arrays, Python metadata, NumPy/BLAS packing and workspace; residual/query products reported separately"}


def _triangular_solve(l, rhs):
    """Two row sweeps; all inner products and target columns run in NumPy.

    The Cholesky factor is reused unchanged. Each dot result spans the entire
    supplied coordinate block, with two p-by-q owned outputs and O(q) vectors.
    There is no Python loop over product terms or target coordinates, and no
    solve/inverse/factorization is invoked here. BLAS workspace is not claimed
    as observed memory. predict_prepared preflights this owned array extent.
    """
    p = l.shape[0]
    forward = np.zeros_like(rhs)
    answer = np.zeros_like(rhs)
    with np.errstate(all="ignore"):
        for i in range(p):
            contribution = np.matmul(l[i, :i], forward[:i, :]) if i else 0.0
            forward[i, :] = (rhs[i, :] - contribution) / l[i, i]
    _finite(forward, "forward solution")
    with np.errstate(all="ignore"):
        for i in range(p-1, -1, -1):
            contribution = np.matmul(l[i+1:, i], answer[i+1:, :]) if i < p-1 else 0.0
            answer[i, :] = (forward[i, :] - contribution) / l[i, i]
    return _finite(answer, "direct symmetric solution")


def _backward(a, b, c):
    with np.errstate(all="ignore"):
        residual = a @ b - c
    _finite(residual, "solve residual")
    denom = _logadd(_norm_log(a) + _norm_log(b), _norm_log(c))
    error = _ratio_logs(_norm_log(residual), denom)
    threshold = 4096 * EPS * max(a.shape[0], 1)
    if error > threshold:
        _fail("solve_residual", "direct solve relative backward error exceeds frozen threshold")
    return {"backward_error": error, "threshold": threshold, "residual": residual}


def predict_prepared(prepared, targets, *, limits, identity):
    _assert_prepared(prepared, PreparedSetting, identity)
    y = _array(targets, "targets")
    n, d = y.shape
    if n != prepared.n:
        _fail("shape_join", "targets do not have the prepared fitting rows")
    reserve = required_elements("predict_prepared", n, prepared.m, d)["owned_float_slots"]
    _bounds(limits, n, prepared.m, d, reserve + prepared.owned_slots,
            (n*d, prepared.m*d, prepared.selected_rank*d, n*n, prepared.m*n))
    target_state = moments(y, limits=limits)
    mean = target_state["mean"]
    with np.errstate(all="ignore"):
        centered = y - mean
    _finite(centered, "centered targets")
    setting = dict(prepared.setting)
    with np.errstate(all="ignore"):
        rhs = centered if setting["family"] == "R3" else prepared.design.T @ centered
    _finite(rhs, "normal right hand side")
    coefficients = _triangular_solve(prepared.factor, rhs)
    diagnostics = _backward(prepared.normal_matrix, coefficients, rhs)
    with np.errstate(all="ignore"):
        prediction = prepared.query_design @ coefficients + mean
    _finite(prediction, "prediction")
    diagnostics.update({"condition": prepared.condition, "spectral_residual": prepared.spectral_state["residual"],
                        "orthogonality": prepared.spectral_state["orthogonality"],
                        "selected_rank": prepared.selected_rank, "feature_scale": prepared.feature_scale,
                        "solver_work": triangular_work(prepared.selected_rank, d)})
    state = {"schema": "neural079_r1_learned_state_v2", "identity": dict(prepared.identity),
             "feature_content_digest": prepared.content_digest, "setting": setting,
             "target_moments": target_state, "intercept": mean, "centered_targets": centered,
             "coefficients": coefficients, "coefficient_kind": "alpha" if setting["family"] == "R3" else "PC_beta",
             "design": prepared.design, "query_design": prepared.query_design,
             "normal_matrix": prepared.normal_matrix, "factor": prepared.factor, "right_hand_side": rhs,
             "spectrum": prepared.spectral_state, "feature_scale": prepared.feature_scale,
             "selected_rank": prepared.selected_rank, "target_digest": _digest((y,)),
             "solver": "numpy_vector_row_substitution_v2",
             "owned_slot_ceiling": reserve + prepared.owned_slots}
    return {"prediction": prediction, "state": state, "diagnostics": diagnostics}


def reference_predict(family, train_grams, cross_grams, targets, setting, *, limits, identity=None):
    if identity is None:
        # Content identity is honest but does not authenticate scientific row IDs.
        identity = {"source_id": "numeric-content-only", "fit_id": "unattested-fit-order",
                    "query_id": "unattested-query-order", "columns_id": "all17-unattested-source-order"}
    prepared = prepare_grams(train_grams, cross_grams, limits=limits, identity=identity)
    selected = prepare_setting(prepared, family, setting, limits=limits, identity=identity)
    return predict_prepared(selected, targets, limits=limits, identity=identity)


def pearson(prediction, target, *, limits=None):
    p, y = _array(prediction, "prediction"), _array(target, "target")
    if p.shape != y.shape or p.shape[0] <= 1:
        raise UndefinedMetric("metric_support", "Pearson requires identical shapes and at least two rows")
    n, d = p.shape
    _optional_bounds(limits, "metrics", n, 0, d)
    values = np.zeros(d)
    flags = np.zeros(d, dtype=np.bool_)
    excesses = np.zeros(d)
    for j in range(d):
        if float(np.min(y[:, j])) == float(np.max(y[:, j])):
            raise UndefinedMetric("constant_target", "Pearson is undefined for a constant required target")
        if float(np.min(p[:, j])) == float(np.max(p[:, j])):
            flags[j] = True
            continue
        normalized = []
        for a in (p[:, j], y[:, j]):
            z = float(np.max(np.abs(a)))
            a = a / z
            a = a - _sum(a) / n
            norm = math.hypot(*(float(v) for v in a))
            if norm == 0 or not math.isfinite(norm):
                raise UndefinedMetric("pearson_denominator", "centered nonconstant metric denominator is undefined")
            normalized.append(a / norm)
        r = _sum(normalized[0] * normalized[1])
        if abs(r) > 1:
            if abs(r) > 1 + 64 * EPS * n:
                raise UndefinedMetric("pearson_range", "Pearson exceeds the frozen rounding interval")
            excesses[j] = r - math.copysign(1.0, r)
            r = math.copysign(1.0, r)
        values[j] = r
    return {"values": values, "constant_prediction": flags, "rounding_excess": excesses,
            "rounding_count": int(np.count_nonzero(excesses)), "rounding_bound": 64*EPS*n}


def mse(prediction, target, fit_variance=None, *, limits=None):
    p, y = _array(prediction, "prediction"), _array(target, "target")
    if p.shape != y.shape:
        raise UndefinedMetric("metric_support", "MSE shapes differ")
    n, d = p.shape
    _optional_bounds(limits, "metrics", n, 0, d)
    if fit_variance is not None:
        v = _array(fit_variance, "fit_variance", 1)
        if v.shape != (d,) or np.any(v <= 0):
            raise UndefinedMetric("fit_variance", "normalized MSE requires positive final-fitting population variance")
    result = np.zeros(d)
    for j in range(d):
        # Subtract first: scaling two nearby large inputs separately destroys
        # their representable difference (NR1). Sterbenz-close differences are
        # exact. Only genuinely overflowing entries need the scaled fallback.
        with np.errstate(all="ignore"):
            direct = p[:, j] - y[:, j]
        finite_difference = np.isfinite(direct)
        if bool(np.all(finite_difference)):
            z = float(np.max(np.abs(direct)))
            difference = direct / z if z else direct
        else:
            z = max(float(np.max(np.abs(p[:, j]))), float(np.max(np.abs(y[:, j]))))
            difference = np.empty(n, dtype=np.float64)
            difference[finite_difference] = direct[finite_difference] / z
            overflowed = ~finite_difference
            difference[overflowed] = p[overflowed, j] / z - y[overflowed, j] / z
        if z == 0:
            continue
        mean_scaled_square = _sum(float(a)*float(a) for a in difference) / n
        if mean_scaled_square <= 0 or not math.isfinite(mean_scaled_square):
            raise UndefinedMetric("mse_underflow", "necessary positive scaled squared difference was destroyed")
        # Combine binary exponents before the final ldexp, so a representable
        # normalized MSE is retained even if its unnormalized square overflows.
        # This also avoids logarithm/exponential cancellation and its rounding.
        zm, ze = math.frexp(z)
        sm, se = math.frexp(mean_scaled_square)
        vm, ve = math.frexp(float(v[j]) if fit_variance is not None else 1.0)
        mantissa = (zm*zm)*sm/vm
        try:
            value = math.ldexp(mantissa, 2*ze+se-ve)
        except OverflowError:
            raise UndefinedMetric("mse_overflow", "required MSE overflows")
        if not math.isfinite(value) or value == 0:
            raise UndefinedMetric("mse_range", "positive required MSE overflows/underflows")
        result[j] = value
    return {"values": result, "normalized": fit_variance is not None,
            "mean": _mean(result)}


def select_setting(family, records):
    candidates = settings(family)
    if not isinstance(records, (tuple, list)) or len(records) != 5 * len(candidates):
        _fail("selection_grid", "the exact setting times five-fold grid is required")
    required = {(s["id"], fold) for s in candidates for fold in range(5)}
    observed = {}
    for record in records:
        if not isinstance(record, dict) or set(record) != {"setting_id", "fold", "score"}:
            _fail("selection_schema", "record keys must be exactly setting_id,fold,score")
        if type(record["setting_id"]) is not str or type(record["fold"]) is not int:
            _fail("selection_schema", "setting ID must be a string and fold must be int")
        if type(record["score"]) not in (int, float):
            _fail("selection_score", "every required score must be finite")
        try:
            finite_score = math.isfinite(record["score"])
        except OverflowError:
            finite_score = False
        if not finite_score:
            _fail("selection_score", "every required score must be representable and finite")
        key = record["setting_id"], record["fold"]
        if key not in required or key in observed:
            _fail("selection_grid", "unexpected or duplicate setting/fold")
        observed[key] = float(record["score"])
    if set(observed) != required:
        _fail("selection_grid", "incomplete setting/fold support")
    means = [{"setting_id": s["id"], "score": _mean(observed[(s["id"], f)] for f in range(5))} for s in candidates]
    scores = {r["setting_id"]: r["score"] for r in means}
    def rank(s):
        order = FRACTIONS.index(s["fraction"]) if family == "R2" else TEMPLATES.index(s["template"]) if family == "R3" else 0
        return (-scores[s["id"]], -float(s["lambda"]), order, s["id"])
    selected = min(candidates, key=rank)
    return {"setting": selected, "score": scores[selected["id"]], "means": means,
            "provenance": "Scalar arithmetic only; owner must independently prove full row/coordinate/evidence coverage."}


def canonical_record(value):
    """JSON-ready little-endian records. Caller preflights serialized byte size."""
    if isinstance(value, np.ndarray):
        if value.dtype == np.bool_:
            return {"dtype": "bool", "shape": list(value.shape), "data": value.tolist()}
        if value.dtype not in (np.dtype("float64"), np.dtype("float32")):
            _fail("serialization_schema", "only finite numeric/bool arrays can be serialized")
        _finite(value, "serialized numeric array")
        dtype = "<f8" if value.dtype.itemsize == 8 else "<f4"
        return {"dtype": dtype, "shape": list(value.shape), "hex": np.asarray(value, dtype=dtype, order="C").tobytes().hex()}
    if is_dataclass(value):
        return {f.name: canonical_record(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, (dict, MappingProxyType)):
        if any(type(k) is not str for k in value):
            _fail("serialization_schema", "record keys must be strings")
        return {k: canonical_record(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [canonical_record(v) for v in value]
    if value is None or type(value) in (bool, str, int):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    _fail("serialization_schema", "unsupported or nonfinite serialized object")


def canonical_json(value):
    return json.dumps(canonical_record(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
