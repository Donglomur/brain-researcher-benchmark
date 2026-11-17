"""Generated numerical controls only; no authentic neuroscience claims."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import h5py
import numpy as np
import pytest
from scipy import signal

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pac_evaluator_under_test', ROOT / 'evaluator.py')
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


def phase_grid(bins=18, trials=2):
    return np.tile((np.linspace(-np.pi, np.pi, bins + 1)[:-1] + np.pi / bins)[:, None], (1, trials))


def test_tort_independent_high_precision_entropy():
    phase = phase_grid()
    amplitude = np.tile(np.arange(1, 19)[:, None], (1, 2))
    r = e.tort(phase, amplitude)
    assert r['mi'] == pytest.approx(0.0582136332947272957134, abs=1e-14)
    np.testing.assert_allclose(r['phase_probability'], np.arange(1, 19) / 171)
    # MATLAB histc's final-edge bin is ignored, even if its amplitude is huge.
    rr = e.tort(np.vstack([phase, [[np.pi, np.pi]]]), np.vstack([amplitude, [[1e12, 1e12]]]))
    assert rr['mi'] == r['mi'] and rr['excluded_upper_edge_samples'] == 2


def test_uniform_and_undefined_tort():
    phase = phase_grid()
    assert abs(e.tort(phase, np.ones_like(phase))['mi']) < 1e-14
    assert e.tort(phase[:-1], np.ones_like(phase[:-1]))['mi'] is None
    amplitude = np.ones_like(phase); amplitude[0] = 0
    assert e.tort(phase, amplitude)['mi'] is None
    with pytest.raises(ValueError):
        e.tort(phase, -np.ones_like(phase))


def test_surrogates_preserve_trial_structure_and_explicit_sample_sd():
    phase = phase_grid(); phase[:, 1] = phase[::-1, 1]
    amp = np.column_stack([np.arange(1, 19), np.arange(2, 20) ** 2])
    perms = np.array([[0, 1], [1, 0], [0, 1], [1, 0]])
    r = e.tort_with_surrogates(phase, amp, permutations=perms)
    independent = [e.tort(phase, amp[:, p])['mi'] for p in perms]
    np.testing.assert_allclose(r['surrogate_mi'], independent)
    assert r['surrogate_sd'] == pytest.approx(np.std(independent, ddof=1))
    assert r['surrogate_mi'][0] == r['mi']
    with pytest.raises(ValueError):
        e.tort_with_surrogates(phase, amp, permutations=[[0, 0], [1, 1]])


def test_epoch_clock_inclusive_and_prospective_right_edges():
    raw = np.arange(100.)
    inclusive = e.epoch_lfp(raw, 0., 4., [5., 10.], .5, 1.)
    np.testing.assert_array_equal(inclusive[:, 0], np.arange(18, 25))
    aligned = e.epoch_lfp(raw, 0., 4., [5., 10.], .5, 1., right_edge_bins=True)
    np.testing.assert_array_equal(aligned, inclusive[1:])
    np.testing.assert_array_equal(e.epoch_lfp(raw, 0., 4., [5.01], .5, 1.)[:, 0], np.arange(19, 25))
    with pytest.raises(ValueError, match='off-grid'):
        e.epoch_lfp(raw, 0., 4., [5.01], .5, 1., right_edge_bins=True)
    with pytest.raises(ValueError, match='incomplete'):
        e.epoch_lfp(raw, 0., 4., [0.], .5, 1.)


def test_spike_binary_bins_endpoint_collision_and_source_lengths():
    out = e.binary_spike_epochs([1., 1.01, 1.04, 1.25, 1.5, 2.], [1.5], 4., .5, .5)
    np.testing.assert_array_equal(out[:, 0], [1, 1, 0, 1])
    assert out.sum() == 3  # left boundary excluded and collisions collapsed
    assert e.binary_spike_epochs([], [5.], 400.).shape == (2200, 1)
    assert e.epoch_lfp(np.zeros(6000), 0., 400., [5.], 1.5, 4.).shape == (2201, 1)


def test_source_filter_independent_sinc_oracle_and_trial_isolation():
    fs, low, high = 400., 4., 6.
    transition = 2.
    order = 660
    t = np.arange(-order // 2, order // 2 + 1)
    window = 25 / 46 - (1 - 25 / 46) * np.cos(2 * np.pi * np.arange(order + 1) / order)
    kernels = []
    for cutoff in [low - transition / 2, high + transition / 2]:
        kernel = np.sinc(2 * cutoff / fs * t) * window
        kernels.append(kernel / kernel.sum())
    expected = kernels[1] - kernels[0]
    np.testing.assert_allclose(e.source_fir_coefficients(fs, low, high), expected, atol=1e-16)
    raw = np.column_stack([np.sin(np.arange(800) / 10), np.full(800, 1e6)])
    np.testing.assert_allclose(e.band_analytic(raw, fs, low, high)[:, 0], e.band_analytic(raw[:, :1], fs, low, high)[:, 0], atol=1e-12)
    with pytest.raises(ValueError):
        e.source_fir_coefficients(fs, 0., 6.)


def test_morlet_fft_matches_direct_complex_convolution():
    fs = 40.; x = np.column_stack([np.arange(25.) / 25, np.sin(np.arange(25.))])
    t = np.arange(-40, 41) / fs
    freq = 7.; width = 7 / (2 * np.pi * freq)
    wavelet = np.exp(2j * np.pi * freq * t) * np.exp(-t*t / (2*width*width))
    expected = np.column_stack([np.abs(np.convolve(x[:, k], wavelet)[40:65]) for k in range(2)])
    np.testing.assert_allclose(e.morlet_amplitude(x, fs, [freq])[:, :, 0], expected, atol=1e-13)


def test_su_table_source_zscore_median_left_edges_and_no_offset():
    phase = phase_grid(10, 2)
    amp = np.empty((10, 2, 2)); amp[:, 0, :] = [1, 2]; amp[:, 1, :] = [3, 6]
    spikes = np.ones((10, 2), bool)
    table = e.su_count_table(phase, amp, spikes)
    np.testing.assert_array_equal(table['counts'], np.ones(20))
    np.testing.assert_array_equal(table['occupancy'], np.ones(20))
    np.testing.assert_allclose(table['design_full'][0], [1, -1, 0, 0, 0, 0], atol=1e-15)
    assert table['exposure_offset'] == 'none_as_in_author_helper'
    with pytest.raises(ValueError):
        e.su_count_table(phase, np.ones_like(amp), spikes)


def test_su_nested_poisson_independent_analytic_oracle():
    theta = np.repeat(np.linspace(-np.pi, np.pi, 11)[:-1], 2)
    gamma = np.tile([0, 1], 10)
    x = np.column_stack([np.ones(20), np.cos(theta), np.sin(theta), gamma,
                         np.cos(theta) * gamma, np.sin(theta) * gamma])
    table = {'design_full': x, 'counts': np.tile([2, 4], 10)}
    r = e.su_model_comparisons(table)
    assert r['comparisons']['interaction']['likelihood_ratio'] == pytest.approx(0, abs=1e-10)
    assert r['comparisons']['gamma_main_effect']['likelihood_ratio'] == pytest.approx(6.795961471815898916, abs=1e-9)
    assert r['comparisons']['gamma_main_effect']['degrees_freedom'] == 1
    assert r['no_gamma_main']['parameters'] == 5
    assert r['full']['parameters'] == 6
    with pytest.raises(ValueError, match='MLE'):
        e.poisson_fit(x, np.zeros(20))
    with pytest.raises(ValueError, match='separation'):
        e.poisson_fit(x, np.tile([0, 4], 10))


def test_source_trial_masks_validate_original_metadata():
    masks = np.asarray(e.SOURCE['lfp']['stratified_trials_one_based']) - 1
    loads = np.ones(140); loads[masks[:, 1]] = 3
    correct = np.ones(140)
    one, three = e.validate_lfp_masks(loads, correct)
    assert len(one) == len(three) == 53
    correct[one[0]] = 0
    with pytest.raises(ValueError, match='accuracy'):
        e.validate_lfp_masks(loads, correct)


def records_fixture():
    roster = []; records = []
    # patient A: session1 channels .1/.3 => .2; session2 .6; patient mean .4.
    # patient B: single channel .0. Patient mean overall .2, not channel-weighted .25.
    for patient, session, channel, delta in [('A', '1', 'a', .1), ('A', '1', 'b', .3), ('A', '2', 'a', .6), ('B', '1', 'a', 0.)]:
        row = dict(patient=patient, session=session, channel=channel)
        roster.append({**row, 'eligible': True})
        records.append({**row, 'load1_mi': np.zeros((7, 25)), 'load3_mi': np.full((7, 25), delta)})
    roster.append(dict(patient='C', session='1', channel='a', eligible=False, reason='prospectively ineligible control'))
    return roster, records


def test_patient_hierarchy_complete_roster_and_deterministic_bootstrap():
    roster, records = records_fixture()
    r = e.patient_contrasts(roster, records, bootstrap=100, seed=7)
    assert r['patient_effects'] == pytest.approx({'A': .4, 'B': 0})
    assert r['mean_effect'] == pytest.approx(.2)
    assert r['n_patients'] == 2 and r['n_sessions'] == 3 and r['n_channels'] == 4
    assert r == e.patient_contrasts(roster, records, bootstrap=100, seed=7)
    with pytest.raises(ValueError, match='population'):
        e.patient_contrasts(roster, records[:-1])
    with pytest.raises(ValueError, match='duplicate'):
        e.patient_contrasts(roster + [roster[0]], records)
    records[0]['load3_mi'][0, 0] = np.nan
    with pytest.raises(ValueError):
        e.patient_contrasts(roster, records)


def test_generated_comodulogram_computes_raw_lfp_and_full_grid():
    fs = 400.; t = np.arange(1401) / fs
    raw = np.column_stack([(1 + .3 * np.cos(2*np.pi*5*t + phi))*np.cos(2*np.pi*100*t) + np.sin(2*np.pi*5*t + phi) + .4*np.sin(2*np.pi*2*t + phi) for phi in [0., 1.]])
    r = e.comodulogram(raw, fs)
    assert r['mi'].shape == (7, 25)
    assert r['phase_probability'].shape == (7, 25, 18)
    assert r['fig2d_curve'].shape == (18,)
    np.testing.assert_allclose(r['fig2d_curve'].sum(), 1, atol=1e-10)
    assert np.isfinite(r['mi']).all()
    assert r['n_surrogates'] == 0


def test_su_requires_explicit_correction_before_any_execution():
    with pytest.raises(ValueError, match='explicit'):
        e.su_example([], [], 0, 400, [], [], [], alignment='native')


def test_generated_nwb_bridge_ragged_indices_and_exact_pin_validation(tmp_path, monkeypatch):
    path = tmp_path / 'generated.nwb'
    with h5py.File(path, 'w') as f:
        f['general/subject/subject_id'] = '26'; f['general/session_id'] = '1'
        f['acquisition/LFPs/data'] = np.arange(100 * 33).reshape(100, 33)
        f['acquisition/LFPs/starting_time'] = 2.
        f['acquisition/LFPs/starting_time'].attrs['rate'] = 400.
        for name, values in [('timestamps_Maintenance', [4., 6.]), ('loads', [1, 3]), ('response_accuracy', [1, 1])]:
            f['intervals/trials/' + name] = values
        f['units/spike_times'] = np.arange(40.)
        f['units/spike_times_index'] = np.arange(2, 41, 2)
    receipt = dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(), bytes=path.stat().st_size,
                   path='sub-26/sub-26_ses-1_ecephys+image.nwb', asset_id='GENERATED-ENGINEERING-CONTROL',
                   version=e.SNAPSHOT, dandiset='000673')
    with pytest.raises(ValueError, match='source-reported'):
        e.load_nwb(path, receipt, example='su')
    # The fixture is explicitly injected as a test pin; it is never source evidence.
    monkeypatch.setitem(e.SOURCE, 'su', {**e.SOURCE['su'], 'asset_sha256': receipt['sha256'],
                                       'asset_bytes': receipt['bytes'], 'asset_id': receipt['asset_id']})
    out = e.load_nwb(path, receipt, example='su')
    np.testing.assert_array_equal(out['spikes'], [38, 39])
    np.testing.assert_array_equal(out['raw'], np.arange(100 * 33).reshape(100, 33)[:, 32])
    assert out['fs'] == 400 and out['start_time'] == 2
    with h5py.File(path, 'r+') as f:
        f['units/spike_times_index'][-1] = 41
    receipt['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    monkeypatch.setitem(e.SOURCE['su'], 'asset_sha256', receipt['sha256'])
    with pytest.raises(ValueError, match='ragged'):
        e.load_nwb(path, receipt, example='su')
    receipt['version'] = '2025'
    with pytest.raises(ValueError, match='2024'):
        e.load_nwb(path, receipt, example='su')


def test_cli_patient_report_is_strict_json_and_preserves_holds(tmp_path):
    roster, records = records_fixture()
    payload = tmp_path / 'input.json'; output = tmp_path / 'output.json'
    payload.write_text(json.dumps(e._jsonable(dict(roster=roster, records=records))))
    subprocess.run([sys.executable, str(ROOT / 'evaluator.py'), 'patient-contrast', str(payload), '--output', str(output)], check=True)
    report = json.loads(output.read_text())
    assert report['scientific_qualification'] == 'unknown'
    assert report['native_reference_verified'] is False
    assert report['result']['mean_effect'] == pytest.approx(.2)
    assert len(report['holds']) >= 5


def test_generated_complete_su_example_path():
    fs = 400.
    maintenance = np.arange(120.) * 6 + 2
    t = np.arange(int((maintenance[-1] + 5) * fs)) / fs
    raw = np.sin(2*np.pi*5*t) + (1 + .4*np.cos(2*np.pi*5*t))*np.cos(2*np.pi*100*t)
    loads = np.ones(120); loads[-2:] = 3
    correct = np.ones(120)
    # Deterministic generated spikes with occupancy in both gamma categories.
    spikes = np.arange(0., t[-1], .0175)
    result = e.su_example(raw, spikes, 0., fs, maintenance, loads, correct,
                          alignment='prospective_right_edge_bins_v1')
    np.testing.assert_array_equal(result['selected_trials_one_based'], [119, 120])
    assert result['table']['occupancy'].sum() == 2000
    assert result['table']['counts'].sum() > 0
    assert np.isfinite(result['models']['full']['log_likelihood'])
    assert result['models']['population_pac_neuron_selection'] == 'not_performed'
