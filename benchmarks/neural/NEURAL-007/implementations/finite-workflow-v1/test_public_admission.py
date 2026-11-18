"""Real public-entry negative controls; no original arrays or provider calls.

The capacity fixture claims complete_unscored adversarially. Its only wire frame
is the authentic 2780-epoch ready projection; its two events are produced by the
unchanged Bridge's actual refusal. It is never successful provider evidence.
Canonical ordering stops public admission at person001, so these controls do
not establish person002 replay, positive admission, or scientific qualification.
"""
from contextlib import contextmanager
from dataclasses import asdict
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest


RELATIVE = Path('benchmarks/neural/NEURAL-007/implementations')
ROOT = Path(os.environ.get('N007_DEPENDENCY_ROOT', Path(__file__).resolve().parents[5])).resolve()
SOURCE = ROOT / RELATIVE / 'finite-workflow-v1'
CAPACITY = 'Viewer provider bridge failed at canonical_full_history_image_capacity; no retry or further action'
WRITES = []
OBSERVATIONS = []
ACTIVE_GUARD = None


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


@contextmanager
def common_module(value):
    previous = sys.modules.get('common')
    sys.modules['common'] = value
    try:
        yield
    finally:
        if previous is None:
            sys.modules.pop('common', None)
        else:
            sys.modules['common'] = previous


C = module(SOURCE / 'common.py', 'sleep007_public_controls_common')
with common_module(C):
    P = module(SOURCE / 'provenance.py', 'sleep007_public_controls_provenance')


def audit(event, args):
    """Observe Python audit events; this is not a syscall/sandbox guarantee."""
    if ACTIVE_GUARD is None:
        return
    if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
        path = Path(os.fsdecode(args[0])).absolute()
        ACTIVE_GUARD['opened'].append(str(path))
        if path.suffix.lower() in ('.npz', '.npy', '.edf') or any(
                path == target or target in path.parents for target in ACTIVE_GUARD['protected']):
            ACTIVE_GUARD['forbidden'].append(str(path))
            raise AssertionError('Generated private/packet/output canary must not be opened')
    if event.startswith(('socket.', 'os.exec', 'os.spawn')) or event in ('subprocess.Popen', 'os.system'):
        ACTIVE_GUARD['external'].append(event)
        raise AssertionError('No network, process, model or native operation')


sys.addaudithook(audit)


def write(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw)
    WRITES.append({'path': str(path), **C.pin(raw)})
    return {'path': str(path), **C.pin(raw)}


def fixture_accounting():
    return {'created_file_bytes': sum(row['bytes'] for row in WRITES),
            'created_files': len(WRITES), 'producer_overwrites': 0,
            'retained_when_explicit_control_root': True, 'writes': list(WRITES),
            'observations': list(OBSERVATIONS)}


def restore_source_modules(before, control):
    for name, value in list(sys.modules.items()):
        file = getattr(value, '__file__', None)
        if not isinstance(file, str):
            continue
        path = Path(file).absolute()
        if path.is_relative_to(ROOT) or path.is_relative_to(control):
            if name in before:
                sys.modules[name] = before[name]
            else:
                del sys.modules[name]


class PublicAdmissionControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        explicit = os.environ.get('N007_PUBLIC_ADMISSION_CONTROL_ROOT')
        if explicit:
            cls.control = Path(explicit).resolve()
            cls.control.mkdir(parents=True, exist_ok=False)
        else:
            temporary = tempfile.TemporaryDirectory(prefix='sleep007-public-admission-')
            cls.control = Path(temporary.name).resolve()
            cls.addClassCleanup(temporary.cleanup)
        before = dict(sys.modules)
        cls.addClassCleanup(restore_source_modules, before, cls.control)
        cls.client = C._module('sleep007_public_fixture_client', *C.original('fresh_provider_client'))
        cls.runtime = cls.client.load_runtime(ROOT, ROOT / RELATIVE / 'viewer-provider-integration-v1')
        cls.provider, cls.transport = cls.runtime['provider'], cls.runtime['transport']
        if cls.provider.PROVIDER_IMAGE_CAP != 1500 or cls.client.CASES != dict(C.SPEC_CASES):
            raise AssertionError('Original full-person roster and provider ceiling must remain unchanged')

    def setUp(self):
        self.addCleanup(restore_source_modules, dict(sys.modules), self.control)
        self.folder = self.control / self._testMethodName
        self.folder.mkdir()
        self.common, self.provenance = C, P
        self.protected = [self.folder / 'protected']

    def evidence(self, value, name='evidence.json'):
        return {'fresh_provider': write(self.folder / name, C.json_bytes(value))}

    def empty_evidence(self):
        rows = [{'case_id': case, 'epochs': epochs,
                 'packet_root': str(self.folder / 'protected' / case / 'packet'),
                 'transport_root': str(self.folder / case / 'transport'),
                 'provider_root': str(self.folder / case / 'provider')}
                for case, epochs in C.SPEC_CASES]
        absent = {'path': str(self.folder / 'protected' / 'collection.json'),
                  'bytes': 1, 'sha256': '0' * 64}
        return {'schema': 'sleep007_fresh_viewer_evidence_v1',
                'condition': self.client.CONDITION, 'rows': rows,
                'collection': dict(absent), 'viewer_collection': dict(absent)}

    def fixture(self, *, missing_bound=False, changed_bound=False, changed_runtime=False):
        """Generate a forged completion claim that the real capacity gate rejects."""
        p, t = self.provider, self.transport
        value = self.empty_evidence()
        row = value['rows'][0]
        token = b"raise AssertionError('TOKEN_BOUND_SOURCE_MUST_NEVER_EXECUTE')\n"
        token_pin = C.pin(token)
        token_path = self.folder / 'token_bound.py'
        write(token_path, token[:-1] + b' ' if changed_bound else token)
        budget = p.Budget(max_turns=12000, max_images=1500, max_history_bytes=16384,
                          max_request_bytes=16384, max_response_bytes=4096,
                          max_total_provider_bytes=1048576, context_tokens=20000,
                          output_tokens=128, wall_seconds=30)
        source_root = ROOT
        if changed_runtime:
            source_root = self.folder / 'changed-runtime'
            # load_runtime authenticates this first body before importing any runtime.
            relative = next(iter(self.client.SOURCES))
            raw = (ROOT / relative).read_bytes()
            write(source_root / relative, raw[:-1] + b' ')
        config = {'schema': 'neural007_viewer_provider_session_v1', 'root': str(source_root),
                  'integration_root': str(ROOT / RELATIVE / 'viewer-provider-integration-v1'),
                  'case_id': row['case_id'], 'model': 'generated-negative-control',
                  'budget': asdict(budget), 'source': self.runtime['source'],
                  'token_bound_source': None if missing_bound else {'path': str(token_path), **token_pin}}
        limits = t.Limits(max_actions=6000, max_images=3000, max_output_bytes=8388608, wall_seconds=35)
        packet_metadata = SimpleNamespace(case=row['case_id'], epochs=row['epochs'])
        ready = t.wire(t.ready_header(packet_metadata, limits, 'a' * 32))
        metadata = []
        def forbidden_callback(*args):
            raise AssertionError('Fixture must refuse before sender or token callback')
        bridge = p.Bridge(task='NEURAL-007', condition=self.client.CONDITION,
                          model=config['model'], budget=budget, send_json=forbidden_callback,
                          input_token_bound=forbidden_callback,
                          record=lambda meta, request, response: metadata.append(meta))
        with self.assertRaisesRegex(ValueError, '^' + CAPACITY + '$'):
            bridge.serve(io.BytesIO(ready), io.BytesIO())
        self.assertEqual([item['event'] for item in metadata], ['ready', 'failed_no_further_action'])
        self.assertEqual(metadata[1]['failure_stage'], 'canonical_full_history_image_capacity')
        self.assertEqual(bridge.turns, 0)
        self.assertEqual(bridge.images, 0)
        provider_root, transport_root = Path(row['provider_root']), Path(row['transport_root'])
        provider_root.mkdir(parents=True)
        (provider_root / 'turns').mkdir()
        config_raw = p.encode(config)
        write(provider_root / 'CONFIG.json', config_raw)
        deadline = 1000.0
        for ordinal, meta in enumerate(metadata):
            write(provider_root / 'events' / f'{ordinal:06d}.json', p.encode({
                'schema': 'neural007_viewer_provider_event_v1', 'config': C.pin(config_raw),
                'deadline': deadline, 'bridge': meta}))
        # Deliberately false completion claim: the public route must refuse it.
        write(provider_root / 'CLIENT_END.json', p.encode({'status': 'complete_unscored', 'deadline': deadline}))
        write(transport_root / 'BOUNDARY.json', p.encode({'limits': asdict(limits)}))
        write(transport_root / 'transport' / 'wire.bin', ready)
        write(self.folder / 'ADVERSARIAL_FIXTURE.txt',
              b'Generated ready-only refusal with a forged complete_unscored claim; not successful provider evidence.\n')
        submission = write(self.folder / 'protected' / 'predictions.npz', b'PRIVATE_ORIGINAL_ARRAY_CANARY_NOT_AN_NPZ\n')
        write(self.folder / 'protected' / 'private_locations.json', b'PRIVATE_TARGET_LOCATION_CANARY\n')
        for item in value['rows']:
            write(Path(item['packet_root']) / 'labels.npz', b'PACKET_ARRAY_CANARY_NOT_AN_NPZ\n')
        return self.evidence(value), submission, token_path

    def copy_finite(self, change):
        directory = self.folder / 'changed-source' / RELATIVE / 'finite-workflow-v1'
        for name in ('common.py', 'provenance.py', 'fresh_viewer.py', 'SOURCE_BINDINGS.json'):
            raw = (SOURCE / name).read_bytes()
            write(directory / name, raw[:-1] + b' ' if change == name else raw)
        if change == 'client.py':
            raw = C.read(*C.original('fresh_provider_client'))
            write(directory.parent / 'viewer-provider-integration-v1' / 'client.py', raw[:-1] + b' ')
        self.common = module(directory / 'common.py', 'sleep007_public_changed_common')
        with common_module(self.common):
            self.provenance = module(directory / 'provenance.py', 'sleep007_public_changed_provenance')

    def invoke(self, proof, submission=None, *, grade=False):
        """Trace genuine function calls and veto any protected Python open event."""
        global ACTIVE_GUARD
        observed = {'test': self._testMethodName, 'calls': [], 'opened': [],
                    'protected': list(self.protected), 'forbidden': [], 'external': []}
        names = {'admit_viewer', 'admit', 'checked_evidence', 'load_runtime', 'source_bytes',
                 'audit_provider_session', 'serve', 'admit_grade', 'admit_programme',
                 'descriptor_read', 'private_targets', 'load_once'}
        def trace(frame, event, arg):
            packet_init = (frame.f_code.co_name == '__init__'
                           and type(frame.f_locals.get('self')).__name__ == 'Packet'
                           and Path(frame.f_code.co_filename) == ROOT / RELATIVE / 'whole-night-viewer-v1/viewer.py')
            if event == 'call' and (frame.f_code.co_name in names or packet_init):
                observed['calls'].append({'name': 'Packet.__init__' if packet_init else frame.f_code.co_name,
                                          'file': frame.f_code.co_filename,
                                          'line': frame.f_code.co_firstlineno})
        previous = sys.getprofile()
        ACTIVE_GUARD = observed
        try:
            with common_module(self.common):
                sys.setprofile(trace)
                if grade:
                    return self.provenance.admit_grade({
                        'schema': 'sleep007_finite_grade_v1', 'source_freeze': {},
                        'viewer_proof': proof, 'programme_commit': {}, 'viewer': submission,
                        'parts': {}, 'references': {},
                        'private_locations': {'path': str(self.folder / 'protected' / 'private_locations.json')}})
                return self.provenance.admit_viewer(proof, submission or {})
        finally:
            sys.setprofile(previous)
            ACTIVE_GUARD = None
            observed['protected'] = [str(path) for path in observed['protected']]
            OBSERVATIONS.append(observed)
            self.observed = observed
            self.assertEqual(observed['forbidden'], [])
            self.assertEqual(observed['external'], [])

    def assert_calls(self, *names):
        actual = [row['name'] for row in self.observed['calls']]
        for name in names:
            self.assertIn(name, actual)

    def assert_no_calls(self, *names):
        actual = [row['name'] for row in self.observed['calls']]
        for name in names:
            self.assertNotIn(name, actual)

    def test_exact_fresh_descriptor_reaches_authenticated_delegate(self):
        with self.assertRaisesRegex(ValueError, '^exact canonical fresh viewer evidence request$'):
            self.invoke(self.evidence({}))
        self.assert_calls('admit_viewer', 'admit', 'checked_evidence')
        called = next(row for row in self.observed['calls'] if row['name'] == 'admit')
        self.assertEqual(Path(called['file']), C.original('fresh_viewer')[0])
        self.assert_no_calls('load_runtime', 'audit_provider_session', 'serve')

    def test_mixed_fresh_and_legacy_descriptor_is_rejected_without_dispatch(self):
        with self.assertRaisesRegex(ValueError, '^accepted old viewer proof$'):
            self.invoke({'fresh_provider': {}, 'complete': {}, 'review': {}})
        self.assert_no_calls('admit', 'descriptor_read')

    def test_dict_subclass_cannot_select_fresh_dispatch(self):
        class Descriptor(dict):
            pass
        with self.assertRaisesRegex(ValueError, '^accepted old viewer proof$'):
            self.invoke(Descriptor(fresh_provider={}))
        self.assert_no_calls('admit', 'descriptor_read')

    def test_malformed_canonical_roster_is_rejected_before_runtime_or_packets(self):
        changes = [lambda x: x.update(condition='other'), lambda x: x['rows'].pop(),
                   lambda x: x['rows'].reverse(), lambda x: x['rows'][0].update(epochs=True),
                   lambda x: x['rows'][0].update(packet_root='relative'),
                   lambda x: x['rows'][1].update(packet_root=x['rows'][0]['packet_root'])]
        for ordinal, change in enumerate(changes):
            value = self.empty_evidence()
            change(value)
            with self.subTest(change=ordinal), self.assertRaises(ValueError):
                self.invoke(self.evidence(value, f'malformed-{ordinal}.json'))
            self.assert_calls('admit_viewer', 'admit', 'checked_evidence')
            self.assert_no_calls('load_runtime', 'audit_provider_session', 'serve')

    def test_changed_admission_source_is_rejected_before_execution(self):
        self.copy_finite('fresh_viewer.py')
        with self.assertRaisesRegex(ValueError, '^input pin mismatch$'):
            self.invoke(self.evidence({}))
        self.assert_no_calls('admit', 'descriptor_read')

    def test_changed_client_source_is_rejected_before_execution(self):
        self.copy_finite('client.py')
        with self.assertRaisesRegex(ValueError, '^input pin mismatch$'):
            self.invoke(self.evidence(self.empty_evidence()))
        self.assert_calls('admit', 'checked_evidence')
        self.assert_no_calls('load_runtime', 'audit_provider_session', 'serve')

    def test_changed_bound_provider_source_is_rejected_before_runtime_execution(self):
        proof, submission, _ = self.fixture(changed_runtime=True)
        with self.assertRaisesRegex(ValueError, '^Source identity changed$'):
            self.invoke(proof, submission)
        self.assert_calls('admit_viewer', 'admit', 'load_runtime', 'source_bytes')
        self.assert_no_calls('audit_provider_session', 'serve')

    def test_missing_token_bound_source_is_rejected_before_provider_audit(self):
        proof, submission, _ = self.fixture(missing_bound=True)
        with self.assertRaisesRegex(ValueError, '^complete real CLI execution requires its frozen token-bound source$'):
            self.invoke(proof, submission)
        self.assert_calls('admit', 'load_runtime')
        self.assert_no_calls('audit_provider_session', 'serve')

    def test_changed_token_source_is_rejected_without_import(self):
        proof, submission, token = self.fixture(changed_bound=True)
        with self.assertRaisesRegex(ValueError, '^Source identity changed$'):
            self.invoke(proof, submission)
        self.assertIn(str(token), self.observed['opened'])
        self.assert_no_calls('audit_provider_session', 'serve')

    def test_real_public_route_authenticates_token_then_refuses_canonical_capacity(self):
        proof, submission, token = self.fixture()
        with self.assertRaisesRegex(ValueError, '^' + CAPACITY + '$'):
            self.invoke(proof, submission)
        self.assert_calls('admit_viewer', 'admit', 'load_runtime', 'source_bytes', 'audit_provider_session', 'serve')
        self.assertIn(str(token), self.observed['opened'])
        self.assertEqual(sum(row['name'] == 'audit_provider_session' for row in self.observed['calls']), 1)
        served = [row for row in self.observed['calls'] if row['name'] == 'serve']
        self.assertEqual(len(served), 1)
        self.assertEqual(Path(served[0]['file']), ROOT / RELATIVE / 'viewer-provider-v1/provider.py')
        self.assert_no_calls('admit_programme', 'private_targets', 'load_once', 'Packet.__init__')
        self.assertFalse(any('development-002/provider/' in path for path in self.observed['opened']))

    def test_real_grade_admission_refuses_viewer_before_programme_or_private_targets(self):
        proof, submission, _ = self.fixture()
        with self.assertRaisesRegex(ValueError, '^' + CAPACITY + '$'):
            self.invoke(proof, submission, grade=True)
        self.assert_calls('admit_grade', 'admit_viewer', 'admit', 'load_runtime', 'audit_provider_session', 'serve')
        self.assert_no_calls('admit_programme', 'private_targets', 'load_once', 'Packet.__init__')

    def test_legacy_shape_keeps_original_pin_rejection_without_fresh_dispatch(self):
        pin = {'path': str(self.folder / 'protected' / 'legacy.json'), 'bytes': 1, 'sha256': '0' * 64}
        with self.assertRaisesRegex(ValueError, '^exact accepted complete proof and independent review$'):
            self.invoke({'complete': dict(pin), 'review': dict(pin)})
        self.assert_calls('admit_viewer')
        self.assert_no_calls('admit', 'descriptor_read', 'load_runtime')


if __name__ == '__main__':
    unittest.main()
