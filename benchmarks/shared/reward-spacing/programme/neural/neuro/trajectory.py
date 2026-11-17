"""Native quadrature-weighted continuous-time encoding references and frozen states."""
from collections import Counter
from .base import require, finite, digest
from .reward_common import native_interval_weights
from . import models


def expand(training, query=False):
    out = []
    for case in training:
        times = case['times']
        if not query:
            require('signal' in case and 'target' in case, 'training_neural_response_removed')
            support = native_interval_weights(times, times[0], times[-1], case['signal']['max_gap'])
            require(support['covered_seconds'] > 0, 'empty_training_native_span')
        for i, t in enumerate(times):
            row = {'id': case['id'] + ':' + str(i), 'case_id': case['id'],
                   'animal': case['animal'], 'condition': case['condition'],
                   'features': {**case['features'], 'tau': finite(t)}}
            if not query:
                weight = support['weights'][i] / support['covered_seconds']
                if weight == 0: continue
                row.update(target=case['target'][i], weight=weight)
            out.append(row)
    return out


def fit_reference(public, reference='R3'):
    require(public['task'] == 'NEURAL-045', 'trajectory_task')
    axes = {'R0': ('tau', 'E'), 'R1': ('tau',), 'R2': ('tau', 'N'),
            'R3': ('tau', 'E', 'N')}[reference]
    training = expand(public['training'])
    nuisance = (set() if reference == 'R0' else
                set.intersection(*(set(r['features']) for r in training)) - {'tau', 'E', 'N'})
    conditions = sorted({r['condition'] for r in training})
    require(len(conditions) >= 2, 'inner_condition_validation_unsupported')
    trials = []
    for dimension in models.GRID:
        for penalty in models.PENALTIES:
            losses = []
            try:
                for held in conditions:
                    tr = [r for r in training if r['condition'] != held]
                    va = [r for r in training if r['condition'] == held]
                    fit = models.fit(tr, axes, dimension, penalty, nuisance)
                    prediction = models.predict(fit, va)
                    # Integrate using the training window weights, then macro animals.
                    by_animal = {}
                    for r, w in zip(va, models.animal_weights(va)):
                        by_animal.setdefault(r['animal'], 0.)
                        by_animal[r['animal']] += w * (prediction[r['id']] - r['target']) ** 2
                    losses.append(sum(by_animal.values()))
                trials.append({'dimension': dimension, 'penalty': penalty,
                               'loss': models.mean(losses), 'status': 'valid'})
            except (ValueError, ArithmeticError) as error:
                trials.append({'dimension': dimension, 'penalty': penalty,
                               'status': 'unsupported', 'reason': str(error)})
    valid = [r for r in trials if r['status'] == 'valid']
    require(valid, 'no_supported_encoding_reference')
    best = min(valid, key=lambda r: (r['loss'], r['dimension'], -r['penalty']))
    fitted = models.fit(training, axes, best['dimension'], best['penalty'], nuisance)
    return {'reference': reference, 'model': fitted, 'selection': best,
            'inner_condition_validation': trials, 'training_input_digest': digest(public),
            'scientific_qualification': False}


def predict_native(reference, query):
    values = models.predict(reference['model'], expand(query, query=True))
    return {r['id']: [values[r['id'] + ':' + str(i)] for i in range(len(r['times']))]
            for r in query}


def frozen_cue_state(reference, query_without_clock):
    require('times' not in query_without_clock and 'target' not in query_without_clock
            and 'signal' not in query_without_clock, 'future_grid_or_neural_input')
    require('concurrent_lick_rate' not in query_without_clock['features'], 'future_behavior')
    return {'schema': 'cue_time_frozen_spline_state_v1', 'model': reference['model'],
            'case_id': query_without_clock['id'], 'animal': query_without_clock['animal'],
            'features_at_cue': query_without_clock['features']}


def evaluate_frozen_state(state, native_times):
    """Only later timestamps enter; no refitting or future event/response input."""
    require(state['schema'] == 'cue_time_frozen_spline_state_v1', 'frozen_state_schema')
    rows = [{'id': str(i), 'animal': state['animal'],
             'features': {**state['features_at_cue'], 'tau': finite(t)}}
            for i, t in enumerate(native_times)]
    values = models.predict(state['model'], rows)
    return [values[str(i)] for i in range(len(native_times))]
