"""Genuine-source positives and declared mutations; never used to construct the bank."""
import json
import os
from pathlib import Path
import shutil
import tempfile
import numpy as np
import pytest
import proof_of_work as p
from fixture_support import emit, read_table, write_table, write_json


@pytest.fixture(scope='module')
def ref():
    return p.load_reference()


def supplied_path(name):
    value = os.environ.get(name)
    if value is None:
        pytest.skip(f'{name} not supplied: actual source execution is separately gated')
    path = Path(value)
    assert path.is_dir(), f'Supplied genuine evidence path does not exist: {name}'
    return path


@pytest.fixture
def output(tmp_path):
    source = supplied_path('REPAIR_ORACLE_OUTPUT')
    with tempfile.TemporaryDirectory(prefix='owned-case-', dir=tmp_path) as folder:
        target = Path(folder)
        for name in ('annotations.csv', 'trials.csv', 'response_epochs.npz', 'fcz_waveforms.csv',
                     'ern.json', 'run_metadata.json', 'findings.md'):
            shutil.copyfile(source / name, target / name)
        yield target


def reject(output, ref, match=None):
    with pytest.raises((AssertionError, ValueError, TypeError, KeyError, EOFError, OSError), match=match):
        p.validate_output_directory(output, ref)


def replace_npz(path, modify):
    with np.load(path, allow_pickle=False) as z:
        arrays = {k: z[k] for k in z.files}
    modify(arrays)
    np.savez_compressed(path, **arrays)


@pytest.mark.parametrize('variable', ['REPAIR_ORACLE_OUTPUT', 'REPAIR_INDEPENDENT_OUTPUT'])
def test_genuine_complete(variable, ref):
    p.validate_output_directory(supplied_path(variable), ref)


def test_genuine_float32_epochs_and_own_arithmetic(output, ref):
    emit(output, ref, ref['epochs'].astype(np.float32))
    p.validate_output_directory(output, ref)


def test_genuine_reordered_equivalent_serialization(output, ref):
    def transform(a):
        a['stimulus_annotation_index'] = a['stimulus_annotation_index'][::-1].astype(float)
        a['sample_offset'] = a['sample_offset'][::-1].astype(float)
        a['fcz_prebaseline_uv'] = a['fcz_prebaseline_uv'][::-1, ::-1]
        a['extra'] = np.array('harmless')
    replace_npz(output / 'response_epochs.npz', transform)
    for name in ('annotations.csv', 'trials.csv', 'fcz_waveforms.csv'):
        rows, fields = read_table(output / name)
        for row in rows:
            for key, val in tuple(row.items()):
                if val and key in p.INTEGER_COLUMNS:
                    row[key] = f'{p.integer(val):.17e}'
                    assert p.integer(row[key]) == p.integer(val)
                elif val and key.endswith('_uv'):
                    row[key] = f'{float(val):.10f}'
            row['extra'] = 'descriptive extra'
        write_table(output / name, rows[::-1], list(reversed(fields)) + ['extra'])
    p.validate_output_directory(output, ref)


def test_genuine_free_prose_versions_warnings_extras(output, ref):
    (output / 'findings.md').write_text('A descriptive within-person computation; interpretation is limited.')
    for filename in ('ern.json', 'run_metadata.json'):
        data = p.read_json(output / filename); data['optional_analysis'] = {'positive': None, 'notes': ['ungraded']}
        if filename == 'run_metadata.json':
            data['software_versions'] = {'equivalent_implementation': 3}
            data['warnings'] = [{'category': 'diagnostic', 'message': 'format example'}]
        write_json(output / filename, data)
    p.validate_output_directory(output, ref)


def test_genuine_source_tolerance_own_recomputation(output, ref):
    x = ref['epochs'].copy(); x[:, ref['offsets'] > 0] += 4e-7
    emit(output, ref, x)
    p.validate_output_directory(output, ref)


