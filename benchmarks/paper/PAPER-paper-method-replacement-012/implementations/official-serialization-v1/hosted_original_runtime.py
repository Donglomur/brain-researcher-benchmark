"""Four generated controls requiring the genuine pinned original runtime.

Source-only draft: not executed locally. No skips, constructor doubles, neural
payloads, model calls or installer. Missing/incompatible runtime is a class error.
The owner must seal the sibling serializer and admit the finite control run first.
"""
from __future__ import annotations

from contextlib import ExitStack
import hashlib
import importlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
import uuid

HERE = Path(__file__).resolve().parent
BRIDGE_SHA256 = 'e6548b3ef63c007056899407ac81159731d2265e19af4b6f490a6f5d96ecd4f7'
BRAINSET = 'bugeon_transcriptomic_2022'
MIB = 1048576
VCS = {
    'temporaldata': 'b0a92bf4f9e36e27c5eddbf02c8acbd5df90ee39',
    'brainsets': '61c8a7bc4fb39412a4d2f12c6209936606d4c12f',
    'torch-brain': 'd48b0c822fbcaa27e15ba982bd6f619ed4260cd7',
}
# These nine complete files were recovered against immutable, complete Git trees;
# each body also passed expected size and Git blob SHA1 at intake.
SOURCE_FILES = {
    'temporaldata.irregular_ts': ('temporaldata', 'temporaldata/irregular_ts.py', '1ea8f95435a7be06a974326e6176e9dd6bc3d975ebd0471369e09d2556873adc'),
    'temporaldata.interval': ('temporaldata', 'temporaldata/interval.py', 'ec73166b641854246f4b6d91ca44d7f148f3cec41a7a1372473b57c8d1281d6f'),
    'temporaldata.data': ('temporaldata', 'temporaldata/data.py', '885bf4cb0209394c4dda04338639890f1ada0435e3cc192ff01f379350eac722'),
    'temporaldata.arraydict': ('temporaldata', 'temporaldata/arraydict.py', '68ba560eaefdaf2d2614395f3b9b19660ba35fcf266d5715fcb0bafb211d46e9'),
    'brainsets.core': ('brainsets', 'brainsets/core.py', 'a3f2ccba9b45b1682d0c8a7c60027e8c29b3a96c5b93948021208f0f80b819e0'),
    'brainsets.descriptions': ('brainsets', 'brainsets/descriptions.py', '8ccd98da7cd05ff6be54b0211f5e1c231092d6ef4a254455f1d28bb74c8bd948'),
    'brainsets.taxonomy.subject': ('brainsets', 'brainsets/taxonomy/subject.py', '309f16283c77e8c1e973ef1311610a5323d75677dd5de9be757976da9b2e5adf'),
    'torch_brain.data.dataset': ('torch-brain', 'torch_brain/data/dataset.py', '25350b4b3f54c2729449c65ab3d7d88e8d302250e23e2d8c8e92e5a2024a3532'),
    'torch_brain.data.sampler': ('torch-brain', 'torch_brain/data/sampler.py', '0a21d992b18d223253697451b50687cee2e63c7cbc28bb0b6920d8a96701e0f3'),
}


def _load_local(path, expected_sha256=None):
    body = path.read_bytes()
    if expected_sha256 and hashlib.sha256(body).hexdigest() != expected_sha256:
        raise RuntimeError('Required frozen local source differs: ' + path.name)
    name = '_nuclr_genuine_control_' + uuid.uuid4().hex
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        # Execute exactly the bytes authenticated above, avoiding a second read.
        exec(compile(body, str(path), 'exec'), module.__dict__)
    except BaseException:
        del sys.modules[name]
        raise
    return module


