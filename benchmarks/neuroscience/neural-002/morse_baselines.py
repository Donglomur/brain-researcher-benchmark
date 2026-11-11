"""Original NumPy baselines for the proposed Morse stimulus-ID task.

These functions fit only supplied training participants. They do not load data,
join events, choose a cohort, qualify a source clock, or enforce a sandbox.
The operator owns the exact six-cell vocabulary and the 32-person split.
"""
from dataclasses import dataclass
import re
import numpy as np

N_CLASSES = 26
EEG_SHAPE = (62, 301)
SHRINKAGE = 0.1
VARIANCE_FLOOR_RATIO = 1e-8


class BaselineError(ValueError):
    """Invalid data, split, model binding or nonfinite numerical operation."""


@dataclass(frozen=True)
class Model:
    kind: str
    cell: str
    vocabulary: tuple
    training_people: tuple
    feature_names: tuple
    centroids: np.ndarray
    variance: np.ndarray
    prior: np.ndarray
    n_training_rows: int
    fit_protocol: str = "equal_person_training_only_fixed_shrinkage_v1"


def _text(value, name):
    if not isinstance(value, str) or not value or len(value) > 128:
        raise BaselineError(name + " must be a nonempty string of at most128 characters")
    if any(ord(c) < 32 for c in value):
        raise BaselineError(name + " contains control characters")
    return value


def _vocabulary(value):
    if isinstance(value, (str, bytes)):
        raise BaselineError("vocabulary must be a sequence")
    try:
        value = tuple(_text(x, "vocabulary entry") for x in value)
    except TypeError as exc:
        raise BaselineError("vocabulary must be a sequence") from exc
    if len(value) != N_CLASSES or len(set(value)) != N_CLASSES:
        raise BaselineError("exactly26 distinct class identifiers required")
    return value


def _people(value, n):
    if isinstance(value, (str, bytes)):
        raise BaselineError("people must contain one identifier per row")
    try:
        value = tuple(_text(x, "participant") for x in value)
    except TypeError as exc:
        raise BaselineError("people must be a sequence") from exc
    if len(value) != n:
        raise BaselineError("participant count differs from row count")
    return value


def _numeric(value, shape_tail, name):
    try:
        arr = np.asarray(value)
    except (TypeError, ValueError) as exc:
        raise BaselineError(name + " is not a numeric array") from exc
    if arr.dtype.kind not in "fiu" or arr.ndim != len(shape_tail) + 1:
        raise BaselineError(name + " requires a real numeric array")
    if arr.shape[0] == 0 or arr.shape[1:] != shape_tail:
        raise BaselineError(name + " has wrong shape or no rows")
    if not np.isfinite(arr).all():
        raise BaselineError(name + " contains nonfinite values")
    try:
        arr = np.array(arr, dtype=np.float64, copy=True)
    except (TypeError, ValueError, OverflowError) as exc:
        raise BaselineError(name + " cannot be represented as float64") from exc
    if not np.isfinite(arr).all():
        raise BaselineError(name + " overflows float64")
    return arr


def _labels(value, n):
    try:
        arr = np.asarray(value)
    except (TypeError, ValueError) as exc:
        raise BaselineError("labels are not a rectangular integer array") from exc
    if arr.dtype.kind not in "iu" or arr.shape != (n,):
        raise BaselineError("labels must be a one-dimensional integer array")
    if np.any(arr < 0) or np.any(arr >= N_CLASSES):
        raise BaselineError("labels must be zero-based integers0..25")
    arr = arr.astype(np.int64, copy=True)
    if not np.array_equal(np.unique(arr), np.arange(N_CLASSES)):
        raise BaselineError("every training class must be represented")
    return arr


def _readonly(arr):
    result = np.array(arr, dtype=np.float64, copy=True)
    result.setflags(write=False)
    return result


def _train_meta(train_y, train_people, cell, vocabulary, n):
    return (_labels(train_y, n), _people(train_people, n),
            _text(cell, "cell"), _vocabulary(vocabulary))


def _prior(y, people):
    # Each participant contributes one smoothed distribution. Additional trials
    # from one person do not give that person extra weight.
    groups = sorted(set(people))
    distributions = []
    for person in groups:
        indexes = np.array([p == person for p in people])
        counts = np.bincount(y[indexes], minlength=N_CLASSES)
        distributions.append((counts + 1.0) / (counts.sum() + N_CLASSES))
    return np.mean(distributions, axis=0)


