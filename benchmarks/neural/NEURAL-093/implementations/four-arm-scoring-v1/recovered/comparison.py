"""Full39 prospective paired reduction of trusted, already-scored session rows.

This module never reads predictions/targets, executes a model or invokes the
original scorer. A future trusted grader must produce all156 rows using the
source-bound original probability/metric definitions after complete public
validation. Candidate-supplied scalar metrics are not admissible inputs.
"""
import math
from controls import ARMS, ORIGINAL_ARMS, CONTROL_ARMS, encoded, pin, need, parent

METRIC_CORE_SHA256 = '42fb4d454098e919e92dde979f1c4209676c56b0016bdc4e198b62a1e8ebffa2'
METRICS = {
    'natural_log_loss': {'lower_is_better': True, 'units': 'nats_per_query'},
    'multiclass_Brier_mean_sum3': {'lower_is_better': True, 'units': 'sum_of_three_squared_probability_errors_per_query'},
    'top1_accuracy': {'lower_is_better': False, 'units': 'fraction_correct'},
}
PAIRS = {
    'neural_increment_given_wheel_context': ('wheel_plus_context', 'neural_wheel_plus_context'),
    'neural_increment_given_context': ('context', 'neural_plus_context'),
}


def fields(value, names, message):
    need(type(value) is dict and set(value) == set(names), message)


def extended(value):
    if math.isnan(value): return {'status': 'undefined', 'value': None}
    if math.isinf(value): return {'status': 'positive_infinity' if value > 0 else 'negative_infinity', 'value': None}
    return {'status': 'finite', 'value': value}


def number(value):
    fields(value, ('status', 'value'), 'exact extended number')
    if value['status'] == 'finite':
        need(type(value['value']) in (int, float) and math.isfinite(value['value']), 'finite nonboolean metric')
        return float(value['value'])
    need(value['value'] is None and value['status'] in ('positive_infinity', 'negative_infinity', 'undefined'),
         'explicit nonfinite status')
    return {'positive_infinity': math.inf, 'negative_infinity': -math.inf, 'undefined': math.nan}[value['status']]


def mean(values):
    # Deliberately retain undefined and infinity; never filter/renormalize.
    need(len(values) > 0, 'complete nonempty mean support')
    return sum(values)/len(values)


def improvement(without_neural, with_neural, metric):
    need(metric in METRICS, 'declared original metric; no generic lower-is-better assumption')
    a, b = number(without_neural), number(with_neural)
    return extended(a-b if METRICS[metric]['lower_is_better'] else b-a)


def descriptor(value):
    fields(value, ('bytes', 'sha256'), 'exact trusted artifact pin')
    need(type(value['bytes']) is int and value['bytes'] > 0 and parent.digest(value['sha256']), 'nonempty pinned artifact')


def _scope(panel):
    need(panel['schema'] == 'neural093_operator_only_four_arm_panel_v1'
         and panel['required_sessions'] == 39 and panel['required_mice'] == 10
         and panel['required_queries'] == 2042 and panel['prediction_tables'] == 156
         and panel['original_78_output_endpoint_modified'] is False, 'complete prospective panel declaration')
    sessions = panel['sessions']
    need(type(sessions) is list and len(sessions) == 39 and [s['ordinal'] for s in sessions] == list(range(1, 40))
         and len({s['session'] for s in sessions}) == 39 and len({s['session_token'] for s in sessions}) == 39
         and len({s['mouse'] for s in sessions}) == 10
         and sum(len(s['query_tokens']) for s in sessions) == 2042, 'whole ordered39/10/2042 support')
    return sessions


def validate_commit(panel, commit):
    sessions = _scope(panel)
    names = ('schema program_sha256 recipe_sha256 tuning_policy_sha256 '
             'program_frozen_before_first_fitval same_reviewed_tuning_policy_and_budget '
             'separate_fits_per_arm all_four_models_sealed_before_each_query_release '
             'all_predictions_committed_before_any_feedback all_owned_producers_absent_before_grading '
             'private_grading_started sessions').split()
    fields(commit, names, 'exact trusted four-arm commitment record')
    need(commit['schema'] == 'neural093_prospective_four_arm_commit_v1', 'prospective commitment identity')
    for name in ('program_sha256', 'recipe_sha256', 'tuning_policy_sha256'):
        need(parent.digest(commit[name]), 'same frozen source/recipe/reviewed tuning policy')
    for name in names[4:-2]: need(commit[name] is True, 'full pre-exposure/closure invariant: '+name)
    need(commit['private_grading_started'] is False, 'complete predictions precede private feedback')
    need(type(commit['sessions']) is dict and set(commit['sessions']) == {s['session_token'] for s in sessions},
         'all39 committed sessions')
    instances = set()
    for s in sessions:
        row = commit['sessions'][s['session_token']]
        fields(row, ('query_tokens_sha256', 'arms'), 'exact session commitment')
        need(row['query_tokens_sha256'] == pin(encoded(s['query_tokens']))['sha256'], 'same ordered source trial identities')
        need(type(row['arms']) is dict and set(row['arms']) == set(ARMS), 'all four arms before feedback')
        for arm in ARMS:
            item = row['arms'][arm]
            fields(item, ('fit_instance_id', 'model', 'prediction', 'query_manifest'), 'exact separate fit/output pins')
            need(parent.digest(item['fit_instance_id']) and item['fit_instance_id'] not in instances,
                 'distinct trusted fit instances, not cross-arm state reuse')
            instances.add(item['fit_instance_id'])
            for name in ('model', 'prediction', 'query_manifest'): descriptor(item[name])
            raw = (s['original_manifest_bytes'] if arm in ORIGINAL_ARMS else s['control_manifest_bytes'])[arm]['query']
            need(item['query_manifest'] == pin(raw), 'exact isolated query packet identity')
    return sessions


