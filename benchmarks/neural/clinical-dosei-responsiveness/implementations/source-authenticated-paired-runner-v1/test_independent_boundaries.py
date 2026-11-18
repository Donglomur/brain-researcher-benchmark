"""Independent generated boundary controls; no model, Docker or array I/O.

The parent owns dispatch. Fake callbacks exercise host contracts, not isolation.
"""
import copy
import hashlib
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
FACTORY_SHA256 = 'e8cc730de704138f095e319fc4a812bdbcec5f68a2037630665309f776359fce'


def load_factory():
    path = HERE / 'delivery_factory.py'
    raw = path.read_bytes()
    assert len(raw) <= 32768 and hashlib.sha256(raw).hexdigest() == FACTORY_SHA256
    module = types.ModuleType('independent_paired_delivery')
    module.__file__ = str(path)
    sys.modules[module.__name__] = module
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


d = load_factory()


def load_local(filename, pin, name):
    path = HERE / filename
    raw = path.read_bytes()
    assert len(raw) <= 65536 and hashlib.sha256(raw).hexdigest() == pin
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


_BUNDLE = None


def bundle():
    global _BUNDLE
    if _BUNDLE is not None:
        return _BUNDLE
    if 'connector_test_bundle' in sys.modules:
        _BUNDLE = sys.modules['connector_test_bundle']
        return _BUNDLE
    admission = load_local('release_admission.py',
        'e10fb1a55e2299043486e79a0d85d8673cbc438503575b54be7fd35f5bab3b89',
        'independent_release_admission')
    fixtures = load_local('generated_fixture.py',
        '092207c43e7144852c9812638998bfc6d8412f8e3ae07eb8767b39af2fd0e35a',
        'independent_release_fixture')
    dependencies = load_local('dependencies.py',
        '9d52635c9dfbb35d95890e35609004dcae75f6a0bd4c8038c536b9a458a21708',
        'independent_release_dependencies')
    assembler = load_local('assembler.py',
        'ec131637eaa623973821bc8f9ee22191aa7438bb93384e2785d02681b7b554ce',
        'independent_assembler')
    modules, data, _ = dependencies.load_dependencies(HERE.parent, prefix='independent_release_existing')
    _BUNDLE = types.SimpleNamespace(MODULES=modules, DATA=data, admission=admission,
        fixture_api=fixtures, assembler=assembler, factory=d)
    return _BUNDLE


