"""Generated process-owner controls; no process is created, waited or signalled."""
from collections import deque
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import signal
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "benchmarks/neural/NEURAL-071/implementations/narratives-programme"
CURRENT = ROOT / "benchmarks/integrity/current-closures/trust-narratives/SOURCE_BINDINGS.json"
NAMESPACE = "_neurobench_narratives_cleanup_test"
package = ModuleType(NAMESPACE)
package.__path__ = [str(PACKAGE / "n071")]
sys.modules[NAMESPACE] = package
runtime = ModuleType(NAMESPACE + ".runtime")
runtime.__file__ = str(PACKAGE / "n071/runtime.py")
runtime.__package__ = NAMESPACE
sys.modules[runtime.__name__] = runtime
# Execute the actual current source bytes, without consulting bytecode caches.
exec(compile(Path(runtime.__file__).read_bytes(), runtime.__file__, "exec"), runtime.__dict__)


class Budget:
    def __init__(self, error=None, fail_at=None):
        self.sequence = 0
        self.checks = 0
        self.error = error
        self.fail_at = fail_at
        self.unknown = []
        self.reservations = []
        self.settlements = []
        self.closed = []

    def reserve(self, *args):
        self.sequence += 1
        self.reservations.append((self.sequence, args))
        return self.sequence

    def reserve_fd(self, *args):
        return self.reserve("fd", *args)

    def attempt(self, *args):
        pass

    def acquired_fd(self, *args):
        pass

    def fd_closed(self, closed):
        self.closed.append(closed)

    def settle(self, token, acknowledged, *, unknown):
        self.settlements.append((token, acknowledged, unknown))

    def checkpoint(self):
        self.checks += 1
        if self.checks == self.fail_at:
            raise self.error
        if self.checks > 20:
            raise AssertionError("Generated control did not terminate")


class Pipe:
    def __init__(self, fd):
        self.fd = fd
        self.closed = False

    def fileno(self):
        return self.fd

    def close(self):
        self.closed = True


class Selector:
    def __init__(self, chunks, events, close_error=None):
        self.mapping = {}
        self.chunks = chunks
        self.events = events
        self.close_error = close_error
        self.closed = False

    def register(self, stream, event, index):
        self.mapping[index] = stream

    def unregister(self, stream):
        index = next(key for key, value in self.mapping.items() if value is stream)
        self.events.append(("eof", index))
        del self.mapping[index]

    def get_map(self):
        return self.mapping

    def select(self, timeout):
        return [(SimpleNamespace(fileobj=stream, data=index), 1)
                for index, stream in self.mapping.items() if self.chunks[stream.fd]]

    def close(self):
        self.closed = True
        if self.close_error:
            raise self.close_error


class Harness:
    def __init__(self, chunks=((), ()), *, error=None, fail_at=None,
                 waits=(), close_error=None, kill_error=None):
        self.events = []
        self.budget = Budget(error, fail_at)
        self.process = SimpleNamespace(pid=55555, stdout=Pipe(31), stderr=Pipe(32), returncode=None)
        self.chunks = {31: deque(chunks[0]), 32: deque(chunks[1])}
        self.selector = Selector(self.chunks, self.events, close_error)
        self.waits = deque(waits)
        self.kill_error = kill_error
        self.owner = runtime.Runtime.__new__(runtime.Runtime)
        self.owner.store = SimpleNamespace(budget=self.budget, root="/not-opened")
        self.owner.process_observations = []
        self.owner.process_records = []
        self.owner.accounting_observations = []

    def wait(self, pid, flags):
        self.events.append(("wait", flags, tuple(self.selector.mapping)))
        if self.waits and not self.waits.popleft():
            return (0, 0, None)
        return (pid, 0, SimpleNamespace(ru_utime=0.01, ru_stime=0.02))

    def kill(self, pid, sig):
        self.events.append(("kill", pid, sig))
        if self.kill_error:
            raise self.kill_error

    def read(self, fd, capacity):
        chunk = self.chunks[fd].popleft()
        if isinstance(chunk, BaseException):
            raise chunk
        if len(chunk) > capacity:
            self.chunks[fd].appendleft(chunk[capacity:])
            chunk = chunk[:capacity]
        return chunk

    def run(self, cap=8):
        with ExitStack() as stack:
            stack.enter_context(patch.object(runtime.subprocess, "Popen", return_value=self.process))
            stack.enter_context(patch.object(runtime.selectors, "DefaultSelector", return_value=self.selector))
            stack.enter_context(patch.object(runtime.os, "set_blocking"))
            stack.enter_context(patch.object(runtime.os, "read", side_effect=self.read))
            stack.enter_context(patch.object(runtime.os, "wait4", side_effect=self.wait))
            stack.enter_context(patch.object(runtime.os, "killpg", side_effect=self.kill))
            return self.owner._process(["/never-executed"], cap)


