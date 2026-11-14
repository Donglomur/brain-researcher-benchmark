"""Run all 31 invented causal-consumer controls; no authentic-data admission."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import stat
import sys
import time
import traceback
import types
import unittest

ROOT = Path(__file__).absolute().parent
MODULES = ("consumer", "scoring", "reference", "cognitive", "pipeline", "checks")
FILES = tuple(name + ".py" for name in MODULES) + ("run_controls.py", "requirements.txt")
READ_LIMIT = 1048576
OUTPUT_LIMIT = 1048576
DEADLINE_SECONDS = 45

def require(ok, message):
    if not ok:
        raise ValueError(message)

def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()

def main():
    started = time.monotonic()
    timed_out = False
    def deadline(*_):
        nonlocal timed_out
        timed_out = True
        # unittest re-raises KeyboardInterrupt instead of continuing later tests.
        raise KeyboardInterrupt("original 45-second control deadline")
    require(sys.platform in ("darwin", "linux"), "Linux or macOS control runner")
    signal.signal(signal.SIGALRM, deadline)
    signal.setitimer(signal.ITIMER_REAL, DEADLINE_SECONDS)
    output = None
    observed = []
    failure = None
    reads = 0
    lock = None
    numpy_version = None
    source_pins = {}
    try:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--out", required=True)
        parser.add_argument("--selection-sha256", required=True)
        args = parser.parse_args()
        require(sys.implementation.name == "cpython" and sys.version_info[:2] == (3, 11),
                "CPython 3.11 required")
        require(sys.flags.isolated == 1 and sys.flags.dont_write_bytecode == 1,
                "use python -I -B")
        def read(name):
            nonlocal reads
            require(name in FILES + ("SOURCE_LOCK.json",), "selected relative source name")
            fd = os.open(ROOT / name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            try:
                before = os.fstat(fd)
                require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                        and 0 <= before.st_size <= 262144, "bounded ordinary source")
                require(reads + before.st_size <= READ_LIMIT, "source read ceiling")
                pieces = []
                remaining = before.st_size
                while remaining:
                    part = os.read(fd, min(remaining, 65536))
                    require(bool(part), "complete source read")
                    reads += len(part)
                    pieces.append(part)
                    remaining -= len(part)
                after = os.fstat(fd)
                named = (ROOT / name).lstat()
                fields = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size",
                          "st_mtime_ns", "st_ctime_ns")
                require(all(getattr(before, key) == getattr(after, key) == getattr(named, key)
                            for key in fields), "stable source identity")
                return b"".join(pieces)
            finally:
                os.close(fd)
        def unique(pairs):
            result = {}
            for key, value in pairs:
                require(key not in result, "duplicate source-lock key")
                result[key] = value
            return result
        lock_raw = read("SOURCE_LOCK.json")
        require(hashlib.sha256(lock_raw).hexdigest() == args.selection_sha256,
                "selected public source lock")
        lock = json.loads(lock_raw, object_pairs_hook=unique)
        require(set(lock) == {"schema", "members", "test_names", "python_minor", "numpy"}
                and lock["schema"] == "hybrid_public_invented_source_v1"
                and set(lock["members"]) == set(FILES)
                and lock["python_minor"] == "3.11" and lock["numpy"] == "2.2.6",
                "complete fixture source and dependency closure")
        bodies = {}
        for name in FILES:
            body = read(name)
            identity = {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
            require(identity == lock["members"][name], "selected source bytes: " + name)
            bodies[name] = body
            source_pins[name] = identity
        proposed_output = Path(args.out).absolute()
        require(".." not in proposed_output.parts
                and not any(p.is_symlink() for p in (proposed_output, *proposed_output.parents))
                and proposed_output.parent.is_dir(), "ordinary existing output parent")
        proposed_output.mkdir(mode=0o700)
        output = proposed_output
        for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                     "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
            os.environ[name] = "1"
        import numpy
        numpy_version = numpy.__version__
        require(numpy_version == lock["numpy"], "selected NumPy version")
        for name in MODULES:
            require(name not in sys.modules, "fresh scientific module namespace")
            module = types.ModuleType(name)
            module.__file__ = str(ROOT / (name + ".py"))
            sys.modules[name] = module
            exec(compile(bodies[name + ".py"], module.__file__, "exec"), module.__dict__)
        require(sys.modules["consumer"].MAIN_CASE_SHA256 is None,
                "authentic-file admission remains disabled")
        case = sys.modules["checks"].FullPathControls
        names = unittest.defaultTestLoader.getTestCaseNames(case)
        require(names == lock["test_names"] and len(names) == 31, "exact complete 31-control roster")

        class RecordedResult(unittest.TextTestResult):
            @staticmethod
            def label(test):
                return getattr(test, "_testMethodName", str(test))
            def __init__(self, *values):
                super().__init__(*values)
                self.started_names = []
                self.records = []
                observed.append(self)
            def startTest(self, test):
                self.started_names.append(self.label(test))
                super().startTest(test)
            def addSuccess(self, test):
                self.records.append({"name": self.label(test), "status": "passed"})
                super().addSuccess(test)
            def addFailure(self, test, error):
                self.records.append({"name": self.label(test), "status": "failed"})
                super().addFailure(test, error)
            def addError(self, test, error):
                self.records.append({"name": self.label(test), "status": "error"})
                super().addError(test, error)
            def addSkip(self, test, reason):
                self.records.append({"name": self.label(test), "status": "skipped"})
                super().addSkip(test, reason)
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(case)
        result = unittest.TextTestRunner(verbosity=2, resultclass=RecordedResult).run(suite)
        require(result.wasSuccessful() and not result.skipped and result.testsRun == 31
                and result.started_names == names
                and result.records == [{"name": name, "status": "passed"} for name in names],
                "all 31 controls must complete without failures, errors or skips")
        require(time.monotonic() - started < DEADLINE_SECONDS, "original success deadline")
    except BaseException as error:
        failure = {"type": type(error).__name__, "message": str(error)[:2048],
                   "traceback": traceback.format_exc()[-16384:]}
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)

    result = observed[0] if observed else None
    elapsed = time.monotonic() - started
    success = failure is None and not timed_out and elapsed < DEADLINE_SECONDS
    report = {
        "schema": "hybrid_public_invented_control_result_v1",
        "status": "PASSED" if success else "FAILED",
        "fixture_only": True, "authentic_admission_enabled": False,
        "authentic_data": False, "scientific_fit": False,
        "synthetic_optimizer_controls": True,
        "tests_run": 0 if result is None else result.testsRun,
        "expected_tests": 31,
        "started_names": [] if result is None else result.started_names,
        "controls": [] if result is None else result.records,
        "failures": [] if result is None else [{"test": str(t), "traceback": s} for t, s in result.failures],
        "errors": [] if result is None else [{"test": str(t), "traceback": s} for t, s in result.errors],
        "skips": [] if result is None else [{"test": str(t), "reason": s} for t, s in result.skipped],
        "exception": failure, "deadline_triggered": timed_out,
        "elapsed_seconds": elapsed, "original_deadline_seconds": DEADLINE_SECONDS,
        "python_version": platform.python_version(), "numpy_version": numpy_version,
        "platform": sys.platform, "source_read_bytes": reads, "source_pins": source_pins,
        "native_R_or_Docker": False, "model_calls": 0, "count_delta": 0,
        "automatic_retry": False, "hard_memory_quota": False,
    }
    body = encode(report)
    require(len(body) <= OUTPUT_LIMIT, "complete control report ceiling")
    if output is not None and output.is_dir():
        fd = os.open(output / "RESULT.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(fd, "wb", closefd=False) as stream:
                stream.write(body)
                stream.flush()
                os.fsync(fd)
        finally:
            os.close(fd)
    else:
        print(body.decode(), file=sys.stderr, end="")
    # Tool/CI exit and this final envelope remain authoritative if final I/O ran late.
    success = success and time.monotonic() - started < DEADLINE_SECONDS
    print(json.dumps({"status": "PASSED" if success else "FAILED", "tests_run": report["tests_run"],
                      "fixture_only": True, "report_bytes": len(body),
                      "source_read_bytes": reads, "elapsed_seconds": time.monotonic() - started,
                      "automatic_retry": False}, sort_keys=True))
    return 0 if success else 1

if __name__ == "__main__":
    raise SystemExit(main())
