"""Run the 53 invented Retina construction controls on a Unix Python runtime."""
import contextlib
import io
import json
from pathlib import Path
import resource
import signal
import sys
import time
import unittest

EXPECTED_TESTS = 53
LOG_CAP_BYTES = 65536
OUTPUT_CAP_BYTES = 131072


class BoundedLog(io.StringIO):
    def __init__(self):
        super().__init__()
        self.bytes_written = 0

    def write(self, text):
        size = len(text.encode("utf-8"))
        if self.bytes_written + size > LOG_CAP_BYTES:
            raise RuntimeError("Control log exceeds 64 KiB")
        self.bytes_written += size
        return super().write(text)


def main():
    if sys.flags.optimize:
        raise RuntimeError("Controls require optimization off")
    start = time.monotonic()
    resource.setrlimit(resource.RLIMIT_CPU, (30, 32))
    resource.setrlimit(resource.RLIMIT_FSIZE, (OUTPUT_CAP_BYTES, OUTPUT_CAP_BYTES))
    signal.signal(signal.SIGALRM, signal.SIG_DFL)
    signal.alarm(30)
    log = BoundedLog()
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            loader = unittest.TestLoader()
            suite = loader.loadTestsFromName("test_retina_construction")
            if loader.errors or suite.countTestCases() != EXPECTED_TESTS:
                raise RuntimeError("Exactly 53 loadable controls are required")
            result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
        success = (result.wasSuccessful() and result.testsRun == EXPECTED_TESTS
                   and not result.skipped and not result.expectedFailures
                   and not result.unexpectedSuccesses)
        report = {
            "schema": "retina-construction-invented-controls-v1",
            "status": "pass" if success else "fail",
            "tests": result.testsRun, "failures": len(result.failures),
            "errors": len(result.errors), "skipped": len(result.skipped),
            "expected_failures": len(result.expectedFailures),
            "unexpected_successes": len(result.unexpectedSuccesses),
            "test_log": log.getvalue(), "elapsed_seconds": time.monotonic() - start,
            "scientific_qualification": False,
            "scope": "Invented offline records and temporary bytes only.",
            "timing_scope": "30-second alarm starts after standard-library imports; CI supplies a separate outer deadline.",
        }
        body = (json.dumps(report, sort_keys=True, allow_nan=False) + "\n").encode()
        if len(body) > OUTPUT_CAP_BYTES:
            raise RuntimeError("Serialized control result exceeds 128 KiB")
        sys.stdout.buffer.write(body)
        return 0 if success else 1
    finally:
        signal.alarm(0)


if __name__ == "__main__":
    raise SystemExit(main())
