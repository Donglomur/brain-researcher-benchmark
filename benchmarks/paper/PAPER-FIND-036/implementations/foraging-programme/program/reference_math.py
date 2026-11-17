"""FIND036 operator mathematics. No file access, author imports or import-time fit.

Inputs are the controller's clipped float64 views and binary int64 labels.
The controller owns biological support, outer splits, ordering, custody and costs.
State members are numeric-only trusted operator artifacts, never candidate models.
"""
import hashlib
import numpy as np

LAMBDAS = (0.001, 0.01, 0.1, 1.0, 10.0, 100.0)
N_NULL = 100
SCHEMA = 1
METHODS = ("bernoulli_nb", "nested_balanced_l2_logistic", "constant_half")
SOLVER_OPTIONS = {"maxiter": 10000, "maxls": 50, "ftol": 1e-12, "gtol": 1e-8}


class ReferenceUnavailable(ValueError):
    """A mandatory reference is unsupported; no replacement or row omission."""


def _array(x, dtype, ndim, name):
    if type(x) is not np.ndarray or x.dtype != np.dtype(dtype) or x.ndim != ndim:
        raise ReferenceUnavailable(name + " must be exact numeric ndarray/dtype/dimension")
    if not np.isfinite(x).all():
        raise ReferenceUnavailable(name + " must be finite")
    return x


def _features(x, n_features=None):
    _array(x, np.float64, 2, "X")
    if min(x.shape) < 1 or (n_features is not None and x.shape[1] != n_features):
        raise ReferenceUnavailable("empty or incompatible full feature view")
    if np.any(x < -5.0) or np.any(x > 5.0):
        raise ReferenceUnavailable("controller must supply source-clipped [-5,5] features")
    return x


def _labels(y, n_rows, minimum=1):
    _array(y, np.int64, 1, "y")
    if y.shape != (n_rows,) or not np.isin(y, [0, 1]).all():
        raise ReferenceUnavailable("expected aligned binary 0=avoidance, 1=escape labels")
    counts = np.bincount(y, minlength=2)
    if np.any(counts < minimum):
        raise ReferenceUnavailable("mandatory class support unavailable")
    return counts


def sigmoid(logits):
    """Finite float64 logits to probabilities; no loss-selection clipping."""
    _array(logits, np.float64, 1, "logits")
    p = np.empty_like(logits)
    positive = logits >= 0
    p[positive] = 1.0 / (1.0 + np.exp(-logits[positive]))
    expz = np.exp(logits[~positive])
    p[~positive] = expz / (1.0 + expz)
    return p


def fit_bnb(x_train, y_train):
    """Bernoulli threshold0, alpha1, and equal class priors, classes[0,1]."""
    x = _features(x_train)
    counts = _labels(y_train, len(x))
    binary = x > 0.0
    ones = np.stack([binary[y_train == c].sum(axis=0, dtype=np.float64) for c in (0, 1)])
    p = (ones + 1.0) / (counts[:, None] + 2.0)
    return {"log_p": np.log(p), "log_not_p": np.log1p(-p)}


def _validate_bnb(state):
    if type(state) is not dict or set(state) != {"log_p", "log_not_p"}:
        raise ReferenceUnavailable("BNB state keys")
    lp = _array(state["log_p"], np.float64, 2, "log_p")
    ln = _array(state["log_not_p"], np.float64, 2, "log_not_p")
    if lp.shape != ln.shape or lp.shape[0] != 2 or lp.shape[1] < 1:
        raise ReferenceUnavailable("BNB full-class shape")
    if np.any(lp >= 0) or np.any(ln >= 0) or not np.allclose(
        np.exp(lp) + np.exp(ln), 1.0, rtol=0.0, atol=1e-12
    ):
        raise ReferenceUnavailable("BNB inconsistent probabilities")
    return lp.shape[1]


def predict_bnb(state, x_query):
    d = _validate_bnb(state)
    binary = (_features(x_query, d) > 0.0).astype(np.float64)
    # Uniform log prior cancels between classes. This matches joint-log-score
    # normalization algebraically; backend/rounding parity is not established.
    with np.errstate(over="raise", invalid="raise"):
        scores = binary @ (state["log_p"] - state["log_not_p"]).T
        scores += state["log_not_p"].sum(axis=1)
        logits = scores[:, 1] - scores[:, 0]
    return sigmoid(logits)


