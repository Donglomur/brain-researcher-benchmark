"""Generated source controls; no Docker or authentic neuroscience inputs.

The one tiny Python helper supplies four owned process-lifecycle cases. Its
children remain in the exact new session and are bounded by the tested cleanup.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import time
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location('n031_qualified_backend', HERE / 'docker_backend.py')
db = importlib.util.module_from_spec(spec); spec.loader.exec_module(db)

WRITTEN_CHARGES = []
HELPER = r"""import os, subprocess, sys, time
mode = sys.argv[1]
if mode == 'normal':
    print('ok', flush=True)
elif mode == 'setup':
    time.sleep(30)
else:
    kwargs = {} if mode == 'pipe' else {'stdout': subprocess.DEVNULL, 'stderr': subprocess.DEVNULL}
    child = subprocess.Popen([sys.executable, '-I', '-B', '-c', 'import time; time.sleep(30)'], **kwargs)
    print(child.pid, flush=True)
    os._exit(0)
"""


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='n031-generated-backend-')
        self.root = Path(self.tmp.name)
        self.backends = []
        self.extra_writes = 0

    def tearDown(self):
        # Preserve cumulative writes even though generated fixtures are removed.
        WRITTEN_CHARGES.append(self.extra_writes + sum(x.journal.written for x in self.backends if x.journal))
        self.tmp.cleanup()

    def backend(self, command=None, *, journal=False):
        index = len(self.backends)
        values = {'command': command, 'docker_binary': sys.executable}
        if journal:
            values.update(journal_root=self.root / f'journal{index}', docker_config=self.root / f'config{index}')
        result = db.DockerBackend(**values)
        self.backends.append(result)
        return result

    def image_transport(self, image=db.SELECTED_IMAGE, env=None, arch='arm64'):
        value = [{'Id': image, 'Os': 'linux', 'Architecture': arch,
                  'Config': {'Env': [k + '=' + v for k, v in (env or db.SELECTED_IMAGE_ENV).items()], 'Volumes': None}}]
        return lambda *unused: db.encoded(value)

    def test_exact_selected_image_accepts_only_recorded_three_thread_variables(self):
        backend = self.backend(self.image_transport())
        backend.verify_image(db.SELECTED_IMAGE, db.Deadline())
        overrides = dict(x.split('=', 1) for x in db.ENV)
        for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
            self.assertEqual(backend.image_environment[db.SELECTED_IMAGE][key], '2')
            self.assertEqual(overrides[key], '1')

    def test_selected_image_wrong_arch_or_environment_refused(self):
        cases = [('amd64', dict(db.SELECTED_IMAGE_ENV)), ('arm64', dict(db.SELECTED_IMAGE_ENV, OMP_NUM_THREADS='1')),
                 ('arm64', dict(db.SELECTED_IMAGE_ENV, API_TOKEN='generated-forbidden'))]
        for arch, env in cases:
            with self.subTest(arch=arch, env_keys=tuple(env)):
                backend = self.backend(self.image_transport(env=env, arch=arch))
                with self.assertRaises(ValueError):
                    backend.verify_image(db.SELECTED_IMAGE, db.Deadline())

    def test_other_images_do_not_inherit_thread_variable_allowance(self):
        image = 'sha256:' + 'a' * 64
        backend = self.backend(self.image_transport(image=image))
        with self.assertRaises(ValueError):
            backend.verify_image(image, db.Deadline())

    def test_empty_streams_private_pins_and_simulation_scope(self):
        backend = self.backend(lambda *unused: b'', journal=True)
        self.assertEqual(backend._command(['generated'], db.Deadline(), 4096), b'')
        rows = backend.journal_records
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]['simulated'])
        for key in ('stdout', 'stderr'):
            desc = rows[0][key]
            path = backend.journal.root / desc['path']
            self.assertEqual(desc['bytes'], 0)
            self.assertEqual(desc['sha256'], hashlib.sha256(b'').hexdigest())
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(backend.journal.root.stat().st_mode), 0o700)
        self.assertFalse(backend.journal_summary()['actual_cli_closure_complete'])
        self.assertEqual(list(backend.config.iterdir()), [])

    def test_complete_command_budget_includes_failure_recovery(self):
        # One image inspection, ten commands/context, forty final absence checks.
        context_caps = [4096, 4096, 4096, 65536, 16384, 4096, 65536, 262144, 4096, 4096]
        normal = [65536] + context_caps * 40 + [4096] * 40
        recovery = [4096, 65536, 4096, 4096]
        self.assertEqual(len(normal), 441)
        self.assertLessEqual(len(normal + recovery), db.COMMAND_CAP)
        self.assertLessEqual(sum(cap + 4096 + db.INTENT_CAP + db.RESULT_CAP for cap in normal + recovery), db.JOURNAL_CAP)

    def test_journal_capacity_refuses_before_process_or_transport_launch(self):
        calls = []
        backend = self.backend(lambda *args: calls.append(args) or b'', journal=True)
        backend.journal.granted = db.JOURNAL_CAP - 1
        with self.assertRaises(ValueError):
            backend._command(['generated'], db.Deadline(), 4096)
        self.assertEqual(calls, [])
        self.assertTrue(backend._journal_failed)

    def test_evidence_failure_allows_only_failure_cleanup_and_blocks_grade(self):
        calls = []
        backend = self.backend(lambda *args: calls.append(args) or b'', journal=True)
        backend._in_recovery = True
        with mock.patch.object(backend.journal, 'begin', side_effect=OSError('generated journal failure')):
            self.assertEqual(backend._command(['rm', '--force', 'generated-owned-name'], db.Deadline(), 4096), b'')
        self.assertEqual(len(calls), 1)
        self.assertTrue(backend._journal_failed)
        backend._in_recovery = False
        with self.assertRaises(ValueError):
            backend.absent_all(db.Deadline())
        self.assertFalse(backend.journal_summary()['actual_cli_closure_complete'])

    def test_normal_evidence_failure_prevents_command_launch(self):
        calls = []
        backend = self.backend(lambda *args: calls.append(args) or b'', journal=True)
        with mock.patch.object(backend.journal, 'begin', side_effect=OSError('generated journal failure')):
            with self.assertRaises(OSError):
                backend._command(['generated'], db.Deadline(), 4096)
        self.assertEqual(calls, [])

    def test_shared_failure_clock_does_not_add_ten_seconds_per_command(self):
        class Clock:
            now = 100.0
            def __call__(self): return self.now
        clock = Clock()
        backend = self.backend(lambda *unused: b'')
        whole = db.Deadline(clock=clock, seconds=480)
        clock.now = 581.0
        first = backend.recovery_deadline(whole)
        self.assertEqual(first.end, 590.0)
        clock.now = 585.0
        self.assertIs(backend.recovery_deadline(whole), first)
        self.assertEqual(first.end, 590.0)

    def test_poisoned_backend_cannot_resume_normal_work_but_can_clean_up(self):
        for flag in ('_unknown_cli_closure', '_journal_failed'):
            calls = []
            backend = self.backend(lambda *args: calls.append(args) or b'')
            setattr(backend, flag, True)
            with self.assertRaises(ValueError):
                backend._command(['generated-normal'], db.Deadline(), 4096)
            self.assertEqual(calls, [])
            backend._in_recovery = True
            self.assertEqual(backend._command(['generated-owned-cleanup'], db.Deadline(), 4096), b'')
            self.assertEqual(len(calls), 1)
            self.assertFalse(backend.journal_summary()['actual_cli_closure_complete'])

    def real_fixture(self):
        path = self.root / 'generated_cli.py'
        path.write_text(HELPER)
        self.extra_writes += len(HELPER.encode())
        backend = self.backend(None, journal=True)
        # Explicit generated test seam; no Docker executable is invoked.
        backend.prefix = [sys.executable, '-I', '-B', str(path)]
        return backend

    def result(self, backend):
        rows = backend.journal_records
        self.assertEqual(len(rows), 1)
        row = rows[0]
        body = (backend.journal.root / row['result']['path']).read_bytes()
        self.assertEqual(hashlib.sha256(body).hexdigest(), row['result']['sha256'])
        return json.loads(body)

    def test_real_generated_normal_cli_is_reaped_and_journaled(self):
        backend = self.real_fixture()
        self.assertEqual(backend._command(['normal'], db.Deadline(seconds=3), 4096), b'ok\n')
        result = self.result(backend)
        self.assertTrue(result['direct_child_reaped'])
        self.assertTrue(result['group_absent'])
        self.assertIsNone(result['error_type'])
        self.assertTrue(backend.journal_summary()['actual_cli_closure_complete'])

    def test_selector_setup_failure_still_closes_created_group(self):
        backend = self.real_fixture()
        with mock.patch.object(db.selectors, 'DefaultSelector', side_effect=OSError('generated selector failure')):
            with self.assertRaises(OSError):
                backend._command(['setup'], db.Deadline(seconds=3), 4096)
        result = self.result(backend)
        self.assertTrue(result['direct_child_reaped'])
        self.assertTrue(result['group_absent'])
        self.assertIn('SIGKILL_owned_group', result['cleanup'])
        self.assertEqual(result['error_type'], 'OSError')

    def assert_orphan_closed(self, mode, expected_error):
        backend = self.real_fixture()
        with self.assertRaises(expected_error):
            backend._command([mode], db.Deadline(seconds=0.4), 4096)
        result = self.result(backend)
        self.assertTrue(result['direct_child_reaped'])
        self.assertIn('SIGKILL_owned_group', result['cleanup'])
        self.assertTrue(result['group_absent'], 'Generated orphan group remains unknown; preserve this failure')
        self.assertFalse(backend.journal_summary()['actual_cli_closure_complete'])
        self.assertIsNotNone(result['error_type'])

    def test_exited_leader_pipe_holding_child_cannot_escape_cleanup(self):
        self.assert_orphan_closed('pipe', TimeoutError)

    def test_exited_leader_silent_child_cannot_escape_cleanup(self):
        self.assert_orphan_closed('silent', ValueError)


if __name__ == '__main__':
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.defaultTestLoader.loadTestsFromTestCase(BackendTests))
    print(json.dumps({'generated_fixture_cumulative_write_charge_bytes': sum(WRITTEN_CHARGES),
                      'real_owned_process_fixture_cases': 4, 'Docker_calls': 0,
                      'authentic_data_reads': 0, 'fixtures_removed': True}, sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)
