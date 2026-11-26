"""Generated-only controls for optional framework timing; no framework discovery."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "framework_timing_under_test", ROOT / "scripts/maintenance/run_framework_shard.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class Clock:
    def __init__(self, value=0):
        self.value = value

    def __call__(self):
        return self.value

    def advance(self, amount):
        self.value += amount


class FrameworkTimingTests(unittest.TestCase):
    def cases(self, methods):
        selected = type("Selected", (unittest.TestCase,),
                        dict(methods, __module__="_a_timing_selected"))

        def forbidden(case):
            raise AssertionError("unassigned generated case executed")

        other = type("Other", (unittest.TestCase,),
                     {"__module__": "_z_timing_other", "test_other": forbidden})
        return [selected(name) for name in sorted(methods)] + [other("test_other")]

    def run_cases(self, tests, clock):
        tests, plan = runner.make_plan(unittest.TestSuite(tests), len(tests))
        output, errors = io.StringIO(), io.StringIO()
        with mock.patch.object(runner, "_perf_counter_ns", clock):
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                code = runner.run_shard(tests, plan, 0)
        lines = output.getvalue().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("FRAMEWORK_SHARD_PLAN "))
        self.assertTrue(lines[1].startswith("FRAMEWORK_SHARD_RESULT "))
        return code, json.loads(lines[1].split(" ", 1)[1]), errors.getvalue()

    def test_elapsed_intervals_align_with_ids_without_repeat(self):
        clock, calls = Clock(), []

        def first(case):
            calls.append("a")
            clock.advance(7)

        def second(case):
            calls.append("b")
            clock.advance(11)

        tests = self.cases({"test_b": second, "test_a": first})
        assigned = [test.id() for test in tests[:-1]]
        code, result, _ = self.run_cases(tests, clock)
        self.assertEqual(code, 0)
        self.assertEqual(calls, ["a", "b"])
        for key in ("assigned_ids", "started_ids", "stopped_ids"):
            self.assertEqual(result[key], assigned)
        self.assertEqual(result["testsRun"], 2)
        self.assertEqual(result["full_count"], 3)
        self.assertEqual(result["timing"]["test_elapsed_ns"], [7, 11])
        self.assertEqual(result["timing"]["run_elapsed_ns"], 18)
        self.assertEqual(result["timing"]["unattributed_run_elapsed_ns"], 0)

    def test_fixture_trace_matches_plain_unittest_and_residual_is_separate(self):
        def fixture(clock, trace):
            def event(name, cost):
                trace.append(name)
                clock.advance(cost)

            module = types.ModuleType("_a_timing_fixture")
            module.setUpModule = lambda: event("module.setup", 40)
            module.tearDownModule = lambda: event("module.teardown", 50)

            class Fixture(unittest.TestCase):
                @classmethod
                def setUpClass(cls):
                    event("class.setup", 20)

                @classmethod
                def tearDownClass(cls):
                    event("class.teardown", 30)

                def setUp(self):
                    event("test.setup", 5)
                    self.addCleanup(event, "test.cleanup", 3)

                def tearDown(self):
                    event("test.teardown", 7)

                def test_a(self):
                    event("a", 11)

                def test_b(self):
                    event("b", 13)

            Fixture.__module__ = module.__name__
            Fixture.__qualname__ = "Fixture"
            return module, [Fixture("test_a"), Fixture("test_b")]

        baseline_clock, baseline_trace = Clock(), []
        module, tests = fixture(baseline_clock, baseline_trace)
        with mock.patch.dict(sys.modules, {module.__name__: module}):
            baseline = unittest.TextTestRunner(stream=io.StringIO(), verbosity=2).run(
                unittest.TestSuite(tests))
        clock, trace = Clock(), []
        module, tests = fixture(clock, trace)
        other = self.cases({"test_unused": lambda case: None})[-1]
        with mock.patch.dict(sys.modules, {module.__name__: module}):
            code, result, _ = self.run_cases(tests + [other], clock)
        self.assertTrue(baseline.wasSuccessful())
        self.assertEqual(code, 0)
        self.assertEqual(trace, baseline_trace)
        self.assertEqual(result["testsRun"], baseline.testsRun)
        self.assertEqual(result["timing"]["test_elapsed_ns"], [26, 28])
        self.assertEqual(result["timing"]["run_elapsed_ns"], 194)
        self.assertEqual(result["timing"]["unattributed_run_elapsed_ns"], 140)
        self.assertIn("Discovery and outer JSON emission are excluded", result["timing"]["scope"])

    def test_original_result_fields_and_outcomes_are_preserved(self):
        def success(case):
            pass

        def failure(case):
            case.fail("generated failure")

        def error(case):
            raise RuntimeError("generated error")

        def expected_failure(case):
            case.fail("generated expected failure")

        def unexpected_success(case):
            pass

        cases = [("success", success, 0, None),
                 ("failure", failure, 1, "failures"),
                 ("error", error, 1, "errors"),
                 ("skip", unittest.skip("generated skip")(success), 0, "skipped"),
                 ("expected", unittest.expectedFailure(expected_failure), 0, "expectedFailures"),
                 ("unexpected", unittest.expectedFailure(unexpected_success), 1, "unexpectedSuccesses")]
        keys = {"schema", "shard", "census_sha256", "full_count", "assigned_ids", "started_ids",
                "stopped_ids", "testsRun", "complete", "successful", "failures", "errors",
                "skipped", "expectedFailures", "unexpectedSuccesses", "timing"}
        for name, method, expected_code, outcome in cases:
            with self.subTest(outcome=name):
                tests = self.cases({"test_generated": method})
                identity = tests[0].id()
                code, result, _ = self.run_cases(tests, Clock())
                self.assertEqual(set(result), keys)
                self.assertEqual(code, expected_code)
                self.assertEqual(result["schema"], "framework-shard-result/v1")
                self.assertTrue(result["complete"])
                self.assertEqual(result["successful"], expected_code == 0)
                self.assertEqual(result["testsRun"], 1)
                self.assertTrue(result["timing"]["complete"])
                for field in ("failures", "errors", "skipped", "expectedFailures", "unexpectedSuccesses"):
                    expected = ([{"id": identity, "reason": "generated skip"}] if field == "skipped"
                                else [identity]) if field == outcome else []
                    self.assertEqual(result[field], expected)

    def test_run_interval_excludes_runner_and_suite_construction(self):
        clock, events = Clock(), []

        def generated(case):
            events.append("case")
            clock.advance(9)

        tests = self.cases({"test_a": generated})
        tests, plan = runner.make_plan(unittest.TestSuite(tests), len(tests))
        plain_runner, plain_suite = unittest.TextTestRunner, unittest.TestSuite

        def construct_runner(*args, **kwargs):
            events.append("runner")
            clock.advance(100)
            return plain_runner(*args, **kwargs)

        def construct_suite(*args, **kwargs):
            events.append("suite")
            clock.advance(200)
            return plain_suite(*args, **kwargs)

        output = io.StringIO()
        with mock.patch.object(runner, "_perf_counter_ns", clock):
            with mock.patch.object(unittest, "TextTestRunner", construct_runner):
                with mock.patch.object(unittest, "TestSuite", construct_suite):
                    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
                        code = runner.run_shard(tests, plan, 0)
        result = json.loads(output.getvalue().splitlines()[-1].split(" ", 1)[1])
        self.assertEqual(code, 0)
        self.assertEqual(events, ["runner", "suite", "case"])
        self.assertEqual(result["timing"]["test_elapsed_ns"], [9])
        self.assertEqual(result["timing"]["run_elapsed_ns"], 9)
        self.assertEqual(result["timing"]["unattributed_run_elapsed_ns"], 0)

    def test_invalid_clock_values_do_not_change_controls(self):
        for value in (None, True, -1, 1.5, float("nan"), "bad"):
            with self.subTest(value=repr(value)):
                calls = []
                tests = self.cases({"test_generated": lambda case: calls.append("ran")})
                code, result, _ = self.run_cases(tests, lambda: value)
                self.assertEqual(code, 0)
                self.assertEqual(calls, ["ran"])
                self.assertFalse(result["timing"]["complete"])
                self.assertNotIn("test_elapsed_ns", result["timing"])

    def test_raising_clock_does_not_interrupt_suite(self):
        def broken():
            raise OSError("generated clock error")

        code, result, _ = self.run_cases(self.cases({"test_a": lambda case: None}), broken)
        self.assertEqual(code, 0)
        self.assertEqual(result["testsRun"], 1)
        self.assertFalse(result["timing"]["complete"])

    def test_backward_clock_is_not_valid_measurement(self):
        values = iter([10, 20, 15, 40])
        code, result, _ = self.run_cases(self.cases({"test_a": lambda case: None}),
                                         lambda: next(values))
        self.assertEqual(code, 0)
        self.assertFalse(result["timing"]["complete"])

    def test_total_smaller_than_test_intervals_is_not_valid_measurement(self):
        values = iter([10, 20, 80, 40])
        code, result, _ = self.run_cases(self.cases({"test_a": lambda case: None}),
                                         lambda: next(values))
        self.assertEqual(code, 0)
        self.assertFalse(result["timing"]["complete"])

    def test_captured_clock_survives_alias_replacement_during_case(self):
        clock = Clock(100)

        def generated(case):
            runner._perf_counter_ns = lambda: None
            clock.advance(9)

        code, result, _ = self.run_cases(self.cases({"test_a": generated}), clock)
        self.assertEqual(code, 0)
        self.assertTrue(result["timing"]["complete"])
        self.assertEqual(result["timing"]["test_elapsed_ns"], [9])
        self.assertEqual(result["timing"]["run_elapsed_ns"], 9)

    def test_incomplete_callbacks_never_claim_complete_timing(self):
        test = self.cases({"test_a": lambda case: None})[0]
        result = runner.RecordedResult(io.StringIO(), True, 0)
        result._clock = Clock()
        result.startTest(test)
        self.assertFalse(result.timing([test.id()], 0, 10)["complete"])
        self.assertEqual(result.started, [test.id()])
        self.assertEqual(result.stopped, [])

    def test_mismatched_and_duplicate_callbacks_are_not_valid_measurements(self):
        tests = self.cases({"test_a": lambda case: None, "test_b": lambda case: None})
        for duplicate in (False, True):
            with self.subTest(duplicate=duplicate):
                result = runner.RecordedResult(io.StringIO(), True, 0)
                result._clock = Clock()
                result.startTest(tests[0])
                if duplicate:
                    result.startTest(tests[0])
                result.stopTest(tests[1])
                self.assertFalse(result.timing([tests[0].id()], 0, 10)["complete"])

    def test_invalid_partition_still_fails_before_case_execution(self):
        calls = []
        tests = self.cases({"test_a": lambda case: calls.append("ran")})
        tests, plan = runner.make_plan(unittest.TestSuite(tests), 2)
        plan["assignments"] = [[0], [0]]
        with self.assertRaisesRegex(ValueError, "full census"):
            runner.run_shard(tests, plan, 0)
        self.assertEqual(calls, [])

    def emit(self, base, timing, limit):
        output, errors = io.StringIO(), io.StringIO()
        with mock.patch.object(runner, "REPORT_LIMIT", limit):
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                runner.emit_result(base, timing)
        return output.getvalue(), errors.getvalue()

    def extent(self, value):
        return len(runner.encoded(value)) + len("FRAMEWORK_SHARD_RESULT ") + 1

    def test_report_limit_omits_only_optional_timing_detail(self):
        base = {"assigned_ids": ["exact.test.id"], "failures": ["exact.test.id"]}
        minimal = {"schema": "framework-shard-timing/v1", "complete": False,
                   "reason": "report_limit"}
        limit = self.extent(dict(base, timing=minimal)) + 1
        output, errors = self.emit(base, {"test_elapsed_ns": [1] * 1000}, limit)
        report = json.loads(output.split(" ", 1)[1])
        self.assertEqual(report.pop("timing"), minimal)
        self.assertEqual(report, base)
        self.assertLess(len(output.encode()), limit)
        self.assertEqual(errors, "")

    def test_near_limit_preserves_full_original_report_when_marker_wont_fit(self):
        base = {"assigned_ids": ["exact.test.id"], "errors": ["exact.test.id"]}
        output, errors = self.emit(base, {"test_elapsed_ns": [1] * 1000}, self.extent(base) + 1)
        self.assertEqual(output, "FRAMEWORK_SHARD_RESULT " + runner.encoded(base).decode() + "\n")
        self.assertIn("timing unavailable", errors)

    def test_existing_report_overflow_still_raises(self):
        base = {"assigned_ids": ["exact.test.id"]}
        with self.assertRaisesRegex(ValueError, "exceeds 256 KiB"):
            self.emit(base, {"complete": True}, self.extent(base))

    def test_large_generated_result_retains_all_ids_and_does_not_raise_cap(self):
        identities = ["module.Class.test_" + str(index) + "x" * 80 for index in range(421)]
        base = {"assigned_ids": identities, "started_ids": identities, "stopped_ids": identities,
                "testsRun": 421, "failures": [], "errors": []}
        timing = {"complete": True, "test_elapsed_ns": [9999999999999999999] * 421}
        output, _ = self.emit(base, timing, 256 * 1024)
        result = json.loads(output.split(" ", 1)[1])
        self.assertEqual(result.pop("timing"), timing)
        self.assertEqual(result, base)
        self.assertEqual(runner.REPORT_LIMIT, 256 * 1024)
        self.assertLess(len(output.encode()), runner.REPORT_LIMIT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
