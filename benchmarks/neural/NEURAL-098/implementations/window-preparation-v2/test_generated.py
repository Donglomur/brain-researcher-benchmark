"""Tiny invented epoch controls; no recordings, model fitting or target reads."""
import importlib.util
from pathlib import Path
import unittest

import numpy as np


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fixed = load('n098_preparation_v2', Path(__file__).with_name('prepare.py'))
legacy = load('n098_preparation_v1', fixed.SOURCE / 'private/prepare.py')


class Epochs:
    ch_names = list(fixed.CHANNELS)

    def __init__(self, times, data=None, sf=100.):
        self.times = np.asarray(times, dtype=float)
        self.info = {'bads': [], 'sfreq': sf}
        self.data = (np.tile(self.times, (3, 6, 1)) if data is None else data)
        self.reads = []

    def get_channel_types(self):
        return ['mag'] * 6

    def __getitem__(self, ids):
        self.reads.append(list(ids))
        return Epochs(self.times, self.data[ids], self.info['sfreq'])

    def get_data(self, picks):
        assert picks == list(fixed.CHANNELS)
        return self.data


ROWS = [{'duration_ms': d} for d in (500, 1000, 1500)]


class ProjectionTests(unittest.TestCase):
    def test_regression_missing_first_baseline_sample(self):
        e = Epochs(np.arange(-49, 201) / 100)
        old = legacy.windows_from_epochs(e, [0, 1, 2], ROWS)
        # Removing t=-.5 changes the baseline mean by .005, yet legacy admits it.
        np.testing.assert_allclose(old[:, 0], .195, atol=1e-14)
        e.reads.clear()
        with self.assertRaisesRegex(ValueError, 'complete physical window'):
            fixed.windows_from_epochs(e, [0, 1, 2], ROWS)
        self.assertEqual(e.reads, [])

    def test_complete_grid_matches_predecessor(self):
        e = Epochs(np.arange(-50, 201) / 100)
        new = fixed.windows_from_epochs(e, [0, 1, 2], ROWS)
        old = legacy.windows_from_epochs(e, [0, 1, 2], ROWS)
        np.testing.assert_allclose(new, old, rtol=0, atol=1e-14)
        np.testing.assert_allclose(new[:, 0], .2, atol=1e-14)
        self.assertEqual(new.dtype, np.dtype('<f8'))

    def test_minimum_complete_extent_and_missing_final_sample(self):
        # t=1.8 is outside post; t=1.79 is required at 100 Hz.
        e = Epochs(np.arange(-50, 180) / 100)
        fixed.windows_from_epochs(e, [0, 1, 2], ROWS)
        e = Epochs(np.arange(-50, 179) / 100)
        with self.assertRaisesRegex(ValueError, 'complete physical window'):
            fixed.windows_from_epochs(e, [0, 1, 2], ROWS)
        self.assertEqual(e.reads, [])

    def test_half_open_windows_use_left_boundary_exclude_right(self):
        times = np.arange(-60, 201) / 100
        x = np.zeros((3, 6, len(times)))
        for at, value in [(-.5, 20.), (-.3, 40.), (-.1, 1000.), (.1, 60.), (.3, 2000.)]:
            x[:, :, np.flatnonzero(np.isclose(times, at, atol=1e-12, rtol=0))] = value
        out = fixed.windows_from_epochs(Epochs(times, x), [0, 1, 2], ROWS)
        np.testing.assert_allclose(out[:, 0], 1.)  # 40/20 - 20/20
        np.testing.assert_allclose(out[:, 1], 2.)  # 60/20 - 20/20

    def test_arbitrary_native_phase_and_fractional_rate(self):
        # The time grid's origin need not coincide with stimulus zero.
        for sf, origin in [(100., -.495), (100., -.503), (127.5, -.503)]:
            times = origin + np.arange(310) / sf
            e = Epochs(times, sf=sf)
            actual = fixed.windows_from_epochs(e, [0, 1, 2], ROWS)
            baseline = times[(times >= -.5) & (times < -.3)].mean()
            for j, (name, (a, b)) in enumerate(fixed.WINDOWS.items()):
                expected = times[(times >= a) & (times < b)].mean() - baseline
                for i, row in enumerate(ROWS):
                    if name in fixed.AVAILABLE[row['duration_ms']]:
                        np.testing.assert_allclose(actual[i, j], expected, atol=1e-14)
                    else:
                        self.assertTrue(np.isnan(actual[i, j]).all())

    def test_incomplete_phase_shifted_grid(self):
        e = Epochs(-.485 + np.arange(250) / 100)
        with self.assertRaisesRegex(ValueError, 'complete physical window'):
            fixed.windows_from_epochs(e, [0, 1, 2], ROWS)

    def test_clock_drift_does_not_accumulate(self):
        base = np.arange(-50, 201) / 100
        e = Epochs(base + np.arange(len(base)) * 5e-9)
        self.assertLess(np.max(np.abs(np.diff(e.times) - .01)), 1e-8)
        with self.assertRaisesRegex(ValueError, 'uniform native clock'):
            fixed.windows_from_epochs(e, [0, 1, 2], ROWS)
        self.assertEqual(e.reads, [])

    def test_invalid_frequencies(self):
        for sf in [0., -1., float('nan'), float('inf')]:
            with self.assertRaisesRegex(ValueError, 'sampling rate'):
                fixed.windows_from_epochs(Epochs(np.arange(-50, 201) / 100, sf=sf), [0, 1, 2], ROWS)

    def test_chunk_selection_and_structural_nan(self):
        times = np.arange(-50, 201) / 100
        slopes = np.arange(1, 13)[:, None, None]
        x = slopes * np.tile(times, (12, 6, 1))
        e = Epochs(times, x)
        ids = list(reversed(range(12)))
        rows = ROWS * 4
        out = fixed.windows_from_epochs(e, ids, rows)
        self.assertEqual(e.reads, [ids[:8], ids[8:]])
        np.testing.assert_allclose(out[:, 0, 0], .2 * np.arange(12, 0, -1))
        for i, row in enumerate(rows):
            for j, name in enumerate(fixed.WINDOWS):
                self.assertEqual(bool(np.isnan(out[i, j]).all()), name not in fixed.AVAILABLE[row['duration_ms']])

    def test_nonfinite_required_observation_rejected(self):
        e = Epochs(np.arange(-50, 201) / 100)
        e.data[0, 0, 0] = np.nan
        with self.assertRaisesRegex(ValueError, 'finite required observations'):
            fixed.windows_from_epochs(e, [0, 1, 2], ROWS)

    def test_sensor_quality_and_row_alignment(self):
        e = Epochs(np.arange(-50, 201) / 100)
        e.info['bads'] = [fixed.CHANNELS[0]]
        with self.assertRaisesRegex(ValueError, 'good magnetometers'):
            fixed.windows_from_epochs(e, [0, 1, 2], ROWS)
        with self.assertRaisesRegex(ValueError, 'one metadata row'):
            fixed.windows_from_epochs(e, [0, 1], ROWS)


if __name__ == '__main__':
    unittest.main()
