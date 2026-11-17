"""Generated schema controls: real NumPy, explicit external-constructor doubles.

No temporaldata/brainsets/HDF5 package, authentic array, training or model run.
The source differential executes only three pinned author AST function bodies.
The full-count iterator control uses an explicitly mocked metadata/custody seam.
"""
from __future__ import annotations

import ast
from copy import deepcopy
import datetime
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('_nuclr_bridge_control', HERE / 'bridge.py')
bridge = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = bridge
spec.loader.exec_module(bridge)


class DomainDouble:
    """Opaque invented endpoint convention; not temporaldata semantics."""
    def __init__(self, intervals):
        self.intervals = tuple(intervals)

    def __or__(self, other):
        return DomainDouble(self.intervals + other.intervals)


class RecordDouble:
    def __init__(self, kind, **values):
        self.kind = kind
        self.__dict__.update(values)

    def to_hdf5(self, handle, *, serialize_fn_map):
        handle['object'] = self
        handle['serializers'] = serialize_fn_map


class TraceDouble(RecordDouble):
    def __init__(self, **values):
        if values['domain'] == 'auto':
            times = values['timestamps']
            values['domain'] = DomainDouble(((float(times[0]), float(times[-1]) + 0.125),))
        super().__init__('IrregularTimeSeries', **values)

    def is_sorted(self):
        return bool(np.all(np.diff(self.timestamps) >= 0))


def runtime_double():
    calls = []
    def ctor(kind):
        def make(**values):
            calls.append((kind, values))
            return RecordDouble(kind, **values)
        return make
    def trace(**values):
        calls.append(('IrregularTimeSeries', dict(values)))
        return TraceDouble(**values)
    return SimpleNamespace(Data=ctor('Data'), ArrayDict=ctor('ArrayDict'),
                           IrregularTimeSeries=trace, BrainsetDescription=ctor('BrainsetDescription'),
                           SubjectDescription=ctor('SubjectDescription'),
                           SessionDescription=ctor('SessionDescription'),
                           Species=SimpleNamespace(UNKNOWN='GENERATED_SPECIES_UNKNOWN'),
                           serialize_fn_map={'generated': 'opaque'},
                           provenance={'role': 'generated_constructor_doubles'}, calls=calls)


def header(value):
    return {'shape': list(value.shape), 'dtype': value.dtype.str,
            'fortran_order': bool(value.flags.f_contiguous and not value.flags.c_contiguous),
            'header_bytes': 128, 'npy_version': [1, 0]}


def generated_session(sid='sb025_20191004', count=6, block_count=2, dtype='<f4', order='C'):
    labels = ['IN', 'EC', 'Pvalb-Pdlim5', 'Lamp5-Lhx1', 'Sst-Chodl', 'Vip-Crh']
    labels = [labels[i % len(labels)] for i in range(count)]
    neurons = [{'id': f'{sid}_u{i}', 'session_id': sid, 'source_neuron_index': i,
                'ttype': label, 'ei_class': label if label in ('IN', 'EC') else 'IN',
                'subclass': 'unknown' if label in ('IN', 'EC') else label.split('-')[0]}
               for i, label in enumerate(labels)]
    units = {'depth': np.arange(count, dtype=np.float32).reshape(-1, 1),
             'plane': np.arange(count, dtype=np.uint32),
             'rfCenter_Xvis': np.arange(count, dtype=np.float64),
             'rfCenter_Yvis': np.arange(count, dtype=np.float32).reshape(-1, 1),
             'stackPosCorrected': np.arange(count * 2, dtype=np.float64).reshape(count, 2)}
    units['depth'][0, 0] = np.nan
    units['rfCenter_Xvis'][-1] = np.inf
    units['rfCenter_Yvis'][0, 0] = -np.inf
    blocks, expected, source_arrays = [], [], {}
    rows = 0
    for i in range(block_count):
        frames = 7 if i % 2 == 0 else 5
        activity = np.array(np.arange(frames * count).reshape(frames, count) + 1 + 17 * i,
                            dtype=dtype, order=order)
        native_clock = np.arange(frames, dtype=np.float64) * 0.237 + 13.625
        clock = native_clock + i * 3600
        experiment = f'Blank/{i + 1}'
        blocks.append({'experiment_id': experiment, 'activity': activity,
                       'timestamps': clock, 'normalized': False})
        expected.append({'experiment_id': experiment, 'frames': frames,
                         'source_directory': f'SB025/2019-10-04/{experiment}',
                         'activity_header': header(activity), 'timestamp_header': header(native_clock),
                         'shifted_first_second': float(clock[0]), 'shifted_last_second': float(clock[-1]),
                         'source_offset_seconds': i * 3600, 'row_start': rows, 'row_stop': rows + frames})
        rows += frames
        source_arrays[experiment] = (activity, native_clock)
    raw = np.concatenate([b['activity'] for b in blocks], axis=0)
    denominator = np.percentile(raw.flatten(), 99.0)
    norm = {'method': 'numpy_percentile_flattened_session_99_default_linear',
            'percentile': float(denominator), 'percentile_scalar_dtype': np.asarray(denominator).dtype.str,
            'native_concatenated_dtype': raw.dtype.str, 'normalized_dtype': (raw / denominator).dtype.str}
    session = {'session_id': sid, 'neurons': count, 'frames': rows, 'experiments': expected,
               'normalization': norm, 'order_policy': 'generated_current_order_only',
               'neuron_headers': {name: header(value) for name, value in units.items()}}
    return session, neurons, blocks, units, source_arrays


