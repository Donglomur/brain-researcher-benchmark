"""Source-bound full FCz epoch validation, followed by own-epoch arithmetic."""
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import os
from pathlib import Path
import numpy as np
import epoch_contract as e

METHOD_SHA = 'e5725d66b28fdb429315721693dd740bc66cbf1cc3d6b92a2689e8a03e26fd1a'
SOURCE_SHA = '31b2d095d29abb0236d2439b67c1a7fc7c301c2562ee46de74f399934095df60'
FIF_SHA = 'ef6957cca68cb4f48d4a1c915e7991af7de91623607896d59b3dc39dcbae44b7'
BANK_SCHEMA = 'errmon-source-epochs-v2'
require = e.require


def safe_path(path):
    path = Path(path).absolute()
    require(not any(p.is_symlink() for p in (path, *path.parents)), f'symlink path: {path}')
    return path.resolve(strict=False)


def regular(path):
    path = safe_path(path)
    require(path.is_file(), f'regular file required: {path}')
    return path


def sha256(path):
    h = hashlib.sha256()
    with regular(path).open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def finite_json(value):
    if isinstance(value, float):
        require(math.isfinite(value), 'nonfinite JSON')
    elif isinstance(value, dict):
        for v in value.values():
            finite_json(v)
    elif isinstance(value, list):
        for v in value:
            finite_json(v)


def json_text(text):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, f'duplicate JSON key {key}')
            result[key] = value
        return result
    def constant(value):
        raise AssertionError(f'nonfinite JSON token {value}')
    value = json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    finite_json(value)
    return value


def read_json(path):
    return json_text(regular(path).read_text())


def integer(value, name='integer', allow_string=True):
    require(not isinstance(value, (bool, np.bool_)), f'{name}: Boolean is not integer')
    require(allow_string or isinstance(value, (int, float, np.integer, np.floating)), f'{name}: JSON number required')
    try:
        v = Decimal(str(value).strip())
    except InvalidOperation as exc:
        raise AssertionError(f'{name}: invalid integer') from exc
    require(v.is_finite() and v == v.to_integral_value(), f'{name}: exact integer required')
    return int(v)


def number(value, name='number', allow_string=True):
    require(not isinstance(value, (bool, np.bool_)), f'{name}: Boolean is not number')
    require(allow_string or isinstance(value, (int, float)), f'{name}: JSON number required')
    try:
        v = float(value)
    except (TypeError, ValueError) as exc:
        raise AssertionError(f'{name}: number required') from exc
    require(math.isfinite(v), f'{name}: finite required')
    return v


def close(actual, expected, atol=0., rtol=0., name='value'):
    a = number(actual, name)
    require(abs(a - expected) <= atol + rtol * abs(expected), f'{name}: numeric mismatch')


def match(actual, expected, atol=0., rtol=0., closed=False, name='JSON'):
    if isinstance(expected, dict):
        require(isinstance(actual, dict), f'{name}: object required')
        require(set(expected) <= set(actual), f'{name}: missing keys')
        if closed:
            require(set(actual) == set(expected), f'{name}: unexpected keys')
        for k, v in expected.items():
            match(actual[k], v, atol, rtol, closed, f'{name}.{k}')
    elif isinstance(expected, list):
        require(isinstance(actual, list) and len(actual) == len(expected), f'{name}: list shape')
        for a, b in zip(actual, expected):
            match(a, b, atol, rtol, closed, name)
    elif isinstance(expected, bool):
        require(type(actual) is bool and actual == expected, f'{name}: Boolean mismatch')
    elif expected is None:
        require(actual is None, f'{name}: null required')
    elif isinstance(expected, int):
        require(integer(actual, name, False) == expected, f'{name}: integer mismatch')
    elif isinstance(expected, float):
        close(number(actual, name, False), expected, atol, rtol, name)
    else:
        require(isinstance(actual, str) and actual == expected, f'{name}: string mismatch')


INTEGER_COLUMNS = {'annotation_index', 'event_sample', 'paired_stimulus_annotation_index',
                   'stimulus_annotation_index', 'stimulus_sample', 'response_annotation_index',
                   'response_sample', 'is_error', 'sample_offset'}