def _real_runtime(bridge):
    """Fail closed on absent/mismatched originals; no install, skip or fallback."""
    try:
        distributions = {}
        for name, revision in VCS.items():
            dist = importlib.metadata.distribution(name)
            provenance = json.loads(dist.read_text('direct_url.json') or 'null')
            if (not isinstance(provenance, dict)
                    or provenance.get('vcs_info', {}).get('vcs') != 'git'
                    or provenance.get('vcs_info', {}).get('commit_id') != revision
                    or provenance.get('dir_info', {}).get('editable') is True):
                raise RuntimeError('Required original VCS declaration differs: ' + name)
            distributions[name] = dist
        paths = {}
        for module_name, (dist_name, relative, expected) in SOURCE_FILES.items():
            path = Path(distributions[dist_name].locate_file(relative)).resolve(strict=True)
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise RuntimeError('Required recovered source bytes differ: ' + module_name)
            paths[module_name] = path
        if importlib.metadata.version('numpy') != '1.23.5':
            raise RuntimeError('Original NumPy 1.23.5 is required')
        if importlib.metadata.version('torch').split('+')[0] != '2.8.0':
            raise RuntimeError('Original Torch 2.8.0 is required')
        runtime = bridge.load_source_runtime()
        runtime.np = importlib.import_module('numpy')
        runtime.h5py = importlib.import_module('h5py')
        runtime.omegaconf = importlib.import_module('omegaconf')
        runtime.Interval = importlib.import_module('temporaldata').Interval
        runtime.Dataset = importlib.import_module('torch_brain.data.dataset').Dataset
        runtime.SequentialFixedWindowSampler = importlib.import_module('torch_brain.data.sampler').SequentialFixedWindowSampler
        for module_name, (_, _, expected) in SOURCE_FILES.items():
            module = importlib.import_module(module_name)
            loaded_path = Path(module.__file__).resolve(strict=True)
            if loaded_path != paths[module_name] or hashlib.sha256(loaded_path.read_bytes()).hexdigest() != expected:
                raise RuntimeError('Loaded module shadows recovered source: ' + module_name)
        return runtime
    except Exception as exc:
        raise RuntimeError(
            'Genuine pinned NuCLR runtime unavailable or incompatible; no controls '
            'may be counted as passed or skipped. Provision/qualify the runtime '
            'separately; this test never installs dependencies. Cause: ' + str(exc)
        ) from exc


def _header(value):
    return {'shape': list(value.shape), 'dtype': value.dtype.str}


def _fixture(bridge, runtime, session_id, spans):
    """Generated arithmetic only: four units; explicit complete synthetic blocks."""
    np = runtime.np
    labels = ['Pvalb-Pdlim5', 'Sst-Chodl', 'Vip-Crh', 'Lamp5-Lhx1']
    neurons = [dict(id=f'{session_id}_u{i}', session_id=session_id,
                    source_neuron_index=i, ttype=label, ei_class='IN',
                    subclass=label.split('-')[0]) for i, label in enumerate(labels)]
    units = {
        'depth': np.arange(4, dtype=np.float32).reshape(4, 1),
        'plane': np.arange(4, dtype=np.uint32),
        'rfCenter_Xvis': np.arange(4, dtype=np.float64),
        'rfCenter_Yvis': np.arange(4, dtype=np.float32).reshape(4, 1),
        'stackPosCorrected': np.arange(8, dtype=np.float64).reshape(4, 2),
    }
    # Source metadata permits NaN; the bridge must not drop or sanitize the unit.
    units['depth'][1, 0] = np.nan
    blocks, experiments = [], []
    for i, (start, end) in enumerate(spans):
        clock = np.arange(start, end + 1, dtype=np.float64)
        raw = (np.arange(clock.size * 4, dtype=np.float32).reshape(-1, 4) + 1 + 1000 * i)
        experiment_id = f'Generated/{i + 1}'
        blocks.append(dict(experiment_id=experiment_id, activity=raw,
                           timestamps=clock, normalized=False))
        experiments.append(dict(experiment_id=experiment_id, frames=clock.size,
                                activity_header=_header(raw), timestamp_header=_header(clock),
                                shifted_first_second=float(clock[0]), shifted_last_second=float(clock[-1])))
    raw = np.concatenate([block['activity'] for block in blocks], axis=0)
    denominator = np.percentile(raw.flatten(), 99.0)
    normalized = raw / denominator
    session = {
        'session_id': session_id, 'neurons': 4, 'frames': raw.shape[0],
        'experiments': experiments,
        'neuron_headers': {name: _header(value) for name, value in units.items()},
        'normalization': {
            'method': 'numpy_percentile_flattened_session_99_default_linear',
            'percentile': float(denominator),
            'percentile_scalar_dtype': np.asarray(denominator).dtype.str,
            'native_concatenated_dtype': raw.dtype.str,
            'normalized_dtype': normalized.dtype.str,
        },
    }
    data = bridge.assemble_session(session, neurons, blocks, units, runtime)
    return data, raw, normalized, np.concatenate([block['timestamps'] for block in blocks])


class OriginalRuntimeControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bridge = _load_local(HERE.parent / 'temporaldata-bridge-v1' / 'bridge.py', BRIDGE_SHA256)
        cls.runtime = _real_runtime(cls.bridge)
        # Parent seals this new component before any admitted run. Deliberately no
        # premature hard-coded hash while serializer source remains under review.
        cls.serializer = _load_local(HERE / 'serializer.py')
        cls.tmp = tempfile.TemporaryDirectory(prefix='nuclr-generated-real-runtime-')
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.root = Path(cls.tmp.name)
        cls.directory = cls.root / BRAINSET
        cls.directory.mkdir()
        # Creation order differs from expected source Dataset discovery order.
        cls.specifications = [('sb002_20200102', [(0, 40)]),
                              ('sb001_20200101', [(0, 65), (3600, 3612)])]
        cls.fixture = {}
        cls.budget = cls.serializer.WriteBudget(MIB)
        cls.bounded_extent = None
        cls.direct_extent = None
        for index, (sid, spans) in enumerate(cls.specifications):
            data, raw, normalized, timestamps = _fixture(cls.bridge, cls.runtime, sid, spans)
            cls.fixture[sid] = (data, raw, normalized, timestamps)
            path = cls.directory / (sid + '.h5')
            if index == 0:
                with path.open('x+b', buffering=0) as raw_file:
                    bounded = cls.serializer.BoundedFile(raw_file, cls.budget)
                    try:
                        with cls.runtime.h5py.File(bounded, 'w', driver='fileobj') as file:
                            data.to_hdf5(file, serialize_fn_map=cls.runtime.serialize_fn_map)
                        bounded.flush()
                    finally:
                        bounded.close()
                cls.bounded_extent = path.stat().st_size
            else:
                # Genuine ordinary HDF5 driver reference. This final-size check
                # does not measure cumulative logical writes for that driver.
                with cls.runtime.h5py.File(path, 'x') as file:
                    data.to_hdf5(file, serialize_fn_map=cls.runtime.serialize_fn_map)
                cls.direct_extent = path.stat().st_size
            if not 0 < path.stat().st_size <= MIB:
                raise RuntimeError('Generated HDF5 fixture exceeds proposed extent envelope')

    def _open_pair(self, stack, sid):
        path = self.directory / (sid + '.h5')
        eager_file = stack.enter_context(self.runtime.h5py.File(path, 'r'))
        lazy_file = stack.enter_context(self.runtime.h5py.File(path, 'r'))
        return (self.runtime.Data.from_hdf5(eager_file, lazy=False),
                self.runtime.Data.from_hdf5(lazy_file, lazy=True), eager_file)

    def test_real_hdf5_roundtrip_and_description_defaults(self):
        np = self.runtime.np
        for sid, (source, raw, normalized, timestamps) in self.fixture.items():
            with self.subTest(session=sid), ExitStack() as stack:
                eager, lazy, handle = self._open_pair(stack, sid)
                for loaded in (eager, lazy):
                    self.assertIs(type(loaded.brainset), self.runtime.Data)
                    self.assertIs(type(loaded.subject), self.runtime.Data)
                    self.assertIs(type(loaded.session), self.runtime.Data)
                    self.assertEqual(loaded.subject.species, 'UNKNOWN')
                    self.assertEqual(loaded.subject.sex, 'UNKNOWN')
                    self.assertEqual(loaded.subject.age, 0.0)
                    self.assertEqual(loaded.subject.genotype, 'unknown')
                    self.assertFalse(hasattr(loaded.subject, 'cre_line'))
                    self.assertFalse(hasattr(loaded.session, 'task'))
                    self.assertEqual(loaded.session.recording_date, str(source.session.recording_date))
                    self.assertEqual(loaded.brainset.brainsets_version, source.brainset.brainsets_version)
                    self.assertEqual(loaded.brainset.temporaldata_version, source.brainset.temporaldata_version)
                    for key in source.units.keys():
                        actual_unit, expected_unit = getattr(loaded.units, key), getattr(source.units, key)
                        self.assertEqual(actual_unit.dtype, expected_unit.dtype)
                        np.testing.assert_array_equal(actual_unit, expected_unit)
                    self.assertTrue(np.isnan(loaded.units.depth[1]))
                    self.assertEqual(loaded.calcium_traces.timestamps.dtype, timestamps.dtype)
                    self.assertEqual(loaded.calcium_traces.df_over_f.dtype, raw.dtype)
                    self.assertEqual(loaded.calcium_traces.df_over_f_norm.dtype, normalized.dtype)
                    np.testing.assert_array_equal(loaded.calcium_traces.timestamps, timestamps)
                    np.testing.assert_array_equal(loaded.calcium_traces.df_over_f, raw)
                    np.testing.assert_array_equal(loaded.calcium_traces.df_over_f_norm, normalized)
                    np.testing.assert_array_equal(loaded.domain.start, source.domain.start)
                    np.testing.assert_array_equal(loaded.domain.end, source.domain.end)
                self.assertEqual(handle.attrs['object'], 'Data')
                self.assertEqual(handle['calcium_traces'].attrs['object'], 'IrregularTimeSeries')
                self.assertEqual(handle['calcium_traces']['timestamps'].shape[0], len(timestamps))
                self.assertEqual(handle['calcium_traces']['timestamps'][-1], timestamps[-1])
                expected_grid = np.arange(source.domain.start[0], source.domain.end[-1] + 1.0, 1.0, dtype=np.float64)
                np.testing.assert_array_equal(handle['calcium_traces']['timestamp_indices_1s'][:],
                                              np.searchsorted(timestamps, expected_grid))
                self.assertIn('id', handle['units'].attrs['_unicode_keys'].astype(str).tolist())
                self.assertEqual(handle['calcium_traces'].attrs['timekeys'].astype(str).tolist(), ['timestamps'])
        accounting = self.budget.receipt()
        self.assertGreater(accounting['logical_write_bytes_reserved'], 0)
        self.assertLessEqual(accounting['logical_write_bytes_reserved'], MIB)
        self.assertGreaterEqual(accounting['extent_bytes_reserved'], self.bounded_extent)
        self.assertLessEqual(accounting['extent_bytes_reserved'], MIB)
        self.assertFalse(accounting['physical_allocation_or_wire_bytes'])
        self.assertLessEqual(self.direct_extent, MIB)

    def test_gap_union_lazy_half_open_end_and_origin_reset(self):
        np = self.runtime.np
        sid = 'sb001_20200101'
        source, raw, normalized, timestamps = self.fixture[sid]
        np.testing.assert_array_equal(source.domain.start, [0.0, 3600.0])
        np.testing.assert_array_equal(source.domain.end, [65.0, 3612.0])
        touching = self.runtime.Interval(0.0, 1.0) | self.runtime.Interval(1.0, 2.0)
        np.testing.assert_array_equal(touching.start, [0.0])
        np.testing.assert_array_equal(touching.end, [2.0])
        duplicate_clock = np.array([0.0, 1.0, 1.0, 2.0, 2.0], dtype=np.float64)
        duplicate_values = np.arange(10, dtype=np.float32).reshape(5, 2)
        duplicate_trace = self.runtime.IrregularTimeSeries(
            timestamps=duplicate_clock, df_over_f=duplicate_values, domain='auto')
        self.assertEqual(duplicate_trace.domain.end[0], 2.0)
        np.testing.assert_array_equal(duplicate_trace.timestamps[-2:], [2.0, 2.0])
        middle = duplicate_trace.slice(1.0, 2.0)
        self.assertEqual(middle.timestamps.dtype, duplicate_clock.dtype)
        self.assertEqual(middle.df_over_f.dtype, duplicate_values.dtype)
        np.testing.assert_array_equal(middle.timestamps, [0.0, 0.0])
        np.testing.assert_array_equal(middle.df_over_f, duplicate_values[1:3])
        left = duplicate_trace.slice(0.0, 1.0)
        np.testing.assert_array_equal(left.timestamps, [0.0])
        np.testing.assert_array_equal(left.df_over_f, duplicate_values[:1])
        for start, end in [(30.0, 65.0), (3600.0, 3612.0), (65.0, 3600.0)]:
            with self.subTest(start=start, end=end), ExitStack() as stack:
                eager, lazy, _ = self._open_pair(stack, sid)
                expected = (timestamps >= start) & (timestamps < end)
                for loaded in (eager, lazy):
                    sample = loaded.slice(start, end)
                    self.assertEqual(sample.calcium_traces.timestamps.dtype, timestamps.dtype)
                    self.assertEqual(sample.calcium_traces.df_over_f.dtype, raw.dtype)
                    self.assertEqual(sample.calcium_traces.df_over_f_norm.dtype, normalized.dtype)
                    np.testing.assert_array_equal(sample.calcium_traces.timestamps, timestamps[expected] - start)
                    np.testing.assert_array_equal(sample.calcium_traces.df_over_f, raw[expected])
                    np.testing.assert_array_equal(sample.calcium_traces.df_over_f_norm, normalized[expected])
                    self.assertEqual(sample._absolute_start, start)
                    self.assertNotIn(end - start, sample.calcium_traces.timestamps)
                    # A domain gap can contain its left endpoint array row: actual
                    # source slicing selects rows by time, independent of domain.
                np.testing.assert_array_equal(eager.calcium_traces.timestamps, timestamps)
        self.assertEqual(timestamps[-1], 3612.0)

    def test_original_dataset_layout_ids_and_sequential_tail(self):
        np = self.runtime.np
        config = self.runtime.omegaconf.OmegaConf.create([
            {'selection': [{'brainset': BRAINSET}], 'config': {}}
        ])
        dataset = self.runtime.Dataset(str(self.root), config=config, split=None,
                                       unit_id_prefix_fn=lambda _: '')
        try:
            expected_recordings = [BRAINSET + '/sb001_20200101', BRAINSET + '/sb002_20200102']
            self.assertEqual(list(dataset.recording_dict), expected_recordings)
            self.assertEqual(dataset.get_session_ids(), expected_recordings)
            expected_units = [f'{sid}_u{i}' for sid in ['sb001_20200101', 'sb002_20200102'] for i in range(4)]
            self.assertEqual(dataset.get_unit_ids(), expected_units)
            intervals = dataset.get_sampling_intervals()
            np.testing.assert_array_equal(intervals[expected_recordings[0]].start, [0.0, 3600.0])
            np.testing.assert_array_equal(intervals[expected_recordings[0]].end, [65.0, 3612.0])
            sample = dataset.get(expected_recordings[0], 30.0, 60.0)
            self.assertEqual(sample.session.id, expected_recordings[0])
            self.assertEqual(sample.subject.id, BRAINSET + '/SB001')
            self.assertEqual(sample.units.id.tolist(), expected_units[:4])
            np.testing.assert_array_equal(sample.calcium_traces.timestamps, np.arange(30, dtype=np.float64))
            sampler = self.runtime.SequentialFixedWindowSampler(
                sampling_intervals=intervals, window_length=30.0, step=None, drop_short=True)
            actual = [(index.recording_id, index.start, index.end) for index in sampler]
            self.assertEqual(actual, [
                (expected_recordings[0], 0.0, 30.0), (expected_recordings[0], 30.0, 60.0),
                (expected_recordings[0], 35.0, 65.0), (expected_recordings[1], 0.0, 30.0),
                (expected_recordings[1], 10.0, 40.0),
            ])
            self.assertEqual(len(sampler), 5)
        finally:
            dataset._close_open_files()

    def test_real_raw_column_assignment_leaves_normalized_input_unchanged(self):
        np = self.runtime.np
        with ExitStack() as stack:
            _, lazy, _ = self._open_pair(stack, 'sb002_20200102')
            sample = lazy.slice(0.0, 30.0)
            expected_normalized = sample.calcium_traces.df_over_f_norm.copy()
            expected_ids = sample.units.id.copy()
            sample.calcium_traces.df_over_f = sample.calcium_traces.df_over_f[:, [0, 2]]
            self.assertEqual(sample.calcium_traces.df_over_f.shape, (30, 2))
            self.assertEqual(sample.calcium_traces.df_over_f_norm.shape, (30, 4))
            np.testing.assert_array_equal(sample.calcium_traces.df_over_f_norm, expected_normalized)
            np.testing.assert_array_equal(sample.units.id, expected_ids)


if __name__ == '__main__':
    unittest.main(verbosity=2)