@pytest.mark.parametrize('variable', ['REPAIR_STIMULUS_CONTROL', 'REPAIR_EOG_CONTROL'])
def test_genuine_wrong_component_rejected_numerically(variable, ref, record_property):
    output = supplied_path(variable)
    # Original-source recomputations, not hand-edited correct outputs. The
    # truthful source annotation ledger must pass before numerical rejection.
    p.table(output / 'annotations.csv', ref['method']['outputs']['annotations.csv'],
            'annotation_index', ref['annotations'], ref['method'])
    with np.load(output / 'response_epochs.npz', allow_pickle=False) as arrays:
        ids = p.int_axis(arrays['stimulus_annotation_index'], 'control IDs')
        offsets = p.int_axis(arrays['sample_offset'], 'control offsets')
        assert set(ids) == set(ref['trial_ids']) and set(offsets) == set(ref['offsets'])
        rows, cols = {int(k): i for i, k in enumerate(ids)}, {int(k): i for i, k in enumerate(offsets)}
        x = arrays['fcz_prebaseline_uv'][np.ix_([rows[int(k)] for k in ref['trial_ids']],
                                               [cols[int(k)] for k in ref['offsets']])].astype(float)
    v = ref['method']['verification']
    discriminating = np.any(np.abs(x - ref['epochs']) > v['source_epoch_atol_uv'] +
                            v['source_epoch_rtol'] * np.abs(ref['epochs']))
    if discriminating:
        with pytest.raises(AssertionError, match='source epoch fidelity mismatch'):
            p.epoch_arrays(output / 'response_epochs.npz', ref)
        with pytest.raises(AssertionError, match='source epoch fidelity mismatch'):
            p.validate_output_directory(output, ref)
        record_property('control_status', 'effective_negative')
    else:
        p.validate_output_directory(output, ref)
        record_property('control_status', 'control_not_discriminating')


@pytest.mark.parametrize('filename', ['annotations.csv', 'trials.csv', 'response_epochs.npz', 'fcz_waveforms.csv',
                                    'ern.json', 'run_metadata.json', 'findings.md'])
@pytest.mark.parametrize('mode', ['missing', 'empty'])
def test_missing_or_empty(output, ref, filename, mode):
    if mode == 'missing': (output / filename).unlink()
    else: (output / filename).write_bytes(b'')
    reject(output, ref)


@pytest.mark.parametrize('filename,key', [('annotations.csv', 'annotation_index'),
                                        ('trials.csv', 'stimulus_annotation_index'),
                                        ('fcz_waveforms.csv', 'sample_offset')])
@pytest.mark.parametrize('mode', ['missing_row', 'duplicate', 'wrong_id', 'fraction_id', 'bool_id', 'missing_column'])
def test_complete_unique_keyed_tables(output, ref, filename, key, mode):
    rows, fields = read_table(output / filename)
    if mode == 'missing_row': rows.pop()
    elif mode == 'duplicate': rows.append(rows[0])
    elif mode == 'wrong_id': rows[0][key] = str(p.integer(rows[0][key]) + 10**9)
    elif mode == 'fraction_id': rows[0][key] = '0.5'
    elif mode == 'bool_id': rows[0][key] = 'true'
    else:
        fields.remove(key)
        for row in rows: row.pop(key)
    write_table(output / filename, rows, fields)
    reject(output, ref)


@pytest.mark.parametrize('mode', ['drop_trial', 'duplicate_trial', 'wrong_trial', 'fraction_trial', 'bool_keys',
                                'overflow_keys', 'drop_time', 'duplicate_time', 'time_shift', 'nan', 'inf',
                                'bool_data', 'complex_data', 'object_extra', 'missing_array'])
