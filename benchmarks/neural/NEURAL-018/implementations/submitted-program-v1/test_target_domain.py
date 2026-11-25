"""Generated target-domain controls; no authentic data or native execution."""
import importlib.util
import math
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common
import grade


def load_core(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


core = load_core(HERE / 'scoring_core.py', '_forecast_current_domain_core')
legacy = load_core(common.SCORER / 'scoring_core.py', '_forecast_legacy_domain_core')


class TargetDomainTests(unittest.TestCase):
    def test_uint64_and_signed_values_cannot_round_into_domain(self):
        for dtype in (np.uint64, np.int64, np.dtype('>u8'), np.dtype('>i8')):
            for value in (2**53 + 1, np.iinfo(dtype).max):
                with self.subTest(dtype=dtype, value=value):
                    target = np.array([[[value]]], dtype=dtype)
                    with self.assertRaisesRegex(ValueError, 'Observed targets'):
                        core.poisson_bits_per_spike(target, np.ones(target.shape))

    def test_valid_boundaries_keep_exact_score_parity(self):
        for dtype in (np.uint64, np.int64, np.dtype('>u8'), np.dtype('>i8')):
            for value in (1, 2**53 - 1, 2**53):
                with self.subTest(dtype=dtype, value=value):
                    target = np.array([[[value]]], dtype=dtype)
                    rates = np.array([[[float(value)]]])
                    self.assertEqual(core.poisson_bits_per_spike(target, rates),
                                     legacy.poisson_bits_per_spike(target, rates))
        for dtype in (np.uint8, np.int16, np.float16, np.float32, np.float64, np.longdouble):
            target = np.array([[[0], [1]], [[2], [3]]], dtype=dtype)
            rates = np.array([[[0.2], [0.8]], [[2.5], [3.1]]])
            with self.subTest(dtype=dtype):
                self.assertEqual(core.poisson_bits_per_spike(target, rates),
                                 legacy.poisson_bits_per_spike(target, rates))

    def test_floating_fraction_and_nonfinite_counts_are_refused(self):
        for dtype in (np.float16, np.float32, np.float64, np.longdouble):
            for value in (-1, 0.5, np.nan, np.inf):
                with self.subTest(dtype=dtype, value=value):
                    with self.assertRaisesRegex(ValueError, 'Observed targets'):
                        core.poisson_bits_per_spike(np.array([[[value]]], dtype=dtype),
                                                   np.ones((1, 1, 1)))
        # On platforms with extra precision, these values become valid-looking
        # integers if validation incorrectly occurs after float64 conversion.
        fractional = np.nextafter(np.longdouble(1), np.longdouble(2))
        with self.assertRaisesRegex(ValueError, 'Observed targets'):
            core.poisson_bits_per_spike(np.array([[[fractional]]]), np.ones((1, 1, 1)))

    def test_fixed_mask_and_zero_target_outcome_are_preserved(self):
        mask = np.array([[[True], [False]]])
        for dtype, invalid in ((np.uint64, 2**64 - 1), (np.int64, -1),
                               (np.float64, np.nan), (np.float64, 1.5)):
            target = np.array([[[1], [invalid]]], dtype=dtype)
            with self.subTest(dtype=dtype):
                result = core.poisson_bits_per_spike(target, np.ones(target.shape), mask)
                self.assertEqual(result['co_bps'], 0.0)
                self.assertEqual(result['valid_cells'], 1)
        result = core.poisson_bits_per_spike(np.zeros((1, 2, 1), dtype=np.uint64),
                                           np.ones((1, 2, 1)))
        self.assertEqual(result['status'], 'undefined_zero_target_spikes')
        self.assertIsNone(result['co_bps'])

    def test_independent_scalar_likelihood_and_input_immutability(self):
        target = np.array([[[0, 0], [1, 0]], [[2, 0], [3, 0]]], dtype=np.uint64)
        target.setflags(write=False)
        saved = target.copy()
        rates = np.array([[[0.5, 0.1], [1.0, 0.2]], [[2.5, 0.3], [4.0, 0.4]]])
        mask = np.array([[[True, True], [True, False]], [[False, True], [True, True]]])
        result = core.poisson_bits_per_spike(target, rates, mask)
        expected = core.scalar_bits_per_spike(target, rates, mask)
        self.assertAlmostEqual(result['co_bps'], expected['fp_bps'], places=13)
        np.testing.assert_array_equal(target, saved)
        for invalid in (0, -1, np.nan, np.inf):
            changed = rates.copy(); changed[0, 1, 1] = invalid
            with self.assertRaisesRegex(ValueError, 'Predictions must'):
                core.poisson_bits_per_spike(target, changed, mask)

    def test_active_grader_mount_selects_corrected_core(self):
        class MountObserved(BaseException):
            pass
        assets = {'public': {'past': {'path': 'past.npz'}, 'manifest': {'path': 'public.json'}}}
        seen = []
        def ordinary(path, *args, **kwargs):
            path = Path(path); seen.append(path)
            if path == HERE / 'scoring_core.py':
                raise MountObserved
            return path
        with tempfile.TemporaryDirectory() as folder:
            config = {'image': grade.IMAGE, 'assets_root': folder}
            with patch.object(grade, 'authenticate'), patch.object(grade, 'load_assets', return_value=assets), \
                    patch.object(grade, 'regular', side_effect=ordinary), \
                    patch.object(grade, 'digest', return_value='a' * 64), \
                    patch.object(grade.subprocess, 'run', side_effect=AssertionError('Native call forbidden')):
                with self.assertRaises(MountObserved):
                    grade.execute('validate', Path(folder) / 'candidate.npz',
                                  Path(folder) / 'score.json', config, time.monotonic() + 120, {})
        self.assertIn(common.SCORER / 'worker.py', seen)
        self.assertIn(HERE / 'scoring_core.py', seen)
        self.assertNotIn(common.SCORER / 'scoring_core.py', seen)

    def test_operational_manifest_binds_corrected_core(self):
        document = common.decode((HERE / 'SOURCE.json').read_bytes())
        relative = (HERE / 'scoring_core.py').relative_to(common.REPO).as_posix()
        self.assertEqual(document['files'][relative], common.pin((HERE / 'scoring_core.py').read_bytes()))


if __name__ == '__main__':
    unittest.main()
