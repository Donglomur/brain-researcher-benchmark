"""One mock-only cleanup-denial control; no processes or signals are launched."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import signal
import subprocess
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("nuclr_backend_cleanup_under_test", HERE / "backend_direct.py")
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)
FIXTURES = None

class CleanupDenialControl(unittest.TestCase):
    def test_group_signal_denial_stops_signalling_preserves_failure_and_reaps(self):
        for denied_signal, reap_timeout in ((signal.SIGTERM, False), (signal.SIGKILL, True)):
            with self.subTest(denied_signal=denied_signal, reap_timeout=reap_timeout):
                events = []
                class StreamDouble:
                    def close(self):
                        events.append(("close",))
                class ProcessDouble:
                    pid = 424242
                    returncode = None
                    stdout = StreamDouble()
                    def wait(self, timeout):
                        events.append(("wait", timeout))
                        if reap_timeout:
                            raise subprocess.TimeoutExpired("generated-process-double", timeout)
                        self.returncode = 0
                        return 0
                    def send_signal(self, *args):
                        raise AssertionError("No alternate per-process signal after denial")
                    def terminate(self):
                        raise AssertionError("No alternate terminate after denial")
                    def kill(self):
                        raise AssertionError("No alternate kill after denial")
                class SelectorDouble:
                    def __enter__(self):
                        return self
                    def __exit__(self, *args):
                        return False
                    def register(self, *args):
                        pass
                    def get_map(self):
                        return {}
                def group_signal(pid, sig):
                    self.assertEqual(pid, 424242)
                    events.append(("signal", sig))
                    if sig == denied_signal:
                        raise PermissionError(1, "generated signal permission denial")
                root = FIXTURES / ("term-denied" if denied_signal == signal.SIGTERM else "kill-denied")
                root.mkdir()
                output = root / "empty.log"
                process = ProcessDouble()
                with mock.patch.object(driver.subprocess, "Popen", return_value=process), mock.patch.object(driver.selectors, "DefaultSelector", return_value=SelectorDouble()), mock.patch.object(driver.os, "killpg", side_effect=group_signal), mock.patch.object(driver.os, "kill", side_effect=AssertionError("No alternate os.kill")), mock.patch.object(driver.signal, "signal", return_value=signal.SIG_DFL), mock.patch.object(driver.time, "sleep"):
                    result = driver.run_owned(["generated-double-never-executed"], str(root), {}, output, 7, 64)
                expected = [("signal", signal.SIGTERM)]
                if denied_signal == signal.SIGKILL:
                    expected.append(("signal", signal.SIGKILL))
                expected.extend([("wait", 3), ("close",)])
                self.assertEqual(events, expected)
                self.assertIsInstance(result["cleanup_error"], str)
                self.assertTrue(result["cleanup_error"])
                self.assertIn("deni", result["cleanup_error"].lower())
                self.assertEqual(result["pid"], 424242)
                self.assertIs(result["leader_reaped"], not reap_timeout)
                self.assertEqual(result["exit_code"], None if reap_timeout else 0)
                if reap_timeout:
                    self.assertIn("reap", result["cleanup_error"].lower())
                self.assertEqual(result["output_bytes"], 0)
                self.assertEqual(output.read_bytes(), b"")
                self.assertEqual(result["log"], {"bytes": 0, "sha256": hashlib.sha256(b"").hexdigest()})
                # Even a successful ordinary wait does not erase denied cleanup.
                self.assertFalse(result["cleanup_error"] is None)

def main():
    global FIXTURES
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, required=True)
    args = parser.parse_args()
    FIXTURES = args.fixtures
    if not FIXTURES.is_absolute() or FIXTURES.exists() or FIXTURES.is_symlink():
        raise ValueError("Use an absolute new fixture root")
    FIXTURES.parent.mkdir(parents=True, exist_ok=True)
    FIXTURES.mkdir()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CleanupDenialControl))
    print("MOCK_CLEANUP_ACCOUNTING=" + json.dumps({"methods": 1, "subcases": 2, "fixture_cumulative_bytes": 0, "empty_regular_logs": 2, "scope": "Popen, group/individual signals and selector mocked; no process or signal launched"}, sort_keys=True))
    return 0 if result.wasSuccessful() and not result.skipped else 1

if __name__ == "__main__":
    raise SystemExit(main())
