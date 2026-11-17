"""Invented C/F storage-order controls; no original packet is opened."""
import hashlib
import io
from pathlib import Path
import struct
import sys
import unittest
from unittest import mock
import zipfile

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import native_inputs as N

SERIALIZED_FIXTURE_BYTES = 0


def fixture():
    counts = [np.arange(6, dtype=np.int64) * 10 + u for u in range(5)]
    raw = np.stack(counts, axis=1)
    locations = np.array(['CA1', 'PFC', 'CA1', 'PFC', 'CA1'])
    area_ix = np.flatnonzero(locations == 'CA1')
    # Literal existing preparation operations; astype defaults to order='K'.
    x = raw[:, area_ix].astype(np.int64)
    z = np.column_stack([np.arange(6) * 3., np.arange(6) * 7. + 2,
                         np.arange(6) + 5., np.arange(6) * 2. + 4,
                         np.arange(6) + 1., np.repeat([0., 1., 0.], 2),
                         np.repeat([1., 0., 1.], 2)])
    return {'x': x, 'z': z.astype(np.float64), 't': np.arange(6) * .5 + .25,
            'trial': np.repeat(np.array([30, 90, 55], dtype=np.int64), 2),
            'unit_ids': np.array([10, 20, 30, 40, 50], dtype=np.int64)[area_ix].astype(np.int64),
            'strict_columns': np.array([0, 1, 2], dtype=np.int64)}


def npy_body(value):
    stream = io.BytesIO()
    np.save(stream, value, allow_pickle=False)
    return stream.getvalue()


def literal_header(shape, dtype='<i8', fortran=True, payload=b''):
    header = repr({'descr': dtype, 'fortran_order': fortran, 'shape': shape}).encode('latin1')
    padding = (-(10 + len(header) + 1)) % 64
    header += b' ' * padding + b'\n'
    return b'\x93NUMPY\x01\x00' + struct.pack('<H', len(header)) + header + payload


def archive(values, replacement=None):
    global SERIALIZED_FIXTURE_BYTES
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as zipped:
        for key, value in values.items():
            body = replacement[key] if replacement and key in replacement else npy_body(value)
            zipped.writestr(key + '.npy', body)
    result = stream.getvalue()
    SERIALIZED_FIXTURE_BYTES += len(result)
    if SERIALIZED_FIXTURE_BYTES > 65536:
        raise AssertionError('generated in-memory fixture budget exceeded64KiB')
    return result


def source_saved(values):
    global SERIALIZED_FIXTURE_BYTES
    stream = io.BytesIO()
    np.savez_compressed(stream, **values)
    result = stream.getvalue()
    SERIALIZED_FIXTURE_BYTES += len(result)
    if SERIALIZED_FIXTURE_BYTES > 65536:
        raise AssertionError('generated in-memory fixture budget exceeded64KiB')
    return result


def case_for(body):
    return {'id': 'KL8-s01-CA1', 'rows': 6, 'source_asset_id': 'generated-asset',
            'source_epoch': 3,
            'native': {'path': 'generated.npz', 'bytes': len(body),
                       'sha256': hashlib.sha256(body).hexdigest()}}


