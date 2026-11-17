"""Inactive source for the complete GCaMP8 pair with transitive recovery."""
import time
ORIGIN = time.monotonic()
import signal
import sys

FINAL_ENDPOINT = ORIGIN + 60


def expired(*_):
    raise TimeoutError("original-gcamp8-outer-endpoint")


def terminated(*_):
    raise InterruptedError("original-gcamp8-outer-termination")


def enter_startup():
    if signal.getitimer(signal.ITIMER_REAL) != (0.0, 0.0):
        raise ValueError("no-inherited-owner-timer")
    saved = (signal.getsignal(signal.SIGALRM), signal.getsignal(signal.SIGTERM))
    signal.signal(signal.SIGALRM, expired)
    signal.signal(signal.SIGTERM, terminated)
    left = ORIGIN + 60 - time.monotonic()
    if left <= 0:
        raise TimeoutError("original-startup-endpoint")
    signal.setitimer(signal.ITIMER_REAL, left)
    return saved


STARTUP = enter_startup() if __name__ == "__main__" else None
import argparse
import os
from pathlib import Path
HERE = Path(__file__).absolute().parent
sys.path.insert(0, str(HERE))
sys.path.insert(1, str(HERE / "legacy"))
import common as U
import adapter as A
import outer
from package_contract import PACKAGE_FILES


def source_capture(capture, expected):
    manifest = U.parse(capture.read(HERE / "SOURCE_MANIFEST.json", 65536, expected))
    U.need(set(manifest) == {"schema", "task_id", "source_only", "files", "qualification_added"} and
           manifest["schema"] == "gcamp8_transitive_recovery_source_v1" and
           manifest["task_id"] == U.TASK and manifest["source_only"] is True and
           manifest["qualification_added"] is False and
           set(manifest["files"]) == set(PACKAGE_FILES), "complete-exact-recovery-source")
    for name in PACKAGE_FILES:
        U.need(not Path(name).is_absolute() and ".." not in Path(name).parts,
               "closed-recovery-source-name")
        capture.read(HERE / name, 1048576, manifest["files"][name])
    return manifest


def main(argv=None):
    global FINAL_ENDPOINT
    saved, primary, result = STARTUP, None, None
    failures = []
    try:
        if saved is None:
            saved = enter_startup()
        U.need(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
               "isolated-no-site-nonwriting-original-entry")
        U.need(type(sys.pycache_prefix) is str and bool(sys.pycache_prefix),
               "explicit-disabled-cache-prefix")
        cache = U.literal(sys.pycache_prefix)
        U.need(not os.path.lexists(cache), "disabled-cache-absent")
        parser = argparse.ArgumentParser(description=__doc__)
        for name in ("program", "output", "review", "source-sha256",
                     "host-selection", "host-selection-sha256"):
            parser.add_argument("--" + name, required=True)
        for name in ("source-bytes", "other-reserve-bytes", "host-selection-bytes"):
            parser.add_argument("--" + name, type=int, required=True)
        args = parser.parse_args(argv)
        capture = U.Capture(ORIGIN + 60)
        expected = U.descriptor({"bytes": args.source_bytes, "sha256": args.source_sha256}, 65536)
        manifest = source_capture(capture, expected)
        legacy_source = manifest["files"]["legacy/SOURCE_MANIFEST.json"]
        binding, control, _ = A.sources(capture, legacy_source)
        plan = A.bind(args, capture, expected, binding, control)
        U.need(not plan["output"].is_relative_to(HERE) and not HERE.is_relative_to(plan["output"]),
               "disjoint-complete-recovery-source-and-output")
        host, host_operand = capture.document({
            "path": args.host_selection, "bytes": args.host_selection_bytes,
            "sha256": args.host_selection_sha256})
        runtime, _ = capture.document(plan["cfg"]["runtime_receipt"])
        plan["operands"].append(host_operand)
        FINAL_ENDPOINT = ORIGIN + plan["whole"]
        result = outer.execute(plan, binding, control, A, capture, expected, host, runtime, ORIGIN,
                               manifest["files"]["failure_evidence.py"])
        source_capture(capture, expected)
        U.need(not os.path.lexists(cache) and sys.pycache_prefix == str(cache),
               "disabled-cache-remained-absent")
        U.need(signal.getsignal(signal.SIGALRM) is expired and
               signal.getsignal(signal.SIGTERM) is terminated, "same-original-signal-owner")
        capture.tick()
        print(U.encoded(result).decode(), end="", flush=True)
        capture.tick()
    except BaseException as error:
        primary = error
        failures.append(error)
    finally:
        if saved is not None:
            for cleanup in (lambda: signal.setitimer(signal.ITIMER_REAL, 0),
                            lambda: signal.signal(signal.SIGALRM, saved[0]),
                            lambda: signal.signal(signal.SIGTERM, saved[1])):
                try:
                    cleanup()
                except BaseException as error:
                    failures.append(error)
                    if primary is None:
                        primary = error
    if primary is not None:
        raise primary
    U.need(time.monotonic() < FINAL_ENDPOINT, "original-final-return-cutoff")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

