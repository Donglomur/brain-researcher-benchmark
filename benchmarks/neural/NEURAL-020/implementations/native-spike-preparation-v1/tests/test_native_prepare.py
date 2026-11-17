"""Generated-only controls: no native source file, target or model is read."""
import ast
import copy
import hashlib
import logging
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import native_prepare as n


def small_snapshot():
    intervals = np.array([[0., 1.413], [1.601, 3.]] )
    return {'unit_ids': ['5', '2', '7', '3'],
            'heldout_mask': np.array([False, True, False, True]),
            'spike_times': [np.array([.001, .001, .005, .1051, .2999, .4, 1.4129, 1.413, 1.61, 2.1]) + i * .00001
                            for i in range(4)],
            'obs_intervals': [intervals.copy() for _ in range(4)],
            'trial_ids': ['a', 'b', 'c'], 'move_onset_time': np.array([.2, 1.2, 2.1]),
            'native_split': ['train', 'val', 'val'], 'ctr_hold_bump': np.array([0, 0, 1])}


def source_class():
    path = Path(__file__).resolve().parents[1] / 'vendor/nlb_nwb_interface.py'
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != '5f77fe3d25d120934c44c8ac1c26f07303eeec9db4821c69406726b141f66121':
        raise AssertionError('source fixture identity changed')
    tree = ast.parse(raw)
    cls = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == 'NWBDataset')
    names = {'load', 'resample', 'make_trial_data', '_make_midx'}
    cls.body = [x for x in cls.body if isinstance(x, ast.FunctionDef) and x.name in names]
    if len(cls.body) != len(names):
        raise AssertionError('source method inventory differs')
    scope = {'np': np, 'pd': pd, 'Path': Path, 'logger': logging.getLogger('source-parity'),
             'TimeSeries': type('TimeSeries', (), {}), 'ProcessingModule': type('ProcessingModule', (), {}),
             'MultiContainerInterface': type('MultiContainerInterface', (), {})}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])), str(path), 'exec'), scope)
    return scope['NWBDataset']


def official(snapshot, width):
    trials = pd.DataFrame({'start_time': snapshot['move_onset_time'] - .1,
                           'stop_time': snapshot['move_onset_time'] + .5,
                           'move_onset_time': snapshot['move_onset_time']}, index=snapshot['trial_ids'])
    trials.index.name = 'id'
    table = SimpleNamespace(to_dataframe=lambda: trials.copy(), colnames=list(trials.columns))
    for name in trials.columns:
        setattr(table, name, SimpleNamespace(description='generated'))
    units = pd.DataFrame({'heldout': snapshot['heldout_mask'], 'spike_times': snapshot['spike_times'],
                          'obs_intervals': snapshot['obs_intervals']}, index=snapshot['unit_ids'])
    fake = SimpleNamespace(trials=table, units=SimpleNamespace(to_dataframe=lambda: units.copy()), children=[])
    dataset = source_class()()
    dataset.data, dataset.trial_info, dataset.descriptions, dataset.bin_width = dataset.load(fake)
    dataset.resample(width)
    trial_data = dataset.make_trial_data(align_field='move_onset_time', align_range=(-100, 500),
                                         allow_overlap=True, allow_nans=True)
    arrays, clocks = [], []
    for trial_id in snapshot['trial_ids']:
        row = trial_data[trial_data['trial_id'] == trial_id]
        clocks.append(row.clock_time.dt.total_seconds().to_numpy() * 1000)
        arrays.append(np.column_stack([row['heldout_spikes' if heldout else 'spikes'][unit_id]
                                       for heldout, unit_id in zip(snapshot['heldout_mask'], snapshot['unit_ids'])]))
    return np.stack(arrays), np.stack(clocks)


