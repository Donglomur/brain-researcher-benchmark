"""Complete Fig. 2d support join, without a scalar win or inference rule.

This operator-side supplied-input component consumes the existing feature
correlation scorer's outputs. It does not compute Pearson correlations, fit a
decoder, recover source windows/shuffles, or authenticate caller provenance.
All contract identities must be independently qualified before scientific use.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import hashlib
import json
import math
from numbers import Real
import re
from typing import Callable, Iterable


class PanelError(ValueError):
    pass


def _need(condition, message):
    if not condition:
        raise PanelError(message)


def _hash(value, name):
    _need(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value),
          name + " must be an explicit lowercase SHA256")
    return value


def _ids(values, name, length=None):
    _need(type(values) is tuple and len(values) > 0,
          name + " must be a nonempty immutable ordered tuple")
    _need(length is None or len(values) == length, name + " has incomplete support")
    _need(all(type(x) is str and x for x in values) and len(set(values)) == len(values),
          name + " requires unique nonempty string identities")
    return values


def _digest(value):
    body = json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


@dataclass(frozen=True)
class Population:
    identity: str
    region: str
    unfamiliar_ids: tuple[str, ...]
    familiar_ids: tuple[str, ...]
    feature_ids: tuple[str, ...]
    window_ids: tuple[str, ...]
    source_binding_sha256: str

    def __post_init__(self):
        _need(type(self.identity) is str and self.identity, "population identity required")
        _need(self.region in ("AM", "PR", "TP"), "Fig. 2d region must be AM, PR or TP")
        _ids(self.unfamiliar_ids, "unfamiliar faces", 1000)
        _ids(self.familiar_ids, "familiar faces", 36)
        _need(not set(self.unfamiliar_ids) & set(self.familiar_ids), "face sets overlap")
        _ids(self.feature_ids, "ordered feature coordinates")
        _need(len(self.feature_ids) >= 2, "correlation needs at least two feature coordinates")
        _ids(self.window_ids, "complete source windows")
        _hash(self.source_binding_sha256, "population source binding")


@dataclass(frozen=True)
class Condition:
    identity: str
    kind: str
    source_mapping_sha256: str

    def __post_init__(self):
        _need(type(self.identity) is str and self.identity, "condition identity required")
        _need(self.kind in ("original", "identity_shuffled"), "unknown source condition")
        # This binds an external original identity-map/protocol artifact. It is
        # not an invented RNG seed, nor proof that the original map was recovered.
        _hash(self.source_mapping_sha256, "source condition mapping")


@dataclass(frozen=True)
class PanelContract:
    populations: tuple[Population, ...]
    conditions: tuple[Condition, ...]
    source_scope_sha256: str
    access_condition: str

    def __post_init__(self):
        _need(type(self.populations) is tuple and self.populations and
              all(isinstance(p, Population) for p in self.populations),
              "explicit ordered population records required")
        _ids(tuple(p.identity for p in self.populations), "population identities")
        _need({p.region for p in self.populations} == {"AM", "PR", "TP"},
              "all original AM/PR/TP regions must remain present")
        _need(type(self.conditions) is tuple and len(self.conditions) == 11 and
              all(isinstance(c, Condition) for c in self.conditions),
              "original condition plus all ten original shuffled controls required")
        _ids(tuple(c.identity for c in self.conditions), "condition identities", 11)
        _need(sum(c.kind == "original" for c in self.conditions) == 1 and
              sum(c.kind == "identity_shuffled" for c in self.conditions) == 10,
              "one original and ten shuffled controls required")
        _hash(self.source_scope_sha256, "complete original scope binding")
        _need(self.access_condition in ("paper_data", "paper_data_author_code"),
              "assistance conditions must be evaluated separately")

    @property
    def sha256(self):
        return _digest(asdict(self))

    def schedule(self):
        """Canonical order; every population's own complete window set survives."""
        for population in self.populations:
            for window in population.window_ids:
                for condition in self.conditions:
                    yield (population.identity, window, condition.identity)

    @property
    def cell_count(self):
        return sum(len(p.window_ids) for p in self.populations) * 11


@dataclass(frozen=True)
class ScoreCell:
    key: tuple[str, str, str]
    # Exact full contract, not just a shape or model-name match.
    contract_sha256: str
    prediction_commitment_sha256: str
    # An existing feature-decoding-v1 FeatureCorrelationScores object. Duck
    # typing permits that module to be imported by its existing deployment name.
    scores: object


@dataclass(frozen=True)
class MetricDifference:
    baseline: float | None
    candidate: float | None
    baseline_state: str
    candidate_state: str
    candidate_minus_baseline: float | None


@dataclass(frozen=True)
class CellComparison:
    key: tuple[str, str, str]
    unfamiliar_ids: tuple[str, ...]
    familiar_ids: tuple[str, ...]
    unfamiliar: tuple[MetricDifference, ...]
    # Axis0 is the omitted unfamiliar face/fold. Axis1 is familiar face.
    familiar_by_fold: tuple[tuple[MetricDifference, ...], ...]


