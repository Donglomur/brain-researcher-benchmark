"""Generated scorer definitions only; no execution during source preparation."""
import io
import math
import os
from pathlib import Path
import stat
import struct
import tempfile
import unittest
from unittest import mock
import zipfile
import numpy as np
import scoring_core as core


def fixture():
    candidate = {'expected_counts': np.full((2, 40, 3), 0.5, dtype=np.float64),
                 'trial_ids': np.asarray(['t0', 't1']),
                 'forecast_unit_ids': np.asarray(['u0', 'u1', 'u2']),
                 'bin_left_edges_ms': np.arange(450, 650, 5),
                 'prediction_units': np.asarray('expected_spikes_per_bin'),
                 'panel_fingerprint': np.asarray('a' * 64)}
    public = {k: v for k, v in candidate.items() if k != 'expected_counts'}
    counts = np.zeros((2, 40, 3), dtype=np.uint16)
    counts[:, ::2, 0] = 1; counts[:, ::4, 1] = 1  # u2 is a zero-rate null unit.
    gold = {'target_counts': counts, 'trial_ids': public['trial_ids'],
            'unit_ids': public['forecast_unit_ids'], 'bin_left_edges_ms': public['bin_left_edges_ms'],
            'valid_mask': np.ones(counts.shape, dtype=bool), 'panel_fingerprint': public['panel_fingerprint']}
    return candidate, public, gold


def npy_bytes(array):
    stream = io.BytesIO(); np.save(stream, array, allow_pickle=True); return stream.getvalue()


