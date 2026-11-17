"""Frozen NEURAL-053 V2 reference mathematics, with no file/data execution API.

This module is imported without NumPy. Numerical entrypoints lazily import it.
Labels are canonical one-based integers, columns are labels 1..C. Only the
parent's separately admitted training workflow may call fit_reference on real
data. These generic dimension functions support small invented engineering
controls; the parent must separately enforce complete canonical support.

Reduction policy: C-contiguous float64 inputs, NumPy axis-0 sums, pinned-runtime
matmul and Cholesky. Runtime/image/BLAS/thread identity must be admitted by the
parent before authentic fitting; this source does not itself qualify it.
"""

from fractions import Fraction
import hashlib
import math
import sys


class ReferenceError(ValueError):
    """Invalid support, selected mathematics or failed numerical disposition."""


TEMPERATURES = (0.1, 1.0, 10.0)
ARMS = ("neural", "ocular", "joint", "neural_availability")
FOURIER_FEATURES = 1024
HISTORICAL_SOURCE_SHA256 = "b83b038e9f72436c99b54a35361853de04023f732837e42c8a25bf9797d68c50"


def _np():
    import numpy
    return numpy


def _integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ReferenceError(f"{name} must be an integer >= {minimum}")
    return value


def _finite(value, name):
    np = _np()
    if not np.isfinite(value).all():
        raise ReferenceError(f"nonfinite {name}; no clipping or numerical fallback")


def setting_grid():
    """Return the exact 16 base settings, in the normative total rank order."""
    result = []
    for alpha in (0.0001, 0.01, 1.0, 100.0):
        result.append({"rank": len(result), "family": "ridge", "parameters": {"alpha": alpha}})
    for gamma in (0.1, 0.5, 1.0):
        result.append({"rank": len(result), "family": "shrinkage_lda", "parameters": {"gamma": gamma}})
    for q in (0.5, 1.0, 2.0):
        for alpha in (0.01, 1.0, 100.0):
            result.append({"rank": len(result), "family": "fourier_ridge", "parameters": {"q": q, "alpha": alpha}})
    return result


def _parameters(family, parameters):
    if not isinstance(parameters, dict):
        raise ReferenceError("parameters must be an exact grid dictionary")
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in parameters.values()):
        raise ReferenceError("numeric non-boolean grid parameters required")
    if family == "historical_centroid" and parameters == {}:
        return {}
    for entry in setting_grid():
        if family == entry["family"] and parameters == entry["parameters"]:
            return dict(entry["parameters"])
    raise ReferenceError("unsupported reference family/setting; query-selected settings refused")


def _training(X, y, n_classes):
    np = _np()
    _integer(n_classes, "n_classes", 2)
    x = np.ascontiguousarray(X, dtype=np.float64)
    labels = np.asarray(y)
    if x.ndim != 2 or x.shape[0] == 0 or x.shape[1] == 0:
        raise ReferenceError("nonempty two-dimensional training matrix required")
    if labels.shape != (len(x),) or labels.dtype.kind not in ("i", "u"):
        raise ReferenceError("aligned integer labels required")
    _finite(x, "training values")
    if np.any(labels < 1) or np.any(labels > n_classes):
        raise ReferenceError("labels must use canonical integers 1..C")
    labels = labels.astype(np.int64, copy=False)
    counts = np.bincount(labels, minlength=n_classes + 1)[1:]
    if len(counts) != n_classes or np.any(counts == 0):
        raise ReferenceError("all class support required")
    if np.any(counts != counts[0]):
        raise ReferenceError("complete balanced reference fit support required")
    return x, labels, counts


