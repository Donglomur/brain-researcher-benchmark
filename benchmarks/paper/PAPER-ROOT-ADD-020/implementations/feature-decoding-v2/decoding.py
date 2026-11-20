"""Original 999-face training / leave-one-face-out feature-decoding schedule.

This is a supplied-input component for Fig. 2d. It does not load the historical
geometry targets, infer a neuron roster, fit a model, or claim author parity.
Response rows must already be the source's repeat-averaged neural responses for
one original time window. All 1,000 unfamiliar folds and 36 familiar queries are
retained. Input validation cannot authenticate a caller's scientific provenance.

Packets deliberately expose only training feature targets. Across all folds the
unfamiliar targets become public, as in ordinary source LOOCV; this API is not an
adversarial isolation boundary. Familiar targets are never included in packets.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from numbers import Real
from types import MappingProxyType
from typing import Iterable, Mapping


class DecodingError(ValueError):
    """A required original face/fold/output is missing or inconsistent."""


def _ids(values, count, name):
    values = tuple(values)
    if (len(values) != count or any(type(v) is not str or not v for v in values)
            or len(set(values)) != count):
        raise DecodingError(f"{name}: {count} unique nonempty identity strings required")
    return values


def _vector(values, width, name):
    try:
        values = tuple(values)
    except TypeError as error:
        raise DecodingError(f"{name}: a numeric vector is required") from error
    if not values or (width is not None and len(values) != width):
        raise DecodingError(f"{name}: complete nonempty vector with matching dimension required")
    try:
        if any(isinstance(v, bool) or not isinstance(v, Real) or not math.isfinite(v) for v in values):
            raise DecodingError(f"{name}: finite real values required, no missing-value deletion")
        return tuple(float(v) for v in values)
    except OverflowError as error:
        raise DecodingError(f"{name}: numeric value is outside the finite float range") from error


@dataclass(frozen=True)
class FaceRoster:
    unfamiliar: tuple[str, ...]
    familiar: tuple[str, ...]

    def __post_init__(self):
        object.__setattr__(self, "unfamiliar", _ids(self.unfamiliar, 1000, "unfamiliar"))
        object.__setattr__(self, "familiar", _ids(self.familiar, 36, "familiar"))
        if set(self.unfamiliar) & set(self.familiar):
            raise DecodingError("familiar and unfamiliar identities must be disjoint")

    @property
    def all_faces(self):
        return self.unfamiliar + self.familiar


@dataclass(frozen=True)
class FoldPacket:
    fold: int
    held_out_id: str
    training_ids: tuple[str, ...]
    training_responses: tuple[tuple[float, ...], ...]
    training_features: tuple[tuple[float, ...], ...]
    query_ids: tuple[str, ...]
    query_responses: tuple[tuple[float, ...], ...]


def _rows(mapping, ids, name):
    if not isinstance(mapping, Mapping) or set(mapping) != set(ids):
        raise DecodingError(f"{name}: exact complete original face identities required")
    rows, width = {}, None
    for identity in ids:
        row = _vector(mapping[identity], width, name)
        width = len(row)
        rows[identity] = row
    return rows


class FeatureDecodingInput:
    """Validate and copy one already prepared original response window.

    Only unfamiliar feature vectors are accepted here. The scorer, under its
    separate operator, holds familiar feature targets. Feature scaling, feature
    order and full neuron inclusion must be established before this interface.
    This class never standardizes, imputes, subsets neurons, or creates windows.
    """

    def __init__(self, roster: FaceRoster, responses: Mapping, unfamiliar_features: Mapping):
        if not isinstance(roster, FaceRoster):
            raise DecodingError("an explicit original face roster is required")
        self.roster = roster
        self.responses = MappingProxyType(_rows(responses, roster.all_faces, "responses"))
        self.unfamiliar_features = MappingProxyType(_rows(unfamiliar_features, roster.unfamiliar, "unfamiliar features"))

    def fold(self, index: int) -> FoldPacket:
        if type(index) is not int or not 0 <= index < 1000:
            raise DecodingError("original LOOCV fold index must be an integer from 0 to 999")
        held = self.roster.unfamiliar[index]
        train = self.roster.unfamiliar[:index] + self.roster.unfamiliar[index + 1:]
        query = (held,) + self.roster.familiar
        return FoldPacket(index, held, train, tuple(self.responses[x] for x in train),
                          tuple(self.unfamiliar_features[x] for x in train), query,
                          tuple(self.responses[x] for x in query))

    def folds(self) -> Iterable[FoldPacket]:
        """Yield exactly 1,000 folds without materializing 999,000 training rows."""
        for index in range(1000):
            yield self.fold(index)


@dataclass(frozen=True)
class FoldPrediction:
    fold: int
    query_ids: tuple[str, ...]
    features: tuple[tuple[float, ...], ...]


@dataclass(frozen=True)
class DecodingPredictions:
    unfamiliar_ids: tuple[str, ...]
    unfamiliar: tuple[tuple[float, ...], ...]
    familiar_ids: tuple[str, ...]
    # [unfamiliar held-out fold][familiar face][feature]. Do not flatten this
    # into 36,000 independent faces or silently average before source scoring.
    familiar_by_fold: tuple[tuple[tuple[float, ...], ...], ...]


def assemble_predictions(roster: FaceRoster, records: Iterable[FoldPrediction],
                         feature_count: int) -> DecodingPredictions:
    """Reassemble a complete LOOCV pass by identities, rejecting partial output.

    A worker may return faces/folds in any order. Assignment uses identifiers,
    never arrival order. No target values are accessed by this function.
    """
    if not isinstance(roster, FaceRoster) or type(feature_count) is not int or feature_count < 2:
        raise DecodingError("original roster and at least two ordered feature coordinates required")
    unfamiliar, familiar, seen = [None] * 1000, [None] * 1000, set()
    for record in records:
        if not isinstance(record, FoldPrediction):
            raise DecodingError("explicit FoldPrediction required")
        fold = record.fold
        if type(fold) is not int or not 0 <= fold < 1000 or fold in seen:
            raise DecodingError("every original fold must occur exactly once")
        held = roster.unfamiliar[fold]
        ids = _ids(record.query_ids, 37, "prediction queries")
        if set(ids) != {held, *roster.familiar}:
            raise DecodingError("query membership must be the omitted unfamiliar face and all familiar faces")
        values = tuple(record.features)
        if len(values) != len(ids):
            raise DecodingError("prediction query and vector lengths differ")
        keyed = {identity: _vector(value, feature_count, "prediction features")
                 for identity, value in zip(ids, values)}
        unfamiliar[fold] = keyed[held]
        familiar[fold] = tuple(keyed[x] for x in roster.familiar)
        seen.add(fold)
    if seen != set(range(1000)):
        raise DecodingError("all 1,000 original LOOCV folds are required; partial scores are forbidden")
    return DecodingPredictions(roster.unfamiliar, tuple(unfamiliar), roster.familiar, tuple(familiar))


@dataclass(frozen=True)
class FeatureCorrelation:
    value: float | None
    state: str


def feature_correlation(predicted, actual) -> FeatureCorrelation:
    """Pearson correlation across the coordinates of one face-feature vector.

    A same-sign anchor is removed before rescaling and centering, preserving
    small finite deviations while preventing avoidable overflow. Undefined
    constant-vector correlations remain explicit, never zero or deleted faces.
    This kernel does not select feature coordinates or normalize their scales.
    """
    actual = _vector(actual, None, "actual face features")
    predicted = _vector(predicted, len(actual), "decoded face features")
    if len(actual) < 2:
        raise DecodingError("face-vector correlation requires at least two coordinates")

    def centered(values):
        # Same-sign subtraction cannot overflow and retains small offsets.
        # Mixed signs use zero so opposite extrema never get subtracted.
        anchor = values[0] if (all(x >= 0 for x in values) or
                               all(x <= 0 for x in values)) else 0.0
        shifted = tuple(x - anchor for x in values)
        scale = max(abs(x) for x in shifted)
        scaled = tuple(x / scale for x in shifted) if scale else shifted
        mean = math.fsum(scaled) / len(scaled)
        return tuple(x - mean for x in scaled)

    a, p = centered(actual), centered(predicted)
    aa, pp = math.fsum(x * x for x in a), math.fsum(x * x for x in p)
    if aa == 0 or pp == 0:
        state = ("constant_actual_and_decoded" if aa == pp == 0 else
                 "constant_actual" if aa == 0 else "constant_decoded")
        return FeatureCorrelation(None, state)
    value = math.fsum(x * y for x, y in zip(a, p)) / (math.sqrt(aa) * math.sqrt(pp))
    # The exact Cauchy-Schwarz bound may be exceeded by floating-point roundoff.
    if abs(value) > 1.0:
        if abs(value) > 1.0 + 8 * math.ulp(1.0):
            raise DecodingError("correlation arithmetic exceeded its mathematical bound")
        value = math.copysign(1.0, value)
    return FeatureCorrelation(value, "defined")


@dataclass(frozen=True)
class FeatureCorrelationScores:
    unfamiliar_ids: tuple[str, ...]
    unfamiliar: tuple[FeatureCorrelation, ...]
    familiar_ids: tuple[str, ...]
    familiar_by_fold: tuple[tuple[FeatureCorrelation, ...], ...]


def score_feature_correlations(roster: FaceRoster, predictions: DecodingPredictions,
                               actual_features: Mapping) -> FeatureCorrelationScores:
    """Original face-vector metric, before unresolved source panel reduction.

    Inputs are a complete assembled prediction pass and operator-owned targets.
    This is an operator function; do not place it inside a candidate packet.
    No SEM, primary region/time aggregate, baseline value, or success threshold
    is invented. Undefined outputs retain identities and fold positions.
    """
    if not isinstance(roster, FaceRoster) or not isinstance(predictions, DecodingPredictions):
        raise DecodingError("complete original roster and assembled predictions required")
    if (predictions.unfamiliar_ids != roster.unfamiliar or
            predictions.familiar_ids != roster.familiar or
            len(predictions.unfamiliar) != 1000 or len(predictions.familiar_by_fold) != 1000):
        raise DecodingError("prediction identity/order and all 1,000 folds must match the source roster")
    targets = _rows(actual_features, roster.all_faces, "actual features")
    unfamiliar = tuple(feature_correlation(value, targets[identity])
                       for identity, value in zip(roster.unfamiliar, predictions.unfamiliar))
    familiar = []
    for fold in predictions.familiar_by_fold:
        if len(fold) != 36:
            raise DecodingError("each familiar prediction fold requires all 36 faces")
        familiar.append(tuple(feature_correlation(value, targets[identity])
                              for identity, value in zip(roster.familiar, fold)))
    return FeatureCorrelationScores(roster.unfamiliar, unfamiliar, roster.familiar, tuple(familiar))
