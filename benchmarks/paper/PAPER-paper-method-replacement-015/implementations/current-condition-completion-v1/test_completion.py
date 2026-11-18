"""Generated full-scope composition and trusted-process observer controls."""
import builtins
from copy import deepcopy
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('_spinal_new_run_test', HERE / 'run.py')
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)
own = run.local_modules()
s, profile, observer = own.source, own.profile, own.observer


def plan(root=Path('/operator/generated')):
    return {'schema': 'spinal_current_completion_plan_v1',
            'scope': 'fixed_one_hz_nonlearning_engineering_pair',
            'bank': str(root / 'bank'), 'assets': str(root / 'assets'),
            'output': str(root / 'attempt'), 'docker': '/usr/local/bin/docker',
            'docker_socket': str(root / 'socket'), 'bank_manifest_sha256': s.BANK_SHA,
            'image': s.IMAGE, 'purpose': 'reproduction', 'output_unit': 'hz',
            'candidate_seconds': 5, 'memory_bytes': 536870912,
            'campaign_seconds': 1800, 'other_reserve_bytes': 0}


def load():
    return s.load_source(s.pin((HERE / 'SOURCE.json').read_bytes())['sha256'])


class ProfileAndSource(unittest.TestCase):
    def test_source_loader_ignores_ambient_local_modules(self):
        sentinel = object()
        with patch.dict(sys.modules, {name: sentinel for name in ('contract', 'materials', 'collect', 'transport')}):
            loaded = load()
            self.assertIs(loaded.transport.c, loaded.contract)
            self.assertIs(loaded.transport.materials, loaded.materials)
            self.assertIs(loaded.transport.collector, loaded.collector)
            self.assertIs(sys.modules['contract'], sentinel)
        self.assertEqual(loaded.delivery_pin['sha256'], s.BASE_SHA)

    def test_aggregate_cap_retains_individual_and_full_scope(self):
        loaded = load()
        p = plan()
        original = loaded.transport.runtime_selection(5, 536870912, 0)
        selected = profile.runtime(p, loaded.transport, loaded.completion_pin, {'bytes': 2, 'sha256': 'a'*64},
                                   deadline=1900., now=100.)
        for key in ('candidate_seconds', 'memory_bytes', 'per_fold_wall_seconds',
                    'folds_per_arm', 'arms', 'retained_limit_bytes', 'read_limit_bytes', 'write_limit_bytes'):
            self.assertEqual(selected[key], original[key])
        self.assertEqual(selected['worker_wall_seconds'], 1740)
        self.assertTrue(selected['all_88_contexts_required'])
        self.assertFalse(selected['partial_success_allowed'])
        self.assertLess(selected['worker_wall_seconds'], original['worker_wall_seconds'])

    def test_stale_future_or_incomplete_remaining_window_refused(self):
        loaded = load()
        for deadline, now in [(500., 100.), (1901., 100.),
                              (math.nextafter(1900., math.inf), 100.),
                              (float('inf'), 0.), (0., 1.)]:
            with self.subTest(deadline=deadline), self.assertRaises(ValueError):
                profile.runtime(plan(), loaded.transport, loaded.completion_pin, {}, deadline=deadline, now=now)

    def test_plan_cannot_change_bank_image_units_scope_or_types(self):
        for name, value in [('bank_manifest_sha256', '0'*64), ('image', 'latest'),
                            ('output_unit', 'expected_spikes_per_bin'), ('scope', 'model_episode'),
                            ('candidate_seconds', True), ('campaign_seconds', 600),
                            ('other_reserve_bytes', -1), ('assets', '/tmp/../private')]:
            p = plan(); p[name] = value
            with self.subTest(name=name), self.assertRaises(ValueError):
                profile.validate(p)