def _standardize_fit(x):
    np = _np()
    n = len(x)
    mean = np.sum(x, axis=0, dtype=np.float64) / n
    centered = x - mean
    variance = np.sum(centered * centered, axis=0, dtype=np.float64) / n
    _finite(mean, "feature mean")
    _finite(variance, "feature population variance")
    if np.any(variance < 0):
        raise ReferenceError("negative feature variance")
    active = variance > 0
    inverse_scale = np.zeros(x.shape[1], dtype=np.float64)
    inverse_scale[active] = 1.0 / np.sqrt(variance[active])
    z = centered * inverse_scale
    _finite(inverse_scale, "inverse feature scale")
    _finite(z, "standardized fit values")
    return {"mean": mean, "variance": variance, "active": active,
            "inverse_scale": inverse_scale}, z


def _transform(state, X):
    np = _np()
    x = np.ascontiguousarray(X, dtype=np.float64)
    if x.ndim != 2 or x.shape[1] != len(state["mean"]):
        raise ReferenceError("finite aligned feature matrix required")
    _finite(x, "prediction/validation input")
    z = np.zeros_like(x)
    active = state["active"]
    z[:, active] = (x[:, active] - state["mean"][active]) * state["inverse_scale"][active]
    _finite(z, "transformed features")
    return z


def _class_sums(a, labels, n_classes):
    np = _np()
    out = np.empty((a.shape[1], n_classes), dtype=np.float64)
    for c in range(1, n_classes + 1):
        out[:, c - 1] = np.sum(a[labels == c], axis=0, dtype=np.float64)
    return out


def _checked_cholesky(A, B, identity):
    np = _np()
    _finite(A, identity + " system")
    _finite(B, identity + " rhs")
    try:
        L = np.linalg.cholesky(A)
        result = np.linalg.solve(L.T, np.linalg.solve(L, B))
    except np.linalg.LinAlgError as exc:
        raise ReferenceError(identity + " Cholesky failure; no retry/jitter/pseudoinverse") from exc
    _finite(result, identity + " solution")
    residual = float(np.linalg.norm(A @ result - B))
    bound = 1e-8 * max(1.0, float(np.linalg.norm(B)))
    if not math.isfinite(residual) or residual > bound:
        raise ReferenceError(identity + " residual check failed")
    return result, {"system": identity, "solver": "cholesky", "residual_frobenius": residual,
                    "residual_bound": bound}


def _ridge_coefficients(features, labels, counts, alpha, constant_columns=None):
    """Solve the exact 1/N objective, choosing a dimension-based system once.

    Primal if P<=N, dual otherwise. This is a predetermined algebraic route,
    never a numerical failure fallback. Full canonical fits take the primal.
    Class sums avoid a full N-by-C one-hot materialization in either route.
    """
    np = _np()
    n, p = features.shape
    classes = len(counts)
    center = np.sum(features, axis=0, dtype=np.float64) / n
    if constant_columns is not None:
        center[constant_columns] = features[0, constant_columns]
    zc = features - center
    if constant_columns is not None:
        zc[:, constant_columns] = 0.0
    prior = counts.astype(np.float64) / n
    sums = np.sum(zc, axis=0, dtype=np.float64)
    rhs = _class_sums(zc, labels, classes) - sums[:, None] * prior[None, :]
    regularizer = n * alpha
    if p <= n:
        A = zc.T @ zc
        A.flat[::p + 1] += regularizer
        W, solve = _checked_cholesky(A, rhs, "primal_ridge")
    else:
        K = zc @ zc.T
        K.flat[::n + 1] += regularizer
        _finite(K, "dual ridge system")
        try:
            L = np.linalg.cholesky(K)
        except np.linalg.LinAlgError as exc:
            raise ReferenceError("dual_ridge Cholesky failure; no fallback") from exc
        W = np.empty((p, classes), dtype=np.float64)
        dual_residual_squared = 0.0
        dual_rhs_squared = 0.0
        for c in range(classes):
            target = (labels == c + 1).astype(np.float64) - prior[c]
            coefficients = np.linalg.solve(L.T, np.linalg.solve(L, target))
            residual = K @ coefficients - target
            dual_residual_squared += float(residual @ residual)
            dual_rhs_squared += float(target @ target)
            W[:, c] = zc.T @ coefficients
        residual = math.sqrt(dual_residual_squared)
        bound = 1e-8 * max(1.0, math.sqrt(dual_rhs_squared))
        if not math.isfinite(residual) or residual > bound:
            raise ReferenceError("dual_ridge residual check failed")
        solve = {"system": "dual_ridge", "solver": "cholesky", "residual_frobenius": residual,
                 "residual_bound": bound, "selection": "feature_count > row_count"}
    _finite(W, "ridge weights")
    # Validate the original primal equation without needing its Gram matrix.
    original_residual = regularizer * W - rhs
    for start in range(0, n, 512):
        block = zc[start:start + 512]
        original_residual += block.T @ (block @ W)
    original_norm = float(np.linalg.norm(original_residual))
    original_bound = 1e-8 * max(1.0, float(np.linalg.norm(rhs)))
    if not math.isfinite(original_norm) or original_norm > original_bound:
        raise ReferenceError("original primal ridge equation residual failed")
    bias = prior - center @ W
    _finite(bias, "ridge intercept")
    solve.update({"original_primal_residual_frobenius": original_norm,
                  "original_primal_residual_bound": original_bound,
                  "objective_divisor": "N", "intercept_penalized": False,
                  "N_alpha": regularizer})
    return W, bias, solve


