"""Paired numerical investigation component; no inference about how files were made.

Reuses the qualified arbitrary sleep probability reader and metrics unchanged.
A larger EOG-minus-EEG contrast is not an optimization reward: weakening the
EEG arm can increase it. Both absolute performances always remain in the result.
"""
import json
import math
from . import candidate_adapter as adapter

ARMS = ('EEG_clock', 'EEG_EOG_clock')
CLAIM_TOLERANCE = 1e-10


def unique(pairs):
    result = {}
    for key, value in pairs:
        adapter.require(key not in result, 'Duplicate claim JSON key')
        result[key] = value
    return result


def check_claims(value, spec):
    adapter.require(type(value) is dict and set(value) == {'schema_version', 'candidate_id', 'reported_contrast'}
                    and type(value['schema_version']) is int and value['schema_version'] == 1 and
                    value['candidate_id'] == 'NEURAL-008', 'Exact optional numerical claim schema')
    claim = value['reported_contrast']
    if claim is None:
        return None
    adapter.require(type(claim) is dict and set(claim) == {
        'person_mean_macro_f1_delta', 'person_mean_rem_recall_delta', 'per_person'}, 'Exact contrast claims')
    def number(v, nullable=False):
        adapter.require((nullable and v is None) or
                        (type(v) in (int, float) and math.isfinite(v) and -1 <= v <= 1),
                        'Finite claimed difference in [-1,1]; bool is not numeric')
    number(claim['person_mean_macro_f1_delta'])
    number(claim['person_mean_rem_recall_delta'], True)
    adapter.require(type(claim['per_person']) is list and len(claim['per_person']) == len(spec.cases),
                    'Complete ordered per-person claim list')
    for row, case in zip(claim['per_person'], spec.cases, strict=True):
        adapter.require(type(row) is dict and set(row) == {'person_id', 'macro_f1_delta', 'rem_recall_delta'}
                        and row['person_id'] == case.case_id, 'Exact claim person identity/order')
        number(row['macro_f1_delta'])
        number(row['rem_recall_delta'], True)
    return claim


def read_claims(path, lock, spec):
    adapter.require(type(lock) is dict and set(lock) == {'bytes', 'sha256'} and
                    type(lock['bytes']) is int and 1 <= lock['bytes'] <= 16384, 'Bounded claim file')
    body = adapter._locked_bytes(path, lock)
    value = json.loads(body.decode('utf-8', errors='strict'), object_pairs_hook=unique,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite claim')))
    check_claims(value, spec)
    return value


def claim_comparison(claim, contrast):
    if claim is None:
        return {'status': 'not_submitted', 'max_absolute_numeric_error': None,
                'within_numeric_tolerance': None, 'scientific_claim_validity': 'not_assessed'}
    rows = []
    def add(name, supplied, recomputed):
        definedness_matches = (supplied is None) == (recomputed is None)
        error = None if supplied is None or recomputed is None else supplied - recomputed
        rows.append({'field': name, 'claimed': supplied, 'recomputed': recomputed,
                     'definedness_matches': definedness_matches,
                     'signed_error': error, 'absolute_error': None if error is None else abs(error)})
    for name in ('person_mean_macro_f1_delta', 'person_mean_rem_recall_delta'):
        add(name, claim[name], contrast[name])
    for requested, actual in zip(claim['per_person'], contrast['per_person'], strict=True):
        for name in ('macro_f1_delta', 'rem_recall_delta'):
            add(requested['person_id'] + '/' + name, requested[name], actual[name])
    numeric = [r['absolute_error'] for r in rows if r['absolute_error'] is not None]
    maximum = max(numeric) if numeric else None
    agrees = all(r['definedness_matches'] and
                 (r['absolute_error'] is None or r['absolute_error'] <= CLAIM_TOLERANCE) for r in rows)
    return {'status': 'consistent' if agrees else 'inconsistent', 'fields': rows,
            'max_absolute_numeric_error': maximum, 'within_numeric_tolerance': agrees,
            'numeric_tolerance': CLAIM_TOLERANCE,
            'scientific_claim_validity': 'not_assessed',
            'numeric_agreement_is_not_model_or_scientific_success': True}


def evaluate(arm_files, claims, spec, target_loader):
    adapter.checked_specification(spec)
    adapter.require(adapter.CLASS_ORDER == ('W', 'N1', 'N2', 'N3', 'R'), 'REM is the fixed fifth class')
    adapter.require(spec.comparator_names == () and type(arm_files) is dict and set(arm_files) == set(ARMS),
                    'Exactly the two named arbitrary arms')
    claim = check_claims(claims, spec)
    validated = {}
    for arm in ARMS:
        row = arm_files[arm]
        adapter.require(type(row) is tuple and len(row) == 2, 'Trusted arm path and hash pair')
        validated[arm] = adapter.validate_submission(row[0], row[1], spec)
    # Both complete arbitrary probability panels and every claim field passed.
    # One operator-owned loader returns both original target files and masks.
    targets = adapter._checked_targets(target_loader(), spec)
    performance = {arm: adapter._score(validated[arm], targets, spec) for arm in ARMS}
    contrast = adapter._difference(performance['EEG_EOG_clock'], performance['EEG_clock'])
    contrast['direction'] = 'EEG_EOG_clock_minus_EEG_clock'
    for row in contrast['per_person']:
        row['rem_recall_delta'] = row['recall_by_stage_delta'][4]
    rem = [r['rem_recall_delta'] for r in contrast['per_person']]
    contrast['person_mean_rem_recall_delta'] = None if any(v is None for v in rem) else math.fsum(rem) / len(rem)
    for arm in ARMS:
        for row in performance[arm]['per_person']:
            row['rem_recall'] = row['recall_by_stage'][4]
    return {
        'status': 'valid_paired_descriptive_investigation_result', 'candidate_id': 'NEURAL-008',
        'absolute_performance': performance, 'paired_contrast': contrast,
        'claim_consistency': claim_comparison(claim, contrast),
        'class_order': list(adapter.CLASS_ORDER), 'row_sum_atol': adapter.ROW_SUM_ATOL,
        'prediction_values_modified': False, 'argmax_ties': 'first fixed class index',
        'input_freezes': {arm: validated[arm]['file'] for arm in ARMS},
        'n_development_people': len(spec.cases), 'private_loader_calls': 1,
        'scalar_optimization_reward': None, 'scientific_success_threshold': None,
        'scientific_improvement_verified': False,
        'paired_training_and_information_access_provenance': 'unverified_from_finished_files',
        'larger_positive_delta_can_result_from_a_weakened_EEG_arm': True,
        'population_inference': False, 'confidence_interval': None, 'p_value': None,
        'rem_comparison_defined': all(v is not None for v in rem),
        'epoch_count_is_not_biological_sample_size': True,
        'exposure': 'Two historical exposed development people; four reserved people untouched',
        'scope': 'Numerical paired artifact assessment only; not a matched-training replay or reviewed physiological explanation',
    }