class SourcePathDouble:
    entries = {}
    def __init__(self, value):
        self.value = str(value)
    def __str__(self):
        return self.value
    def __truediv__(self, value):
        return SourcePathDouble(self.value.rstrip('/') + '/' + str(value))
    def iterdir(self):
        return iter([SourcePathDouble(p) for p in self.entries[self.value]])
    def is_dir(self):
        return True
    def mkdir(self, **kwargs):
        if self.value != '/generated-output':
            raise AssertionError('unexpected source mkdir')


class NumpySourceDouble:
    """Only np.load is replaced; all numerical functions are actual NumPy."""
    def __init__(self, arrays):
        self.arrays = arrays
    def load(self, path):
        return np.array(self.arrays[str(path)], copy=True, order='K')
    def __getattr__(self, name):
        return getattr(np, name)


def original_prepare(session, neurons, units, source_arrays, runtime):
    path = HERE / 'reference' / 'prepare_data.py'
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != bridge.PREPARER_SHA256:
        raise AssertionError('pinned original preparer differs')
    tree = ast.parse(body)
    names = {'extract_neural_activity', 'extract_neurons', 'main'}
    selected = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    if {n.name for n in selected} != names:
        raise AssertionError('original source functions unavailable')
    subject, date = session['session_id'].split('_')
    date = date[:4] + '-' + date[4:6] + '-' + date[6:]
    session_dir = f'{subject.upper()}/{date}'
    base = '/generated-raw/' + session_dir
    source_experiments = [row['experiment_id'] for row in session['experiments']]
    stimuli = list(dict.fromkeys(x.split('/')[0] for x in source_experiments))
    SourcePathDouble.entries = {base: [base + '/' + x for x in stimuli]}
    for stimulus in stimuli:
        SourcePathDouble.entries[base + '/' + stimulus] = [base + '/' + x for x in source_experiments
                                                          if x.startswith(stimulus + '/')]
    arrays = {base + '/neuron.' + name + '.npy': value for name, value in units.items()}
    for experiment, (activity, times) in source_arrays.items():
        arrays[base + '/' + experiment + '/frame.neuralActivity.npy'] = activity
        arrays[base + '/' + experiment + '/frame.times.npy'] = times.reshape(-1, 1)
    args = SimpleNamespace(session_dir=session_dir, raw_dir=SourcePathDouble('/generated-raw'),
                           processed_dir=SourcePathDouble('/generated-output'))
    parser = SimpleNamespace(add_argument=lambda *a, **k: None, parse_args=lambda: args)
    captured = {}
    class FakeFile:
        def __init__(self, filename, mode):
            if str(filename) != f'/generated-output/{session["session_id"]}.h5' or mode != 'w':
                raise AssertionError('unexpected source HDF5 target')
        def __enter__(self):
            return captured
        def __exit__(self, *args):
            return False
    namespace = dict(vars(runtime))
    namespace.update(np=NumpySourceDouble(arrays), Path=SourcePathDouble, datetime=datetime,
                     argparse=SimpleNamespace(ArgumentParser=lambda: parser),
                     h5py=SimpleNamespace(File=FakeFile), print=lambda *a, **k: None,
                     read_txt_list=lambda _: [row['ttype'] for row in neurons])
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), 'exec'), namespace)
    namespace['main']()
    if captured['serializers'] is not runtime.serialize_fn_map:
        raise AssertionError('source serialization mapping differs')
    return captured['object']


