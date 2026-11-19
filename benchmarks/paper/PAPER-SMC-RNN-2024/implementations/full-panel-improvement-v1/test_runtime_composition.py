"""Source/metadata composition controls: no children, containers or original data."""
from pathlib import Path
import hashlib
import importlib.util
import json
import stat
import tempfile
import types
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent

def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

E = load('_test_full_panel_episode', 'full_panel_episode.py')
O = load('_test_full_panel_overlay', 'owner_overlay.py')

def need(value, message):
    if not value:
        raise ValueError(message)

def raw(value):
    return (json.dumps(value, sort_keys=True) + '\n').encode()

def pin(value):
    return {'bytes': len(value), 'sha256': hashlib.sha256(value).hexdigest()}

def read(path, expected=None):
    value = Path(path).read_bytes()
    if expected is not None:
        need(pin(value)['sha256'] == expected, 'changed metadata')
    return json.loads(value)


class RuntimeCompositionControls(unittest.TestCase):
    def test_foreign_continuous_code_rejected_before_load(self):
        retained = types.SimpleNamespace(source_identity=lambda: None)
        names = ('need', 'path', 'body', 'read', 'publish', 'relative', 'descriptor', 'checked',
                 'encoded', 'request_bytes', 'pin', 'decode', 'file_mount', 'mount_identity',
                 'validate_closed', 'observe_closed', 'provider_class')
        for name in names:
            setattr(retained, name, mock.Mock())
        retained.need = need
        retained.read = lambda _: {'schema': 'smc_full_panel_runtime_dependencies_v1',
            'retained_episode': E.EPISODE_PIN, 'retained_episode_source': E.EPISODE_SOURCE_PIN,
            'benchmark': {'bytes': 1, 'sha256': '0' * 64}, 'task': E.TASK_PIN, 'policy': E.POLICY_PIN}
        with mock.patch.object(E, '_read_source', return_value=b''), \
             mock.patch.object(E, '_module', return_value=retained) as loader:
            with self.assertRaisesRegex(ValueError, 'dependencies'):
                E.FullPanelEpisode('/operator-repo', '/operator-component')
            self.assertEqual(loader.call_count, 1)  # Only the independently pinned retained module.

    def test_source_extent_and_hash_refuse_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'source.py'
            p.write_bytes(b'raise AssertionError("must not execute")\n')
            with self.assertRaises(ValueError):
                E._module('_forbidden_extent', p, {'bytes': 1, 'sha256': '0' * 64})
            with self.assertRaises(ValueError):
                E._module('_forbidden_hash', p, {'bytes': p.stat().st_size, 'sha256': '0' * 64})
            alias = Path(directory) / 'alias.py'
            alias.symlink_to(p)
            with self.assertRaises(ValueError):
                E._read_source(alias, pin(p.read_bytes()))

    def test_overlay_dotdot_output_refuses_before_any_source_read(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = root / 'repository'
            sibling = root / 'sibling'
            repository.mkdir(); sibling.mkdir()
            alias = sibling / '..' / 'repository' / 'unsafe-overlay'
            with mock.patch.object(O, 'ADAPTER_PIN', {'bytes': 1, 'sha256': '0' * 64}), \
                 mock.patch.object(O, 'FACADE_PIN', {'bytes': 1, 'sha256': '1' * 64}), \
                 mock.patch.object(O, 'source', side_effect=AssertionError('no source read')):
                with self.assertRaisesRegex(ValueError, 'Canonical'):
                    O.build_overlay(repository, alias, max_bytes=1000)
            self.assertFalse((repository / 'unsafe-overlay').exists())

    def test_overlay_refuses_symlink_and_oversize_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'source.json'
            p.write_bytes(b'{}')
            alias = Path(directory) / 'alias.json'; alias.symlink_to(p)
            with self.assertRaises(ValueError):
                O.source(alias, None)
            oversize = types.SimpleNamespace(st_mode=stat.S_IFREG | 0o644, st_nlink=1, st_size=1024**2 + 1)
            with mock.patch.object(O.os, 'fstat', return_value=oversize):
                with self.assertRaises(ValueError):
                    O.source(p, None)

    def episode(self, directory):
        L = E.FullPanelEpisode.__new__(E.FullPanelEpisode)
        L.need, L.path, L.pin, L.read = need, Path, pin, read
        L.body = lambda path, *unused: Path(path).read_bytes()
        L._protocol_path = Path(directory) / 'PROTOCOL.json'
        L._protocol = {'programs': {}, 'pair_path': '/operator/pair_manifest.json', 'task_path': '/operator/task.json'}
        L._captured_actual = {}
        L.api = types.SimpleNamespace(hash_file=lambda path, cap: pin(Path(path).read_bytes())['sha256'])
        return L

    def capture(self, directory):
        root = Path(directory)
        L = self.episode(root)
        programme = {'program': {'bytes': 4, 'sha256': 'a' * 64},
                     'declaration': {'bytes': 4, 'sha256': 'b' * 64},
                     'method': {'path': '/operator/method.json', 'sha256': 'c' * 64}}
        result = {'schema': 'smc_full_panel_program_result_v1', 'inference_condition_id': E.INFERENCE_CONDITION,
                  'outcome': 'improvement', 'condition': E.CONDITIONS[0],
                  'program_sha256': 'a' * 64, 'declaration_sha256': 'b' * 64,
                  'method_freeze_sha256': 'c' * 64, 'submission_keys': ['offline']}
        bodies = {'offline.h5': b'generated-byte-only-capture-fixture', 'actual_declaration.json': raw({'post_run': True}),
                  'RESULT.json': raw(result), 'OUTPUTS.json': raw({})}
        for name, value in bodies.items():
            (root / name).write_bytes(value)
        receipt = {'quarantine_root': str(root), 'output_inventory': {
            'complete': True, 'files': {name: pin(value) for name, value in bodies.items()}}}
        return L, programme, receipt

    def test_closed_capture_retains_separate_actual_declaration(self):
        with tempfile.TemporaryDirectory() as directory:
            L, programme, receipt = self.capture(directory)
            predictions = L.captured_predictions(receipt, E.CONDITIONS[0], 'improvement', programme)
            self.assertEqual(predictions, {'offline': Path(directory) / 'offline.h5'})
            self.assertEqual(L._captured_actual[E.CONDITIONS[0]]['path'], str(Path(directory) / 'actual_declaration.json'))

    def test_capture_rejects_missing_actual_or_changed_method(self):
        with tempfile.TemporaryDirectory() as directory:
            L, programme, receipt = self.capture(directory)
            del receipt['output_inventory']['files']['actual_declaration.json']
            with self.assertRaises(ValueError):
                L.captured_predictions(receipt, E.CONDITIONS[0], 'improvement', programme)
            self.assertEqual(L._captured_actual, {})
        with tempfile.TemporaryDirectory() as directory:
            L, programme, receipt = self.capture(directory)
            programme['method']['sha256'] = 'd' * 64
            with self.assertRaises(ValueError):
                L.captured_predictions(receipt, E.CONDITIONS[0], 'improvement', programme)
            self.assertEqual(L._captured_actual, {})

    def test_freeze_uses_closed_actual_not_pre_run_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            L, programme, receipt = self.capture(directory)
            condition = E.CONDITIONS[0]
            folder = Path(directory) / condition; folder.mkdir()
            plan = folder / 'declaration.json'; plan.write_bytes(raw({'planned': True}))
            programme['declaration'] = pin(plan.read_bytes())
            # Capture is bound to this same updated declaration descriptor.
            result = read(Path(directory) / 'RESULT.json')
            result['declaration_sha256'] = programme['declaration']['sha256']
            body = raw(result); (Path(directory) / 'RESULT.json').write_bytes(body)
            receipt['output_inventory']['files']['RESULT.json'] = pin(body)
            L._protocol['programs'][condition] = programme
            predictions = L.captured_predictions(receipt, condition, 'improvement', programme)
            called = []
            L.api.freeze = lambda *args, **kwargs: called.append((args, kwargs)) or {'captured': True}
            adapter = E._BenchmarkCompatibility(L)
            adapter.freeze('/pair', 'p', '/task', 't', condition, 'improvement', predictions, plan,
                           Path(directory) / 'frozen.json', max_bytes=100000)
            self.assertEqual(called[0][0][7], str(Path(directory) / 'actual_declaration.json'))
            self.assertNotEqual(called[0][0][7], str(plan))
            self.assertEqual(called[0][1]['method_sha256'], 'c' * 64)
            (Path(directory) / 'actual_declaration.json').write_bytes(b'changed')
            with self.assertRaises(ValueError):
                adapter.freeze('/pair', 'p', '/task', 't', condition, 'improvement', predictions, plan,
                               Path(directory) / 'frozen-2.json', max_bytes=100000)
            self.assertEqual(len(called), 1)

    def test_failed_admission_clears_all_captured_context(self):
        with tempfile.TemporaryDirectory() as directory:
            L = self.episode(directory)
            L._captured_actual['old'] = {'path': 'old'}
            L._admit_protocol_impl = mock.Mock(side_effect=ValueError('failed immutable join'))
            with self.assertRaises(ValueError):
                L.admit_protocol(Path(directory) / 'PROTOCOL.json', '0' * 64)
            self.assertIsNone(L._protocol)
            self.assertIsNone(L._protocol_path)
            self.assertEqual(L._captured_actual, {})

    def test_data_verification_composes_only_in_owned_inspection(self):
        calls = []
        L = types.SimpleNamespace(api=types.SimpleNamespace(
            hash_file=None, inspect_pair=lambda *a, **k: calls.append('pair') or {'admitted': True}),
            _method=lambda c: calls.append(('method', c)), _release=lambda c: calls.append(('release', c)))
        result = E._BenchmarkCompatibility(L).inspect_pair('/pair', 'sha', '/task', 'sha', max_bytes=100)
        self.assertEqual(result, {'admitted': True})
        self.assertEqual(calls, ['pair', ('method', E.CONDITIONS[0]), ('release', E.CONDITIONS[0]),
                               ('method', E.CONDITIONS[1]), ('release', E.CONDITIONS[1])])

    def grade_fixture(self, directory):
        top = Path(directory)
        root, public, protocols, reports = [top / name for name in ('closed', 'public', 'protocols', 'reports')]
        for folder in (root, public, protocols, reports):
            folder.mkdir()
        L = self.episode(root)
        L.TASK_SHA = 'e' * 64
        L.material_binding = lambda: {'new_pair': {'bytes': 1, 'sha256': 'f' * 64}}
        deployment = {'pid_limit': 64, 'binding_pin': {'bytes': 1, 'sha256': '9' * 64}}
        L.deployment_binding = lambda: deployment
        runtime = {'qualification': {'path': '/operator/qualification.json', 'bytes': 1, 'sha256': '8' * 64},
                   'image': 'sha256:' + '7' * 64, 'deployment': deployment,
                   'source_read_bytes': 1024**2, 'host_write_bytes': 2 * 1024**2}
        protocol = {'source': {'bytes': 1, 'sha256': '6' * 64}, 'outcome': 'improvement',
                    'pair_path': str(public / 'pair_manifest.json'), 'task_path': str(public / 'task.json'),
                    'programs': {c: {'program': {'bytes': 1, 'sha256': 'a' * 64},
                                    'declaration': {'bytes': 1, 'sha256': 'b' * 64},
                                    'method': {'path': str(protocols / (c + '.method.json')), 'sha256': 'c' * 64}}
                                 for c in E.CONDITIONS}}
        L._protocol, L._protocol_path = protocol, protocols / 'PROTOCOL.json'
        L.admit_protocol = lambda *unused: (protocol, runtime)
        L.public_context = lambda *unused: ({}, {})
        L.validate_closed = lambda request, receipt: None  # Native closure is outside this source fixture.
        L.mounts_for = lambda *args: {'generated-view': 'identity'}
        L.mount_identity = lambda mounts: mounts
        L.request_bytes = L.encoded = raw
        def publish(path, value, mode=0o400):
            with Path(path).open('xb') as stream:
                stream.write(value)
            return pin(value)
        L.publish = publish
        target_calls = []
        L.api.score = lambda *args, **kwargs: target_calls.append((args, kwargs)) or {'fixture_measurement': 0}
        L._compatibility = E._BenchmarkCompatibility(L)
        closed = {'schema': L.CLOSED_SCHEMA, 'route': L.ROUTE, 'both_conditions_closed_before_private_grade': True,
                  'private_target_accessed': False, 'protocol_path': str(protocols / 'PROTOCOL.json'),
                  'protocol_sha256': 'd' * 64, 'source': protocol['source'], 'outcome': 'improvement',
                  'runtime_qualification': runtime['qualification'],
                  'owner_invocation_pin': {'bytes': 1, 'sha256': '5' * 64}, 'conditions': {}}
        for i, condition in enumerate(E.CONDITIONS):
            jobdir = root / 'jobs' / condition; jobdir.mkdir(parents=True)
            quarantine = root / 'quarantine' / condition; quarantine.mkdir(parents=True)
            receipt_path = root / 'control' / condition / 'RECEIPT.json'; receipt_path.parent.mkdir(parents=True)
            freeze_path = root / 'freezes' / (condition + '.json'); freeze_path.parent.mkdir(exist_ok=True)
            programme = protocol['programs'][condition]
            result = {'schema': 'smc_full_panel_program_result_v1', 'inference_condition_id': E.INFERENCE_CONDITION,
                      'outcome': 'improvement', 'condition': condition, 'program_sha256': 'a' * 64,
                      'declaration_sha256': 'b' * 64, 'method_freeze_sha256': 'c' * 64, 'submission_keys': ['offline']}
            bodies = {'offline.h5': b'generated-capture-' + bytes([65 + i]),
                      'actual_declaration.json': raw({'post_run_fixture': True}),
                      'RESULT.json': raw(result), 'OUTPUTS.json': raw({})}
            for name, value in bodies.items():
                (quarantine / name).write_bytes(value)
            exposure = {'mounts': {'generated-view': 'identity'}, 'source': protocol['source'],
                        'image': runtime['image'], 'role': 'A' if i == 0 else 'B', 'command': L.COMMAND,
                        'boundary_audit': {k: runtime['qualification'][k] for k in ('bytes', 'sha256')}}
            exposure_pin = publish(jobdir / 'EXPOSURE.json', raw(exposure))
            publish(jobdir / 'EXECUTION.json', raw(L.job_for(protocol, condition)))
            request = {'schema': L.REQUEST_SCHEMA, 'phase_id': condition, 'role': exposure['role'],
                       'image': runtime['image'], 'source': protocol['source'], 'command': L.COMMAND,
                       'workdir': '/work', 'action': 'held_attempt', 'resources': L.resources('improvement', runtime),
                       'output': {'kind': 'generic', 'manifest': 'OUTPUTS.json'}, 'exposure': exposure_pin,
                       'aggregate': {'phase_id': condition, 'deployment_pin': deployment['binding_pin'],
                                     'invocation_pin': closed['owner_invocation_pin']}}
            request_pin = publish(jobdir / 'REQUEST.json', raw(request))
            receipt = {'quarantine_root': str(quarantine), 'exposure': exposure_pin,
                       'input_before': exposure['mounts'], 'input_after': exposure['mounts'],
                       'output_inventory': {'complete': True, 'files': {n: pin(b) for n, b in bodies.items()}}}
            receipt_pin = publish(receipt_path, raw(receipt))
            frozen = {'condition': condition, 'outcome': 'improvement',
                      'submissions': {'offline': {'path': str(quarantine / 'offline.h5'),
                                                  'sha256': pin(bodies['offline.h5'])['sha256']}}}
            frozen_pin = publish(freeze_path, raw(frozen))
            closed['conditions'][condition] = {'receipt_path': str(receipt_path), 'receipt': receipt_pin,
                                               'freeze_path': str(freeze_path), 'freeze': frozen_pin,
                                               'request': request_pin}
        closed_path = root / 'PAIR_CLOSED.json'; closed_path.write_bytes(raw(closed))
        return L, closed_path, reports / 'report.json', closed, target_calls

    def test_facade_grade_crosses_real_profile_join_before_both_scores(self):
        with tempfile.TemporaryDirectory() as directory:
            L, path, output, closed, calls = self.grade_fixture(directory)
            result = L._grade_from_owned_pair(path, pin(path.read_bytes())['sha256'], '/protected/target',
                                              '/evaluator', output, 1000)
            self.assertEqual(len(calls), 2)
            self.assertTrue((path.parent / 'GRADE_STARTED.json').exists())
            self.assertTrue(result['transductive_fixed_panel'])
            self.assertFalse(result['fresh_trial_generalization'])
            self.assertFalse(result['pre_test_authoring_isolation_verified'])

    def test_facade_wrong_request_profile_cannot_reach_target_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            L, path, output, closed, calls = self.grade_fixture(directory)
            condition = E.CONDITIONS[0]
            request_path = path.parent / 'jobs' / condition / 'REQUEST.json'
            request = read(request_path); request['resources']['memory_bytes'] = 1
            request_path.write_bytes(raw(request))
            closed['conditions'][condition]['request'] = pin(request_path.read_bytes())
            path.write_bytes(raw(closed))
            with self.assertRaisesRegex(ValueError, 'request/profile'):
                L._grade_from_owned_pair(path, pin(path.read_bytes())['sha256'], '/protected/target',
                                         '/evaluator', output, 1000)
            self.assertEqual(calls, [])
            self.assertFalse((path.parent / 'GRADE_STARTED.json').exists())

    def test_second_condition_corruption_prevents_first_condition_score(self):
        with tempfile.TemporaryDirectory() as directory:
            L, path, output, closed, calls = self.grade_fixture(directory)
            prediction = path.parent / 'quarantine' / E.CONDITIONS[1] / 'offline.h5'
            prediction.write_bytes(b'changed')
            with self.assertRaises(ValueError):
                L._grade_from_owned_pair(path, pin(path.read_bytes())['sha256'], '/protected/target',
                                         '/evaluator', output, 1000)
            self.assertEqual(calls, [])
            self.assertFalse((path.parent / 'GRADE_STARTED.json').exists())

    def test_invalid_second_method_prevents_either_full_panel_release(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            L = self.episode(root)
            L.TASK_SHA = 'e' * 64
            L.material_binding = lambda: {'new_pair': {'bytes': 1, 'sha256': 'f' * 64}}
            L.public_context = lambda *unused: ({}, {})
            L.decode = json.loads
            L.runtime_config = lambda value: value
            runtime_path = root / 'runtime.json'; runtime_path.write_bytes(raw({}))
            L.api.inspect_method = mock.Mock(side_effect=[{'first_method': True}, ValueError('invalid second method')])
            L.api.release_inference_view = mock.Mock(side_effect=AssertionError('must not release either view'))
            methods = {c: {'path': str(root / (c + '.method.json')), 'sha256': 'c' * 64} for c in E.CONDITIONS}
            output = root / 'protocol'
            with self.assertRaisesRegex(ValueError, 'invalid second method'):
                L.instantiate('/operator/pair_manifest.json', '/operator/task.json', methods, runtime_path,
                              pin(runtime_path.read_bytes())['sha256'], output)
            self.assertEqual(L.api.inspect_method.call_count, 2)
            L.api.release_inference_view.assert_not_called()
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
