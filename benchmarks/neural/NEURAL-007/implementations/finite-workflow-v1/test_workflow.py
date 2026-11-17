"""Generated metadata controls; no Docker, recordings, targets or programme run."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C
import provenance as P
import workflow as W


class WorkflowControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="sleep007-generated-workflow-")
        self.root = Path(self.temp.name).resolve()
        self.profile = json.loads(C.read(*C.original("profile")))
        self.programme = {"bytes": 7, "sha256": "a" * 64}
        self.definition = {"programme": self.programme}
        self.definition_pin = {"bytes": 9, "sha256": "b" * 64}
        self.source = {"producer.py": {"bytes": 5, "sha256": "c" * 64},
                       "common.py": {"bytes": 6, "sha256": "d" * 64}}
        self.case = "development-001"
        self.documents = {}

    def tearDown(self):
        self.temp.cleanup()

    def descriptor(self, name, value):
        raw = C.json_bytes(value)
        result = {"path": str(self.root / name), **C.pin(raw)}
        self.documents[result["path"]] = raw
        return result

    def read_document(self, value, cap=2**20):
        raw = self.documents[value["path"]]
        self.assertEqual(C.pin(raw), C.plain(value))
        self.assertLessEqual(len(raw), cap)
        return raw

    def phase(self, change=None):
        request = {"schema": "osl_owned_phase_request_v1", "phase_id": "sleep007_development_001", "action": "held_attempt", "role": "A",
                   "image": C.IMAGE, "source": self.definition_pin, "exposure": {"bytes": 10, "sha256": "e" * 64},
                   "command": W.COMMAND, "resources": dict(W.RESOURCES), "workdir": "/work",
                   "clock": {"origin": 1000., "phase_deadline": 1110.},
                   "output": {"kind": "generic", "manifest": "OUTPUTS.json"}}
        prediction = {"path": str(self.root / "captured/predictions.npz"), "bytes": 30, "sha256": "f" * 64}
        result = self.descriptor("captured/RESULT.json", {"schema": "sleep007_finite_producer_v1", "case_id": self.case,
                  "epochs": 2780, "programme": self.programme, "predictions": C.plain(prediction), "participant_exit": 0})
        expected = P.scientific_inputs(self.profile, self.case)
        expected.update({"/program/program.py": self.programme, "/trusted/PROGRAMME.json": self.definition_pin,
                         "/trusted/producer.py": self.source["producer.py"], "/trusted/common.py": self.source["common.py"]})
        inputs = {target: {"kind": "file", "purpose": "input", "files": {Path(target).name: pin}}
                  for target, pin in expected.items()}
        receipt = {"schema": "osl_owned_phase_receipt_v1", "phase_id": request["phase_id"], "request_sha256": None,
                   "action": request["action"], "role": request["role"], "image": C.IMAGE, "source": self.definition_pin,
                   "exposure": request["exposure"], "status": "captured", "all_native_resources_closed": True,
                   "producer_closed_before_capture": True, "cli_reaped": True, "error": None,
                   "enforced_resource_limits": dict(W.RESOURCES), "deadline_exceeded": False,
                   "timing": {"origin": 1000., "original_deadline": 1260., "phase_deadline": 1101., "started": 1001., "finished": 1002.},
                   "natural_exit": {"ExitCode": 0, "Status": "exited", "Dead": False, "Pid": 0, "Running": False, "OOMKilled": False},
                   "retired_resources": [{"kind": kind, "name": str(i), "closed": True,
                                          "absence_observed": True, "creation_outcome_unknown": False}
                                         for i, kind in enumerate(("container", "container", "volume"))],
                   "input_before": inputs, "input_after": copy.deepcopy(inputs), "quarantine_root": str(self.root / "captured"),
                   "output_inventory": {"complete": True, "files": {"predictions.npz": C.plain(prediction),
                        "RESULT.json": C.plain(result), "OUTPUTS.json": {"bytes": 20, "sha256": "1" * 64}}}}
        if change:
            change(request, receipt)
        req = self.descriptor("request.json", request)
        receipt["request_sha256"] = req["sha256"]
        rec = self.descriptor("receipt.json", receipt)
        obs = self.descriptor("observer.json", {"receipt": receipt, "receipt_pin": C.plain(rec), "independent_candidate_channel": True})
        return {"request": req, "receipt": rec, "observer": obs, "result": result, "predictions": prediction}

    def check(self, record):
        with mock.patch.object(C, "descriptor_read", side_effect=self.read_document):
            return P.check_phase(record, self.definition, self.definition_pin, self.source, self.profile, self.case)

    def test_exact_original_mounts_include_six_train_people_and_only_active_development(self):
        prepared = {"programme": {"path": str(self.root / "program.py"), **self.programme},
                    "definition": {"path": str(self.root / "PROGRAMME.json"), **self.definition_pin}}
        locations = {row["path"]: str(self.root / (str(i) + ".npz")) for i, row in enumerate(
            self.profile["training"] + self.profile["helpers"] + [r for u in self.profile["units"] for r in u["active_inputs"]])}
        source = {"files": self.source}
        first = W.make_mounts(prepared, source, self.profile, locations, "development-001")
        second = W.make_mounts(prepared, source, self.profile, locations, "development-002")
        self.assertEqual(len(first), 28)
        self.assertEqual(set(first), set(second))
        self.assertEqual(sum(target.startswith("/training/labels/") for target in first), 6)
        self.assertEqual(sum(target.startswith("/training/") for target in first), 20)
        self.assertFalse(any("private" in target or "labels" in target and not target.startswith("/training/") for target in first))
        for target in first:
            if target not in ("/input/case.json", "/input/features.npz", "/input/model.npz"):
                self.assertEqual(first[target], second[target])
        self.assertNotEqual(first["/input/features.npz"], second["/input/features.npz"])

    def test_complete_canonical_capture_passes_without_reading_arrays(self):
        request, receipt = self.check(self.phase())
        self.assertEqual(request["action"], "held_attempt")
        self.assertTrue(receipt["producer_closed_before_capture"])

    def test_any_open_uncertain_or_unreaped_producer_blocks_admission(self):
        changes = [lambda q, r: r.update(all_native_resources_closed=False),
                   lambda q, r: r.update(producer_closed_before_capture=False),
                   lambda q, r: r.update(cli_reaped=False),
                   lambda q, r: r["retired_resources"][0].update(closed=False),
                   lambda q, r: r["retired_resources"][0].update(creation_outcome_unknown=True),
                   lambda q, r: r["retired_resources"][0].update(absence_observed=False),
                   lambda q, r: r["retired_resources"][0].update(name="1"),
                   lambda q, r: r["natural_exit"].update(ExitCode=1),
                   lambda q, r: r["natural_exit"].update(ExitCode=False),
                   lambda q, r: r["natural_exit"].update(OOMKilled=True)]
        for change in changes:
            with self.subTest(change=changes.index(change)), self.assertRaises(ValueError):
                self.check(self.phase(change))

    def test_changed_exposure_information_or_source_is_not_another_condition(self):
        changes = [lambda q, r: q.update(image="sha256:" + "0" * 64),
                   lambda q, r: q["resources"].update(producer_seconds=21),
                   lambda q, r: q.update(command=["/usr/bin/python", "unreviewed.py"]),
                   lambda q, r: r["input_before"].update({"/input/labels.npz": {"kind": "file", "files": {}}}),
                   lambda q, r: r["input_before"]["/input/features.npz"]["files"].update({"extra": self.programme}),
                   lambda q, r: r["input_after"].pop("/training/labels/train-006_labels.npz")]
        for change in changes:
            with self.subTest(change=changes.index(change)), self.assertRaises(ValueError):
                self.check(self.phase(change))

    def test_partial_or_relocated_capture_and_changed_observer_fail(self):
        record = self.phase()
        record["predictions"] = {**record["predictions"], "path": str(self.root / "elsewhere.npz")}
        with self.assertRaises(ValueError):
            self.check(record)

    def test_refreshed_or_changed_clock_policy_cannot_be_admitted(self):
        changes = [lambda q, r: q["clock"].update(phase_deadline=1120.),
                   lambda q, r: r["timing"].update(original_deadline=1300.),
                   lambda q, r: r["timing"].update(finished=1200.),
                   lambda q, r: r["timing"].update(started=float("nan")),
                   lambda q, r: r.update(deadline_exceeded=True),
                   lambda q, r: q.update(phase_id="sleep007_development_002"),
                   lambda q, r: r["enforced_resource_limits"].update(producer_seconds=21)]
        for change in changes:
            with self.subTest(change=changes.index(change)), self.assertRaises(ValueError):
                self.check(self.phase(change))
        record = self.phase(lambda q, r: r["output_inventory"].update(complete=False))
        with self.assertRaises(ValueError):
            self.check(record)
        record = self.phase()
        record["observer"] = self.descriptor("changed-observer.json", {"receipt": {}, "receipt_pin": C.plain(record["receipt"]),
                                                                       "independent_candidate_channel": True})
        with self.assertRaises(ValueError):
            self.check(record)

    def test_programme_freeze_precedes_any_input_and_is_exclusive_under_private_umask(self):
        programme = self.root / "candidate.py"
        programme.write_bytes(b"print('generated only')\n")
        source = {"path": str(self.root / "source.json"), "bytes": 1, "sha256": "0" * 64}
        events = []
        original_snapshot = C.snapshot
        with mock.patch.object(C, "authenticate_sources", side_effect=lambda x: events.append("source")), \
             mock.patch.object(C, "snapshot", side_effect=lambda *x: (events.append("programme"), original_snapshot(*x))[1]):
            old = os.umask(0o077)
            try:
                prepared = W.freeze(programme, source, self.root / "prepared")
            finally:
                os.umask(old)
            self.assertEqual(events, ["source", "programme"])
            self.assertEqual((self.root / "prepared/program.py").stat().st_mode & 0o777, 0o444)
            self.assertEqual((self.root / "prepared/PROGRAMME.json").stat().st_mode & 0o777, 0o444)
            self.assertEqual(Path(prepared["path"]).stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                W.freeze(programme, source, self.root / "prepared")

    def test_metadata_snapshot_rejects_symlink_hardlink_oversize_and_wrong_hash(self):
        target = self.root / "ordinary"
        target.write_bytes(b"invented")
        for operation in (lambda: C.snapshot(target, 2), lambda: C.read(target, {"bytes": 8, "sha256": "0" * 64})):
            with self.assertRaises(ValueError):
                operation()
        linked = self.root / "symlink"
        linked.symlink_to(target)
        with self.assertRaises(ValueError):
            C.snapshot(linked, 20)
        os.link(target, self.root / "hardlink")
        with self.assertRaises(ValueError):
            C.snapshot(target, 20)

    def test_provider_selection_is_additive_authenticated_and_has_no_launch_side_effect(self):
        prefix = "_sleep_finite_transport"
        prior = {k: sys.modules[k] for k in tuple(sys.modules) if k == prefix or k.startswith(prefix + ".")}
        for key in prior:
            del sys.modules[key]
        try:
            with mock.patch("subprocess.Popen", side_effect=AssertionError("no native command")):
                provider = C.load_provider()
            self.assertIn("provider-public-mode-v2", provider.__file__)
            self.assertEqual(C.bindings()["provider_manifest"]["sha256"], "335f696f47529a115479f543c62cbcab12d12c02f8a62606b8dc133ae92333c4")
            with self.assertRaises(ValueError):
                C.load_provider()
        finally:
            for key in tuple(sys.modules):
                if key == prefix or key.startswith(prefix + "."):
                    del sys.modules[key]
            sys.modules.update(prior)

    def test_grade_admission_checks_both_producer_proofs_and_original_refs_without_private_read(self):
        request = {"schema": "sleep007_finite_grade_v1", "source_freeze": {}, "viewer_proof": {}, "programme_commit": {},
                   "viewer": {}, "parts": {}, "references": {}, "private_locations": {"path": "MUST_NOT_OPEN"}}
        assets = json.loads(C.read(*C.original("assets")))
        request["references"] = {name: {"path": str(self.root / (name + ".npz")), **C.plain(row)}
                                  for name, row in assets["comparators"].items()}
        events = []
        with mock.patch.object(P, "admit_viewer", side_effect=lambda *x: events.append("viewer")), \
             mock.patch.object(P, "admit_programme", side_effect=lambda *x: events.append("programme")), \
             mock.patch.object(C, "descriptor_read", side_effect=AssertionError("no private location read")):
            P.admit_grade(request)
            self.assertEqual(events, ["viewer", "programme"])
            request["references"]["RF"]["sha256"] = "0" * 64
            with self.assertRaises(ValueError):
                P.admit_grade(request)


if __name__ == "__main__":
    unittest.main()
