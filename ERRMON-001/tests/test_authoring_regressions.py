"""Manufactured parser, event and arithmetic regressions, not source results."""
import copy
import json
from pathlib import Path
import numpy as np
import pytest
import epoch_contract as e
import proof_of_work as p
from fixture_support import toy_reference, emit, read_table, write_table, write_json


@pytest.fixture
def ref():
    return toy_reference()


@pytest.fixture
def output(tmp_path, ref):
    emit(tmp_path, ref)
    return tmp_path


def test_manufactured_complete(output, ref):
    p.validate_output_directory(output, ref)


def test_source_pair_and_drop_ledger(ref):
    a, t = ref['annotations'], ref['trials']
    assert a[0]['disposition'] == 'orphan_response'
    assert a[5]['disposition'] == 'extra_response'
    assert a[11]['disposition'] == 'unmapped'
    assert [r['epoch_status'] for r in t] == ['outside_record', 'retained', 'retained', 'retained', 'unpaired', 'outside_record']
    assert a[3]['paired_stimulus_annotation_index'] == a[4]['paired_stimulus_annotation_index'] == 3
    assert a[5]['paired_stimulus_annotation_index'] is None
    assert t[2]['is_error'] == 1 and t[2]['compatibility'] == 'incompatible'


def test_same_sample_ties_fail(ref):
    rows = copy.deepcopy(ref['annotations']); rows[4]['event_sample'] = rows[3]['event_sample']
    with pytest.raises(AssertionError, match='tie'):
        e.ledger(rows, ref['method'])


@pytest.mark.parametrize('mode', ['zero', 'constant', 'positive_difference', 'negative_difference', 'error_empty', 'all_empty'])
def test_no_effect_direction_or_variation_gate(tmp_path, ref, mode):
    if mode in ('error_empty', 'all_empty'):
        for trial in ref['trials']:
            if trial['epoch_status'] == 'retained' and (mode == 'all_empty' or trial['is_error']):
                trial['epoch_status'] = 'outside_record'
        keep = [i for i, key in enumerate(ref['trial_ids']) if any(t['stimulus_annotation_index'] == key and
                t['epoch_status'] == 'retained' for t in ref['trials'])]
        ref['epochs'] = ref['epochs'][keep]; ref['trial_ids'] = ref['trial_ids'][keep]
    elif mode in ('zero', 'constant'):
        ref['epochs'][:] = 0 if mode == 'zero' else 123.4
    else:
        ref['epochs'][:] = 0
        i = next(i for i, key in enumerate(ref['trial_ids']) if any(t['stimulus_annotation_index'] == key and
                 t['is_error'] == 1 for t in ref['trials']))
        ref['epochs'][i, ref['offsets'] > 0] = 1 if mode == 'positive_difference' else -1
    own = emit(tmp_path, ref)
    ref['metadata']['status'] = own['results']['status']
    p.validate_output_directory(tmp_path, ref)
    if mode.endswith('empty'):
        assert own['results']['ern_amplitude_uv'] is None


def test_window_zero_in_both_and_minus205_excluded(ref):
    x = np.zeros_like(ref['epochs']); x[:, ref['offsets'] == -205] = 1000
    x[:, ref['offsets'] == 0] = 205
    own = e.derive(x, ref['trial_ids'], ref['offsets'], ref['annotations'], ref['trials'], ref['method'])
    t = next(t for t in own['trials'] if t['epoch_status'] == 'retained')
    assert t['baseline_mean_uv'] == 1
    assert t['window_mean_prebaseline_uv'] == 205 / 103
    assert t['window_mean_uv'] == pytest.approx(205 / 103 - 1)


@pytest.mark.parametrize('dtype', ['float32', 'float64', 'int64'])
def test_accepted_numeric_epoch_serialization(tmp_path, ref, dtype):
    if dtype == 'int64':
        ref['epochs'] = np.rint(ref['epochs'])
    emit(tmp_path, ref, ref['epochs'].astype(dtype))
    p.validate_output_directory(tmp_path, ref)


def test_axes_rows_columns_extras_and_float_ids(output, ref):
    np.savez(output / 'response_epochs.npz', stimulus_annotation_index=ref['trial_ids'][::-1].astype(float),
             sample_offset=ref['offsets'][::-1].astype(float), fcz_prebaseline_uv=ref['epochs'][::-1, ::-1], note=np.array('extra'))
    for name in ('annotations.csv', 'trials.csv', 'fcz_waveforms.csv'):
        rows, fields = read_table(output / name)
        for r in rows:
            for k in p.INTEGER_COLUMNS.intersection(r):
                if r[k]:
                    r[k] = f'{int(r[k]):.17e}'
            r['extra'] = 'ignored'
        write_table(output / name, rows[::-1], list(reversed(fields)) + ['extra'])
    meta = p.read_json(output / 'run_metadata.json'); meta['software_versions'] = {'my_reader': 2.0}
    meta['warnings'] = [{'category': 'Example', 'message': 'preserved'}]; meta['extra'] = {'valid': True}
    write_json(output / 'run_metadata.json', meta)
    p.validate_output_directory(output, ref)


