"""NEURAL-055 pure public transport validation; standard library only."""
import json
import math
import re

SIZE = 200
MAX_JSON_BYTES = 4 * 1024 * 1024
ID = re.compile(r'[A-Za-z0-9_-]{1,128}\Z')


class ContractError(ValueError):
    pass


def need(condition, message):
    if not condition:
        raise ContractError(message)


def decode_json(raw):
    """Bounded strict JSON; duplicate object keys/nonfinite constants rejected."""
    need(type(raw) is bytes and 0 < len(raw) <= MAX_JSON_BYTES, 'bounded UTF-8 JSON bytes required')
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    def bad_constant(value):
        raise ContractError('nonfinite JSON constant: ' + value)
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=bad_constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ContractError('invalid JSON encoding or structure') from exc


def exact_keys(value, keys, name):
    need(type(value) is dict and set(value) == set(keys), name + ': exact keys required')


def opaque_id(value):
    need(type(value) is str and ID.fullmatch(value) is not None, 'invalid opaque ID syntax')
    return value


def roster(value, name):
    need(type(value) is list and len(value) == SIZE, name + ': exactly200 IDs required')
    for key in value:
        opaque_id(key)
    need(len(set(value)) == SIZE, name + ': duplicate ID')
    return value


def validate_case(case):
    exact_keys(case, ['schema', 'case_id', 'query_ids', 'candidate_ids'], 'public case')
    need(case['schema'] == 'neural055-public-case-v1', 'public case schema')
    opaque_id(case['case_id'])
    roster(case['query_ids'], 'public query IDs')
    roster(case['candidate_ids'], 'public candidate IDs')
    need(not (set(case['query_ids']) & set(case['candidate_ids'])), 'query/candidate namespaces must be disjoint')
    return case


def validate_prediction(case, prediction, *, row_sum_abs_tolerance):
    """No renormalization, row dropping, assignment optimization or private reads.

    Tolerance is mandatory operator input, never silently chosen here. Its actual
    value is not frozen by the existing scientific contract.
    """
    validate_case(case)
    need(type(row_sum_abs_tolerance) in (float, int) and 0 <= row_sum_abs_tolerance < 1
         and math.isfinite(row_sum_abs_tolerance), 'explicit finite row-sum tolerance in[0,1) required')
    exact_keys(prediction, ['schema', 'case_id', 'query_ids', 'candidate_ids',
                            'probabilities', 'assignment'], 'prediction')
    need(prediction['schema'] == 'neural055-prediction-v1', 'prediction schema')
    need(prediction['case_id'] == case['case_id'], 'wrong case ID')
    queries = roster(prediction['query_ids'], 'prediction query IDs')
    candidates = roster(prediction['candidate_ids'], 'prediction candidate IDs')
    need(set(queries) == set(case['query_ids']), 'query roster mismatch')
    need(set(candidates) == set(case['candidate_ids']), 'candidate roster mismatch')
    matrix = prediction['probabilities']
    need(type(matrix) is list and len(matrix) == SIZE, 'exactly200 probability rows required')
    for row in matrix:
        need(type(row) is list and len(row) == SIZE, 'exactly200 probability columns required')
        for value in row:
            need(type(value) in (int, float), 'probabilities must be numeric, not Boolean')
            need(0 <= value <= 1 and math.isfinite(value), 'finite probabilities in[0,1] required')
        need(abs(math.fsum(row) - 1.0) <= row_sum_abs_tolerance, 'probability row not normalized')
    assignment = roster(prediction['assignment'], 'assignment')
    need(set(assignment) == set(candidates), 'assignment must bijectively cover candidates')
    return prediction
