"""Train-only matched ridge references. Source implementation, never run in BUILD ONLY."""
from dataclasses import dataclass
import math
from .partition import Fold, Trial
from .prediction_schema import ARMS

ALPHAS = (0.1, 1.0, 10.0)
EEG_FEATURES = 96

@dataclass(frozen=True)
class Observation:
    identity: Trial
    contrast_trigger: int
    eeg: tuple
    rt_seconds: object

@dataclass(frozen=True)
class FrozenRidge:
    arm: str
    alpha: float
    training_ids: tuple
    feature_mean: object
    feature_scale: object
    coefficient: object
    target_mean: float

def key(row):
    t = row.identity
    return (t.person, t.session, t.trial)

def check_rows(rows, expected_ids, labels, arm):
    rows = tuple(rows)
    if arm not in ARMS or len(rows) != len(expected_ids):
        raise ValueError("exact arm/row roster")
    if len(set(expected_ids)) != len(expected_ids):
        raise ValueError("duplicate expected source identity")
    out = {}
    for r in rows:
        if type(r) is not Observation or type(r.identity) is not Trial:
            raise ValueError("source observation type")
        if type(r.identity.person) is not int or not 0 <= r.identity.person < 26:
            raise ValueError("source person type")
        if r.identity.instruction not in ("speed", "accuracy"):
            raise ValueError("instruction")
        if type(r.contrast_trigger) is not int or not 0 < r.contrast_trigger < 99:
            raise ValueError("original base contrast trigger")
        if key(r) in out:
            raise ValueError("duplicate observation")
        if labels:
            if (type(r.rt_seconds) not in (int, float) or not math.isfinite(r.rt_seconds)
                    or r.rt_seconds <= 0.1):
                raise ValueError("finite observed at-risk training target")
        elif r.rt_seconds is not None:
            raise ValueError("query target must be absent before prediction")
        if arm == "eeg":
            if (type(r.eeg) is not tuple or len(r.eeg) != EEG_FEATURES
                    or any(type(v) not in (int, float) or not math.isfinite(v) for v in r.eeg)):
                raise ValueError("fixed EEG features")
        elif r.eeg != ():
            raise ValueError("comparator receives no EEG")
        out[key(r)] = r
    if set(out) != set(expected_ids):
        raise ValueError("source identity join")
    return tuple(out[k] for k in expected_ids)

def features(rows, arm):
    values = []
    for r in rows:
        contrast = r.contrast_trigger / 100.0
        instruction = float(r.identity.instruction == "accuracy")
        # No side, response, correctness, block/order, person or timing feature.
        base = (contrast, instruction, contrast * instruction)
        values.append(base + (r.eeg if arm == "eeg" else ()))
    return values

def _fit(rows, arm, alpha):
    import numpy as np
    x = np.asarray(features(rows, arm), dtype=np.float64)
    y = np.asarray([r.rt_seconds for r in rows], dtype=np.float64)
    counts = {}
    for r in rows:
        counts[r.identity.person] = counts.get(r.identity.person, 0) + 1
    weight = np.asarray([1.0 / (len(counts) * counts[r.identity.person])
                         for r in rows], dtype=np.float64)
    mean = np.sum(x * weight[:, None], axis=0)
    scale = np.sqrt(np.sum(((x - mean) ** 2) * weight[:, None], axis=0))
    scale[scale == 0] = 1.0
    z = (x - mean) / scale
    ymean = float(np.sum(weight * y))
    gram = z.T @ (weight[:, None] * z)
    coefficient = np.linalg.solve(gram + alpha * np.eye(gram.shape[0]),
                                  z.T @ (weight * (y - ymean)))
    if not all(np.all(np.isfinite(a)) for a in (mean, scale, coefficient)) or not math.isfinite(ymean):
        raise ValueError("nonfinite training state")
    for a in (mean, scale, coefficient):
        a.flags.writeable = False
    return FrozenRidge(arm, alpha, tuple(key(r) for r in rows),
                       mean, scale, coefficient, ymean)

def _predict(model, rows):
    import numpy as np
    x = np.asarray(features(rows, model.arm), dtype=np.float64)
    values = model.target_mean + ((x - model.feature_mean) / model.feature_scale) @ model.coefficient
    if not np.all(np.isfinite(values)):
        raise ValueError("nonfinite reference predictions")
    # Fixed support projection; no target access or fitted query transform.
    lower = math.nextafter(0.1, math.inf)
    return tuple(max(lower, float(v)) for v in values)

def fit_reference(training_rows, fold, arm):
    """25-person outer training, each complete inner person held out in turn."""
    if (type(fold) is not Fold or type(fold.held_person) is not int
            or not 0 <= fold.held_person < 26):
        raise ValueError("compiled fold")
    rows = check_rows(training_rows, fold.training, True, arm)
    expected_people = set(range(26)) - {fold.held_person}
    if {r.identity.person for r in rows} != expected_people:
        raise ValueError("all25 training people and no held person")
    if (len(fold.inner) != 25
            or {p for p, _, _ in fold.inner} != expected_people):
        raise ValueError("complete25 inner folds")
    by_key = {key(r): r for r in rows}
    losses = []
    for alpha in ALPHAS:
        person_losses = []
        for person, train_ids, validation_ids in fold.inner:
            train = tuple(by_key[k] for k in train_ids)
            validation = tuple(by_key[k] for k in validation_ids)
            if (len(set(train_ids)) != len(train_ids)
                    or len(set(validation_ids)) != len(validation_ids)
                    or set(train_ids) & set(validation_ids)
                    or set(train_ids) | set(validation_ids) != set(fold.training)
                    or {r.identity.person for r in validation} != {person}
                    or {r.identity.person for r in train} != expected_people - {person}):
                raise ValueError("whole-person inner partition")
            model = _fit(train, arm, alpha)
            predicted = _predict(model, validation)
            loss = math.fsum(abs(v - r.rt_seconds) for v, r in zip(predicted, validation)) / len(validation)
            if not math.isfinite(loss):
                raise ValueError("nonfinite inner validation loss")
            person_losses.append(loss)
        losses.append((math.fsum(person_losses) / 25, alpha))
    selected_alpha = min(losses)[1]
    return _fit(rows, arm, selected_alpha)

def predict_reference(model, query_rows, fold):
    if type(model) is not FrozenRidge or type(fold) is not Fold:
        raise ValueError("frozen reference and compiled fold")
    if model.training_ids != fold.training:
        raise ValueError("reference source training membership")
    rows = check_rows(query_rows, fold.query, False, model.arm)
    if {r.identity.person for r in rows} != {fold.held_person}:
        raise ValueError("one held person only")
    return _predict(model, rows)