class NarrativesCleanupTests(unittest.TestCase):
    def assert_closed(self, harness):
        self.assertTrue(harness.process.stdout.closed)
        self.assertTrue(harness.process.stderr.closed)
        self.assertTrue(harness.selector.closed)
        self.assertEqual(harness.budget.closed, [True, True])

    def test_timeout_with_descendant_held_pipes_kills_before_waiting(self):
        original = RuntimeError("clock-budget")
        harness = Harness(error=original, fail_at=2)
        with self.assertRaises(RuntimeError) as caught:
            harness.run()
        self.assertIs(caught.exception, original)
        self.assertEqual(harness.events, [
            ("kill", 55555, signal.SIGKILL), ("wait", 0, (0, 1))])
        self.assertEqual(harness.owner.process_records[0]["eof_observed"], [False, False])
        self.assertTrue(harness.owner.process_records[0]["wait_owned"])
        self.assert_closed(harness)

    def test_one_pipe_eof_does_not_release_original_leader_identity(self):
        original = RuntimeError("clock-budget")
        harness = Harness(((b"",), ()), error=original, fail_at=2)
        with self.assertRaises(RuntimeError) as caught:
            harness.run()
        self.assertIs(caught.exception, original)
        self.assertEqual(harness.events, [
            ("eof", 0), ("kill", 55555, signal.SIGKILL), ("wait", 0, (1,))])
        self.assertEqual(harness.owner.process_records[0]["eof_observed"], [True, False])
        self.assert_closed(harness)

    def test_success_waits_after_both_eofs_and_retains_payload_and_probe_accounting(self):
        harness = Harness(((b"abc", b""), (b"xy", b"")))
        result = harness.run(cap=5)
        self.assertEqual(harness.events, [("eof", 0), ("eof", 1),
                                          ("wait", runtime.os.WNOHANG, ())])
        self.assertEqual((result["stdout"], result["stderr"], result["exit_code"]), (b"abc", b"xy", 0))
        self.assertAlmostEqual(result["wait_cpu_seconds"], 0.03)
        self.assertEqual(result["pipe_observation"], {
            "payload_cap_bytes": 5, "probe_capacity_bytes": 1, "payload_bytes": 5,
            "probe_bytes": 0, "eof_observed": [True, True], "probe_attempts": 2})
        self.assertEqual(harness.budget.settlements, [(1, 5, False), (2, 0, False)])
        self.assert_closed(harness)

    def test_closed_pipes_with_running_leader_continue_bounded_wait(self):
        harness = Harness(((b"",), (b"",)), waits=(False, True))
        result = harness.run()
        self.assertEqual(harness.events, [("eof", 0), ("eof", 1),
            ("wait", runtime.os.WNOHANG, ()), ("wait", runtime.os.WNOHANG, ())])
        self.assertEqual(result["exit_code"], 0)
        self.assert_closed(harness)

    def test_pipe_read_failure_keeps_original_error_and_attempts_group_cleanup(self):
        original = OSError("generated-read-error")
        secondary = PermissionError("generated-kill-error")
        harness = Harness(((original,), ()), kill_error=secondary)
        with self.assertRaises(OSError) as caught:
            harness.run()
        self.assertIs(caught.exception, original)
        self.assertEqual(harness.events, [
            ("kill", 55555, signal.SIGKILL), ("wait", 0, (0, 1))])
        self.assertEqual(harness.owner.process_observations[0].secondary, [("worker-kill", secondary)])
        self.assertEqual(harness.budget.settlements, [(1, 0, True), (2, 0, False)])
        self.assert_closed(harness)

    def test_cleanup_error_after_wait_does_not_signal_reusable_pid(self):
        original = RuntimeError("generated-selector-close-error")
        harness = Harness(((b"",), (b"",)), close_error=original)
        with self.assertRaises(RuntimeError) as caught:
            harness.run()
        self.assertIs(caught.exception, original)
        self.assertEqual(harness.events, [("eof", 0), ("eof", 1),
                                          ("wait", runtime.os.WNOHANG, ())])
        self.assertTrue(harness.owner.process_records[0]["wait_owned"])
        self.assert_closed(harness)

    def test_current_source_set_preserves_predecessor_and_changes_only_runtime(self):
        current = json.loads(CURRENT.read_text())
        predecessor_body = (PACKAGE / "PUBLIC_SOURCE_MANIFEST.json").read_bytes()
        self.assertEqual(hashlib.sha256(predecessor_body).hexdigest(),
                         "1ed3c51ccfaf7150c30c44ff5ad3106bbedbb6a59840c56003d46bc587e6d43b")
        predecessor = json.loads(predecessor_body)
        before = {item["path"]: item for item in predecessor["identity_preimage"]["members"]}
        after = {item["path"]: item for item in current["current_identity_preimage"]["members"]}
        self.assertEqual(set(before), set(after))
        self.assertEqual([name for name in before if before[name] != after[name]], ["n071/runtime.py"])
        for name, record in after.items():
            body = (PACKAGE / name).read_bytes()
            self.assertEqual((len(body), hashlib.sha256(body).hexdigest()),
                             (record["bytes"], record["sha256"]), name)
        canonical = json.dumps(current["current_identity_preimage"], sort_keys=True,
                               separators=(",", ":"), ensure_ascii=True).encode("ascii")
        self.assertEqual(hashlib.sha256(canonical).hexdigest(), current["current_source_set_identity"])
        self.assertNotEqual(current["current_source_set_identity"], predecessor["source_set_identity"])
        self.assertFalse(current["scientific_qualification"])
        self.assertFalse(current["execution_authority"])


if __name__ == "__main__":
    unittest.main()
