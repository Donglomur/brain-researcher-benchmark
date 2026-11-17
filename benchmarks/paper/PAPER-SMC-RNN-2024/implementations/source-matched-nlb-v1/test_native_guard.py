"""Generated owned-process controls; never touch the shared resource ledger."""
import contextlib
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import native_guard


class NativeGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.processes = []

    def tearDown(self):
        for child in self.processes:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=5)
            if child.stdout:
                child.stdout.close()
        self.temp.cleanup()

    def child(self, *, ignore_term=False, ram_limit=8 * 1024**3):
        script = self.root / 'author_predict.py'
        script.write_text('import signal,time\n'
                          + ('signal.signal(signal.SIGTERM,signal.SIG_IGN)\n' if ignore_term else '')
                          + "print('ready',flush=True)\ntime.sleep(30)\n")
        child = subprocess.Popen([sys.executable, str(script)], start_new_session=True,
                                 stdout=subprocess.PIPE, text=True)
        self.processes.append(child)
        self.assertEqual(child.stdout.readline().strip(), 'ready')
        row = dict(id='smc-full-generated-test', owner='smc', child_pid=child.pid,
                   coordinator_pid=os.getpid(), status='running', command=[sys.executable,str(script)],
                   started_utc=datetime.now(timezone.utc).isoformat(),
                   declared_max_working_ram_bytes=ram_limit)
        ledger = self.root / 'ledger.json'
        ledger.write_text(json.dumps({'native_runs':[row]}))
        return child, row, ledger, self.root / 'receipt.json'

    def run_guard(self, ledger, output, wall=10):
        with contextlib.redirect_stdout(io.StringIO()):
            return native_guard.guard(ledger, 'smc-full-generated-test', output, wall)

    def test_wall_deadline_escalates_owned_sigterm_ignoring_child(self):
        child, row, ledger, output = self.child(ignore_term=True)
        start = time.monotonic()
        result = self.run_guard(ledger, output, wall=0.1)
        child.wait(timeout=3)
        self.assertEqual(child.returncode, -signal.SIGKILL)
        self.assertEqual(result['termination_reason'], 'wall_deadline')
        self.assertTrue(result['sigkill_sent'])
        self.assertGreaterEqual(time.monotonic()-start, native_guard.TERM_GRACE_SECONDS)
        self.assertLess(time.monotonic()-start, 9)
        self.assertGreater(result['guard_child_cpu_seconds'], 0)
        self.assertEqual(json.loads(output.read_text())['error'], None)

    def test_rss_limit_terminates_owned_child_without_escalation(self):
        child, row, ledger, output = self.child(ram_limit=1)
        result = self.run_guard(ledger, output)
        child.wait(timeout=3)
        self.assertEqual(child.returncode, -signal.SIGTERM)
        self.assertEqual(result['termination_reason'], 'rss_limit')
        self.assertFalse(result['sigkill_sent'])
        self.assertGreater(result['peak_observed_rss_bytes'], 1)

    def test_wrong_coordinator_never_signals_live_process(self):
        child, row, ledger, output = self.child(ram_limit=1)
        row['coordinator_pid'] += 1
        ledger.write_text(json.dumps({'native_runs':[row]}))
        with self.assertRaisesRegex(RuntimeError, 'identity'):
            self.run_guard(ledger, output)
        self.assertIsNone(child.poll())
        self.assertEqual(json.loads(output.read_text())['exit_reason'], 'guard_error')

    def test_pid_identity_change_before_signal_is_rejected(self):
        child, row, ledger, output = self.child(ram_limit=1)
        original = native_guard.process_snapshot
        calls = 0
        def recycled(pid):
            nonlocal calls
            calls += 1
            result = original(pid)
            if calls > 1:
                result['started'] = 'different process start'
            return result
        with mock.patch.object(native_guard, 'process_snapshot', side_effect=recycled):
            with self.assertRaisesRegex(RuntimeError, 'PID identity changed'):
                self.run_guard(ledger, output)
        self.assertIsNone(child.poll())
        self.assertFalse(json.loads(output.read_text())['sigkill_sent'])

    def test_changed_lease_limit_before_signal_is_rejected(self):
        child, row, ledger, output = self.child(ram_limit=1)
        original = native_guard.process_snapshot
        def mutate(pid):
            result = original(pid)
            changed = dict(row, declared_max_working_ram_bytes=2)
            ledger.write_text(json.dumps({'native_runs':[changed]}))
            return result
        with mock.patch.object(native_guard, 'process_snapshot', side_effect=mutate):
            with self.assertRaisesRegex(RuntimeError, 'lease identity changed'):
                self.run_guard(ledger, output)
        self.assertIsNone(child.poll())

    def test_completed_lease_does_not_signal_live_process(self):
        child, row, ledger, output = self.child(ram_limit=1)
        row['status'] = 'succeeded'
        ledger.write_text(json.dumps({'native_runs':[row]}))
        result = self.run_guard(ledger, output)
        self.assertIsNone(child.poll())
        self.assertEqual(result['exit_reason'], 'lease_completed')
        self.assertIsNone(result['termination_reason'])

    def test_cli_identity_failure_is_nonzero_and_preserves_receipt(self):
        child, row, ledger, output = self.child(ram_limit=1)
        row['coordinator_pid'] += 1
        ledger.write_text(json.dumps({'native_runs':[row]}))
        command = [sys.executable, str(Path(native_guard.__file__)),
                   '--ledger', str(ledger), '--run-id', row['id'],
                   '--output', str(output), '--wall-seconds', '10']
        result = subprocess.run(command, capture_output=True, text=True, timeout=5)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(output.read_text())['exit_reason'], 'guard_error')
        self.assertIn('no signal sent', result.stderr)
        self.assertIsNone(child.poll())

    def test_refuses_deadline_beyond_prospective_limit(self):
        with self.assertRaises(ValueError):
            self.run_guard(self.root/'unused', self.root/'unused-output', wall=7200)


if __name__ == '__main__':
    unittest.main()