@pytest.mark.parametrize('values', [[True], [1.5], [np.nan], [np.inf], [2**63], [1, 1]])
def test_bad_axes(values):
    with pytest.raises(AssertionError):
        p.int_axis(np.asarray(values), 'axis')


@pytest.mark.parametrize('value', ['NaN', 'Infinity', '-Infinity', '1e999', '{"x":1,"x":2}', '{"nested":[1e999]}'])
def test_json_nonfinite_and_duplicate(value):
    with pytest.raises(AssertionError):
        p.json_text(value)


@pytest.mark.parametrize('value', [True, '1', 1.5, float('nan')])
def test_json_integer_type(value):
    with pytest.raises(AssertionError):
        p.match(value, 1)


def test_large_integer_exactness():
    p.match(2**60 + 1, 2**60 + 1)
    with pytest.raises(AssertionError):
        p.match(2**60, 2**60 + 1)


@pytest.mark.parametrize('name', ['annotations.csv', 'trials.csv', 'response_epochs.npz', 'fcz_waveforms.csv',
                                'ern.json', 'run_metadata.json', 'findings.md'])
def test_missing_required(output, ref, name):
    (output / name).unlink()
    with pytest.raises(AssertionError):
        p.validate_output_directory(output, ref)


@pytest.mark.parametrize('name,key', [('annotations.csv', 'annotation_index'), ('trials.csv', 'stimulus_annotation_index'),
                                    ('fcz_waveforms.csv', 'sample_offset')])
@pytest.mark.parametrize('mode', ['drop', 'duplicate', 'fractional', 'bool'])
def test_table_key_integrity(output, ref, name, key, mode):
    rows, fields = read_table(output / name)
    if mode == 'drop': rows.pop()
    elif mode == 'duplicate': rows.append(rows[0])
    else: rows[0][key] = 'true' if mode == 'bool' else '1.5'
    write_table(output / name, rows, fields)
    with pytest.raises(AssertionError):
        p.validate_output_directory(output, ref)


@pytest.mark.parametrize('mode', ['shift', 'unit', 'flip', 'swap', 'baseline_already_removed'])
def test_coherent_source_wrong_epochs(tmp_path, ref, mode):
    x = ref['epochs'].copy()
    if mode == 'shift': x += 1
    elif mode == 'unit': x *= 1e-6
    elif mode == 'flip': x *= -1
    elif mode == 'swap': x = x[::-1]
    else: x -= x[:, (ref['offsets'] >= -204) & (ref['offsets'] <= 0)].mean(axis=1)[:, None]
    emit(tmp_path, ref, x)
    with pytest.raises(AssertionError, match='source epoch'):
        p.validate_output_directory(tmp_path, ref)


def test_derived_uses_accepted_epochs_not_second_bank_target(tmp_path, ref):
    # Small source-allowed perturbation to every postzero sample accumulates in
    # the contrast. All public scalar targets follow accepted X, not bank X.
    x = ref['epochs'].copy(); x[1, ref['offsets'] > 0] += 8e-7
    emit(tmp_path, ref, x)
    p.validate_output_directory(tmp_path, ref)
    result = p.read_json(tmp_path / 'ern.json'); result['ern_amplitude_uv'] += 1e-3
    write_json(tmp_path / 'ern.json', result)
    with pytest.raises(AssertionError, match='ern_amplitude'):
        p.validate_output_directory(tmp_path, ref)


def test_wrong_scalar_cancellation_still_checks_trials(output, ref):
    rows, fields = read_table(output / 'trials.csv')
    valid = [r for r in rows if r['epoch_status'] == 'retained']
    valid[0]['window_mean_uv'] = str(float(valid[0]['window_mean_uv']) + .1)
    valid[-1]['window_mean_uv'] = str(float(valid[-1]['window_mean_uv']) - .1)
    write_table(output / 'trials.csv', rows, fields)
    with pytest.raises(AssertionError, match='window_mean_uv'):
        p.validate_output_directory(output, ref)


def test_obsolete_bank_always_rejected(tmp_path):
    path = tmp_path / 'old.npz'; np.savez(path, ref_stats=np.array([1.]))
    with pytest.raises(AssertionError, match='obsolete'):
        p.load_reference(path)