def test_npz_support_and_type(output, ref, mode):
    def mutate(a):
        if mode == 'drop_trial':
            a['stimulus_annotation_index'] = a['stimulus_annotation_index'][:-1]
            a['fcz_prebaseline_uv'] = a['fcz_prebaseline_uv'][:-1]
        elif mode == 'duplicate_trial': a['stimulus_annotation_index'][0] = a['stimulus_annotation_index'][1]
        elif mode == 'wrong_trial': a['stimulus_annotation_index'][0] = 10**9
        elif mode == 'fraction_trial':
            a['stimulus_annotation_index'] = a['stimulus_annotation_index'].astype(float)
            a['stimulus_annotation_index'][0] += .5
        elif mode == 'bool_keys': a['stimulus_annotation_index'] = a['stimulus_annotation_index'].astype(bool)
        elif mode == 'overflow_keys':
            a['stimulus_annotation_index'] = a['stimulus_annotation_index'].astype(np.uint64)
            a['stimulus_annotation_index'][0] = 2**63
        elif mode == 'drop_time':
            a['sample_offset'] = a['sample_offset'][:-1]; a['fcz_prebaseline_uv'] = a['fcz_prebaseline_uv'][:, :-1]
        elif mode == 'duplicate_time': a['sample_offset'][0] = a['sample_offset'][1]
        elif mode == 'time_shift': a['sample_offset'] += 1
        elif mode in ('nan', 'inf'): a['fcz_prebaseline_uv'][0, 0] = np.nan if mode == 'nan' else np.inf
        elif mode == 'bool_data': a['fcz_prebaseline_uv'] = a['fcz_prebaseline_uv'].astype(bool)
        elif mode == 'complex_data': a['fcz_prebaseline_uv'] = a['fcz_prebaseline_uv'].astype(complex)
        elif mode == 'object_extra': a['extra'] = np.array([{}], dtype=object)
        else: a.pop('sample_offset')
    replace_npz(output / 'response_epochs.npz', mutate)
    reject(output, ref)


@pytest.mark.parametrize('mode', ['polarity', 'volts_as_uv', 'gain', 'constant', 'row_swap', 'time_reverse',
                                'baseline_removed', 'cancelling_trial_offsets'])
def test_coherent_source_wrong_epoch_controls(output, ref, mode, record_property):
    x = ref['epochs'].copy()
    if mode == 'polarity': x *= -1
    elif mode == 'volts_as_uv': x *= 1e-6
    elif mode == 'gain': x *= 1.1
    elif mode == 'constant': x[:] = x.mean()
    elif mode == 'row_swap': x = x[::-1]
    elif mode == 'time_reverse': x = x[:, ::-1]
    elif mode == 'baseline_removed': x -= x[:, (ref['offsets'] >= -204) & (ref['offsets'] <= 0)].mean(axis=1)[:, None]
    else: x[0] += 1; x[1] -= 1
    v = ref['method']['verification']
    discriminating = np.any(np.abs(x - ref['epochs']) > v['source_epoch_atol_uv'] + v['source_epoch_rtol'] * np.abs(ref['epochs']))
    emit(output, ref, x)
    if discriminating:
        # Deliberately check numerical evidence before any metadata comparison.
        with pytest.raises(AssertionError, match='source epoch fidelity'):
            p.epoch_arrays(output / 'response_epochs.npz', ref)
        with pytest.raises(AssertionError, match='source epoch fidelity'):
            p.validate_output_directory(output, ref)
        record_property('control_status', 'effective_negative')
    else:
        p.validate_output_directory(output, ref)
        record_property('control_status', 'control_not_discriminating')


@pytest.mark.parametrize('filename,column', [('annotations.csv', 'description'), ('annotations.csv', 'event_role'),
    ('annotations.csv', 'disposition'), ('annotations.csv', 'event_sample'), ('annotations.csv', 'onset_s'),
    ('annotations.csv', 'duration_s'), ('annotations.csv', 'paired_stimulus_annotation_index'),
    ('trials.csv', 'target_hand'), ('trials.csv', 'response_hand'), ('trials.csv', 'compatibility'),
    ('trials.csv', 'is_error'), ('trials.csv', 'response_sample'), ('trials.csv', 'response_annotation_index'),
    ('trials.csv', 'rt_s'), ('trials.csv', 'epoch_status'), ('trials.csv', 'pair_status'),
    ('trials.csv', 'baseline_mean_uv'), ('trials.csv', 'window_mean_prebaseline_uv'), ('trials.csv', 'window_mean_uv'),
    ('fcz_waveforms.csv', 'time_s'), ('fcz_waveforms.csv', 'error_uv'),
    ('fcz_waveforms.csv', 'correct_uv'), ('fcz_waveforms.csv', 'difference_uv')])
