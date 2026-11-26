"""Offline transport controls; one harmless child checks parent timeout cleanup."""
import contextlib
import hashlib
import importlib.util
import io
from pathlib import Path
import os
import socket
import subprocess
import sys
import time
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError
from urllib.request import Request

REAL_RUN, REAL_POPEN = subprocess.run, subprocess.Popen
ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "workflow_syntax_under_test", ROOT / "scripts/maintenance/check_workflow_syntax.py")
lint = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lint)
URL = "https://github.com/rhysd/actionlint/releases/download/v1.7.12/test.tar.gz"
BODY = b"invented archive bytes; download tests do not execute or extract this"
ASSET = {"name": "test.tar.gz", "bytes": len(BODY),
         "sha256": hashlib.sha256(BODY).hexdigest()}


class Response:
    def __init__(self, body=BODY, *, url=URL, status=200):
        self.body, self.url, self.status = body, url, status
        self.closed = False
        self.read_limits = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def geturl(self):
        return self.url

    def read(self, limit):
        self.read_limits.append(limit)
        if isinstance(self.body, BaseException):
            raise self.body
        return self.body() if callable(self.body) else self.body


class Opener:
    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def open(self, request, *, timeout):
        self.calls.append((request, timeout))
        if not self.outcomes:
            raise AssertionError("unexpected extra acquisition attempt")
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome() if callable(outcome) else outcome