def null_seed(session_token, fold_one_based, replicate):
    if type(session_token) is not str or not session_token or len(session_token.encode("utf8")) > 4096:
        raise ReferenceUnavailable("authenticated session token required")
    if type(fold_one_based) is not int or not 1 <= fold_one_based <= 5:
        raise ReferenceUnavailable("outer fold must be1..5")
    if type(replicate) is not int or not 0 <= replicate < N_NULL:
        raise ReferenceUnavailable("replicate must be0..99")
    text = f"FIND036|full40-null-v1|{session_token}|{fold_one_based}|{replicate}"
    return int.from_bytes(hashlib.sha256(text.encode("utf8")).digest()[:16], "big")


def native_fold(x_train, y_train, x_query, session_token, fold_one_based):
    """Return all queries, columns[real, null0,...,null99]; train order is binding."""
    _features(x_train)
    _labels(y_train, len(x_train))
    _features(x_query, x_train.shape[1])
    result = np.empty((len(x_query), 1 + N_NULL), dtype=np.float64)
    result[:, 0] = predict_bnb(fit_bnb(x_train, y_train), x_query)
    for r in range(N_NULL):
        shuffled = y_train.copy()
        rng = np.random.Generator(np.random.PCG64(null_seed(session_token, fold_one_based, r)))
        rng.shuffle(shuffled)
        result[:, r + 1] = predict_bnb(fit_bnb(x_train, shuffled), x_query)
    return result


def canonical_inner_splits(y_train):
    """Exact adopted sklearn1.6.1 semantics on this supplied training row order.

    This import is a future qualified dependency, not satisfied by local source
    construction. A different installed version is not accepted as historical.
    """
    _labels(y_train, len(y_train), minimum=3)
    try:
        import sklearn
        from sklearn.model_selection import StratifiedKFold
    except ImportError as exc:
        raise ReferenceUnavailable("qualified sklearn1.6.1 split runtime absent") from exc
    if sklearn.__version__ != "1.6.1":
        raise ReferenceUnavailable("inner split requires adopted sklearn1.6.1")
    folds = StratifiedKFold(n_splits=3, shuffle=True, random_state=623)
    return tuple((a.astype(np.int64), b.astype(np.int64)) for a, b in folds.split(
        np.zeros((len(y_train), 1), dtype=np.uint8), y_train
    ))


def validate_inner_splits(y_train, supplied, canonical):
    """Require canonical membership/order and complete disjoint validation support."""
    _labels(y_train, len(y_train), minimum=3)
    if not isinstance(supplied, (tuple, list)) or len(supplied) != 3 or len(canonical) != 3:
        raise ReferenceUnavailable("three inner folds required")
    seen = np.zeros(len(y_train), dtype=np.int64)
    full = np.arange(len(y_train), dtype=np.int64)
    for pair, expected in zip(supplied, canonical):
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise ReferenceUnavailable("inner split pair required")
        train, valid = pair
        for a in pair:
            _array(a, np.int64, 1, "inner indices")
            if len(a) == 0 or np.any(a < 0) or np.any(a >= len(y_train)) or len(np.unique(a)) != len(a):
                raise ReferenceUnavailable("invalid inner indices")
        if not np.array_equal(np.sort(np.concatenate(pair)), full):
            raise ReferenceUnavailable("inner split must partition all permitted rows")
        if not all(np.array_equal(a, b) for a, b in zip(pair, expected)):
            raise ReferenceUnavailable("inner folds differ from adopted canonical assignments/order")
        _labels(y_train[train], len(train))
        _labels(y_train[valid], len(valid))
        seen[valid] += 1
    if not np.all(seen == 1):
        raise ReferenceUnavailable("every inner row must be held out once")
    return tuple((a.copy(), b.copy()) for a, b in supplied)


def fit_scaler(x_train):
    x = _features(x_train)
    mu = x.mean(axis=0)
    scale = np.maximum(x.std(axis=0, ddof=0), 1e-8)
    return mu, scale


