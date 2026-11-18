#!/usr/bin/env python3
"""Run one of two deterministic, whole-module framework unittest shards."""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
REPORT_LIMIT = 256 * 1024


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def emit(value, prefix=""):
    body = encoded(value)
    if len(body) + len(prefix.encode()) + 1 >= REPORT_LIMIT:
        raise ValueError("framework report exceeds 256 KiB")
    print(prefix + body.decode(), flush=True)


def make_plan(suite, expected_count):
    tests = []

    def visit(item):
        if type(item) is unittest.TestSuite:
            for child in item:
                visit(child)
        elif isinstance(item, unittest.TestCase):
            tests.append(item)
        else:
            raise ValueError("custom suite semantics are not supported")
    visit(suite)
    ids = [test.id() for test in tests]
    if expected_count < 1 or len(tests) != expected_count or suite.countTestCases() != expected_count:
        raise ValueError("framework count differs from expected %d" % expected_count)
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate framework test IDs")
    modules = {}
    for index, test in enumerate(tests):
        modules.setdefault(type(test).__module__, []).append(index)
    groups, loads = [], [0, 0]
    for module in sorted(modules, key=lambda name: (-len(modules[name]), name)):
        shard = min(range(2), key=lambda value: (loads[value], value))
        indices = modules[module]
        groups.append({"module": module, "shard": shard, "indices": indices})
        loads[shard] += len(indices)
    assignments = [sorted(index for group in groups if group["shard"] == shard
                          for index in group["indices"]) for shard in range(2)]
    if any(not part for part in assignments):
        raise ValueError("both framework shards must be nonempty")
    if sorted(assignments[0] + assignments[1]) != list(range(expected_count)):
        raise ValueError("framework partition is not an exhaustive disjoint union")
    census = [[test.id(), type(test).__module__] for test in tests]
    plan = {"schema": "framework-shard-plan/v1", "expected_count": expected_count,
            "full_count": len(tests), "census_sha256": hashlib.sha256(encoded(census)).hexdigest(),
            "test_ids": ids, "module_groups": groups, "assignments": assignments}
    if len(encoded(plan)) > REPORT_LIMIT:
        raise ValueError("framework discovery plan exceeds 256 KiB")
    return tests, plan


def discover_plan(expected_count):
    loader = unittest.TestLoader()
    with contextlib.redirect_stdout(sys.stderr):
        suite = loader.discover(str(ROOT / "tests/framework"), pattern="test_*.py")
    if loader.errors:
        raise ValueError("framework discovery failed:\n" + "\n".join(loader.errors))
    return make_plan(suite, expected_count)


class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.started, self.stopped = [], []

    def startTest(self, test):
        self.started.append(test.id())
        super().startTest(test)

    def stopTest(self, test):
        self.stopped.append(test.id())
        super().stopTest(test)


def run_shard(tests, plan, shard):
    census = [[test.id(), type(test).__module__] for test in tests]
    if (plan["full_count"] != len(tests) or plan["expected_count"] != len(tests)
            or plan["test_ids"] != [row[0] for row in census]
            or plan["census_sha256"] != hashlib.sha256(encoded(census)).hexdigest()
            or sorted(plan["assignments"][0] + plan["assignments"][1]) != list(range(len(tests)))):
        raise ValueError("framework execution plan differs from the full census")
    indices = plan["assignments"][shard]
    selected = [tests[index] for index in indices]
    assigned = [test.id() for test in selected]
    if assigned != [plan["test_ids"][index] for index in indices]:
        raise ValueError("selected test objects differ from the discovery plan")
    emit({"shard": shard, "full_count": plan["full_count"],
          "census_sha256": plan["census_sha256"], "assigned_ids": assigned},
         "FRAMEWORK_SHARD_PLAN ")
    result = unittest.TextTestRunner(verbosity=2, failfast=False, buffer=False,
                                    warnings="default", resultclass=RecordedResult).run(
                                        unittest.TestSuite(selected))
    complete = result.started == assigned and result.stopped == assigned and result.testsRun == len(assigned)
    successful = result.wasSuccessful() and complete
    emit({"schema": "framework-shard-result/v1", "shard": shard,
          "census_sha256": plan["census_sha256"], "full_count": plan["full_count"],
          "assigned_ids": assigned, "started_ids": result.started, "stopped_ids": result.stopped,
          "testsRun": result.testsRun, "complete": complete, "successful": successful,
          "failures": [test.id() for test, _ in result.failures],
          "errors": [test.id() for test, _ in result.errors],
          "skipped": [{"id": test.id(), "reason": reason} for test, reason in result.skipped],
          "expectedFailures": [test.id() for test, _ in result.expectedFailures],
          "unexpectedSuccesses": [test.id() for test in result.unexpectedSuccesses]},
         "FRAMEWORK_SHARD_RESULT ")
    return 0 if successful else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-count", required=True, type=int)
    parser.add_argument("--shard-index", type=int, choices=(0, 1))
    parser.add_argument("--list-only", action="store_true", help="discover and emit the full plan; run no tests")
    args = parser.parse_args(argv)
    if args.list_only == (args.shard_index is not None):
        parser.error("choose --list-only or exactly one --shard-index")
    os.chdir(ROOT)
    try:
        tests, plan = discover_plan(args.expected_count)
        if args.list_only:
            emit(plan)
            return 0
        return run_shard(tests, plan, args.shard_index)
    except (ValueError, OSError) as exc:
        print("framework shard refused: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
