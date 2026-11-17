"""Generated restricted-episode controls; no containers or participant execution.

Reuses the frozen v2 tiny fixture builder, not its test suite. Original material
admission, v2 freezes and numerical evaluation remain real. Only the unavailable
runtime qualification/provider and unsupported active-owner boundaries are
replaced by explicit fakes. This is internal source composition only, not a
working protected benchmark. A separate test proves the real owner refusal.
"""
from contextlib import contextmanager
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import site
import stat
import sys
import unittest
from unittest.mock import patch

import h5py
import numpy as np


HERE = Path(__file__).resolve().parent


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, filename)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


episode = module("smc_episode_controls", HERE / "episode.py")
worker = module("smc_worker_controls", HERE / "worker.py")
fixture_path = HERE.parent / "continuous-outcomes-v2/test_benchmark.py"
if hashlib.sha256(fixture_path.read_bytes()).hexdigest() != "c2c926fb1fa058a765c5b01c6e4ba7d6dc1d1aa566e7ab1b92013257cb121f8d":
    raise ValueError("Frozen generated fixture source changed")
fx = module("smc_frozen_asset_fixture", fixture_path)
fx.benchmark = episode.benchmark()
F = fx.AssetAccessTests
bench = fx.benchmark


def write(path, raw):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fx.write_bytes(path, raw)


def save(path, value):
    write(path, episode.encoded(value))


def file_pin(path):
    return episode.pin(Path(path).read_bytes())


@contextmanager
def preserved(*paths):
    values = {Path(p): (Path(p).read_bytes(), stat.S_IMODE(Path(p).stat().st_mode)) for p in paths}
    try:
        for path in values:
            path.chmod(0o600)
        yield
    finally:
        for path, (raw, mode) in values.items():
            path.chmod(0o600)
            write(path, raw)
            path.chmod(mode)


def make_protocol(root, outcome="improvement", qualification_value=None):
    root.mkdir()
    programs, declarations = {}, {}
    for condition in episode.CONDITIONS:
        programs[condition] = root / (condition + ".py")
        write(programs[condition], ("# Generated " + condition + "\nraise AssertionError('NEVER EXECUTE ON HOST')\n").encode())
        obj = F()
        obj.condition = condition
        declaration = obj.declaration(outcome)
        for row in declaration["methods"].values():
            row["source_sha256"] = fx.sha(programs[condition])
        declarations[condition] = root / (condition + ".declaration.json")
        save(declarations[condition], declaration)
    qualification = root / "qualification.json"
    save(qualification, qualification_value or {"generated_unavailable_runtime_boundary": True})
    runtime = root / "runtime.json"
    save(runtime, {"schema": "smc_restricted_runtime_v1", "image": "sha256:" + "1" * 64,
        "docker_binary": str(root / "UNAVAILABLE_DOCKER"), "docker_socket": str(root / "UNAVAILABLE_SOCKET"),
        "qualification": {"path": str(qualification), **file_pin(qualification)},
        "source_read_bytes": 64 * 1024**2, "host_write_bytes": 16 * 1024**2})
    destination = root / "protocol"
    result = episode.instantiate(F.pair_path, F.task, outcome, programs, declarations, runtime,
                                 fx.sha(runtime), destination)
    return {"root": root, "protocol": destination / "PROTOCOL.json", "protocol_sha": fx.sha(destination / "PROTOCOL.json"),
            "document": result, "programs": programs, "declarations": declarations, "runtime": runtime}