def logistic_objective(theta, z, y, lam):
    """Balanced training BCE +lambda||w||²/2; intercept is never penalized."""
    _array(z, np.float64, 2, "scaled training features")
    _array(theta, np.float64, 1, "theta")
    if min(z.shape) < 1 or theta.shape != (z.shape[1] + 1,):
        raise ReferenceUnavailable("logistic parameter dimension")
    counts = _labels(y, len(z))
    if type(lam) not in (int, float) or not np.isfinite(lam) or lam <= 0:
        raise ReferenceUnavailable("positive finite lambda")
    weights = 0.5 / counts[y]
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        logits = z @ theta[:-1] + theta[-1]
        losses = np.logaddexp(0.0, (1.0 - 2.0 * y) * logits)
        objective = float(weights @ losses + 0.5 * lam * (theta[:-1] @ theta[:-1]))
        residual = weights * (sigmoid(logits) - y)
        gradient = np.concatenate((z.T @ residual + lam * theta[:-1], [residual.sum()]))
    if not np.isfinite(objective) or not np.isfinite(gradient).all():
        raise ReferenceUnavailable("nonfinite logistic objective/gradient")
    return objective, gradient


def _solve(z, y, lam, minimize_impl=None):
    """Future L-BFGS-B with no bounds (unconstrained L-BFGS), strict acceptance."""
    if minimize_impl is None:
        try:
            import scipy
            from scipy.optimize import minimize
        except ImportError as exc:
            raise ReferenceUnavailable("qualified scipy1.15.3 solver absent") from exc
        if scipy.__version__ != "1.15.3":
            raise ReferenceUnavailable("solver requires adopted scipy1.15.3")
        minimize_impl = minimize
    theta0 = np.zeros(z.shape[1] + 1, dtype=np.float64)
    result = minimize_impl(logistic_objective, theta0, args=(z, y, lam), jac=True,
                           method="L-BFGS-B", options=dict(SOLVER_OPTIONS))
    if not bool(result.success):
        raise ReferenceUnavailable("mandatory logistic solver did not converge")
    theta = _array(result.x, np.float64, 1, "solver parameters")
    loss, grad = logistic_objective(theta, z, y, lam)
    grad_max = float(np.max(np.abs(grad)))
    if grad_max > 1e-5 or not 0 <= int(result.nit) <= 10000:
        raise ReferenceUnavailable("mandatory logistic final gradient/iteration guard")
    return theta.copy(), {"objective": loss, "gradient_max": grad_max, "iterations": int(result.nit)}


def selection_metrics(y, logits):
    _labels(y, len(logits))
    p = sigmoid(logits)
    pred = p >= 0.5
    ba = 0.5 * (np.mean(pred[y == 1]) + np.mean(~pred[y == 0]))
    nll = np.mean(np.logaddexp(0.0, (1.0 - 2.0 * y) * logits))
    if not np.isfinite(ba) or not np.isfinite(nll):
        raise ReferenceUnavailable("nonfinite inner selection metric")
    return float(ba), float(nll)


def select_index(ba, nll):
    for values in (ba, nll):
        _array(values, np.float64, 1, "selection metrics")
        if values.shape != (6,):
            raise ReferenceUnavailable("fixed six-lambda selection required")
    if np.any(ba < 0) or np.any(ba > 1) or np.any(nll < 0):
        raise ReferenceUnavailable("invalid selection metrics")
    return min(range(6), key=lambda k: (-float(ba[k]), float(nll[k]), -LAMBDAS[k]))