class Fixture:
    """Complete fictional identity set; only one case is ever projected."""
    def __init__(self):
        self.recorded = []
        self.fail_kind = None
        self.codes = []
        self.wrong_observation = False
        self.close_error = None
        self.project_calls = 0
        self.manifest = []
        self.indices = {}
        self.receipts = {}
        self.contexts = []
        for number in range(1, d.CASES + 1):
            case_id = f'{number:064x}'
            rid = str(1 + (number - 1) % d.RECORDINGS)
            row = number
            self.indices[case_id] = {
                'schema': 'dosei_private_window_index_v1', 'visibility': 'evaluator_private',
                'case_id': case_id, 'evaluator': {'case_id': case_id, 'recording_id': rid,
                'source_row': row, 'source_event_id': f'recording:{rid}/row:{row}'}}
            self.receipts[rid] = {'schema': 'dosei_full_eeg_member_success_v1',
                'recording_id': rid, 'status': 'succeeded', 'complete_source_EOF_CRC_SHA': True,
                'all_three_streams_closed_and_size_stat_checked': True}
            raw = d.canonical(self.packet(case_id))
            self.manifest.append({'case_id': case_id, 'observation_sha256': d.binding(raw)['sha256']})
            self.contexts.append(f'{number + 100000:064x}')

        class Delivery:
            def __init__(self, packet, projection, *, viewer):
                self.packet = copy.deepcopy(packet)
                self.raw = d.canonical(packet)
                self.projection = copy.deepcopy(projection)
                self.actions = []
            def public_binding(self):
                return {'case_id': self.packet['case_id'], 'observation_sha256': d.binding(self.raw)['sha256']}
            def disclosure(self): return json.loads(d.COMMON_DISCLOSURE)
            def code_observation(self): return self.raw
            def viewer_action(self, request):
                self.actions.append(copy.deepcopy(request))
                return b'fictional image bytes'

        class Code:
            def __init__(code, **kwargs):
                code.options = kwargs
                code.close_calls = 0
                self.codes.append(code)
            def code_observation(code):
                return b'wrong observation' if self.wrong_observation else code.options['observation_bytes']
            def viewer_action(code, request): return code.options['viewer'](request)
            def run_tool(code, name, source): return {'status': 'ok', 'text': 'generated'}
            def close(code):
                code.close_calls += 1
                if self.close_error is not None: raise self.close_error
                return code.options['recorder']('fake_code_close', b'generated code closure')

        self.options = dict(project_case=self.project, projection_options={},
            delivery_module=types.SimpleNamespace(PairedCaseDelivery=Delivery,
                DISCLOSURE=json.loads(d.COMMON_DISCLOSURE)),
            viewer_module=types.SimpleNamespace(TraceViewer=object, validate_packet=lambda value: None),
            code_backend_factory=Code,
            code_options={'profile_bytes': b'generated profile', 'staging_parent': '/generated/staging',
                'docker_executable': '/generated/docker', 'docker_socket': '/generated/socket',
                'policy_api': object(), 'command_api': object(), 'call_wall_seconds': 1, 'max_calls': 2},
            context_ids=self.contexts,
            owned_process_v2=types.SimpleNamespace(OwnedProcess=lambda *a, **k: None),
            owned_process_sha256=d.OWNED_PROCESS_SHA256, evidence_sink=self.sink)

    @staticmethod
    def packet(case_id):
        return {'schema': 'generated_packet', 'condition': 'native_marker_relative_30s_v1',
            'case_id': case_id, 'channels': ['EEG1', 'EEG2'], 'units': 'uV',
            'interval_ms': [-30000, 0], 'relative_time_ms': [-4], 'values_uv': [[1.0, 2.0]],
            'observation_mask': [[True, True]], 'source_endpoint_mask': [[False, False]],
            'coverage': {'row_count': 1}}

    def project(self, index, receipt):
        self.project_calls += 1
        packet = self.packet(index['case_id'])
        raw = d.canonical(packet)
        evidence = {'schema': 'dosei_host_slice_projection_receipt_v1',
            'visibility': 'evaluator_private', 'case_id': index['case_id'],
            'observation_sha256': d.binding(raw)['sha256'], 'observation_bytes': len(raw),
            'source_rows_read': 1, 'array_identity_binding_sha256': 'a' * 64,
            'private_generated_marker': 'must remain only in the host evidence sink'}
        self.last_projected = packet, evidence
        return packet, evidence

    def sink(self, kind, raw):
        self.recorded.append((kind, bytes(raw)))
        if kind == self.fail_kind: raise OSError('generated custody failure')
        return d.binding(raw)

    def factory(self):
        return d.OrderedDeliveryFactory(self.manifest, self.indices, self.receipts, **self.options)


class IndependentBoundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = bundle()
        cls.release_fixture = cls.bundle.fixture_api.Fixture(cls.bundle.MODULES, cls.bundle.admission)

    def test_coherently_rebound_private_source_and_observation_joins(self):
        admission, modules = self.bundle.admission, self.bundle.MODULES
        fixture = self.release_fixture
        row = fixture.rows[-1]
        original_coverage = copy.deepcopy(row['coverage'])
        row['coverage'] = copy.deepcopy(original_coverage)
        row['coverage']['row_count'] = float(row['coverage']['row_count'])
        fixture.rebuild()
        with self.assertRaisesRegex(admission.AdmissionRefusal, 'retained case coverage differs'):
            admission.admit_generated_release(fixture.blobs, fixture.members, modules=modules,
                                               generated_pins=fixture.pins)
        row['coverage'] = original_coverage
        original_identity = row['array_identity_binding_sha256']
        row['array_identity_binding_sha256'] = 'f' * 64
        self.assertNotEqual(original_identity, row['array_identity_binding_sha256'])
        fixture.rebuild()
        with self.assertRaisesRegex(admission.AdmissionRefusal, 'exact accepted array identity'):
            admission.admit_generated_release(fixture.blobs, fixture.members, modules=modules,
                                               generated_pins=fixture.pins)
        row['array_identity_binding_sha256'] = original_identity
        fixture.rebuild()

    def test_assembler_interruption_priority_and_incomplete_comparison_claim(self):
        b = self.bundle
        fixture = self.release_fixture
        env = b.fixture_api.Environment(fixture, b.MODULES, b.DATA, b.assembler)
        def build():
            return b.assembler.build_generated_runner(fixture.blobs, fixture.members,
                generated_pins=fixture.pins, admission_module=b.admission, factory_module=b.factory,
                modules=b.MODULES, data=b.DATA, projector=env.project, renderer=env.renderer(),
                code_factory=env.code, **env.options())
        with patch.object(b.MODULES['controller'], 'PairController',
                          side_effect=KeyboardInterrupt('original construction interruption')), \
             patch.object(b.factory.OrderedDeliveryFactory, 'close',
                          side_effect=OSError('secondary custody failure')) as cleanup:
            with self.assertRaisesRegex(KeyboardInterrupt, 'original construction interruption'):
                build()
            self.assertEqual(cleanup.call_count, 1)
        self.assertEqual(env.projections, 0)
        original_project = env.project
        def bad_project(*args, **kwargs):
            packet, receipt = original_project(*args, **kwargs)
            packet['units'] = 'generated mismatch'
            return packet, receipt
        env.project = bad_project
        runner = build()
        result = runner.run()
        self.assertEqual(result['status'], 'invalid_incomplete_pair')
        self.assertIs(result['accepted_packet_and_default_PNG_bytes_compared'], False)
        self.assertEqual(result['source_read_counters'], runner.resource_counters())
        self.assertEqual(env.models, 0)

    def test_detached_caller_and_returned_bindings(self):
        fixture = Fixture()
        factory = fixture.factory()
        public = fixture.manifest[0]
        first = factory(public, 'viewer_only')
        original = dict(first['source_evidence'])
        first['source_evidence']['sha256'] = 'f' * 64
        fixture.last_projected[0]['values_uv'][0][0] = 999
        fixture.last_projected[1]['private_generated_marker'] = 'changed caller alias'
        closed = first['backend'].close()
        closed['sha256'] = 'e' * 64
        self.assertNotEqual(first['backend'].close()['sha256'], closed['sha256'])
        second = factory(public, 'code_enabled')
        self.assertEqual(second['source_evidence'], original)
        self.assertEqual(second['backend'].code_observation(), d.canonical(fixture.packet(public['case_id'])))
        self.assertNotIn('private_generated_marker', second)
        second['backend'].close()
        factory.close()
        self.assertEqual(fixture.project_calls, 1)

    def test_failed_close_is_terminal_and_preserves_interruption(self):
        for interruption in (False, True):
            with self.subTest(interruption=interruption):
                fixture = Fixture()
                factory = fixture.factory()
                public = fixture.manifest[0]
                factory(public, 'viewer_only')['backend'].close()
                backend = factory(public, 'code_enabled')['backend']
                fixture.fail_kind = 'paired_delivery_close'
                if interruption: fixture.close_error = KeyboardInterrupt('generated close interruption')
                expected = KeyboardInterrupt if interruption else OSError
                with self.assertRaises(expected): backend.close()
                self.assertEqual(fixture.codes[0].close_calls, 1)
                for operation in (lambda: backend.viewer_action({'action': 'view'}),
                                  backend.code_observation,
                                  lambda: backend.run_tool('python', 'print(1)'), backend.close):
                    with self.assertRaises(d.DeliveryFactoryRefusal): operation()
                with self.assertRaises(d.DeliveryFactoryRefusal): factory(public, 'code_enabled')
                with self.assertRaises(d.DeliveryFactoryRefusal): factory.close()
                self.assertEqual(fixture.codes[0].close_calls, 1)
                self.assertTrue(factory.summary()['poisoned'])
                self.assertTrue(factory.summary()['cache_empty'])


if __name__ == '__main__':
    unittest.main()
