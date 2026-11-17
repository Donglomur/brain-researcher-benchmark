"""Generated ownership controls; never start a process or send a real signal."""
import contextlib
import io
import signal
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "benchmarks/shared/program-execution/ownership-v4/group_bootstrap.py"


class HardExit(BaseException):
    """Stand-in for the non-returning os._exit, never a real process exit."""


class ParkInterrupted(Exception):
    pass


class BootstrapCleanupTests(unittest.TestCase):
    def invoke(self, options=None, *, pid=101, pgid=101, sid=101,
               seconds="10", gate=True, activation=True, controller_error=None,
               ready_error=None, timer_error=None, kill_error=None):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            if gate:
                (folder / "process_gate.json").write_text("{}\n")
            token = "a" * 32
            argv = [str(SOURCE), *(options if options is not None else [
                "--owner", str(folder / "process_owner.json"),
                "--token", token, "--seconds=" + seconds])]
            owner = {"pid": pid, "token": token, "controller": {"generated": True},
                     "child_argv": ["generated-controller"]}
            dependencies = types.ModuleType("process_owner")
            dependencies.atomic = Mock(side_effect=ready_error)
            dependencies.expected = Mock(return_value=(owner, []))
            dependencies.read = Mock(return_value={"token": token, "activate": activation})
            trusted = types.ModuleType("trusted_controller")
            trusted.validate_controller = Mock(side_effect=controller_error)
            child = Mock(pid=202)
            child.wait.return_value = 0
            out, err = io.StringIO(), io.StringIO()
            with contextlib.ExitStack() as stack:
                stack.enter_context(patch.dict(sys.modules, {
                    "process_owner": dependencies, "trusted_controller": trusted}))
                stack.enter_context(patch.object(sys, "argv", argv))
                stack.enter_context(patch.object(sys, "path", list(sys.path)))
                stack.enter_context(patch.object(sys, "dont_write_bytecode", True))
                getpid = stack.enter_context(patch("os.getpid", return_value=pid))
                getpgrp = stack.enter_context(patch("os.getpgrp", return_value=pgid))
                getsid = stack.enter_context(patch("os.getsid", return_value=sid))
                kill = stack.enter_context(patch("os.killpg", side_effect=kill_error))
                hard_exit = stack.enter_context(patch("os._exit", side_effect=HardExit))
                handler = stack.enter_context(patch("signal.signal"))
                timer = stack.enter_context(patch("signal.setitimer", side_effect=timer_error))
                popen = stack.enter_context(patch("subprocess.Popen", return_value=child))
                stack.enter_context(patch("time.monotonic", side_effect=[0.0, 10.0]))
                sleep = stack.enter_context(patch("time.sleep", side_effect=ParkInterrupted))
                stack.enter_context(contextlib.redirect_stdout(out))
                stack.enter_context(contextlib.redirect_stderr(err))
                caught = None
                try:
                    exec(compile(SOURCE.read_bytes(), str(SOURCE), "exec"),
                         {"__name__": "__main__", "__file__": str(SOURCE)})
                except BaseException as error:
                    caught = error
            return {"error": caught, "out": out.getvalue(), "err": err.getvalue(),
                    "kill": kill, "exit": hard_exit, "handler": handler, "timer": timer,
                    "popen": popen, "child": child, "dependencies": dependencies,
                    "controller": trusted.validate_controller, "sleep": sleep,
                    "getpid": getpid, "getpgrp": getpgrp, "getsid": getsid}

    def assert_unowned(self, result):
        for name in ("kill", "exit", "handler", "timer", "popen"):
            result[name].assert_not_called()
        result["dependencies"].atomic.assert_not_called()

    def assert_owned_cleanup(self, result):
        self.assertIsInstance(result["error"], HardExit)
        result["kill"].assert_called_once_with(101, signal.SIGKILL)
        result["exit"].assert_called_once_with(124)
        # Cleanup must retain the established identity, not query a later group.
        result["getpid"].assert_called_once_with()
        result["getpgrp"].assert_called_once_with()
        result["getsid"].assert_called_once_with(0)

    def test_help_preserves_zero_exit_without_claiming_a_group(self):
        result = self.invoke(["--help"], pgid=50, sid=50)
        self.assertIsInstance(result["error"], SystemExit)
        self.assertEqual(result["error"].code, 0)
        self.assertIn("usage:", result["out"])
        self.assert_unowned(result)
        result["getpid"].assert_not_called()

    def test_missing_arguments_preserve_parser_error_without_signals(self):
        result = self.invoke([], pgid=50, sid=50)
        self.assertIsInstance(result["error"], SystemExit)
        self.assertEqual(result["error"].code, 2)
        self.assert_unowned(result)

    def test_nonisolated_or_pid_one_rejection_never_signals(self):
        for identity in ({"pgid": 50}, {"sid": 50}, {"pid": 1, "pgid": 1, "sid": 1}):
            with self.subTest(identity=identity):
                result = self.invoke(**identity)
                self.assertIsInstance(result["error"], ValueError)
                self.assertIn("session/group leader", str(result["error"]))
                self.assert_unowned(result)

    def test_invalid_budget_cannot_establish_cleanup_ownership(self):
        for value in ("0", "301", "nan", "inf", "-inf"):
            with self.subTest(seconds=value):
                result = self.invoke(seconds=value)
                self.assertIsInstance(result["error"], ValueError)
                self.assert_unowned(result)

    def test_owned_activation_timeout_terminates_only_verified_group(self):
        result = self.invoke(gate=False)
        self.assert_owned_cleanup(result)
        result["popen"].assert_not_called()
        self.assertEqual(result["dependencies"].atomic.call_count, 1)

    def test_owned_timer_setup_failure_still_cleans_group(self):
        result = self.invoke(timer_error=ValueError("generated timer error"))
        self.assert_owned_cleanup(result)
        self.assertIn("generated timer error", result["err"])
        result["popen"].assert_not_called()

    def test_owned_readiness_write_failure_still_cleans_group(self):
        result = self.invoke(ready_error=OSError("generated journal error"))
        self.assert_owned_cleanup(result)
        result["popen"].assert_not_called()

    def test_bad_activation_never_starts_controller_but_cleans_owned_group(self):
        result = self.invoke(activation=False)
        self.assert_owned_cleanup(result)
        self.assertIn("Activation binds exact group", result["err"])
        result["popen"].assert_not_called()
        result["controller"].assert_not_called()

    def test_bad_controller_never_starts_child_but_cleans_owned_group(self):
        result = self.invoke(controller_error=ValueError("generated controller refusal"))
        self.assert_owned_cleanup(result)
        result["popen"].assert_not_called()
        self.assertIn("generated controller refusal", result["err"])

    def test_completed_child_stays_owned_until_park_interruption(self):
        result = self.invoke()
        self.assert_owned_cleanup(result)
        result["popen"].assert_called_once_with(["generated-controller"])
        result["child"].wait.assert_called_once_with()
        self.assertEqual(result["dependencies"].atomic.call_count, 2)
        completion = result["dependencies"].atomic.call_args.args[1]
        self.assertEqual(completion["returncode"], 0)
        self.assertEqual(completion["child_pid"], 202)
        self.assertTrue(completion["group_leader_waits_for_owner_stop"])
        result["sleep"].assert_called_once_with(0.1)

    def test_cleanup_hard_exits_even_if_group_is_already_absent(self):
        result = self.invoke(gate=False, kill_error=ProcessLookupError())
        self.assert_owned_cleanup(result)


if __name__ == "__main__":
    unittest.main()
