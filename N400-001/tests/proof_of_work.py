"""Source-bound N400 receipt validation; no estimator or outcome-direction gate."""
from __future__ import annotations
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
from pathlib import Path
import numpy as np

PIPELINE = 'erpcore-n400-target-subset-v2'
TASK = 'N400-001'
SUBJECTS = list(range(1, 13))
KEYS = {'source_events.csv': ('subject', 'event_index'), 'segments.csv': ('subject', 'segment_id'),
        'trial_measurements.csv': ('subject', 'event_index'), 'curves.csv': ('subject', 'sample_offset'),
        'per_subject.csv': ('subject',)}
INTEGER_FIELDS = {'subject', 'event_index', 'event_sample', 'boundary_cut_sample', 'segment_id',
                  'start_sample', 'end_sample_exclusive', 'n_samples', 'filter_length', 'pad_samples',
                  'epoch_start_sample', 'epoch_end_sample_exclusive', 'sample_offset',
                  'n_related_candidate', 'n_unrelated_candidate', 'n_related_retained',
                  'n_unrelated_retained', 'n_related_dropped', 'n_unrelated_dropped'}
SOURCE_FLOAT_FIELDS = {'latency_samples', 'duration_samples', 'time_ms'}
AMPLITUDE_FIELDS = {'baseline_uv', 'window_raw_mean_uv', 'window_baseline_corrected_uv',
                    'related_uv', 'unrelated_uv', 'difference_uv', 'n400_uv'}
NULLABLE = {'duration_samples', 'event_sample', 'boundary_cut_sample', 'segment_id',
            'baseline_uv', 'window_raw_mean_uv', 'window_baseline_corrected_uv'}

def require(condition, message):
    if not condition:
        raise AssertionError(message)

def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()

def read_json(path):
    def reject_constant(value):
        raise AssertionError(f'Nonfinite JSON constant {value}')
    def unique_pairs(pairs):
        out = {}
        for key, value in pairs:
            require(key not in out, f'Duplicate JSON key {key}')
            out[key] = value
        return out
    return json.loads(Path(path).read_text(), parse_constant=reject_constant, object_pairs_hook=unique_pairs)

def number(value, label='number'):
    require(not isinstance(value, (bool, np.bool_)), f'{label}: boolean is not a number')
    require(isinstance(value, (str, int, float, np.integer, np.floating)), f'{label}: invalid numeric type')
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise AssertionError(f'{label}: invalid number') from exc
    require(math.isfinite(result), f'{label}: nonfinite number')
    return result

def integer(value, label='integer'):
    require(not isinstance(value, (bool, np.bool_)), f'{label}: boolean integer')
    try:
        result = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise AssertionError(f'{label}: invalid integer') from exc
    require(result.is_finite() and result == result.to_integral_value(), f'{label}: noninteger')
    return int(result)

def boolean(value, label='boolean'):
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in {'true', 'false'}:
        return value.strip().lower() == 'true'
    result = integer(value, label)
    require(result in (0, 1), f'{label}: not boolean')
    return bool(result)

def close(value, expected, label, atol=1e-6, rtol=1e-6):
    value, expected = number(value, label), number(expected, label)
    require(abs(value - expected) <= atol + rtol * abs(expected), f'{label}: numeric/source mismatch')

def exact(value, expected, label, *, closed=True, float_atol=1e-9):
    if isinstance(expected, dict):
        require(isinstance(value, dict), f'{label}: expected object')
        require(set(expected) <= set(value), f'{label}: missing keys')
        if closed:
            require(set(value) == set(expected), f'{label}: unexpected keys')
        for key in expected:
            exact(value[key], expected[key], f'{label}.{key}', closed=closed, float_atol=float_atol)
    elif isinstance(expected, list):
        require(isinstance(value, list) and len(value) == len(expected), f'{label}: list shape')
        for index, (actual, reference) in enumerate(zip(value, expected)):
            exact(actual, reference, f'{label}[{index}]', closed=closed, float_atol=float_atol)
    elif isinstance(expected, bool):
        require(isinstance(value, bool) and value == expected, f'{label}: boolean mismatch')
    elif isinstance(expected, int):
        require(isinstance(value, (int, float)) and not isinstance(value, bool), f'{label}: numeric JSON type')
        require(integer(value, label) == expected, f'{label}: integer mismatch')
    elif isinstance(expected, float):
        require(isinstance(value, (int, float)) and not isinstance(value, bool), f'{label}: numeric JSON type')
        close(value, expected, label, atol=float_atol, rtol=0)
    else:
        require(type(value) is type(expected) and value == expected, f'{label}: value mismatch')

def parse_field(name, value):
    require(value is not None, f'{name}: missing CSV cell')
    value = value.strip()
    if value == '' and name in NULLABLE:
        return None
    if name in INTEGER_FIELDS:
        return integer(value, name)
    if name == 'retained':
        return boolean(value, name)
    if name in SOURCE_FLOAT_FIELDS | AMPLITUDE_FIELDS:
        return number(value, name)
    return value