def test_source_ledger_and_own_arithmetic(output, ref, filename, column):
    rows, fields = read_table(output / filename)
    row = next(r for r in rows if r[column] != '')
    try: row[column] = str(float(row[column]) + 1)
    except ValueError: row[column] = 'wrong'
    write_table(output / filename, rows, fields)
    reject(output, ref)


@pytest.mark.parametrize('field', ['status', 'subject', 'electrode', 'units', 'contrast', 'n_annotations', 'n_stimuli',
    'n_paired_trials', 'n_error_trials', 'n_correct_trials', 'n_retained_trials', 'measurement_offsets_inclusive',
    'measurement_samples', 'error_mean_uv', 'correct_mean_uv', 'ern_amplitude_uv'])
def test_results_required_and_recomputed(output, ref, field):
    data = p.read_json(output / 'ern.json'); data.pop(field)
    write_json(output / 'ern.json', data)
    reject(output, ref)


@pytest.mark.parametrize('field', ['status', 'method_id', 'method_contract_sha256', 'source_manifest_sha256',
    'source_fif_sha256', 'sfreq_hz', 'n_samples', 'first_sample', 'eeg_channels', 'eog_channels', 'bads',
    'n_projectors', 'custom_ref_applied', 'historical_reference_known', 'n_annotations', 'n_stimuli',
    'n_paired_trials', 'n_retained_trials', 'software_versions', 'warnings'])
def test_metadata_required(output, ref, field):
    data = p.read_json(output / 'run_metadata.json'); data.pop(field)
    write_json(output / 'run_metadata.json', data)
    reject(output, ref)


@pytest.mark.parametrize('mode', ['wrong_source', 'wrong_method', 'failed', 'pilot', 'bool_count', 'string_count',
                                'json_nan', 'json_overflow', 'duplicate_json', 'undefined_result', 'headline_only',
                                'scalar_shift', 'waveform_cancellation'])
def test_coherent_or_malformed_claims(output, ref, mode):
    meta = p.read_json(output / 'run_metadata.json'); result = p.read_json(output / 'ern.json')
    if mode == 'wrong_source': meta['source_fif_sha256'] = '0' * 64
    elif mode == 'wrong_method': meta['method_contract_sha256'] = '0' * 64
    elif mode in ('failed', 'pilot'): meta['status'] = 'failed_precondition' if mode == 'failed' else 'resource_pilot'
    elif mode == 'bool_count': result['n_annotations'] = True
    elif mode == 'string_count': result['n_annotations'] = str(result['n_annotations'])
    elif mode in ('json_nan', 'json_overflow', 'duplicate_json'):
        token = '{"extra":NaN}' if mode == 'json_nan' else '{"extra":1e999}' if mode == 'json_overflow' else '{"x":1,"x":2}'
        (output / 'ern.json').write_text(json.dumps(result)[:-1] + ',' + token[1:])
        reject(output, ref); return
    elif mode == 'undefined_result': result['ern_amplitude_uv'] = None; result['status'] = 'insufficient_condition'
    elif mode == 'headline_only': result['ern_amplitude_uv'] += 1
    elif mode == 'scalar_shift':
        result['error_mean_uv'] += 1; result['correct_mean_uv'] += 1
    else:
        rows, fields = read_table(output / 'fcz_waveforms.csv')
        # Same offsetting change to both conditions preserves every difference,
        # yet disagrees with the actual submitted epochs.
        for row in rows:
            row['error_uv'] = str(float(row['error_uv']) + 1)
            row['correct_uv'] = str(float(row['correct_uv']) + 1)
        write_table(output / 'fcz_waveforms.csv', rows, fields)
    write_json(output / 'run_metadata.json', meta); write_json(output / 'ern.json', result)
    reject(output, ref)
