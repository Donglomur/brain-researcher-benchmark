"""Execute maintained transport lifecycle functions with inert generated seams.

These controls do not launch a process, deliver a scientific observation, replay
a full panel, or qualify an operating-system boundary. The exact run function is
compiled from each maintained transport; only its external viewer, pipe, process
and ownership dependencies are replaced. The separate owned-exit tests exercise
the shared ownership implementation itself. No source function is rewritten.
"""
from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
import uuid


HERE = Path(__file__).resolve().parent
SOURCE_ROOT = Path(os.environ.get("VIEWER_OWNERSHIP_SOURCE_ROOT", HERE.parents[2]))
TRANSPORTS = (
    "benchmarks/neural/NEURAL-077/implementations/visual-transport-v1/transport.py",
    "benchmarks/neural/NEURAL-077/implementations/visual-provider-pair-v1/transport.py",
    "benchmarks/neural/NEURAL-007/implementations/viewer-transport-v1/transport.py",
    "benchmarks/neural/NEURAL-007/implementations/viewer-provider-integration-v1/transport.py",
)


def need(ok, message):
    if not ok:
        raise ValueError(message)


def encode(value):
    return json.dumps(value, sort_keys=True, allow_nan=False).encode()


def write_new(path, body):
    with Path(path).open("xb") as stream:
        stream.write(body)


def digest(body):
    return hashlib.sha256(body).hexdigest()


class UnsafeLifecycle(BaseException):
    """Cannot be swallowed by a transport's ordinary operator-failure handler."""


class WireFailure(Exception):
    def __init__(self, reason, captured=b""):
        super().__init__(reason)
        self.reason, self.captured = reason, captured


@dataclass
class Limits:
    # Generated lifecycle settings, never a selected scientific study budget.
    max_actions: int = 6000
    max_images: int = 3000
    max_output_bytes: int = 1024 * 1024
    wall_seconds: float = 30.0

    def validate(self, *args):
        pass


