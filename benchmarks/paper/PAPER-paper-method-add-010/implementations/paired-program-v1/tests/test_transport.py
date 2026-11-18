"""Generated metadata/control tests only; no Docker, data, fit or isolation run."""
import copy
import importlib.util
import os
from pathlib import Path
import shutil
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("meg_transport_controls", ROOT / "transport.py")
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)


def _generated_profile():
    return {"setup_seconds": 15, "producer_seconds": 30, "capture_seconds": 10, "cleanup_seconds": 15,
            "memory_bytes": 268435456, "cpu_nanos": 1000000000, "pids": 64, "scratch_bytes": 4096,
            "max_files": 2, "max_directories": 1, "max_file_bytes": 65536, "max_output_bytes": 131072,
            "manifest_bytes": 4096, "max_cli_calls": 100, "max_cli_bytes": 1048576,
            "inventory_bytes": 4096, "source_read_bytes": 1048576, "host_write_bytes": 1048576}


def _generated_mounts(role="A"):
    # Deliberately fictional metadata; no scientific file or native path is read.
    value = {}
    for target, purpose, kind in [("/input/WINDOWS.npy", "input", "file"),
                                  ("/input/CONTEXT.json", "input", "file"),
                                  ("/program", "program", "directory"),
                                  ("/paper", "paper", "directory"),
                                  ("/contract", "contract", "directory")]:
        name = Path(target).name if kind == "file" else "fixture.txt"
        value[target] = {"path": "/generated" + target, "kind": kind, "purpose": purpose,
                         "files": {name: t.pin(b"fictional")}}
    files = {"candidate_wrapper.py": t.WRAPPER_PIN, "submission.py": t.pin(b"generated candidate")}
    manifest = {"schema": "meg-frozen-program/v1", "files": copy.deepcopy(files)}
    files["PROGRAM.json"] = t.pin(t.canonical(manifest))
    value["/program"]["files"] = files
    if role == "B":
        value["/author"] = {"path": "/generated/author", "kind": "directory",
                            "purpose": "historical_author_source", "files": {"source.py": t.pin(b"fictional source")}}
    return value


def _generated_request(role="A", fold=0):
    mounts = _generated_mounts(role)
    return t.make_request("generated", role, fold, "sha256:" + "a" * 64,
                          mounts["/program"]["files"]["PROGRAM.json"], t.pin(b"generated exposure"),
                          _generated_profile(), 100.0, 200.0)


def _generated_receipt(request, mounts):
    p = t._vendor()
    identity = p.bounds.mount_identity(mounts)
    files = {"OUTPUTS.json": t.pin(b"generated envelope"), "RESULT.json": t.pin(b"{}")}
    cli = {"phase": "image", "returncode": 0, "error_type": None, "observed_retained_bytes": 40,
           "seconds": 0.01, "client_reaped": True, "cleanup_complete": True,
           "cleanup_before_original_cutoff": True, "owned_group_absence_observed": True,
           "leader_exited_with_group_alive": False, "group_probe_or_cleanup_error": None}
    return {"schema": "osl_owned_phase_receipt_v1", "phase_id": request["phase_id"],
            "request_sha256": t.pin(p.engine.encoded(request))["sha256"], "ownership_pin": t.pin(b"generated ownership"),
            "action": "held_attempt", "role": request["role"], "image": request["image"],
            "source": copy.deepcopy(request["source"]), "exposure": copy.deepcopy(request["exposure"]),
            "status": "captured", "producer_closed_before_capture": True, "all_native_resources_closed": True,
            "cli_reaped": True, "oom": False, "deadline_exceeded": False, "error": None,
            "exit_observation_error": None,
            "natural_exit": {"Status": "exited", "Running": False, "Dead": False, "Pid": 0, "ExitCode": 0, "OOMKilled": False},
            "retired_resources": [{"kind": "volume" if suffix == "volume" else "container",
                "name": "osl-" + "b" * 24 + "-" + suffix, "closed": True,
                "absence_observed": True, "creation_outcome_unknown": False}
                for suffix in ("producer", "holder", "volume")],
            "enforced_resource_limits": copy.deepcopy(request["resources"]),
            "input_before": copy.deepcopy(identity), "input_after": copy.deepcopy(identity),
            "timing": {"origin": 100.0, "original_deadline": 250.0, "phase_deadline": 180.0,
                       "started": 105.0, "finished": 150.0}, "command_metadata": [cli],
            "output_inventory": {"complete": True, "files": files, "total_bytes": sum(p["bytes"] for p in files.values())},
            "quarantine_root": "/generated/quarantine/" + request["phase_id"]}