def read_table(path, fields, keys):
    with Path(path).open(newline='') as handle:
        reader = csv.DictReader(handle)
        require(reader.fieldnames is not None and len(reader.fieldnames) == len(set(reader.fieldnames)), 'CSV duplicate/missing header')
        require(set(fields) <= set(reader.fieldnames), f'{Path(path).name}: missing columns')
        rows = {}
        for raw in reader:
            require(None not in raw, 'CSV malformed row width')
            row = {name: parse_field(name, raw[name]) for name in fields}
            key = tuple(row[name] for name in keys)
            require(key not in rows, f'{Path(path).name}: duplicate identity')
            rows[key] = row
    return rows

def index_rows(rows, keys):
    out = {tuple(row[key] for key in keys): row for row in rows}
    require(len(out) == len(rows), 'Reference duplicate identity')
    return out

def compare_table(actual, expected, name):
    require(set(actual) == set(expected), f'{name}: incomplete or wrong source membership')
    for key, reference in expected.items():
        for field, target in reference.items():
            value = actual[key][field]
            label = f'{name}{key}.{field}'
            if target is None:
                require(value is None, f'{label}: undefined must be blank')
            elif field in AMPLITUDE_FIELDS:
                close(value, target, label)
            elif field in SOURCE_FLOAT_FIELDS:
                close(value, target, label, atol=1e-9, rtol=0)
            else:
                require(value == target and not (isinstance(value, bool) and not isinstance(target, bool)), f'{label}: source/category mismatch')

def uncertainty(value):
    return 1e-6 + 1e-6 * abs(float(value))

def algebra(value, expression, terms, label):
    # A submitted result and each contributing input may be independently rounded.
    budget = uncertainty(value) + sum(abs(weight) * uncertainty(reference) for weight, reference in terms)
    require(abs(value - expression) <= budget + 1e-12, f'{label}: inconsistent arithmetic')

def mean(values):
    require(len(values) > 0, 'Empty support')
    return math.fsum(values) / len(values)

def validate_algebra(tables, reference_tables, result):
    trials = tables['trial_measurements.csv']
    source_trials = reference_tables['trial_measurements.csv']
    for key, row in trials.items():
        if row['status'] != 'retained':
            continue
        ref = source_trials[key]
        algebra(row['window_baseline_corrected_uv'], row['window_raw_mean_uv'] - row['baseline_uv'],
                [(1, ref['window_raw_mean_uv']), (-1, ref['baseline_uv'])], 'Trial baseline subtraction')
    for key, row in tables['curves.csv'].items():
        ref = reference_tables['curves.csv'][key]
        algebra(row['difference_uv'], row['unrelated_uv'] - row['related_uv'],
                [(1, ref['unrelated_uv']), (-1, ref['related_uv'])], 'Curve signed difference')
    for key, row in tables['per_subject.csv'].items():
        subject = key[0]
        ref_subject = reference_tables['per_subject.csv'][key]
        for condition in ('related', 'unrelated'):
            selected = [k for k, r in trials.items() if r['subject'] == subject and r['condition'] == condition and r['status'] == 'retained']
            terms = [(1 / len(selected), source_trials[k]['window_baseline_corrected_uv']) for k in selected]
            algebra(row[f'{condition}_uv'], mean([trials[k]['window_baseline_corrected_uv'] for k in selected]), terms, 'Subject equal-trial mean')
            curve_keys = [(subject, offset) for offset in range(77, 129)]
            terms = [(1 / 52, reference_tables['curves.csv'][k][f'{condition}_uv']) for k in curve_keys]
            algebra(row[f'{condition}_uv'], mean([tables['curves.csv'][k][f'{condition}_uv'] for k in curve_keys]), terms, 'Curve measurement mean')
            baseline_keys = [(subject, offset) for offset in range(-51, 1)]
            baseline = mean([tables['curves.csv'][k][f'{condition}_uv'] for k in baseline_keys])
            budget = mean([uncertainty(reference_tables['curves.csv'][k][f'{condition}_uv']) for k in baseline_keys])
            require(abs(baseline) <= budget + 1e-12, 'Curve baseline does not average to zero')
        algebra(row['n400_uv'], row['unrelated_uv'] - row['related_uv'],
                [(1, ref_subject['unrelated_uv']), (-1, ref_subject['related_uv'])], 'Subject signed contrast')
    for field, output in (('n400_uv', 'n400_difference_amplitude_uv'), ('related_uv', 'related_mean_amplitude_uv'), ('unrelated_uv', 'unrelated_mean_amplitude_uv')):
        keys = sorted(tables['per_subject.csv'])
        algebra(number(result[output], output), mean([tables['per_subject.csv'][k][field] for k in keys]),
                [(1 / len(keys), reference_tables['per_subject.csv'][k][field]) for k in keys], 'Equal-subject headline')

