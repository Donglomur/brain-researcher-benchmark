"""Independent generated-input boundaries and literal source-selection controls.

No original packet, estimator fit, scientific score or installed dependency
change is involved. NPY failures must be detected before np.load allocates.
"""
from __future__ import annotations

import hashlib
import io
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import glm_search as G
import native_inputs as N


def generated_arrays():
    n = 12
    z = np.zeros((n, 7), dtype=np.float64)
    z[:, 0] = np.arange(n)
    z[:, 1] = np.arange(n)[::-1]
    z[:, 2] = 5
    z[:, 3] = 6
    z[:, 4] = np.arange(n) / 10
    z[:, 5] = np.repeat(np.arange(6) % 2, 2)
    z[:, 6] = np.repeat(np.arange(6) % 2, 2)
    return {'x': np.arange(n * 3, dtype=np.int64).reshape(n, 3) % 4,
            'z': z, 't': .25 + np.arange(n, dtype=np.float64) / 2,
            'trial': np.repeat(np.arange(6, dtype=np.int64), 2),
            'unit_ids': np.array([4, 8, 15], dtype=np.int64),
            'strict_columns': np.array([0, 2], dtype=np.int64)}


def case():
    return {'rows': 12, 'source_asset_id': N.SOURCE_ORDER['KL8'][0],
            'source_epoch': 1, 'id': 'KL8-s01-CA1',
            'native': {'path': 'KL8-s01-CA1.npz', 'bytes': 1, 'sha256': '0' * 64}}


def npy_body(array):
    stream = io.BytesIO()
    np.save(stream, array, allow_pickle=False)
    return stream.getvalue()


def header_only(shape, descr='<f8', *, padding=0):
    # Construct NPY1.0 independently of NumPy's writer, without allocating shape.
    text = repr({'descr': descr, 'fortran_order': False, 'shape': shape})
    text += ' ' * ((-(10 + len(text) + 1)) % 64 + padding)
    body = text.encode('ascii') + b'\n'
    return b'\x93NUMPY\x01\x00' + struct.pack('<H', len(body)) + body


def packet(arrays=None, replacements=None):
    arrays = generated_arrays() if arrays is None else arrays
    replacements = replacements or {}
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, values in arrays.items():
            archive.writestr(name + '.npy', replacements.get(name, npy_body(values)))
    return stream.getvalue()


class HeaderBoundaries(unittest.TestCase):
    def assert_before_array_load(self, replacements):
        body = packet(replacements=replacements)
        with mock.patch.object(N.np, 'load', side_effect=AssertionError('np.load reached before rejection')):
            with self.assertRaises(ValueError):
                N.load_packet(body, case())

    def test_enormous_declared_shape_refused_before_allocation(self):
        self.assert_before_array_load({'x': header_only((2**40, 3), '<i8')})

    def test_object_dtype_refused_before_array_load(self):
        self.assert_before_array_load({'x': header_only((12, 3), '|O') + b'no pickle allowed'})

    def test_structured_dtype_refused_before_array_load(self):
        self.assert_before_array_load({'x': header_only((12, 3), [('field', '<f8')]) + b'\0' * 288})

    def test_short_payload_refused_before_array_load(self):
        self.assert_before_array_load({'x': npy_body(generated_arrays()['x'])[:-8]})

    def test_trailing_payload_refused_before_array_load(self):
        self.assert_before_array_load({'x': npy_body(generated_arrays()['x']) + b'extra bytes'})

    def test_wrong_latent_dimensions_refused_before_array_load(self):
        self.assert_before_array_load({'z': npy_body(np.zeros((12, 6), dtype=np.float64))})

    def test_oversized_header_refused_before_array_load(self):
        self.assert_before_array_load({'x': header_only((12, 3), '<i8', padding=20000) + b'\0' * 288})

    def test_non_npy_member_refused_before_array_load(self):
        self.assert_before_array_load({'x': b'this is not an NPY member'})


