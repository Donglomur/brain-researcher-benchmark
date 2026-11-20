"""Recovered NEURAL-031 endpoint and producer-neutral paired scoring kernel.

Pure standard library; no file reads, fitting, target recovery or execution of
participant programs. Provenance and limits are in README.md and the preserved v1 SOURCES.json.
"""
import math
from collections import Counter
from fractions import Fraction


MICE = (
    'JW082', 'JW083', 'JW090', 'JW092', 'JW129', 'JW130', 'JW150',
    'JW153', 'JW154', 'JW167', 'JW168', 'JW169', 'JW193', 'JW202',
    'JW205', 'JW206', 'JW213', 'JW215', 'JW270', 'JW306',
)
VIEWS = ('baseline', 'neural')
RAW_ROWS, REQUEST_ROWS, SCORED_ROWS = 1143, 774, 731
LABELS = ('New Spine', 'Eliminated Spine', 'Absent', 'Shaft Spine')


def need(condition, message):
    if not condition:
        raise ValueError(message)


def finite_number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def flag_membership(value):
    """Preserve author string-substring versus list/tuple element membership."""
    need(type(value) is dict and set(value) == {'kind', 'value'}, 'Typed source flag required')
    kind, raw = value['kind'], value['value']
    need((kind == 'str' and type(raw) is str) or
         (kind in ('list', 'tuple') and type(raw) is list and
          all(type(item) is str for item in raw)), 'Original flag representation required')
    return {label: label in raw for label in LABELS}


def eligibility(base, later, baseline_flags, followup_flags):
    """Baseline defines requests; follow-up only defines observed ratio targets.

    Nonfinite source numbers are accepted as missing source measurements. None
    is the JSON representation of an unavailable target; it never means zero.
    """
    need(type(base) in (int, float) and type(later) in (int, float), 'Numeric source volumes required')
    first, second = flag_membership(baseline_flags), flag_membership(followup_flags)
    baseline_reasons = ['baseline_' + label.replace(' ', '_').lower()
                        for label in ('Eliminated Spine', 'Absent', 'Shaft Spine') if first[label]]
    if not finite_number(base):
        baseline_reasons.append('baseline_nonfinite')
    elif base <= 0:
        baseline_reasons.append('baseline_not_positive')
    request = not baseline_reasons
    target_reasons, ratio = [], None
    if request:
        target_reasons = ['followup_' + label.replace(' ', '_').lower()
                          for label in ('Eliminated Spine', 'Absent', 'New Spine', 'Shaft Spine') if second[label]]
        if not finite_number(later):
            target_reasons.append('followup_nonfinite')
        elif later < 0:
            target_reasons.append('followup_negative')
        try:
            ratio = later / base
        except OverflowError:
            ratio = math.inf
        if not finite_number(ratio):
            target_reasons.append('ratio_nonfinite')
    else:
        target_reasons = ['not_requested']
    observed = request and not target_reasons
    return {'request': request, 'observed': observed,
            'y': ratio if observed else None, 'baseline_new': first['New Spine'],
            'baseline_reasons': baseline_reasons, 'target_reasons': target_reasons}


def validate_support(support):
    """The original public-support schema, constrained to the declared panel."""
    need(type(support) is dict and set(support) ==
         {'schema', 'candidate_id', 'folds', 'request_rows', 'query_targets_included'} and
         support['schema'] == 'neural031_ordinary_public_support_v1' and
         support['candidate_id'] == 'NEURAL-031' and support['query_targets_included'] is False and
         type(support['folds']) is list and len(support['folds']) == 20,
         'Exact complete public support required')
    seen = set()
    for fold, item in enumerate(support['folds']):
        need(type(item) is dict and set(item) == {'fold', 'rowids', 'views'} and
             type(item['fold']) is int and item['fold'] == fold and
             type(item['rowids']) is list and 0 < len(item['rowids']) <= RAW_ROWS and
             all(type(row) is int and 0 <= row < RAW_ROWS for row in item['rowids']) and
             item['rowids'] == sorted(set(item['rowids'])) and not seen.intersection(item['rowids']) and
             type(item['views']) is dict and set(item['views']) == set(VIEWS),
             'Every held mouse once, unique sorted original row IDs and both views required')
        for view in item['views'].values():
            need(type(view) is dict and set(view) == {'data', 'manifest'}, 'Physical view identity required')
            for pin in view.values():
                need(type(pin) is dict and set(pin) == {'bytes', 'sha256'} and
                     type(pin['bytes']) is int and 0 < pin['bytes'] <= 262144 and
                     type(pin['sha256']) is str and len(pin['sha256']) == 64 and
                     all(char in '0123456789abcdef' for char in pin['sha256']), 'Exact view descriptor required')
        seen.update(item['rowids'])
    need(type(support['request_rows']) is int and support['request_rows'] == len(seen) == REQUEST_ROWS,
         'All 774 declared baseline requests required; no partial-panel score')