class Harness:
    """Inert dependency fixture; real files contain only generated metadata."""

    def __init__(self, root, relative, scenario="clean", trusted=False):
        self.root, self.relative = Path(root), relative
        self.scenario, self.trusted = scenario, trusted
        self.events, self.children = [], []
        self.sleep = "NEURAL-007" in relative
        self.client = self.root / "client.py"
        self.client.write_text("# Inert generated fixture; never executed.\n")
        self.packet = SimpleNamespace(case="development-001", epochs=2780, pins={})
        self.namespace = self.make_namespace()
        source = SOURCE_ROOT / relative
        tree = ast.parse(source.read_bytes(), filename=str(source))
        name = "run_person" if self.sleep else "run_episode"
        selected = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name]
        need(len(selected) == 1, "Exactly one maintained run function required")
        # Execute the original AST body, without altering its branches or calls.
        unit = ast.Module(body=selected, type_ignores=[])
        exec(compile(unit, str(source), "exec"), self.namespace)
        self.run_function = self.namespace[name]

    def forbidden(self, *args, **kwargs):
        self.events.append("UNSAFE_DIRECT_PROCESS_OPERATION")
        raise UnsafeLifecycle("Transport bypassed the owned-exit helper")

    def make_namespace(self):
        harness = self

        class Pipe:
            closed = False

            def fileno(self):
                return 123

            def close(self):
                self.closed = True

        class Child:
            def __init__(self, *args, **kwargs):
                harness.events.append("spawn")
                if harness.scenario == "spawn_failure":
                    raise OSError("Generated launch failure")
                self.pid, self.returncode = 4242, None
                self.stdin, self.stdout = Pipe(), Pipe()
                harness.children.append(self)

            poll = wait = communicate = kill = terminate = send_signal = harness.forbidden

        class Observer:
            def __init__(self, child):
                harness.events.append("observe")
                if harness.scenario == "observer_failure":
                    raise OSError("Generated notification registration failure")
                need(child is harness.children[0], "Observer must own the launched child")
                self.child, self.exit_observed = child, False

            def wait(self, deadline):
                harness.events.append("observe_exit")
                need(self.child.returncode is None, "Transport reaped before observation")
                self.exit_observed = harness.scenario != "timeout"
                return self.exit_observed

        def preflight():
            harness.events.append("preflight")
            if harness.scenario == "preflight_failure":
                raise RuntimeError("Generated unsupported observer")

        def stop_and_reap(child, observer, deadline):
            harness.events.append("owned_cleanup")
            need(child.returncode is None, "Cleanup must receive unreaped child")
            need(observer is None or observer.child is child, "Exact observer child")
            code = 7 if harness.scenario == "nonzero_exit" else 0
            complete = harness.scenario != "cleanup_failure"
            child.returncode = code
            return {
                "schema": "viewer-owned-process-cleanup/v1", "pid": child.pid,
                "exit_observed_before_stop": bool(observer and observer.exit_observed),
                "leader_unreaped_before_signal": True, "group_signal": "sent",
                "group_signal_errno": None, "reaped": True, "returncode": code,
                "group_absence_observed": complete, "cleanup_complete": complete,
                "descendant_containment_qualified": False,
                "error": None if complete else "generated_cleanup_failure",
            }

        class Journal:
            def __init__(self, path):
                self.path = Path(path)
                self.path.mkdir()
                self.sequence, self.offset, self.previous = 0, 0, "0" * 64

            def record(self, direction, body, complete=True):
                self.sequence += 1
                self.offset += len(body)
                self.previous = digest(body)

            def close(self):
                harness.events.append("journal_closed")

        class EEGSession:
            def __init__(self, dataset, ordinal, mode, output):
                self.output = Path(output)
                self.output.mkdir()
                self.closed, self.sequence = False, 0
                self.previous, self.state = "0" * 64, {}

            def handle(self, body):
                self.sequence += 1
                action = json.loads(body)["action"]
                harness.events.append("viewer_" + action)
                if action == "finalize":
                    self.closed = True
                    write_new(self.output / "FINAL.json", encode({"status": "valid_unscored"}))
                    return {"status": "valid_unscored"}
                return {"status": "rendered"}

        class SleepSession:
            def __init__(self, packet, *args):
                self.actions, self.finished = 0, False

            def handle(self, request):
                harness.events.append("viewer_" + request["action"])
                self.actions += 1
                self.finished = True
                return {"kind": "complete"}

        class Cwd:
            def __init__(self, **kwargs):
                self.path = harness.root / "empty-client-cwd"

            def __enter__(self):
                self.path.mkdir()
                return str(self.path)

            def __exit__(self, *args):
                return False

        def fresh_output(path):
            path = Path(path)
            path.mkdir()
            return path

        def set_blocking(fd, flag):
            harness.events.append("configure_pipe")
            need("observe" in harness.events, "Observe immediately after launch")

        def read_frame(fd, deadline):
            harness.events.append("read_action")
            action = "finish" if harness.sleep else "finalize"
            return b"\0" * 8 + encode({"action": action})

        def write_frame(fd, body, deadline):
            harness.events.append("write_observation")

        viewer = SimpleNamespace(
            need=need, write_new=write_new, encode=encode, decode=json.loads, digest=digest,
            Session=SleepSession if self.sleep else EEGSession,
            transition=lambda *args: None, dependencies=lambda: (None, None, None),
            fresh_output=fresh_output, CASES={"development-001": 2780, "development-002": 2670},
            MODE="whole_person_raw_viewer_zero_shot",
        )
        return {
            "owner": SimpleNamespace(preflight=preflight, ExitObserver=Observer, stop_and_reap=stop_and_reap),
            "subprocess": SimpleNamespace(Popen=Child, PIPE=-1, DEVNULL=-3),
            "os": SimpleNamespace(set_blocking=set_blocking, path=os.path, killpg=self.forbidden, kill=self.forbidden),
            "tempfile": SimpleNamespace(TemporaryDirectory=Cwd), "v": viewer,
            "Path": Path, "sys": sys, "uuid": uuid, "time": time, "asdict": asdict,
            "Limits": Limits, "Journal": Journal, "WireFailure": WireFailure,
            "need": need, "encode": encode, "digest": digest,
            "read_body": lambda path, cap: Path(path).read_bytes(), "MAX_CLIENT": 262144,
            "PREFIX": struct.Struct("!II"), "PNG_MAX": 256, "HEADER_MAX": 256, "RESERVE": 64,
            "wire": lambda header, png=b"": encode(header) + png,
            "unpack": lambda raw, inbound=False: (json.loads(raw[8:]), b""),
            "read_frame": read_frame, "write_frame": write_frame,
            "projection": lambda response: (dict(response), b""),
            "ready_header": lambda *args: {"fixture": "inert-generated-lifecycle"},
            "boundary_manifest": lambda *args: {"fixture": "inert-generated-lifecycle"},
            "viewer_manifest": lambda *args: {"fixture": "inert-generated-lifecycle"},
            "source_identity": lambda: {"fixture": "inert-generated-lifecycle"},
        }

    def run(self):
        kwargs = {"output": self.root / "session", "client": self.client,
                  "python": sys.executable, "sandbox": "protocol_only", "limits": Limits()}
        if self.trusted:
            def launcher(command, cwd):
                self.events.append("trusted_launcher")
                return self.namespace["subprocess"].Popen(command, cwd=cwd)
            kwargs["client_launcher"] = launcher
        if self.sleep:
            return self.run_function(self.packet, **kwargs)
        return self.run_function({}, 0, "zero_shot", **kwargs)


