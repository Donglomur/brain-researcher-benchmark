"""Strict source-keyed public receipts, independent from the oracle."""
import csv
from decimal import Decimal, InvalidOperation
import json
import math
from pathlib import Path
import numpy as np
from memory_statistics import (ARRAY_FIELDS, POPULATIONS, METHOD_SHA256, SOURCE_SHA256,
    require, doubled_u, rank_measure, generate_masks, primitive_fingerprint, analyze, summarize)

TABLE_KEYS = {'sessions.csv': ['asset_path'], 'trials.csv': ['asset_path', 'source_trial_row'],
    'units.csv': ['asset_path', 'source_unit_row'], 'neurons.csv': ['unit_key'], 'split_events.csv': ['unit_key', 'repeat']}
TOLERANCES = {'auc': (1e-8, 0.), 'composed_auc': (2e-8, 0.), 'p': (1e-10, 1e-7),
              'time': (1e-9, 0.), 'exact': (0., 0.)}


def integer(value):
    require(not isinstance(value, (bool, np.bool_)), 'Boolean is not an integer')
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise AssertionError('Invalid integer')
    require(parsed.is_finite() and parsed == parsed.to_integral_value(), 'Nonfinite/fractional integer')
    return int(parsed)


def number(value):
    require(not isinstance(value, (bool, np.bool_)), 'Boolean is not a number')
    try:
        parsed = float(value)
    except (ValueError, TypeError, OverflowError):
        raise AssertionError('Invalid number')
    require(math.isfinite(parsed), 'Nonfinite number')
    return parsed


def flag(value):
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, str) and value.lower() in ('true', 'false'):
        return value.lower() == 'true'
    require((type(value) is int and value in (0, 1)) or
            (isinstance(value, str) and value in ('0', '1')), 'Invalid Boolean flag')
    return str(value) == '1'


def close(actual, expected, kind='auc', label='measurement'):
    a, b = number(actual), number(expected); atol, rtol = TOLERANCES[kind]
    require(abs(a-b) <= atol+rtol*abs(b), f'{label} differs from source/declared arithmetic')


def json_load(path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'Duplicate JSON key'); result[key] = value
        return result
    def invalid(value):
        raise AssertionError('Nonfinite JSON constant')
    result = json.loads(Path(path).read_text(), object_pairs_hook=pairs, parse_constant=invalid)
    def finite_tree(value):
        if isinstance(value, float):
            require(math.isfinite(value), 'Nonfinite JSON number')
        elif isinstance(value, dict):
            for item in value.values(): finite_tree(item)
        elif isinstance(value, list):
            for item in value: finite_tree(item)
    finite_tree(result)
    return result


def match(actual, expected, label='JSON', kind='auc', closed=False):
    if expected is None:
        require(actual is None, f'{label}: required undefined value must be null')
    elif isinstance(expected, bool):
        require(type(actual) is bool and actual == expected, f'{label}: wrong Boolean')
    elif isinstance(expected, int):
        require(type(actual) is int and actual == expected, f'{label}: wrong integer')
    elif isinstance(expected, float):
        require(type(actual) in (int, float), f'{label}: native JSON numeric required')
        close(actual, expected, kind, label)
    elif isinstance(expected, str):
        require(type(actual) is str and actual == expected, f'{label}: wrong string')
    elif isinstance(expected, list):
        require(isinstance(actual, list) and len(actual) == len(expected), f'{label}: wrong list')
        for index, value in enumerate(expected):
            match(actual[index], value, f'{label}[{index}]', kind, closed)
    elif isinstance(expected, dict):
        require(isinstance(actual, dict) and set(expected) <= set(actual), f'{label}: required keys missing')
        if closed:
            require(set(actual) == set(expected), f'{label}: unknown scientific keys')
        for key, value in expected.items():
            match(actual[key], value, f'{label}.{key}', kind, closed)
    else:
        raise AssertionError('Unsupported expected schema type')


def cell(value, descriptor):
    if value == '':
        require(descriptor.startswith('nullable_'), 'Unexpected empty CSV field'); return None
    if 'boolean' in descriptor:
        return flag(value)
    if 'integer' in descriptor:
        parsed = integer(value)
        if 'nonnegative' in descriptor:
            require(parsed >= 0, 'Negative count')
        return parsed
    if 'probability' in descriptor or descriptor == 'finite_float':
        parsed = number(value)
        if 'probability' in descriptor:
            require(0 <= parsed <= 1, 'Probability outside[0,1]')
        return parsed
    require(isinstance(value, str), 'Expected source string'); return value