def _uniform_open(data):
    word = int.from_bytes(hashlib.sha256(data).digest()[:8], "big") >> 12
    return (word + 0.5) / (2 ** 52)


def fourier_basis(input_dim, fold_ordinal, arm):
    """Exact V2 indexed SHA256/Box-Muller law; independent of fit values."""
    np = _np()
    _integer(input_dim, "input_dim", 1)
    _integer(fold_ordinal, "fold_ordinal", 0)
    if fold_ordinal >= 4 or arm not in ARMS:
        raise ReferenceError("canonical fold/arm seed domain required")
    seed_text = f"NEURAL-053/reference-v2/rff1024/fold/{fold_ordinal}/arm/{arm}"
    seed = hashlib.sha256(seed_text.encode("ascii")).digest()
    G = np.empty((input_dim, FOURIER_FEATURES), dtype=np.float64)
    phases = np.empty(FOURIER_FEATURES, dtype=np.float64)
    for j in range(input_dim):
        for m in range(FOURIER_FEATURES):
            prefix = seed + f"/normal/{j}/{m}".encode("ascii")
            u1 = _uniform_open(prefix + b"/0")
            u2 = _uniform_open(prefix + b"/1")
            G[j, m] = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
    for m in range(FOURIER_FEATURES):
        phases[m] = 2.0 * math.pi * _uniform_open(seed + f"/phase/{m}".encode("ascii"))
    return G, phases, seed.hex()


def _freeze_arrays(value):
    np = _np()
    if isinstance(value, np.ndarray):
        value.setflags(write=False)
    elif isinstance(value, dict):
        for child in value.values():
            _freeze_arrays(child)


