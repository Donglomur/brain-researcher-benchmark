"""Tiny generated HDF5 controls for the original spike/QC preparation boundary.

No authentic data or NeuroPyxels execution. Optional --package and
--preparation paths support testing an isolated source candidate.
"""
import argparse
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

import h5py
import numpy as np

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('--package', type=Path, default=Path(__file__).resolve().parents[1])
parser.add_argument('--preparation', type=Path)
parser.add_argument('--work-dir', type=Path)
options, remaining = parser.parse_known_args()
sys.path.insert(0, str(options.package))
if options.preparation:
    spec = importlib.util.spec_from_file_location('programme.preparation', options.preparation)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

from programme.cohort import Member, Population, SupportError, UnitKey
from programme.preparation import load_raw_unit


class SpikeOrderChecks(unittest.TestCase):
    def load(self, spikes, species='mouse'):
        key = UnitKey(species, 'generated_lab', 'generated_animal',
                      'generated_session', 'generated_recording', '7')
        member = Member(key, 'lisberger' if species == 'macaque' else 'hull_labelled',
                        'generated_unit', Population.MONKEY_EXPERT if species == 'macaque'
                        else Population.MOUSE_GROUND_TRUTH, 'eligible', 'generated only',
                        0, 'generated only')
        with tempfile.TemporaryDirectory(prefix='c4-spike-order-', dir=options.work_dir) as temp:
            path = Path(temp) / 'generated.h5'
            with h5py.File(path, 'w') as handle:
                group = handle.create_group(member.h5_group)
                group['sampling_rate'] = np.float64(40000 if species == 'macaque' else 30000)
                group['spike_indices'] = spikes
                group['mean_waveform_preprocessed'] = np.zeros((2, 4))
                group['channelmap'] = np.arange(2)
                group['dataset_id'] = np.bytes_(key.recording)
                group['neuron_id' if species == 'macaque' else 'neuron_relative_id'] = np.bytes_(key.unit)
                group['human_layer' if species == 'macaque' else 'phyllum_layer'] = np.bytes_('unknown')
                if species == 'mouse':
                    group['sane_spikes'] = np.arange(len(spikes)) != 1
                    group['fn_fp_filtered_spikes'] = np.ones(len(spikes), dtype=bool)
            raw = load_raw_unit(path, member,
                external_quality_policy='release_lisberger_all_spikes_curator_qc_required')
            # The loader closes the source without changing its timestamps.
            with h5py.File(path, 'r') as handle:
                np.testing.assert_array_equal(handle[member.h5_group]['spike_indices'][()], spikes)
            return raw

    def test_unsigned_decreases_rejected_before_preprocessing(self):
        for species in ('mouse', 'macaque'):
            for dtype in (np.uint8, np.uint16, np.uint32, np.uint64):
                with self.subTest(species=species, dtype=dtype):
                    with self.assertRaisesRegex(SupportError, 'ordered nonnegative integers'):
                        self.load(np.array([0, 30, 20, 60], dtype=dtype), species)

    def test_signed_decreases_still_rejected(self):
        for dtype in (np.int8, np.int16, np.int32, np.int64):
            with self.subTest(dtype=dtype):
                with self.assertRaisesRegex(SupportError, 'ordered nonnegative integers'):
                    self.load(np.array([0, 30, 20, 60], dtype=dtype))

    def test_ordered_indices_duplicates_and_qc_are_preserved(self):
        for dtype in (np.uint8, np.uint16, np.uint32, np.uint64,
                      np.int8, np.int16, np.int32, np.int64):
            with self.subTest(dtype=dtype):
                spikes = np.array([0, 1, 1, 127], dtype=dtype)
                raw = self.load(spikes)
                self.assertEqual(raw.spike_indices.dtype, spikes.dtype)
                np.testing.assert_array_equal(raw.spike_indices, spikes)
                np.testing.assert_array_equal(raw.sane_mask, [True, False, True, True])
                np.testing.assert_array_equal(raw.quality_mask, [True] * 4)

    def test_full_unsigned_range_is_not_cast_to_signed_or_float(self):
        spikes = np.array([0, 2**63, 2**64 - 1], dtype=np.uint64)
        raw = self.load(spikes)
        self.assertEqual(raw.spike_indices.dtype, spikes.dtype)
        np.testing.assert_array_equal(raw.spike_indices, spikes)
        # This checks validation only; these are not feasible ACG inputs.

    def test_negative_signed_indices_still_rejected(self):
        with self.assertRaisesRegex(SupportError, 'ordered nonnegative integers'):
            self.load(np.array([-1, 0, 30], dtype=np.int64))

    def test_noninteger_indices_still_rejected(self):
        with self.assertRaisesRegex(SupportError, 'ordered nonnegative integers'):
            self.load(np.array([0., 1., 30.]))


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0], *remaining])
