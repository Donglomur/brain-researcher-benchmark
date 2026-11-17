"""Generated tests of the actual NumPy packet validator; no neural inputs."""
from fractions import Fraction
from pathlib import Path
import types
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'benchmarks/neural/NEURAL-078/implementations/neural078-deferred-grade/scorer/analysis_core.py'
core = types.ModuleType('_neural078_rt_core')
core.__file__ = str(SOURCE)
exec(compile(SOURCE.read_bytes(), str(SOURCE), 'exec'), core.__dict__)


def packet(person='sub-001', rt=512, n=1):
    return {
        'participant_id': np.asarray(person),
        'trial_ids': np.asarray([f'{person}-{i:024x}' for i in range(n)]),
        'epochs': np.zeros((n, 3, 1024), dtype=np.float64),
        'response_error': np.asarray([i % 2 for i in range(n)], dtype=np.uint8),
        'response_hand': np.ones(n, dtype=np.uint8),
        'stimulus_congruency': np.ones(n, dtype=np.uint8),
        'rt_samples': np.full(n, rt, dtype=np.int64),
        'sample_offsets': np.arange(-614, 410, dtype=np.int16),
        'channels': np.asarray(['FCz_reref', 'HEOG_bipolar', 'VEOG_bipolar']),
        'units': np.asarray('native_EEGLAB_amplitude'),
    }


class ReactionTimeBounds(unittest.TestCase):
    def test_admission_matches_exact_millisecond_definition(self):
        d = packet()
        for sample in range(-32, 1100):
            with self.subTest(sample=sample):
                d['rt_samples'][0] = sample
                milliseconds = Fraction(sample * 1000, 1024)
                if 200 <= milliseconds <= 1000:
                    self.assertIs(core.validate_packet(d, 'sub-001'), d)
                else:
                    with self.assertRaisesRegex(ValueError, 'Eligible marker RT'):
                        core.validate_packet(d, 'sub-001')

    def test_int64_overflow_aliases_and_extremes_refuse(self):
        for sample in ((1 << 61) + 512, -(1 << 61) + 512,
                       np.iinfo(np.int64).max, np.iinfo(np.int64).min):
            with self.subTest(sample=sample):
                self.assertFalse(200 <= Fraction(int(sample) * 1000, 1024) <= 1000)
                with self.assertRaisesRegex(ValueError, 'Eligible marker RT'):
                    core.validate_packet(packet(rt=sample), 'sub-001')

    def test_dtype_and_shape_contract_is_preserved(self):
        for rt in (np.asarray([512], dtype=np.uint64),
                   np.asarray([512], dtype=np.float64),
                   np.asarray([[512]], dtype=np.int64),
                   np.asarray(512, dtype=np.int64)):
            with self.subTest(dtype=rt.dtype, shape=rt.shape):
                d = packet()
                d['rt_samples'] = rt
                with self.assertRaisesRegex(ValueError, 'Eligible marker RT'):
                    core.validate_packet(d, 'sub-001')

    def test_boundary_samples_work_in_complete_eight_person_panel(self):
        packets = {person: packet(person, 205 if i % 2 else 1024, n=24)
                   for i, person in enumerate(core.PEOPLE)}
        report = core.make_report(packets)
        self.assertEqual(len(report['participants']), 8)
        self.assertEqual(report['aggregate']['status'], 'all_participants_supported')
        for row in report['participants']:
            self.assertEqual(row['matched_pairs_n'], 12)
            self.assertEqual(row['mean_RT_difference_ms'], 0.0)
            self.assertEqual(row['max_abs_RT_difference_ms'], 0.0)

    def test_one_overflowed_rt_refuses_complete_report(self):
        packets = {person: packet(person, n=24) for person in core.PEOPLE}
        packets[core.PEOPLE[-1]]['rt_samples'][0] = (1 << 61) + 512
        with self.assertRaisesRegex(ValueError, 'Eligible marker RT'):
            core.make_report(packets)


if __name__ == '__main__':
    unittest.main()