def fit_reference(family, parameters, X, y, n_classes, fold_ordinal, arm):
    """Fit one declared setting on already-admitted training support only."""
    np = _np()
    parameters = _parameters(family, parameters)
    _integer(fold_ordinal, "fold_ordinal")
    if fold_ordinal >= 4 or arm not in ARMS:
        raise ReferenceError("canonical fold/arm required")
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            x, labels, counts = _training(X, y, n_classes)
            state, z = _standardize_fit(x)
            n, d = x.shape
            prior = counts.astype(np.float64) / n
            result = {"schema": "neural053_reference_fit_v1", "family": family,
                      "parameters": parameters, "class_count": n_classes, "input_dim": d,
                      "training_rows": n, "per_class_count": int(counts[0]),
                      "fold_ordinal": fold_ordinal, "arm": arm, "standardization": state,
                      "runtime": {"python": sys.version, "numpy": np.__version__,
                                  "runtime_and_BLAS_qualification": "required_external_gate"}}
            if family in ("ridge", "fourier_ridge") and not state["active"].any():
                result.update({"weights": np.zeros((d, n_classes)), "bias": prior,
                               "fallback": "all_constant_inputs", "solve": {"system": "bypass_constant"}})
            elif family == "ridge":
                W, b, solve = _ridge_coefficients(z, labels, counts, parameters["alpha"])
                result.update({"weights": W, "bias": b, "solve": solve, "fallback": None})
            elif family == "fourier_ridge":
                G, phase, seed = fourier_basis(d, fold_ordinal, arm)
                ell = parameters["q"] * math.sqrt(d)
                frequencies = G / ell
                h = math.sqrt(2.0 / FOURIER_FEATURES) * np.cos(z @ frequencies + phase)
                _finite(h, "Fourier features")
                constants = np.all(h == h[0], axis=0)
                W, b, solve = _ridge_coefficients(h, labels, counts, parameters["alpha"], constants)
                result.update({"weights": W, "bias": b, "solve": solve, "fallback": None,
                               "frequencies": frequencies, "phases": phase, "fourier_seed": seed,
                               "fourier_basis_sha256": hashlib.sha256(G.tobytes(order="C")).hexdigest(),
                               "fourier_phase_sha256": hashlib.sha256(phase.tobytes(order="C")).hexdigest(),
                               "fourier_features": FOURIER_FEATURES, "ell": ell})
            elif family == "shrinkage_lda":
                if n <= n_classes:
                    raise ReferenceError("LDA requires N>C")
                active = state["active"]
                W = np.zeros((d, n_classes), dtype=np.float64)
                if not active.any():
                    b = np.full(n_classes, -math.log(n_classes), dtype=np.float64)
                    solve, fallback, tau = {"system": "bypass_constant"}, "all_constant_inputs", None
                else:
                    a = z[:, active]
                    means = _class_sums(a, labels, n_classes) / counts[None, :]
                    centered = a - means[:, labels - 1].T
                    S = (centered.T @ centered) / (n - n_classes)
                    S = (S + S.T) / 2.0
                    tau = float(np.trace(S)) / a.shape[1]
                    if not math.isfinite(tau) or tau < 0:
                        raise ReferenceError("invalid pooled covariance trace")
                    if tau == 0:
                        covariance = np.eye(a.shape[1], dtype=np.float64)
                        fallback = "zero_within_class_identity"
                    else:
                        gamma = parameters["gamma"]
                        covariance = (1.0 - gamma) * S + gamma * tau * np.eye(a.shape[1])
                        fallback = None
                    coefficients, solve = _checked_cholesky(covariance, means, "lda_shared_covariance")
                    W[active] = coefficients
                    b = -0.5 * np.sum(means * coefficients, axis=0) - math.log(n_classes)
                result.update({"weights": W, "bias": b, "solve": solve, "fallback": fallback,
                               "covariance_tau": tau, "covariance_denominator": n - n_classes})
            else:
                # Historical source has a scale=1 fallback, not the newfamily
                # inactive mask. Its fitted zero centers cancel the difference.
                historical_inverse = np.ones(d, dtype=np.float64)
                historical_inverse[state["active"]] = state["inverse_scale"][state["active"]]
                state["inverse_scale"] = historical_inverse
                zh = (x - state["mean"]) * historical_inverse
                centers = _class_sums(zh, labels, n_classes) / counts[None, :]
                W = centers / d
                b = -0.5 * np.sum(centers * centers, axis=0) / d
                result.update({"weights": W, "bias": b, "solve": {"system": "historical_class_means"},
                               "fallback": None, "fixed_temperature": 1.0,
                               "historical_source_sha256": HISTORICAL_SOURCE_SHA256})
            _finite(result["weights"], "final reference weights")
            _finite(result["bias"], "final reference bias")
            _freeze_arrays(result)
            return result
    except (FloatingPointError, OverflowError) as exc:
        raise ReferenceError("nonfinite reference arithmetic; no clipping or fallback") from exc


