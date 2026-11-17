"""Source-only NEURAL083 reference split into training and frozen inference.

Importing this module uses only the standard library. Numerical libraries are
loaded only by a separately authorized production fit or inference. Model
serialization is the trusted worker's responsibility; do not load untrusted
pickle data. The production source is a successor to the original combined
predict function, not an empirically verified numerical-parity claim.
"""
from dataclasses import dataclass
import math

ARMS = ('EEG', 'CONTEXT', 'PERMUTED_EEG')
SETTINGS = ('target20', 'transfer0', 'target100', 'other_session20')
CALIBRATION_COUNTS = {'target20': 20, 'transfer0': 0,
                      'target100': 100, 'other_session20': 20}


def need(ok, message):
    if not ok:
        raise ValueError(message)


class ReferenceAbstained(ValueError):
    """A preserved numerical failure; the case must not receive predictions."""


@dataclass
class Readout:
    arm: str
    model: object
    weights: object = None
    mean: object = None
    sd: object = None

    def features(self, values):
        import numpy as np
        if self.arm != 'CONTEXT':
            projected = np.einsum('ntc,ck->ntk', values, self.weights)
            variance = np.var(projected, axis=1, ddof=1)
            need(np.isfinite(variance).all() and (variance > 0).all(),
                 'Positive finite projected variances')
            return np.log(variance)
        return (values - self.mean) / self.sd

    def __call__(self, values):
        return self.model.decision_function(self.features(values))


def fit_readout(x, labels, arm):
    """Same prospective CSP/logvariance/shrinkage-LDA equations as original."""
    import numpy as np
    from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
    from scipy.linalg import eigh
    y = np.asarray(labels)
    need(set(y) == {0, 1} and all((y == cls).sum() >= 2 for cls in (0, 1)),
         'Both classes with >=2 training trials')
    readout = Readout(arm, None)
    if arm != 'CONTEXT':
        covariance = []
        for cls in (0, 1):
            flat = x[y == cls].reshape(-1, 20)
            covariance.append(np.cov(flat, rowvar=False, ddof=1))
        total = covariance[0] + covariance[1]
        ridge = 1e-6 * np.trace(total) / 20
        need(np.isfinite(ridge) and ridge > 0, 'Positive finite CSP scale')
        _values, vectors = eigh(covariance[1], total + ridge * np.eye(20))
        readout.weights = vectors[:, [0, 1, -2, -1]]
    else:
        readout.mean = x.mean(0)
        readout.sd = x.std(0)
        readout.sd[readout.sd == 0] = 1
    features = readout.features(x)
    readout.model = LinearDiscriminantAnalysis(
        solver='lsqr', shrinkage='auto', priors=[.5, .5])
    readout.model.fit(features, y)
    return readout


def make_calibrator():
    from sklearn.linear_model import LogisticRegression
    return LogisticRegression(C=1., solver='lbfgs', max_iter=1000,
                              random_state=83083)


@dataclass
class ReferenceState:
    generation: str
    case: str
    setting: str
    arm: str
    kind: str
    training_count: int
    prior: float
    readout: object = None
    calibrator: object = None
    reason: str = ''

    def identity(self):
        return {key: getattr(self, key)
                for key in ('generation', 'case', 'setting', 'arm')}


def _state(v, kind, count, prior, **kwargs):
    return ReferenceState(v['generation'], v['case'], v['setting'], v['arm'],
                          kind, count, prior, **kwargs)


def validate_training(v, x):
    """Check full permitted metadata; original-source custody is external."""
    need(type(v) is dict and 'query' not in v and 'query_pin' not in v,
         'No query metadata in reference fitting')
    need(v.get('arm') in ARMS and v.get('setting') in SETTINGS,
         'Declared condition')
    for name in ('generation', 'case'):
        need(type(v.get(name)) is str and bool(v[name]), 'Case identity')
    training = v.get('training')
    need(type(training) is list and len(training) == len(x), 'Training alignment')
    need(x.shape[1:] == ((5,) if v['arm'] == 'CONTEXT' else (251, 20)),
         'Exact arm geometry')
    expected_calibration = CALIBRATION_COUNTS[v['setting']]
    need(len(training) == 10600 + expected_calibration, 'Complete training count')
    people = {}
    calibration = []
    seen = set()
    for row in training:
        need(type(row) is dict and set(row) ==
             {'trial', 'person', 'role', 'y', 'inner_fold'}, 'Exact training row')
        need(type(row['trial']) is str and row['trial'] not in seen,
             'Unique opaque training row')
        seen.add(row['trial'])
        need(type(row['person']) is str and bool(row['person']), 'Opaque person')
        need(type(row['y']) is int and row['y'] in (0, 1), 'Training binary labels')
        need(type(row['inner_fold']) is int and 0 <= row['inner_fold'] < 5,
             'Predeclared training-only folds')
        need(row['role'] in ('donor', 'calibration'), 'Declared training role')
        if row['role'] == 'calibration':
            calibration.append(row)
        else:
            people.setdefault(row['person'], []).append(row)
    need(len(people) == 53 and all(len(rows) == 200 for rows in people.values()),
         'All53 other people with both100-trial offline sessions')
    need(all(len({r['inner_fold'] for r in rows}) == 1 for rows in people.values()),
         'Donor folds preserve whole people')
    need(len(calibration) == expected_calibration, 'Exact calibration allowance')
    if calibration:
        identities = {row['person'] for row in calibration}
        need(len(identities) == 1 and not identities.intersection(people),
             'Target calibration is disjoint from donor people')
    return training


