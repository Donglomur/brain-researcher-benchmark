"""Target-last arithmetic: no dropped cases, no missing-model backfill."""
from collections import defaultdict
import random
import math
from .base import require, finite, native_loss, digest
from .contracts import assert_numerical, assert_endpoint_applicable
from .models import mean as _ordinary_mean


def mean(values):
    """Preserve ordinary rounding; rescue only finite summation overflow.

    The scoring inputs are already validated finite. Exact rational summation
    avoids both intermediate overflow and cancellation loss in the exceptional
    branch. Model fitting continues to use the unchanged models.mean.
    """
    try:
        return _ordinary_mean(values)
    except OverflowError:
        from fractions import Fraction
        total = sum((Fraction.from_float(finite(v, 'metric_mean_operand'))
                     for v in values), Fraction())
        return finite(float(total / len(values)), 'metric_mean')


def validate_submission(submission, public):
    c = assert_numerical(public['cell_id'], public['task'])
    assert_endpoint_applicable(public['cell_id'], public['task'], public['endpoint'])
    require(public['endpoint_support']['schema'] == 'endpoint_eligibility_summary_v1' and
            public['endpoint_support']['endpoint'] == public['endpoint'], 'endpoint_support_binding')
    require(set(submission) == {'schema', 'task', 'cell_id', 'input_digest',
                               'predictions', 'model_artifact_digests'}, 'submission_keys')
    require(submission['schema'] == 'sealed_neural_predictions_v1', 'submission_schema')
    require(submission['task'] == public['task'] and submission['cell_id'] == public['cell_id'],
            'submission_binding')
    require(submission['input_digest'] == digest(public), 'input_digest')
    query = {r['id']: r for r in public['query']}
    require(len(query) == len(public['query']) and query, 'query_identity')
    predictions = submission['predictions']
    if public['task'] == 'NEURAL-045':
        require(set(predictions) == set(query), 'native_case_identity')
        for key, values in predictions.items():
            require(isinstance(values, list) and len(values) == len(query[key]['times']),
                    'native_shape')
            for x in values: finite(x, 'native_prediction')
    else:
        expected = set(c['NEURAL-046']['models_produced']) or {'P'}
        require(set(predictions) == expected, 'missing_or_extra_model_no_backfill')
        require(set(submission['model_artifact_digests']) == expected, 'model_commitments')
        for model in expected:
            require(set(predictions[model]) == set(query), 'scalar_case_identity')
            for x in predictions[model].values(): finite(x, 'scalar_prediction')
    return c


