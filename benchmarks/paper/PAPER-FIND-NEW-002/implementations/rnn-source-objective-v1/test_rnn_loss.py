"""Generated arithmetic controls only; no native arrays, models or fitting."""
import importlib.util
from pathlib import Path
import unittest

import numpy as np

SPEC = importlib.util.spec_from_file_location('rnn_loss', Path(__file__).with_name('rnn_loss.py'))
loss = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(loss)


class LossTests(unittest.TestCase):
    def test_trial_weighting_is_not_global_mask_weighting(self):
        output = np.array([[[1., 3.], [9., 9.]], [[2., 2.], [4., 4.]]])
        target = np.zeros_like(output)
        mask = np.array([[[1.], [0.]], [[1.], [1.]]])
        result = loss.masked_trial_mse(output, target, mask)
        # Hand calculation: first trial=(1+9)/2=5; second=(4+16)/2=10.
        self.assertEqual(result['per_trial_mse'], [5., 10.])
        self.assertEqual(result['mean_trial_mse'], 7.5)
        self.assertNotEqual(result['mean_trial_mse'], 25/3)

    def test_author_squares_mask_before_reduction(self):
        result = loss.masked_trial_mse([[[2., 4.]]], [[[0., 0.]]], [[[0.5]]])
        # ((.5*2)^2+(.5*4)^2)/2/.5 = 5; weighting squared error gives 10.
        self.assertEqual(result['mean_trial_mse'], 5.)

    def test_full_channel_mask_denominator_is_first_channel(self):
        result = loss.masked_trial_mse([[[2., 4.]]], [[[0., 0.]]], [[[1., 0.]]])
        self.assertEqual(result['mean_trial_mse'], 2.)

    def test_exact_zero_and_complete_panel_keeps_all_32_rows(self):
        shape = loss.SOURCE_SHAPE
        output = np.broadcast_to(np.arange(32, dtype=float)[:, None, None], shape)
        zeros = np.broadcast_to(np.array(0.), shape)
        ones = np.broadcast_to(np.array(1.), shape)
        result = loss.score_source_panel(output, zeros, ones)
        expected = sum(i*i for i in range(32))/32
        self.assertEqual(result['mean_trial_mse'], expected)
        self.assertEqual(result['diagnostics']['natural_rows_0_to_13_mean'], sum(i*i for i in range(14))/14)
        self.assertEqual(result['diagnostics']['zero_input_control_rows_14_to_31_mean'], sum(i*i for i in range(14, 32))/18)
        self.assertFalse(result['paper_improvement_established'])
        self.assertEqual(loss.masked_trial_mse([[[2.]]], [[[2.]]], [[[1.]]])['mean_trial_mse'], 0.)

    def test_wrong_support_and_broadcasts_rejected(self):
        for target, mask in [([[[0.]]], [[[1.]]]), ([[[0., 0.]]], [[[1.], [1.]]])]:
            with self.assertRaises(ValueError):
                loss.masked_trial_mse([[[1., 2.]]], target, mask)
        with self.assertRaises(ValueError):
            loss.score_source_panel(np.broadcast_to(0., (14, 1000, 500)), np.broadcast_to(0., (14, 1000, 500)), np.broadcast_to(1., (14, 1000, 500)))
        shape = loss.SOURCE_SHAPE
        with self.assertRaises(ValueError):
            loss.score_source_panel(np.broadcast_to(0., shape), np.broadcast_to(0., shape), np.broadcast_to(0.5, shape))

        with self.assertRaises(ValueError):
            loss.score_source_panel(np.broadcast_to(0., shape), np.broadcast_to(1., shape), np.broadcast_to(1., shape))

    def test_undefined_and_nonfinite_arithmetic_rejected(self):
        for value in (float('nan'), float('inf'), float('-inf')):
            with self.assertRaises(ValueError):
                loss.masked_trial_mse([[[value]]], [[[0.]]], [[[0.]]])
        for mask in ([[[0.]]], [[[-1.]]], [[[float('nan')]]]):
            with self.assertRaises(ValueError):
                loss.masked_trial_mse([[[1.]]], [[[0.]]], mask)
        for output in ([[[True]]], [[['1']]], np.empty((0, 1, 1)), [[[1e308]]]):
            with self.assertRaises(ValueError):
                loss.masked_trial_mse(output, [[[0.]]], [[[1.]]])


if __name__ == '__main__':
    unittest.main()