class NativeStorageOrderControls(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        print(f'generated_serialized_fixture_bytes={SERIALIZED_FIXTURE_BYTES}; '
              'fixture_disk_bytes=0; authentic_payload_reads=0', flush=True)

    def assert_rejected_before_load(self, body, message=None):
        with mock.patch.object(N.np, 'load', side_effect=AssertionError('np.load reached malformed member')) as load:
            if message:
                with self.assertRaisesRegex(N.ContractError, message):
                    N.load_packet(body, case_for(body))
            else:
                with self.assertRaises((N.ContractError, ValueError)):
                    N.load_packet(body, case_for(body))
            load.assert_not_called()

    def test_literal_original_column_selection_and_save_preserves_matrix(self):
        arrays = fixture()
        self.assertTrue(arrays['x'].flags.f_contiguous)
        self.assertFalse(arrays['x'].flags.c_contiguous)
        body = source_saved(arrays)
        with zipfile.ZipFile(io.BytesIO(body)) as zipped:
            raw = zipped.read('x.npy')
        stream = io.BytesIO(raw)
        version = np.lib.format.read_magic(stream)
        shape, fortran, dtype = np.lib.format._read_array_header(stream, version, max_header_size=16384)
        self.assertTrue(fortran)
        wire = np.frombuffer(raw, dtype=dtype, offset=stream.tell())
        np.testing.assert_array_equal(wire.reshape(shape, order='F'), arrays['x'])
        self.assertFalse(np.array_equal(wire.reshape(shape, order='C'), arrays['x']))
        loaded = N.load_packet(body, case_for(body))
        np.testing.assert_array_equal(loaded['x'], [[0, 2, 4], [10, 12, 14], [20, 22, 24],
                                                 [30, 32, 34], [40, 42, 44], [50, 52, 54]])
        np.testing.assert_array_equal(loaded['native_unit_ids'], [10, 30, 50])
        np.testing.assert_array_equal(loaded['unit_ids'], ['generated-asset|unit=10',
                                                        'generated-asset|unit=30',
                                                        'generated-asset|unit=50'])

    def test_all_c_f_x_z_combinations_equal_independent_numpy_decode(self):
        original = fixture()
        baseline = None
        for x_order in ('C', 'F'):
            for z_order in ('C', 'F'):
                arrays = {**original, 'x': np.array(original['x'], order=x_order, copy=True),
                          'z': np.array(original['z'], order=z_order, copy=True)}
                body = source_saved(arrays)
                with np.load(io.BytesIO(body), allow_pickle=False) as independent:
                    expected = {key: independent[key].copy() for key in independent.files}
                loaded = N.load_packet(body, case_for(body))
                for key in ('x', 'z', 't', 'trial'):
                    np.testing.assert_array_equal(loaded[key], expected[key])
                np.testing.assert_array_equal(loaded['native_unit_ids'], expected['unit_ids'])
                if baseline is None:
                    baseline = loaded
                for key in ('x', 'z', 't', 'trial', 'row_ids', 'unit_ids', 'native_unit_ids'):
                    np.testing.assert_array_equal(loaded[key], baseline[key])
        expected_rows = [f'generated-asset|epoch=3|t={float(t).hex()}|trial={int(tr)}'
                         for t, tr in zip(original['t'], original['trial'])]
        np.testing.assert_array_equal(baseline['row_ids'], expected_rows)

    def test_fortran_non_native_endian_numeric_values_are_preserved(self):
        original = fixture()
        values = {**original, 'x': np.array(original['x'], dtype='>i8', order='F'),
                  'z': np.array(original['z'], dtype='>f8', order='F')}
        body = archive(values)
        loaded = N.load_packet(body, case_for(body))
        np.testing.assert_array_equal(loaded['x'], original['x'])
        np.testing.assert_array_equal(loaded['z'], original['z'])

    def test_fortran_wrong_shape_rejected_before_array_loading(self):
        values = fixture()
        for name, raw in [('x', literal_header((3, 6), payload=values['x'].tobytes(order='F'))),
                          ('z', literal_header((7, 6), dtype='<f8', payload=values['z'].tobytes(order='F'))),
                          ('x', literal_header((-6, 3)))]:
            with self.subTest(member=name):
                self.assert_rejected_before_load(archive(values, {name: raw}))

    def test_fortran_truncated_or_trailing_payload_rejected_before_loading(self):
        values = fixture()
        raw = npy_body(np.array(values['x'], order='F'))
        for damaged in (raw[:-1], raw + b'\x00'):
            self.assert_rejected_before_load(archive(values, {'x': damaged}), 'payload length')

    def test_fortran_object_structured_and_complex_dtypes_remain_refused(self):
        values = fixture()
        for dtype in ('|O', [('danger', '<i8')], '<c16'):
            # Only a literal primitive header is built; no pickle is created or executed.
            raw = literal_header((6, 3), dtype=dtype, fortran=True)
            self.assert_rejected_before_load(archive(values, {'x': raw}), 'plain numeric')

    def test_fortran_declared_huge_extent_cannot_allocate(self):
        values = fixture()
        raw = literal_header((128 * 1024**2, 3), fortran=True)
        self.assert_rejected_before_load(archive(values, {'x': raw}), 'exceed ceiling')

    def test_header_order_must_be_boolean_before_loading(self):
        values = fixture()
        for flag in (1, 'F', None):
            raw = literal_header((6, 3), fortran=flag, payload=values['x'].tobytes(order='F'))
            self.assert_rejected_before_load(archive(values, {'x': raw}))

    def test_fortran_order_does_not_bypass_finite_nonnegative_count_checks(self):
        for name, invalid in [('x', -1.), ('x', np.nan), ('z', np.inf)]:
            values = fixture()
            values[name] = np.array(values[name], dtype=float, order='F')
            values[name][0, 0] = invalid
            body = archive(values)
            with self.subTest(member=name, invalid=invalid), self.assertRaises(N.ContractError):
                N.load_packet(body, case_for(body))


if __name__ == '__main__':
    unittest.main()
