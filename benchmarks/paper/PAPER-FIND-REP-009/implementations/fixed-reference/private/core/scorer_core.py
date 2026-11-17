"""Finite Figure3C reconstruction agreement; stdlib only and lazy reference IO."""
import json
import math
from decimal import Decimal, DecimalException
from statistics import median

PAIR_CAP = 4_000_000
REFERENCE_CAP = 12_000_000
SCORE_CAP = 1_000_000
CONDITIONS = ['Laser_OFF', 'Laser_ON']
LEVELS = ['Randomised', 'Regular']


class InvalidSubmission(ValueError):
    pass


def need(ok, message):
    if not ok:
        raise ValueError(message)


def public(ok, message):
    if not ok:
        raise InvalidSubmission(message)


def strict_json(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            public(key not in value, 'Duplicate JSON key')
            value[key] = item
        return value
    def floating(token):
        value = float(token)
        public(math.isfinite(value), 'Nonfinite number')
        public(value != 0 or Decimal(token) == 0, 'Nonzero numeric literal underflow')
        return value
    try:
        text = raw.decode('utf-8', errors='strict') if type(raw) is bytes else raw
        public(type(text) is str, 'UTF-8 JSON text')
        value = json.loads(text, object_pairs_hook=pairs, parse_float=floating,
                          parse_constant=lambda _: public(False, 'Nonfinite constant'))
        def strings(item):
            if type(item) is str:
                item.encode('utf-8', errors='strict')
            elif type(item) is dict:
                for key, child in item.items(): strings(key); strings(child)
            elif type(item) is list:
                for child in item: strings(child)
        strings(value)
        return value
    except (UnicodeError, json.JSONDecodeError, RecursionError, OverflowError, ValueError, DecimalException) as exc:
        raise InvalidSubmission(str(exc)[:200]) from exc


def number(value):
    return type(value) in (float, int) and 0 <= value <= 1 and math.isfinite(value)


def validate_manifest(manifest):
    need(manifest['schema'] == 'thalamus_figure3C_reconstruction_sessions_v1' and
         manifest['panel'] == '3C' and manifest['session_count'] == 17 and
         manifest['condition_count'] == 34 and manifest['conditions'] == CONDITIONS and
         len(manifest['sessions']) == 17, 'Fixed complete public manifest')
    sessions = manifest['sessions']
    need([x['cohort_index'] for x in sessions] == list(range(1, 18)) and
         len({x['experiment_id'] for x in sessions}) == 17, 'Ordered unique sessions')
    return sessions


def validate_pair(raw, session):
    public(type(raw) is bytes and 0 < len(raw) <= PAIR_CAP, 'Bounded complete pair bytes')
    value = strict_json(raw)
    public(type(value) is dict and set(value) == {'schema', 'cohort_index', 'experiment_id', 'conditions'} and
           value['schema'] == 'thalamus_figure3C_candidate_pair_v1' and
           type(value['cohort_index']) is int and value['cohort_index'] == session['cohort_index'] and
           value['experiment_id'] == session['experiment_id'] and
           type(value['conditions']) is list and len(value['conditions']) == 2,
           'Exact selected session and two-condition envelope')
    for condition, cell in zip(CONDITIONS, value['conditions']):
        spec = session['condition_specs'][condition]
        public(type(cell) is dict and set(cell) == {'condition', 'feature_order', 'training_rows', 'test_rows',
               'probability_randomised'} and cell['condition'] == condition, 'Exact ordered condition fields')
        features = cell['feature_order']
        public(type(features) is list and 1 <= len(features) <= spec['feature_count_upper_bound'] and
               all(type(x) is str and x.startswith('uuid_') and len(x.encode('utf-8')) <= 260 for x in features) and
               len(set(features)) == len(features), 'Unique bounded feature roster')
        train, test = cell['training_rows'], cell['test_rows']
        public(type(train) is list and type(test) is list and len(train) == spec['training_rows'] and
               len(test) == spec['test_rows'] and all(type(x) is int and 1 <= x <= spec['trial_rows'] for x in train + test) and
               len(set(train)) == len(train) and len(set(test)) == len(test) and test == sorted(test) and
               sorted(train + test) == list(range(1, spec['trial_rows'] + 1)), 'Complete disjoint public trial partition')
        probability = cell['probability_randomised']
        public(type(probability) is list and len(probability) == len(test) and all(number(x) for x in probability),
               'Complete finite Randomised probabilities in test-row order')
    return value


def validate_all(raw_pairs, manifest):
    sessions = validate_manifest(manifest)
    public(type(raw_pairs) is list and len(raw_pairs) == 17, 'All17 submitted pairs')
    return [validate_pair(raw, session) for raw, session in zip(raw_pairs, sessions)]


def validate_reference(reference, manifest, expected):
    need(type(reference) is dict and set(reference) == {'schema', 'source_actual_index', 'source_joined_scalars',
         'reference_image', 'protocol', 'cells', 'native_model_fits', 'assembled_from_saved_outputs'} and
         reference['schema'] == 'thalamus_figure3C_fixed_reference_v1' and
         reference['source_actual_index'] == expected['actual_index'] and
         reference['source_joined_scalars'] == expected['joined_scalars'] and
         reference['reference_image'] == expected['image'] and reference['protocol'] == expected['protocol'] and
         type(reference['native_model_fits']) is int and reference['native_model_fits'] == 0 and
         reference['assembled_from_saved_outputs'] is True and
         type(reference['cells']) is list and len(reference['cells']) == 34, 'Exact fixed-reference provenance and full34 cells')
    for index, session in enumerate(validate_manifest(manifest)):
        for offset, condition in enumerate(CONDITIONS):
            cell = reference['cells'][2 * index + offset]
            need(type(cell) is dict and set(cell) == {'cohort_index', 'experiment_id', 'condition', 'feature_order',
                 'training_rows', 'test_rows', 'labels', 'probability_randomised', 'source_predictions', 'source_split'} and
                 type(cell['cohort_index']) is int and cell['cohort_index'] == session['cohort_index'] and cell['experiment_id'] == session['experiment_id'] and
                 cell['condition'] == condition, 'Exact reference cell identity')
            # Trusted structural checks, never a candidate's own reference claim.
            spec = session['condition_specs'][condition]
            feature = cell['feature_order']; train = cell['training_rows']; test = cell['test_rows']; prob = cell['probability_randomised']
            need(type(feature) is list and 1 <= len(feature) <= spec['feature_count_upper_bound'] and
                 all(type(x) is str and x.startswith('uuid_') and len(x.encode('utf-8')) <= 260 for x in feature) and
                 len(set(feature)) == len(feature) and type(train) is list and type(test) is list and
                 len(train) == spec['training_rows'] and len(test) == spec['test_rows'] and
                 all(type(x) is int and 1 <= x <= spec['trial_rows'] for x in train + test) and
                 len(set(train)) == len(train) and len(set(test)) == len(test) and test == sorted(test) and
                 sorted(train + test) == list(range(1, spec['trial_rows'] + 1)) and
                 type(prob) is list and len(prob) == len(test) and all(number(x) for x in prob), 'Complete fixed reference support and probabilities')
            labels = cell['labels']
            need(type(labels) is list and len(labels) == len(test) and all(type(x) is str and x in LEVELS for x in labels) and
                 {x: labels.count(x) for x in LEVELS} == spec['test_class_counts'], 'Exact trusted reference label support')
            source = expected['cells'][2 * index + offset]
            need(cell['source_predictions'] == source['predictions'] and cell['source_split'] == source['split'],
                 'Exact held source predictions and split descriptors')
    return reference['cells']


def metrics(probability, labels):
    positive = [p for p, label in zip(probability, labels) if label == 'Randomised']
    negative = [p for p, label in zip(probability, labels) if label == 'Regular']
    need(positive and negative, 'Both fixed AUC classes')
    auc = math.fsum(sum(p > q for q in negative) + .5 * sum(p == q for q in negative)
                    for p in positive) / (len(positive) * len(negative))
    prediction = ['Randomised' if p >= .5 else 'Regular' for p in probability]
    accuracy = sum(p == q for p, q in zip(prediction, labels)) / len(labels)
    direction = '<' if median(positive) <= median(negative) else '>'
    auto_auc = 1 - auc if direction == '<' else auc
    confusion = [{'prediction': p, 'reference': label,
                  'count': sum(a == p and b == label for a, b in zip(prediction, labels))}
                 for p in LEVELS for label in LEVELS]
    return {'accuracy': accuracy, 'fixed_auc': auc, 'source_auto_auc': auto_auc,
            'source_auto_levels': LEVELS, 'source_auto_direction': direction, 'confusion': confusion}, prediction


def score(raw_pairs, manifest, expected, load_reference):
    """Call private loader exactly once, only after every public pair is valid."""
    try:
        pairs = validate_all(raw_pairs, manifest)
    except InvalidSubmission as exc:
        return {'schema': 'thalamus_figure3C_score_v1', 'status': 'invalid_submission',
                'reason': str(exc)[:400], 'primary_metric': None, 'private_loader_calls': 0,
                'private_reference_reads': 0, 'private_reference_read_attempts': 0,
                'scientific_success': None, 'research_qualified': False, 'full_paper_complete': False}
    reference = validate_reference(load_reference(), manifest, expected)
    rows = []; paired = []; candidate_statistics = []; reference_statistics = []
    for index, pair in enumerate(pairs):
        local = []
        for offset, candidate in enumerate(pair['conditions']):
            ref = reference[2 * index + offset]
            mismatch = [key for key in ('feature_order', 'training_rows', 'test_rows') if candidate[key] != ref[key]]
            row = {'cohort_index': pair['cohort_index'], 'experiment_id': pair['experiment_id'],
                   'condition': candidate['condition'], 'primary_weight': 1 / 34,
                   'reference_test_rows': len(ref['test_rows']), 'submitted_test_rows': len(candidate['test_rows']),
                   'support_match': not mismatch, 'support_mismatch_fields': mismatch}
            if mismatch:
                row.update(primary_cell_error=1.0, candidate_metrics=None, reference_metrics=None,
                           diagnostics_unavailable_reason='fixed_support_mismatch')
            else:
                observed, predicted = metrics(candidate['probability_randomised'], ref['labels'])
                target, target_class = metrics(ref['probability_randomised'], ref['labels'])
                differences=[abs(a-b) for a,b in zip(candidate['probability_randomised'],ref['probability_randomised'])]
                error=math.fsum(differences)/len(ref['test_rows'])
                underflow=error==0 and any(x!=0 for x in differences)
                row.update(primary_cell_error=None if underflow else error,
                           primary_cell_unavailable_reason='destructive_float_underflow' if underflow else None,
                           candidate_metrics=observed, reference_metrics=target, diagnostics_unavailable_reason=None,
                           prediction_disagreement=sum(a != b for a, b in zip(predicted, target_class)) / len(predicted),
                           fixed_auc_absolute_error=abs(observed['fixed_auc']-target['fixed_auc']),
                           source_auto_auc_absolute_error=abs(observed['source_auto_auc']-target['source_auto_auc']),
                           accuracy_absolute_error_percentage_points=100*abs(observed['accuracy']-target['accuracy']),
                           fixed_auc_signed_difference=observed['fixed_auc']-target['fixed_auc'],
                           source_auto_auc_signed_difference=observed['source_auto_auc']-target['source_auto_auc'],
                           accuracy_signed_difference_percentage_points=100*(observed['accuracy']-target['accuracy']))
            rows.append(row); local.append(row)
        summary = {'cohort_index': pair['cohort_index'], 'experiment_id': pair['experiment_id'],
                   'both_conditions_comparable': all(x['support_match'] for x in local)}
        if summary['both_conditions_comparable']:
            summary['contrasts'] = {}
            for endpoint in ('source_auto_auc', 'fixed_auc', 'accuracy'):
                unit = 100 if endpoint == 'accuracy' else 1
                delta = unit*(local[1]['candidate_metrics'][endpoint]-local[0]['candidate_metrics'][endpoint])
                fixed = unit*(local[1]['reference_metrics'][endpoint]-local[0]['reference_metrics'][endpoint])
                summary['contrasts'][endpoint] = {'candidate_ON_minus_OFF': delta, 'reference_ON_minus_OFF': fixed,
                                                  'absolute_error': abs(delta-fixed),
                                                  'units': 'percentage_points' if unit == 100 else 'AUC'}
            for destination, key in ((candidate_statistics, 'candidate_metrics'), (reference_statistics, 'reference_metrics')):
                destination.append({'experiment_id': pair['experiment_id'], 'metrics': {
                    c: {ep: local[j][key][ep] for ep in ('source_auto_auc', 'fixed_auc', 'accuracy')}
                    for j, c in enumerate(CONDITIONS)}})
        else:
            summary.update(contrasts=None, unavailable_reason='fixed_support_mismatch')
        paired.append(summary)
    comparable = sum(x['support_match'] for x in rows)
    complete = comparable == 34
    primary=None if any(row['primary_cell_error'] is None for row in rows) else math.fsum(row['primary_cell_error'] for row in rows)/34
    primary_reason='cell_destructive_float_underflow' if primary is None else None
    if primary==0 and any(row['primary_cell_error']!=0 for row in rows):
        primary=None;primary_reason='aggregate_destructive_float_underflow'
    result = {'schema': 'thalamus_figure3C_score_v1', 'status': 'scored',
              'primary_metric': primary, 'primary_unavailable_reason':primary_reason,
              'primary_metric_name': 'macro_34_cell_mean_absolute_probability_discrepancy',
              'primary_direction': 'lower_is_better', 'primary_units': 'probability',
              'primary_denominator': 34, 'sessions': paired, 'cells': rows,
              'comparable_cells': comparable, 'support_mismatch_cells': 34-comparable,
              'all17_outcomes_retained': True, 'all34_primary_slots_retained': True,
              'private_loader_calls': 1, 'private_reference_reads': 1, 'private_reference_read_attempts': 1,
              'scientific_success': None, 'research_qualified': False, 'full_paper_complete': False,
              'new_reference_fits': 0, 'exposed_labels_are_reproduction_only': True,
              'whole17_statistics_status': 'pending_R431' if complete else 'not_computed_incomplete_fixed_support',
              'statistics': None,
              'limits': ['Nominal session dependence and unverified animal mapping.',
                         'Source-auto orientation uses evaluated labels; fixed orientation remains separate.',
                         'No protected improvement, published-p parity or whole-paper claim.']}
    secondary_fields = ('prediction_disagreement', 'fixed_auc_absolute_error',
        'source_auto_auc_absolute_error', 'accuracy_absolute_error_percentage_points',
        'fixed_auc_signed_difference', 'source_auto_auc_signed_difference',
        'accuracy_signed_difference_percentage_points')
    result['equal_cell_secondary_diagnostics'] = {
        'status': 'complete34_equal_cell' if complete else 'unavailable_incomplete_fixed_support',
        'denominator': 34, 'comparable_cells': comparable,
        'values': {key: math.fsum(row[key] for row in rows) / 34 for key in secondary_fields} if complete else None}
    if complete:
        result['_statistics_input'] = {'schema': 'thalamus_candidate_and_reference_diagnostics_v1',
            'session_order': [x['experiment_id'] for x in pairs], 'candidate': candidate_statistics,
            'reference': reference_statistics}
    return result
