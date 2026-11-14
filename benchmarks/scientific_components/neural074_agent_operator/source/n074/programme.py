"""One actual nested fitting path with immutable predictions before target scoring.

This library does not itself establish real reader custody, native sandboxing,
protected target issuance, or independent resource observations.
"""
from dataclasses import dataclass
from .contracts import require
from .maps import read_training, freeze_prediction
from .metrics import tuning_loss
from .models import ARMS, fit
from .semantics import fit_features
from .splits import fit_schedule


@dataclass(frozen=True)
class Prediction:
    person: str
    family: str
    endpoint: str
    arm: str
    status: str
    value: object | None
    reason: str | None


@dataclass(frozen=True)
class ProgrammeResult:
    protocol_identity: str
    taxonomy_identity: str
    eligibility_identity: str
    support_identity: str
    predictions: tuple
    fit_events: tuple
    selected_configurations: tuple
    native_observation: str
    stage_events: tuple
    completion: str


class ProgrammeFailure(RuntimeError):
    """A failed attempt retains its partial values and all recorded stage outcomes."""
    def __init__(self, cause, partial):
        super().__init__(type(cause).__name__)
        self.partial = partial


class FitJournal:
    """Logical fit accounting only; not an OS resource or independent evidence issuer."""
    def __init__(self, maximum):
        self.maximum = maximum
        self.events = []
        self.stages = []

    def stage(self, label, operation):
        ordinal = len(self.stages)
        self.stages.append((ordinal, label, 'entered', None))
        try:
            value = operation()
        except BaseException as error:
            self.stages[ordinal] = (ordinal, label, 'failed', type(error).__name__)
            raise
        self.stages[ordinal] = (ordinal, label, 'returned', None)
        return value

    def attempt(self, label, operation):
        require(len(self.events) < self.maximum, 'Declared whole-programme fit bound exceeded')
        ordinal = len(self.events)
        self.events.append((ordinal, label, 'attempted', None))
        try:
            value = operation()
        except BaseException as error:
            self.events[ordinal] = (ordinal, label, 'failed', type(error).__name__)
            raise
        self.events[ordinal] = (ordinal, label, 'returned', None)
        return value


def _design_rows(designs, ids):
    require(set(ids) <= set(designs), 'Missing selected design')
    return tuple(designs[i] for i in ids)


def _inner_arrays(y, outer, inner):
    import numpy as np
    pindex = {p: i for i, p in enumerate(outer.training_people)}
    eindex = {e: i for i, e in enumerate(outer.training_endpoints)}
    pi = [pindex[p] for p in inner.training_people]
    ei = [eindex[e] for e in inner.training_endpoints]
    qi = [eindex[e] for e in inner.query_endpoints]
    training = y[np.ix_(pi, ei, range(y.shape[2]))]
    validation = y[pindex[inner.held_person], qi, :]
    return training, validation


def _choose(scores, configurations, arm, matched_rank=None):
    candidates = []
    for index, config in enumerate(configurations):
        losses = scores[arm, index]
        if matched_rank is not None and config.rank != matched_rank:
            continue
        if losses and all(v is not None for v in losses):
            candidates.append((sum(losses) / len(losses), index))
    require(bool(candidates), 'No configuration has complete valid nested support for ' + arm)
    # The selected configuration order is a predeclared deterministic tie-break.
    return min(candidates)[1]