class GeneratedScorerTests(unittest.TestCase):
    def test_arbitrary_float32_and_float64_archive(self):
        for dtype in (np.float32, np.float64):
            candidate, public, _ = fixture()
            candidate['expected_counts'] = candidate['expected_counts'].astype(dtype)
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / 'candidate.npz'; np.savez(path, **candidate)
                loaded = core.load_validated_submission(path, public, 2, 3)
                self.assertEqual(loaded['expected_counts'].dtype, dtype)

    def test_shape_object_extra_duplicate_link_and_truncation_before_np_load(self):
        candidate, _, _ = fixture()
        variants = []
        wrong = dict(candidate); wrong['expected_counts'] = np.ones((2, 39, 3)); variants.append(('shape', wrong))
        wrong = dict(candidate); wrong['expected_counts'] = np.full((2, 40, 3), 'x', dtype=object); variants.append(('object', wrong))
        wrong = dict(candidate); wrong['extra'] = np.asarray(1); variants.append(('extra', wrong))
        wrong = dict(candidate); wrong['expected_counts'] = np.ones((2, 40, 3), dtype=np.int64); variants.append(('integer_rates', wrong))
        with tempfile.TemporaryDirectory() as folder:
            for name, bundle in variants:
                path = Path(folder) / (name + '.npz'); np.savez(path, **bundle)
                with mock.patch.object(core.np, 'load', side_effect=AssertionError('Allocated before rejection')):
                    with self.assertRaises(ValueError): core.candidate_npz(path, 2, 3)
            for mode in ('duplicate', 'linked_member', 'truncated_payload'):
                path = Path(folder) / (mode + '.npz')
                with zipfile.ZipFile(path, 'w') as archive:
                    for field, value in candidate.items():
                        info = zipfile.ZipInfo(field + '.npy')
                        if mode == 'linked_member' and field == 'expected_counts':
                            info.create_system = 3; info.external_attr = (stat.S_IFLNK | 0o777) << 16
                        payload = npy_bytes(value)
                        if mode == 'truncated_payload' and field == 'expected_counts': payload = payload[:-1]
                        archive.writestr(info, payload)
                    if mode == 'duplicate': archive.writestr('trial_ids.npy', npy_bytes(candidate['trial_ids']))
                with mock.patch.object(core.np, 'load', side_effect=AssertionError('Allocated before rejection')):
                    with self.assertRaises(ValueError): core.candidate_npz(path, 2, 3)

    def test_filesystem_link_and_empty_archive_rejected(self):
        candidate, _, _ = fixture()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'candidate.npz'; np.savez(path, **candidate)
            linked = Path(folder) / 'linked.npz'; linked.symlink_to(path)
            empty = Path(folder) / 'empty.npz'; empty.write_bytes(b'')
            for item in (linked, empty):
                with mock.patch.object(core.np, 'load', side_effect=AssertionError('Allocated before rejection')):
                    with self.assertRaises(ValueError): core.candidate_npz(item, 2, 3)
            hardlinked = Path(folder) / 'hardlinked.npz'; os.link(path, hardlinked)
            with mock.patch.object(core.np, 'load', side_effect=AssertionError('Allocated before rejection')):
                with self.assertRaises(ValueError): core.candidate_npz(hardlinked, 2, 3)

    def test_crc_corruption_rejected_before_np_load(self):
        candidate, _, _ = fixture()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'corrupt.npz'; np.savez(path, **candidate)
            with zipfile.ZipFile(path) as archive:
                entry = archive.getinfo('expected_counts.npy')
                self.assertEqual(entry.compress_type, zipfile.ZIP_STORED)
                offset, size = entry.header_offset, entry.compress_size
            raw = bytearray(path.read_bytes())
            filename_length, extra_length = struct.unpack_from('<HH', raw, offset + 26)
            payload_start = offset + 30 + filename_length + extra_length
            raw[payload_start + size - 1] ^= 1  # Header and declared lengths remain valid.
            path.write_bytes(raw)
            with mock.patch.object(core.np, 'load', side_effect=AssertionError('Allocated before CRC rejection')):
                with self.assertRaises(zipfile.BadZipFile): core.candidate_npz(path, 2, 3)

    def test_public_rejections_precede_any_private_loader(self):
        candidate, public, _ = fixture()
        changes = [('expected_counts', np.zeros((2, 40, 3))),
                   ('expected_counts', np.full((2, 40, 3), np.nan)),
                   ('expected_counts', np.full((2, 40, 3), np.inf)),
                   ('trial_ids', np.asarray(['t0', 't0'])),
                   ('forecast_unit_ids', np.asarray(['u0', 'u1', 'wrong'])),
                   ('bin_left_edges_ms', np.arange(450, 650, 5) + 1),
                   ('panel_fingerprint', np.asarray('b' * 64)),
                   ('prediction_units', np.asarray('Hz'))]
        with tempfile.TemporaryDirectory() as folder:
            for index, (field, value) in enumerate(changes):
                changed = dict(candidate); changed[field] = value
                path = Path(folder) / (str(index) + '.npz'); np.savez(path, **changed)
                private_loader = mock.Mock(side_effect=AssertionError('Private target accessed'))
                with self.assertRaises(ValueError):
                    core.load_validated_submission(path, public, 2, 3)
                    private_loader()
                private_loader.assert_not_called()

    def test_axis_permutation_and_negative_gain_are_accepted(self):
        candidate, public, gold = fixture(); fixed = dict(candidate)
        candidate = dict(candidate); candidate['expected_counts'] = np.full((2, 40, 3), 5.0)
        candidate['expected_counts'][:, :, 0] = 3.0
        candidate['expected_counts'][1] *= 2.0
        original = core.evaluate(candidate, gold, fixed)
        candidate['trial_ids'] = candidate['trial_ids'][::-1]
        candidate['forecast_unit_ids'] = candidate['forecast_unit_ids'][::-1]
        candidate['expected_counts'] = candidate['expected_counts'][::-1, :, ::-1]
        core.validate_candidate(candidate, public, 2, 3)
        result = core.evaluate(candidate, gold, fixed)
        self.assertEqual(result['candidate']['fp_bps'], original['candidate']['fp_bps'])
        self.assertEqual(result['status'], 'scored_development_candidate')
        self.assertLess(result['candidate_minus_condition_fp_bps'], 0)
        self.assertFalse(result['positive_gain_required'])
        self.assertFalse(result['reference_family_required'])

    def test_joint_metric_and_independent_scalar_agree(self):
        candidate, _, gold = fixture()
        candidate['expected_counts'][:, :, 0] = 0.6
        candidate['expected_counts'][:, :, 1] = 0.3
        candidate['expected_counts'][:, :, 2] = 0.01
        vector = core.poisson_bits_per_spike(gold['target_counts'], candidate['expected_counts'], gold['valid_mask'])
        scalar = core.scalar_bits_per_spike(gold['target_counts'], candidate['expected_counts'], gold['valid_mask'])
        self.assertTrue(math.isclose(vector['co_bps'], scalar['fp_bps'], rel_tol=1e-12, abs_tol=1e-12))
        self.assertEqual(vector['target_spikes'], 60)
        self.assertEqual(vector['valid_cells'], 240)

    def test_zero_target_total_is_undefined_not_reward(self):
        candidate, _, gold = fixture(); gold['target_counts'][:] = 0
        result = core.evaluate(candidate, gold, candidate)
        self.assertEqual(result['status'], 'undefined_zero_target_spikes')
        self.assertIsNone(result['candidate']['fp_bps'])
        self.assertIsNone(result['candidate_minus_condition_fp_bps'])

    def test_official_source_wrong_pin_rejected_before_extraction(self):
        with self.assertRaises(ValueError): core.official_functions('unused.py', '0' * 64)


if __name__ == '__main__':
    unittest.main()
