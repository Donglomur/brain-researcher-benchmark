"""Generated software controls only; no authentic recording or target reads."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch

import numpy as np


HERE = Path(__file__).resolve().parent
ORIGINAL = HERE.parent / 'investigation' / 'source_repository' / 'private'
PINS = {
    'artifact_io.py': 'adf200892c5b850721d2ac479d506f7287bc325974c9d1ffcae8cedae4b6b817',
    'data_adapter.py': '1acf5c26d1eaee7f04117fc68864537446bddba45312060d74a24e8f0afbf476',
    'analysis_core.py': '8b1d19029d244701e93ee309a7ca9a1b0a1790474280cecd6ae2cf68d4c80502',
}


def load(name, path, pin=None):
    if pin is not None:
        if hashlib.sha256(path.read_bytes()).hexdigest() != pin:
            raise AssertionError('predecessor source changed: ' + path.name)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def example():
    # Invented source primitives. Contact IDs deliberately differ from row
    # indices, two contacts share depth but have different labels, and one
    # contact has no units. A source unit has an empty spike segment.
    edges = np.arange(-50, 51, dtype=np.float64) / 1000
    first = [1 + edges[index] for index in (0, 1, 50, 51, 51, 99, 100)]
    first += [2 + edges[index] for index in (0, 99, 100)]
    second = [1 + edges[52], 1 + edges[53], 2 + edges[52]]
    return {
        'unit_id': np.array([17, 31, 52]),
        'unit_electrode': np.array([0, 1, 3]),
        'spike_times': np.array(first + second),
        'spike_end': np.array([len(first), len(first) + len(second), len(first) + len(second)]),
        'trial_start': np.array([1., 2.]),
        'trial_stop': np.array([1.0001, 2.0001]),
        'electrode_id': np.array([101, 202, 303, 404]),
        'electrode_y': np.array([0., 0., 1., 2.]),
        'electrode_layer': np.array([4, 6, 0, 6]),
    }


class AdapterControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.io = load('artifact_io', ORIGINAL / 'artifact_io.py', PINS['artifact_io.py'])
        cls.prior_module = sys.modules.get('artifact_io')
        sys.modules['artifact_io'] = cls.io
        cls.old = load('prior_adapter', ORIGINAL / 'data_adapter.py', PINS['data_adapter.py'])
        cls.new = load('successor_adapter', HERE / 'data_adapter.py')
        cls.core = load('original_core', ORIGINAL / 'analysis_core.py', PINS['analysis_core.py'])

    @classmethod
    def tearDownClass(cls):
        if cls.prior_module is None:
            del sys.modules['artifact_io']
        else:
            sys.modules['artifact_io'] = cls.prior_module

    def setUp(self):
        self.row = {'asset_id': 'invented-record', 'participant_id': 'invented-mouse', 'area': 'A1'}
        self.arrays = example()

    def rejected(self, arrays, pattern):
        # A malformed primitive must not reach the uninitialized output buffer.
        original_empty = np.empty
        def deny_count_buffer(shape, *args, **kwargs):
            if isinstance(shape, tuple) and len(shape) == 3 and shape[-1] == 100:
                raise AssertionError('count buffer allocated before validation')
            return original_empty(shape, *args, **kwargs)
        class AdapterNumpy:
            def __getattr__(self, name):
                return deny_count_buffer if name == 'empty' else getattr(np, name)
        # Only the adapter sees this spy. NumPy's own validation/lazy imports
        # must retain the real np.empty, including its function metadata.
        with patch.object(self.new, 'np', AdapterNumpy()):
            with self.assertRaisesRegex(ValueError, pattern):
                self.new.normalized(self.row, arrays)

    def test_half_open_bins_against_scalar_oracle_and_predecessor(self):
        got = self.new.normalized(self.row, self.arrays)
        old = self.old.normalized(self.row, self.arrays)
        expected = np.zeros((2, 3, 100), dtype=np.uint32)
        expected[0, 0, [0, 1, 50, 99]] = 1
        expected[0, 0, 51] = 2
        expected[1, 0, [0, 99]] = 1
        expected[0, 1, [52, 53]] = 1
        expected[1, 1, 52] = 1
        np.testing.assert_array_equal(got['counts'], expected)
        np.testing.assert_array_equal(got['counts'], old['counts'])
        lower = 0
        for unit, end in enumerate(self.arrays['spike_end']):
            spikes = self.arrays['spike_times'][lower:int(end)]
            lower = int(end)
            for trial, start in enumerate(self.arrays['trial_start']):
                for index in range(100):
                    left = start + (index - 50) / 1000
                    right = start + (index - 49) / 1000
                    self.assertEqual(int(got['counts'][trial, unit, index]),
                                     sum(left <= timestamp < right for timestamp in spikes))
        self.assertEqual(got['unit_electrode_id'], [101, 202, 404])
        self.assertEqual(got['electrodes'], old['electrodes'])
        self.assertEqual([row['layer'] for row in got['electrodes']], ['L4', 'L6', 'outside', 'L6'])
        self.assertEqual([row['depth_rank'] for row in got['electrodes']], [0, 0, 1, 2])

    def test_negative_contact_index_counterexample(self):
        self.arrays['unit_electrode'][0] = -1
        # Demonstrates the real predecessor defect without authentic input.
        self.assertEqual(self.old.normalized(self.row, self.arrays)['unit_electrode_id'][0], 404)
        self.rejected(self.arrays, 'nonnegative contact-table row')

    def test_short_ragged_index_refused_before_allocation(self):
        self.arrays['spike_end'] = self.arrays['spike_end'][:-1]
        self.rejected(self.arrays, 'per source unit')

    def test_unsorted_unit_spikes_refused_before_searchsorted(self):
        self.arrays['spike_times'][0:2] = self.arrays['spike_times'][1::-1]
        # The former adapter silently accepts a sequence outside searchsorted's contract.
        self.assertEqual(self.old.normalized(self.row, self.arrays)['counts'].shape, (2, 3, 100))
        self.rejected(self.arrays, 'must be chronological')

    def test_entire_ragged_partition_required(self):
        for endpoints in ([10, 9, 13], [-1, 13, 13], [10, 13, 14], [10, 12, 12]):
            with self.subTest(endpoints=endpoints):
                arrays = copy.deepcopy(self.arrays)
                arrays['spike_end'] = np.array(endpoints)
                self.rejected(arrays, 'partition the entire spike vector')

    def test_shapes_integer_types_and_finiteness(self):
        cases = [
            ('unit_electrode', np.array([0., .5, 3.]), 'integer values'),
            ('unit_electrode', np.array([False, True, True]), 'numeric array'),
            ('unit_electrode', np.array([0, 1, 4]), 'contact-table row'),
            ('spike_times', np.array([np.nan] * 13), 'finite'),
            ('electrode_y', np.array([0., np.inf, 1., 2.]), 'finite'),
            ('trial_start', np.array([[1., 2.]]), 'one-dimensional'),
            ('electrode_layer', np.array([4, 6, 99, 6]), 'layer codes'),
            ('electrode_layer', np.array([4, 6, 0]), 'complete nonempty contact table'),
            ('trial_stop', np.array([1.0001]), 'one native pulse stop'),
        ]
        for key, value, message in cases:
            with self.subTest(key=key, message=message):
                arrays = copy.deepcopy(self.arrays)
                arrays[key] = value
                self.rejected(arrays, message)

    def test_unique_identity_and_exact_fields(self):
        for key in ('unit_id', 'electrode_id'):
            arrays = copy.deepcopy(self.arrays)
            arrays[key][1] = arrays[key][0]
            self.rejected(arrays, 'unique source')
        self.arrays['extra'] = np.array([1])
        self.rejected(self.arrays, 'exact primitive')

    def test_pulse_is_not_an_observation_window(self):
        # A 100-microsecond stop is earlier than the 50-ms analysis endpoint;
        # requiring trial_stop >= start + .05 would silently redefine exposure.
        result = self.new.normalized(self.row, self.arrays)
        self.assertEqual(int(result['counts'][0, 0, 99]), 1)
        self.arrays['trial_stop'][0] = 1.
        self.rejected(self.arrays, 'pulse stop must follow')

    def test_windows_and_source_trial_order_are_not_repaired(self):
        for starts in ([.01, 2.], [2., 1.], [1., 1.09]):
            arrays = copy.deepcopy(self.arrays)
            arrays['trial_start'] = np.array(starts)
            arrays['trial_stop'] = arrays['trial_start'] + .0001
            self.rejected(arrays, 'nonnegative nonoverlapping')

    def test_empty_spike_segments_units_and_trials_remain_explicit(self):
        arrays = copy.deepcopy(self.arrays)
        arrays['spike_times'] = np.array([], dtype=float)
        arrays['spike_end'] = np.array([0, 0, 0])
        self.assertFalse(self.new.normalized(self.row, arrays)['counts'].any())
        arrays.update({key: np.array([], dtype=int) for key in ('unit_id', 'unit_electrode', 'spike_end')})
        self.assertEqual(self.new.normalized(self.row, arrays)['counts'].shape, (2, 0, 100))
        arrays['trial_start'] = arrays['trial_stop'] = np.array([], dtype=float)
        self.assertEqual(self.new.normalized(self.row, arrays)['counts'].shape, (0, 0, 100))

    def test_count_memory_cap_before_allocation(self):
        with patch.object(self.new, 'MAX_COUNT_BYTES', 1):
            self.rejected(self.arrays, 'memory cap')
        # A valid uncapped input reaches count allocation, proving the spy
        # would still catch an allocation moved before the production cap.
        with self.assertRaisesRegex(AssertionError, 'count buffer allocated before validation'):
            self.rejected(self.arrays, 'memory cap')

    def npy_members(self, version=(1, 0)):
        members = {}
        for key, array in self.arrays.items():
            buffer = io.BytesIO()
            np.lib.format.write_array(buffer, array, version=version, allow_pickle=False)
            members[key + '.npy'] = buffer.getvalue()
        return members

    def load_generated_members(self, members, compression=zipfile.ZIP_STORED, forbid_load=False):
        with tempfile.TemporaryDirectory() as directory:
            packet = Path(directory)
            path = packet / 'invented.npz'
            with zipfile.ZipFile(path, 'w', compression=compression) as archive:
                for key, payload in members.items():
                    archive.writestr(key, payload)
            raw = path.read_bytes()
            manifest = {'recordings': [dict(self.row, file=path.name,
                        pin={'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})]}
            if forbid_load:
                with patch.object(np, 'load', side_effect=AssertionError('array load reached before preflight')):
                    return next(self.new.records(packet, manifest))
            return next(self.new.records(packet, manifest))

    def test_npy_declarations_preflight_before_any_array_load(self):
        def declared(shape=(2000000,), descr='<f8', version=(1, 0), payload=b''):
            header = (repr({'descr': descr, 'fortran_order': False, 'shape': shape}) + '\n').encode()
            width = 2 if version == (1, 0) else 4
            return b'\x93NUMPY' + bytes(version) + len(header).to_bytes(width, 'little') + header + payload
        cases = [
            ('oversized', declared(), 'declared payload'),
            ('short_payload', declared(shape=(4,)), 'declared payload'),
            ('trailing_payload', declared(shape=(0,), payload=b'extra'), 'declared payload'),
            ('multidimensional', declared(shape=(1, 1)), 'one-dimensional'),
            ('boolean_dimension', declared(shape=(True,)), 'one-dimensional'),
            ('negative_dimension', declared(shape=(-1,)), 'one-dimensional'),
            ('object_dtype', declared(shape=(0,), descr='|O'), 'nonobject numeric'),
            ('text_dtype', declared(shape=(0,), descr='<U4'), 'nonobject numeric'),
            ('unsupported_version', declared(version=(9, 0)), 'supported primitive NPY version'),
            ('oversized_header', b'\x93NUMPY\x01\x00' + (10001).to_bytes(2, 'little'), 'bounded primitive NPY header'),
        ]
        for label, malformed, message in cases:
            with self.subTest(label=label):
                members = self.npy_members()
                # Put the bad member last: even earlier valid members must not
                # reach np.load until every member has been preflighted.
                del members['unit_id.npy']
                members['unit_id.npy'] = malformed
                with self.assertRaisesRegex(ValueError, message):
                    self.load_generated_members(members, forbid_load=True)

    def test_compressed_npz_refused_before_array_load(self):
        with self.assertRaisesRegex(ValueError, 'uncompressed unencrypted'):
            self.load_generated_members(self.npy_members(), zipfile.ZIP_DEFLATED, forbid_load=True)

    def test_supported_npy_versions_preserve_values(self):
        expected = self.new.normalized(self.row, self.arrays)
        for version in ((1, 0), (2, 0), (3, 0)):
            with self.subTest(version=version):
                got = self.load_generated_members(self.npy_members(version))
                np.testing.assert_array_equal(got['counts'], expected['counts'])
                self.assertEqual(got['unit_electrode_id'], expected['unit_electrode_id'])
                self.assertEqual(got['electrodes'], expected['electrodes'])

    def test_real_npz_stream_and_full47_core_preserve_all_conditions(self):
        with tempfile.TemporaryDirectory() as directory:
            packet = Path(directory)
            members, roster = [], []
            for index in range(47):
                asset = 'invented-record-%02d' % index
                participant = 'invented-mouse-%02d' % (index if index < 41 else index - 41)
                area = 'A1' if index < 39 else 'A2'
                path = packet / (asset + '.npz')
                np.savez(path, **self.arrays)
                raw = path.read_bytes()
                members.append({'asset_id': asset, 'participant_id': participant, 'area': area,
                                'file': path.name, 'pin': {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}})
                roster.append({'recording_id': asset, 'participant_id': participant, 'area': area})
            manifest_path = packet / 'PREPARED.json'
            manifest_path.write_text(json.dumps({'status': 'complete', 'recordings': members}))
            manifest_pin = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
            manifest = self.new.load_manifest(manifest_path, manifest_pin)
            got = self.core.analyze(self.new.records(packet, manifest), roster)
            old = self.core.analyze(self.old.records(packet, manifest), roster)
            self.assertEqual(got, old)
            self.assertEqual(got['recordings'], 47)
            self.assertEqual(got['participants'], 41)
            self.assertEqual(got['source_area_recording_counts'], {'A1': 39, 'A2': 8})
            self.assertEqual(set(got['conditions']), set(self.core.CONDITIONS))
            with self.assertRaisesRegex(ValueError, 'manifest pin'):
                self.new.load_manifest(manifest_path, '0' * 64)
            wrong = copy.deepcopy(manifest)
            wrong['recordings'][0]['pin']['sha256'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'selected array identity'):
                next(self.new.records(packet, wrong))
            invalid = copy.deepcopy(self.arrays)
            invalid['unit_electrode'][0] = -1
            first_path = packet / members[0]['file']
            np.savez(first_path, **invalid)
            raw = first_path.read_bytes()
            # Authentic bytes are not sufficient for a scientifically usable
            # mapping: even a newly pinned malformed payload must be rejected.
            manifest['recordings'][0]['pin'] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
            with self.assertRaisesRegex(ValueError, 'contact-table row'):
                next(self.new.records(packet, manifest))


if __name__ == '__main__':
    unittest.main(verbosity=2)
