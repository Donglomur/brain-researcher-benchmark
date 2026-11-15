"""One bounded invented-only source suite. No authentic input is opened."""
import io
import json
from pathlib import Path
import resource
import signal
import sys
import time
import unittest

START = time.monotonic()
signal.alarm(29)
resource.setrlimit(resource.RLIMIT_CPU, (25, 25))
if sys.flags.optimize != 0:
    raise RuntimeError("Controls require optimization off")


class LimitedLog(io.StringIO):
    def write(self, value):
        if self.tell() + len(value) > 65536:
            raise RuntimeError("Control log exceeds 64 KiB")
        return super().write(value)


root = Path(__file__).resolve().parent
sys.path.insert(0, str(root))
suite = unittest.defaultTestLoader.loadTestsFromName("test_occurrence_adapter")
if suite.countTestCases() != 27:
    raise RuntimeError("Exact 27-test suite required")
log = LimitedLog()
result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
success = result.wasSuccessful() and result.testsRun == 27 and not result.skipped
print(json.dumps({
    "schema": "consensus-occurrence-invented-control-result-v1",
    "tests": result.testsRun, "failures": len(result.failures),
    "errors": len(result.errors), "skipped": len(result.skipped),
    "status": "pass" if success else "fail",
    "test_log": log.getvalue(), "owner_seconds": time.monotonic() - START,
    "authentic_inputs": 0, "native_deserializations": 0, "fits": 0,
    "network": 0, "model_calls": 0, "scientific_qualification": False,
    "benchmark_count_delta": 0,
    "timing_scope": "Alarm starts after stdlib imports; interpreter bootstrap is not independently bounded.",
    "hard_RSS_or_CPU_affinity_claimed": False,
}, sort_keys=True))
sys.exit(0 if success else 1)