def table(path, columns, key, expected, method):
    with regular(path).open(newline='') as f:
        reader = csv.DictReader(f)
        require(reader.fieldnames is not None and len(set(reader.fieldnames)) == len(reader.fieldnames), 'CSV header')
        require(set(columns) <= set(reader.fieldnames), 'CSV required columns')
        rows = list(reader)
    indexed = {}
    for row in rows:
        require(None not in row and all(v is not None for v in row.values()), 'CSV malformed row')
        identity = integer(row[key], key)
        require(identity not in indexed, f'duplicate {key}')
        indexed[identity] = row
    require(set(indexed) == {r[key] for r in expected}, f'{path.name}: complete source keys required')
    for ref in expected:
        row = indexed[ref[key]]
        for col in columns:
            a, b = row[col].strip(), ref[col]
            if b is None:
                require(a == '', f'{col}: undefined must be blank')
            elif col in INTEGER_COLUMNS:
                require(integer(a, col) == b, f'{col}: source integer mismatch')
            elif isinstance(b, str):
                require(a == b, f'{col}: source category mismatch')
            elif col.endswith('_uv'):
                close(a, b, method['verification']['derived_atol_uv'], method['verification']['derived_rtol'], col)
            else:
                close(a, b, method['verification']['time_atol_seconds'], 0, col)
    return rows


def int_axis(array, name):
    require(array.ndim == 1 and array.dtype.kind in 'iuf', f'{name}: integer-valued numeric vector required')
    # Python integers preserve uint64/large float boundaries; avoid overflow through
    # an int64 cast or an imprecise float representation of INT64_MAX.
    values = [integer(v, name, False) for v in array]
    limit = np.iinfo(np.int64)
    require(all(limit.min <= v <= limit.max for v in values), f'{name}: integer overflow')
    result = np.asarray(values, dtype=np.int64)
    require(len(set(map(int, result))) == len(result), f'{name}: duplicate identity')
    return result


def epoch_arrays(path, ref):
    with np.load(regular(path), allow_pickle=False) as z:
        require(len(z.files) == len(set(z.files)), 'duplicate NPZ keys')
        require({'stimulus_annotation_index', 'sample_offset', 'fcz_prebaseline_uv'} <= set(z.files), 'NPZ missing keys')
        for name in z.files:
            require(not z[name].dtype.hasobject, 'NPZ object forbidden')
        keys = int_axis(z['stimulus_annotation_index'], 'stimulus_annotation_index')
        offsets = int_axis(z['sample_offset'], 'sample_offset')
        x = z['fcz_prebaseline_uv']
        require(x.dtype.kind in 'fiu' and x.shape == (len(keys), len(offsets)) and np.isfinite(x).all(), 'epoch numeric shape/finite')
        require(set(map(int, keys)) == set(map(int, ref['trial_ids'])), 'complete retained trial identity')
        require(set(map(int, offsets)) == set(map(int, ref['offsets'])), 'complete epoch time identity')
        rows = {int(v): i for i, v in enumerate(keys)}; cols = {int(v): i for i, v in enumerate(offsets)}
        x = np.asarray(x[np.ix_([rows[int(v)] for v in ref['trial_ids']],
                               [cols[int(v)] for v in ref['offsets']])], dtype=np.float64)
    v = ref['method']['verification']
    require(np.all(np.abs(x - ref['epochs']) <= v['source_epoch_atol_uv'] +
                   v['source_epoch_rtol'] * np.abs(ref['epochs'])), 'source epoch fidelity mismatch')
    return x


def public_method_path():
    local = Path(__file__).resolve().parents[1] / 'environment/method_contract.json'
    return local if local.is_file() else Path('/app/method_contract.json')