def _run(population, designs, protocol, training_reader, maximum_map_bytes, state):
    """Fit and predict P1 only. No query response is requested or scored here."""
    population.validate()
    protocol.validate()
    require(type(maximum_map_bytes) is int and maximum_map_bytes > 0, 'Missing immutable-map retention bound')
    require(len({d.endpoint for d in designs}) == len(designs), 'Duplicate design metadata')
    dmap = {d.endpoint: d for d in designs}
    require(set(dmap) == {e.identity for e in population.endpoints}, 'Designs do not cover the exact declared roster')
    for d in designs:
        d.validate()
    schedule = fit_schedule(population, protocol)
    journal = FitJournal(sum(r['fits'] for r in schedule))
    predictions, selected = [], []
    state.update(journal=journal, predictions=predictions, selected=selected)
    for row in schedule:
        outer = row['fold']
        key = row['outer']
        if row['status'] != 'planned':
            predictions.extend(Prediction(outer.held_person, outer.held_family, e, arm, row['status'], None, 'complete_support_unavailable')
                               for e in outer.query_endpoints for arm in ARMS)
            continue
        try:
            y = journal.stage((key, 'training_inputs'), lambda: read_training(
                training_reader, population, outer, protocol.spatial_support_identity, maximum_map_bytes))
        except Exception as error:
            predictions.extend(Prediction(outer.held_person, outer.held_family, e, arm, 'training_input_failed', None, type(error).__name__)
                               for e in outer.query_endpoints for arm in ARMS)
            continue
        scores = {(arm, i): [] for arm in ARMS for i in range(len(protocol.configurations))}
        for inner in row['inner']:
            inner_key = (key, 'inner', inner.held_person, inner.held_family)
            training, validation = journal.stage((inner_key, 'response_projection'), lambda: _inner_arrays(y, outer, inner))
            feature_owner = journal.stage((inner_key, 'feature_fit'), lambda: fit_features(_design_rows(dmap, inner.training_endpoints)))
            x = journal.stage((inner_key, 'training_features'), lambda: feature_owner.transform(_design_rows(dmap, inner.training_endpoints)))
            xq = journal.stage((inner_key, 'query_features'), lambda: feature_owner.transform(_design_rows(dmap, inner.query_endpoints)))
            for index, config in enumerate(protocol.configurations):
                for arm in ARMS:
                    label = (key, 'inner', inner.held_person, inner.held_family, arm, index)
                    try:
                        model = journal.attempt(label, lambda: fit(arm, training, x, config))
                        predicted = journal.stage((label, 'prediction'), lambda: model.predict(xq))
                        loss = journal.stage((label, 'tuning_metric'), lambda: tuning_loss(predicted, validation, protocol.tuning_metric))
                    except Exception:
                        loss = None
                    scores[arm, index].append(loss)
        try:
            component_index = _choose(scores, protocol.configurations, 'shared_components')
            indices = {'shared_components': component_index,
                       'full_rank_ridge': _choose(scores, protocol.configurations, 'full_rank_ridge'),
                       'rank_matched_ridge': _choose(scores, protocol.configurations, 'rank_matched_ridge',
                                                    protocol.configurations[component_index].rank)}
        except Exception as error:
            predictions.extend(Prediction(outer.held_person, outer.held_family, e, arm, 'selection_failed', None, type(error).__name__)
                               for e in outer.query_endpoints for arm in ARMS)
            continue
        feature_owner = journal.stage((key, 'final_feature_fit'), lambda: fit_features(_design_rows(dmap, outer.training_endpoints)))
        x = journal.stage((key, 'final_training_features'), lambda: feature_owner.transform(_design_rows(dmap, outer.training_endpoints)))
        xq = journal.stage((key, 'final_query_features'), lambda: feature_owner.transform(_design_rows(dmap, outer.query_endpoints)))
        for arm in ARMS:
            index = indices[arm]
            selected.append((key, arm, index, protocol.configurations[index]))
            try:
                model = journal.attempt((key, 'final', arm, index), lambda: fit(arm, y, x, protocol.configurations[index]))
                maps = journal.stage((key, 'final_prediction', arm), lambda: model.predict(xq))
                require(len(maps) == len(outer.query_endpoints), 'Incomplete query prediction')
                frozen = journal.stage((key, 'prediction_capture', arm), lambda: tuple(
                    freeze_prediction(outer.held_person, e, arm, a, protocol.spatial_support_identity, maximum_map_bytes)
                    for e, a in zip(outer.query_endpoints, maps)))
            except Exception as error:
                predictions.extend(Prediction(outer.held_person, outer.held_family, e, arm, 'final_prediction_failed', None, type(error).__name__)
                                   for e in outer.query_endpoints)
                continue
            predictions.extend(Prediction(outer.held_person, outer.held_family, e, arm, 'predicted', v, None)
                               for e, v in zip(outer.query_endpoints, frozen))
    expected = {(p, e.identity, arm) for p in population.people for e in population.endpoints for arm in ARMS}
    actual = [(p.person, p.endpoint, p.arm) for p in predictions]
    require(len(actual) == len(set(actual)) and set(actual) == expected, 'Programme output lost or duplicated a declared endpoint')
    return ProgrammeResult(protocol.selection_identity, population.taxonomy_pin, population.eligibility_pin,
                           protocol.spatial_support_identity, tuple(predictions), tuple(journal.events), tuple(selected),
                           'UNESTABLISHED: internal fit journal is not independent native/resource evidence',
                           tuple(journal.stages), 'complete_source_attempt')


def run(population, designs, protocol, training_reader, maximum_map_bytes):
    """Whole library-attempt owner; native process/cleanup observations remain external."""
    population.validate()
    protocol.validate()
    state = {}
    try:
        return _run(population, designs, protocol, training_reader, maximum_map_bytes, state)
    except BaseException as cause:
        predictions = list(state.get('predictions', ()))
        existing = {(p.person, p.endpoint, p.arm) for p in predictions}
        for person in population.people:
            for endpoint in population.endpoints:
                for arm in ARMS:
                    if (person, endpoint.identity, arm) not in existing:
                        predictions.append(Prediction(person, endpoint.family, endpoint.identity, arm,
                                                      'programme_aborted', None, type(cause).__name__))
        journal = state.get('journal')
        partial = ProgrammeResult(protocol.selection_identity, population.taxonomy_pin, population.eligibility_pin,
                                  protocol.spatial_support_identity, tuple(predictions),
                                  () if journal is None else tuple(journal.events), tuple(state.get('selected', ())),
                                  'UNESTABLISHED: native cleanup/resource observation unavailable',
                                  () if journal is None else tuple(journal.stages), 'failed_source_attempt')
        raise ProgrammeFailure(cause, partial) from cause