def score(submission, public, private_query, closure, reference_mse=None):
    require(closure.get('all_required_producers_closed') is True and
            closure.get('all_required_artifacts_sealed') is True and
            closure.get('private_targets_opened_before_closure') is False,
            'target_last_closure_required')
    c = validate_submission(submission, public)
    require(len(private_query) == len(public['query']), 'private_case_join')
    pairs = list(zip(public['query'], private_query))
    require(len({r['domain'] for r in private_query}) == 1, 'mixed_neural_units')
    for exposed, hidden in pairs:
        require(exposed['condition'] == hidden['condition'], 'private_condition_join')
        if c['control'] != 'opaque_ID':
            require(exposed['id'] == hidden['id'] and exposed['animal'] == hidden['animal'],
                    'private_biological_case_join')
    # The operator stores this exact opaque/public-to-private positional join at preparation.
    if public['task'] == 'NEURAL-045':
        grouped = defaultdict(list)
        conditions = {}
        trials = []
        for exposed, hidden in pairs:
            require(exposed['times'] == hidden['signal']['times'], 'private_native_clock_join')
            result = native_loss(hidden['signal']['times'], hidden['target'],
                                 submission['predictions'][exposed['id']], hidden['signal']['max_gap'])
            grouped[hidden['animal']].append(result)
            conditions[hidden['animal']] = hidden['condition']
            trials.append({'animal': hidden['animal'], 'session': hidden['session'],
                           'condition': hidden['condition'], 'sex': hidden['features']['sex'],
                           'hardware': hidden['features']['hardware'],
                           'outcome': hidden['outcome_stratum'],
                           'first_six': hidden['trial_ordinal'] <= 6, **result})
        animals = {a: {k: mean([r[k] for r in rs]) for k in ('mse', 'mae', 'bias')}
                   for a, rs in grouped.items()}
        macro = {k: mean([r[k] for r in animals.values()]) for k in ('mse', 'mae', 'bias')}
        skill, zero = None, []
        if reference_mse is not None:
            require(set(reference_mse) == set(animals), 'reference_animal_join')
            values = []
            for a in animals:
                denominator = finite(reference_mse[a])
                require(denominator >= 0, 'negative_reference_error')
                if denominator == 0: zero.append(a)
                else: values.append(finite(1 - animals[a]['mse'] / denominator, 'skill'))
            if not zero: skill = mean(values)
        by_condition = {}
        for condition in set(conditions.values()):
            by_condition[condition] = {k: mean([v[k] for a, v in animals.items()
                                                if conditions[a] == condition])
                                      for k in ('mse', 'mae', 'bias')}
        metrics = {'animal_macro': macro, 'animals': animals, 'conditions': by_condition,
                   'condition_macro_mse': mean([x['mse'] for x in by_condition.values()]),
                   'reference_relative_skill': skill, 'undefined_reference_animals': zero,
                   'skill_is_variance_R2': False,
                   'strata': stratified_losses(trials), 'trial_contributions': trials}
    else:
        model_results = {}
        for model, predictions in submission['predictions'].items():
            errors = defaultdict(list)
            trials = []
            for exposed, hidden in pairs:
                e = finite(predictions[exposed['id']]) - finite(hidden['target'])
                errors[hidden['animal']].append(finite(e * e, 'squared_error'))
                trials.append({'animal': hidden['animal'], 'session': hidden['session'],
                    'condition': hidden['condition'], 'sex': hidden['features']['sex'],
                    'hardware': hidden['features']['hardware'], 'outcome': hidden['outcome_stratum'],
                    'first_six': hidden['trial_ordinal'] <= 6, 'mse': e * e})
            per = {a: mean(v) for a, v in errors.items()}
            conditions = {r['animal']: r['condition'] for r in private_query}
            per_condition = {c0: mean([v for a, v in per.items() if conditions[a] == c0])
                             for c0 in set(conditions.values())}
            model_results[model] = {'animal_macro_mse': mean(list(per.values())), 'animals': per,
                                   'conditions': per_condition,
                                   'condition_macro_mse': mean(list(per_condition.values())),
                                   'strata': stratified_losses(trials), 'trial_contributions': trials}
        contrasts = {}
        L = {m: r['animal_macro_mse'] for m, r in model_results.items()}
        if {'ME', 'MN', 'MEN'} <= set(L):
            contrasts = {'Delta': L['MN'] - L['ME'], 'G_E': L['MN'] - L['MEN'],
                         'G_N': L['ME'] - L['MEN']}
        for model in ('ME', 'MN', 'MEN'):
            if {'M0', model} <= set(L): contrasts[model + '_gain_over_M0'] = L['M0'] - L[model]
        allowed = set(c['NEURAL-046']['numeric_endpoint'])
        require(set(contrasts) <= allowed, 'contrast_backfill')
        metrics = {'models': model_results, 'contrasts': contrasts,
                   'Delta_is_effect_not_contestant_reward': True,
                   'comparison_status': c['NEURAL-046']['applicability']}
    return {'schema': 'closed_neural_scientific_arithmetic_v1', 'task': public['task'],
            'cell_id': public['cell_id'], 'submission_digest': digest(submission),
            'endpoint': public.get('endpoint', 'cue'), 'domain': private_query[0]['domain'],
            'endpoint_support': public['endpoint_support'],
            'metrics': metrics, 'target_count': len(private_query),
            'replication_unit': 'biological_animal_subject_to_source_identity_gate',
            'synthetic': public['synthetic'], 'scientific_qualification': False}


