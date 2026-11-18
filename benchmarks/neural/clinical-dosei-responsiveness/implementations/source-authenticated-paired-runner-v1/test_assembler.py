"""New connector controls only. All metadata, packets and participants fictional."""
import gc
import hashlib
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def load(path, name):
    raw = path.read_bytes()
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


admission = load(HERE/'release_admission.py', 'connector_admission')
assembler = load(HERE/'assembler.py', 'connector_assembler')
factory = load(HERE/'delivery_factory.py', 'connector_factory')
dependencies = load(HERE/'dependencies.py', 'connector_dependencies')
fixture_api = load(HERE/'generated_fixture.py', 'connector_fixture')
MODULES, DATA, SOURCE_BINDINGS = dependencies.load_dependencies(HERE.parent, prefix='connector_existing')


class ConnectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = fixture_api.Fixture(MODULES, admission)
    def build(self, env):
        f = self.fixture
        return assembler.build_generated_runner(f.blobs, f.members, generated_pins=f.pins,
            admission_module=admission, factory_module=factory, modules=MODULES, data=DATA,
            projector=env.project, renderer=env.renderer(), code_factory=env.code, **env.options())
    def test_complete7345_new_factory_controller_and_seal_connection(self):
        env = fixture_api.Environment(self.fixture, MODULES, DATA, assembler)
        with patch.object(MODULES['host'].os, 'pread', side_effect=AssertionError('authentic array read forbidden')), \
             patch.object(MODULES['code_backend'], 'DockerCodeBackend', side_effect=AssertionError('Docker forbidden')):
            runner = self.build(env)
            result = runner.run()
            self.assertEqual(result['status'], 'complete_unsealed')
            self.assertEqual(result['execution_scope'], 'generated_only')
            self.assertEqual(env.projections, 7345)
            self.assertEqual(env.views, 14690)
            self.assertEqual(env.models, 14690)
            self.assertEqual(env.model_closes, 14690)
            self.assertEqual(env.code_closes, 7345)
            self.assertEqual(env.code_calls, 7345)
            summary = result['delivery_factory_summary']
            self.assertEqual(summary['completed_cases'], 7345)
            self.assertEqual(summary['facade_closures'], 14690)
            self.assertTrue(summary['cache_empty'] and summary['closed'] and summary['all_cases_completed'])
            self.assertFalse(summary['poisoned'] or result['real_participant_backend_qualified'])
            with self.assertRaises(assembler.AssemblyRefusal):
                runner.run()
            sealed = runner.seal(result)
            # Grading is a separate API; this fixture is explicitly fictional.
            result['terminal_snapshots'].clear()
            gc.collect()
            scored = runner.score(sealed)
            report = MODULES['controller'].strict_json(scored['score_report_bytes'])
            self.assertEqual(report['paired_graded_denominator'], 6912)
            self.assertEqual(len(report['recordings']), 171)
            self.assertFalse(report['source_cases_filtered'])
            self.assertFalse(report['biological_person_inference'])
            self.assertEqual(scored['prediction_seal_sha256'], sealed['receipt_sha256'])
    def test_fixed_authentic_entry_and_prospective_environment_refuse_fictional_or_changed_inputs(self):
        f = self.fixture
        with self.assertRaises(admission.AdmissionRefusal):
            admission.admit_release(f.blobs, f.members, modules=MODULES)
        env = fixture_api.Environment(f, MODULES, DATA, assembler)
        options = env.options()
        budget = MODULES['controller'].strict_json(options['budget_bytes'])
        budget['analysis_environment_sha256'] = 'b'*64
        options['budget_bytes'] = MODULES['controller'].canonical(budget)
        with self.assertRaises(assembler.AssemblyRefusal):
            assembler.build_generated_runner(f.blobs, f.members, generated_pins=f.pins,
                admission_module=admission, factory_module=factory, modules=MODULES, data=DATA,
                projector=env.project, renderer=env.renderer(), code_factory=env.code, **options)
        self.assertEqual(env.projections, 0)
    def test_projected_packet_and_default_image_mismatch_invalidates_without_padding(self):
        for mode in ('packet', 'image'):
            env = fixture_api.Environment(self.fixture, MODULES, DATA, assembler, retain=True)
            original = env.project
            def bad_project(*args, **kwargs):
                packet, receipt = original(*args, **kwargs)
                packet['units'] = 'not-source-units'
                return packet, receipt
            renderer = env.renderer()
            if mode == 'packet':
                env.project = bad_project
            else:
                original_renderer = renderer.TraceViewer
                class BadRenderer(original_renderer):
                    def action(self, command):
                        png, receipt = super().action(command)
                        return png+b'changed', receipt
                renderer.TraceViewer = BadRenderer
            f = self.fixture
            runner = assembler.build_generated_runner(f.blobs, f.members, generated_pins=f.pins,
                admission_module=admission, factory_module=factory, modules=MODULES, data=DATA,
                projector=env.project, renderer=renderer, code_factory=env.code, **env.options())
            result = runner.run()
            self.assertEqual(result['status'], 'invalid_incomplete_pair')
            self.assertEqual(len(result['terminal_snapshots']['viewer_only']), 1)
            self.assertEqual(len(result['terminal_snapshots']['code_enabled']), 0)
            self.assertEqual(env.models, 0)
            with self.assertRaises(assembler.AssemblyRefusal):
                runner.seal(result)
            self.assertTrue(env.retained)