def validate_all(bundle, support):
    """Validate all 40 outputs before a caller opens any private target file."""
    validate_support(support)
    need(type(bundle) is dict and set(bundle) == {'schema', 'candidate_id', 'outputs'} and
         bundle['schema'] == 'neural031_ordinary_submission_bundle_v1' and
         bundle['candidate_id'] == 'NEURAL-031' and type(bundle['outputs']) is list and
         len(bundle['outputs']) == 40, 'Complete paired submission bundle required')
    result = {}
    for fold in range(20):
        expected = support['folds'][fold]
        for offset, view in enumerate(VIEWS):
            value = bundle['outputs'][2 * fold + offset]
            need(type(value) is dict and set(value) ==
                 {'schema', 'candidate_id', 'fold', 'view', 'input_manifest', 'rows'} and
                 value['schema'] == 'neural031_ordinary_prediction_v1' and
                 value['candidate_id'] == 'NEURAL-031' and type(value['fold']) is int and
                 value['fold'] == fold and value['view'] == view and
                 type(value['input_manifest']) is dict and
                 set(value['input_manifest']) == {'bytes', 'sha256'} and
                 type(value['input_manifest']['bytes']) is int and
                 type(value['input_manifest']['sha256']) is str and
                 value['input_manifest'] == expected['views'][view]['manifest'] and
                 type(value['rows']) is list and len(value['rows']) == len(expected['rowids']),
                 'Every output must bind to its held mouse and information view')
            predictions = []
            for item, rowid in zip(value['rows'], expected['rowids']):
                need(type(item) is dict and set(item) == {'row_id', 'prediction'} and
                     type(item['row_id']) is int and item['row_id'] == rowid and
                     finite_number(item['prediction']) and item['prediction'] >= 0,
                     'All requested predictions must be finite, nonnegative and in exact original row order')
                predictions.append(float(item['prediction']))
            result[fold, view] = predictions
    return result


def validate_targets(target, support):
    need(type(target) is dict and set(target) == {'schema', 'candidate_id', 'mice', 'rows'} and
         target['schema'] == 'neural031_ratio_targets_v1' and target['candidate_id'] == 'NEURAL-031' and
         target['mice'] == list(MICE) and type(target['rows']) is list and len(target['rows']) == RAW_ROWS,
         'All 1143 original private rows and exact 20-mouse identity required')
    groups = [[] for _ in MICE]
    for rowid, row in enumerate(target['rows']):
        need(type(row) is dict and set(row) ==
             {'rowid', 'mouse', 'y', 'request', 'observed', 'baseline_new', 'compartment'} and
             type(row['rowid']) is int and row['rowid'] == rowid and
             type(row['mouse']) is int and 0 <= row['mouse'] < 20 and
             all(type(row[key]) is int and row[key] in (0, 1)
                 for key in ('request', 'observed', 'baseline_new', 'compartment')),
             'Original row IDs, mouse IDs and binary eligibility fields required')
        need((row['observed'] == 1 and row['request'] == 1 and finite_number(row['y']) and row['y'] >= 0) or
             (row['observed'] == 0 and row['y'] is None),
             'Observed nonnegative ratio or explicit unavailable null required')
        groups[row['mouse']].append(row)
    for fold, rows in enumerate(groups):
        need([row['rowid'] for row in rows if row['request']] == support['folds'][fold]['rowids'] and
             any(row['observed'] for row in rows),
             'Same complete baseline requests and at least one observed target for every mouse required')
    need(sum(row['observed'] for row in target['rows']) == SCORED_ROWS,
         'All 731 declared observed targets required; exclusions cannot be chosen by predictions')
    return groups


