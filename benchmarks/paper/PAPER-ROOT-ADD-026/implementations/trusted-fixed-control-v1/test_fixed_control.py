"""Small generated fixtures for the complete fixed temporal026 controller.

The real observation/record control materializes one invented response table and
five invented variable files once. Full 79-electrode/2054-job support is metadata;
no authentic arrays, fits, native campaigns or large prediction bank are used.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent


def dependency_directories(here, environ):
    """Public adjacent components, explicit overrides, or private-phase defaults."""
    adjacent_interface = here.parent / "prediction-interface-v1"
    adjacent_producer = here.parent / "source-model-producer-v1"
    private_interface = here.parents[2] / "completion15-v1/temporal-prediction/source/benchmarks/paper/PAPER-ROOT-ADD-026/implementations/prediction-interface-v1"
    private_producer = Path("/Users/nicholas/Documents/Codex/neuro-repository-overhaul-20261116-v1/benchmarks/paper/PAPER-ROOT-ADD-026/implementations/source-model-producer-v1")
    return (Path(environ["TEMPORAL_INTERFACE_DIR"]) if "TEMPORAL_INTERFACE_DIR" in environ else
            adjacent_interface if adjacent_interface.is_dir() else private_interface,
            Path(environ["TEMPORAL_PRODUCER_DIR"]) if "TEMPORAL_PRODUCER_DIR" in environ else
            adjacent_producer if adjacent_producer.is_dir() else private_producer)


INTERFACE, PRODUCER = dependency_directories(HERE, os.environ)
FIXTURES = HERE / "generated-tests"
FIXTURES.mkdir(exist_ok=True)
tempfile.tempdir = str(FIXTURES)
os.environ["TEMPORAL_REPLAY_DIR"] = str(PRODUCER.parent / "source-cv-replay-v1")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


control = load("temporal16_control_generated", HERE / "fixed_control.py")
zero = load("temporal16_zero_generated", HERE / "zero_rule.py")
interface = load("temporal16_interface_generated", INTERFACE / "protocol.py")
submissions = load("temporal16_submissions_generated", INTERFACE / "submissions.py")
source_tests = load("temporal16_original_generated_fixture", PRODUCER / "test_producer.py")
WRITTEN = 0
WRITE_LIMIT = 240 * 1024
original_budget_write = control.WriteBudget.write
original_submission_write = submissions._write


def precharge(raw):
    global WRITTEN
    if WRITTEN + len(raw) > WRITE_LIMIT - 150000:
        raise ValueError("generated test write allowance would be exceeded")
    WRITTEN += len(raw)


def budget_write(self, path, value, cap):
    precharge(control.encoded(value))
    return original_budget_write(self, path, value, cap)


def submission_write(fd, name, raw):
    precharge(raw)
    return original_submission_write(fd, name, raw)


control.WriteBudget.write = budget_write
submissions._write = submission_write


class FixedControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source_tests.ProducerControls.setUpClass()
        cls.addClassCleanup(source_tests.ProducerControls.doClassCleanups)
        cls.fixture = source_tests.ProducerControls()
        cls.source = interface.Source(PRODUCER)
        cls.protocols = {
            branch: interface.Protocol(plan, plan["plan_sha256"], cls.fixture.manifest,
                                       hashlib.sha256((HERE / "zero_rule.py").read_bytes()).hexdigest(),
                                       "paper_data", cls.source)
            for branch, plan in cls.fixture.plans.items()
        }
        cls.protocol = cls.protocols["named_response_columns"]
        cls.cv = next(job for job in cls.protocol.delivery_jobs if job["mode"] == "cv")

    def directory(self):
        tmp = tempfile.TemporaryDirectory(prefix="fixed-control-", dir=FIXTURES)
        self.addCleanup(tmp.cleanup)
        return Path(tmp.name)

    def one_byte_bindings(self):
        sha = hashlib.sha256(b"x").hexdigest()
        pin = lambda name: {"path": name, "bytes": 1, "sha256": sha}
        return {"responses": {str(i): pin("response-%02d" % i) for i in range(79)},
                "variables": {str(i): pin("variable-%d" % i) for i in range(5)}}

    def score(self):
        rows, electrodes = [], []
        for e_index, electrode in enumerate(self.source.replay.cohort()):
            scores = [None if e_index == 0 and fold == 0 else -0.25 for fold in range(12)]
            for scaling in ("none", "S"):
                for fold, value in enumerate(scores):
                    values = ([{"value": None, "status": "undefined_source_r2", "zero_observed_variance": True}] * 6
                              if value is None else [{"value": value, "status": "finite"}] * 6)
                    rows.append({"job_id": electrode["id"] + "/DN-" + scaling + "/fold%02d" % fold,
                                 "status": "submitted", "condition_r2": values,
                                 "rounded_condition_r2": None if value is None else [value] * 6,
                                 "fold_r2": value})
                electrodes.append({**electrode, "scaling": scaling, "fold_r2": list(scores),
                                   "r2": None if None in scores else -0.25})
        return {"protocol_sha256": self.protocol.protocol_sha256,
                "plan_sha256": self.protocol.plan_sha256, "method_sha256": self.protocol.method_sha256,
                "condition": "paper_data", "source_branch": "named_response_columns",
                "complete_job_count": 2054, "failures": [],
                "candidate_status_counts": {"submitted": 2054, "failed": 0, "cv": 1896, "full": 158},
                "cv_cells": rows, "electrode_cv": electrodes,
                "figure3_regional_cv": [{"scaling": "none", "median": -0.2}, {"scaling": "S", "median": -0.3}]}

    def test_dependencies_support_explicit_overrides_and_public_adjacent_components(self):
        explicit = dependency_directories(HERE, {"TEMPORAL_INTERFACE_DIR": "/generated/interface",
                                                 "TEMPORAL_PRODUCER_DIR": "/generated/producer"})
        self.assertEqual(explicit, (Path("/generated/interface"), Path("/generated/producer")))
        root = self.directory() / "implementations"
        (root / "fixed-control-v1").mkdir(parents=True)
        (root / "prediction-interface-v1").mkdir()
        (root / "source-model-producer-v1").mkdir()
        self.assertEqual(dependency_directories(root / "fixed-control-v1", {}),
                         (root / "prediction-interface-v1", root / "source-model-producer-v1"))

    def test_zero_rule_accepts_only_original_counts_and_takes_no_observations(self):
        self.assertEqual(list(inspect.signature(zero.predict).parameters), ["query_count"])
        for count in (6, 72):
            with mock.patch("builtins.open", side_effect=AssertionError("zero rule opened a file")), \
                 mock.patch("os.open", side_effect=AssertionError("zero rule opened a descriptor")):
                result = zero.predict(count)
            self.assertEqual(len(result), count)
            self.assertTrue(all(len(row) == 819 and all(type(x) is int and x == 0 for x in row) for row in result))
        for count in (True, 6.0, 0, 5, 73, "6"):
            with self.assertRaises(ValueError):
                zero.predict(count)
        with self.assertRaises(TypeError):
            zero.predict(6, observations=[999])

    def test_zero_rule_has_no_cross_call_prediction_state(self):
        first = zero.predict(6)
        first[0][0] = 99
        second = zero.predict(6)
        self.assertEqual(second[0][0], 0)
        self.assertIsNot(first[0], second[0])

    def test_actual_original_projection_to_one_zero_prediction_record(self):
        observations = {}
        for branch, protocol in self.protocols.items():
            observation = protocol.project_job(self.fixture.root, self.cv["id"])
            branch_job = protocol.job_info(self.cv["id"])["job"]
            self.assertEqual(control.inspect_observation(protocol, branch_job, observation), 6)
            self.assertEqual(len(observation["training"]), 66)
            self.assertTrue(all("response" not in row for row in observation["queries"]))
            observations[branch] = observation
        named = observations["named_response_columns"]["training"][0]
        positional = observations["source_positional_cv"]["training"][0]
        self.assertEqual(positional["response"], [float(positional["temp_cond"])] + named["response"][:-1])
        directory = self.directory()
        prediction = zero.predict(6)
        pin = submissions.write_record(directory, self.protocol, self.cv["id"], predictions=prediction)
        saved = json.loads((directory / pin["path"]).read_text())
        self.assertEqual(saved["predictions"], [[0] * 819] * 6)
        self.assertEqual(saved["status"], "submitted")
        self.assertEqual(saved["job_id"], self.cv["id"])
        self.assertNotIn("observations", saved)
        self.assertEqual(hashlib.sha256((directory / pin["path"]).read_bytes()).hexdigest(), pin["sha256"])

    def test_full_projection_stays_named_and_exposed_within_positional_branch(self):
        protocol = self.protocols["source_positional_cv"]
        full = next(job for job in protocol.delivery_jobs if job["mode"] == "full")
        observation = protocol.project_job(self.fixture.root, full["id"])
        self.assertEqual(control.inspect_observation(protocol, full, observation), 72)
        self.assertEqual(observation["column_branch"], "named_response_columns")
        self.assertEqual(len(observation["training"]), 72)
        self.assertEqual(observation["training"][0]["response"], self.fixture.observed)

    def test_observation_guard_refuses_query_payload_order_and_sample_loss(self):
        original = self.protocol.project_job(self.fixture.root, self.cv["id"])
        mutations = [lambda d: d["queries"][0].update(response=[1]),
                     lambda d: d["queries"].reverse(),
                     lambda d: d["training"][0]["response"].pop(),
                     lambda d: d.update(method_sha256="0" * 64)]
        for mutation in mutations:
            changed = copy.deepcopy(original)
            mutation(changed)
            with self.assertRaises(ValueError):
                control.inspect_observation(self.protocol, self.cv, changed)

    def test_full_score_metadata_preserves_undefined_without_forcing_regional_equality(self):
        checks = control.fixed_score_checks(self.score(), self.protocol)
        self.assertEqual(checks, {"paired_cv_coordinates_equal": 948, "paired_electrodes_equal": 79,
                                  "undefined_fold_scores_preserved": 2, "regional_bootstrap_equality_required": False})

    def test_score_guard_refuses_none_S_cell_and_electrode_mismatches(self):
        changed = self.score()
        next(row for row in changed["cv_cells"] if "/DN-S/" in row["job_id"] and row["fold_r2"] is not None)["fold_r2"] = -0.2501
        with self.assertRaisesRegex(ValueError, "paired source slots differ"):
            control.fixed_score_checks(changed, self.protocol)
        changed = self.score()
        changed["electrode_cv"][1]["r2"] = 0.0
        with self.assertRaisesRegex(ValueError, "electrode slots differ"):
            control.fixed_score_checks(changed, self.protocol)

    def test_score_guard_refuses_extra_and_replacing_duplicate_CV_rows(self):
        for extra in (False, True):
            changed = self.score()
            if extra:
                changed["cv_cells"].append(copy.deepcopy(changed["cv_cells"][0]))
            else:
                changed["cv_cells"][-1] = copy.deepcopy(changed["cv_cells"][0])
            with self.assertRaises(ValueError):
                control.fixed_score_checks(changed, self.protocol)

    def test_score_guard_refuses_extra_and_replacing_duplicate_electrodes(self):
        for extra in (False, True):
            changed = self.score()
            if extra:
                changed["electrode_cv"].append(copy.deepcopy(changed["electrode_cv"][0]))
            else:
                changed["electrode_cv"][-1] = copy.deepcopy(changed["electrode_cv"][0])
            with self.assertRaises(ValueError):
                control.fixed_score_checks(changed, self.protocol)

    def test_score_guard_refuses_wrong_branch_method_and_incomplete_panel(self):
        for key, value in (("source_branch", "source_positional_cv"), ("method_sha256", "0" * 64),
                           ("complete_job_count", 2053), ("failures", [{"job": "x", "status": "failed"}])):
            changed = self.score()
            changed[key] = value
            with self.assertRaises(ValueError):
                control.fixed_score_checks(changed, self.protocol)

    def test_source_reads_full28440_multiplicity_on_one_byte_generated_inputs(self):
        bindings = self.one_byte_bindings()
        calls, checkpoints = [], []
        def reader(root, pin):
            calls.append(pin["path"])
            return b"x"
        # Scale only the input-byte total for this generated one-byte source
        # seam; original100/4108 multiplicities and28440calls remain unchanged.
        with mock.patch.object(control, "EXPECTED_RETURNED_BYTES", 28440):
            reads = control.SourceReads("generated-bank", bindings, reader, lambda: checkpoints.append(1))
            for values, count in ((bindings["responses"], 100), (bindings["variables"], 4108)):
                for pin in values.values():
                    for _ in range(count):
                        self.assertEqual(reads("generated-bank", pin), b"x")
            summary = reads.summary(complete=True)
            self.assertEqual(summary["logical_source_read_attempts"], 28440)
            self.assertEqual(summary["logical_source_returned_bytes"], 28440)
            self.assertEqual(summary["logical_source_requested_allowance_including_eof_probes"], 56880)
            self.assertEqual(len(checkpoints), 56880)
            with self.assertRaisesRegex(ValueError, "multiplicity exceeded"):
                reads("generated-bank", bindings["responses"]["0"])
            self.assertEqual(len(calls), 28440)

    def test_source_reads_pin_root_and_complete_support_guards(self):
        bindings = self.one_byte_bindings()
        calls = []
        reads = control.SourceReads("generated-bank", bindings, lambda *args: calls.append(args) or b"x", lambda: None)
        pin = bindings["responses"]["0"]
        for root, changed in (("different-bank", pin), ("generated-bank", {**pin, "sha256": "0" * 64}),
                              ("generated-bank", {**pin, "path": "../outside"})):
            with self.assertRaises(ValueError):
                reads(root, changed)
        self.assertEqual(calls, [])
        self.assertEqual(reads.summary()["logical_source_read_attempts"], 0)
        with self.assertRaisesRegex(ValueError, "full source-read support"):
            reads.summary(complete=True)
        bindings["responses"].pop("0")
        with self.assertRaisesRegex(ValueError, "all79responses"):
            control.SourceReads("generated-bank", bindings, lambda *args: b"x", lambda: None)

    def test_source_reads_failed_attempt_retains_full_allowance(self):
        bindings = self.one_byte_bindings()
        def failure(*args):
            raise OSError("generated source read failure")
        reads = control.SourceReads("generated-bank", bindings, failure, lambda: None)
        with self.assertRaises(OSError):
            reads("generated-bank", bindings["responses"]["0"])
        summary = reads.summary()
        row = next(row for row in summary["rows"] if row["name"] == "0" and row["role"] == "response")
        self.assertEqual((row["attempts"], row["returned_bytes"], row["unknown_failed_allowance"]), (1, 0, 2))
        self.assertEqual(summary["logical_source_requested_allowance_including_eof_probes"], 2)
        with self.assertRaises(ValueError):
            reads.summary(complete=True)

    def test_write_budget_exclusive_failure_is_charged_without_overwrite(self):
        path = self.directory() / "receipt.json"
        budget = control.WriteBudget(1024)
        pin = budget.write(path, {"a": 1}, 100)
        before = path.read_bytes()
        self.assertEqual(path.stat().st_mode & 0o777, 0o400)
        with self.assertRaises(FileExistsError):
            budget.write(path, {"a": 2}, 100)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(budget.charged, len(before) + len(control.encoded({"a": 2})))
        self.assertEqual(pin["sha256"], hashlib.sha256(before).hexdigest())

    def test_write_budget_partial_failure_retains_file_and_precharge(self):
        path = self.directory() / "partial.json"
        budget = control.WriteBudget(1024)
        with mock.patch.object(control.os, "fsync", side_effect=OSError("generated fsync failure")):
            with self.assertRaises(OSError):
                budget.write(path, {"partial": True}, 100)
        self.assertTrue(path.exists())
        self.assertEqual(path.read_bytes(), control.encoded({"partial": True}))
        self.assertEqual(budget.charged, len(path.read_bytes()))
        with self.assertRaises(ValueError):
            budget.charge("no-refund", 1024, "cannot reuse failed allowance")

    def test_write_budget_caps_precede_write_and_reject_bool_or_negative_charges(self):
        directory = self.directory()
        budget = control.WriteBudget(20)
        with self.assertRaises(ValueError):
            budget.write(directory / "too-large.json", {"oversize": "a" * 30}, 10)
        self.assertEqual(budget.charged, 0)
        self.assertEqual(list(directory.iterdir()), [])
        for value in (-1, True, 21):
            with self.assertRaises(ValueError):
                budget.charge("bad", value, "generated")

    def coordinator(self, fail_second=False):
        output = self.directory()
        events = []
        bindings = self.one_byte_bindings()
        pipeline = {"branch_order": ["source_positional_cv", "named_response_columns"],
                    "condition": "paper_data", "bootstrap_seed": 19,
                    "expected_interface_bytes": dict(control.INTERFACE_BYTES)}
        p = {"pipeline": pipeline, "output": {"reserved_bytes": 128 * 1024**2},
             "source_limits": {"calls": 28440, "returned_bytes": 9387131288,
                               "requested_bytes_with_eof": 9387131288 + 28440},
             "zero_rule": {"path": "generated-rule", "sha256": "3" * 64},
             "input_bindings": {"path": "generated-bindings"},
             "prior_input_join": {"path": "generated-prior"},
             "expected_ordered_metadata_sha256": "a" * 64, "expected_manifest_sha256": "b" * 64,
             "expected_plans": {branch: str(index + 1) * 64 for index, branch in enumerate(control.BRANCHES)},
             "input_root": "generated-bank"}
        def read_pin(pin):
            if pin["path"] == "generated-bindings":
                return control.encoded(bindings)
            if pin["path"] == "generated-prior":
                return control.encoded({"ordered_metadata": {"generated": True}})
            return b"generated source seam"
        admission = types.SimpleNamespace(protocol=p, protocol_sha256="c" * 64,
                                          create_output=lambda: output, read_pin=read_pin,
                                          checkpoint=lambda: None, report=lambda: {"generated_seam": True},
                                          meters=types.SimpleNamespace(snapshot=lambda: {"generated_seam": True}),
                                          activate_numpy=lambda: events.append("activate_numpy"))
        source = types.SimpleNamespace(
            replay=types.SimpleNamespace(digest=lambda metadata: "a" * 64,
                                         freeze=lambda metadata, seed: {"manifest_sha256": "b" * 64}),
            producer=types.SimpleNamespace(make_plan=lambda manifest, sha, inputs, branch, replay:
                                           {"plan_sha256": p["expected_plans"][branch], "branch": branch},
                                           read_member=lambda *args: b"x"))
        fake_interface = types.SimpleNamespace(Source=lambda path: source,
                                              Protocol=lambda plan, sha, manifest, method, condition, source:
                                              types.SimpleNamespace(branch=plan["branch"]))
        staged = {name: (output / name, b"generated source") for name in (
            "prediction-interface-v1/protocol.py", "prediction-interface-v1/delivery.py",
            "prediction-interface-v1/submissions.py", "source-model-producer-v1/producer.py")}
        def module(name, path, raw):
            return fake_interface if name == "temporal_control_interface" else types.SimpleNamespace()
        def collect(protocol, branch, *args):
            events.append("collect:" + branch)
            if fail_second and branch == "named_response_columns":
                raise ValueError("generated second panel failure")
            return {"branch": branch, "observations": 2054, "commitment": {"generated_complete": True}}
        def score(protocol, row, *args):
            self.assertIn("collect:source_positional_cv", events)
            self.assertIn("collect:named_response_columns", events)
            events.append("score:" + row["branch"])
            return {"branch": row["branch"], "generated_score": True}
        class FakeReads:
            def __init__(self, *args):
                pass
            def summary(self, complete=False):
                if complete:
                    assert events[-1] == "score:named_response_columns"
                return {"generated_metadata_only": True, "complete": complete}
        with mock.patch.object(control, "stage_interfaces", return_value=staged), \
             mock.patch.object(control, "load_bytes_module", side_effect=module), \
             mock.patch.object(control, "SourceReads", FakeReads), \
             mock.patch.object(control, "collect_branch", side_effect=collect), \
             mock.patch.object(control, "score_branch", side_effect=score):
            if fail_second:
                with self.assertRaisesRegex(ValueError, "second panel failure"):
                    control.execute(admission)
                self.assertTrue((output / "FAILURE.json").exists())
                self.assertFalse((output / "RESULT.json").exists())
            else:
                result = control.execute(admission)
                self.assertEqual(result["status"], "completed")
                self.assertFalse(result["scientific_qualification"])
        return events

    def test_coordinator_collects_both_full_panels_before_any_metric_phase(self):
        self.assertEqual(self.coordinator(), ["activate_numpy", "collect:source_positional_cv",
                                             "collect:named_response_columns", "score:source_positional_cv",
                                             "score:named_response_columns"])

    def test_second_collection_failure_never_runs_either_metric_phase(self):
        events = self.coordinator(fail_second=True)
        self.assertEqual(events, ["activate_numpy", "collect:source_positional_cv", "collect:named_response_columns"])


if __name__ == "__main__":
    suite = (unittest.TestSuite(FixedControlTests(name) for name in sys.argv[1:]) if len(sys.argv) > 1
             else unittest.defaultTestLoader.loadTestsFromTestCase(FixedControlTests))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    total = WRITTEN + getattr(source_tests.ProducerControls, "generated_fixture_bytes", 0)
    print(json.dumps({"generated_cumulative_application_write_charge_bytes": total,
                      "generated_write_limit_bytes": WRITE_LIMIT,
                      "authentic_array_reads": 0, "native_execution": False,
                      "full_coordinator_scope": "generated trusted seams only; no full numerical panels"}))
    raise SystemExit(0 if result.wasSuccessful() and total <= WRITE_LIMIT else 1)
