"""Metadata-only execute() ordering controls; never Docker or real predictions.

Fake Provider receipts are deliberately not valid native closure evidence.
Separate grading and provenance suites test the real admission implementations.
Here their explicit gates exercise the actual coordinator's sequence and aborts.
"""
from contextlib import ExitStack
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C
import grading
import provenance as P
import workflow as W


class CoordinatorControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="sleep007-coordinator-generated-")
        cls.root = Path(cls.temp.name).resolve()
        cls.created_bytes = 0
        cls.created_files = 0
        cls.write_original = C.write

        def accounted_write(file, raw, mode=0o600):
            if not C.path(file).is_relative_to(cls.root):
                raise AssertionError("generated coordinator writes stay in owned temp directory")
            if cls.created_bytes + len(raw) > 128 * 2**10:
                raise AssertionError("cumulative generated metadata ceiling")
            value = cls.write_original(file, raw, mode)
            cls.created_bytes += len(raw)
            cls.created_files += 1
            return value

        cls.writer = mock.patch.object(C, "write", side_effect=accounted_write)
        cls.writer.start()
        cls.addClassCleanup(cls.writer.stop)
        cls.addClassCleanup(cls.temp.cleanup)
        cls.source = {"schema": "sleep007_finite_source_v1", "files": {
            name: C.pin(C.snapshot(C.HERE / name, 2**20)) for name in C.RUNTIME_FILES}}
        cls.source_descriptor = C.write(cls.root / "SOURCE.json", C.json_bytes(cls.source))
        # Actual metadata authentication only; the scientific arrays are absent.
        cls.profile = json.loads(C.read(*C.original("profile")))
        cls.assets = json.loads(C.read(*C.original("assets")))
        expected_paths = {row["path"] for row in cls.profile["training"] + cls.profile["helpers"]
                          + [r for unit in cls.profile["units"] for r in unit["active_inputs"]]}
        cls.public_map = {name: str(cls.root / ("absent-public-" + str(i)))
                          for i, name in enumerate(sorted(expected_paths))}
        cls.locations = C.write(cls.root / "LOCATIONS.json", C.json_bytes({
            "schema": "sleep007_public_locations_v1", "files": cls.public_map}))
        cls.exposures = {case: C.write(cls.root / (case + "-EXPOSURE.json"), C.json_bytes({
            "schema": "invented_exposure_for_sequence_control", "case": case})) for case, _ in C.SPEC_CASES}
        cls.programme = C.write(cls.root / "candidate.py", b"# Invented fixture; never executed.\n")
        cls.references = {name: {"path": str(cls.root / ("absent-" + name + ".npz")),
                                 **C.plain(cls.assets["comparators"][name])} for name in ("YASA", "RF")}
        cls.viewer = {"path": str(cls.root / "absent-viewer.npz"), **P.VIEWER_SUBMISSION}

    @classmethod
    def tearDownClass(cls):
        retained = sum(p.stat().st_size for p in cls.root.rglob("*") if p.is_file())
        assert retained == cls.created_bytes <= 128 * 2**10
        cls.temp.cleanup()
        assert not cls.root.exists()
        print("GENERATED_COORDINATOR_ACCOUNTING=" + json.dumps({
            "created_files": cls.created_files, "cumulative_metadata_bytes": cls.created_bytes,
            "peak_retained_metadata_bytes": retained, "owned_temporary_directory_removed": True,
            "filesystem_overhead_bytes": None, "authentic_arrays": False,
            "prediction_files_are_small_invented_text_not_npz": True}, sort_keys=True))

    def setUp(self):
        self.events = []
        self.native_calls = []
        self.phase_checks = []
        self.mode = None
        run_root = self.root / self._testMethodName
        self.prepared = W.freeze(self.programme["path"], self.source_descriptor, run_root)
        self.config = {"schema": "sleep007_finite_execution_v1", "prepared": self.prepared,
                       "public_locations": self.locations, "viewer_proof": {"invented": "old-accepted-proof"},
                       "viewer": self.viewer, "references": self.references,
                       "private_locations": {"path": str(self.root / "PRIVATE_MUST_NOT_BE_OPENED"),
                                             **C.pin(b"invented-private-location-descriptor")},
                       "provider": {"docker_binary": "/invented/not-invoked/docker", "docker_socket": "/invented/no-socket"},
                       "exposures": self.exposures}
        self.attempt = run_root / "attempt"

    def provider_module(self):
        owner = self

        class FakeProvider:
            def __init__(self, control, quarantine, binary, socket, source, exposures, read_limit, write_limit):
                owner.events.append("provider_created")
                owner.assertEqual((binary, socket), ("/invented/not-invoked/docker", "/invented/no-socket"))
                owner.assertEqual(exposures, {v["sha256"]: v["path"] for v in owner.exposures.values()})
                owner.assertEqual((read_limit, write_limit), (65 * 2**20, 16 * 2**20))
                self.control, self.quarantine = control, quarantine
                self.read_used, self.write_used = 0, 0
                self.results = {}

            def execute_phase(self, request, mounts, deadline, journal):
                index = len(owner.native_calls)
                case, epochs = C.SPEC_CASES[index]
                owner.events.append("execute:" + case)
                owner.native_calls.append((request, mounts, deadline))
                owner.assertEqual(request["clock"]["phase_deadline"], request["clock"]["origin"] + 110 * (index + 1))
                owner.assertEqual(deadline, request["clock"]["origin"] + W.GLOBAL_SECONDS)
                owner.assertEqual(request["command"], C.PROGRAMME_COMMAND)
                owner.assertEqual(request["resources"], C.PROGRAMME_RESOURCES)
                # Genuine make_mounts() must expose only the active person's inputs.
                active = next(u for u in owner.profile["units"] if u["unit_id"] == case)
                allowed = owner.profile["training"] + owner.profile["helpers"] + active["active_inputs"]
                owner.assertEqual(set(mounts), {r["mount_destination"] for r in allowed} | {
                    "/input/case.json", "/input/public_validation.py", "/program/program.py",
                    "/trusted/PROGRAMME.json", "/trusted/common.py", "/trusted/producer.py"})
                for row in allowed:
                    exposure = mounts[row["mount_destination"]]
                    owner.assertEqual(exposure["path"], owner.public_map[row["path"]])
                    owner.assertEqual(list(exposure["files"].values()), [C.plain(row)])
                    owner.assertFalse(Path(exposure["path"]).exists())
                if index == 1:
                    owner.assertIn("check:development-001", owner.events)
                if owner.mode == "second_phase_failure" and index == 1:
                    raise RuntimeError("generated second phase failure")
                journal("invented_phase_started", {"case": case})
                control = self.control / request["phase_id"]
                control.mkdir()
                request_descriptor = C.write(control / "REQUEST.json", C.json_bytes(request))
                output = self.quarantine / case
                output.mkdir()
                predictions = C.write(output / "predictions.npz", b"invented metadata only; deliberately not an NPZ\n")
                result = C.write(output / "RESULT.json", C.json_bytes({"case": case, "invented": True}))
                receipt = {"status": "captured", "request_sha256": request_descriptor["sha256"],
                           "quarantine_root": str(output), "generated_closed": not (owner.mode == "open_closure" and index == 1),
                           "output_inventory": {"files": {"RESULT.json": C.plain(result), "predictions.npz": C.plain(predictions)}},
                           "timing": {"original_deadline": deadline, "started": request["clock"]["origin"] + index * 3,
                                      "finished": request["clock"]["origin"] + index * 3 + 1}}
                descriptor = C.write(control / "RECEIPT.json", C.json_bytes(receipt))
                captured = {"receipt": receipt, "receipt_pin": C.plain(descriptor), "receipt_path": descriptor["path"]}
                self.results[request["phase_id"]] = captured
                self.read_used += 1
                self.write_used += predictions["bytes"] + result["bytes"]
                return captured

            def observe(self, phase_id, request_sha256, receipt_pin, deadline):
                captured = self.results[phase_id]
                owner.events.append("observe:" + phase_id)
                owner.assertEqual(request_sha256, captured["receipt"]["request_sha256"])
                owner.assertEqual(receipt_pin, captured["receipt_pin"])
                owner.assertEqual(deadline, captured["receipt"]["timing"]["original_deadline"])
                return {"receipt": captured["receipt"], "receipt_pin": receipt_pin, "invented_observer": True}

        return types.SimpleNamespace(Provider=FakeProvider, encoded=C.json_bytes)

    def phase_gate(self, row, definition, definition_pin, source_files, profile, case):
        self.events.append("check:" + case)
        self.phase_checks.append(case)
        request = json.loads(C.descriptor_read(row["request"]))
        receipt = json.loads(C.descriptor_read(row["receipt"]))
        self.assertEqual(request["source"], definition_pin)
        self.assertEqual(definition["programme"], C.plain(self.programme))
        self.assertEqual(set(source_files), C.RUNTIME_FILES)
        if not receipt["generated_closed"]:
            raise ValueError("generated closure admission refused")
        return request, receipt

    def public_gate(self, viewer, parts, references):
        self.events.append("public_validation")
        self.assertEqual(viewer, self.viewer)
        self.assertEqual(references, self.references)
        self.assertEqual(set(parts), {c for c, _ in C.SPEC_CASES})
        self.assertTrue((self.attempt / "PROGRAMME_COMMIT.json").is_file())
        self.assertEqual(len(self.native_calls), 2)
        self.assertEqual(self.phase_checks, ["development-001", "development-002"] * 2)
        if self.mode == "public_validation_failure":
            raise ValueError("generated public validation refused")

    def grade_boundary(self, request_descriptor, root, deadline):
        self.events.append("grade_dispatch")
        self.assertEqual(self.events[-2], "public_validation")
        self.assertEqual(len(self.native_calls), 2)
        self.assertEqual(root, self.attempt)
        self.assertEqual(deadline, self.native_calls[0][2])
        request = json.loads(C.descriptor_read(request_descriptor))
        self.assertEqual(request["private_locations"], self.config["private_locations"])
        self.assertFalse(Path(request["private_locations"]["path"]).exists())
        commit = json.loads(C.descriptor_read(request["programme_commit"]))
        self.assertEqual(commit["parts"], request["parts"])
        self.assertEqual(set(commit["phases"]), {case for case, _ in C.SPEC_CASES})
        # Deliberately no process, private loader or metric result is created.
        return {"generated_dispatch_boundary_only": True}

    def run_execute(self):
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(C, "load_provider", return_value=self.provider_module()))
            stack.enter_context(mock.patch.object(P, "admit_viewer", side_effect=lambda *args: self.events.append("old_viewer_admitted")))
            stack.enter_context(mock.patch.object(P, "check_phase", side_effect=self.phase_gate))
            self.public = stack.enter_context(mock.patch.object(grading, "validate_public", side_effect=self.public_gate))
            self.dispatch = stack.enter_context(mock.patch.object(W, "dispatch_grade", side_effect=self.grade_boundary))
            return W.execute(self.config)

    def test_two_sequential_frozen_phases_public_admission_then_fresh_grade_boundary(self):
        descriptor = self.run_execute()
        complete = json.loads(C.descriptor_read(descriptor))
        self.assertEqual(complete["status"], "complete")
        self.assertEqual((complete["people"], complete["epochs"]), (2, 5450))
        self.assertFalse(complete["scientific_qualification"])
        self.assertFalse(complete["automatic_retry"])
        self.assertEqual(complete["grade"], {"generated_dispatch_boundary_only": True})
        self.public.assert_called_once()
        self.dispatch.assert_called_once()
        self.assertEqual([e for e in self.events if e.startswith("execute:")], ["execute:development-001", "execute:development-002"])
        self.assertLess(self.events.index("check:development-001"), self.events.index("execute:development-002"))
        self.assertEqual(self.events[-2:], ["public_validation", "grade_dispatch"])
        prepared = json.loads(C.descriptor_read(self.prepared))
        frozen = Path(prepared["programme"]["path"])
        self.assertEqual(frozen.stat().st_mode & 0o777, 0o444)
        self.assertEqual(C.snapshot(frozen, 200000), b"# Invented fixture; never executed.\n")
        self.assertEqual(self.native_calls[0][0]["source"], self.native_calls[1][0]["source"])

    def test_second_phase_failure_prevents_commit_public_gate_and_grade(self):
        self.mode = "second_phase_failure"
        with self.assertRaisesRegex(RuntimeError, "generated second phase"):
            self.run_execute()
        self.assertEqual(len(self.native_calls), 2)
        self.assertEqual(self.phase_checks, ["development-001"])
        self.public.assert_not_called()
        self.dispatch.assert_not_called()
        self.assertFalse((self.attempt / "PROGRAMME_COMMIT.json").exists())
        self.assertFalse((self.attempt / "COMPLETE.json").exists())

    def test_open_second_closure_prevents_commit_public_gate_and_grade(self):
        self.mode = "open_closure"
        with self.assertRaisesRegex(ValueError, "generated closure"):
            self.run_execute()
        self.assertEqual(len(self.native_calls), 2)
        self.assertEqual(self.phase_checks, ["development-001", "development-002"])
        self.public.assert_not_called()
        self.dispatch.assert_not_called()
        self.assertFalse((self.attempt / "PROGRAMME_COMMIT.json").exists())
        self.assertFalse((self.attempt / "COMPLETE.json").exists())

    def test_public_validation_failure_keeps_commit_but_prevents_grade_request_and_dispatch(self):
        self.mode = "public_validation_failure"
        with self.assertRaisesRegex(ValueError, "generated public validation"):
            self.run_execute()
        self.public.assert_called_once()
        self.dispatch.assert_not_called()
        self.assertTrue((self.attempt / "PROGRAMME_COMMIT.json").exists())
        self.assertFalse((self.attempt / "GRADE_REQUEST.json").exists())
        self.assertFalse((self.attempt / "COMPLETE.json").exists())


if __name__ == "__main__":
    unittest.main()