def assert_tree_equal(case, actual, expected):
    if isinstance(expected, np.ndarray):
        case.assertEqual(actual.dtype, expected.dtype)
        np.testing.assert_array_equal(actual, expected)
    elif isinstance(expected, DomainDouble):
        case.assertEqual(actual.intervals, expected.intervals)
    elif isinstance(expected, RecordDouble):
        case.assertEqual(set(vars(actual)), set(vars(expected)))
        for key, value in vars(expected).items():
            assert_tree_equal(case, getattr(actual, key), value)
    else:
        case.assertEqual(actual, expected)


class SchemaControls(unittest.TestCase):
    def test_author_ast_full_session_differential(self):
        for dtype, order in [('<f4', 'C'), ('<f4', 'F'), ('<f8', 'F')]:
            with self.subTest(dtype=dtype, order=order):
                session, neurons, blocks, units, source = generated_session(dtype=dtype, order=order)
                original = original_prepare(session, neurons, units, source, runtime_double())
                result = bridge.assemble_session(session, neurons, blocks, units, runtime_double())
                assert_tree_equal(self, result, original)

    def test_complete_raw_normalized_and_gap_preserved(self):
        session, neurons, blocks, units, _ = generated_session()
        rt = runtime_double()
        data = bridge.assemble_session(session, neurons, blocks, units, rt)
        traces = data.calcium_traces
        self.assertEqual(traces.df_over_f.shape, (12, 6))
        self.assertFalse(np.shares_memory(traces.df_over_f, traces.df_over_f_norm))
        self.assertEqual(len(traces.domain.intervals), 2)
        self.assertEqual(traces.domain.intervals[0][1], float(blocks[0]['timestamps'][-1]) + 0.125)
        np.testing.assert_array_equal(traces.timestamps, np.concatenate([b['timestamps'] for b in blocks]))
        self.assertGreater(traces.timestamps[7] - traces.timestamps[6], 3500)
        trace_calls = [values for kind, values in rt.calls if kind == 'IrregularTimeSeries']
        self.assertEqual([v['domain'] for v in trace_calls[:2]], ['auto', 'auto'])
        self.assertIs(data.domain, traces.domain)
        self.assertNotIn('unique_id', vars(data.units))
        self.assertTrue(np.isnan(data.units.depth[0]))
        self.assertTrue(np.isposinf(data.units.rf_center_xvis[-1]))
        self.assertEqual(data.units.plane.dtype, np.dtype('<u4'))

    def test_column_order_and_label_refusals(self):
        for mutation in ('reorder', 'duplicate', 'label', 'count'):
            with self.subTest(mutation=mutation):
                s, n, b, u, _ = generated_session()
                if mutation == 'reorder': n.reverse()
                if mutation == 'duplicate': n[1]['id'] = n[0]['id']
                if mutation == 'label': n[2]['subclass'] = 'fabricated'
                if mutation == 'count': n.pop()
                with self.assertRaises(bridge.BridgeError):
                    bridge.assemble_session(s, n, b, u, runtime_double())

    def test_block_coverage_order_and_normalization_role_refusals(self):
        for mutation in ('drop', 'reverse', 'normalized', 'crop', 'frames'):
            with self.subTest(mutation=mutation):
                s, n, b, u, _ = generated_session()
                if mutation == 'drop': b.pop()
                if mutation == 'reverse': b.reverse()
                if mutation == 'normalized': b[0]['normalized'] = True
                if mutation == 'crop': b[0]['activity'] = b[0]['activity'][:-1]
                if mutation == 'frames': s['frames'] += 1
                with self.assertRaises(bridge.BridgeError):
                    bridge.assemble_session(s, n, b, u, runtime_double())

    def test_nonfinite_unsorted_and_shifted_clock_refusals(self):
        for mutation in ('activity_nan', 'clock_nan', 'unsorted', 'shift'):
            with self.subTest(mutation=mutation):
                s, n, b, u, _ = generated_session()
                if mutation == 'activity_nan': b[0]['activity'][0, 0] = np.nan
                if mutation == 'clock_nan': b[0]['timestamps'][2] = np.nan
                if mutation == 'unsorted': b[0]['timestamps'][2] = b[0]['timestamps'][1] - 1
                if mutation == 'shift': b[1]['timestamps'] = b[1]['timestamps'] + 1
                with self.assertRaises(bridge.BridgeError):
                    bridge.assemble_session(s, n, b, u, runtime_double())

    def test_native_metadata_extent_dtype_and_extra_input_refusals(self):
        for mutation in ('dtype', 'shape', 'extra', 'missing'):
            with self.subTest(mutation=mutation):
                s, n, b, u, _ = generated_session()
                if mutation == 'dtype': u['depth'] = u['depth'].astype(np.float64)
                if mutation == 'shape': u['plane'] = u['plane'][:-1]
                if mutation == 'extra': u['UniqueID'] = np.arange(6)
                if mutation == 'missing': del u['plane']
                with self.assertRaises(bridge.BridgeError):
                    bridge.assemble_session(s, n, b, u, runtime_double())

    def test_recorded_normalization_mismatch_refusals(self):
        for mutation in ('zero', 'nan', 'method', 'dtype', 'scalar'):
            with self.subTest(mutation=mutation):
                s, n, b, u, _ = generated_session()
                norm = s['normalization']
                if mutation == 'zero': norm['percentile'] = 0
                if mutation == 'nan': norm['percentile'] = float('nan')
                if mutation == 'method': norm['method'] = 'per_neuron'
                if mutation == 'dtype': norm['normalized_dtype'] = '<i4'
                if mutation == 'scalar': norm['percentile_scalar_dtype'] = '<i4'
                with self.assertRaises(bridge.BridgeError):
                    bridge.assemble_session(s, n, b, u, runtime_double())

    def test_real_constructor_sortedness_is_enforced(self):
        s, n, b, u, _ = generated_session()
        with patch.object(TraceDouble, 'is_sorted', return_value=False):
            with self.assertRaisesRegex(bridge.BridgeError, 'sortedness'):
                bridge.assemble_session(s, n, b, u, runtime_double())


