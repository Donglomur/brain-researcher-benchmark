"""Source-free mechanics: manufactured annotations/voltages, no original EEG."""
import copy
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import types
import warnings

import mne
import numpy as np
import pytest
from scipy.signal import fftconvolve

TASK = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('errmon_compute', TASK / 'solution' / 'compute.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
METHOD = json.loads((TASK / 'environment' / 'method_contract.json').read_text())


def fake_raw(events, n=4000):
    annotation = types.SimpleNamespace(onset=np.array([e[0] / 1024 for e in events]),
        duration=np.array([e[2] if len(e) > 2 else 0. for e in events]),
        description=np.array([e[1] for e in events]), orig_time=None)
    return types.SimpleNamespace(annotations=annotation, n_times=n, first_samp=0, info={'sfreq': 1024.},
        time_as_index=lambda onset, use_rounding, origin: np.round(onset * 1024).astype(int))


def paired(events, n=4000):
    ledger = c.annotation_ledger(fake_raw(events, n), METHOD)
    return ledger, c.pair_trials(ledger, n, 1024.)


SL = 'stimulus/compatible/target_left'
SR = 'stimulus/incompatible/target_right'
RL, RR = 'response/left', 'response/right'


def test_frozen_method_pin():
    raw = (TASK / 'environment' / 'method_contract.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == c.METHOD_SHA256
    assert METHOD['source_manifest_sha256'] == c.SOURCE_SHA256


def test_pairing_ledger_full_original_ids_and_extra_orphan():
    ledger, trials = paired([(1, RL), (20, 'note'), (100, SL), (110, RR), (115, RL),
                             (200, SR), (300, SL), (310, RL)])
    assert [r['disposition'] for r in ledger] == [
        'orphan_response', 'unmapped', 'paired_stimulus', 'paired_response', 'extra_response',
        'unanswered_stimulus', 'paired_stimulus', 'paired_response']
    assert [t['stimulus_annotation_index'] for t in trials] == [2, 5, 6]
    assert [t['response_annotation_index'] for t in trials] == [3, None, 7]
    assert [t['is_error'] for t in trials] == [1, None, 0]
    assert trials[0]['rt_s'] == 10 / 1024
    assert ledger[2]['paired_stimulus_annotation_index'] == ledger[3]['paired_stimulus_annotation_index'] == 2
    assert ledger[4]['paired_stimulus_annotation_index'] is None


def test_unknown_tie_allowed_but_mapped_tie_fails():
    ledger, _ = paired([(100, SL), (100, 'note'), (120, RL)])
    assert ledger[1]['disposition'] == 'unmapped'
    with pytest.raises(ValueError, match='sample tie'):
        paired([(100, SL), (100, RL)])


def test_samples_use_ties_to_even_and_original_row_keys():
    raw = fake_raw([(100.5, SL), (101.5, RL)])
    ledger = c.annotation_ledger(raw, METHOD)
    assert [r['event_sample'] for r in ledger] == [100, 102]
    assert [r['annotation_index'] for r in ledger] == [0, 1]


@pytest.mark.parametrize('event', [(-1, SL), (4000, RL), (100, 'BAD blink'),
                                   (100, 'edge'), (100, 'bad_acq_skip'), (100, SL, .01),
                                   (float('nan'), RL), (100, SL, float('inf'))])
def test_bad_annotation_preconditions(event):
    with pytest.raises(ValueError):
        c.annotation_ledger(fake_raw([event]), METHOD)


def test_pairing_is_hand_not_compatibility():
    _, trials = paired([(500, SR), (600, RR), (1000, SL), (1100, RR)])
    assert trials[0]['compatibility'] == 'incompatible' and trials[0]['is_error'] == 0
    assert trials[1]['compatibility'] == 'compatible' and trials[1]['is_error'] == 1


def test_last_response_interval_and_no_cross_trial_reuse():
    ledger, trials = paired([(100, SL), (200, SR), (3999, RL)])
    assert trials[0]['pair_status'] == 'unanswered'
    assert trials[1]['response_sample'] == 3999 and trials[1]['is_error'] == 1
    assert ledger[-1]['paired_stimulus_annotation_index'] == 1


def test_complete_common_epoch_boundary_and_null_unanswered():
    _, trials = paired([(1, SL), (255, RL), (256, SR), (300, RR),
                        (3100, SL), (3436, RR), (3440, SR), (3437 + 100, RL), (3900, SL)])
    measured = c.epoch_measurements(np.arange(4000, dtype=float), trials, METHOD)
    assert [t['epoch_status'] for t in trials] == ['outside_record', 'retained', 'retained', 'outside_record', 'unpaired']
    assert measured['fcz_prebaseline_uv'].shape == (2, 820)
    assert np.array_equal(measured['sample_offset'], np.arange(-256, 564))
    assert measured['fcz_prebaseline_uv'][1, -1] == 3999
    assert trials[0]['baseline_mean_uv'] is None and trials[-1]['window_mean_uv'] is None


def test_exact_window_inclusivity_and_signed_result():
    ledger, trials = paired([(500, SL), (800, RR), (2000, SR), (2300, RR)])
    signal = np.zeros(4000)
    offsets = np.arange(-256, 564)
    error_epoch = np.full(820, 7.)
    error_epoch[offsets == -205] = 1000000.  # Explicitly outside baseline.
    error_epoch[(offsets >= 0) & (offsets <= 102)] += 2
    signal[800 + offsets] = error_epoch
    signal[2300 + offsets] = 3
    measured = c.epoch_measurements(signal, trials, METHOD)
    assert trials[0]['baseline_mean_uv'] == pytest.approx(7 + 2 / 205)
    assert trials[0]['window_mean_prebaseline_uv'] == 9
    assert trials[0]['window_mean_uv'] == pytest.approx(2 - 2 / 205)
    result = c.summarize(METHOD, ledger, trials, measured)
    assert result['ern_amplitude_uv'] > 0  # No mandatory negative sign.
    assert result['n_error_trials'] == result['n_correct_trials'] == 1
    assert result['ern_amplitude_uv'] == pytest.approx(np.mean(measured['curves']['difference'][256:359]))


@pytest.mark.parametrize('events', [[], [(500, SL)], [(500, SL), (800, RL)], [(500, SL), (800, RR)]])
def test_empty_conditions_preserve_available_information(events):
    ledger, trials = paired(events)
    measured = c.epoch_measurements(np.zeros(4000), trials, METHOD)
    result = c.summarize(METHOD, ledger, trials, measured)
    assert result['status'] == 'insufficient_condition' and result['ern_amplitude_uv'] is None
    assert measured['curves']['difference'] is None
    assert measured['fcz_prebaseline_uv'].shape == (int(len(events) == 2), 820)


def analytic_kernel():
    def lowpass(n, cutoff):
        x = np.arange(n) - (n - 1) / 2
        h = (2 * cutoff / 1024) * np.sinc(2 * cutoff / 1024 * x)
        h *= .54 - .46 * np.cos(2 * np.pi * np.arange(n) / (n - 1))
        return h / np.sum(h)
    h = -lowpass(33793, .05)
    h[(33793 - 451) // 2:(33793 + 451) // 2] += lowpass(451, 33.75)
    return h


def test_exact_mne_fir_kernel_against_public_formula():
    actual = mne.filter.create_filter(None, 1024., .1, 30., filter_length=33793,
        l_trans_bandwidth=.1, h_trans_bandwidth=7.5, fir_window='hamming', fir_design='firwin',
        phase='zero', verbose=False)
    assert actual.shape == (33793,)
    np.testing.assert_allclose(actual, analytic_kernel(), atol=2e-17, rtol=2e-13)


def test_native_filter_reference_matches_direct_convolution_excludes_eog():
    n = 1200
    rng = np.random.default_rng(17)
    data = rng.standard_normal((33, n)) * 1e-6
    data[30:] += 1e3  # Must never enter the 30-channel average.
    names = METHOD['input']['eeg_channels'] + METHOD['input']['eog_channels']
    raw = mne.io.RawArray(data, mne.create_info(names, 1024., ['eeg'] * 30 + ['eog'] * 3), verbose=False)
    messages = []
    with c.recorded_warnings(messages):
        actual = c.filter_fcz(raw, METHOD)
    x = (data[20] - data[:30].mean(axis=0)) * 1e6
    e = n - 1
    padded = np.r_[2 * x[0] - x[e:0:-1], x, 2 * x[-1] - x[-2:-e-2:-1]]
    expected = fftconvolve(padded, analytic_kernel())[e + 16896:e + 16896 + n]
    np.testing.assert_allclose(actual, expected, atol=1e-10, rtol=1e-9)
    assert any('filter_length' in text for text in messages)
    np.testing.assert_array_equal(raw.get_data(), data)


def test_warning_capture_retains_and_prints(capsys):
    messages = []
    with c.recorded_warnings(messages):
        warnings.warn('manufactured diagnostic', RuntimeWarning)
    assert messages == ['RuntimeWarning: manufactured diagnostic']
    assert 'manufactured diagnostic' in capsys.readouterr().err


def header_fixture():
    info = dict(sfreq=1024., bads=[], projs=[], custom_ref_applied=1, meas_date=None,
        chs=[dict(unit=107, unit_mul=0, range=1., cal=9.999999974752427e-7) for _ in range(33)])
    return types.SimpleNamespace(info=info, n_times=935936, first_samp=0,
        ch_names=METHOD['input']['eeg_channels'] + METHOD['input']['eog_channels'],
        annotations=types.SimpleNamespace(orig_time=None), get_channel_types=lambda: ['eeg'] * 30 + ['eog'] * 3)


def test_exact_header_passes_without_signal_access():
    c.validate_header(header_fixture(), METHOD)


@pytest.mark.parametrize('field', ['rate', 'samples', 'first', 'channels', 'types', 'bads', 'projector',
                                  'reference', 'date', 'origin', 'unit', 'unit_mul', 'range', 'cal'])
def test_header_preconditions(field):
    raw = header_fixture()
    if field == 'rate': raw.info['sfreq'] = 1000
    elif field == 'samples': raw.n_times -= 1
    elif field == 'first': raw.first_samp = 1
    elif field == 'channels': raw.ch_names = raw.ch_names[::-1]
    elif field == 'types': raw.get_channel_types = lambda: ['eeg'] * 33
    elif field == 'bads': raw.info['bads'] = ['FCz']
    elif field == 'projector': raw.info['projs'] = [object()]
    elif field == 'reference': raw.info['custom_ref_applied'] = 0
    elif field == 'date': raw.info['meas_date'] = 'unexpected'
    elif field == 'origin': raw.annotations.orig_time = 'unexpected'
    else: raw.info['chs'][0][field] = 1e-6 if field == 'cal' else 100
    with pytest.raises(ValueError): c.validate_header(raw, METHOD)


@pytest.mark.parametrize('relation', ['same', 'inside', 'contains', 'traversal'])
def test_source_output_overlap_rejected_without_writes(tmp_path, relation):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'original').write_text('preserve')
    output = {'same': source, 'inside': source / 'output', 'contains': tmp_path,
              'traversal': tmp_path / 'elsewhere' / '..' / 'source' / 'output'}[relation]
    with pytest.raises(ValueError, match='disjoint'):
        c.prepare_output(source, output, tmp_path / 'method.json')
    assert list(source.iterdir()) == [source / 'original']


@pytest.mark.parametrize('which', ['source', 'output', 'method', 'ancestor'])
def test_symlink_guards(tmp_path, which):
    source, output, method = tmp_path / 'source', tmp_path / 'out', tmp_path / 'method'
    source.mkdir()
    method.write_text('method')
    link = tmp_path / 'link'
    target = {'source': source, 'output': output, 'method': method, 'ancestor': tmp_path}[which]
    link.symlink_to(target, target_is_directory=which != 'method')
    if which == 'source': source = link
    elif which == 'output': output = link
    elif which == 'method': method = link
    else: output = link / 'out'
    with pytest.raises(ValueError, match='Symlink'):
        c.prepare_output(source, output, method)


def test_existing_output_preserved_and_empty_allowed(tmp_path):
    output = tmp_path / 'out'
    output.mkdir()
    assert c.prepare_output(tmp_path / 'source', output, tmp_path / 'method') == output
    (output / 'keep').write_text('old result')
    assert c.main(['--data-dir', str(tmp_path / 'source'), '--output-dir', str(output)]) == 1
    assert {p.name for p in output.iterdir()} == {'keep'}


def test_method_input_not_overwritten(tmp_path):
    output = tmp_path / 'out'
    with pytest.raises(ValueError, match='method'):
        c.prepare_output(tmp_path / 'source', output, output / 'method.json')
    assert not output.exists()


def test_helper_fallback_local_and_harbor_layout(tmp_path):
    local, runtime = tmp_path / 'local.py', tmp_path / 'runtime.py'
    runtime.write_text('# helper')
    assert c.source_helper_path(local, runtime) == runtime
    local.write_text('# local helper')
    assert c.source_helper_path(local, runtime) == local
    with pytest.raises(ValueError): c.source_helper_path(tmp_path / 'missing', tmp_path / 'also-missing')


def test_wrong_method_digest_fails_before_source_helper(tmp_path, monkeypatch):
    method = tmp_path / 'method.json'
    method.write_text('{}')
    monkeypatch.setattr(c, 'source_helper_path', lambda: pytest.fail('source helper should not be imported'))
    with pytest.raises(ValueError, match='method SHA256'):
        c.load_inputs(tmp_path / 'source', method)


def test_manufactured_seven_outputs_and_primitive_axes(tmp_path):
    ledger, trials = paired([(500, SL), (800, RR), (2000, SR), (2300, RR)])
    measured = c.epoch_measurements(np.sin(np.arange(4000) / 17), trials, METHOD)
    result = c.summarize(METHOD, ledger, trials, measured)
    c.emit(tmp_path, METHOD, ledger, trials, measured, result, {'status': result['status']})
    assert {p.name for p in tmp_path.iterdir()} == set(METHOD['outputs'])
    with np.load(tmp_path / 'response_epochs.npz', allow_pickle=False) as data:
        assert set(data.files) == set(METHOD['outputs']['response_epochs.npz'])
        assert data['fcz_prebaseline_uv'].shape == (2, 820)
    rows = list(csv.DictReader((tmp_path / 'trials.csv').open()))
    assert rows[0]['stimulus_annotation_index'] == '0' and rows[1]['is_error'] == '0'
    assert json.loads((tmp_path / 'ern.json').read_text()) == result


def test_empty_condition_csv_fields_and_json_null(tmp_path):
    ledger, trials = paired([(500, SL), (800, RL)])
    measured = c.epoch_measurements(np.zeros(4000), trials, METHOD)
    result = c.summarize(METHOD, ledger, trials, measured)
    c.emit(tmp_path, METHOD, ledger, trials, measured, result, {'status': result['status']})
    rows = list(csv.DictReader((tmp_path / 'fcz_waveforms.csv').open()))
    assert all(r['error_uv'] == r['difference_uv'] == '' for r in rows)
    assert json.loads((tmp_path / 'ern.json').read_text())['error_mean_uv'] is None


def test_primitive_write_failure_does_not_publish_complete_markers(tmp_path, monkeypatch):
    ledger, trials = paired([(500, SL), (800, RL)])
    measured = c.epoch_measurements(np.zeros(4000), trials, METHOD)
    result = c.summarize(METHOD, ledger, trials, measured)
    def fail(*args, **kwargs): raise OSError('manufactured disk failure')
    monkeypatch.setattr(np, 'savez_compressed', fail)
    with pytest.raises(OSError) as error:
        c.emit(tmp_path, METHOD, ledger, trials, measured, result, {'status': 'ok'})
    c.failure_output(tmp_path, error.value, [])
    assert json.loads((tmp_path / 'ern.json').read_text())['status'] == 'failed_precondition'
    assert json.loads((tmp_path / 'run_metadata.json').read_text())['reason'] == 'manufactured disk failure'
    assert (tmp_path / 'findings.md').read_text().strip()


def test_actual_solve_entrypoint_missing_inputs_reports_failure(tmp_path):
    output = tmp_path / 'output'
    completed = subprocess.run([str(TASK / 'solution' / 'solve.sh'), '--data-dir', str(tmp_path / 'missing'),
        '--method-contract', str(tmp_path / 'missing_method'), '--output-dir', str(output)],
        capture_output=True, text=True, timeout=30)
    assert completed.returncode != 0
    assert {p.name for p in output.iterdir()} == {'ern.json', 'run_metadata.json', 'findings.md'}
    for name in ('ern.json', 'run_metadata.json'):
        receipt = json.loads((output / name).read_text())
        assert receipt['status'] == 'failed_precondition' and receipt['reason']


def test_import_has_no_execution_or_outputs(tmp_path):
    env = dict(os.environ, OUTPUT_DIR=str(tmp_path / 'never-created'), PYTHONDONTWRITEBYTECODE='1')
    code = 'import runpy; runpy.run_path(' + repr(str(TASK / 'solution' / 'compute.py')) + ', run_name="import_only")'
    result = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0 and not (tmp_path / 'never-created').exists()


@pytest.mark.parametrize('filenames', ['single', 'split', 'other', 'empty'])
def test_explicit_native_loader_options_and_single_source(tmp_path, monkeypatch, filenames):
    source = tmp_path / 'pinned.fif'
    raw = header_fixture()
    raw.annotations = fake_raw([]).annotations
    raw.time_as_index = lambda *args, **kwargs: np.array([], dtype=np.int64)
    raw.filenames = {'single': [source], 'split': [source, tmp_path / 'split.fif'],
                     'other': [tmp_path / 'other.fif'], 'empty': []}[filenames]
    closed, calls = [], []
    raw.close = lambda: closed.append(True)
    inputs = dict(method=METHOD, source_fif_sha256='0' * 64, fif_path=source)
    monkeypatch.setattr(c, 'load_inputs', lambda *args: inputs)
    monkeypatch.setattr(mne.io, 'read_raw_fif', lambda *args, **kwargs: calls.append((args, kwargs)) or raw)
    monkeypatch.setattr(c, 'filter_fcz', lambda *args: np.zeros(1000))
    if filenames == 'single':
        assert c.run(tmp_path / 'source', tmp_path / 'method', tmp_path)['status'] == 'insufficient_condition'
        assert set(p.name for p in tmp_path.iterdir()) == set(METHOD['outputs'])
    else:
        with pytest.raises(ValueError, match='single FIF'):
            c.run(tmp_path / 'source', tmp_path / 'method', tmp_path)
    assert closed == [True]
    assert calls[0][1] == dict(preload=False, allow_maxshield=False, on_split_missing='raise', verbose=False)
