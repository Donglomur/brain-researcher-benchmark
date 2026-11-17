"""Completed-curve numerical scoring; never executes submitted programs."""
import hashlib
import json
import math
import os
from pathlib import Path
import stat


def need(ok, message):
    if not ok:
        raise ValueError(message)


def unique(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, 'duplicate JSON field')
        result[key] = value
    return result


def bad_constant(value):
    raise ValueError('nonfinite JSON token: '+value)


def decode(body):
    return json.loads(body, object_pairs_hook=unique, parse_constant=bad_constant)


def read_pinned(path, pin, cap):
    need(type(pin['bytes']) is int and 0 <= pin['bytes'] <= cap, 'bounded pinned input')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and before.st_size == pin['bytes'], 'ordinary exact-size input')
        pieces = []; remaining = before.st_size
        while remaining:
            part = os.read(fd, min(65536, remaining))
            need(bool(part), 'truncated input'); pieces.append(part); remaining -= len(part)
        after = os.fstat(fd)
        need(not os.read(fd, 1) and all(getattr(before, k) == getattr(after, k)
             for k in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_nlink')),
             'input changed while reading')
        body = b''.join(pieces)
        need(hashlib.sha256(body).hexdigest() == pin['sha256'], 'input hash mismatch')
        return body
    finally:
        os.close(fd)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate(obj, design):
    need(type(obj) is dict and set(obj) == {'schema_version', 'records'}
         and type(obj['schema_version']) is int and obj['schema_version'] == 1, 'exact schema')
    need(type(obj['records']) is list and len(obj['records']) == 300, '300 records required')
    expected = {(r, c, t) for r in design['regions'] for c in design['conditions'] for t in design['time']}
    result = {}
    for row in obj['records']:
        need(type(row) is dict and set(row) == {'region', 'condition', 'time', 'mean', 'sem', 'defined_cells'}, 'exact record fields')
        need(type(row['region']) is str and type(row['condition']) is str and finite(row['time']), 'typed identity')
        key = (row['region'], row['condition'], row['time'])
        need(key in expected and key not in result, 'unexpected or duplicate record')
        n = row['defined_cells']
        need(type(n) is int and 0 <= n <= design['regions'][key[0]]['cells'], 'bounded integer cell count')
        if n == 0:
            need(row['mean'] is None and row['sem'] is None, 'zero cells requires null mean/SEM')
        else:
            need(finite(row['mean']) and -1 <= row['mean'] <= 1 and finite(row['sem'])
                 and 0 <= row['sem'] <= 1, 'finite cosine mean/SEM range')
            need(n != 1 or row['sem'] == 0, 'singleton sample SEM is zero')
        result[key] = row
    need(set(result) == expected, 'complete curve coverage')
    return result


def calculate(candidate, reference, design):
    groups = []; undefined_mismatches = []
    for region in design['regions']:
        for condition in design['conditions']:
            gold = reference['panels'][region]['source_'+condition]
            need(len(gold['mean']) == len(gold['sample_sem_across_neurons']) == len(gold['defined_cells']) == 50, 'private curve shape')
            mean_errors = []; sem_errors = []; counts = []
            for index, tick in enumerate(design['time']):
                row = candidate[region, condition, tick]
                n = gold['defined_cells'][index]; mean = gold['mean'][index]; sem = gold['sample_sem_across_neurons'][index]
                need(type(n) is int and 0 <= n <= design['regions'][region]['cells'], 'private count')
                need((n == 0 and mean is None and sem is None) or (n > 0 and finite(mean) and finite(sem)), 'private undefined policy')
                counts.append(row['defined_cells']-n)
                if (row['defined_cells'] == 0) != (n == 0):
                    undefined_mismatches.append({'region': region, 'condition': condition, 'time': tick})
                elif n > 0:
                    mean_errors.append(row['mean']-mean); sem_errors.append(row['sem']-sem)
            rms = lambda values: math.sqrt(math.fsum(v*v for v in values)/len(values)) if values else None
            groups.append({'region': region, 'condition': condition,
                           'mean_RMSE': rms(mean_errors), 'sem_RMSE': rms(sem_errors),
                           'defined_count_MAE': math.fsum(abs(v) for v in counts)/50,
                           'defined_count_mismatch_n': sum(v != 0 for v in counts),
                           'compared_finite_times': len(mean_errors)})
    if undefined_mismatches:
        return {'status': 'incompatible_undefined_pattern', 'score': None,
                'undefined_mismatch_n': len(undefined_mismatches), 'undefined_mismatches': undefined_mismatches,
                'groups': groups}
    need(all(g['mean_RMSE'] is not None for g in groups), 'private group has no comparable finite values')
    return {'status': 'scored', 'score': math.fsum(g['mean_RMSE'] for g in groups)/6,
            'metrics': {'equal_region_type_mean_curve_RMSE': math.fsum(g['mean_RMSE'] for g in groups)/6,
                        'equal_region_type_sem_RMSE': math.fsum(g['sem_RMSE'] for g in groups)/6,
                        'equal_region_type_defined_count_MAE': math.fsum(g['defined_count_MAE'] for g in groups)/6},
            'defined_count_mismatch_n': sum(g['defined_count_mismatch_n'] for g in groups),
            'undefined_mismatch_n': 0, 'groups': groups}


def main():
    private_loads = 0
    try:
        assets = decode(Path('/source/operator_assets.json').read_bytes())
        invocation = decode(Path('/source/invocation.json').read_bytes())
        design = decode(read_pinned('/source/public_design.json', assets['source_files']['public_design.json'], 100000))
        try:
            candidate = validate(decode(read_pinned('/submission/predictions.json', invocation['submission'], assets['max_submission_bytes'])), design)
        except Exception as exc:
            print(json.dumps({'status': 'invalid_submission', 'score': None, 'reason': str(exc), 'private_numeric_loads': 0})); return 2
        private_loads += 1
        reference = decode(read_pinned('/private/expected.json', assets['expected'], 100000))
        need(reference['status'] == 'bounded_stable_centered_reference_completed', 'private reference status')
        result = calculate(candidate, reference, design)
        result.update(metric='equal_region_type_mean_curve_RMSE', direction='lower', private_numeric_loads=private_loads,
                      scientific_success_threshold=None, candidate_code_executed=False, candidate_chronology_verified=False,
                      full_contract_qualified=False, improvement_qualified=False,
                      scope='Six archived stable-centered 50-ms numerical curves; descriptive neuron SEM, not whole-paper or population inference')
        print(json.dumps(result, allow_nan=False)); return 0 if result['status'] == 'scored' else 2
    except Exception as exc:
        print(json.dumps({'status': 'operator_error', 'score': None, 'reason': str(exc), 'private_numeric_loads': private_loads})); return 1


if __name__ == '__main__':
    raise SystemExit(main())