def _fit_matrix(x, y, people, cell, vocabulary, kind, names):
    groups = sorted(set(people))
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            centroids = []
            for label in range(N_CLASSES):
                person_centroids = []
                for person in groups:
                    index = np.array([p == person for p in people]) & (y == label)
                    if index.any():
                        person_centroids.append(x[index].mean(axis=0))
                centroids.append(np.mean(person_centroids, axis=0))
            centroids = np.asarray(centroids)
            # Mean class-residual squared deviation, first within participant,
            # then equally across participants. This is a declared population
            # second moment, not an unbiased covariance estimate.
            person_residuals = []
            person_total = []
            for person in groups:
                index = np.array([p == person for p in people])
                residual = x[index] - centroids[y[index]]
                person_residuals.append(np.mean(residual * residual, axis=0))
                centered = x[index] - x[index].mean(axis=0)
                person_total.append(np.mean(centered * centered, axis=0))
            pooled = np.mean(person_residuals, axis=0)
            target = float(np.mean(pooled))
            total_scale = float(np.mean(person_total))
            # Constant training arrays have a defined finite variance floor.
            reference_scale = total_scale if total_scale > 0 else 1.0
            floor = VARIANCE_FLOOR_RATIO * reference_scale
            floor = max(floor, np.finfo(float).tiny)
            variance = np.maximum((1.0 - SHRINKAGE) * pooled + SHRINKAGE * target, floor)
    except FloatingPointError as exc:
        raise BaselineError("training arithmetic overflow/invalid value") from exc
    if not np.isfinite(centroids).all() or not np.isfinite(variance).all():
        raise BaselineError("nonfinite fitted parameters")
    return Model(kind, cell, vocabulary, tuple(groups), tuple(names),
                 _readonly(centroids), _readonly(variance),
                 _readonly(_prior(y, people)), x.shape[0])


def fit(train_x, train_y, train_people, cell, vocabulary):
    """Fit equal-person ERP centroids and pooled diagonal variance.

    Input is n×62×301. Hyperparameters are fixed: diagonal variance is shrunk
    10% toward its scalar mean, with a1e-8 total-variance floor. No query labels,
    query arrays, validation fold or fitted query normalization are accepted.
    """
    x = _numeric(train_x, EEG_SHAPE, "training EEG")
    y, people, cell, vocabulary = _train_meta(train_y, train_people, cell, vocabulary, len(x))
    return _fit_matrix(x.reshape(len(x), -1), y, people, cell, vocabulary,
                       "eeg_centroid", ())


def fit_prior(train_y, train_people, cell, vocabulary):
    """Equal-person add-one training-label prior; EEG is not an input."""
    raw = np.asarray(train_y)
    if raw.ndim != 1 or len(raw) == 0:
        raise BaselineError("training labels must be nonempty and one-dimensional")
    y, people, cell, vocabulary = _train_meta(train_y, train_people, cell, vocabulary, len(raw))
    return Model("prior", cell, vocabulary, tuple(sorted(set(people))), (),
                 _readonly(np.empty((N_CLASSES, 0))), _readonly(np.empty(0)),
                 _readonly(_prior(y, people)), len(y))


def _nuisance_names(names):
    if isinstance(names, (str, bytes)):
        raise BaselineError("nuisance columns must be a sequence")
    try:
        names = tuple(names)
    except TypeError as exc:
        raise BaselineError("nuisance columns must be a sequence") from exc
    for name in names:
        _text(name, "nuisance column")
        if not re.fullmatch(r"stimulus_duration_ms|within_block_order|response_onehot_[A-Za-z0-9_]+", name):
            raise BaselineError("unsupported nuisance column")
    if not 1 <= len(names) <= 64 or len(set(names)) != len(names):
        raise BaselineError("one to64 distinct diagnostic columns required")
    return names


