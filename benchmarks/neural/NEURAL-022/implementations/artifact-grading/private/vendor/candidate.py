"""Public 92-row validation precedes the private loader; no candidate code runs here."""
import json
import math
import re

SCHEMA = 'neural022_predictions_v1'
METHODS = ('active_neural', 'passive_neural', 'active_mean', 'passive_mean',
           'active_direction', 'passive_direction', 'zero')
DIRECTIONS = tuple(range(0, 360, 45))
MAX_SUBMISSION_BYTES = 65536


def need(ok, why):
    if not ok:
        raise ValueError(why)


def strict(raw):
    def pairs(items):
        out = {}
        for k, v in items:
            need(k not in out, 'Duplicate JSON key')
            out[k] = v
        return out
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda s: need(False, 'Nonfinite JSON'))


def cases(value):
    need(type(value) is dict and set(value) == {'schema', 'cases'}
         and value['schema'] == 'neural022_public_cases_v1', 'Exact public cases schema')
    rows = value['cases']
    need(type(rows) is list and len(rows) == 92, 'All92 public cases')
    for row in rows:
        need(type(row) is dict and set(row) == {'id', 'mode', 'direction'}
             and type(row['id']) is str and re.fullmatch('[a-f0-9]{24}', row['id'])
             and row['mode'] in ('active', 'passive') and type(row['direction']) is int
             and row['direction'] in DIRECTIONS, 'Only opaque identity and declared context')
    need(len({r['id'] for r in rows}) == 92, 'Unique public identities')
    for mode, n in (('passive', 40), ('active', 52)):
        selected = [r for r in rows if r['mode'] == mode]
        need(len(selected) == n and {r['direction'] for r in selected} == set(DIRECTIONS),
             'Full mode/eight-direction denominator')
    return rows


def vectors(rows, ids):
    need(type(rows) is list and len(rows) == 92, 'Exactly92 prediction rows')
    need(all(type(r) is dict and set(r) == {'id', 'velocity'} for r in rows),
         'Exactly id and velocity per row')
    need([r['id'] for r in rows] == ids, 'All unique opaque IDs in public order')
    values = [r['velocity'] for r in rows]
    need(all(type(v) is list and len(v) == 2 and all(type(x) in (int, float)
             and math.isfinite(x) for x in v) for v in values), 'Two finite nonboolean velocities')
    return values


def validate(raw, public):
    rows = cases(public)
    need(type(raw) is bytes and 0 < len(raw) <= MAX_SUBMISSION_BYTES, 'Bounded nonempty submission')
    obj = strict(raw)
    need(type(obj) is dict and set(obj) == {'schema', 'predictions'} and obj['schema'] == SCHEMA,
         'Exact candidate table; candidate cannot choose a fixed-reference identity')
    return vectors(obj['predictions'], [r['id'] for r in rows])


def fixed_scores(rows, private, held_score, expected):
    ids = [r['id'] for r in rows]
    need(type(private) is dict and set(private) == {'ids', 'velocity', 'references'}
         and private['ids'] == ids and set(private['references']) == set(METHODS),
         'Complete sealed private target and all seven unchanged reference identities')
    truth = [{'id': i, 'velocity': v} for i, v in zip(ids, private['velocity'])]
    vectors(truth, ids)
    predictions = {m: [{'id': i, 'velocity': v} for i, v in zip(ids, private['references'][m])]
                   for m in METHODS}
    result = held_score(rows, truth, predictions)
    need(result['units'] == '(m/s)^2' and result['status'] == 'complete_fixed_query_scoring',
         'Original fixed reference endpoint')
    for mode in ('passive', 'active'):
        need(set(expected['losses'][mode]) == set(METHODS), 'Expected fixed methods')
        for m in METHODS:
            need(math.isclose(result['losses'][mode][m], expected['losses'][mode][m],
                              rel_tol=1e-13, abs_tol=1e-15), 'Saved reference scalar reproduction')
    need(math.isclose(result['primary_active_minus_passive_neural_loss'],
                      expected['primary_active_minus_passive_neural_loss'],
                      rel_tol=1e-13, abs_tol=1e-15), 'Original signed reference primary preserved')
    return truth, result


def evaluate(raw, public, load_private, held_score, expected):
    """Only this callback can access private arrays. Invalid public tables never call it."""
    common = dict(candidate_id='NEURAL-022', candidate_identity='candidate_program',
                  private_target_loads=0, primary_metric='passive_mean_squared_euclidean_error',
                  public_validation_invocations=1, public_output_admission_complete=False,
                  public_prediction_rows_admitted=0,
                  units='(m/s)^2', method_provenance_verified=False,
                  training_only_or_nontransductive_behavior_certified=False,
                  positive_gain_required=False, research_qualified=False, new_benchmark_IDs=0)
    # Malformed trusted public metadata is an operator failure, not candidate invalidity.
    rows = cases(public)
    try:
        prediction = validate(raw, public)
    except (ValueError, TypeError, OverflowError, UnicodeError, RecursionError) as error:
        return common | dict(status='invalid_submission', primary_score=None,
                             reason=type(error).__name__ + ': ' + str(error)[:300])
    common.update(public_output_admission_complete=True, public_prediction_rows_admitted=92)
    common['private_target_loads'] = 1
    truth, reference = fixed_scores(rows, load_private(), held_score, expected)
    try:
        trial_losses = [math.fsum((p[j] - t['velocity'][j]) ** 2 for j in range(2))
                        for p, t in zip(prediction, truth)]
        if not all(math.isfinite(v) for v in trial_losses):
            raise ArithmeticError('Nonfinite candidate squared loss')
        metrics = {}
        strata = []
        for mode, n in (('passive', 40), ('active', 52)):
            selected = [i for i, r in enumerate(rows) if r['mode'] == mode]
            loss = math.fsum(trial_losses[i] for i in selected) / n
            metrics[mode] = {'trials': n, 'mean_squared_euclidean_error': loss,
                            'candidate_minus_fixed_reference':
                                {m: loss - reference['losses'][mode][m] for m in METHODS}}
            for direction in DIRECTIONS:
                idx = [i for i in selected if rows[i]['direction'] == direction]
                value = math.fsum(trial_losses[i] for i in idx) / len(idx)
                fixed = next(v for v in reference['direction_strata']
                             if v['mode'] == mode and v['direction'] == direction)
                strata.append({'mode': mode, 'direction': direction, 'trials': len(idx),
                               'candidate_loss': value, 'fixed_reference_losses': fixed['losses'],
                               'candidate_minus_fixed_reference':
                                   {m: value - fixed['losses'][m] for m in METHODS}})
    except (ArithmeticError, OverflowError) as error:
        return common | dict(status='unsupported_numerical_result', primary_score=None,
                             reason='Finite public predictions exceed representable score arithmetic: '
                                    + type(error).__name__)
    return common | dict(status='scored_exposed_transfer_candidate', submission_rows=92,
        primary_score=metrics['passive']['mean_squared_euclidean_error'],
        candidate_minus_fixed_passive_neural=
            metrics['passive']['candidate_minus_fixed_reference']['passive_neural'],
        negative_gap_means='candidate lower loss than the privately calibrated fixed passive neural reference',
        metrics=metrics, direction_strata=strata, fixed_reference_losses=reference['losses'],
        original_reference_diagnostic={
            'identity': 'historical_active_neural_minus_passive_neural_on_passive_queries',
            'value': reference['primary_active_minus_passive_neural_loss'],
            'candidate_is_not_active_neural': True, 'recomputed_from_unchanged_saved_predictions': True},
        independent_animals=1, unseen_evaluation=False)
