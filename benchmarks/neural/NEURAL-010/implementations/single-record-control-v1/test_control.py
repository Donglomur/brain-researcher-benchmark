"""Small generated controls only; never invoke worker or scientific imports."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('single_record_control', HERE / 'control.py')
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)
ROOT = Path(os.environ['NEURAL010_SINGLE_CONTROL_TEST_ROOT']).resolve()
ROOT.mkdir()


class Controls(unittest.TestCase):
    def setUp(self):
        self.root = ROOT / self._testMethodName
        self.root.mkdir()

    def test_supervisor_natural_completion(self):
        result = control.run_supervised([sys.executable, '-I', '-B', '-c', 'print("generated")'],
            self.root, self.root / 'output.log', wall_seconds=2, cleanup_seconds=1, log_limit=128)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['exit_code'], 0)
        self.assertEqual((self.root / 'output.log').read_bytes(), b'generated\n')

    def test_wall_deadline_stops_only_owned_child(self):
        result = control.run_supervised([sys.executable, '-I', '-B', '-c', 'import time; time.sleep(5)'],
            self.root, self.root / 'output.log', wall_seconds=0.15, cleanup_seconds=1, log_limit=128)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['reason'], 'worker_wall_deadline')
        self.assertLess(result['wall_seconds'], 1.5)
        self.assertIsNotNone(result['exit_code'])
        self.assertFalse(result['unrelated_processes_signaled'])

    def test_output_overflow_is_bounded_and_fails(self):
        result = control.run_supervised([sys.executable, '-I', '-B', '-c',
            'import os; os.write(1,b"x"*4096)'], self.root, self.root / 'output.log',
            wall_seconds=2, cleanup_seconds=1, log_limit=64)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['reason'], 'worker_output_limit')
        self.assertEqual((self.root / 'output.log').stat().st_size, 64)

    def test_log_creation_is_exclusive(self):
        p = self.root / 'output.log'
        p.write_bytes(b'prior-generated')
        with self.assertRaises(FileExistsError):
            control.run_supervised([sys.executable, '-I', '-B', '-c', 'print("no")'],
                self.root, p, wall_seconds=1, cleanup_seconds=1, log_limit=64)
        self.assertEqual(p.read_bytes(), b'prior-generated')

    def test_read_budget_does_not_admit_excess(self):
        reads = control.Reads()
        reads.reserve('generated bound', control.READ_LIMIT)
        with self.assertRaises(ValueError):
            reads.reserve('excess', 1)
        self.assertEqual(reads.total, control.READ_LIMIT)
        with self.assertRaises(ValueError):
            control.Reads().reserve('boolean', True)

    def test_whole_supervisor_timer_restores_signal_state(self):
        with self.assertRaisesRegex(TimeoutError, 'whole supervisor deadline'):
            with control.whole_attempt_guard(0.05):
                time.sleep(0.5)
        self.assertEqual(control.signal.getitimer(control.signal.ITIMER_REAL), (0.0, 0.0))

    def test_worker_result_capture_requires_reserved_bounded_read(self):
        p = self.root / 'result.generated.json'
        p.write_bytes(b'{"generated":true}\n')
        reads = control.Reads()
        with self.assertRaisesRegex(ValueError, 'reserved before opening'):
            control.capture_worker_result(p, reads)
        reads.reserve('supervisor worker-result capture', control.META_LIMIT + 1)
        self.assertEqual(control.capture_worker_result(p, reads), b'{"generated":true}\n')

    def test_whole_alarm_during_cleanup_cannot_leave_owned_child(self):
        log = self.root / 'output.log'
        command = [sys.executable, '-I', '-B', '-c',
            'import os,signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); print(os.getpid(),flush=True); time.sleep(5)']
        with self.assertRaisesRegex(TimeoutError, 'whole supervisor deadline'):
            with control.whole_attempt_guard(0.15):
                control.run_supervised(command, self.root, log,
                    wall_seconds=0.08, cleanup_seconds=0.25, log_limit=128)
        pid = int(log.read_text().strip())
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)

    def test_source_capture_rejects_dangling_symlink(self):
        p = self.root / 'metadata.generated'
        p.symlink_to(self.root / 'outside.generated')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            control.captured(p, control.pin(b'generated'), control.Reads())
        self.assertFalse((self.root / 'outside.generated').exists())

    def test_source_capture_checks_exact_body_and_uses_no_native_imports(self):
        p = self.root / 'metadata.generated'
        p.write_bytes(b'generated metadata')
        expected = control.pin(p.read_bytes())
        self.assertEqual(control.captured(p, expected, control.Reads()), b'generated metadata')
        with self.assertRaises(ValueError):
            control.captured(p, {**expected, 'sha256': '0' * 64}, control.Reads())
        self.assertNotIn('numpy', sys.modules)
        self.assertNotIn('h5py', sys.modules)
        self.assertEqual(control.PROJECT_LIMIT, 93188096)
        self.assertEqual(control.OUTPUT_LIMIT, 96 * 1048576)


if __name__ == '__main__':
    result = unittest.main(exit=False, verbosity=2).result
    report = {'schema': 'neural010-one-record-generated-supervisor-controls/v1',
        'tests': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
        'scope': 'generated metadata and three tiny stdlib child processes only',
        'authentic_source_or_projection_bodies_read': 0, 'scientific_imports': 0,
        'original_projector_invocations': 0, 'models': 0,
        'retained_fixture_bytes_before_report': sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file())}
    (ROOT / 'RESULT.json').write_text(json.dumps(report, sort_keys=True, indent=2) + '\n')
    sys.exit(not result.wasSuccessful())