def score_reference(fitted, X):
    """Training/validation score path; final query uses admitted exported plan."""
    np = _np()
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            z = _transform(fitted["standardization"], X)
            if fitted["family"] == "fourier_ridge" and fitted["fallback"] is None:
                z = math.sqrt(2.0 / FOURIER_FEATURES) * np.cos(z @ fitted["frequencies"] + fitted["phases"])
            scores = z @ fitted["weights"] + fitted["bias"]
            _finite(scores, "reference scores")
            return scores
    except (FloatingPointError, OverflowError) as exc:
        raise ReferenceError("nonfinite reference scoring") from exc


def log_probabilities(scores, temperature):
    np = _np()
    if type(temperature) not in (int, float) or temperature not in TEMPERATURES:
        raise ReferenceError("temperature must be in frozen grid")
    x = np.asarray(scores, dtype=np.float64)
    if x.ndim != 2 or x.shape[1] < 2:
        raise ReferenceError("two-dimensional multiclass scores required")
    _finite(x, "scores")
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise", under="ignore"):
            scaled = x / temperature
            maximum = np.max(scaled, axis=1, keepdims=True)
            shifted = scaled - maximum
            result = shifted - np.log(np.sum(np.exp(shifted), axis=1, keepdims=True))
            _finite(result, "log probabilities")
            return result
    except FloatingPointError as exc:
        raise ReferenceError("invalid log-softmax arithmetic") from exc


def calibrated_probabilities(scores, temperature):
    """Exact stored-output convention: stable float64 then float32, no clipping."""
    np = _np()
    return np.exp(log_probabilities(scores, temperature)).astype(np.float32)


def training_only_metrics(scores, y, person_groups, n_classes, temperature,
                          expected_people=3, expected_per_person_class=10):
    """Balanced full inner support, aggregated by person then class.

    Noncanonical expected counts are only for explicitly invented controls.
    Parent must enforce 3 people, C=1854, 10 validation rows/person/class.
    """
    np = _np()
    _integer(n_classes, "n_classes", 2)
    _integer(expected_people, "expected_people", 1)
    _integer(expected_per_person_class, "expected_per_person_class", 1)
    s = np.asarray(scores, dtype=np.float64)
    labels = np.asarray(y)
    groups = np.asarray(person_groups)
    if s.ndim != 2 or s.shape[1] != n_classes or labels.shape != (len(s),) or groups.shape != (len(s),):
        raise ReferenceError("inner validation arrays must align")
    if labels.dtype.kind not in ("i", "u") or np.any(labels < 1) or np.any(labels > n_classes):
        raise ReferenceError("canonical one-based validation labels required")
    unique = np.unique(groups)
    if len(unique) != expected_people:
        raise ReferenceError("complete inner person support required")
    logs = log_probabilities(s, temperature)
    predictions = np.argmax(s, axis=1) + 1
    correct = predictions == labels
    person_losses = []
    for group in unique:
        class_losses = []
        for c in range(1, n_classes + 1):
            mask = (groups == group) & (labels == c)
            if int(mask.sum()) != expected_per_person_class:
                raise ReferenceError("complete equal person/class inner support required")
            class_losses.append(math.fsum(float(-x) for x in logs[mask, c - 1]) / expected_per_person_class)
        person_losses.append(math.fsum(class_losses) / n_classes)
    loss = math.fsum(person_losses) / expected_people
    if not math.isfinite(loss):
        raise ReferenceError("finite inner log loss required")
    count = int(np.sum(correct))
    return {"top1_fraction": [count, len(s)], "balanced_top1": count / len(s),
            "mean_log_loss": loss, "temperature": float(temperature),
            "people": expected_people, "classes": n_classes,
            "validation_rows_per_person_class": expected_per_person_class}