class IdentityBoundaries(unittest.TestCase):
    def test_duplicate_native_unit_ids_refused(self):
        arrays = generated_arrays()
        arrays['unit_ids'][1] = arrays['unit_ids'][0]
        with self.assertRaises(N.ContractError):
            N.load_packet(packet(arrays), case())

    def test_nonmonotonic_source_times_refused(self):
        arrays = generated_arrays()
        arrays['t'][4] = arrays['t'][3]
        with self.assertRaises(N.ContractError):
            N.load_packet(packet(arrays), case())

    def test_inconsistent_trial_correctness_refused(self):
        arrays = generated_arrays()
        arrays['z'][1, 5] = 1
        with self.assertRaises(N.ContractError):
            N.load_packet(packet(arrays), case())

    def test_negative_native_trial_id_refused(self):
        arrays = generated_arrays()
        arrays['trial'][0] = -1
        with self.assertRaises(N.ContractError):
            N.load_packet(packet(arrays), case())

    def test_wrong_design_row_count_refused(self):
        record = case()
        record['rows'] = 13
        with self.assertRaises(N.ContractError):
            N.load_packet(packet(), record)

    def test_checked_reader_refuses_symlink_and_fifo(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'ordinary'
            target.write_bytes(b'packet')
            digest = hashlib.sha256(b'packet').hexdigest()
            alias = Path(directory) / 'alias'
            alias.symlink_to(target)
            fifo = Path(directory) / 'fifo'
            os.mkfifo(fifo)
            for path in (alias, fifo):
                with self.subTest(path=path.name), self.assertRaises((N.ContractError, OSError)):
                    N.checked_bytes(path, digest, 6)


class SourceSelectionBoundaries(unittest.TestCase):
    @staticmethod
    def cv_result(scores):
        return {f'split{i}_test_score': scores[i] for i in range(10)}

    def test_finite_tie_chooses_first_alpha(self):
        scores = np.zeros((10, 10))
        scores[:, 2] = scores[:, 7] = 3
        self.assertEqual(G.source_refit(self.cv_result(scores)), 2)

    def test_all_nan_alpha_is_not_silently_removed(self):
        scores = np.zeros((10, 10))
        scores[:, 3] = np.nan
        scores[:, 9] = 20
        self.assertEqual(G.source_refit(self.cv_result(scores)), 3)

    def test_all_nan_grid_preserves_first_argmax(self):
        scores = np.full((10, 10), np.nan)
        self.assertEqual(G.source_refit(self.cv_result(scores)), 0)

    def test_statistics_count_infinities_as_non_nan(self):
        scores = np.ones((1, 10, 10))
        scores[0, 0, 0] = np.inf
        scores[0, 0, 1] = np.nan
        means, deviations, counts = G.score_statistics(scores)
        self.assertEqual(int(counts[0, 0]), 9)
        self.assertTrue(np.isposinf(means[0, 0]))
        self.assertTrue(np.isnan(deviations[0, 0]))
        np.testing.assert_array_equal(counts[0, 1:], np.full(9, 10))


class CompleteGridReduction(unittest.TestCase):
    def test_all13824_jobs_reduce216_source_scores_without_winner(self):
        import producer as P
        calls = []
        binding = {'generated': 'complete numerical reduction control'}
        animals = ('KL8', 'ER1', 'JS34', 'JS14', 'JS17', 'JS21', 'JS15', 'ZT2')

        def supplied_checkpoint(directory, observed_binding, *, max_bytes, arrays):
            name = Path(directory).name
            region, encoded_basis, animal, encoded_session = name.split('-')
            basis = int(encoded_basis[1:])
            session = int(encoded_session[1:]) - 1
            cell = animals.index(animal) * 8 + session
            self.assertEqual(observed_binding, binding)
            self.assertEqual(max_bytes, 12345)
            self.assertIs(arrays, False)
            value = (100000 if region == 'PFC' else 0) + 100 * basis + cell
            if region == 'CA1' and basis == 0:
                value = {'__nonfinite__': 'nan'} if cell == 0 else cell + 1
            if region == 'CA1' and basis == 1:
                value = {'__nonfinite__': 'nan'}
            if region == 'PFC' and basis == 107 and cell == 63:
                value = {'__nonfinite__': '+inf'}
            calls.append(name)
            return {'job': {'region': region, 'basis_index': basis, 'basis': list(G.GRID[basis]),
                            'animal': animal, 'session_index': session, 'id': name},
                    'source_session_mean_selected_cv_d2': value}

        with mock.patch.object(P, 'load_result', side_effect=supplied_checkpoint):
            result = P.validate_complete_grid('unused-generated-directory', binding,
                                               max_result_bytes=12345)
        self.assertEqual(len(calls), 13824)
        self.assertEqual(len(set(calls)), 13824)
        self.assertEqual(result['jobs'], calls)
        self.assertEqual(calls[0], 'CA1-b000-KL8-s01')
        self.assertEqual(calls[-1], 'PFC-b107-ZT2-s08')
        self.assertIsNone(result['winner'])
        scores = result['configuration_scores']
        self.assertEqual([(r['region'], r['basis_index']) for r in scores],
                         [(r, b) for r in ('CA1', 'PFC') for b in range(108)])
        self.assertTrue(all(r['session_values'].shape == (64,) for r in scores))
        self.assertEqual(scores[0]['score'], 33)
        self.assertTrue(np.isnan(scores[0]['session_values'][0]))
        self.assertTrue(np.isnan(scores[1]['score']))
        self.assertTrue(np.isnan(scores[1]['session_values']).all())
        self.assertEqual(scores[2]['score'], 231.5)
        self.assertEqual(scores[108]['score'], 100031.5)
        self.assertTrue(np.isposinf(scores[-1]['score']))
        self.assertTrue(np.isposinf(scores[-1]['session_values'][-1]))


if __name__ == '__main__':
    unittest.main()