class GeneratedProvider:
    """Only a generated provider seam: no subprocess, Docker or model calls."""
    mode = None
    calls = []
    instances = []
    owner_events = []
    contract = None
    bounds = None
    engine = None

    def __init__(self, control, quarantine, binary, socket, source, exposures, read_limit, write_limit):
        self.control, self.quarantine = Path(control), Path(quarantine)
        self.exposures = exposures
        self.results = {}
        self.__class__.instances.append(self)

    def execute_phase(self, request, mounts, deadline, journal):
        self.contract.validate_request(request, mounts, deadline)
        # Use the independently retained provider ABI, never the caller's helper.
        request_sha = hashlib.sha256(self.engine.encoded(request)).hexdigest()
        self.contract.validate_exposure(json.loads(Path(self.exposures[request["exposure"]["sha256"]]).read_text()), request, mounts)
        meter = self.bounds.Meter(64 * 1024**2, 1, deadline)
        observed_inputs = {target: self.bounds.tree(desc, meter) for target, desc in mounts.items()}
        jobs = self.control.parent / "jobs"
        assert all((jobs / c / "REQUEST.json").exists() and (jobs / c / "EXPOSURE.json").exists() for c in episode.CONDITIONS)
        self.calls.append({"request": copy.deepcopy(request), "mounts": copy.deepcopy(mounts)})
        condition = request["phase_id"]
        journal("OWNERSHIP", {"phase_id": condition, "generated_wiring_only": True})
        job = json.loads(Path(mounts["/execution.json"]["path"]).read_text())
        folder = self.quarantine / condition
        folder.mkdir()
        files = {}
        for key in job["submission_keys"]:
            output = folder / (key + ".h5")
            write(output, F.predictions[key].read_bytes())
            files[output.name] = file_pin(output)
        result = {"schema": "smc_restricted_program_result_v1", "outcome": job["outcome"], "condition": condition,
                  "program_sha256": job["program_sha256"], "declaration_sha256": job["declaration_sha256"],
                  "submission_keys": job["submission_keys"]}
        save(folder / "RESULT.json", result)
        files["RESULT.json"] = file_pin(folder / "RESULT.json")
        save(folder / "OUTPUTS.json", {"schema": "osl_transport_output_manifest_v1", "phase_id": condition,
            "request_sha256": request_sha, "files": files})
        files["OUTPUTS.json"] = file_pin(folder / "OUTPUTS.json")
        receipt = {"phase_id": condition, "request_sha256": request_sha,
            "status": "captured", "producer_closed_before_capture": True, "all_native_resources_closed": True,
            "cli_reaped": True, "source": request["source"], "image": request["image"], "role": request["role"],
            "enforced_resource_limits": request["resources"], "quarantine_root": str(folder),
            "exposure": request["exposure"], "input_before": observed_inputs, "input_after": observed_inputs,
            "output_inventory": {"complete": True, "files": files}}
        if self.mode == "unclosed":
            receipt["all_native_resources_closed"] = False
        self.control.joinpath(condition).mkdir()
        receipt_path = self.control / condition / "RECEIPT.json"
        save(receipt_path, receipt)
        value = {"receipt": receipt, "receipt_pin": file_pin(receipt_path), "receipt_path": str(receipt_path)}
        self.results[condition] = copy.deepcopy(value)
        if self.mode == "changed_prediction":
            target = folder / (job["submission_keys"][0] + ".h5")
            with h5py.File(target, "r+") as handle:
                handle[bench.source.DATASET]["eval_rates_heldout"][0, 0, 0] += 0.5
            fx.charge(target.stat().st_size)
        if self.mode == "changed_second_program" and condition == episode.CONDITIONS[0]:
            first = Path(mounts["/program/program.py"]["path"])
            second = first.parent.parent / episode.CONDITIONS[1] / "program.py"
            second.chmod(0o600)
            write(second, b"# forbidden post-first-release replacement\n")
        return value

    def observe(self, phase_id, request_sha, receipt_pin, deadline):
        request = next(call["request"] for call in self.calls if call["request"]["phase_id"] == phase_id)
        assert request_sha == hashlib.sha256(self.engine.encoded(request)).hexdigest(), "Wrong retained request ABI at observe"
        assert receipt_pin == self.results[phase_id]["receipt_pin"], "Wrong saved receipt identity at observe"
        value = copy.deepcopy(self.results[phase_id])
        if self.mode == "observation_mismatch":
            value["receipt"]["image"] = "sha256:" + "2" * 64
        return {"receipt": value["receipt"], "receipt_pin": value["receipt_pin"]}


@contextmanager
def unavailable_runtime(mode=None):
    GeneratedProvider.mode = mode
    GeneratedProvider.calls = []
    GeneratedProvider.instances = []
    GeneratedProvider.owner_events = []
    def journal(name, value):
        GeneratedProvider.owner_events.append({"name": name, "value": copy.deepcopy(value)})
    with patch.object(episode, "qualify", return_value={"image_inventory_sha256": "3" * 64}), \
         patch.object(episode, "active_owner_journal", return_value=journal), \
         patch.object(episode, "_PROVIDER", GeneratedProvider):
        yield


class EpisodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary_path = patch.object(fx.tempfile, "tempdir", str(Path(fx.tempfile.gettempdir()).resolve()))
        temporary_path.start()
        cls.addClassCleanup(temporary_path.stop)
        F.setUpClass()
        cls.addClassCleanup(F.doClassCleanups)
        # Preserve the authentic 71-file interface with more tiny source files;
        # no geometry, original phase validation or packet-count check is mocked.
        count = 1 + sum(len(json.loads((F.pair_root / c / "delivery_manifest.json").read_text())["files"]) + 1
                        for c in episode.CONDITIONS)
        source = json.loads(F.code_manifest.read_text())
        for index in range(71 - count):
            name = "generated_source_" + str(index) + ".py"
            write(F.author / name, b"# generated source-only fixture\n")
            source["files"].append({"path": name, "role": "source", **file_pin(F.author / name)})
        save(F.code_manifest, source)
        bench.SOURCE_PINS["source_manifest.json"] = fx.sha(F.code_manifest)
        F.budget = copy.deepcopy(episode.PROFILES)
        save(F.budget_path, F.budget)
        F.pair_root = F.root / "episode-pair"
        bench.export_pair(F.inputs, F.author, F.paper, F.task, F.task_sha,
            F.budget_path, F.pair_root, max_bytes=episode.PAIR_CAP, reserve_bytes=0)
        fx.charge(sum(p.stat().st_size for p in F.pair_root.rglob("*") if p.is_file()))
        F.pair_path = F.pair_root / "pair_manifest.json"
        F.pair_sha = fx.sha(F.pair_path)
        for name, value in (("TASK_SHA", F.task_sha), ("PAIR_SHA", F.pair_sha), ("POLICY_SHA", bench.POLICY_SHA256)):
            manager = patch.object(episode, name, value)
            manager.start()
            cls.addClassCleanup(manager.stop)
        episode.source_identity()
        episode.provider_class()  # Authenticate unchanged seven-file provider; no call or socket.
        GeneratedProvider.contract = sys.modules["_smc_existing_transport.contract"]
        GeneratedProvider.bounds = sys.modules["_smc_existing_transport.bounds"]
        GeneratedProvider.engine = sys.modules["_smc_existing_transport.engine"]
        cls.shared = make_protocol(F.root / "shared-protocol")
        cls.shared_execution = F.root / "shared-execution"
        with unavailable_runtime():
            cls.closed = episode.execute(cls.shared["protocol"], cls.shared["protocol_sha"], cls.shared_execution)
        cls.closed_path = cls.shared_execution / "PAIR_CLOSED.json"
        cls.closed_sha = fx.sha(cls.closed_path)
        cls.first_calls = copy.deepcopy(GeneratedProvider.calls)
        cls.first_owner_events = copy.deepcopy(GeneratedProvider.owner_events)

    def setUp(self):
        import tempfile
        self.case = Path(tempfile.mkdtemp(prefix="episode-case-", dir=F.operator))
        self.addCleanup(shutil.rmtree, self.case)
        self.target = self.case / "target.h5"
        self.evaluator = bench.RETAINED / "third_party/nlb_tools_0_0_3/evaluation.py"

    def grade(self, closed_path=None, closed_sha=None, output=None):
        return episode.grade(closed_path or self.closed_path, closed_sha or self.closed_sha,
            self.target, self.evaluator, output or self.case / "grade.json", 2 * 1024**2)

    def test_shared_execution_has_exact_profiles_mounts_and_immutable_capture(self):
        self.assertEqual(len(self.first_calls), 2)
        self.assertTrue(self.closed["both_conditions_closed_before_private_grade"])
        self.assertFalse(self.closed["private_target_accessed"])
        self.assertFalse(self.closed["generic_primary_profile_equivalence"])
        for condition, call in zip(episode.CONDITIONS, self.first_calls):
            limits = call["request"]["resources"]
            self.assertEqual(limits["producer_seconds"], episode.PROFILES["improvement"]["wall_seconds"])
            self.assertEqual(limits["memory_bytes"], 4294967296)
            self.assertEqual(limits["pids"], 1)
            mounts = call["mounts"]
            self.assertFalse(any("test/eval_target" in x for x in mounts))
            self.assertTrue(all("target.h5" not in x["path"] for x in mounts.values()))
            self.assertEqual(any("official_source" in x for x in mounts), condition == episode.CONDITIONS[1])
            if condition == episode.CONDITIONS[1]:
                empty = mounts["/materials/official_source/vi_rnn/__init__.py"]
                self.assertEqual(empty["files"]["__init__.py"]["bytes"], 0)
            row = self.closed["conditions"][condition]
            frozen = episode.read(row["freeze_path"])
            file = Path(frozen["submissions"]["offline"]["path"])
            self.assertEqual(file_pin(file)["sha256"], frozen["submissions"]["offline"]["sha256"])
            self.assertEqual(stat.S_IMODE(file.stat().st_mode), 0o400)

    def test_both_programmes_and_declarations_are_committed_before_dispatch(self):
        protocol = self.shared["document"]
        self.assertTrue(protocol["all_programmes_and_declarations_frozen_before_first_phase"])
        for condition in episode.CONDITIONS:
            folder = self.shared["protocol"].parent / condition
            self.assertEqual(file_pin(folder / "program.py"), protocol["programs"][condition]["program"])
            self.assertEqual(file_pin(folder / "declaration.json"), protocol["programs"][condition]["declaration"])
        # Every generated provider release already asserted both exposure/request
        # files exist and authenticated all mounts through the actual provider ABI.
        self.assertEqual([c["request"]["phase_id"] for c in self.first_calls], list(episode.CONDITIONS))
        self.assertEqual(self.first_owner_events, [{"name": "OWNERSHIP", "value": {
            "phase_id": condition, "generated_wiring_only": True}} for condition in episode.CONDITIONS])

    def test_request_bytes_and_all_receipt_joins_match_retained_engine_abi(self):
        for call in self.first_calls:
            request = call["request"]
            condition = request["phase_id"]
            expected = GeneratedProvider.engine.encoded(request)
            expected_pin = episode.pin(expected)
            jobs = self.shared_execution / "jobs" / condition
            row = self.closed["conditions"][condition]
            self.assertEqual(episode.request_bytes(request), expected)
            self.assertNotEqual(episode.encoded(request), expected)
            self.assertEqual((jobs / "REQUEST.json").read_bytes(), expected)
            self.assertEqual(row["request"], expected_pin)
            receipt = episode.read(row["receipt_path"])
            self.assertEqual(receipt["request_sha256"], expected_pin["sha256"])
            manifest = episode.read(Path(receipt["quarantine_root"]) / "OUTPUTS.json")
            self.assertEqual(manifest["request_sha256"], expected_pin["sha256"])
            exposure = (jobs / "EXPOSURE.json").read_bytes()
            self.assertEqual(exposure, episode.encoded(json.loads(exposure)))
            self.assertEqual(episode.pin(exposure), request["exposure"])
            wrong = dict(receipt, request_sha256=episode.pin(episode.encoded(request))["sha256"])
            with self.assertRaisesRegex(ValueError, "exact phase/profile"):
                episode.validate_closed(request, wrong)
        # Even a rehashed pretty request cannot retain a compact provider receipt.
        condition = episode.CONDITIONS[1]
        request_path = self.shared_execution / "jobs" / condition / "REQUEST.json"
        with preserved(request_path, self.closed_path), patch.object(bench, "score") as private_score:
            save(request_path, episode.read(request_path))
            closed = copy.deepcopy(self.closed)
            closed["conditions"][condition]["request"] = file_pin(request_path)
            save(self.closed_path, closed)
            with self.assertRaisesRegex(ValueError, "Current exact executed request/profile"):
                self.grade(closed_sha=fx.sha(self.closed_path))
            private_score.assert_not_called()
        self.assertFalse((self.shared_execution / "GRADE_STARTED.json").exists())
        self.assertFalse(self.target.exists())

    def test_method_hash_and_changed_program_or_declaration_refuse_before_release(self):
        for filename in ("program.py", "declaration.json"):
            path = self.shared["protocol"].parent / episode.CONDITIONS[1] / filename
            with self.subTest(filename=filename), preserved(path), unavailable_runtime():
                write(path, b"{}\n")
                with self.assertRaises(ValueError):
                    episode.execute(self.shared["protocol"], self.shared["protocol_sha"], self.case / "never-created")
                self.assertEqual(GeneratedProvider.calls, [])
        path = self.case / "bad-program.py"
        write(path, b"# generated different source\n")
        with self.assertRaisesRegex(ValueError, "bind the submitted"):
            episode.instantiate(F.pair_path, F.task, "improvement", dict.fromkeys(episode.CONDITIONS, path),
                self.shared["declarations"], self.shared["runtime"], fx.sha(self.shared["runtime"]), self.case / "bad")
        self.assertFalse((self.case / "bad").exists())

    def test_unsupported_native_runtime_is_refused_before_provider_creation(self):
        with patch.object(episode.sys, "platform", "darwin"), patch.object(episode, "provider_class") as factory, \
             patch.object(episode, "active_owner_journal", return_value=lambda *_: None):
            with self.assertRaisesRegex(ValueError, "qualified Linux"):
                episode.execute(self.shared["protocol"], self.shared["protocol_sha"], self.case / "native-denied")
        factory.assert_not_called()
        self.assertFalse((self.case / "native-denied").exists())

    def test_all_true_runtime_assertions_cannot_bypass_actual_owner_refusal(self):
        assertion = {"schema": "smc_restricted_runtime_qualification_v1", "route": episode.ROUTE,
            "source": episode.source_identity(), "image": "sha256:" + "1" * 64,
            "image_inventory_sha256": "3" * 64, "profiles": episode.PROFILES,
            "single_process_entry_qualified": True, "generic_base_image_without_task_assets_qualified": True}
        protocol = make_protocol(self.case / "all-true-qualification", qualification_value=assertion)
        with patch.object(bench, "inspect_pair") as arrays, patch.object(episode, "qualify") as qualification, \
             patch.object(episode, "provider_class") as factory:
            with self.assertRaisesRegex(NotImplementedError, "unsupported_active_owner"):
                episode.execute(protocol["protocol"], protocol["protocol_sha"], self.case / "owner-refused")
        arrays.assert_not_called()
        qualification.assert_not_called()
        factory.assert_not_called()
        self.assertFalse((self.case / "owner-refused").exists())

    def test_unclosed_or_disagreeing_receipts_never_emit_closed_pair(self):
        for mode in ("unclosed", "observation_mismatch"):
            root = self.case / mode
            with self.subTest(mode=mode), unavailable_runtime(mode):
                with self.assertRaises(ValueError):
                    episode.execute(self.shared["protocol"], self.shared["protocol_sha"], root)
            self.assertEqual(len(GeneratedProvider.calls), 1)
            self.assertFalse((root / "PAIR_CLOSED.json").exists())
            self.assertTrue((root / "FAILED.json").exists())
            self.assertFalse((root / "GRADE_STARTED.json").exists())
        self.assertFalse(self.target.exists())

    def test_post_capture_prediction_drift_refuses_closed_pair(self):
        with unavailable_runtime("changed_prediction"), self.assertRaises(ValueError):
            episode.execute(self.shared["protocol"], self.shared["protocol_sha"], self.case / "changed-capture")
        self.assertFalse((self.case / "changed-capture/PAIR_CLOSED.json").exists())

    def test_second_program_cannot_be_replaced_after_first_release(self):
        protocol = make_protocol(self.case / "mutable-candidate")
        with unavailable_runtime("changed_second_program"), self.assertRaises(ValueError):
            episode.execute(protocol["protocol"], protocol["protocol_sha"], self.case / "second-program-change")
        self.assertEqual(len(GeneratedProvider.calls), 1)
        self.assertFalse((self.case / "second-program-change/PAIR_CLOSED.json").exists())

    def test_changed_receipt_and_second_prediction_fail_before_any_target_read(self):
        row = self.closed["conditions"][episode.CONDITIONS[1]]
        receipt_path = Path(row["receipt_path"])
        with preserved(receipt_path):
            write(receipt_path, b"{}\n")
            with self.assertRaises(ValueError):
                self.grade()
        for field, value in (("image", "sha256:" + "9" * 64), ("role", "A"),
                             ("source", {"bytes": 1, "sha256": "9" * 64}),
                             ("input_after", {}), ("enforced_resource_limits", {})):
            with self.subTest(field=field), preserved(receipt_path, self.closed_path):
                receipt = episode.read(receipt_path)
                receipt[field] = value
                save(receipt_path, receipt)
                closed = copy.deepcopy(self.closed)
                closed["conditions"][episode.CONDITIONS[1]]["receipt"] = file_pin(receipt_path)
                save(self.closed_path, closed)
                with self.assertRaises(ValueError):
                    self.grade(closed_sha=fx.sha(self.closed_path))
        frozen = episode.read(row["freeze_path"])
        prediction = Path(frozen["submissions"]["offline"]["path"])
        with preserved(prediction):
            with h5py.File(prediction, "r+") as handle:
                handle[bench.source.DATASET]["eval_rates_heldout"][0, 0, 0] += 0.5
            fx.charge(prediction.stat().st_size)
            with self.assertRaises(ValueError):
                self.grade()
        self.assertFalse(self.target.exists())
        self.assertFalse((self.shared_execution / "GRADE_STARTED.json").exists())

    def test_complete_original_reproduction_runs_through_freeze_and_numeric_grade(self):
        protocol = make_protocol(self.case / "reproduction", "reproduction")
        execution = self.case / "reproduction-execution"
        with unavailable_runtime():
            episode.execute(protocol["protocol"], protocol["protocol_sha"], execution)
        F.make_target(self.target, 6, 4, 1134)
        closed_path = execution / "PAIR_CLOSED.json"
        with patch.object(bench.source, "TARGET_SHA256", fx.sha(self.target)):
            report = self.grade(closed_path, fx.sha(closed_path))
        self.assertEqual(set(report["conditions"]), set(episode.CONDITIONS))
        with h5py.File(self.target, "r") as handle:
            counts = handle[bench.source.DATASET]["eval_spikes_heldout"][()].astype(float)
        baseline = counts.mean(axis=(0, 1), keepdims=True)
        for condition, result in report["conditions"].items():
            self.assertEqual(len(result["findings"]), 8)
            for arm in ("causal", "noncausal"):
                with h5py.File(F.predictions[arm], "r") as handle:
                    rates = handle[bench.source.DATASET]["eval_rates_heldout"][()].astype(float)
                expected = np.sum(counts * np.log(rates / baseline) + baseline - rates) / counts.sum() / np.log(2)
                self.assertAlmostEqual(result["metrics"][arm]["co-bps"], expected, places=11)
        self.assertFalse(report["AI_attribution_verified"])
        self.assertFalse(report["broader_SOTA_claim"])
        with self.assertRaises(FileExistsError):
            self.grade(closed_path, fx.sha(closed_path), self.case / "second-grade.json")
        self.assertFalse((self.case / "second-grade.json").exists())

    def test_second_condition_grade_failure_keeps_no_partial_paired_report(self):
        protocol = make_protocol(self.case / "grade-failure")
        execution = self.case / "grade-failure-execution"
        with unavailable_runtime():
            episode.execute(protocol["protocol"], protocol["protocol_sha"], execution)
        closed_path = execution / "PAIR_CLOSED.json"
        F.make_target(self.target, 6, 4, 1134)
        original_score = bench.score
        calls = []
        def second_fails(*args, **kwargs):
            calls.append(args[0])
            if len(calls) == 2:
                raise RuntimeError("generated second-condition scorer failure")
            return original_score(*args, **kwargs)
        with patch.object(bench.source, "TARGET_SHA256", fx.sha(self.target)), patch.object(bench, "score", side_effect=second_fails):
            with self.assertRaisesRegex(RuntimeError, "second-condition"):
                self.grade(closed_path, fx.sha(closed_path))
        self.assertEqual(len(calls), 2)
        self.assertFalse((self.case / "grade.json").exists())
        self.assertTrue((execution / "GRADE_STARTED.json").exists())
        self.assertEqual(list(self.case.glob(".smc-private-grade-*")), [])

    def test_successful_improvement_grade_keeps_both_four_vectors_and_deltas(self):
        # The shared capture is complete and no other method grades it. Reuse it
        # once to avoid writing an unnecessary duplicate pair of predictions.
        F.make_target(self.target, 6, 4, 1134)
        with patch.object(bench.source, "TARGET_SHA256", fx.sha(self.target)):
            report = self.grade()
        self.assertEqual(set(report["conditions"]), set(episode.CONDITIONS))
        self.assertIsNone(report["binary_reproduction_or_improvement_win"])
        self.assertFalse(report["cross_condition_averaging"])
        for condition, row in report["conditions"].items():
            values = row["metrics"]["offline"]
            self.assertEqual(set(values), set(bench.source.METRICS))
            self.assertEqual(len(row["comparisons"]), 6)
            self.assertEqual(row["method_specific_smc_co_bps_difference"], values["co-bps"] - 0.3410160879591172)
            self.assertEqual(row["source_paper_NDT_co_bps_difference"], values["co-bps"] - 0.3597)
            self.assertEqual(row["binary_decision"], "not_applicable")
            self.assertFalse(row["AI_attribution_verified"])

    def test_worker_installs_cpu_and_thread_limits_before_candidate_entry(self):
        spec = {"outcome": "improvement", "condition": episode.CONDITIONS[0],
            "resource_profile": episode.PROFILES["improvement"], "submission_keys": ["offline"],
            "program_sha256": "4" * 64, "declaration_sha256": "5" * 64, "max_file_bytes": 100}
        root = self.case / "output"
        root.mkdir()
        save(self.case / "execution.json", spec)
        save(self.case / "request.json", {"phase_id": "generated-worker-only"})
        original_path = Path
        def mapped(value):
            routes = {"/execution.json": self.case / "execution.json", "/request.json": self.case / "request.json", "/output": root}
            return routes.get(str(value), original_path(value))
        events = []
        def setlimit(kind, values):
            events.append((kind, values))
        def site_start():
            self.assertEqual(events[:2], [(worker.resource.RLIMIT_CPU, (7200, 7200)), (worker.resource.RLIMIT_CORE, (0, 0))])
            events.append("site-after-limits")
        def candidate(path, run_name):
            self.assertEqual(events[:2], [(worker.resource.RLIMIT_CPU, (7200, 7200)), (worker.resource.RLIMIT_CORE, (0, 0))])
            self.assertEqual(os.environ["OMP_THREAD_LIMIT"], "1")
            self.assertEqual(events[-1], "site-after-limits")
            self.assertEqual(path, "/program/program.py")
            self.assertEqual(run_name, "__main__")
            write(root / "offline.h5", b"opaque generated worker output")
        with patch.object(worker, "Path", side_effect=mapped), patch.object(worker.resource, "setrlimit", side_effect=setlimit), \
             patch.object(worker.resource, "getrlimit", return_value=(7200, 7200)), patch.object(site, "main", side_effect=site_start), \
             patch.object(worker.runpy, "run_path", side_effect=candidate), patch.dict(os.environ, {}, clear=False), \
             patch.object(worker.sys, "argv", ["test-worker"]):
            worker.main()
        self.assertEqual(set(p.name for p in root.iterdir()), {"offline.h5", "RESULT.json", "OUTPUTS.json"})
        result = json.loads((root / "RESULT.json").read_text())
        self.assertEqual(result["program_sha256"], spec["program_sha256"])

    def test_worker_invalid_cpu_never_enters_participant_code(self):
        save(self.case / "execution.json", {"resource_profile": {"cpu_seconds": True}})
        save(self.case / "request.json", {})
        def mapped(value):
            return self.case / Path(value).name
        with patch.object(worker, "Path", side_effect=mapped), patch.object(worker.resource, "setrlimit") as limits, \
             patch.object(worker.runpy, "run_path") as candidate:
            with self.assertRaises(ValueError):
                worker.main()
        limits.assert_not_called()
        candidate.assert_not_called()
        save(self.case / "execution.json", {"resource_profile": {"cpu_seconds": 7200}})
        with patch.object(worker, "Path", side_effect=mapped), patch.object(worker.resource, "setrlimit") as limits, \
             patch.object(worker.resource, "getrlimit", return_value=(1, 1)), patch.object(site, "main") as hooks, \
             patch.object(worker.runpy, "run_path") as candidate:
            with self.assertRaisesRegex(ValueError, "was not installed"):
                worker.main()
        limits.assert_called_once_with(worker.resource.RLIMIT_CPU, (7200, 7200))
        hooks.assert_not_called()
        candidate.assert_not_called()


def load_tests(loader, standard_tests, pattern):
    # The imported TestCase is a fixture builder only. Explicit discovery avoids
    # accidentally rerunning its previously completed twenty-control suite.
    return loader.loadTestsFromTestCase(EpisodeTests)


if __name__ == "__main__":
    try:
        unittest.main()
    finally:
        print("KNOWN_GENERATED_WRITES_LOWER_BOUND=" + str(fx.KNOWN_WRITTEN_BYTES))
