"""24KiB reserved fake-observation controls; zero real processes/procfs reads.

All process, selector, pipe-read, clock and namespace observations are doubles.
No Docker, provider, data, model or child/group signal is run. No fixture files.
"""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from adapters import process as m
from adapters.common import AdapterError


class Budget:
    origin_monotonic = -1.0
    deadline_monotonic = 10.0
    def __init__(self): self.used = {}
    def check_clock(self): pass
    def charge(self, name, amount=1): self.used[name] = self.used.get(name, 0) + amount


class Pipe:
    def __init__(self, fd): self.fd, self.closed = fd, False
    def fileno(self): return self.fd
    def close(self): self.closed = True


class Clock:
    def __init__(self, sequence=None): self.value, self.sequence = 0.0, list(sequence or [])
    def now(self):
        if self.sequence: self.value = self.sequence.pop(0)
        return self.value


class Child:
    pid = 321
    def __init__(self, clock, code=0, wait_time=None):
        self.stdout, self.stderr = Pipe(501), Pipe(502)
        self.clock, self.code, self.wait_time = clock, code, wait_time
        self.wait_calls = 0
    def poll(self): return self.code
    def wait(self, timeout):
        self.wait_calls += 1
        if self.wait_time is not None: self.clock.value = self.wait_time
        return self.code


class Selector:
    def __init__(self, clock, stall=False): self.clock, self.stall, self.rows, self.closed = clock, stall, {}, False
    def register(self, pipe, events, name): self.rows[pipe.fd] = SimpleNamespace(fileobj=pipe, data=name)
    def unregister(self, pipe): del self.rows[pipe.fd]
    def get_map(self): return self.rows
    def select(self, timeout):
        if self.stall: self.clock.value = 2.0; return []
        return [(row, 1) for row in list(self.rows.values())]
    def close(self): self.closed = True


class ObserverControls(unittest.TestCase):
    def tearDown(self):
        # This module can contain only these fake children; do not copy this
        # test-only clearing operation into the production inspection API.
        m._UNRESOLVED.clear()

    def invoke(self, *, code=0, group="absent", identity=True, stall=False,
               stdout=b"", cap=16, wait_time=None, clock_sequence=None):
        clock = Clock(clock_sequence); child = Child(clock, code, wait_time)
        selector = Selector(clock, stall)
        chunks = {501: [stdout, b""] if stdout else [b""], 502: [b""]}
        captured = {"state": "present", "pid": 321, "parent_pid": 99,
                    "process_group": 321, "session": 321, "birth_ticks": 17}
        if not identity: captured = {"state": "absent"}
        group_record = {"state": group, "members": [] if group == "absent" else [{"pid": 654}],
                        "reason": "invented_reused_or_unknown" if group == "unknown" else "invented_snapshot"}
        with patch.object(m, "preflight_observer_namespace", return_value={"invented_supported_namespace": True}), \
             patch.object(m, "_read_process_identity", return_value=captured), \
             patch.object(m, "observe_process_group", return_value=group_record), \
             patch.object(m.subprocess, "Popen", return_value=child), \
             patch.object(m.selectors, "DefaultSelector", return_value=selector), \
             patch.object(m.os, "set_blocking"), patch.object(m.os, "getpid", return_value=99), \
             patch.object(m.os, "read", side_effect=lambda fd, n: chunks[fd].pop(0)), \
             patch.object(m.time, "monotonic", side_effect=clock.now):
            try:
                result = m.ProcessObserver().run(["/invented/python", "invented"], cwd="/invented", env={},
                    budget=Budget(), seconds=1, cleanup_seconds=0.1, stream_cap=cap)
                return result["observation"], child, None
            except AdapterError as exc:
                return exc.evidence, child, exc

    def assert_refused(self, result):
        observation, child, error = result
        self.assertIsInstance(error, AdapterError)
        self.assertTrue(observation["separate_authorized_inspection_required"])
        self.assertFalse(observation["child_mutation_attempted"])
        self.assertEqual(observation["quarantine_persistence"], "process_local_not_durable_across_interpreter_exit")
        self.assertIn(observation["quarantine_token"], m._UNRESOLVED)
        return observation, child

    def test_01_exact_zero_eof_absent_group_on_time_passes(self):
        observation, child, error = self.invoke()
        self.assertIsNone(error)
        self.assertIs(type(observation["natural_exit_code"]), int)
        self.assertEqual(observation["natural_exit_code"], 0)
        self.assertTrue(observation["streams_closed"] and observation["process_group_absent"])
        self.assertFalse(observation["separate_authorized_inspection_required"])
        self.assertLessEqual(observation["ended_monotonic"], observation["normal_deadline_monotonic"])

    def test_02_leader_zero_residual_group_refuses(self):
        observation, _ = self.assert_refused(self.invoke(group="present"))
        self.assertEqual(observation["natural_exit_code"], 0)
        self.assertFalse(observation["process_group_absent"])

    def test_03_already_reaped_or_reused_identity_refuses_without_action(self):
        for kwargs in ({"identity": False}, {"group": "unknown"}):
            observation, child = self.assert_refused(self.invoke(**kwargs))
            self.assertEqual(observation["observed_leader_exit_code"], 0)
            if not kwargs.get("identity", True):
                self.assertFalse(child.stdout.closed or child.stderr.closed)

    def test_04_timeout_retains_unknown_survivor_handles(self):
        observation, child = self.assert_refused(self.invoke(code=None, stall=True))
        self.assertIsNone(observation["natural_exit_code"])
        self.assertFalse(observation["process_reaped"])
        self.assertFalse(child.stdout.closed or child.stderr.closed)
        self.assertEqual(child.wait_calls, 0)

    def test_05_nonzero_or_noninteger_exit_refuses(self):
        for code in (3, False, 0.0):
            self.assert_refused(self.invoke(code=code))

    def test_06_stream_cap_failure_never_promotes_later_zero(self):
        observation, child = self.assert_refused(self.invoke(stdout=b"12345", cap=4))
        self.assertIsNone(observation["natural_exit_code"])
        self.assertEqual(observation["observed_leader_exit_code"], 0)
        self.assertFalse(observation["streams_closed"])
        self.assertFalse(child.stdout.closed or child.stderr.closed)

    def test_07_late_wait_or_refinalization_refuses(self):
        self.assert_refused(self.invoke(wait_time=1.01))
        self.assert_refused(self.invoke(clock_sequence=[0, 0, 0, 0, 1.01]))

    def test_08_unsupported_host_refuses_before_popen(self):
        with patch.object(m, "preflight_observer_namespace", side_effect=AdapterError("invented unsupported procfs")), \
             patch.object(m.subprocess, "Popen", side_effect=AssertionError("must not launch")) as launch:
            with self.assertRaises(AdapterError):
                m.ProcessObserver().run(["/invented/python"], cwd="/invented", env={}, budget=Budget(),
                                        seconds=1, cleanup_seconds=0.1, stream_cap=8)
            launch.assert_not_called()

    def test_09_source_has_no_numeric_child_or_group_mutator(self):
        path = Path(m.__file__); size = path.stat().st_size
        self.assertLess(size, 40000)
        tree = ast.parse(path.read_text())
        forbidden = {"killpg", "kill", "terminate", "send_signal", "pthread_kill", "pidfd_send_signal"}
        self.assertFalse(any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                             and node.func.attr in forbidden for node in ast.walk(tree)))
        self.assertFalse(any(isinstance(node, ast.Import) and any(a.name == "signal" for a in node.names)
                             for node in ast.walk(tree)))


if __name__ == "__main__": unittest.main(verbosity=2)