def mean(values):
    """Stable finite arithmetic mean, including near-maximum finite ratios."""
    values = list(values)
    need(bool(values) and all(finite_number(value) for value in values), 'Finite nonempty metric required')
    # Exact accumulation preserves a small signed gain after large positive
    # and negative mouse gains cancel. Scaling first can erase that residual.
    value = float(sum((Fraction(value) for value in values), Fraction()) / len(values))
    need(math.isfinite(value), 'Representable finite metric required')
    return value


def balanced_median(rows):
    """Lower weighted median: each training mouse has equal total mass."""
    counts = Counter(row['mouse'] for row in rows)
    need(bool(counts), 'Observed training targets required')
    cumulative = Fraction(0)
    for row in sorted(rows, key=lambda item: item['y']):
        cumulative += Fraction(1, len(counts) * counts[row['mouse']])
        if cumulative >= Fraction(1, 2):
            return row['y']
    raise ValueError('Training median failed')


def grade_validated(predictions, support, target):
    """Internal evaluator seam; use score() for an unvalidated bundle."""
    groups = validate_targets(target, support)
    rows = []
    for fold, group in enumerate(groups):
        requested = [row for row in group if row['request']]
        valid = [index for index, row in enumerate(requested) if row['observed']]
        row = {'fold': fold, 'mouse_id': MICE[fold], 'raw_rows': len(group),
               'request_rows': len(requested), 'scored_rows': len(valid),
               'unavailable_rows': len(requested) - len(valid)}
        for view in VIEWS:
            row[view + '_mae'] = mean(abs(predictions[fold, view][index] - requested[index]['y']) for index in valid)
        row['baseline_minus_neural_mae'] = row['baseline_mae'] - row['neural_mae']
        row['no_change_mae'] = mean(abs(1.0 - requested[index]['y']) for index in valid)
        training = [item for other, group_rows in enumerate(groups) if other != fold
                    for item in group_rows if item['observed']]
        median = balanced_median(training)
        row['training_median_mae'] = mean(abs(median - requested[index]['y']) for index in valid)
        row['strata'] = []
        for field in ('compartment', 'baseline_new'):
            for value in (0, 1):
                indexes = [index for index in valid if requested[index][field] == value]
                row['strata'].append({'field': field, 'value': value, 'scored_rows': len(indexes),
                    **{view + '_mae': mean(abs(predictions[fold, view][index] - requested[index]['y'])
                                           for index in indexes) if indexes else None for view in VIEWS}})
        rows.append(row)
    fields = ('baseline_mae', 'neural_mae', 'baseline_minus_neural_mae', 'no_change_mae', 'training_median_mae')
    return {'schema': 'neural031_ratio_score_v1', 'candidate_id': 'NEURAL-031',
            'mice': rows, 'macro': {field: mean(row[field] for row in rows) for field in fields},
            'primary_metric': 'equal_mouse_baseline_minus_neural_mae',
            'primary': mean(row['baseline_minus_neural_mae'] for row in rows),
            'direction': 'higher', 'units': 'followup_volume / baseline_volume (dimensionless)',
            'raw_rows': RAW_ROWS, 'request_rows': REQUEST_ROWS, 'scored_rows': SCORED_ROWS,
            'unavailable_rows': REQUEST_ROWS - SCORED_ROWS,
            'positive_mouse_differences': sum(row['baseline_minus_neural_mae'] > 0 for row in rows),
            'inference': 'Descriptive whole-mouse cross-validation; overlapping training sets are not independent folds.',
            'claim_limit': 'Conditional observed same-spine follow-up ratio after Early activity; no survival, causal, precise elapsed-time or direct/viewer-understanding claim.'}


def score(support, bundle, target):
    return grade_validated(validate_all(bundle, support), support, target)
