"""Generated process-boundary controls: no process or private grader is run."""
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workflow as W


class GraderOwnership(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="sleep007-generated-grader-owner-")
        self.root = Path(self.temp.name).resolve()
        self.request = {"path": str(self.root / "request.json"), "bytes": 1, "sha256": "a" * 64}
        self.signals = []

    def tearDown(self):
        self.temp.cleanup()

    def run_dispatch(self, initial_exit=0, timeout=False, surviving_group=False):
        process = mock.Mock(pid=43210, returncode=None)
        calls = []

        def wait(*, timeout):
            calls.append(timeout)
            if len(calls) == 1 and timeout == 20 and fail_timeout:
                self.assertIsNone(process.returncode)
                raise subprocess.TimeoutExpired("invented trusted grader", 20)
            process.returncode = initial_exit if len(calls) == 1 else process.returncode
            return process.returncode

        def killpg(pid, sig):
            self.assertEqual(pid, process.pid)
            self.signals.append(sig)
            if sig == signal.SIGKILL:
                self.assertIsNone(process.returncode)
                process.returncode = -signal.SIGKILL
            elif not surviving_group:
                raise ProcessLookupError

        fail_timeout = timeout
        process.wait.side_effect = wait
        raw = b'{"status":"valid_descriptive_paired_result","private_loader_calls":1}'
        with mock.patch.object(W.subprocess, "Popen", return_value=process), \
             mock.patch.object(W.os, "killpg", side_effect=killpg), \
             mock.patch.object(W.C, "snapshot", return_value=raw):
            return W.dispatch_grade(self.request, self.root, W.time.monotonic() + 100)

    def test_normal_reaped_leader_only_probed_never_signalled(self):
        result = self.run_dispatch()
        self.assertTrue(result["process_group_closed"])
        self.assertEqual(self.signals, [0])

    def test_nonzero_reaped_leader_not_signalled_or_promoted(self):
        with self.assertRaises(ValueError):
            self.run_dispatch(initial_exit=2)
        self.assertEqual(self.signals, [])

    def test_timeout_retains_child_ownership_signals_then_reaps_and_stays_failure(self):
        with self.assertRaises(subprocess.TimeoutExpired):
            self.run_dispatch(timeout=True)
        self.assertEqual(self.signals, [signal.SIGKILL])

    def test_surviving_or_reused_group_after_reap_fails_without_kill(self):
        with self.assertRaises(ValueError):
            self.run_dispatch(surviving_group=True)
        self.assertEqual(self.signals, [0])


if __name__ == "__main__":
    unittest.main()
