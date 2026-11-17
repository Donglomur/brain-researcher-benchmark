"""Generated real successor dispatch controls, without scientific execution.

Actual captured entry/bootstrap, reference preparation, phase-driver callsite,
replay callsite and protected release consumer execute. Scientific precursor
proofs and native execution are explicit test doubles; no test qualifies them.
Full686 metadata and all529 views stay in memory. No data body is opened.
"""
from contextlib import ExitStack
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import test_bridge as fixture
import bridge as b
V2 = HERE.parent / 'programme-source/implementation-v2'
PROGRAM = V2 / 'program'


def module(path, name, **bindings):
    m = types.ModuleType(name)
    m.__file__ = str(path)
    m.__dict__.update(bindings)
    sys.modules[name] = m
    exec(compile(path.read_bytes(), str(path), 'exec'), m.__dict__)
    return m


class StopBeforeNative(Exception):
    pass


class Successor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f = fixture.Fixture()
        cls.partial_selection = copy.deepcopy(cls.f.streaming_selection)
        cls.partial_files = dict(cls.f.files)
        for view in cls.f.views[2:]:
            cls.f.add_event('view_intent', view)
            cls.f.add_event('view_complete', view)
        cls.f.streaming_selection['checkpoint'] = {'sequence': len(cls.f.events),
            'sha256': cls.f.tip, 'total': dict(cls.f.total)}
        cls.entry = module(PROGRAM / 'entry.py', 'generated_successor_entry')
        cls.manifest_pin = b.pin((PROGRAM / 'SOURCE_MANIFEST.json').read_bytes())
        root, cls.bodies, cls.source_files, cls.load, cls.bootstrap_reads, cls.source_pin = cls.entry.bootstrap(
            cls.manifest_pin['bytes'], cls.manifest_pin['sha256'])
        cls.load = staticmethod(cls.load)
        cls.c = cls.load('common')
        cls.reference = cls.load('reference_study')
        cls.dispatch = cls.load('preparation_dispatch')
        cls.phase = cls.load('phase_driver')
        cls.release = cls.load('release')
        cls.old = cls.load('legacy').load(cls.bodies)
        cls.ios = []
        f, owner = cls.f, cls
        actual = cls.dispatch.BudgetIO
        class MemoryBudgetIO(actual):
            def __init__(self, roots, budget):
                super().__init__(roots, budget)
                self.files, self.stats = dict(f.files), dict(f.stats)
                owner.ios.append(self)
            capture = fixture.MemoryIO.capture
            journal_body = fixture.MemoryIO.journal_body
            names = fixture.MemoryIO.names
            stat_only = fixture.MemoryIO.stat_only
            prohibited = fixture.MemoryIO.prohibited
        cls.memory_io = MemoryBudgetIO

    def budget(self, read_bytes=256 * 1048576):
        return self.c.Budget(1.0, {'seconds': 100.0, 'read_bytes': read_bytes,
            'write_bytes': 0, 'native_cpu_seconds': 0, 'native_processes': 0,
            'host_processes': 0, 'provider_requests': 0, 'provider_tokens': 0,
            'stream_bytes': 0, 'tool_processes': 0}, clock=lambda: 2.0)

    def admit(self, selection):
        with patch.object(self.dispatch, 'BudgetIO', self.memory_io):
            return self.reference.preparation(selection, self.budget(), self.old)

    def assert_no_labels(self, io):
        self.assertFalse(any(io.prohibited(x['path']) for x in io.accesses if x.get('body_opened') is not False))

    def test_actual_program_bootstrap_closes_and_imports_dispatcher(self):
        self.assertEqual(len(self.source_files), 40)
        self.assertIs(self.phase.reference_study, self.reference)
        self.assertIs(self.release.reference_study, self.reference)
        self.assertEqual(self.bodies['preparation_compatibility.py'], (HERE / 'bridge.py').read_bytes())
        self.assertIs(self.reference.preparation_dispatch, self.dispatch)
        with self.assertRaisesRegex(ValueError, 'changed exact source'):
            self.entry.bootstrap(self.manifest_pin['bytes'], '0' * 64)

    def test_actual_central_bootstrap_captures_closed_successor_and_shared_sources(self):
        central = V2 / 'central-integration'
        u = module(central / 'common_io.py', 'generated_successor_central_io')
        loader = module(central / 'bootstrap.py', 'generated_successor_central_bootstrap', u=u)
        source = b.pin((central / 'SOURCE_MANIFEST.json').read_bytes())
        reader = u.Reader(read_limit=8 * 1048576, write_limit=0, deadline=time.monotonic() + 20)
        env = loader.capture(central, source, reader, time.monotonic(), sys.executable)
        self.assertEqual(env['parent_root'], PROGRAM)
        self.assertEqual(env['parent_pin'], self.source_pin)
        self.assertEqual(len(env['parent_files']), 40)
        self.assertEqual(env['parent_driver'].reference_study.preparation_dispatch.__file__, str(PROGRAM / 'preparation_dispatch.py'))
        self.assertEqual(env['gate'].CONTRACT, (V2 / 'shared/contract').relative_to(env['repo']).as_posix())
        self.assertLess(reader.read_reserved, reader.read_limit)
        manifest = b.parse((central / 'SOURCE_MANIFEST.json').read_bytes())
        self.assertIs(manifest['qualified'], False)
        for name, pin in manifest['files'].items():
            self.assertEqual(b.pin((central / name).read_bytes()), pin)

    def test_actual_preparation_both_routes_all529_and_request_composition(self):
        for selected in (self.f.original_selection, self.f.streaming_selection):
            prepared = self.admit(selected)
            self.assertEqual(prepared['route'], selected['route'])
            self.assertEqual(prepared['receipt_pin'], selected['receipt'])
            self.assertTrue(prepared['all_views_materialized_checked'])
            self.assertEqual(len(prepared['views']), 529)
            self.assertEqual(len(prepared['rows']), 686)
            self.assertEqual(len(prepared['people']), 23)
            self.assert_no_labels(self.ios[-1])
            outer, _, inner = self.f.selected_names[1].split('/')
            wanted = '/'.join((outer, 'matched_no_eeg', inner, '0', 'fit'))
            job = next(x for x in self.load('schedule').reference_jobs(prepared['rows']) if x['id'] == wanted)
            study = object.__new__(self.reference.ReferenceStudy)
            study.p, study.identity, study.limits = prepared, b.pin(b'GENERATED SOURCE'), {'max_input_bytes': 10**9}
            study.ops, study.features = {}, {}
            request, inputs, opaque = study.request(job)
            self.assertEqual(request['records']['path'], selected['private_root'] + '/views/' + self.f.selected_names[1] + '/TRAIN.json')
            self.assertEqual(opaque, [request['records']['path']])
            self.assert_no_labels(self.ios[-1])

    def test_actual_preparation_rejects_partial_view_materialization(self):
        original = self.f.files
        self.f.files = self.partial_files
        try:
            with patch.object(self.dispatch, 'BudgetIO', self.memory_io):
                with self.assertRaisesRegex(ValueError, 'materialization completion'):
                    self.reference.preparation(self.partial_selection, self.budget(), self.old)
        finally:
            self.f.files = original

    def test_actual_legacy_five_field_path_uses_shared_receipt_validator(self):
        selected = {k: self.f.original_selection[k] for k in ('receipt', 'public_root', 'private_root', 'selected_source_manifest', 'selected_original_roster')}
        io = self.f.io()
        def capture(desc, budget, roots):
            budget.charge('read_bytes', desc['bytes'] + 1)
            return io.capture(desc, 'generated_legacy_capture')
        with patch.object(self.dispatch, 'BudgetIO', self.memory_io), patch.object(self.c, 'capture', capture):
            prepared = self.reference.preparation(selected, self.budget(), self.old)
            self.assertEqual(prepared['assessment_pin'], self.f.original_receipt['assessment'])
            self.assertTrue(prepared['all_views_materialized_checked'])
            for altered in ({**self.f.original_receipt, 'actual_models_or_scores': True}, {k: v for k, v in self.f.original_receipt.items() if k != 'vendor_sources'}):
                raw = b.encoded(altered)
                io.files[selected['receipt']['path']] = raw
                changed = copy.deepcopy(selected)
                changed['receipt'].update(b.pin(raw))
                old_reads = len(io.accesses)
                with self.assertRaises(ValueError):
                    self.reference.preparation(changed, self.budget(), self.old)
                self.assertEqual(len(io.accesses), old_reads + 1)
        self.assert_no_labels(io)

    def test_real_phase_driver_routes_preparation_before_native_construction(self):
        refs = self.phase.reference_sources(self.source_files)
        manifest = next(x for x in refs if x['path'].endswith('/SOURCE_MANIFEST.json'))
        actual = self.reference.preparation
        for selected in (self.f.original_selection, self.f.streaming_selection):
            prepared = []
            def witness(*args):
                result = actual(*args)
                prepared.append(result)
                return result
            def no_native(*args):
                self.assertEqual(prepared[0]['receipt_pin'], selected['receipt'])
                self.assertTrue(prepared[0]['all_views_materialized_checked'])
                raise StopBeforeNative('actual native construction reached after admission')
            request = {'phase': 'references', 'output_root': '/generated/no-output', 'source': self.source_pin,
                'payload': {'capture_roots': ['/generated'], 'fixed_authors_closure': {},
                    'reference_seal_settings': {'preparation': selected, 'reference_source': manifest,
                        'reference_limits': {}, 'native_config': {}, 'native_phase_limits': {}, 'native_source_files': refs}}}
            with ExitStack() as stack:
                stack.enter_context(patch.object(self.dispatch, 'BudgetIO', self.memory_io))
                stack.enter_context(patch.object(self.reference, 'preparation', witness))
                stack.enter_context(patch.object(self.c, 'new_directory', lambda p, budget: Path(p)))
                stack.enter_context(patch.object(self.phase, 'closure', lambda *args: {'artifacts': {'phase_result': {}}}))
                stack.enter_context(patch.object(self.phase, 'object_body', lambda *args: {'schema': 'neural010-data-free-authors-v1', 'authors': [0, 1, 2]}))
                stack.enter_context(patch.object(self.phase.native, 'Native', no_native))
                with self.assertRaises(StopBeforeNative):
                    self.phase.execute(request, {}, {'root': '/generated'}, {}, self.budget(), self.bodies, self.source_files)
            self.assert_no_labels(self.ios[-1])

    def test_real_replay_routes_same_receipt_before_original_job_admission(self):
        for selected in (self.f.original_selection, self.f.streaming_selection):
            prepared = self.admit(selected)
            request = {k: {} for k in self.release.SEAL_FIELDS}
            request.update(schema='neural010-four-stream-seal-request-v1', preparation=selected)
            study = {'schema': 'neural010-reference-study-provisional-v1', 'preparation': selected['receipt'],
                'panel': prepared['panel_pin'], 'metadata': prepared['metadata_pin'], 'reference_source': {},
                'operations': [], 'final_folds': [], 'reference_counts': self.load('schedule').expected_counts(),
                'observer_own_exit_established': False, 'assessment_operand_opened': False,
                'global_assessment_release_authorized': False}
            def stop(rows, operations):
                self.assertEqual(len(rows), 686)
                raise StopBeforeNative('actual original complete-job gate reached')
            with ExitStack() as stack:
                stack.enter_context(patch.object(self.dispatch, 'BudgetIO', self.memory_io))
                stack.enter_context(patch.object(self.release, '_source', lambda *args: {}))
                stack.enter_context(patch.object(self.c, 'capture_json', lambda *args: study))
                stack.enter_context(patch.object(self.release.schedule, 'complete_reference_admission', stop))
                with self.assertRaises(StopBeforeNative):
                    self.release._replay(request, self.budget(), [Path('/generated')], self.old)
            self.assert_no_labels(self.ios[-1])

    def test_actual_release_reads_common_pin_only_after_barrier(self):
        # This controls consumer ordering only. Every source/native/observer
        # precursor below is an explicit generated double, not accepted proof.
        prepared = self.admit(self.f.streaming_selection)
        self.assertNotIn('assessment', prepared['receipt'])
        desc = lambda name: {'path': '/generated/' + name, **b.pin(name.encode())}
        request = {k: desc(k) for k in self.release.RELEASE_FIELDS if k != 'schema'}
        request['schema'] = 'neural010-assessment-release-request-v1'
        seal = {'source': request['source'], 'reference_study': desc('study'),
                'reference_source': desc('worker-source'), 'reference_phase_request': desc('phase')}
        master = {'schema': 'neural010-four-stream-master-v1', 'task_id': 'NEURAL-010',
            'seal_request': seal, 'source': request['source'], 'reference_study': seal['reference_study'],
            'reference_source': seal['reference_source'], 'reference_phase_request': seal['reference_phase_request'],
            'preparation': prepared['receipt_pin'], 'panel': prepared['panel_pin'], 'metadata': prepared['metadata_pin'],
            'event_source': {}, 'reference_counts': self.load('schedule').expected_counts(), 'dispositions': [],
            'final_folds': [], 'predictions': {arm: desc(arm) for arm in self.c.ARMS},
            'admission': request['master_admission'], 'observer_own_exit_established': False,
            'assessment_operand_opened': False, 'global_assessment_release_authorized': False}
        raw = self.c.encoded(master)
        request['master'] = {'path': '/generated/master', **b.pin(raw)}
        events = []
        authority = {k: {} for k in self.release.AUTHORITY_FIELDS}
        authority.update({k: request[k] for k in ('source','master','master_admission','reference_spec','reference_observation','reference_external')})
        authority.update(schema='neural010-root-assessment-release-authority-v1',
            release_request=b.pin(self.c.encoded(request)), original_origin=1.0, original_deadline=101.0,
            assessment={'path': str(prepared['private_root'] / 'assessment.json'), **prepared['assessment_pin']})
        actual_descriptor = self.c.descriptor
        def descriptor(value, *args, **kwargs):
            if value is authority['assessment']:
                self.assertEqual(events, ['closure', 'replay', 'admission', 'carriers'])
                events.append('assessment_descriptor')
            return actual_descriptor(value, *args, **kwargs)
        def replay(*args):
            events.append('replay')
            return {'prepared': prepared, 'event_source': {}, 'dispositions': [], 'study': {'final_folds': []}}
        def capture(desc, *args):
            if desc == request['master']:
                return raw
            self.assertEqual(desc, dict.get(authority, 'assessment'))
            self.assertEqual(events[-1], 'assessment_descriptor')
            events.append('assessment_capture_attempt')
            raise StopBeforeNative('correct common pin reached protected assessment capture')
        with ExitStack() as stack:
            stack.enter_context(patch.object(self.c, 'source_authority', lambda *args: None))
            stack.enter_context(patch.object(self.c, 'descriptor', descriptor))
            stack.enter_context(patch.object(self.c, 'capture', capture))
            stack.enter_context(patch.object(self.c, 'capture_json', lambda *args: events.append('admission') or {}))
            stack.enter_context(patch.object(self.release, '_reference_observer', lambda *args: events.append('closure') or {}))
            stack.enter_context(patch.object(self.release, '_replay', replay))
            stack.enter_context(patch.object(self.release, '_admission', lambda *args: {}))
            stack.enter_context(patch.object(self.release, '_carriers', lambda *args: events.append('carriers') or []))
            stack.enter_context(patch.object(self.release, '_empty_output', lambda root, budget: Path(root)))
            with self.assertRaises(StopBeforeNative):
                self.release.release_assessment(request, protected_authority=authority, budget=self.budget(),
                    capture_roots=['/generated'], output_root='/generated/no-output', legacy=self.old)
        self.assertEqual(events[-1], 'assessment_capture_attempt')


if __name__ == '__main__':
    unittest.main(verbosity=2)