def select_setting(records, family=None):
    """Select from all required grid/temperature records, never best query data."""
    expected = [x for x in setting_grid() if family is None or x["family"] == family]
    if not expected:
        raise ReferenceError("unknown selection family")
    expected_pairs = {(x["rank"], t) for x in expected for t in TEMPERATURES}
    seen = set()
    candidates = []
    for record in records:
        rank, temperature = record.get("rank"), record.get("temperature")
        if type(rank) is not int or type(temperature) not in (int, float):
            raise ReferenceError("exact setting/temperature record required")
        pair = (rank, temperature)
        if pair not in expected_pairs or pair in seen:
            raise ReferenceError("unexpected or duplicate validation setting record")
        seen.add(pair)
        num, den = record["top1_fraction"]
        if type(num) is not int or type(den) is not int or den <= 0 or not 0 <= num <= den:
            raise ReferenceError("valid exact balanced correct-count fraction required")
        loss = record["mean_log_loss"]
        if type(loss) not in (int, float) or not math.isfinite(loss) or loss < 0:
            raise ReferenceError("finite nonnegative training-only loss required")
        candidates.append(((-Fraction(num, den), loss, rank, TEMPERATURES.index(temperature)), record))
    if seen != expected_pairs:
        raise ReferenceError("incomplete validation grid; surviving-family promotion refused")
    return dict(min(candidates, key=lambda pair: pair[0])[1])


class TrainingMetricAccumulator:
    """Complete training-only support, without retaining N-by-C predictions.

    support is an ordered list of (opaque_row_id, opaque_person_group, label).
    It must be independently admitted outer-training support. Each row occurs
    once across the 15 inner validations; unknown/duplicate/missing IDs refuse.
    Store only one true-class log loss and correctness bit per expected row.
    """

    def __init__(self, support, n_classes, temperature, expected_people=3,
                 expected_per_person_class=10):
        np = _np()
        _integer(n_classes, "n_classes", 2)
        _integer(expected_people, "expected_people", 1)
        _integer(expected_per_person_class, "expected_per_person_class", 1)
        if type(temperature) not in (int, float) or temperature not in TEMPERATURES:
            raise ReferenceError("frozen temperature required")
        rows = list(support)
        if len(rows) != n_classes * expected_people * expected_per_person_class:
            raise ReferenceError("complete accumulator support size required")
        self._lookup, self._groups, self._labels = {}, [], []
        for i, row in enumerate(rows):
            if not isinstance(row, (tuple, list)) or len(row) != 3:
                raise ReferenceError("support rows must be id/person/label triples")
            identity, group, label = row
            if type(identity) is not str or not identity or identity in self._lookup:
                raise ReferenceError("unique nonempty opaque row IDs required")
            if type(group) is not str or not group or type(label) is not int or not 1 <= label <= n_classes:
                raise ReferenceError("opaque person and canonical label required")
            self._lookup[identity] = i
            self._groups.append(group)
            self._labels.append(label)
        self._groups = np.asarray(self._groups)
        self._labels = np.asarray(self._labels, dtype=np.int64)
        self._people = tuple(sorted(set(self._groups.tolist())))
        if len(self._people) != expected_people:
            raise ReferenceError("complete accumulator person support required")
        self._strata = []
        for person in self._people:
            person_strata = []
            for label in range(1, n_classes + 1):
                indices = np.flatnonzero((self._groups == person) & (self._labels == label))
                if len(indices) != expected_per_person_class:
                    raise ReferenceError("complete equal person/class accumulator support required")
                person_strata.append(indices)
            self._strata.append(person_strata)
        self._loss = np.zeros(len(rows), dtype=np.float64)
        self._correct = np.zeros(len(rows), dtype=np.bool_)
        self._seen = np.zeros(len(rows), dtype=np.bool_)
        self.classes = n_classes
        self.temperature = float(temperature)
        self.per_class = expected_per_person_class

    def update(self, scores, row_ids):
        np = _np()
        identities = list(row_ids)
        if any(type(x) is not str for x in identities) or len(set(identities)) != len(identities):
            raise ReferenceError("unique opaque IDs per validation batch required")
        if any(x not in self._lookup for x in identities):
            raise ReferenceError("unknown/query row refused by training-only accumulator")
        indices = np.asarray([self._lookup[x] for x in identities], dtype=np.int64)
        if self._seen[indices].any():
            raise ReferenceError("duplicate validation row across batches")
        s = np.asarray(scores, dtype=np.float64)
        if s.shape != (len(indices), self.classes) or not len(indices):
            raise ReferenceError("nonempty complete class scores aligned with IDs required")
        logs = log_probabilities(s, self.temperature)
        losses = -logs[np.arange(len(indices)), self._labels[indices] - 1]
        correct = np.argmax(s, axis=1) + 1 == self._labels[indices]
        self._loss[indices], self._correct[indices], self._seen[indices] = losses, correct, True

    def finalize(self):
        if not self._seen.all():
            raise ReferenceError("incomplete validation support; no partial selection")
        people_losses = []
        for person in self._strata:
            class_losses = [math.fsum(float(x) for x in self._loss[indices]) / self.per_class for indices in person]
            people_losses.append(math.fsum(class_losses) / self.classes)
        loss = math.fsum(people_losses) / len(self._people)
        count = int(self._correct.sum())
        return {"top1_fraction": [count, len(self._seen)], "balanced_top1": count / len(self._seen),
                "mean_log_loss": loss, "temperature": self.temperature,
                "people": len(self._people), "classes": self.classes,
                "validation_rows_per_person_class": self.per_class}