def load_reference(path=None):
    path = Path(path or os.environ.get('REPAIR_REFERENCE_PATH', Path(__file__).with_name('reference.npz')))
    with np.load(regular(path), allow_pickle=False) as z:
        require('schema' in z and str(z['schema']) == BANK_SCHEMA, 'obsolete/untrusted source bank')
        ref = {k: json_text(str(z[k + '_json'])) for k in ('method', 'metadata', 'annotations', 'trials')}
        ref.update(epochs=z['epochs'], trial_ids=z['trial_ids'], offsets=z['offsets'])
    require(sha256(public_method_path()) == METHOD_SHA, 'public method fingerprint')
    match(ref['method'], read_json(public_method_path()), closed=True)
    meta = ref['metadata']; method = ref['method']; inp = method['input']
    require(meta['method_contract_sha256'] == METHOD_SHA and meta['source_manifest_sha256'] == SOURCE_SHA and
            meta['source_fif_sha256'] == FIF_SHA, 'bank provenance')
    match(meta, dict(method_id=method['method_id'], sfreq_hz=inp['sfreq_hz'], n_samples=inp['n_samples'],
                    first_sample=inp['first_sample'], eeg_channels=inp['eeg_channels'], eog_channels=inp['eog_channels'],
                    bads=[], n_projectors=0, custom_ref_applied=1, historical_reference_known=False))
    ref['trial_ids'] = int_axis(ref['trial_ids'], 'bank trial IDs')
    ref['offsets'] = int_axis(ref['offsets'], 'bank offsets')
    require(np.array_equal(ref['offsets'], np.arange(-256, 564)), 'bank epoch clock')
    require(ref['epochs'].dtype == np.float64 and ref['epochs'].shape == (len(ref['trial_ids']), 820) and
            np.isfinite(ref['epochs']).all(), 'bank finite full epochs')
    require([r['annotation_index'] for r in ref['annotations']] == list(range(len(ref['annotations']))), 'bank original annotation axis')
    base = [{k: r[k] for k in ('annotation_index', 'onset_s', 'duration_s', 'description', 'event_sample')}
            for r in ref['annotations']]
    annotations, trials = e.ledger(base, method)
    match(ref['annotations'], annotations, closed=True); match(ref['trials'], trials, closed=True)
    require(list(ref['trial_ids']) == [r['stimulus_annotation_index'] for r in trials if r['epoch_status'] == 'retained'],
            'bank complete retained population')
    own = e.derive(ref['epochs'], ref['trial_ids'], ref['offsets'], annotations, trials, method)
    for key in ('status', 'n_annotations', 'n_stimuli', 'n_paired_trials', 'n_retained_trials'):
        match(meta[key], own['results'][key])
    return ref


def validate_output_directory(output_dir, ref=None):
    ref = load_reference() if ref is None else ref
    output = safe_path(output_dir); method = ref['method']; fields = method['outputs']; v = method['verification']
    for filename in fields:
        regular(output / filename)
    require((output / 'findings.md').read_text().strip(), 'nonempty findings required')
    table(output / 'annotations.csv', fields['annotations.csv'], 'annotation_index', ref['annotations'], method)
    x = epoch_arrays(output / 'response_epochs.npz', ref)
    own = e.derive(x, ref['trial_ids'], ref['offsets'], ref['annotations'], ref['trials'], method)
    table(output / 'trials.csv', fields['trials.csv'], 'stimulus_annotation_index', own['trials'], method)
    table(output / 'fcz_waveforms.csv', fields['fcz_waveforms.csv'], 'sample_offset', own['waveforms'], method)
    result = read_json(output / 'ern.json')
    require(isinstance(result, dict) and set(fields['ern.json']) <= set(result), 'required result fields')
    match(result, own['results'], v['derived_atol_uv'], v['derived_rtol'])
    metadata = read_json(output / 'run_metadata.json')
    require(isinstance(metadata, dict) and set(fields['run_metadata.json']) <= set(metadata), 'required metadata fields')
    for key in fields['run_metadata.json']:
        if key in ('software_versions', 'warnings'):
            continue
        expected = own['results'][key] if key in own['results'] else ref['metadata'][key]
        match(metadata[key], expected, name=key)
    versions = metadata['software_versions']
    require(isinstance(versions, dict) and versions and all(isinstance(k, str) and k.strip() for k in versions),
            'actual software versions object')
    require(isinstance(metadata['warnings'], list), 'warnings array')
    return own