def fit_references(x_train, y_train, inner_splits=None):
    """All mandatory controls, six-by-three nested fits and one full-training refit.

    No test features/labels, outer-row indices, archive or other fold state enter.
    Supplied splits are verified against sklearn's fixed canonical assignment.
    """
    x = _features(x_train)
    _labels(y_train, len(x), minimum=3)
    canonical = canonical_inner_splits(y_train)
    splits = validate_inner_splits(y_train, canonical if inner_splits is None else inner_splits, canonical)
    ba = np.empty(6, dtype=np.float64)
    nll = np.empty(6, dtype=np.float64)
    gradients = np.empty(19, dtype=np.float64)
    iterations = np.empty(19, dtype=np.int64)
    for k, lam in enumerate(LAMBDAS):
        logits = np.empty(len(x), dtype=np.float64)
        for j, (train, valid) in enumerate(splits):
            mu, scale = fit_scaler(x[train])
            theta, check = _solve((x[train] - mu) / scale, y_train[train], lam)
            logits[valid] = ((x[valid] - mu) / scale) @ theta[:-1] + theta[-1]
            gradients[3*k+j] = check["gradient_max"]
            iterations[3*k+j] = check["iterations"]
        ba[k], nll[k] = selection_metrics(y_train, logits)
    chosen = select_index(ba, nll)
    mu, scale = fit_scaler(x)
    theta, check = _solve((x - mu) / scale, y_train, LAMBDAS[chosen])
    gradients[-1], iterations[-1] = check["gradient_max"], check["iterations"]
    bnb = fit_bnb(x, y_train)
    state = {
        "schema": np.array([SCHEMA], dtype=np.int64),
        "n_train": np.array([len(x)], dtype=np.int64),
        "selected_index": np.array([chosen], dtype=np.int64),
        "log_p": bnb["log_p"], "log_not_p": bnb["log_not_p"],
        "mean": mu, "scale": scale, "theta": theta,
        "inner_ba": ba, "inner_nll": nll,
        "gradient_max": gradients, "iterations": iterations,
    }
    validate_state(state)
    return state


def validate_state(state):
    keys = {"schema", "n_train", "selected_index", "log_p", "log_not_p", "mean", "scale",
            "theta", "inner_ba", "inner_nll", "gradient_max", "iterations"}
    if type(state) is not dict or set(state) != keys:
        raise ReferenceUnavailable("exact numeric reference state schema required")
    for key in ("schema", "n_train", "selected_index"):
        if _array(state[key], np.int64, 1, key).shape != (1,):
            raise ReferenceUnavailable("scalar state member shape")
    if state["schema"][0] != SCHEMA or state["n_train"][0] < 6:
        raise ReferenceUnavailable("state version/training support")
    d = _validate_bnb({k: state[k] for k in ("log_p", "log_not_p")})
    for key, shape in [("mean", (d,)), ("scale", (d,)), ("theta", (d+1,)),
                       ("inner_ba", (6,)), ("inner_nll", (6,)), ("gradient_max", (19,))]:
        if _array(state[key], np.float64, 1, key).shape != shape:
            raise ReferenceUnavailable("reference state full feature shape")
    if _array(state["iterations"], np.int64, 1, "iterations").shape != (19,):
        raise ReferenceUnavailable("all nineteen solve diagnostics required")
    if np.any(state["scale"] < 1e-8) or np.any(np.abs(state["mean"]) > 5):
        raise ReferenceUnavailable("invalid training scaler")
    if np.any(state["gradient_max"] < 0) or np.any(state["gradient_max"] > 1e-5):
        raise ReferenceUnavailable("unaccepted final gradient")
    if np.any(state["iterations"] < 0) or np.any(state["iterations"] > 10000):
        raise ReferenceUnavailable("unaccepted solver iterations")
    if state["selected_index"][0] != select_index(state["inner_ba"], state["inner_nll"]):
        raise ReferenceUnavailable("selection inconsistent with fixed tie-break")
    return d


def predict_references(state, x_query):
    d = validate_state(state)
    x = _features(x_query, d)
    bnb = predict_bnb({k: state[k] for k in ("log_p", "log_not_p")}, x)
    logits = ((x - state["mean"]) / state["scale"]) @ state["theta"][:-1] + state["theta"][-1]
    logistic = sigmoid(logits)
    return np.column_stack((bnb, logistic, np.full(len(x), 0.5, dtype=np.float64)))


def state_to_npz_members(state):
    """Numeric-only member mapping. Parent admits/writes a sealed operator archive."""
    validate_state(state)
    return {key: value.copy() for key, value in state.items()}


def state_from_npz_members(members):
    """Parent supplies admitted trusted arrays loaded with allow_pickle=False.

    This is not a safe general archive reader; parent must enforce member/header/
    expanded-byte bounds and provenance before materialization. No files opened.
    """
    validate_state(members)
    return {key: value.copy() for key, value in members.items()}


def retained_state_bytes(n_features):
    """Exact numeric bytes, excluding archive headers and all solver workspace."""
    if type(n_features) is not int or n_features < 1:
        raise ReferenceUnavailable("positive full feature count required")
    # 4d BNB, 2d scaler, d+1 theta,12 metrics,19 gradients,19 iterations,3 scalars.
    return 8 * (7 * n_features + 54)