def summarize(panel, commit, records):
    """Reduce trusted source-bound metrics; declarations alone do not prove custody.

    Every row must be computed on the same complete ordered query tokens with
    the frozen score_core definitions. The caller must authenticate metric rows
    and the commit from an independently qualified operator, never a candidate.
    """
    sessions = validate_commit(panel, commit)
    need(type(records) is list and len(records) == 156, 'all156 scored arm/session rows, no subset')
    expected = {(s['session_token'], arm) for s in sessions for arm in ARMS}
    by = {}
    session_by = {s['session_token']: s for s in sessions}
    for record in records:
        fields(record, ('session_token', 'arm', 'program_sha256', 'recipe_sha256', 'tuning_policy_sha256',
            'prediction', 'query_tokens', 'metric_core_sha256', 'metrics'), 'exact trusted metric row, not candidate score fields')
        key = (record['session_token'], record['arm'])
        need(key in expected and key not in by, 'unique full arm/session support')
        s = session_by[key[0]]
        need(record['query_tokens'] == s['query_tokens'], 'identical trial IDs/order, not merely same count')
        need(all(record[name] == commit[name] for name in ('program_sha256', 'recipe_sha256', 'tuning_policy_sha256')),
             'one prospective program/recipe/tuning policy across all156 rows')
        need(record['metric_core_sha256'] == METRIC_CORE_SHA256
             and record['prediction'] == commit['sessions'][key[0]]['arms'][key[1]]['prediction'],
             'trusted original metric definition and precommitted prediction identity')
        fields(record['metrics'], METRICS, 'all three original metrics, no selected metric')
        for metric, value in record['metrics'].items():
            x = number(value)
            if metric == 'natural_log_loss': need(not math.isnan(x) and x >= 0, 'nonnegative logloss including positive infinity')
            else: need(math.isfinite(x) and 0 <= x <= (2 if metric == 'multiclass_Brier_mean_sum3' else 1), 'bounded Brier/accuracy')
        by[key] = record
    need(set(by) == expected, 'every required comparison remains paired')
    session_rows = []
    for s in sessions:
        absolute = {arm: by[(s['session_token'], arm)]['metrics'] for arm in ARMS}
        effects = {name: {metric: improvement(absolute[a][metric], absolute[b][metric], metric)
                         for metric in METRICS} for name, (a, b) in PAIRS.items()}
        session_rows.append(dict(ordinal=s['ordinal'], session=s['session'], mouse=s['mouse'],
            query_rows=len(s['query_tokens']), absolute=absolute, effects=effects))
    mouse_rows = []
    for mouse in sorted({s['mouse'] for s in sessions}):
        rows = [s for s in session_rows if s['mouse'] == mouse]
        absolute = {arm: {metric: extended(mean([number(s['absolute'][arm][metric]) for s in rows]))
                         for metric in METRICS} for arm in ARMS}
        # Difference after equal-session absolute aggregation preserves the old
        # infinity semantics; do not finite-only average per-session effects.
        effects = {name: {metric: improvement(absolute[a][metric], absolute[b][metric], metric)
                         for metric in METRICS} for name, (a, b) in PAIRS.items()}
        mouse_rows.append(dict(mouse=mouse, sessions=[s['session'] for s in rows], absolute=absolute, effects=effects))
    absolute = {arm: {metric: extended(mean([number(m['absolute'][arm][metric]) for m in mouse_rows]))
                     for metric in METRICS} for arm in ARMS}
    effects = {name: {metric: extended(mean([number(m['effects'][name][metric]) for m in mouse_rows]))
                     for metric in METRICS} for name in PAIRS}
    return dict(schema='neural093_prospective_neural_increment_summary_v1', sessions=39, mice=10,
        queries_per_arm=2042, arm_session_outputs=156, session_records=session_rows, mouse_records=mouse_rows,
        equal_mouse_absolute_metrics=absolute, equal_mouse_improvements=effects,
        contrast_definitions={name: dict(without_neural=a, with_neural=b) for name, (a, b) in PAIRS.items()},
        metric_directions_and_units=METRICS, old_endpoint_or_primary_modified=False,
        uncertainty={'status':'not_computed_by_this_component', 'prospective_requirement':
            'The preselected primary logloss contrast requires separately source-bound paired-mouse PCG64 seed20261102/10000 draws/linear2.5,97.5 interval; nonfinite mouse effects make it undefined, never trimmed.'},
        old_primary='ln(3) minus original candidate joint logloss, unchanged and reported separately',
        prospective_primary='neural_increment_given_wheel_context / natural_log_loss',
        secondary_comparisons_descriptive=True, causal_claim=False, strict_induction_claim=False,
        exposure_free_claim=False, runtime_qualified=False, scientific_result_established=False)