def full_snapshot():
    rows = 826
    intervals = np.array([[float(i), i + .8] for i in range(rows)])
    source = {'unit_ids': ['unit-%02d' % i for i in range(65)],
              'heldout_mask': np.array([False] * 63 + [True] * 2),
              'spike_times': [np.arange(rows, dtype=float) + .2 for _ in range(65)],
              'obs_intervals': [intervals.copy() for _ in range(65)],
              'trial_ids': ['trial-%03d' % i for i in range(rows)],
              'move_onset_time': np.arange(rows, dtype=float) + .2,
              'native_split': ['train', 'train', 'val', 'val'] + ['test'] * (rows - 4),
              'ctr_hold_bump': np.arange(rows) % 2}
    protocol = {'protocol_id': 'generated-fixture-only',
                'native_split_roles': {'train': 'train', 'val': 'eval', 'test': 'excluded'},
                'selection_rationale': 'Generated native-conversion control; no authentic split chosen.',
                'condition_policy': 'report_active_and_perturbed_within_condition_null',
                'access_policy': 'Generated software controls only', 'resource_budget': 'one thread / at most 1 GiB'}
    return source, protocol, {'test': 'Generated fixture exclusion'}


class NativeConversionControls(unittest.TestCase):
    def test_generated_hdf5_reader_authentication_and_ragged_axes(self):
        import h5py
        source, _, _ = full_snapshot()
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'generated-only.nwb'
            with h5py.File(path, 'w') as fixture:
                fixture['session_start_time'] = '2017-12-07T17:06:09.727000-05:00'
                fixture['general/subject/subject_id'] = 'Han'
                fixture['units/id'] = np.arange(65)
                fixture['units/heldout'] = source['heldout_mask']
                fixture['units/spike_times'] = np.concatenate(source['spike_times'])
                fixture['units/spike_times_index'] = np.arange(1, 66) * 826
                fixture['units/obs_intervals'] = np.concatenate(source['obs_intervals'])
                fixture['units/obs_intervals_index'] = np.arange(1, 66) * 826
                fixture['intervals/trials/id'] = np.arange(826)
                fixture['intervals/trials/move_onset_time'] = source['move_onset_time']
                fixture['intervals/trials/ctr_hold_bump'] = source['ctr_hold_bump']
                fixture['intervals/trials/split'] = np.asarray(source['native_split'], dtype='S5')
            with self.assertRaisesRegex(ValueError, 'size'):
                n.read_nwb(path)
            with mock.patch.object(n, 'SOURCE_BYTES', path.stat().st_size):
                with self.assertRaisesRegex(ValueError, 'SHA256'):
                    n.read_nwb(path)
                # Only the GENERATED fixture's hash is admitted in this control.
                with mock.patch.object(n, 'SOURCE_SHA256', n.sha256_file(path)):
                    actual = n.read_nwb(path)
            self.assertEqual(actual['unit_ids'], list(map(str, range(65))))
            self.assertEqual(actual['trial_ids'], list(map(str, range(826))))
            self.assertEqual(actual['native_split'], source['native_split'])
            for unit in range(65):
                np.testing.assert_array_equal(actual['spike_times'][unit], source['spike_times'][unit])
                np.testing.assert_array_equal(actual['obs_intervals'][unit], source['obs_intervals'][unit])
            np.testing.assert_array_equal(actual['heldout_mask'], source['heldout_mask'])

    def test_full_source_method_parity_at_both_bin_widths(self):
        for width in (5, 20):
            for offset in (0., .0004):
                with self.subTest(width=width, offset=offset):
                    source = small_snapshot()
                    source['move_onset_time'] += offset
                    expected, expected_clock = official(source, width)
                    actual, clock = n.bin_spikes(source, width)
                    np.testing.assert_array_equal(actual, expected)
                    np.testing.assert_allclose(clock, expected_clock, rtol=0, atol=1e-9)

    def test_hand_derived_partial_observation_and_spike_boundaries(self):
        source = small_snapshot()
        source['move_onset_time'] = np.array([.1])
        source['trial_ids'], source['native_split'], source['ctr_hold_bump'] = ['a'], ['train'], np.array([0])
        source['obs_intervals'] = [np.array([[.0002, .0122], [.02, .8]]) for _ in range(4)]
        source['spike_times'] = [np.array([.0009, .001, .005, .0119, .012, .02]) for _ in range(4)]
        actual, clock = n.bin_spikes(source, 5)
        np.testing.assert_array_equal(clock[0, :5], [0, 5, 10, 15, 20])
        np.testing.assert_array_equal(actual[0, :5, 0], [np.nan, 1, 1, np.nan, 1])
        expected, _ = official(source, 5)
        np.testing.assert_array_equal(actual, expected)

    def test_native_microsecond_slice_failure_does_not_pad_or_drop(self):
        source = small_snapshot()
        source['move_onset_time'][0] = .2000005
        with self.assertRaisesRegex(ValueError, 'microsecond'):
            n.bin_spikes(source, 20)

    def test_first_unit_mask_assumption_requires_source_equality(self):
        source = small_snapshot()
        source['obs_intervals'][2][0, 0] = .01
        with self.assertRaisesRegex(ValueError, 'within-group'):
            n.bin_spikes(source, 20)

    def test_different_heldin_and_heldout_masks_preserved(self):
        source = small_snapshot()
        for unit in (1, 3):
            source['obs_intervals'][unit] = np.array([[0., .3], [.4, 3.]])
        actual, _ = n.bin_spikes(source, 20)
        expected, _ = official(source, 20)
        np.testing.assert_array_equal(actual, expected)
        self.assertTrue(np.isnan(actual[0, 10, 1]))
        self.assertFalse(np.isnan(actual[0, 10, 0]))

    def test_malformed_source_times_and_ragged_indices_rejected(self):
        for times in (np.array([-.1]), np.array([.2, .1]), np.array([np.inf]), np.array([3.])):
            source = small_snapshot()
            source['spike_times'][0] = times
            with self.subTest(times=times), self.assertRaises(ValueError):
                n.bin_spikes(source, 20)
        for ends in ([-1, 2], [2, 1], [1, 3]):
            with self.subTest(ends=ends), self.assertRaises(ValueError):
                n.ragged(np.array([1., 2.]), np.array(ends), 2, 'spikes')

    def test_float16_integer_loss_rejected(self):
        source = small_snapshot()
        source['spike_times'][0] = np.full(2049, .2)
        with self.assertRaisesRegex(ValueError, 'float16'):
            n.bin_spikes(source, 20)

    def test_full_826_by_65_packet_and_both_condition_scoring(self):
        source, protocol, exclusions = full_snapshot()
        metadata, (query, training, gold), audit = n.prepare_snapshot(source, protocol, 20, exclusions)
        self.assertEqual(len(metadata['trial_roster']), 826)
        self.assertEqual(query['visible_counts'].shape, (2, 30, 63))
        self.assertEqual(gold['target_counts'].shape, (2, 30, 2))
        self.assertEqual(audit['block_count'], 826)
        self.assertFalse(audit['source_file_authenticated'])
        self.assertFalse({'ctr_hold_bump', 'source_move_onset_seconds', 'target_counts'} & query.keys())
        e = n.evaluator()
        report = e.score_submission(gold, e.mean_rate_reference(training, query))
        self.assertEqual(set(report['primary_endpoints']), {'active', 'perturbed'})
        self.assertFalse(report['research_qualified'])

    def test_true_block_identity_rejects_interleaved_native_splits(self):
        source, protocol, exclusions = full_snapshot()
        source['obs_intervals'] = [np.array([[0., 826.]]) for _ in range(65)]
        with self.assertRaisesRegex(ValueError, 'whole continuous block'):
            n.prepare_snapshot(source, protocol, 20, exclusions)

    def test_recording_gap_cannot_be_hidden_by_arbitrary_trial_blocks(self):
        source = small_snapshot()
        counts, left = n.bin_spikes(source, 20)
        self.assertTrue(np.isnan(counts[1]).any())
        with self.assertRaisesRegex(ValueError, 'recording gap'):
            n.continuous_blocks(source, left, 20)

    def test_actual_clock_windows_detect_cross_split_overlap(self):
        source, protocol, exclusions = full_snapshot()
        source['move_onset_time'][2] = source['move_onset_time'][0]
        with self.assertRaisesRegex(ValueError, 'whole continuous block'):
            n.prepare_snapshot(source, protocol, 20, exclusions)


if __name__ == '__main__':
    unittest.main()