def _fit_admitted(v, x, readout_factory, calibrator_factory):
    """Algorithm kernel; only public fit supplies production admission."""
    training = v['training']
    calibration = [row['role'] == 'calibration' for row in training]
    use = calibration if any(calibration) else [True] * len(training)
    rows = [row for row, take in zip(training, use) if take]
    xx = x[use]
    y = [row['y'] for row in rows]
    prior = (float(sum(y)) + .5) / (len(y) + 1)
    if len(set(y)) < 2:
        return _state(v, 'prior', len(y), prior)
    folds = [row['inner_fold'] for row in rows]
    scores = [None] * len(y)
    for fold in range(5):
        test = [value == fold for value in folds]
        selected = [not value for value in test]
        fit_y = [value for value, keep in zip(y, selected) if keep]
        if not any(test) or any(fit_y.count(cls) < 2 for cls in (0, 1)):
            return _state(v, 'prior', len(y), prior)
        model = readout_factory(xx[selected], fit_y, v['arm'])
        held = list(model(xx[test]))
        need(len(held) == sum(test), 'Every out-of-fold decision')
        for index, value in zip((i for i, take in enumerate(test) if take), held):
            scores[index] = float(value)
    need(all(value is not None and math.isfinite(value) for value in scores),
         'Finite OOF scores')
    calibrator = calibrator_factory()
    # Lists become the same float64 two-dimensional design and integer targets
    # inside sklearn validation; no mathematical estimator setting changes.
    calibrator.fit([[value] for value in scores], y)
    if hasattr(calibrator, 'n_iter_'):
        need(max(calibrator.n_iter_) < 1000, 'Platt calibration iteration cap')
    readout = readout_factory(xx, y, v['arm'])
    return _state(v, 'fitted', len(y), prior,
                  readout=readout, calibrator=calibrator)


def _finite_array(values):
    import numpy as np
    need(type(values) is np.ndarray and values.dtype == np.dtype('<f4') and
         values.flags.c_contiguous, 'Exact contiguous float32 array')
    # Bounded validation temporaries; no transform or fitting is performed.
    for start in range(0, len(values), 128):
        need(np.isfinite(values[start:start + 128]).all(), 'Finite input values')


def fit(v, x, readout_factory=fit_readout, calibrator_factory=make_calibrator):
    """Fit using complete training-only input; never receives a query operand."""
    validate_training(v, x)
    _finite_array(x)
    selected_count = CALIBRATION_COUNTS[v['setting']] or 10600
    try:
        return _fit_admitted(v, x, readout_factory, calibrator_factory)
    except (ValueError, RuntimeError, FloatingPointError, ArithmeticError) as exc:
        return _state(v, 'abstain', selected_count, 0.,
                      reason=type(exc).__name__ + ':' + str(exc)[:200])


def infer(state, query):
    """Apply sealed state to the fixed100 query rows without fitting."""
    need(type(state) is ReferenceState and state.arm in ARMS and
         state.setting in SETTINGS, 'Typed reference state')
    need(len(query) == 100 and query.shape[1:] ==
         ((5,) if state.arm == 'CONTEXT' else (251, 20)), 'Complete query geometry')
    _finite_array(query)
    if state.kind == 'abstain':
        raise ReferenceAbstained(state.reason)
    if state.kind == 'prior':
        result = [state.prior] * 100
    else:
        need(state.kind == 'fitted', 'Declared model kind')
        decisions = list(state.readout(query))
        need(len(decisions) == 100, 'Complete query decisions')
        matrix = state.calibrator.predict_proba([[float(v)] for v in decisions])
        positive = list(state.calibrator.classes_).index(1)
        result = [float(row[positive]) for row in matrix]
    need(len(result) == 100 and all(math.isfinite(p) and 0 <= p <= 1 for p in result),
         'Finite complete probability')
    return result