def stratified_losses(trials):
    result = {}
    for key in ('session', 'sex', 'hardware', 'outcome', 'first_six'):
        groups = defaultdict(lambda: defaultdict(list))
        for row in trials: groups[str(row[key])][row['animal']].append(row['mse'])
        result[key] = {label: {'animal_macro_mse': mean([mean(v) for v in animals.values()]),
                               'animals': len(animals), 'trials': sum(len(v) for v in animals.values())}
                       for label, animals in groups.items()}
    sessions = defaultdict(lambda: defaultdict(list))
    for row in trials: sessions[row['animal']][row['session']].append(row['mse'])
    result['equal_session_sensitivity'] = {
        a: mean([mean(values) for values in ss.values()]) for a, ss in sessions.items()}
    return result


def bootstrap_paired(differences, animal_conditions, replicates=10000, seed=0,
                     interpretation='conditional_on_fit_descriptive'):
    require(set(differences) == set(animal_conditions), 'bootstrap_identity')
    require(type(replicates) is int and replicates > 0, 'bootstrap_replicates')
    groups = defaultdict(list)
    for animal, condition in animal_conditions.items():
        finite(differences[animal]); groups[condition].append(animal)
    require(all(len(v) >= 2 for v in groups.values()), 'bootstrap_condition_insufficient_animals')
    rng = random.Random(seed)
    samples = []
    for _ in range(replicates):
        draw = [rng.choice(animals) for animals in groups.values() for _ in animals]
        samples.append(mean([differences[a] for a in draw]))
    samples.sort()
    return {'estimate': mean(list(differences.values())),
            'lower': samples[int(.025 * (replicates - 1))],
            'upper': samples[int(.975 * (replicates - 1))],
            'replicates': replicates, 'seed': seed, 'interpretation': interpretation,
            'public_CV_confirmatory_significance': False}


def score_sensitivities(predictions, public, private_query):
    """Only previously audited/sealed MEN sensitivity; never an absent primary model."""
    c = assert_numerical(public['cell_id'], public['task'])
    expected = {'MEN_independently_tuned'} if 'MEN' in c['NEURAL-046']['models_produced'] else set()
    require(set(predictions) == expected, 'sensitivity_backfill')
    result = {}
    for name, values in predictions.items():
        require(set(values) == {r['id'] for r in public['query']}, 'sensitivity_case_join')
        groups = defaultdict(list)
        for exposed, hidden in zip(public['query'], private_query):
            groups[hidden['animal']].append(finite((finite(values[exposed['id']]) - finite(hidden['target'])) ** 2))
        animals = {a: mean(v) for a, v in groups.items()}
        result[name] = {'animals': animals, 'animal_macro_mse': mean(list(animals.values()))}
    return result


def holm(pvalues):
    for p in pvalues.values(): require(0 <= finite(p) <= 1, 'pvalue_range')
    ordered = sorted(pvalues, key=pvalues.get)
    adjusted, previous = {}, 0.
    for i, key in enumerate(ordered):
        previous = max(previous, min(1., (len(ordered) - i) * pvalues[key]))
        adjusted[key] = previous
    return adjusted


def terminal_report(closed_result, interpretation):
    """Interpretation cannot change models/targets; exact arithmetic stays attached."""
    require(interpretation['closed_result_digest'] == digest(closed_result), 'interpretation_binding')
    require(interpretation['claims'] and isinstance(interpretation['limitations'], list), 'report_fields')
    return {'schema': 'terminal_neural_report_v1', 'closed_result': closed_result,
            'interpretation': interpretation, 'retraining_permitted': False,
            'scientific_qualification': False}


def interpretation_packet(result):
    """Aggregate-only irreversible handoff. Trial and animal losses stay custodian-side."""
    import copy
    packet = copy.deepcopy(result)
    packet['schema'] = 'closed_aggregate_interpretation_evidence_v1'
    packet['custodian_result_digest'] = digest(result)
    def clean(value):
        if isinstance(value, dict):
            return {k: clean(v) for k, v in value.items() if k not in (
                'trial_contributions', 'animals', 'equal_session_sensitivity',
                'covariate_support', 'inner_validation', 'joint_inner_validation')}
        if isinstance(value, list): return [clean(v) for v in value]
        return value
    return clean(packet)