class TransportControls(unittest.TestCase):
    def test_exact_vendor_bytes_and_class_are_selected(self):
        bodies = t._authenticated_vendor_sources(ROOT / "vendor_transport")
        self.assertEqual(len(bodies), 7)
        p = t._vendor()
        self.assertIs(p.Provider, p.provider.Provider)
        self.assertEqual(p.provider.__file__, str(ROOT / "vendor_transport/provider.py"))

    def test_vendor_tamper_or_extra_member_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve() / "_generated_vendor"
            shutil.copytree(ROOT / "vendor_transport", root)
            extra = root / "extra.py"
            extra.write_bytes(b"# generated\n")
            with self.assertRaises(ValueError):
                t._authenticated_vendor_sources(root)
            extra.unlink()
            (root / "bounds.py").write_bytes(b"# generated corruption\n")
            with self.assertRaises(ValueError):
                t._authenticated_vendor_sources(root)

    def test_both_role_exposures_bind_exact_public_inputs(self):
        for role in ("A", "B"):
            mounts = _generated_mounts(role)
            programme = mounts["/program"]["files"]["PROGRAM.json"]
            exposure = t.make_exposure(role, "sha256:" + "a" * 64, programme, mounts,
                                       "c" * 64, t.pin(b"generated reviewed boundary"), role_boundary_verified=True)
            request = _generated_request(role)
            request["exposure"] = t.pin(t.canonical(exposure))
            self.assertIs(t._vendor().contract.validate_exposure(exposure, request, mounts), exposure)
            self.assertEqual(set(exposure["mounts"]), set(mounts))

    def test_paper_only_rejects_author_or_operator_mounts(self):
        mounts = _generated_mounts("B")
        with self.assertRaises(ValueError):
            t.validate_mounts("A", mounts)
        mounts = _generated_mounts()
        mounts["/operator"] = mounts["/paper"]
        with self.assertRaises(ValueError):
            t.validate_mounts("A", mounts)
        mounts = _generated_mounts("B")
        mounts["/author"]["purpose"] = "operator_reference"
        with self.assertRaises(ValueError):
            t.validate_mounts("B", mounts)

    def test_manifest_and_wrapper_replacement_refused(self):
        for filename in ("candidate_wrapper.py", "submission.py", "PROGRAM.json"):
            mounts = _generated_mounts()
            mounts["/program"]["files"][filename] = t.pin(b"replacement")
            with self.assertRaises(ValueError):
                t.validate_mounts("A", mounts)
        mounts = _generated_mounts()
        with self.assertRaises(ValueError):
            t.validate_mounts("A", mounts, t.pin(b"wrong programme"))

    def test_no_unreviewed_boundary_boolean(self):
        mounts = _generated_mounts()
        for value in (False, 1, "true", None):
            with self.assertRaises(ValueError):
                t.make_exposure("A", "sha256:" + "a" * 64, mounts["/program"]["files"]["PROGRAM.json"],
                                mounts, "c" * 64, t.pin(b"boundary"), role_boundary_verified=value)

    def test_twenty_unique_phases_preserve_frozen_clock_and_profile(self):
        names = set()
        for role in ("A", "B"):
            for fold in range(10):
                request = _generated_request(role, fold)
                t._vendor().contract.validate_request(request, _generated_mounts(role), 250.0)
                names.add(request["phase_id"])
                self.assertEqual(request["clock"], {"origin": 100.0, "phase_deadline": 200.0})
                self.assertEqual(request["resources"], _generated_profile())
        self.assertEqual(len(names), 20)
        for fold in (True, -1, 10):
            with self.assertRaises(ValueError):
                _generated_request("A", fold)

    def test_missing_or_boolean_resource_limit_refused(self):
        for resources in ({}, {**_generated_profile(), "pids": True}):
            with self.assertRaises(ValueError):
                t.make_request("generated", "A", 0, "sha256:" + "a" * 64, t.pin(b"p"), t.pin(b"e"),
                               resources, 100.0, 200.0)

    def test_valid_generated_closed_receipt_accepts_only_pinned_result(self):
        request, mounts = _generated_request(), _generated_mounts()
        receipt = _generated_receipt(request, mounts)
        self.assertEqual(t.validate_closed_receipt(receipt, request, mounts, 250.0), t.pin(b"{}"))

    def test_selected_engine_retire_records_join_receipt_validator(self):
        # Exercise the actual selected retirement implementation with an
        # explicitly generated CLI responder, not a real daemon or namespace.
        engine = t._vendor().engine
        records = []
        for suffix in ("producer", "holder", "volume"):
            kind = "volume" if suffix == "volume" else "container"
            name = "osl-" + "b" * 24 + "-" + suffix
            owner = "osl-" + "b" * 24 + "/" + suffix
            ident = name if kind == "volume" else "d" * 64
            item = {"kind": kind, "name": name, "owner": owner, "attempted": True, "acknowledged": True}
            if kind == "container":
                item["id"] = ident
            state = {"removed": False}
            def _generated_cli(args, end, phase, cap):
                if args[1] == "ls":
                    return b"" if state["removed"] else (ident + "\n").encode()
                if args[1] == "inspect":
                    value = {"Name": name if kind == "volume" else "/" + name,
                             "Labels": {engine.LABEL: owner}, "Config": {"Labels": {engine.LABEL: owner}},
                             "Id": ident, "State": {"Running": False}}
                    return engine.encoded([value])
                self.assertEqual(args[1], "rm")
                state["removed"] = True
                return b""
            records.append(engine.retire(_generated_cli, item, time.monotonic() + 5))
        self.assertTrue(all(row["removed"] for row in records))
        request, mounts = _generated_request(), _generated_mounts()
        receipt = _generated_receipt(request, mounts)
        receipt["retired_resources"] = records
        self.assertEqual(t.validate_closed_receipt(receipt, request, mounts, 250.0), t.pin(b"{}"))

    def test_changed_identity_resource_or_clock_refused(self):
        request, mounts = _generated_request(), _generated_mounts()
        cases = [("phase_id", "other"), ("role", "B"), ("source", t.pin(b"other")),
                 ("enforced_resource_limits", {**request["resources"], "pids": 128})]
        for key, value in cases:
            receipt = _generated_receipt(request, mounts)
            receipt[key] = value
            with self.assertRaises(ValueError):
                t.validate_closed_receipt(receipt, request, mounts, 250.0)
        receipt = _generated_receipt(request, mounts)
        receipt["timing"]["original_deadline"] = 300.0
        with self.assertRaises(ValueError):
            t.validate_closed_receipt(receipt, request, mounts, 250.0)

    def test_missing_unknown_and_boolean_exit_fields_refused(self):
        request, mounts = _generated_request(), _generated_mounts()
        for key in ("error", "ownership_pin", "exit_observation_error", "all_native_resources_closed"):
            receipt = _generated_receipt(request, mounts)
            receipt.pop(key)
            with self.assertRaises(ValueError):
                t.validate_closed_receipt(receipt, request, mounts, 250.0)
        for change in ("natural_exit", "retired_resources", "command_metadata"):
            receipt = _generated_receipt(request, mounts)
            if change == "natural_exit":
                receipt[change]["Pid"] = False
            elif change == "retired_resources":
                receipt[change][0]["creation_outcome_unknown"] = True
            else:
                receipt[change][0]["owned_group_absence_observed"] = False
            with self.assertRaises(ValueError):
                t.validate_closed_receipt(receipt, request, mounts, 250.0)

    def test_wrong_mount_or_additional_export_refused(self):
        request, mounts = _generated_request(), _generated_mounts()
        receipt = _generated_receipt(request, mounts)
        receipt["input_after"]["/paper"]["files"]["fixture.txt"] = t.pin(b"changed")
        with self.assertRaises(ValueError):
            t.validate_closed_receipt(receipt, request, mounts, 250.0)
        receipt = _generated_receipt(request, mounts)
        receipt["output_inventory"]["files"]["EXTRA.json"] = t.pin(b"x")
        with self.assertRaises(ValueError):
            t.validate_closed_receipt(receipt, request, mounts, 250.0)

    def test_private_nofollow_file_and_exact_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            root.chmod(0o700)
            file = root / "RESULT.json"
            file.write_bytes(b"{}")
            file.chmod(0o600)
            self.assertEqual(t._read_exact(t._private_path(root, file), t.pin(b"{}"), 16), b"{}")
            with self.assertRaises(ValueError):
                t._read_exact(file, t.pin(b"[]"), 16)
            file.chmod(0o644)
            with self.assertRaises(ValueError):
                t._private_path(root, file)
            file.chmod(0o600)
            link = root / "link.json"
            link.symlink_to(file)
            with self.assertRaises(ValueError):
                t._private_path(root, link)
            os.link(file, root / "hard.json")
            with self.assertRaises(ValueError):
                t._private_path(root, file)

    def test_full_campaign_gate_and_no_executor_injection(self):
        # Explicitly generated state-only seam: no Provider or execution claim.
        owner = object.__new__(t.OwnedTransport)
        owner.deadline = time.monotonic() + 10
        owner._accepted = {(role, fold): {"generated": True} for role in ("A", "B") for fold in range(10)}
        self.assertEqual(len(owner.complete_for_grading()), 20)
        owner._accepted.pop(("B", 9))
        with self.assertRaises(ValueError):
            owner.complete_for_grading()
        with self.assertRaises(TypeError):
            t.OwnedTransport(provider=lambda: True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
