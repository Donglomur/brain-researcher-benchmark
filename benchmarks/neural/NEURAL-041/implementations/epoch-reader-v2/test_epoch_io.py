"""Generated controls for the public-API replacement epoch reader."""
import argparse
import importlib.util
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import zipfile

PARSER = argparse.ArgumentParser()
PARSER.add_argument('--runtime-source', type=Path, default=Path(__file__).resolve().parent.parent / 'registered-runtime/runtime/source')
PARSER.add_argument('--scratch', type=Path, required=True)
ARGS, REST = PARSER.parse_known_args()
sys.path.insert(0, str(ARGS.runtime_source.resolve()))
import numpy as np
from core import Budget, Refusal, pin


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


READER = module('n041_public_epoch', Path(__file__).with_name('epoch_io.py'))
OLD = module('n041_original_epoch', ARGS.runtime_source / 'epoch_io.py')
WRITTEN = 0


def arrays():
    return {
        'lfp': np.arange(2000, dtype='<f8').reshape(2, 1000) / 1000,
        'lfp_region': np.array([0, 1], dtype='<i4'),
        'spike_times': np.array([0., .5, 2.49, .2, 2.4], dtype='<f8'),
        'spike_offsets': np.array([0, 3, 5], dtype='<i8'),
        'unit_region': np.array([0, 1], dtype='<i4'),
    }


def npy(value, version=(1, 0)):
    body = io.BytesIO()
    np.lib.format.write_array(body, value, version=version, allow_pickle=False)
    return body.getvalue()


def header(shape, descr='<f8', fortran=False, padding=0):
    value = repr({'descr': descr, 'fortran_order': fortran, 'shape': shape}).encode('ascii') + b' ' * padding + b'\n'
    return b'\x93NUMPY\x01\x00' + struct.pack('<H', len(value)) + value


class EpochReaderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='n041-generated-', dir=ARGS.scratch)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()

    def fixture(self, values=None, version=(1, 0), replace=None):
        global WRITTEN
        values = arrays() if values is None else values
        out = io.BytesIO()
        with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_STORED) as z:
            for name, value in sorted(values.items()):
                info = zipfile.ZipInfo(name + '.npy', date_time=(1980, 1, 1, 0, 0, 0))
                z.writestr(info, replace[name] if replace and name in replace else npy(value, version))
        body = out.getvalue()
        path = self.root / 'epoch.npz'
        path.write_bytes(body)
        path.chmod(0o444)
        WRITTEN += len(body)
        return {'epoch': {'path': path.name, 'pin': pin(body)}}

    def read(self, row, reader=READER):
        budget = Budget(0, 1, 128 * 1024, 0, clock=lambda: .5)
        return reader.load_epoch(self.root, row, budget, 32768, ['Hippo', 'Amy'])

    def assert_arrays(self, actual, expected):
        self.assertEqual(set(actual), set(expected))
        for name in actual:
            self.assertEqual(actual[name].dtype, expected[name].dtype)
            np.testing.assert_array_equal(actual[name], expected[name])

    def test_complete_v1_epoch(self):
        values = arrays()
        self.assert_arrays(self.read(self.fixture(values)), values)

    def test_complete_v2_epoch(self):
        values = arrays()
        self.assert_arrays(self.read(self.fixture(values, (2, 0))), values)

    def test_missing_private_export_regression(self):
        row = self.fixture()
        original = np.lib.format
        public_only = types.SimpleNamespace(
            read_magic=original.read_magic,
            read_array_header_1_0=original.read_array_header_1_0,
            read_array_header_2_0=original.read_array_header_2_0,
        )
        # Public readers retain their real module globals. Only the exported
        # surface is restricted, as when an implementation moves internally.
        with patch.object(np.lib, 'format', public_only):
            with self.assertRaises(AttributeError):
                self.read(row, OLD)
            self.assert_arrays(self.read(row), arrays())

    def test_spike_only_epoch_retained(self):
        values = arrays()
        values['lfp'] = np.empty((0, 1000), dtype='<f8')
        values['lfp_region'] = np.empty(0, dtype='<i4')
        self.assert_arrays(self.read(self.fixture(values)), values)

    def test_unsupported_npy_version_rejected_before_load(self):
        row = self.fixture(version=(3, 0))
        with patch.object(np, 'load', side_effect=AssertionError('array load reached')) as load:
            with self.assertRaisesRegex(Refusal, 'primitive header'):
                self.read(row)
            load.assert_not_called()

    def test_oversized_header_rejected_before_load(self):
        row = self.fixture(replace={'lfp': header((2, 1000), padding=1500)})
        with patch.object(np, 'load', side_effect=AssertionError('array load reached')) as load:
            with self.assertRaises(ValueError):
                self.read(row)
            load.assert_not_called()

    def test_advertised_extent_rejected_before_load(self):
        row = self.fixture(replace={'lfp': header((2, 20000))})
        with patch.object(np, 'load', side_effect=AssertionError('array load reached')) as load:
            with self.assertRaisesRegex(Refusal, 'advertised extent'):
                self.read(row)
            load.assert_not_called()

    def test_fortran_payload_rejected_before_load(self):
        row = self.fixture(replace={'lfp': header((2, 1000), fortran=True)})
        with patch.object(np, 'load', side_effect=AssertionError('array load reached')) as load:
            with self.assertRaisesRegex(Refusal, 'payload'):
                self.read(row)
            load.assert_not_called()

    def test_object_payload_rejected_before_load(self):
        row = self.fixture(replace={'lfp': header((2, 1000), descr='|O')})
        with patch.object(np, 'load', side_effect=AssertionError('array load reached')) as load:
            with self.assertRaisesRegex(Refusal, 'payload'):
                self.read(row)
            load.assert_not_called()

    def test_region_and_spike_bounds_retained(self):
        for name, bad in [('lfp_region', np.array([0, 2], dtype='<i4')),
                          ('spike_times', np.array([0., .5, 2.5, .2, 2.4]))]:
            with self.subTest(name=name):
                values = arrays()
                values[name] = bad
                path = self.root / 'epoch.npz'
                if path.exists():
                    path.unlink()
                with self.assertRaises(Refusal):
                    self.read(self.fixture(values))


if __name__ == '__main__':
    result = unittest.main(argv=[sys.argv[0]] + REST, exit=False)
    print(json.dumps({'python': sys.version.split()[0], 'numpy': np.__version__,
                      'tests': result.result.testsRun,
                      'failures': len(result.result.failures),
                      'errors': len(result.result.errors),
                      'generated_fixture_bytes_written': WRITTEN,
                      'authentic_inputs_opened': 0}))
    raise SystemExit(not result.result.wasSuccessful())