class TransportOwnershipControls(unittest.TestCase):
    def fixtures(self):
        for relative in TRANSPORTS:
            yield relative, False
            if "provider" in relative:
                yield relative, True

    def exercise(self, scenario, check):
        for relative, trusted in self.fixtures():
            with self.subTest(transport=relative, trusted_launcher=trusted, scenario=scenario):
                with tempfile.TemporaryDirectory(prefix="viewer-ownership-control-") as root:
                    fixture = Harness(root, relative, scenario, trusted)
                    check(fixture)

    def test_preflight_refuses_before_any_launch(self):
        def check(fixture):
            with self.assertRaises(RuntimeError):
                fixture.run()
            self.assertEqual(fixture.events, ["preflight"])
            self.assertEqual(fixture.children, [])
        self.exercise("preflight_failure", check)

    def test_clean_final_observes_exit_then_delegates_unreaped_cleanup(self):
        def check(fixture):
            result = fixture.run()
            expected = "complete_unscored" if fixture.sleep else "valid_unscored"
            self.assertEqual(result["status"], expected)
            events = fixture.events
            self.assertEqual(events[0], "preflight")
            spawn = events.index("spawn")
            self.assertEqual(events[spawn + 1], "observe")
            final = "viewer_finish" if fixture.sleep else "viewer_finalize"
            self.assertLess(events.index(final), events.index("observe_exit"))
            self.assertLess(events.index("observe_exit"), events.index("owned_cleanup"))
            self.assertEqual(events.count("owned_cleanup"), 1)
            self.assertTrue(result["process_ownership"]["leader_unreaped_before_signal"])
            self.assertFalse(result["process_ownership"]["descendant_containment_qualified"])
            self.assertTrue(all(child.stdin.closed and child.stdout.closed for child in fixture.children))
        self.exercise("clean", check)

    def test_registration_failure_still_cleans_the_launched_child(self):
        def check(fixture):
            result = fixture.run()
            self.assertEqual(result["status"], "failed")
            self.assertEqual(fixture.events.count("owned_cleanup"), 1)
            self.assertNotIn("configure_pipe", fixture.events)
            self.assertNotIn("read_action", fixture.events)
            self.assertFalse(result["process_ownership"]["exit_observed_before_stop"])
        self.exercise("observer_failure", check)

    def test_notification_timeout_cannot_admit_a_terminal_answer(self):
        def check(fixture):
            result = fixture.run()
            self.assertEqual(result["status"], "failed")
            self.assertIn("observe_exit", fixture.events)
            self.assertEqual(fixture.events.count("owned_cleanup"), 1)
            self.assertFalse(result["process_ownership"]["exit_observed_before_stop"])
        self.exercise("timeout", check)

    def test_unverified_cleanup_cannot_admit_a_terminal_answer(self):
        def check(fixture):
            result = fixture.run()
            self.assertEqual(result["status"], "failed")
            self.assertFalse(result["process_ownership"]["cleanup_complete"])
            self.assertFalse(result["process_ownership"]["group_absence_observed"])
        self.exercise("cleanup_failure", check)

    def test_nonzero_exit_cannot_admit_a_terminal_answer(self):
        def check(fixture):
            result = fixture.run()
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["client_exit_code"], 7)
            self.assertEqual(fixture.events.count("owned_cleanup"), 1)
        self.exercise("nonzero_exit", check)

    def test_launch_failure_does_not_invent_an_owned_child(self):
        def check(fixture):
            result = fixture.run()
            self.assertEqual(result["status"], "failed")
            self.assertEqual(fixture.children, [])
            self.assertNotIn("owned_cleanup", fixture.events)
            self.assertIsNone(result["process_ownership"])
        self.exercise("spawn_failure", check)


if __name__ == "__main__":
    unittest.main()
