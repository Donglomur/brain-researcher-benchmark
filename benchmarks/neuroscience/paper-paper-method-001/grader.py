"""Continuous reconstruction score; validates candidate records before gold decode."""
import hashlib
import json
import math
from pathlib import Path


def need(ok, message):
    if not ok:
        raise ValueError(message)


def unique(pairs):
    out = {}
    for key, value in pairs:
        need(key not in out, 'duplicate JSON object key')
        out[key] = value
    return out


def read_json(path, cap, expected=None):
    with Path(path).open('rb') as f:
        raw = f.read(cap + 1)
    need(len(raw) <= cap, 'input byte limit')
    if expected is not None:
        need(len(raw) == expected['bytes'] and hashlib.sha256(raw).hexdigest() == expected['sha256'], 'artifact identity')
    return json.loads(raw, object_pairs_hook=unique,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite JSON token')))


def validate(value, design):
    need(type(value) is dict and set(value) == {'records'}, 'exact records object required')
    rows = value['records']
    expected = {(p['point'], e) for p in design['cases'] for e in design['estimators']}
    need(type(rows) is list and len(rows) == len(expected), 'complete76-record panel required')
    result = {}
    for row in rows:
        need(type(row) is dict and set(row) == {'point', 'estimator', 'A', 'B', 'ratio'}, 'record fields')
        need(type(row['point']) is str and type(row['estimator']) is str, 'string identity')
        key = row['point'], row['estimator']
        need(key in expected and key not in result, 'unknown or duplicate record')
        parsed = {}
        for field in ('A', 'B', 'ratio'):
            x = row[field]
            need(type(x) in (int, float), 'real number required')
            x = float(x)
            need(math.isfinite(x) and abs(x) <= 1e100, 'finite bounded numerical value')
            parsed[field] = x
        result[key] = parsed
    need(set(result) == expected, 'complete exact panel')
    return result


def rms(values):
    return math.sqrt(math.fsum(x*x for x in values) / len(values))


def main():
    gold_loads = 0
    plan = read_json('/source/operator_assets.json', 100000)
    design = read_json('/source/public_design.json', 600000, plan['public_design'])
    invocation = read_json('/source/invocation.json', 100000)
    try:
        candidate = validate(read_json('/submission/predictions.json', plan['max_submission_bytes'], invocation['submission']), design)
    except (ValueError, TypeError, OverflowError, RecursionError) as exc:
        print(json.dumps({'status': 'invalid_submission', 'score': None, 'reason': str(exc), 'private_numeric_loads': 0}))
        return 2
    # Host hashes these bytes for integrity earlier. Numeric decoding only starts
    # after the complete public submission schema passes in this worker.
    raw = read_json('/private/expected.json', 600000, plan['expected'])
    gold_loads += 1
    points = {'full': raw['full_reference']}
    for point in raw['points']:
        if not point['reuses_full_reference']:
            points[point['axis'] + str(point['grid_index'])] = point['moments']
    need(set(points) == {p['point'] for p in design['cases']}, 'private/public panel identity')
    errors = {group: {field: [] for field in ('A', 'B', 'ratio')} for group in ('full', 'nonfull')}
    details = []
    for (point, estimator), values in sorted(candidate.items()):
        target = points[point][estimator]
        group = 'full' if point == 'full' else 'nonfull'
        delta = {}
        for field in ('A', 'B', 'ratio'):
            expected = target[field]
            need(type(expected) in (int, float) and math.isfinite(expected) and expected != 0, 'qualified nonzero reference required')
            relative = (values[field] - expected) / abs(expected)
            need(math.isfinite(relative), 'finite score arithmetic')
            errors[group][field].append(relative)
            delta[field] = relative
        details.append({'point': point, 'estimator': estimator, 'signed_relative_errors': delta})
    scores = {group + '_' + field + '_relative_RMSE': rms(values)
              for group, fields in errors.items() for field, values in fields.items()}
    report = {'status': 'scored', 'score': scores['full_ratio_relative_RMSE'],
        'direction': 'lower', 'primary_metric': 'full_ratio_relative_RMSE',
        'metrics': scores, 'record_count': len(candidate), 'nested_panels': len(points),
        'independent_animals': 1, 'private_numeric_loads': gold_loads,
        'signed_record_errors': details, 'success_threshold': None,
        'scientific_reconstruction_only': True, 'candidate_program_or_chronology_verified': False,
        'whole_paper_or_improvement_qualified': False}
    print(json.dumps(report, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
