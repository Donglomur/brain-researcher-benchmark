"""Portable bounded runner for the maintained25 generated Generic controls.

Default CI executes every frozen method. --select supports a named delivery-only
check without claiming a new25-pass result. Outputs stay outside the source tree.
"""
import argparse
import json
import os
from pathlib import Path
import resource
import sys
import unittest

METHOD_SCHEMA = "meg-generic-classification-control-methods/v1"
FIXTURE_LIMIT = 1572864
WRITER_LIMIT = 1441792
LOG_LIMIT = 131072


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def validate_method_ids(discovered, expected):
    if (type(expected) is not list or len(expected) != 25
            or any(type(value) is not str for value in expected)
            or expected != sorted(set(expected))):
        raise ValueError("exact sorted25-method manifest required")
    if len(discovered) != len(set(discovered)) or set(discovered) != set(expected):
        raise ValueError("discovered methods differ from the complete frozen25-method roster")


def discover_suite(test_root, selected=()):
    document = json.loads((test_root / "CONTROL_METHODS.json").read_text())
    if set(document) != {"schema", "methods", "scope"} or document["schema"] != METHOD_SCHEMA:
        raise ValueError("fixed method manifest schema required")
    cases = list(flatten(unittest.defaultTestLoader.discover(str(test_root), pattern="test_*.py")))
    identifiers = [case.id() for case in cases]
    validate_method_ids(identifiers, document["methods"])
    selected = list(selected) if selected else list(document["methods"])
    if len(selected) != len(set(selected)) or not set(selected) <= set(identifiers):
        raise ValueError("selected methods must be unique members of the fixed roster")
    return unittest.TestSuite(case for case in cases if case.id() in selected), sorted(selected), sorted(identifiers)


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
        # Emit the same bounded unittest transcript for the maintained dispatcher.
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--output", required=True)
    parser.add_argument("--select", action="append", default=[])
    args = parser.parse_args(argv)
    source, output = Path(args.source).resolve(), Path(args.output).resolve(strict=False)
    test_root = Path(__file__).resolve().parent
    if output.exists() or not output.parent.is_dir() or output == source or source in output.parents:
        raise ValueError("fresh output under an existing external parent required")
    resource.setrlimit(resource.RLIMIT_CPU, (110, 110))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1048576, 1048576))
    os.umask(0o077)
    os.environ["MEG_CONTROL_OUTPUT"] = str(output)
    sys.path[:0] = [str(source), str(test_root)]
    # Discovery validates the complete maintained roster even for --select.
    suite, selected_ids, discovered_ids = discover_suite(test_root, args.select)
    import storage
    import prepare
    import generic_prepare
    import run
    modules = (storage, prepare, generic_prepare, run)
    old_writers = [(module, module.write) for module in modules]
    original_write = storage.write
    written = [0]
    def bounded_write(path, body, *arguments, **keywords):
        if written[0] + len(body) > WRITER_LIMIT:
            raise ValueError("cumulative generated artifact writer allowance exhausted")
        written[0] += len(body)
        return original_write(path, body, *arguments, **keywords)
    log = BoundedLog(output.with_suffix(".log"), sys.stderr)
    try:
        for module in modules:
            module.write = bounded_write
        result = unittest.TextTestRunner(verbosity=2, stream=log, resultclass=RecordingResult).run(suite)
        retained = sum(p.stat().st_size for p in output.rglob("*") if p.is_file()) if output.exists() else 0
        positive = sorted(result.positive_method_ids)
        successful = (result.wasSuccessful() and not result.skipped and positive == selected_ids
                      and retained <= FIXTURE_LIMIT and log.attempted == log.retained)
        report = {"scope": "generated_source_controls_no_fits_no_native",
            "full_maintained_suite": not args.select, "discovered_method_ids": discovered_ids,
            "selected_method_ids": selected_ids, "positive_method_ids": positive,
            "tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
            "skips": len(result.skipped), "successful": successful,
            "retained_generated_bytes": retained, "fixture_write_limit_bytes": FIXTURE_LIMIT,
            "shared_writer_reserved_bytes": written[0], "local_log_limit_bytes": LOG_LIMIT,
            "local_log_retained_bytes": log.retained, "local_log_attempted_bytes": log.attempted,
            "local_log_truncated": log.attempted > log.retained,
            "physical_io_or_aggregate_rss_measured": False}
        # A grade-only selection has no generated tree; retain its report too.
        output.mkdir(mode=0o700, exist_ok=True)
        (output / "CONTROL_RESULT.json").write_text(json.dumps(report, indent=2) + "\n")
        return 0 if successful else 1
    finally:
        for module, original in old_writers:
            module.write = original
        log.close()


if __name__ == "__main__":
    raise SystemExit(main())
