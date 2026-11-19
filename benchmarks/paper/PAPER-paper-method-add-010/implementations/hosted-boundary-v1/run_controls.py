"""Portable bounded runner for the new hosted-boundary generated controls.

This runs source controls only. Docker, actual network and native qualification
are never selected by this entry. The frozen method manifest is authoritative.
"""
import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import resource
import socket
import subprocess
import sys
import time
import unittest
from unittest import mock

METHOD_SCHEMA = "meg-hosted-boundary-control-methods/v1"
FIXTURE_LIMIT = 786432
LOG_LIMIT = 65536
REPORT_LIMIT = 32768


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def discover_suite(test_root):
    path = test_root / "CONTROL_METHODS.json"
    if path.stat().st_size > 16384:
        raise ValueError("method roster exceeds its fixed source extent")
    document = json.loads(path.read_text())
    if set(document) != {"schema", "methods", "scope"} or document["schema"] != METHOD_SCHEMA:
        raise ValueError("exact method roster schema required")
    expected = document["methods"]
    if (type(expected) is not list or not 1 <= len(expected) <= 64
            or any(type(x) is not str for x in expected)
            or expected != sorted(set(expected))):
        raise ValueError("nonempty unique sorted bounded method roster required")
    cases = list(flatten(unittest.defaultTestLoader.discover(str(test_root), pattern="test_*.py")))
    found = [case.id() for case in cases]
    if len(found) != len(set(found)) or sorted(found) != expected:
        raise ValueError("discovered methods differ from the frozen exact roster")
    return unittest.TestSuite(cases), expected, sorted(found)


class BoundedLog:
    def __init__(self, path, console):
        self.stream = open(path, "xb", buffering=0)
        self.console = console
        self.attempted = 0
        self.retained = 0
    def write(self, text):
        body = text.encode("utf-8", errors="replace")
        self.attempted += len(body)
        selected = body[:max(0, LOG_LIMIT - self.retained)]
        self.stream.write(selected)
        self.retained += len(selected)
        self.console.write(selected.decode("utf-8", errors="replace"))
        return len(text)
    def flush(self):
        self.stream.flush()
        self.console.flush()
    def isatty(self):
        return False
    def close(self):
        self.flush()
        self.stream.close()


class RecordingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.positive_method_ids = []
    def addSuccess(self, test):
        self.positive_method_ids.append(test.id())
        super().addSuccess(test)


def forbidden_native_operation(*args, **kwargs):
    raise RuntimeError("actual process/network/signal operation forbidden in generated source controls")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--implementation-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--paired-source-root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    implementation = Path(args.implementation_root).resolve(strict=True)
    paired = Path(args.paired_source_root).resolve(strict=True)
    test_root = Path(__file__).resolve().parent
    output = Path(args.output).resolve(strict=False)
    if (output.exists() or not output.parent.is_dir()
            or any(output == p or p in output.parents for p in (implementation, paired, test_root))):
        raise ValueError("fresh output under an existing external parent required")
    os.umask(0o077)
    resource.setrlimit(resource.RLIMIT_CPU, (50, 50))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1048576, 1048576))
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ[name] = "1"
    os.environ["MEG_BOUNDARY_CONTROL_OUTPUT"] = str(output)
    os.environ["MEG_BOUNDARY_CONTROL_IMPLEMENTATION"] = str(implementation)
    os.environ["MEG_BOUNDARY_CONTROL_PAIRED_SOURCE"] = str(paired)
    sys.path[:0] = [str(implementation), str(paired), str(test_root)]
    output.mkdir(mode=0o700)
    log = BoundedLog(output / "CONTROL.log", sys.stderr)
    started = time.monotonic()
    result = None
    expected = []
    discovered = []
    initialization_error = None
    try:
        try:
            with ExitStack() as guards:
                for target, name in ((subprocess, "Popen"), (os, "system"), (os, "kill"),
                                     (os, "killpg"), (socket.socket, "connect"),
                                     (socket.socket, "connect_ex")):
                    guards.enter_context(mock.patch.object(target, name, side_effect=forbidden_native_operation))
                suite, expected, discovered = discover_suite(test_root)
                result = unittest.TextTestRunner(verbosity=2, stream=log, resultclass=RecordingResult).run(suite)
        except Exception as exc:
            initialization_error = type(exc).__name__ + ": " + str(exc)[:2048]
            log.write("CONTROL INITIALIZATION FAILED: " + initialization_error + "\n")
        retained = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
        positive = sorted(result.positive_method_ids) if result else []
        test_module = sys.modules.get("test_boundary_qualification")
        counters = test_module.control_accounting() if test_module is not None else {}
        accounting_valid = (type(counters.get("cumulative_generated_write_bytes")) is int
                            and 0 <= counters["cumulative_generated_write_bytes"] <= FIXTURE_LIMIT
                            and counters.get("observed_fixture_builds") == 1)
        successful = bool(result and result.wasSuccessful() and not result.skipped
                          and positive == expected and result.testsRun == len(expected)
                          and len(positive) == len(set(positive))
                          and retained <= FIXTURE_LIMIT and log.attempted == log.retained
                          and accounting_valid)
        report = {
            "schema": "meg-hosted-boundary-generated-control-result/v1",
            "scope": "generated source controls; no actual Docker/network/isolation/scientific qualification",
            "successful": successful, "initialization_error": initialization_error,
            "discovered_method_ids": discovered, "selected_method_ids": expected,
            "positive_method_ids": positive, "tests": result.testsRun if result else 0,
            "failures": len(result.failures) if result else 0,
            "errors": len(result.errors) if result else (1 if initialization_error else 0),
            "skips": len(result.skipped) if result else 0,
            "retained_generated_bytes_before_report": retained,
            "control_accounting": counters, "control_accounting_valid": accounting_valid,
            "fixture_and_scratch_limit_bytes": FIXTURE_LIMIT,
            "local_log_limit_bytes": LOG_LIMIT, "local_log_retained_bytes": log.retained,
            "local_log_attempted_bytes": log.attempted,
            "local_log_truncated": log.attempted != log.retained,
            "wall_seconds": time.monotonic() - started,
            "physical_IO_or_hard_aggregate_RAM_measured": False,
            "scientific_fits": 0, "actual_native_qualification": False,
            "source_campaign_guard": "unmocked subprocess creation, OS signalling and socket connects refused",
        }
        body = (json.dumps(report, indent=2) + "\n").encode()
        if len(body) > REPORT_LIMIT:
            raise ValueError("control report exceeded fixed allowance")
        with open(output / "CONTROL_RESULT.json", "xb") as stream:
            stream.write(body)
        return 0 if successful else 1
    finally:
        log.close()


if __name__ == "__main__":
    raise SystemExit(main())