class WorkflowSyntaxControls(unittest.TestCase):
    def setUp(self):
        # Network and process launches fail unless the one timeout control explicitly selects its harmless child.
        self.socket_guard = patch.object(socket, "socket", side_effect=AssertionError("network forbidden"))
        self.process_guard = patch.object(subprocess, "Popen", side_effect=AssertionError("process forbidden"))
        self.socket_guard.start()
        self.process_guard.start()
        self.addCleanup(self.socket_guard.stop)
        self.addCleanup(self.process_guard.stop)
        self.stderr = io.StringIO()
        self.output = contextlib.redirect_stderr(self.stderr)
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def download(self, opener):
        with patch.object(lint, "build_opener", return_value=opener):
            return lint.download_archive(ASSET)

    def test_success_uses_exact_extent_and_closes_response(self):
        response = Response()
        opener = Opener(response)
        self.assertEqual(self.download(opener), BODY)
        self.assertEqual(len(opener.calls), 1)
        self.assertEqual(response.read_limits, [len(BODY) + 1])
        self.assertTrue(response.closed)
        self.assertGreater(opener.calls[0][1], 0)
        self.assertLessEqual(opener.calls[0][1], 20)

    def test_stage_markers_are_flushed_before_blocking_operations(self):
        def reading():
            self.assertIn("attempt 1/2: response read", self.stderr.getvalue())
            self.assertGreaterEqual(flushed.call_count, 2)
            return BODY
        def opening():
            self.assertIn("attempt 1/2: request open", self.stderr.getvalue())
            self.assertGreaterEqual(flushed.call_count, 1)
            return Response(reading)
        with patch.object(self.stderr, "flush", wraps=self.stderr.flush) as flushed:
            self.assertEqual(self.download(Opener(opening)), BODY)

    def test_open_timeout_then_success_retries_only_once(self):
        opener = Opener(TimeoutError("invented socket read timeout"), Response())
        self.assertEqual(self.download(opener), BODY)
        self.assertEqual(len(opener.calls), 2)
        self.assertIn("attempt 1/2 failed during request open", self.stderr.getvalue())
        self.assertIn("Retrying actionlint transport timeout once", self.stderr.getvalue())

    def test_urllib_wrapped_transport_timeout_can_retry(self):
        opener = Opener(URLError(TimeoutError("invented connect timeout")), Response())
        self.assertEqual(self.download(opener), BODY)
        self.assertEqual(len(opener.calls), 2)

    def test_body_timeout_discards_partial_response_before_retry(self):
        consumed = []
        def partial_body():
            consumed.append(BODY[:8])
            raise TimeoutError("invented partial-body timeout")
        first = Response(partial_body)
        second = Response()
        opener = Opener(first, second)
        self.assertEqual(self.download(opener), BODY)
        self.assertEqual(len(opener.calls), 2)
        self.assertTrue(first.closed and second.closed)
        self.assertEqual(consumed, [BODY[:8]])
        self.assertEqual(first.read_limits, [len(BODY) + 1])
        self.assertIn("failed during response read", self.stderr.getvalue())

    def test_two_transport_timeouts_exhaust_attempts(self):
        opener = Opener(TimeoutError("first"), TimeoutError("second"), Response())
        with self.assertRaisesRegex(TimeoutError, "second"):
            self.download(opener)
        self.assertEqual(len(opener.calls), 2)
        self.assertEqual(self.stderr.getvalue().count("Retrying actionlint"), 1)
        self.assertIn("attempt 2/2", self.stderr.getvalue())

    def test_non_timeout_transport_and_http_errors_do_not_retry(self):
        failures = [HTTPError(URL, 404, "missing", {}, None),
                    HTTPError(URL, 404, TimeoutError("unusual HTTP reason"), {}, None),
                    URLError("DNS lookup failed"), ConnectionResetError("reset"),
                    OSError("other transport error")]
        for failure in failures:
            with self.subTest(error=type(failure).__name__):
                opener = Opener(failure, Response())
                with self.assertRaises(type(failure)):
                    self.download(opener)
                self.assertEqual(len(opener.calls), 1)

    def test_integrity_failures_never_retry(self):
        for bad in (BODY[:-1], BODY + b"!", b"x" * len(BODY)):
            with self.subTest(bytes=len(bad)):
                response = Response(bad)
                opener = Opener(response, Response())
                with self.assertRaisesRegex(ValueError, "size mismatch|SHA256 mismatch"):
                    self.download(opener)
                self.assertEqual(len(opener.calls), 1)
                self.assertTrue(response.closed)
        self.assertNotIn("Retrying actionlint", self.stderr.getvalue())

    def test_forbidden_final_url_and_failed_status_do_not_retry(self):
        for response in (Response(url="https://example.invalid/asset"), Response(status=404)):
            with self.subTest(url=response.url, status=response.status):
                opener = Opener(response, Response())
                with self.assertRaises(ValueError):
                    self.download(opener)
                self.assertEqual(len(opener.calls), 1)
                self.assertEqual(response.read_limits, [])
                self.assertTrue(response.closed)

    def test_forbidden_redirect_is_rejected_without_retry(self):
        def forbidden():
            return lint.ReleaseRedirects().redirect_request(
                Request(URL), None, 302, "redirect", {}, "https://example.invalid/asset")
        opener = Opener(forbidden, Response())
        with self.assertRaisesRegex(ValueError, "Unexpected actionlint release URL"):
            self.download(opener)
        self.assertEqual(len(opener.calls), 1)

    def test_urllib_wrapped_aggregate_deadline_does_not_retry(self):
        failure = URLError(lint.AcquisitionDeadline("aggregate deadline"))
        opener = Opener(failure, Response())
        with self.assertRaises(URLError):
            self.download(opener)
        self.assertEqual(len(opener.calls), 1)
        self.assertNotIn("Retrying actionlint", self.stderr.getvalue())

    def test_retry_preserves_original_deadline_and_rejects_late_body(self):
        clock = [0.0]
        def first():
            clock[0] = 30.0
            raise TimeoutError("first request timed out")
        def late_body():
            clock[0] = 46.0
            return BODY
        response = Response(late_body)
        opener = Opener(first, response)
        with patch.object(lint.time, "monotonic", side_effect=lambda: clock[0]):
            with self.assertRaises(lint.AcquisitionDeadline):
                self.download(opener)
        self.assertEqual([row[1] for row in opener.calls], [20, 15])
        self.assertTrue(response.closed)

    def test_parent_verifies_worker_bytes_and_fixed_launch(self):
        completed = subprocess.CompletedProcess([], 0, BODY, b"retry diagnostic\n")
        with patch.dict(lint.ASSETS, {("Linux", "x86_64"): ASSET}, clear=True):
            with patch.object(lint.subprocess, "run", return_value=completed) as run:
                self.assertEqual(lint.download(ASSET), BODY)
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0], [sys.executable, "-I", "-S", "-B",
                         str(ROOT / "scripts/maintenance/check_workflow_syntax.py"),
                         "--download-archive", "test.tar.gz"])
        self.assertEqual(run.call_args.kwargs, {"cwd": ROOT, "env": dict(os.environ),
                         "capture_output": True, "timeout": 45, "check": False})
        self.assertIn("retry diagnostic", self.stderr.getvalue())

    def test_parent_rejects_bad_worker_bytes_and_failed_exit_without_retry(self):
        for code, body in ((0, BODY[:-1]), (0, BODY + b"!"), (0, b"x" * len(BODY)), (1, BODY)):
            with self.subTest(code=code, bytes=len(body)):
                completed = subprocess.CompletedProcess([], code, body, b"worker context\n")
                with patch.dict(lint.ASSETS, {("Linux", "x86_64"): ASSET}, clear=True):
                    with patch.object(lint.subprocess, "run", return_value=completed) as run:
                        with self.assertRaises(ValueError):
                            lint.download(ASSET)
                run.assert_called_once()

    def test_parent_timeout_kills_and_reaps_unresponsive_worker(self):
        processes = []
        def spawn(*args, **kwargs):
            process = REAL_POPEN(*args, **kwargs)
            processes.append(process)
            return process
        def controlled_worker(command, **kwargs):
            self.assertEqual(command[-2:], ["--download-archive", ASSET["name"]])
            # Real, harmless child. It ignores Python alarm delivery and blocks;
            # no network, archive extraction or actionlint executable is used.
            child = [sys.executable, "-I", "-S", "-B", "-c",
                     "import signal,time; signal.signal(signal.SIGALRM, signal.SIG_IGN); time.sleep(5)"]
            with patch.object(subprocess, "Popen", side_effect=spawn):
                return REAL_RUN(child, **kwargs)
        started = time.monotonic()
        with patch.dict(lint.ASSETS, {("Linux", "x86_64"): ASSET}, clear=True):
            with patch.object(lint, "ACQUISITION_SECONDS", 0.2):
                with patch.object(lint.subprocess, "run", side_effect=controlled_worker) as run:
                    with self.assertRaises(subprocess.TimeoutExpired):
                        lint.download(ASSET)
        self.assertLess(time.monotonic() - started, 2)
        run.assert_called_once()
        self.assertEqual(len(processes), 1)
        self.assertIsNotNone(processes[0].returncode)
        self.assertLess(processes[0].returncode, 0)
        with self.assertRaises(ChildProcessError):
            os.waitpid(processes[0].pid, os.WNOHANG)

    def test_parent_timeout_preserves_diagnostic_without_retry(self):
        error = subprocess.TimeoutExpired(["worker"], 45, output=b"partial", stderr=b"attempt context\n")
        with patch.dict(lint.ASSETS, {("Linux", "x86_64"): ASSET}, clear=True):
            with patch.object(lint.subprocess, "run", side_effect=error) as run:
                with self.assertRaises(subprocess.TimeoutExpired):
                    lint.download(ASSET)
        run.assert_called_once()
        self.assertIn("attempt context", self.stderr.getvalue())

    def test_parent_refuses_unreviewed_asset_before_process_start(self):
        with patch.object(lint.subprocess, "run") as run:
            with self.assertRaisesRegex(ValueError, "Reviewed actionlint asset"):
                lint.download(ASSET)
        run.assert_not_called()

    def test_child_mode_emits_only_verified_archive_bytes(self):
        output = Mock(buffer=io.BytesIO())
        with patch.dict(lint.ASSETS, {("Linux", "x86_64"): ASSET}, clear=True):
            with patch.object(lint, "download_archive", return_value=BODY) as fetch:
                with patch.object(lint.sys, "stdout", output):
                    self.assertEqual(lint.acquisition_main(ASSET["name"]), 0)
        fetch.assert_called_once_with(ASSET)
        self.assertEqual(output.buffer.getvalue(), BODY)
        output.write.assert_not_called()

    def test_child_mode_rejects_unknown_asset_and_preserves_fetch_failure(self):
        with patch.object(lint, "download_archive") as fetch:
            self.assertEqual(lint.acquisition_main("unknown.tar.gz"), 1)
            fetch.assert_not_called()
        with patch.dict(lint.ASSETS, {("Linux", "x86_64"): ASSET}, clear=True):
            with patch.object(lint, "download_archive", side_effect=TimeoutError("worker exhausted")) as fetch:
                self.assertEqual(lint.acquisition_main(ASSET["name"]), 1)
                fetch.assert_called_once()
        self.assertIn("worker exhausted", self.stderr.getvalue())

    @contextlib.contextmanager
    def main_fixture(self, *, acquisition=BODY, extraction=Path("invented-actionlint"), result=0):
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(lint.platform, "system", return_value="Linux"))
            stack.enter_context(patch.object(lint.platform, "machine", return_value="x86_64"))
            stack.enter_context(patch.object(lint, "workflow_paths", return_value=[Path("fixture.yml")]))
            download = stack.enter_context(patch.object(lint, "download"))
            extract = stack.enter_context(patch.object(lint, "extract_binary"))
            run = stack.enter_context(patch.object(lint.subprocess, "run"))
            download.side_effect = acquisition if isinstance(acquisition, BaseException) else None
            download.return_value = acquisition
            extract.side_effect = extraction if isinstance(extraction, BaseException) else None
            extract.return_value = extraction
            run.return_value = Mock(returncode=result)
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            yield download, extract, run

    def test_acquisition_failure_stops_before_extract_or_lint(self):
        with self.main_fixture(acquisition=TimeoutError("exhausted")) as (download, extract, run):
            self.assertEqual(lint.main(), 1)
            download.assert_called_once()
            extract.assert_not_called()
            run.assert_not_called()
        self.assertIn("failed during archive acquisition", self.stderr.getvalue())

    def test_archive_failure_stops_without_redownload_or_lint(self):
        with self.main_fixture(extraction=ValueError("forbidden archive member")) as (download, extract, run):
            self.assertEqual(lint.main(), 1)
            download.assert_called_once()
            extract.assert_called_once()
            run.assert_not_called()
        self.assertIn("failed during archive extraction", self.stderr.getvalue())

    def test_lint_failure_does_not_retry_or_relax_core_checks(self):
        with self.main_fixture(result=1) as (download, extract, run):
            self.assertEqual(lint.main(), 1)
            download.assert_called_once()
            extract.assert_called_once()
            run.assert_called_once()
            self.assertEqual(run.call_args.args[0], ["invented-actionlint", "-no-color",
                                                   "-shellcheck=", "-pyflakes=", "fixture.yml"])
            self.assertEqual(run.call_args.kwargs["timeout"], 60)
            self.assertEqual(run.call_args.kwargs["env"]["GOMAXPROCS"], "1")
            self.assertEqual(run.call_args.kwargs["env"]["GOMEMLIMIT"], "256MiB")
        self.assertIn("failed during lint: actionlint exited 1", self.stderr.getvalue())

    def test_successful_lint_keeps_original_result(self):
        with self.main_fixture(result=0) as (download, extract, run):
            self.assertEqual(lint.main(), 0)
            download.assert_called_once()
            extract.assert_called_once()
            run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