def csv_load(path, specification):
    with Path(path).open(newline='', encoding='utf8') as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames is not None and len(reader.fieldnames) == len(set(reader.fieldnames)), 'Missing/duplicate CSV header')
        require(set(specification['columns']) <= set(reader.fieldnames), 'Required CSV columns missing')
        rows = []
        for raw in reader:
            require(None not in raw and all(raw[k] is not None for k in specification['columns']), 'Malformed CSV row')
            rows.append({k: cell(raw[k], specification['types'][k]) for k in specification['columns']})
    return rows


def keyed(rows, keys):
    result = {}
    for row in rows:
        require(isinstance(row, dict) and set(keys) <= set(row), 'Missing row identity')
        key = tuple(row[k] for k in keys)
        require(key not in result, 'Duplicate source row'); result[key] = row
    return result


def validate_table(actual, expected, keys):
    a, b = keyed(actual, keys), keyed(expected, keys)
    require(set(a) == set(b), 'Incomplete/wrong source row identities')
    for key, row in b.items():
        for field, wanted in row.items():
            require(field in a[key], 'Missing required measurement')
            kind = 'p' if field in ('full_p', 'train_p') else ('time' if field.endswith('_time_s') else 'auc')
            match(a[key][field], wanted, field, kind)
    return a


def axis_order(actual, expected, name):
    require(actual.ndim == expected.ndim == 1, f'Invalid {name} axis')
    values = actual.tolist()
    require(len(values) == len(set(values)) and set(values) == set(expected.tolist()), f'Wrong {name} source IDs')
    mapping = {value: i for i, value in enumerate(values)}
    return np.asarray([mapping[value] for value in expected.tolist()], dtype=np.int64)


def validate_arrays(path, ref):
    with np.load(path, allow_pickle=False) as archive:
        require(set(ARRAY_FIELDS) <= set(archive.files), 'Missing required response arrays')
        raw = {key: np.array(archive[key]) for key in archive.files}
    require(all(v.dtype.kind in 'biufUS' for v in raw.values()), 'Nonprimitive NPZ arrays')
    require(raw['unit_key'].dtype.kind == 'U', 'Unicode unit keys required')
    unit_order = axis_order(raw['unit_key'], ref['unit_key'], 'unit_key'); n = len(ref['spike_count'])
    for field in ('response_unit_index', 'source_trial_row', 'trial_id', 'source_label', 'spike_count', 'repeat_id'):
        require(raw[field].dtype.kind in 'iu' and raw[field].ndim == 1, f'Integer {field} required')
    for field in ARRAY_FIELDS[1:7]:
        require(raw[field].shape == (n,), f'Incomplete {field} response axis')
    unit_indices = raw['response_unit_index'].tolist()
    require(all(0 <= v < len(unit_order) for v in unit_indices), 'Invalid response unit index')
    names = raw['unit_key'].tolist()
    source_keys = [(ref['unit_key'][int(u)], int(t)) for u, t in zip(ref['response_unit_index'], ref['source_trial_row'])]
    actual_keys = [(names[u], int(t)) for u, t in zip(unit_indices, raw['source_trial_row'])]
    require(len(actual_keys) == len(set(actual_keys)) and set(actual_keys) == set(source_keys), 'Wrong/duplicate source response membership')
    lookup = {key: index for index, key in enumerate(actual_keys)}
    order = np.asarray([lookup[key] for key in source_keys], dtype=np.int64)
    repeat_order = axis_order(raw['repeat_id'], ref['repeat_id'], 'repeat_id')
    require(raw['train_membership'].dtype.kind == 'b' and raw['train_membership'].shape == (60, n), 'Wrong Boolean membership shape')
    actual = dict(unit_key=ref['unit_key'], response_unit_index=ref['response_unit_index'], repeat_id=ref['repeat_id'])
    for name in ('source_trial_row', 'trial_id', 'source_label', 'spike_count'):
        actual[name] = raw[name][order]
        require(actual[name].tolist() == ref[name].tolist(), f'{name} differs from original source')
    actual['train_membership'] = raw['train_membership'][np.ix_(repeat_order, order)]
    require(np.array_equal(actual['train_membership'], ref['train_membership']), 'Wrong frozen RNG split membership')
    rates = raw['rate_hz'][order]
    require(rates.dtype.kind == 'f' and np.isfinite(rates).all() and np.all(rates >= 0), 'Invalid rate receipt')
    require(np.all(np.abs(rates-ref['spike_count']/1.5) <= 1e-8), 'Incoherent source count/rate')
    actual['rate_hz'] = rates
    return actual