class RuntimeControls(unittest.TestCase):
    @staticmethod
    def distribution(name, **override):
        direct = {'vcs_info': {'vcs': 'git', 'commit_id': bridge.VCS_DEPENDENCIES[name]}}
        direct.update(override)
        return SimpleNamespace(version='generated-version', read_text=lambda _: json.dumps(direct))

    def test_declared_vcs_provenance_is_explicitly_unqualified(self):
        result = bridge.required_runtime_provenance(self.distribution)
        self.assertEqual(set(result), {'temporaldata', 'brainsets'})
        self.assertTrue(all(row['loaded_source_tree_authenticated'] is False for row in result.values()))

    def test_missing_editable_wrong_and_malformed_dependency_refusals(self):
        def absent(_):
            raise importlib.metadata.PackageNotFoundError('generated-missing')
        factories = [absent,
                     lambda n: self.distribution(n, dir_info={'editable': True}),
                     lambda n: self.distribution(n, vcs_info={'vcs': 'git', 'commit_id': '0' * 40}),
                     lambda n: self.distribution(n, vcs_info=[]),
                     lambda n: self.distribution(n, dir_info=[]),
                     lambda n: SimpleNamespace(version='x', read_text=lambda _: 'not-json')]
        for factory in factories:
            with self.subTest(factory=factory):
                with self.assertRaises(bridge.BridgeError):
                    bridge.required_runtime_provenance(factory)

    def test_route_source_pin_precedes_any_execution(self):
        with patch.object(Path, 'read_bytes', return_value=b'raise AssertionError("must not execute")'):
            with self.assertRaisesRegex(bridge.BridgeError, 'route source differs'):
                bridge.load_route()
        route = bridge.load_route()
        self.assertEqual(route.ROUTE_ID, 'multi_split_resample_transductive_v1')