def _nuisance_values(value, names):
    x = _numeric(value, (len(names),), "nuisance covariates")
    response_columns = []
    for j, name in enumerate(names):
        if name == "stimulus_duration_ms" and np.any(x[:, j] <= 0):
            raise BaselineError("stimulus duration must be positive")
        if name == "within_block_order" and (np.any(x[:, j] < 1) or np.any(x[:, j] != np.floor(x[:, j]))):
            raise BaselineError("trial order must be a positive integer")
        if name.startswith("response_onehot_"):
            if not np.isin(x[:, j], (0.0, 1.0)).all():
                raise BaselineError("response columns must be binary one-hot indicators")
            response_columns.append(j)
    if response_columns and not np.all(np.sum(x[:, response_columns], axis=1) == 1):
        raise BaselineError("exactly one supplied response category per row required")
    return x


def fit_nuisance(train_values, train_y, train_people, cell, vocabulary, columns):
    """Train a separate duration/order/one-hot-response diagnostic comparator.

    Call separately for each explanatory family or an explicitly declared
    combined comparator. These covariates are never added to the EEG model.
    The operator must authenticate field meanings and select the response
    category vocabulary without query-outcome-driven fitting.
    """
    names = _nuisance_names(columns)
    x = _nuisance_values(train_values, names)
    y, people, cell, vocabulary = _train_meta(train_y, train_people, cell, vocabulary, len(x))
    return _fit_matrix(x, y, people, cell, vocabulary, "nuisance_centroid", names)


def _query(model, people, cell, n, kind):
    if type(model) is not Model or model.kind != kind:
        raise BaselineError("wrong model type")
    if _text(cell, "cell") != model.cell:
        raise BaselineError("query cell differs from fitted cell")
    people = _people(people, n)
    if set(people) & set(model.training_people):
        raise BaselineError("training and query participants overlap")
    if model.fit_protocol != "equal_person_training_only_fixed_shrinkage_v1":
        raise BaselineError("unsupported model protocol")
    return people


def _predict_matrix(model, x):
    if model.centroids.shape != (N_CLASSES, x.shape[1]) or model.variance.shape != (x.shape[1],):
        raise BaselineError("fitted feature dimensions differ")
    if not np.isfinite(model.centroids).all() or not np.isfinite(model.variance).all() or np.any(model.variance <= 0):
        raise BaselineError("invalid fitted numerical parameters")
    scores = np.empty((len(x), N_CLASSES))
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise", under="ignore"):
            for label in range(N_CLASSES):
                diff = x - model.centroids[label]
                # Uniform class priors and feature-count-normalized distance.
                scores[:, label] = -0.5 * np.mean(diff * diff / model.variance, axis=1)
            scores -= scores.max(axis=1, keepdims=True)
            probabilities = np.exp(scores)
            probabilities /= probabilities.sum(axis=1, keepdims=True)
    except FloatingPointError as exc:
        raise BaselineError("prediction arithmetic overflow/invalid value") from exc
    if not np.isfinite(probabilities).all():
        raise BaselineError("nonfinite prediction")
    return probabilities


def predict(model, query_x, query_people, cell):
    """Return n×26 probabilities. Lowest class index wins an argmax tie."""
    x = _numeric(query_x, EEG_SHAPE, "query EEG")
    _query(model, query_people, cell, len(x), "eeg_centroid")
    return _predict_matrix(model, x.reshape(len(x), -1))


def predict_prior(model, query_people, cell):
    """Return the fitted prior per query participant row, without EEG."""
    if isinstance(query_people, (str, bytes)):
        raise BaselineError("people must be a sequence")
    try:
        people = tuple(query_people)
    except TypeError as exc:
        raise BaselineError("people must be a sequence") from exc
    if not people:
        raise BaselineError("no query rows")
    _query(model, people, cell, len(people), "prior")
    prior = model.prior
    if prior.shape != (N_CLASSES,) or not np.isfinite(prior).all() or np.any(prior <= 0) or not np.isclose(prior.sum(), 1.0, rtol=0, atol=1e-12):
        raise BaselineError("invalid fitted prior")
    return np.broadcast_to(prior, (len(people), N_CLASSES)).copy()


def predict_nuisance(model, query_values, query_people, cell, columns):
    """Diagnostic only; requires the exact fitted column order."""
    names = _nuisance_names(columns)
    if type(model) is not Model or names != model.feature_names:
        raise BaselineError("diagnostic feature order differs from fit")
    x = _nuisance_values(query_values, names)
    _query(model, query_people, cell, len(x), "nuisance_centroid")
    return _predict_matrix(model, x)