def validate_metadata(actual, ref, headline):
    wanted = ref['metadata']
    for name in ('status', 'task_id', 'dandiset_id', 'published_version', 'source_manifest_sha256', 'method_contract_sha256'):
        match(actual.get(name), wanted[name], name, 'exact')
    match(actual.get('headline_population'), headline, 'headline population')
    for name in ('source_sha256', 'method_contract'):
        match(actual.get(name), wanted[name], name, 'exact', closed=True)
    source = wanted['source_observed']; supplied = actual.get('source_observed')
    match(supplied, {k: v for k, v in source.items() if k != 'sessions'}, 'source observations', 'exact')
    a, b = keyed(supplied.get('sessions', []), ['asset_path']), keyed(source['sessions'], ['asset_path'])
    require(set(a) == set(b), 'Incomplete source session observations')
    for key, row in b.items():
        match(a[key], row, 'source session', 'exact')
        for field in ('phase_experiment_ids', 'clock_mapping_counts', 'label_membership_counts', 'unit_electrode_link_counts'):
            match(a[key][field], row[field], field, 'exact', closed=True)
    software = actual.get('software_versions')
    require(isinstance(software, dict) and software and all(isinstance(k, str) and k.strip() and
        isinstance(v, str) and v.strip() for k, v in software.items()), 'Actual software version mapping required')


def check_result(actual, expected, kind='auc'):
    require(isinstance(actual, dict), 'Results object required')
    for name in ('memory_selective_new_old_auc', 'proportion_memory_selective'):
        require(name in actual, 'Required result missing')
        if actual[name] is not None:
            require(0 <= number(actual[name]) <= 1, 'Result probability outside[0,1]')
    for row in actual.get('populations', {}).values():
        if isinstance(row, dict) and row.get('mean_auc') is not None:
            require(0 <= number(row['mean_auc']) <= 1, 'Population probability outside[0,1]')
    match(actual, expected, 'results', kind)
    for name in ('populations', 'population_overlap'):
        match(actual[name], expected[name], name, kind, closed=True)


def validate_arithmetic(tables, results, ref):
    # Individual fields have already passed the public1e-8 source-count bound.
    # A source-close component and source-close reported mean can round in opposite
    # directions: means, max(a,1-a) and direction reversal are1-Lipschitz, so their
    # internal cross-check needs the justified2e-8 sum of two serialization bounds.
    # This does NOT widen any field's comparison to exact count-derived values.
    events = keyed(tables['split_events.csv'], ['unit_key', 'repeat']); neurons = tables['neurons.csv']
    for row in neurons:
        selected = [events[(row['unit_key'], repeat)]['test_directed_auc'] for repeat in range(60)
                    if events[(row['unit_key'], repeat)]['included_in_conditional_summary']]
        require(row['n_selected_splits'] == len(selected), 'Incoherent selection count')
        if selected:
            close(row['conditional_auc'], math.fsum(selected)/len(selected), 'composed_auc', 'conditional split mean')
        else:
            require(row['conditional_auc'] is None, 'Undefined conditional mean required')
        if row['full_status'] == 'ok':
            close(row['auc_old'], row['u_old_twice']/(2*row['n_new']*row['n_old']), 'auc', 'full U/AUC')
            close(row['same_trial_auc'], max(row['auc_old'], 1-row['auc_old']), 'composed_auc', 'same-trial AUC')
    for row in events.values():
        if row['status'] != 'ok':
            continue
        close(row['train_auc_old'], row['train_u_old_twice']/(2*row['n_train_new']*row['n_train_old']), 'auc', 'train U/AUC')
        close(row['test_auc_old'], row['test_u_old_twice']/(2*row['n_test_new']*row['n_test_old']), 'auc', 'test U/AUC')
        directed = row['test_auc_old'] if row['train_preferred_sign'] == 1 else 1-row['test_auc_old']
        close(row['test_directed_auc'], directed, 'composed_auc', 'train-directed test AUC')
    check_result(results, summarize(ref, neurons, results['headline_population']), 'composed_auc')


def validate_output_directory(output, ref):
    root = Path(output); contract = ref['metadata']['method_contract']
    for name in contract['outputs']:
        require((root/name).is_file() and (root/name).stat().st_size > 0, f'Missing/empty {name}')
    tables = {name: csv_load(root/name, contract['outputs'][name]) for name in TABLE_KEYS}
    for name, source in [('sessions.csv', 'sessions'), ('trials.csv', 'trials'), ('units.csv', 'units')]:
        validate_table(tables[name], ref[source], TABLE_KEYS[name])
    validate_arrays(root/'trial_counts.npz', ref)
    derived = analyze(ref)
    validate_table(tables['split_events.csv'], derived['split_events'], TABLE_KEYS['split_events.csv'])
    validate_table(tables['neurons.csv'], derived['neurons'], TABLE_KEYS['neurons.csv'])
    results = json_load(root/'results.json')
    require(isinstance(results, dict) and results.get('headline_population') in POPULATIONS, 'Explicit valid headline required')
    check_result(results, summarize(ref, derived['neurons'], results['headline_population']))
    validate_arithmetic(tables, results, ref)
    validate_metadata(json_load(root/'run_metadata.json'), ref, results['headline_population'])
    require((root/'findings.md').read_text(encoding='utf8').strip(), 'Nonempty findings required')