def validate_metadata(actual, expected):
    require(isinstance(actual, dict), 'Metadata must be an object')
    for key, value in expected.items():
        if key == 'software_versions':
            continue
        require(key in actual, f'Missing metadata {key}')
        if key == 'source_observed':
            require(isinstance(actual[key], dict) and 'subjects' in actual[key], 'source_observed schema')
            rows = actual[key]['subjects']
            require(isinstance(rows, list), 'source_observed.subjects must be a list')
            indexed = {}
            for row in rows:
                require(isinstance(row, dict) and 'subject' in row, 'Source subject metadata missing')
                subject = integer(row['subject'])
                require(subject not in indexed, 'Duplicate metadata subject')
                indexed[subject] = row
            expected_rows = {row['subject']: row for row in value['subjects']}
            require(set(indexed) == set(expected_rows), 'Metadata source subject membership')
            for subject in indexed:
                require(set(expected_rows[subject]) <= set(indexed[subject]), 'Missing observed subject fields')
                selected = {key: indexed[subject][key] for key in expected_rows[subject]}
                exact(selected, expected_rows[subject], f'source_observed.subjects[{subject}]')
        else:
            exact(actual[key], value, f'metadata.{key}', float_atol=0 if key == 'method_contract' else 1e-9)
    versions = actual.get('software_versions')
    require(isinstance(versions, dict) and versions and all(isinstance(k, str) and k.strip() and isinstance(v, str) and v.strip() for k, v in versions.items()), 'software_versions must report a nonempty actual stack')

def load_reference(path=None):
    path = Path(path) if path else Path(__file__).with_name('reference.npz')
    with np.load(path, allow_pickle=False) as archive:
        require('reference_json' in archive, 'Obsolete reference bank; independent original-source rebuild required')
        payload = json.loads(str(archive['reference_json'].item()))
    require(payload.get('pipeline_id') == PIPELINE, 'Reference pipeline mismatch')
    require(payload.get('provenance') == 'independent-original-set-fdt-scipy', 'Reference provenance mismatch')
    require(set(payload['tables']) == set(KEYS), 'Reference table set mismatch')
    require(payload['results']['subject_ids'] == SUBJECTS, 'Reference subject membership')
    require(payload['results']['n_subjects'] == 12 and payload['results']['n_target_events'] == 1440, 'Reference full source support')
    require(len(payload['tables']['source_events.csv']) == 4343, 'Reference incomplete source events')
    metadata = payload['metadata']
    require(metadata['pipeline_id'] == PIPELINE and metadata['status'] == 'ok', 'Reference metadata identity')
    require(len(metadata['source_sha256']) == 24 and all(isinstance(v, str) and len(v) == 64 for v in metadata['source_sha256'].values()), 'Reference source hashes')
    require(metadata['method_contract']['pipeline_id'] == PIPELINE, 'Reference method contract')
    for name, rows in payload['tables'].items():
        index_rows(rows, KEYS[name])
        for row in rows:
            for field in AMPLITUDE_FIELDS | SOURCE_FLOAT_FIELDS:
                if field in row and row[field] is not None:
                    number(row[field], 'Reference numeric')
    indexed = {name: index_rows(rows, KEYS[name]) for name, rows in payload['tables'].items()}
    validate_algebra(indexed, indexed, payload['results'])
    return payload

def validate_output_directory(output, reference=None):
    output = Path(output)
    reference = load_reference() if reference is None else reference
    contract = reference['metadata']['method_contract']
    expected_tables = {name: index_rows(rows, KEYS[name]) for name, rows in reference['tables'].items()}
    tables = {}
    for name in KEYS:
        require((output / name).is_file(), f'Missing {name}')
        tables[name] = read_table(output / name, contract['outputs'][name], KEYS[name])
        compare_table(tables[name], expected_tables[name], name)
    result = read_json(output / 'n400.json')
    require(isinstance(result, dict), 'n400.json must be an object')
    for field, expected in reference['results'].items():
        require(field in result, f'Missing result {field}')
        if field.endswith('amplitude_uv'):
            require(isinstance(result[field], (int, float)) and not isinstance(result[field], bool), 'Result numeric type')
            close(result[field], expected, field)
        elif field == 'subject_ids':
            require(isinstance(result[field], list), 'subject_ids must be a list')
            values = [integer(v, field) for v in result[field]]
            require(sorted(values) == sorted(expected), 'Result subject membership')
        else:
            exact(result[field], expected, f'result.{field}')
    validate_algebra(tables, expected_tables, result)
    validate_metadata(read_json(output / 'run_metadata.json'), reference['metadata'])
    require((output / 'findings.md').is_file() and (output / 'findings.md').read_text().strip(), 'Missing/empty findings')
    return tables
