"""NEURAL-021 public format validation. No target access or scientific fit."""
import json
import math
import re

TASK = 'NEURAL-021'
SCHEMA = 'neural021_trajectory_predictions_v1'
MAX_JSON = 4 * 1024 * 1024


def strict_json(raw):
    if not isinstance(raw, bytes) or len(raw) > MAX_JSON:
        raise ValueError('bounded UTF-8 JSON bytes required')
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError('duplicate JSON key')
            out[key] = value
        return out
    def bad(value):
        raise ValueError('nonfinite JSON literal')
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=bad)


def validate_queries(cases):
    if not isinstance(cases, dict) or cases.get('schema') != 'neural021_public_cases_v1':
        raise ValueError('public cases schema')
    if cases.get('task_id') != TASK or cases.get('time_bins') != 30:
        raise ValueError('task / time-bin mismatch')
    queries = cases.get('queries')
    if not isinstance(queries, list) or not 2 <= len(queries) <= 826:
        raise ValueError('complete query roster required')
    ids = []
    for row in queries:
        if (not isinstance(row, dict) or set(row) != {'trial_id', 'condition'} or
                not isinstance(row['trial_id'], str) or
                re.fullmatch(r'q[0-9]{4}', row['trial_id']) is None or
                row['condition'] not in ('active', 'passive')):
            raise ValueError('invalid query identity / condition')
        ids.append(row['trial_id'])
    if len(set(ids)) != len(ids) or {x['condition'] for x in queries} != {'active', 'passive'}:
        raise ValueError('unique queries and both conditions required')
    return queries


def validate_submission(submission, cases, cases_sha256):
    """Return canonical roster order only after validating every submitted value."""
    queries = validate_queries(cases)
    if (not isinstance(submission, dict) or
            set(submission) != {'schema', 'task_id', 'cases_sha256', 'predictions'} or
            submission['schema'] != SCHEMA or submission['task_id'] != TASK or
            submission['cases_sha256'] != cases_sha256 or
            re.fullmatch('[0-9a-f]{64}', cases_sha256) is None):
        raise ValueError('prediction header or public case identity mismatch')
    predictions = submission['predictions']
    if not isinstance(predictions, list) or len(predictions) != len(queries):
        raise ValueError('exactly one trajectory per public query required')
    by_id = {}
    expected = {r['trial_id'] for r in queries}
    for row in predictions:
        if not isinstance(row, dict) or set(row) != {'trial_id', 'velocity_m_s'}:
            raise ValueError('prediction record keys')
        key, values = row['trial_id'], row['velocity_m_s']
        if not isinstance(key, str) or key not in expected or key in by_id:
            raise ValueError('unknown or duplicate query')
        if not isinstance(values, list) or len(values) != 30:
            raise ValueError('all 30 time bins required')
        for pair in values:
            if not isinstance(pair, list) or len(pair) != 2:
                raise ValueError('two native axes required')
            if any(type(x) not in (int, float) or abs(x) > 1e6 or not math.isfinite(x) for x in pair):
                raise ValueError('finite numeric velocities within declared ±1e6 m/s envelope')
        by_id[key] = values
    return [by_id[r['trial_id']] for r in queries]
