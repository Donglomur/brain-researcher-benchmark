"""Small generated subprocesses only; no source data, networking or native arrays."""
import base64
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from suns2_benchmark.input_process import run_child


class ProcessControls(unittest.TestCase):
    def test_exact_binary_capture_is_lossless(self):
        command = [sys.executable, "-I", "-S", "-B", "-c",
                   "import sys;sys.stdout.buffer.write(bytes([0,255,10]));sys.stderr.buffer.write(b'err')"]
        with tempfile.TemporaryDirectory() as root:
            result = run_child(command, root, seconds=3, capture_bytes=64)
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(base64.b64decode(result["stdout_base64"]), bytes([0,255,10]))
        self.assertEqual(base64.b64decode(result["stderr_base64"]), b"err")
        self.assertTrue(result["capture_complete"])

    def test_real_child_overflow_is_bounded_and_refused(self):
        command = [sys.executable, "-I", "-S", "-B", "-c", "import sys;sys.stdout.write('A'*65)"]
        with tempfile.TemporaryDirectory() as root:
            result = run_child(command, root, seconds=3, capture_bytes=64)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["stdout_captured_bytes"]+result["stderr_captured_bytes"], 64)
        self.assertFalse(result["capture_complete"])
        self.assertEqual(result["stdout_observed_bytes"], 65)
        self.assertIn(result["cleanup"]["status"], {"signal_requests_completed", "cleanup_unverified"})

    def test_owned_timeout_keeps_cleanup_status_and_never_succeeds(self):
        command = [sys.executable, "-I", "-S", "-B", "-c", "import time;time.sleep(10)"]
        with tempfile.TemporaryDirectory() as root:
            result = run_child(command, root, seconds=0.1, capture_bytes=64)
        self.assertEqual(result["status"], "failed")
        self.assertIn("TimeoutExpired", result["error"])
        self.assertIsNotNone(result["cleanup"])
        self.assertIn(result["cleanup"]["status"], {"signal_requests_completed", "cleanup_unverified"})


if __name__ == "__main__":
    unittest.main()