class IteratorControls(unittest.TestCase):
    """Full-count generated metadata, not actual accepted input custody."""
    def make_boundary(self):
        sessions, neurons, assets, payloads, definitions, block_data = {}, {}, {}, {}, {}, {}
        for i in range(17):
            sid = f'sb025_201910{i + 1:02d}'
            count = 601 if i == 16 else 597
            s, n, b, u, _ = generated_session(sid, count=count, block_count=5 if i == 16 else 4)
            sessions[sid] = s
            neurons.update({r['id']: r for r in n})
            directory = f'GENERATED/{sid}'
            definitions[sid] = {'source_directory': directory}
            block_data.update({(sid, r['experiment_id']): r for r in b})
            for name, values in u.items():
                member = directory + '/neuron.' + name + '.npy'
                assets[member] = {'source_member': member, 'relative_path': 'native/' + member,
                                  'sha256': hashlib.sha256(member.encode()).hexdigest()}
                payloads[str(Path('/GENERATED-NO-FILES') / assets[member]['relative_path'])] = (member, values, s['neuron_headers'][name])
        reads, opened, checked = [], [], []
        def read_block(sid, experiment, start, stop, *, normalized):
            self.assertIs(normalized, False)
            original = block_data[sid, experiment]
            self.assertEqual((start, stop), (0, original['activity'].shape[0]))
            reads.append((sid, experiment))
            return {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in original.items()}
        class NativeArrayDouble:
            def __init__(self, path, *, sha256):
                self.path = str(path)
                member, self.values, self.header = payloads[self.path]
                if sha256 != assets[member]['sha256']:
                    raise AssertionError('asset digest not forwarded')
                opened.append(member)
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def check(self): checked.append(self.path)
        inputs = SimpleNamespace(sessions=sessions, neurons=neurons, assets=assets,
                                 manifest={'sessions': list(sessions.values())},
                                 root=Path('/GENERATED-NO-FILES'), read_block=read_block)
        native = SimpleNamespace(profile=lambda: {'sessions': definitions}, NativeArray=NativeArrayDouble)
        binding = SimpleNamespace(binding_role='accepted_owner_input_metadata', _inputs=inputs, _native=native,
                                  canonical_manifest_sha256='a' * 64, independent_acceptance_sha256='b' * 64)
        selection = SimpleNamespace(_binding=binding, receipt={'label_level': 'subclass', 'panel': 'transductive'},
                                    receipt_sha256='c' * 64,
                                    _selected_projection={'label_map': {f'generated-label-{i}': 0 for i in range(1500)}})
        check_calls = []
        def check_selection(value):
            if value is not selection:
                raise AssertionError('selection delegation missing')
            check_calls.append(value)
        route = SimpleNamespace(_check_selection=check_selection)
        return selection, route, reads, opened, checked, check_calls

    def test_all_sessions_neurons_blocks_and_source_checks_complete(self):
        selection, route, reads, opened, checked, checks = self.make_boundary()
        rows = list(bridge.iter_accepted_sessions(selection, route, runtime_double()))
        self.assertEqual(len(checks), 1)
        self.assertEqual(len(rows), 17)
        self.assertEqual(len(reads), 69)
        self.assertEqual(len(set(reads)), 69)
        self.assertEqual(len(opened), 85)
        self.assertEqual(len(checked), 85)
        self.assertEqual(sum(len(row.data.units.id) for row in rows), 10153)
        self.assertEqual(sum(row.provenance['blocks'] for row in rows), 69)
        self.assertTrue(all(row.provenance['contains_owner_only_transcriptomic_labels'] for row in rows))
        for row in rows:
            for flag in ('loaded_runtime_qualified', 'hdf5_serialized', 'historical_reference_reproduced', 'scientific_qualification'):
                self.assertIs(row.provenance[flag], False)
            self.assertEqual(row.provenance['selection_receipt_sha256'], 'c' * 64)
            self.assertEqual(row.provenance['input_manifest_sha256'], 'a' * 64)

    def test_wrong_panel_label_role_and_population_refuse_before_array_reads(self):
        for mutation in ('panel', 'label', 'role', 'label_count', 'sessions', 'neurons', 'blocks'):
            with self.subTest(mutation=mutation):
                selection, route, reads, opened, _, _ = self.make_boundary()
                inputs = selection._binding._inputs
                if mutation == 'panel': selection.receipt['panel'] = 'inductive_zero_shot'
                if mutation == 'label': selection.receipt['label_level'] = 'ei'
                if mutation == 'role': selection._binding.binding_role = 'generated_control_metadata'
                if mutation == 'label_count': selection._selected_projection['label_map'].popitem()
                if mutation == 'sessions': inputs.sessions.popitem()
                if mutation == 'neurons': inputs.neurons.popitem()
                if mutation == 'blocks': next(iter(inputs.sessions.values()))['experiments'].pop()
                with self.assertRaises(bridge.BridgeError):
                    list(bridge.iter_accepted_sessions(selection, route, runtime_double()))
                self.assertFalse(reads)
                self.assertFalse(opened)

    def test_changed_metadata_member_path_or_header_refused(self):
        for mutation in ('path', 'header'):
            with self.subTest(mutation=mutation):
                selection, route, _, _, _, _ = self.make_boundary()
                inputs = selection._binding._inputs
                if mutation == 'path':
                    next(iter(inputs.assets.values()))['relative_path'] = 'native/wrong.npy'
                else:
                    first = inputs.manifest['sessions'][0]
                    first['neuron_headers']['depth'] = dict(first['neuron_headers']['depth'], dtype='<f8')
                with self.assertRaises(bridge.BridgeError):
                    next(bridge.iter_accepted_sessions(selection, route, runtime_double()))


if __name__ == '__main__':
    unittest.main(verbosity=2)