def export_plan(fitted, temperature):
    """Produce the sibling method evaluator's immutable JSON-compatible graph."""
    np = _np()
    if type(temperature) not in (int, float) or temperature not in TEMPERATURES:
        raise ReferenceError("frozen temperature required")
    if fitted["family"] == "historical_centroid" and temperature != 1.0:
        raise ReferenceError("historical comparator uses fixed unit temperature")
    d, c = fitted["input_dim"], fitted["class_count"]
    constants, nodes = {}, []

    def constant(name, values):
        a = np.asarray(values, dtype=np.float64)
        _finite(a, "exported constant")
        constants[name] = {"dtype": "float64", "shape": list(a.shape),
                           "values": a.ravel(order="C").tolist()}
        return name

    mask = fitted["standardization"]["active"].astype(np.float64)
    nodes.append({"id": "active_input", "op": "mul_const", "input": "input",
                  "constant": constant("active_mask", mask)})
    nodes.append({"id": "center", "op": "add_const", "input": "active_input",
                  "constant": constant("negative_mean", -fitted["standardization"]["mean"] * mask)})
    nodes.append({"id": "standardized", "op": "mul_const", "input": "center",
                  "constant": constant("inverse_scale", fitted["standardization"]["inverse_scale"])})
    source = "standardized"
    if fitted["family"] == "fourier_ridge" and fitted["fallback"] is None:
        nodes.append({"id": "angles", "op": "affine", "input": source,
                      "weight": constant("frequencies", fitted["frequencies"]),
                      "bias": constant("phases", fitted["phases"])})
        nodes.append({"id": "cosines", "op": "cos", "input": "angles"})
        nodes.append({"id": "fourier", "op": "mul_const", "input": "cosines",
                      "constant": constant("fourier_scale", math.sqrt(2.0 / FOURIER_FEATURES))})
        source = "fourier"
    nodes.append({"id": "scores", "op": "affine", "input": source,
                  "weight": constant("weights", fitted["weights"]),
                  "bias": constant("bias", fitted["bias"])})
    nodes.append({"id": "temperature_scores", "op": "div_const", "input": "scores",
                  "constant": constant("temperature", float(temperature))})
    nodes.append({"id": "probabilities", "op": "softmax", "input": "temperature_scores", "axis": "classes"})
    return {"schema": "neural053_row_plan_v1", "input_dim": d, "class_count": c,
            "constants": constants, "nodes": nodes, "output": "probabilities"}
