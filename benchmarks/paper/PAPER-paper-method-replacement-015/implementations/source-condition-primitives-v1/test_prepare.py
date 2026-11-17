"""Generated-only controls. No native data, model or scientific result is used."""
import ast
from copy import deepcopy
import glob
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from scipy.interpolate import interp1d
from scipy.io import loadmat, savemat
from scipy.ndimage import gaussian_filter1d
from scipy.signal import resample

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('spinal_condition_producer_controls', HERE / 'prepare.py')
p = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = p
spec.loader.exec_module(p)


def record(*, rate=30., n=150, neuron='a', ordinal=0, recordings=1, amplitude=.03):
    times = np.arange(n) / rate
    values = amplitude * (np.sin(np.arange(n) / 20.) + .1 * np.cos(np.arange(n) / 7.))
    return p.NativeRecord(neuron, 'glutamatergic' if neuron == 'a' else 'gabaergic',
                          f'Ground_truth/{neuron}_mini.mat', '0' * 64, ordinal, recordings,
                          times, values, np.array([.2, 1., 1.01, 2., 2.3]))


def native_dict(r):
    return {'fluo_time': r.times, 'fluo_mean': r.fluorescence, 'events_AP': r.event_seconds * 10_000}


def write_mat(path, records):
    cells = np.empty((1, len(records)), dtype=object)
    for i, r in enumerate(records):
        cells[0, i] = native_dict(r)
    savemat(path, {'CAttached': cells})


def fixture_inventory(folder, cells=44, trials=3, n=100):
    entries = []
    for i in range(cells):
        path = folder / f'n{i:02d}_mini.mat'
        write_mat(path, [record(neuron=f'n{i}', ordinal=j, recordings=trials, n=n) for j in range(trials)])
        payload = path.read_bytes()
        entries.append({'path': path.name, 'bytes': len(payload), 'sha256': p.sha256(payload),
                        'git_blob_sha1': hashlib.sha1(b'blob ' + str(len(payload)).encode() + b'\0' + payload).hexdigest(),
                        'neuron_id': f'n{i}', 'cohort': 'glutamatergic' if i < 21 else 'gabaergic'})
    return {'files': entries, 'expected_neurons': cells, 'expected_recordings': cells * trials,
            'expected_native_samples': cells * trials * n, 'expected_file_bytes': sum(r['bytes'] for r in entries)}


def original_function(rng):
    source = (HERE / 'upstream' / 'utils.py').read_bytes()
    assert p.sha256(source) == '0b9c9485d610e8de19c186bc0de9575509f358fedbe43b248b222a4ed91e0f63'
    tree = ast.parse(source)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'calibrated_ground_truth_artificial_noise')
    class NumpyProxy:
        random = rng
        def __getattr__(self, name):
            return getattr(np, name)
    class SioProxy:
        loadmat = staticmethod(loadmat)
    ns = {'np': NumpyProxy(), 'glob': glob, 'os': os, 'sio': SioProxy(), 'interp1d': interp1d, 'resample': resample}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), 'pinned_upstream_utils.py', 'exec'), ns)
    return ns[fn.name]


def predictions(bank, candidate=False):
    result = {}
    for row in bank['recordings']:
        target = row['arrays']['target_hz']
        result[row['metadata']['recording_id']] = {
            'oasis': {'values': target, 'unit': 'arbitrary'},
            'default_cascade': {'values': target / bank['condition']['nominal_rate_hz'], 'unit': 'expected_spikes_per_bin'},
            'glutamatergic_cascade': {'values': target, 'unit': 'hz'},
            'gabaergic_cascade': {'values': target, 'unit': 'hz'}}
        if candidate:
            result[row['metadata']['recording_id']]['candidate'] = {'values': target, 'unit': 'hz'}
    return result


class ConditionControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = record()
        cls.condition = p.Condition()
        cls.ready = p.prepare_record(cls.r, cls.condition, 'generated-control-v1')
        cls.bank = p.build_bank([record(neuron='a', ordinal=i, recordings=2) for i in range(2)] +
                               [record(neuron='b', ordinal=i, recordings=2) for i in range(2)],
                               cls.condition, 'generated-control-v1')

    def test_pinned_inventory_complete_and_nonmini_retained(self):
        payload = (HERE / 'NATIVE_INVENTORY.json').read_bytes()
        self.assertEqual(p.sha256(payload), p.INVENTORY_SHA256)
        inv = json.loads(payload)
        self.assertEqual((len(inv['files']), inv['expected_recordings'], inv['expected_native_samples'], inv['expected_file_bytes']),
                         (44, 132, 434390, 6225113))
        self.assertEqual(sum(r['cohort'] == 'glutamatergic' for r in inv['files']), 21)
        self.assertEqual(sum(not r['later_author_mini_glob_matches'] for r in inv['files']), 4)
        self.assertEqual(sum(r['cohort'] == 'glutamatergic' and not r['later_author_mini_glob_matches'] for r in inv['files']), 1)

    def test_original_numerics_at_native_rate(self):
        self.assert_original_parity(30., 30.)

    def test_original_numerics_fourier_downsample(self):
        self.assert_original_parity(30., 10.)

    def test_original_numerics_fourier_upsample(self):
        self.assert_original_parity(10., 30.)

    def test_original_numerics_within_five_percent_no_resample(self):
        self.assert_original_parity(29., 30.)

    def assert_original_parity(self, native_rate, requested_rate):
        r = record(rate=native_rate, n=180)
        condition = p.Condition(requested_rate, 7.)
        actual = p.prepare_record(r, condition, 'parity-bank')
        with tempfile.TemporaryDirectory() as folder:
            write_mat(Path(folder) / 'fixture_mini.mat', [r])
            fn = original_function(p.keyed_rng(r, condition, 'parity-bank')[0])
            source_x, source_y, source_rate, _ = fn(folder, 7., requested_rate, False, verbose=0)
        self.assertIsNotNone(source_x[0], 'exact upstream function must produce its generated trace')
        np.testing.assert_array_equal(actual['arrays']['fluorescence'], source_x[0][:, 0])
        np.testing.assert_array_equal(actual['arrays']['counts'], source_y[0][:, 0])
        self.assertEqual(actual['metadata']['native_rate_hz'], source_rate[0])

    def test_source_sigma_schedule(self):
        self.assertEqual([p.Condition(r).sigma_seconds for r in [2.5, 5, 10, 15, 20, 25, 30]], [.4, .2, .1, .1, .1, .05, .05])
        self.assertFalse(p.Condition(10).metadata()['original_figure4_anchor_parameters'])
        self.assertFalse(p.Condition().metadata()['historical_paper_realization'])

    def test_condition_does_not_accept_unsupported_or_nonfinite_settings(self):
        for args in [(12., 7.), (30., -1), (30., float('nan')), (True, 7.), (30., True)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                p.Condition(*args)

    def test_rng_is_order_independent_and_shared_across_methods(self):
        reverse = p.build_bank(list(reversed([record(neuron='a', ordinal=i, recordings=2) for i in range(2)] +
                                           [record(neuron='b', ordinal=i, recordings=2) for i in range(2)])), self.condition, 'generated-control-v1')
        by_id = {r['metadata']['recording_id']: r for r in reverse['recordings']}
        for row in self.bank['recordings']:
            np.testing.assert_array_equal(row['arrays']['fluorescence'], by_id[row['metadata']['recording_id']]['arrays']['fluorescence'])
        self.assertNotEqual(self.bank['recordings'][0]['metadata']['rng_key_sha256'], self.bank['recordings'][1]['metadata']['rng_key_sha256'])

    def test_bank_seed_changes_noise_but_not_targets_or_support(self):
        other = p.prepare_record(self.r, self.condition, 'different-bank')
        self.assertFalse(np.array_equal(self.ready['arrays']['fluorescence'], other['arrays']['fluorescence']))
        for field in ('counts', 'target_hz', 'support'):
            np.testing.assert_array_equal(self.ready['arrays'][field], other['arrays'][field])

    def test_source_fixed_context_mask(self):
        mask = self.ready['arrays']['support']
        self.assertEqual(np.flatnonzero(mask).tolist(), list(range(32, 118)))
        low = p.prepare_record(record(n=300), p.Condition(10), 'context')
        self.assertEqual(np.flatnonzero(low['arrays']['support']).tolist(), list(range(16, 84)))

    def test_short_record_is_preserved_and_not_scored(self):
        short = p.prepare_record(record(n=40), self.condition, 'short')
        self.assertEqual(short['metadata']['status'], 'prepared')
        self.assertEqual(short['metadata']['scored_bins'], 0)
        self.assertTrue(short['metadata']['short_recording'])

    def test_target_is_one_record_gaussian_rate_not_native_400ms(self):
        arr = self.ready['arrays']
        expected = gaussian_filter1d(arr['counts'].astype(float), 1.5, mode='reflect', truncate=4.) * 30.
        np.testing.assert_array_equal(arr['target_hz'], expected)
        self.assertFalse(np.allclose(expected, gaussian_filter1d(arr['counts'].astype(float), 12.) * 30.))

    def test_outside_events_not_clipped_into_edge_bins(self):
        r = record()
        r = p.NativeRecord(**{**r.__dict__, 'event_seconds': np.r_[-10., r.event_seconds, 100.]})
        prepared = p.prepare_record(r, self.condition, 'outside')
        self.assertEqual(prepared['metadata']['events_outside_source_bins'], 2)
        self.assertEqual(prepared['arrays']['counts'].sum(), 5)

    def test_noisy_ineligible_record_retained(self):
        bank = p.build_bank([record(amplitude=100.)], self.condition, 'ineligible')
        self.assertEqual(len(bank['recordings']), 1)
        self.assertEqual(bank['recordings'][0]['metadata']['reason'], 'native_noise_exceeds_requested_noise')
        self.assertEqual(bank['unavailable_recordings'], ['a/recording-000'])
        with self.assertRaisesRegex(ValueError, 'unavailable'):
            p.metric_operands(bank, {})

    def test_complete_lono_excludes_all_held_recordings(self):
        train = p.training_records(self.bank, 'a')
        self.assertEqual([r['metadata']['recording_id'] for r in train], ['b/recording-000', 'b/recording-001'])
        self.assertEqual(len(self.bank['recordings']), 4)
        with self.assertRaises(ValueError):
            p.training_records(self.bank, 'unknown')

    def test_complete_generated_44_neuron_132_recording_native_parser(self):
        with tempfile.TemporaryDirectory() as folder:
            inv = fixture_inventory(Path(folder))
            rows = p._read_native(folder, inv)
        self.assertEqual((len(rows), len({r.neuron_id for r in rows}), sum(len(r.times) for r in rows)), (132, 44, 13200))
        self.assertTrue(all(r.recordings_in_neuron == 3 for r in rows))

    def test_native_checksum_corruption_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            inv = fixture_inventory(Path(folder), cells=1)
            path = Path(folder) / inv['files'][0]['path']
            content = bytearray(path.read_bytes()); content[-1] ^= 1; path.write_bytes(content)
            with self.assertRaisesRegex(ValueError, 'identity'):
                p._read_native(folder, inv)

    def test_missing_original_recording_census_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            inv = fixture_inventory(Path(folder), cells=1)
            inv['expected_recordings'] += 1
            with self.assertRaisesRegex(ValueError, 'census'):
                p._read_native(folder, inv)

    def test_source_symlink_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            inv = fixture_inventory(Path(folder), cells=1)
            path = Path(folder) / inv['files'][0]['path']
            other = path.with_suffix('.other'); path.rename(other); path.symlink_to(other)
            with self.assertRaisesRegex(ValueError, 'symlink'):
                p._read_native(folder, inv)

    def test_original_clock_and_nan_event_handling(self):
        trial = native_dict(self.r)
        trial['events_AP'] = np.array([10_000., np.nan, -10_000.])
        _, _, ev, dropped = p.parse_trial(trial)
        np.testing.assert_array_equal(ev, [-1., 1.])
        self.assertEqual(dropped, 1)

    def test_nonfinite_and_nonuniform_native_data_refused(self):
        for field, bad in [('fluo_time', np.nan), ('fluo_mean', np.inf), ('events_AP', np.inf)]:
            trial = deepcopy(native_dict(self.r)); trial[field][1] = bad
            with self.subTest(field=field), self.assertRaises(ValueError):
                p.parse_trial(trial)
        trial = deepcopy(native_dict(self.r)); trial['fluo_time'][10] += .001
        with self.assertRaisesRegex(ValueError, 'uniform'):
            p.parse_trial(trial)

    def test_finite_extreme_native_clock_overflow_refused(self):
        trial = {'fluo_time': np.array([-1e308, 0., 1e308]), 'fluo_mean': np.zeros(3), 'events_AP': []}
        with self.assertRaisesRegex(ValueError, 'uniform'):
            p.parse_trial(trial)

    def test_complex_boolean_and_matrix_native_fields_refused(self):
        for field in ('fluo_time', 'fluo_mean', 'events_AP'):
            for bad in (np.array([1 + 2j, 3 + 4j, 5 + 6j]), np.ones((3, 3)), np.ones(3, dtype=bool)):
                trial = deepcopy(native_dict(self.r)); trial[field] = bad
                with self.subTest(field=field, dtype=bad.dtype), self.assertRaisesRegex(ValueError, 'real numeric vectors'):
                    p.parse_trial(trial)

    def test_complete_output_allocation_is_admitted_before_noise(self):
        r = record()
        with patch.object(p, 'MAX_OUTPUT_SAMPLES', 200), patch.object(p, 'prepare_record') as prepare:
            with self.assertRaisesRegex(ValueError, 'before resampling'):
                p.build_bank([r, record(neuron='b')], self.condition, 'bounded')
            prepare.assert_not_called()

    def test_five_method_metric_bridge_and_candidate_units(self):
        result = p.score_bank(self.bank, predictions(self.bank, candidate=True))
        self.assertFalse(result['historical_paper_comparison_qualified'])
        for row in result['metrics']['per_neuron'].values():
            self.assertEqual(row['scored_bins'], 172)
            for method in p.METHODS[2:] + ('candidate',):
                self.assertAlmostEqual(row['methods'][method]['correlation']['value'], 1.)
                self.assertAlmostEqual(row['methods'][method]['rate_diagnostics']['normalized_l1'], 0.)

    def test_raw_control_cannot_be_replaced(self):
        given = predictions(self.bank)
        given['a/recording-000']['raw_fluorescence'] = {'values': [0.] * 150, 'unit': 'arbitrary'}
        with self.assertRaisesRegex(ValueError, 'raw'):
            p.metric_operands(self.bank, given)

    def test_float32_predictions_accepted_but_complex_predictions_refused(self):
        given = predictions(self.bank)
        given['a/recording-000']['oasis']['values'] = given['a/recording-000']['oasis']['values'].astype(np.float32)
        p.score_bank(self.bank, given)
        given['a/recording-000']['oasis']['values'] = given['a/recording-000']['oasis']['values'].astype(complex)
        with self.assertRaisesRegex(ValueError, 'real numeric vector'):
            p.metric_operands(self.bank, given)

    def test_missing_recording_and_partial_candidate_refused(self):
        given = predictions(self.bank); given.pop('a/recording-000')
        with self.assertRaisesRegex(ValueError, 'every original'):
            p.metric_operands(self.bank, given)
        given = predictions(self.bank, candidate=True); given['a/recording-000'].pop('candidate')
        with self.assertRaisesRegex(ValueError, 'candidate'):
            p.metric_operands(self.bank, given)

    def test_nonfinite_prediction_inside_support_refused_without_remasking(self):
        given = predictions(self.bank)
        given['a/recording-000']['oasis']['values'] = given['a/recording-000']['oasis']['values'].copy()
        given['a/recording-000']['oasis']['values'][40] = np.nan
        with self.assertRaisesRegex(ValueError, 'finite'):
            p.score_bank(self.bank, given)

    def test_all_context_only_neuron_cannot_disappear(self):
        bank = p.build_bank([record(n=40)], self.condition, 'short-metrics')
        with self.assertRaisesRegex(ValueError, 'insufficient'):
            p.metric_operands(bank, predictions(bank))

    def test_operator_only_export_pins_arrays_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'bank'
            receipt = p.write_bank(self.bank, output)
            self.assertTrue(receipt['operator_only_contains_targets'])
            self.assertEqual(output.stat().st_mode & 0o777, 0o700)
            self.assertEqual((output / 'BANK.json').stat().st_mode & 0o777, 0o600)
            self.assertEqual(len(receipt['recordings']), 4)
            for row in receipt['recordings']:
                pin = row['operator_payload']; payload = (output / pin['path']).read_bytes()
                self.assertEqual(p.sha256(payload), pin['sha256'])
                self.assertEqual((output / pin['path']).stat().st_mode & 0o777, 0o600)
                with np.load(output / pin['path'], allow_pickle=False) as data:
                    self.assertEqual(set(data.files), {'fluorescence', 'target_hz', 'counts', 'support', 'bin_centers_seconds'})
            with self.assertRaisesRegex(ValueError, 'exist'):
                p.write_bank(self.bank, output)

    def test_operator_byte_budget_refuses_before_creating_output(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'bank'
            with patch.object(p, 'MAX_OUTPUT_BYTES', 1):
                with self.assertRaisesRegex(ValueError, 'before writing'):
                    p.write_bank(self.bank, output)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