class ObserverControls(unittest.TestCase):
    def test_real_owned_generated_child_preserves_both_streams_and_exit(self):
        out, err, record = observer.observe([sys.executable, '-I', '-S', '-B', '-c',
                "import sys; print('generated'); print('diagnostic',file=sys.stderr)"],
                time.monotonic()+60, os.environ.copy())
        self.assertEqual(out, b'generated\n'); self.assertEqual(err, b'diagnostic\n')
        self.assertTrue(record['natural_exit'] and record['process_reaped'] and record['owned_host_group_absent'])
        self.assertFalse(record['container_absence_inferred'])

    def test_real_nonzero_child_retains_failure_diagnostic(self):
        with self.assertRaises(observer.Failure) as seen:
            observer.observe([sys.executable, '-I', '-S', '-B', '-c',
                    "import sys; print('preserve-me',file=sys.stderr); sys.exit(7)"],
                    time.monotonic()+60, os.environ.copy())
        failure = seen.exception
        self.assertEqual(failure.stderr, b'preserve-me\n')
        self.assertEqual(failure.observation['exit_code'], 7)
        self.assertTrue(failure.observation['process_reaped'])

    def test_oversized_trusted_stream_fails_with_bounded_retention(self):
        with self.assertRaises(observer.Failure) as seen:
            observer.observe([sys.executable, '-I', '-S', '-B', '-c',
                    "import sys; sys.stdout.write('x'*70000)"],
                    time.monotonic()+60, os.environ.copy())
        self.assertEqual(len(seen.exception.stdout), observer.PIPE_CAP)
        self.assertTrue(seen.exception.observation['process_reaped'])
        self.assertTrue(seen.exception.observation['owned_host_group_absent'])


class OuterFailureControls(unittest.TestCase):
    def test_failed_worker_cannot_publish_host_completion(self):
        loaded = load()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); p = plan(root)
            failure = observer.Failure({'exit_code': 7, 'process_reaped': True}, b'partial\n', b'reason\n')
            with patch.object(observer, 'observe', side_effect=failure), \
                 patch('shutil.disk_usage', return_value=types.SimpleNamespace(free=2**60)), \
                 self.assertRaises(observer.Failure):
                run.outer(p, s.encoded(p), loaded, own, time.monotonic())
            attempt = root/'attempt'
            self.assertEqual((attempt/'worker.stderr').read_bytes(), b'reason\n')
            self.assertTrue((attempt/'FAILED.json').exists())
            self.assertFalse((attempt/'HOST_EXIT.json').exists())
            self.assertFalse((attempt/'campaign').exists())

    def test_aliasing_inputs_as_output_refused_before_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); p = plan(root); p['output'] = str(root)
            body = s.encoded(p); target=root/'plan.json'; target.write_bytes(body)
            with self.assertRaisesRegex(ValueError, 'separate protected'):
                run.load_plan(target, s.pin(body)['sha256'], s, profile)


class FullScopeAggregateControl(unittest.TestCase):
    def test_all_88_old_lifecycle_joins_under_new_aggregate_profile(self):
        """One changed-profile composition run; lifecycle and tiny data invented."""
        loaded = load()
        modules = {'contract': loaded.contract, 'materials': loaded.materials, 'transport': loaded.transport}
        ordinary = builtins.__import__
        def bound(name, globals=None, locals=None, fromlist=(), level=0):
            if level == 0 and name in modules:
                return modules[name]
            return ordinary(name, globals, locals, fromlist, level)
        for name in ('test_materials', 'test_transport'):
            module = types.ModuleType('_spinal_completion_fixture_'+name)
            module.__file__ = str(s.BASE/(name+'.py'))
            module.__dict__['__builtins__'] = dict(vars(builtins), __import__=bound)
            exec(compile((s.BASE/(name+'.py')).read_bytes(), module.__file__, 'exec'), module.__dict__)
            modules[name] = module
        case = modules['test_transport'].CampaignControls()
        case.setUp()
        try:
            p = plan(case.root)
            p['purpose'] = 'improvement'  # Same declaration as the existing fixture's seal.
            # Keep the exact-endpoint fixture independent of host clock rounding.
            now = 100.0
            case.runtime = profile.runtime(p, loaded.transport, loaded.completion_pin, s.pin(s.encoded(p)),
                                           deadline=now+1800, now=now)
            # A stricter generated-fixture cap bounds cumulative writes without
            # changing the prospective authentic protocol or scientific inputs.
            with patch.object(loaded.transport, 'WRITES', 64*1024**2):
                result = case.run_campaign()
            self.assertEqual(len(case.calls), 88)
            self.assertEqual(len(set(case.calls)), 88)
            self.assertTrue(result['same_data_across_arms'])
            self.assertEqual(result['eligible_recordings'], 116)
            self.assertEqual(result['required_neurons'], 44)
            self.assertEqual(result['selected_fold_seconds'], 88*425)
            self.assertFalse(result['scientific_scoring_performed'])
            print('generated_full_campaign_managed_write_charge_bytes=',
                  result['budget']['precharged_managed_write_bytes'])
            for arm in loaded.contract.ARMS:
                self.assertEqual(result['arms'][arm]['folds'], 44)
                self.assertEqual(result['arms'][arm]['eligible_recordings'], 116)
        finally:
            case.doCleanups()


if __name__ == '__main__':
    unittest.main()