def _metric(item):
    try:
        value, state = item.value, item.state
    except AttributeError as error:
        raise PanelError("existing scorer value/state record required") from error
    valid_states = ("defined", "constant_actual", "constant_decoded",
                    "constant_actual_and_decoded")
    _need(type(state) is str and state in valid_states, "unknown correlation state")
    if state == "defined":
        _need(not isinstance(value, bool) and isinstance(value, Real), "finite correlation required")
        try:
            number = float(value)
        except (OverflowError, ValueError) as error:
            raise PanelError("finite correlation required") from error
        _need(math.isfinite(number) and -1.0 <= number <= 1.0, "correlation outside [-1,1]")
        return number, state
    _need(value is None, "undefined correlation must remain explicit null")
    return None, state


def _difference(baseline, candidate):
    b, bs = _metric(baseline)
    c, cs = _metric(candidate)
    actual_constant = {"constant_actual", "constant_actual_and_decoded"}
    _need((bs in actual_constant) == (cs in actual_constant),
          "paired scores disagree about the same actual feature vector")
    return MetricDifference(b, c, bs, cs, None if b is None or c is None else c - b)


def _validate_cell(cell, expected_key, population, digest):
    _need(isinstance(cell, ScoreCell), "explicit ScoreCell required")
    _need(type(cell.key) is tuple and cell.key == expected_key,
          "panel cells must follow the complete declared schedule without duplicates")
    _need(cell.contract_sha256 == digest, "source/support/assistance contract mismatch")
    _hash(cell.prediction_commitment_sha256, "frozen prediction commitment")
    score = cell.scores
    try:
        _need(type(score.unfamiliar_ids) is tuple and
              score.unfamiliar_ids == population.unfamiliar_ids,
              "unfamiliar/fold identities or order differ")
        _need(type(score.familiar_ids) is tuple and
              score.familiar_ids == population.familiar_ids,
              "familiar identities or order differ")
        _need(type(score.unfamiliar) is tuple and len(score.unfamiliar) == 1000,
              "all1000 unfamiliar fold scores required")
        _need(type(score.familiar_by_fold) is tuple and len(score.familiar_by_fold) == 1000,
              "all1000 familiar-query folds required; no prematurity averaging")
        _need(all(type(row) is tuple and len(row) == 36 for row in score.familiar_by_fold),
              "every fold requires all36 familiar scores")
    except AttributeError as error:
        raise PanelError("complete existing scorer output required") from error
    return score


def compare_panels(contract: PanelContract, baseline: Iterable[ScoreCell],
                   candidate: Iterable[ScoreCell], emit: Callable[[CellComparison], None]):
    """Stream paired complete scores, return a receipt only after exact exhaustion.

    No reduction across faces/folds/regions/windows/controls is introduced.
    Completion means schedule/identity/value consistency only. It is not an
    improvement decision or an independently authenticated source result.
    An emitter may retain partial output if a later cell fails: that output is
    invalid as a complete panel without the returned completion receipt.
    """
    _need(isinstance(contract, PanelContract) and callable(emit), "contract and output consumer required")
    digest = contract.sha256
    b_iter, c_iter = iter(baseline), iter(candidate)
    populations = {p.identity: p for p in contract.populations}
    output_hash = hashlib.sha256()
    prediction_chain = hashlib.sha256()
    count = undefined = 0
    sentinel = object()
    for key in contract.schedule():
        b_cell, c_cell = next(b_iter, sentinel), next(c_iter, sentinel)
        _need(b_cell is not sentinel and c_cell is not sentinel, "incomplete paired panel")
        pop = populations[key[0]]
        b = _validate_cell(b_cell, key, pop, digest)
        c = _validate_cell(c_cell, key, pop, digest)
        unfamiliar = tuple(_difference(x, y) for x, y in zip(b.unfamiliar, c.unfamiliar))
        familiar = tuple(tuple(_difference(x, y) for x, y in zip(br, cr))
                         for br, cr in zip(b.familiar_by_fold, c.familiar_by_fold))
        result = CellComparison(key, pop.unfamiliar_ids, pop.familiar_ids, unfamiliar, familiar)
        # Hash the immutable paired record before the consumer can retain it.
        serial = {"key": key, "unfamiliar": [tuple(asdict(x).values()) for x in unfamiliar],
                  "familiar_by_fold": [[tuple(asdict(x).values()) for x in row] for row in familiar]}
        output_hash.update(bytes.fromhex(_digest(serial)))
        prediction_chain.update(bytes.fromhex(_digest({"key": key,
            "baseline": b_cell.prediction_commitment_sha256,
            "candidate": c_cell.prediction_commitment_sha256})))
        undefined += sum(x.candidate_minus_baseline is None for x in unfamiliar)
        undefined += sum(x.candidate_minus_baseline is None for row in familiar for x in row)
        emit(result)
        count += 1
    _need(next(b_iter, sentinel) is sentinel and next(c_iter, sentinel) is sentinel,
          "extra panel cells are forbidden")
    return {"schema": "paper020-complete-paired-panel/v1", "contract_sha256": digest,
            "cell_count": count, "correlation_count": count * 37000,
            "undefined_paired_differences": undefined,
            "paired_cells_sha256": output_hash.hexdigest(),
            "prediction_chain_sha256": prediction_chain.hexdigest(),
            "assistance_condition": contract.access_condition,
            "qualification": "supplied_input_complete_support_only",
            "reproduction_outcome": "unknown", "improvement_outcome": "unknown",
            "paper_win": None, "scientific_readiness": "not_established"}
