"""Focused generated controls for the new hosted boundary implementation.

Native operations are blocked by the driver. Tests patch only concrete low-level
observation references; no production test mode is introduced.
"""
import ast
import builtins
import copy
from contextlib import ExitStack, contextmanager
import errno
import hashlib
import json
import os
from pathlib import Path
import socket
import struct
from types import SimpleNamespace
import unittest
from unittest import mock

import boundary_fixtures as fixtures
import boundary_audit as audit
import engineering_probe as probe
import boundary_entry as entry
import generic_contract as contract
import transport as existing_transport

WRITE_LIMIT = 786432
CONTROL_ACCOUNTING = {"cumulative_generated_write_bytes": 0, "observed_fixture_builds": 0}
_REAL_WRITE = os.write
_REAL_PWRITE = os.pwrite


def charged_write(fd, body):
    CONTROL_ACCOUNTING["cumulative_generated_write_bytes"] += len(body)
    if CONTROL_ACCOUNTING["cumulative_generated_write_bytes"] > WRITE_LIMIT:
        raise ValueError("cumulative focused-control write allowance exhausted")
    return _REAL_WRITE(fd, body)


def charged_pwrite(fd, body, offset):
    CONTROL_ACCOUNTING["cumulative_generated_write_bytes"] += len(body)
    if CONTROL_ACCOUNTING["cumulative_generated_write_bytes"] > WRITE_LIMIT:
        raise ValueError("cumulative focused-control write allowance exhausted")
    return _REAL_PWRITE(fd, body, offset)


def write_body(path, body):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        if os.write(fd, body) != len(body):
            raise ValueError("complete focused-control write required")
    finally:
        os.close(fd)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def control_accounting():
    return dict(CONTROL_ACCOUNTING)


class FakeSocket:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.timeouts = []
        self.endpoints = []
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def settimeout(self, value):
        self.timeouts.append(value)
    def connect_ex(self, endpoint):
        self.endpoints.append(endpoint)
        if self.error is not None:
            raise self.error
        return self.result


class BoundaryQualificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.output = Path(os.environ["MEG_BOUNDARY_CONTROL_OUTPUT"])
        cls.implementation = Path(os.environ["MEG_BOUNDARY_CONTROL_IMPLEMENTATION"])
        cls.paired_source = Path(os.environ["MEG_BOUNDARY_CONTROL_PAIRED_SOURCE"])
        cls.scratch = cls.output / "scratch"
        cls.scratch.mkdir(mode=0o700)
        cls._write_patch = mock.patch.object(os, "write", side_effect=charged_write)
        cls._pwrite_patch = mock.patch.object(os, "pwrite", side_effect=charged_pwrite)
        cls._write_patch.start()
        cls._pwrite_patch.start()
        cls.addClassCleanup(cls._write_patch.stop)
        cls.addClassCleanup(cls._pwrite_patch.stop)
        cls.freeze_observations = []
        real_exec = builtins.exec
        def observe_exec(code, namespace):
            real_exec(code, namespace)
            build = namespace["build_panel"]
            def observe_panel(*args, **kwargs):
                frozen = {}
                for kind in ("constant", "probe"):
                    root = cls.output / "fixture" / "programmes" / kind
                    program = json.loads((root / "PROGRAM.json").read_bytes())
                    observed = {}
                    for name in ("submission.py", "candidate_wrapper.py"):
                        raw = (root / name).read_bytes()
                        observed[name] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
                    if program != {"schema": "meg-frozen-program/v1", "files": observed}:
                        raise AssertionError("both full capsules must freeze before first labelled panel")
                    frozen[kind] = observed
                cls.freeze_observations.append(frozen)
                return build(*args, **kwargs)
            namespace["build_panel"] = observe_panel
        with mock.patch.object(fixtures, "exec", side_effect=observe_exec, create=True):
            cls.fixture = fixtures.build_fixture(cls.paired_source, cls.output / "fixture",
                cls.implementation / "engineering_probe.py", "01" * 16)
        CONTROL_ACCOUNTING["observed_fixture_builds"] += 1
        cls.contexts = {fold: json.loads(Path(item["path"]).read_bytes())
                        for fold, item in cls.fixture["contexts"].items()}

    def scratch_file(self, name, body=b"generated-test-only\n"):
        path = self.scratch / name
        write_body(path, body)
        return path

    def valid_probe_report(self):
        return {"schema": probe.SCHEMA, "phase_id": "generated-A-fold-00", "role": "A", "fold": 0,
            "context_sha256": self.contexts["0"]["context_sha256"], "scientific_evaluation": False,
            "qualified": True, "checks": {
                "private_sentinel": {"qualified": True, "operation": "read_open", "opened": False, "errno": errno.ENOENT},
                "readonly_features": {"qualified": True, "operation": "write_open_then_same_byte",
                    "opened_writable": False, "write_bytes": 0, "errno": errno.EROFS},
                "external_network": {"qualified": True, "operation": "connect_ex", "endpoint": ["192.0.2.1", 9],
                    "errno": errno.ENETUNREACH, "timed_out": False},
                "fresh_work_marker": {"qualified": True, "absent_before": True, "created": True,
                    "readback_matches": True, "errno": None}}}

    def validate_report(self, report):
        return probe.validate_probe_result(report, phase_id="generated-A-fold-00", role="A", fold=0,
                                           context_sha256=self.contexts["0"]["context_sha256"])

    def test_fixture_freezes_both_programmes_before_labels(self):
        self.assertEqual(len(self.freeze_observations), 1)
        self.assertEqual(set(self.freeze_observations[0]), {"constant", "probe"})
        self.assertEqual(self.fixture["construction_order"], ["constant_programme_frozen", "probe_programme_frozen",
            "generated_labelled_panel_built", "fold_0_public_context_built", "fold_4_public_context_built"])
        self.assertEqual(self.freeze_observations[0]["constant"]["submission.py"], fixtures.DONORS["generic_fixed_control.py"])
        for campaign in self.fixture["campaigns"].values():
            self.assertEqual(campaign["frozen_programs"]["A"], campaign["frozen_programs"]["B"])
        self.assertNotEqual(self.fixture["campaigns"]["constant"]["program_pin"], self.fixture["campaigns"]["probe"]["program_pin"])

    def test_fixture_generated_provenance_and_geometry_are_honest(self):
        manifest = self.fixture
        source_body = Path(manifest["private"]["GENERATED_SOURCE.json"]["path"]).read_bytes()
        source = json.loads(source_body)
        self.assertEqual(manifest["source_binding"], {"bytes": len(source_body), "sha256": hashlib.sha256(source_body).hexdigest()})
        self.assertNotEqual(manifest["source_binding"]["sha256"], "80b16614e7654a4b0efaafced5abb251ab17e625f264c66c87c0c8658737fa2d")
        self.assertTrue(source["generated_only"])
        self.assertEqual(len(source["records"]), 188)
        self.assertEqual(len(source["participant_folds"]), 94)
        self.assertEqual([sum(value == fold for value in source["participant_folds"].values()) for fold in range(10)], [10]*4+[9]*6)
        self.assertEqual([len(self.contexts[f]["queries"]) for f in ("0", "4")], [20, 18])
        self.assertFalse(manifest["scientific_evaluation"])
        self.assertFalse(manifest["production_authentic_admission"])
        panel = json.loads(Path(manifest["private"]["PANEL.json"]["path"]).read_bytes())
        bank_path = manifest["campaigns"]["constant"]["mounts"]["0"]["A"]["/input/FEATURES.npy"]["path"]
        bank = Path(bank_path).read_bytes()
        self.assertEqual(bank[:8], b"\x93NUMPY\x01\x00")
        length = struct.unpack("<H", bank[8:10])[0]
        header = ast.literal_eval(bank[10:10+length].decode().strip())
        self.assertEqual(header, {"descr": "<f8", "fortran_order": False, "shape": (188,)})
        values = struct.unpack("<188d", bank[10+length:])
        self.assertEqual([hashlib.sha256(struct.pack("<d", value)).hexdigest() for value in values],
                         [row["scalar_sha256"] for row in panel["public_rows"]])
        def strings(value):
            if isinstance(value, dict):
                return set(value).union(*(strings(item) for item in value.values()))
            if isinstance(value, list):
                return set().union(*(strings(item) for item in value))
            return {value} if isinstance(value, str) else set()
        public_strings = strings(self.contexts)
        for record in panel["private_records"]:
            self.assertNotIn(record["row_key"], public_strings)
            self.assertNotIn(record["participant"], public_strings)
        for context in self.contexts.values():
            self.assertFalse(set(context["queries"]) & {row["id"] for row in context["training"]})

    def test_fixture_role_mounts_and_private_positive_control(self):
        for campaign in self.fixture["campaigns"].values():
            for fold in ("0", "4"):
                a, b = campaign["mounts"][fold]["A"], campaign["mounts"][fold]["B"]
                self.assertEqual(set(b) - set(a), {"/author"})
                self.assertEqual({key: b[key] for key in a}, a)
                self.assertEqual(set(a), {"/input/FEATURES.npy", "/input/CONTEXT.json", "/program", "/paper", "/contract"})
                for descriptor in b.values():
                    self.assertNotIn("/private/", descriptor["path"])
        private = self.fixture["private"]
        sentinel_body = Path(private["sentinel"]["path"]).read_bytes()
        self.assertEqual(private["host_positive_control"]["observed_pin"],
                         {"bytes": len(sentinel_body), "sha256": hashlib.sha256(sentinel_body).hexdigest()})
        self.assertTrue(private["host_positive_control"]["read_succeeded"])
        self.assertFalse(private["host_positive_control"]["value_published"])
        paper_path = self.fixture["campaigns"]["constant"]["mounts"]["0"]["A"]["/paper"]["path"]
        paper = (Path(paper_path) / "PAPER.bin").read_bytes()
        self.assertNotIn(sentinel_body, paper)
        self.assertTrue(json.loads(paper)["generated_only"])

    def test_fixture_existing_target_refuses_before_writes(self):
        before = CONTROL_ACCOUNTING["cumulative_generated_write_bytes"]
        with self.assertRaisesRegex(ValueError, "fresh target"):
            fixtures.build_fixture(self.paired_source, self.output / "fixture", self.implementation / "engineering_probe.py", "01" * 16)
        self.assertEqual(before, CONTROL_ACCOUNTING["cumulative_generated_write_bytes"])

    def test_probe_private_denial_requires_failed_open(self):
        for code in (errno.ENOENT, errno.EACCES, errno.EPERM):
            with self.subTest(errno=code), mock.patch.object(probe.os, "open", side_effect=OSError(code, "generated denial")):
                result = probe.check_private("/generated/private-sentinel")
                self.assertTrue(result["qualified"])
                self.assertFalse(result["opened"])
        readable = self.scratch_file("readable-private-sentinel")
        with mock.patch.object(probe.os, "read", side_effect=AssertionError("sentinel content must not be read")) as read:
            result = probe.check_private(readable)
            read.assert_not_called()
        self.assertFalse(result["qualified"])
        self.assertTrue(result["opened"])
        with mock.patch.object(probe.os, "open", side_effect=OSError(errno.EIO, "not a denial")):
            self.assertFalse(probe.check_private("/generated/private-sentinel")["qualified"])

    def test_probe_readonly_refuses_any_admitted_write(self):
        with mock.patch.object(probe.os, "open", side_effect=OSError(errno.EROFS, "generated readonly")):
            self.assertTrue(probe.check_readonly("/input/FEATURES.npy")["qualified"])
        writable = self.scratch_file("writable-feature", b"generated-feature")
        before = writable.read_bytes()
        result = probe.check_readonly(writable)
        self.assertFalse(result["qualified"])
        self.assertTrue(result["opened_writable"])
        self.assertEqual(result["write_bytes"], 1)
        self.assertEqual(writable.read_bytes(), before)

    def test_probe_network_requires_explicit_denial_and_bounded_endpoint(self):
        for code in (errno.ENETUNREACH, errno.EACCES, errno.EPERM, 0, errno.ECONNREFUSED, errno.EHOSTUNREACH, errno.ETIMEDOUT):
            fake = FakeSocket(result=code)
            with self.subTest(errno=code), mock.patch.object(probe.socket, "socket", return_value=fake), \
                    mock.patch.object(probe.time, "monotonic", return_value=10.0):
                result = probe.check_network(11.0)
                self.assertIs(result["qualified"], code in (errno.ENETUNREACH, errno.EACCES, errno.EPERM))
                self.assertEqual(fake.endpoints, [("192.0.2.1", 9)])
                self.assertEqual(fake.timeouts, [0.25])
        fake = FakeSocket(error=TimeoutError("generated timeout"))
        with mock.patch.object(probe.socket, "socket", return_value=fake), mock.patch.object(probe.time, "monotonic", return_value=10.0):
            self.assertFalse(probe.check_network(11.0)["qualified"])

    def test_probe_network_expiry_refuses_before_socket(self):
        with mock.patch.object(probe.time, "monotonic", return_value=10.0), \
                mock.patch.object(probe.socket, "socket") as create:
            with self.assertRaisesRegex(ValueError, "remaining original probe deadline"):
                probe.check_network(10.0)
            create.assert_not_called()

    def test_probe_marker_requires_initial_absence_and_real_readback(self):
        path = self.scratch / "phase-marker"
        first = probe.check_marker(path, "generated-A-fold-00")
        self.assertEqual(first, {"qualified": True, "absent_before": True, "created": True, "readback_matches": True, "errno": None})
        self.assertEqual(json.loads(path.read_bytes())["phase_id"], "generated-A-fold-00")
        second = probe.check_marker(path, "generated-A-fold-04")
        self.assertFalse(second["qualified"])
        self.assertFalse(second["absent_before"])
        self.assertEqual(json.loads(path.read_bytes())["phase_id"], "generated-A-fold-00")
        with mock.patch.object(probe, "read_bounded", return_value=b"wrong phase contents"):
            mismatch = probe.check_marker(self.scratch / "readback-mismatch-marker", "generated-B-fold-04")
        self.assertTrue(mismatch["created"])
        self.assertFalse(mismatch["readback_matches"])
        self.assertFalse(mismatch["qualified"])

    def test_probe_validator_recomputes_flags_and_current_identity(self):
        valid = self.valid_probe_report()
        self.assertTrue(self.validate_report(valid)["qualified"])
        wrong = copy.deepcopy(valid)
        wrong["checks"]["private_sentinel"]["opened"] = True
        wrong["checks"]["private_sentinel"]["errno"] = None
        with self.assertRaisesRegex(ValueError, "flags agree"):
            self.validate_report(wrong)
        wrong["checks"]["private_sentinel"]["qualified"] = False
        wrong["qualified"] = False
        self.assertFalse(self.validate_report(wrong)["qualified"])
        for field, value in (("phase_id", "other-A-fold-00"), ("role", "B"), ("fold", True), ("context_sha256", "0"*64)):
            mismatch = copy.deepcopy(valid); mismatch[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.validate_report(mismatch)
        contradictory = copy.deepcopy(valid); contradictory["qualified"] = False
        with self.assertRaisesRegex(ValueError, "aggregate flag"):
            self.validate_report(contradictory)

    def test_probe_validator_rejects_ambiguous_network_claim(self):
        for code in (0, errno.EHOSTUNREACH, errno.ECONNREFUSED, errno.ETIMEDOUT):
            invalid = self.valid_probe_report()
            invalid["checks"]["external_network"]["errno"] = code
            with self.subTest(errno=code), self.assertRaisesRegex(ValueError, "flags agree"):
                self.validate_report(invalid)
        invalid = self.valid_probe_report()
        invalid["checks"]["external_network"]["errno"] = True
        with self.assertRaisesRegex(ValueError, "bounded observed errno"):
            self.validate_report(invalid)

    def test_probe_collection_joins_request_and_enforces_original_deadline(self):
        root = self.scratch / "collect-input"
        root.mkdir(mode=0o700)
        write_body(root / "CONTEXT.json", encoded({"fold": 0, "context_sha256": self.contexts["0"]["context_sha256"]}))
        phase = "generated-A-fold-00"
        request_path = self.scratch_file("collect-request.json", encoded({"schema": "osl_owned_phase_request_v1",
            "phase_id": phase, "role": "A", "clock": {"phase_deadline": 12.0}}))
        paper = self.fixture["campaigns"]["probe"]["mounts"]["0"]["A"]["/paper"]
        paper_path = Path(paper["path"]) / "PAPER.bin"
        observations = self.valid_probe_report()["checks"]
        with mock.patch.object(probe, "check_private", return_value=observations["private_sentinel"]) as private, \
             mock.patch.object(probe, "check_readonly", return_value=observations["readonly_features"]) as readonly, \
             mock.patch.object(probe, "check_network", return_value=observations["external_network"]) as network, \
             mock.patch.object(probe, "check_marker", return_value=observations["fresh_work_marker"]) as marker, \
             mock.patch.object(probe.time, "monotonic", return_value=10.0):
            result = probe.collect(root, paper_path, request_path)
            self.assertTrue(self.validate_report(result)["qualified"])
            private.assert_called_once_with(self.fixture["private"]["sentinel"]["path"])
            readonly.assert_called_once_with(root / "FEATURES.npy")
            network.assert_called_once_with(12.0)
            marker.assert_called_once_with(probe.MARKER, phase)
        with mock.patch.object(probe.time, "monotonic", return_value=13.0), \
                mock.patch.object(probe, "check_private") as private:
            with self.assertRaisesRegex(ValueError, "live original request deadline"):
                probe.collect(root, paper_path, request_path)
            private.assert_not_called()

    def audit_expected(self):
        return {"schema": "meg-boundary-audit-expected/v1", "attempt_id": "generated-controls",
            "source_manifest": {"bytes": 1, "sha256": "a"*64},
            "registry_metadata": {"path": "/generated/IMAGE_METADATA.json", "pin": dict(audit.REGISTRY_PIN)},
            "docker_binary": "/generated/docker", "docker_socket": "/generated/docker.sock",
            "image": audit.IMAGE, "immutable_pull_reference": audit.PULL_REFERENCE,
            "fixture_sha256": audit.pin(audit.encoded(self.fixture["audit_view"]))["sha256"],
            "fixture_not_before_unix": 1.0, "policy_sha256": audit.AUDIT_POLICY_PIN["sha256"]}

    def audit_observations(self):
        expected = self.audit_expected()
        boot = "01234567-89ab-cdef-0123-456789abcdef"
        records, children = [], []
        for index, phase in enumerate(audit.CLI_CAPS):
            records.append({"phase": phase, "returncode": 0, "error_type": None,
                "group_probe_or_cleanup_error": None, "leader_exited_with_group_alive": False,
                "client_reaped": True, "cleanup_complete": True, "cleanup_before_original_cutoff": True,
                "owned_group_absence_observed": True, "observed_retained_bytes": 128, "seconds": 0.25})
            pid = 5001 + index
            children.append({"index": index, "phase": phase, "docker_exec_still_gated": True,
                "independent_group": True, "pid": pid, "pgid": pid,
                "process_identity": {"schema": "osl_linux_process_identity_v1", "pid": pid,
                    "pgid": pid, "session_id": pid, "uid": 1000, "boot_id": boot,
                    "start_time_ticks": 10001 + index}})
        return {"schema": "meg-boundary-actual-observations/v1",
            "host": {"system": "Linux", "sys_platform": "linux", "machine": "x86_64", "uid": 1000,
                "pid": 4321, "boot_id": boot, "pidfd_apis_available": True,
                "os_release": {"ID": "ubuntu", "VERSION_ID": "24.04"}},
            "docker": {
                "version": {role: {"Os": "linux", "Arch": "amd64", "Version": "generated-version"}
                            for role in ("Client", "Server")},
                "info": {"OSType": "linux", "Architecture": "x86_64", "CgroupVersion": "2", "ID": "generated-daemon"},
                "image": {"Id": audit.IMAGE, "Os": "linux", "Architecture": "amd64",
                    "RepoDigests": ["docker.io/library/python@" + audit.MANIFEST],
                    "Config": {"Volumes": {}, "Healthcheck": None,
                               "Env": ["PATH=/usr/local/bin:/usr/bin:/bin", "LANG=C.UTF-8", "PYTHON_VERSION=3.11.0"]},
                    "RootFS": {"Type": "layers", "Layers": ["sha256:" + value*64 for value in "abcd"]}}},
            "cli_records": records, "cli_children": children, "started": 10.0, "finished": 11.0, "deadline": 12.0,
            "docker_binary": {"path": expected["docker_binary"], "pin": {"bytes": 15, "sha256": "f"*64}},
            "docker_socket": {"path": expected["docker_socket"]}, "binary_unchanged": True, "socket_unchanged": True}

    def test_audit_synthetic_observations_never_issue_native_approval(self):
        report = audit.evaluate_observations(self.audit_expected(), self.audit_observations())
        self.assertTrue(report["observations_valid"])
        self.assertEqual(report["evidence_kind"], "mock_source_control")
        self.assertFalse(report["native_audit"])
        self.assertFalse(report["role_boundary_verified"])
        campaign = self.fixture["campaigns"]["constant"]
        for forgery in (report, {"native_audit": True, "role_boundary_verified": True}, {}):
            with self.subTest(forgery=forgery), self.assertRaisesRegex(ValueError, "actual native audit handle"):
                audit.approve_exposure(forgery, "A", campaign["mounts"]["0"]["A"], campaign["program_pin"])
        with self.assertRaisesRegex(ValueError, "actual observer-issued"):
            audit.AuditHandle(object(), {}, [], 12.0, None, None, self.audit_expected())

    def test_audit_missing_mismatched_or_unknown_observations_are_refused(self):
        mutations = [
            ("host", ("host", "system"), "Darwin"),
            ("image", ("docker", "image", "Id"), "sha256:" + "0"*64),
            ("manifest", ("docker", "image", "RepoDigests"), ["python@sha256:" + "0"*64]),
            ("environment", ("docker", "image", "Config", "Env"), ["PATH=/usr/bin", "PYTHON_VERSION=3.11.0", "AWS_SECRET_ACCESS_KEY=generated-only"]),
            ("implicit-volume", ("docker", "image", "Config", "Volumes"), {"/unexpected": {}}),
            ("health-process", ("docker", "image", "Config", "Healthcheck"), {"Test": ["CMD", "generated"]}),
            ("rootfs", ("docker", "image", "RootFS", "Layers"), ["sha256:" + "a"*64]),
            ("capture-overflow", ("cli_records", 0, "observed_retained_bytes"), 131073),
            ("capture-negative", ("cli_records", 0, "observed_retained_bytes"), -1),
            ("capture-boolean", ("cli_records", 0, "observed_retained_bytes"), True),
            ("duration-nonfinite", ("cli_records", 0, "seconds"), float("nan")),
            ("unknown-closure", ("cli_records", 2, "cleanup_complete"), None),
            ("missing-reap", ("cli_records", 0, "client_reaped"), False),
            ("late-cleanup", ("cli_records", 1, "cleanup_before_original_cutoff"), False),
            ("leader-left-group", ("cli_records", 2, "leader_exited_with_group_alive"), True),
            ("identity", ("cli_children", 1, "process_identity", "start_time_ticks"), 0),
            ("binary-custody", ("binary_unchanged",), False),
            ("deadline", ("finished",), 12.0),
            ("socket", ("docker_socket", "path"), "/generated/other.sock"),
        ]
        for name, keys, value in mutations:
            wrong = self.audit_observations()
            parent = wrong
            for key in keys[:-1]:
                parent = parent[key]
            parent[keys[-1]] = value
            with self.subTest(predicate=name), self.assertRaises(ValueError):
                audit.evaluate_observations(self.audit_expected(), wrong)
        missing = self.audit_observations(); del missing["cli_records"]
        with self.assertRaisesRegex(ValueError, "complete observation schema"):
            audit.evaluate_observations(self.audit_expected(), missing)

    def test_audit_bad_selected_policy_refuses_before_observation(self):
        expected = self.audit_expected(); expected["policy_sha256"] = "0"*64
        target = self.scratch / "refused-audit"
        with mock.patch.object(audit, "_observe_host") as host, mock.patch.object(audit, "_observe_docker") as docker:
            with self.assertRaisesRegex(ValueError, "independently selected policy"):
                audit.audit_environment(self.paired_source, target, expected, self.fixture["audit_view"],
                    100.0, 1048576, 524288, lambda *args: None)
            host.assert_not_called()
            docker.assert_not_called()
        self.assertFalse(target.exists())

    @contextmanager
    def mocked_entry_boundary(self, *, failed_probe=False, now=100.0):
        """Mock concrete native references only; these outputs never qualify a host."""
        fixture = self.fixture
        test = self
        state = {"instances": [], "calls": [], "fixture_calls": 0}
        binding = {"image": audit.IMAGE, "docker_binary": "/generated/docker",
            "docker_socket": "/generated/docker.sock", "operation_seconds": 900,
            "audit_read_bytes": 1048576, "audit_write_bytes": 524288,
            "transport_read_bytes": 1048576, "transport_write_bytes": 524288,
            "phase_resources": {"generated_source_control_only": True}}
        class FakeOwnedTransport:
            def __init__(self, **kwargs):
                self.options = kwargs
                self.attempted = set()
                self.control = kwargs["control_root"]
                self.control.mkdir(mode=0o700)
                kwargs["quarantine_root"].mkdir(mode=0o700)
                state["instances"].append(self)
            def execute_fold(self, role, fold, mounts, exposure_pin, resources, deadline, journal):
                key = (role, fold)
                if key in self.attempted:
                    raise ValueError("generated fake detected repeated role/fold in a transport instance")
                self.attempted.add(key)
                phase = self.options["campaign_id"] + f"-{role}-fold-{fold:02d}"
                state["calls"].append({"campaign": self.options["campaign_id"], "role": role,
                    "fold": fold, "deadline": deadline, "mounts": mounts})
                context = test.contexts[str(fold)]
                if "-constant-" in self.options["campaign_id"]:
                    response = {"schema": contract.RESPONSE_SCHEMA, "input_mode": contract.MODE,
                        "context_sha256": context["context_sha256"],
                        "probabilities": {query: 0.5 for query in context["queries"]}}
                else:
                    response = test.valid_probe_report()
                    response.update(phase_id=phase, role=role, fold=fold,
                        context_sha256=context["context_sha256"])
                    if failed_probe:
                        response["checks"]["external_network"].update(qualified=False, errno=0)
                        response["qualified"] = False
                phase_root = self.control / phase
                phase_root.mkdir(mode=0o700)
                resources = [{"kind": kind, "name": phase + "-" + suffix, "owner": "generated-control-owner"}
                    for kind, suffix in (("container", "container"), ("volume", "work"), ("volume", "output"))]
                ownership = encoded({"generated_source_control_only": True, "resources": resources})
                write_body(phase_root / "OWNERSHIP.json", ownership)
                raw = encoded(response)
                placeholder = {"bytes": 1, "sha256": "d" * 64}
                return {"phase_id": phase, "result_bytes": raw, "result_pin": entry.pin(raw),
                    "request_pin": placeholder, "receipt_pin": placeholder,
                    "receipt": {"ownership_pin": entry.pin(ownership)},
                    "final_transport_counters": {"generated_source_control_only": True},
                    "adapter_read_reserved_bytes": len(raw) + 1}
        engine = SimpleNamespace(encoded=entry.encoded,
            process_identity=lambda *args: {"schema": "generated-source-control-identity/v1"})
        transport = SimpleNamespace(OwnedTransport=FakeOwnedTransport, _vendor=lambda: SimpleNamespace(engine=engine),
            make_exposure=lambda role, image, programme, mounts, **approval:
                {"role": role, "image": image, "programme": programme, "mounts": mounts,
                 "generated_source_control_only": True})
        fake_audit = SimpleNamespace(
            approve_exposure=mock.Mock(return_value={}),
            owners_from_ownership=lambda document: document["resources"],
            audit_environment=mock.Mock(return_value={"audit_pin": {"bytes": 1, "sha256": "e"*64},
                "audit_path": "/generated/mock-audit-never-native.json",
                "docker_context": {"binary": "/generated/docker", "socket": "/generated/docker.sock",
                    "image": audit.IMAGE, "daemon_id": "generated-control-daemon"}}))
        def fixture_once(*args):
            state["fixture_calls"] += 1
            return fixture
        with ExitStack() as stack:
            for name, value in (("transport", transport), ("boundary_audit", fake_audit),
                ("boundary_fixtures", SimpleNamespace(build_fixture=fixture_once)),
                ("engineering_probe", probe), ("generic_contract", contract),
                ("_SOURCE_HANDLE", {"app_root": str(self.implementation), "mock_source_control_only": True})):
                stack.enter_context(mock.patch.object(entry, name, value))
            stack.enter_context(mock.patch.object(entry, "validate_binding", return_value=binding))
            stack.enter_context(mock.patch.object(entry, "_audit_expected", return_value={"mock_source_control_only": True}))
            stack.enter_context(mock.patch.object(entry.platform, "system", return_value="Linux"))
            stack.enter_context(mock.patch.object(entry.time, "monotonic", return_value=now))
            yield state, binding

    def test_entry_uses_two_fresh_namespaces_and_eight_ordered_phases(self):
        output = self.scratch / "mocked-entry-run"
        with self.mocked_entry_boundary() as (state, binding):
            entry.run_qualification(self.paired_source, output, binding)
        self.assertEqual(state["fixture_calls"], 1)
        self.assertEqual(len(state["instances"]), 2)
        self.assertIsNot(state["instances"][0], state["instances"][1])
        expected = [("A", 0), ("B", 0), ("A", 4), ("B", 4)]
        self.assertEqual([(row["role"], row["fold"]) for row in state["calls"]], expected * 2)
        self.assertEqual(len({row["campaign"] for row in state["calls"]}), 2)
        self.assertEqual({row["deadline"] for row in state["calls"]}, {1000.0})
        for instance in state["instances"]:
            self.assertEqual(instance.attempted, set(expected))
            self.assertEqual(instance.options["frozen_programs"]["A"], instance.options["frozen_programs"]["B"])
        provisional = json.loads((output / "PROVISIONAL.json").read_bytes())
        self.assertEqual(provisional["status"], "awaiting_external_exit_and_closure")
        self.assertFalse(provisional["production_authentic_admission"])
        self.assertFalse(provisional["scientific_evaluation"])
        self.assertEqual(provisional["docker_context"]["daemon_id"], "generated-control-daemon")
        self.assertEqual((provisional["configuration_phase_count"], provisional["probe_phase_count"]), (4, 4))
        self.assertEqual(len(provisional["resource_owners"]), 24)
        self.assertEqual(len({row["name"] for row in provisional["resource_owners"]}), 24)
        self.assertTrue(all(c["complete_ten_fold_campaign"] is False for c in provisional["campaigns"]))
        self.assertFalse((output / "QUALIFICATION.json").exists())

    def test_entry_failed_probe_and_expiry_stop_before_later_phases(self):
        for reason in ("failed-probe", "expired"):
            with self.subTest(reason=reason):
                now = 100.0 if reason == "failed-probe" else 950.0
                root = self.scratch / ("entry-" + reason)
                root.mkdir(mode=0o700)
                with self.mocked_entry_boundary(failed_probe=True, now=now) as (state, binding):
                    evidence = entry.Evidence(root, 1000.0, cap=65536)
                    with self.assertRaisesRegex(ValueError,
                            "designated engineering probe failed" if reason == "failed-probe" else "final closure reserve"):
                        entry.execute_campaign("probe", self.fixture, binding, {}, root / "probe", 100.0, 1000.0, evidence)
                self.assertEqual(len(state["instances"]), 1)
                self.assertEqual(len(state["calls"]), 1 if reason == "failed-probe" else 0)
                journal = root / "JOURNAL.jsonl"
                events = [json.loads(line) for line in journal.read_bytes().splitlines()] if journal.exists() else []
                self.assertEqual(len(events), 1 if reason == "failed-probe" else 0)
                self.assertFalse(any(row.get("event") == "PHASE-ACCEPTED" for row in events))

    def test_existing_duplicate_fold_guard_refuses_before_provider(self):
        owned = existing_transport.OwnedTransport.__new__(existing_transport.OwnedTransport)
        owned.campaign_id = "generated-duplicate-control"
        owned.image = audit.IMAGE
        owned.frozen_programs = {"A": self.fixture["campaigns"]["constant"]["program_pin"]}
        owned.origin = 100.0
        owned._attempted = {("A", 0)}
        owned._provider = mock.Mock()
        with mock.patch.object(existing_transport, "make_request", return_value={}) as request, \
             mock.patch.object(existing_transport, "_vendor") as vendor:
            with self.assertRaisesRegex(ValueError, "no repeated phase or automatic retry"):
                owned.execute_fold("A", 0, {}, {}, {}, 1000.0, mock.Mock())
            request.assert_called_once()
            vendor.assert_not_called()
            owned._provider.execute_phase.assert_not_called()
        self.assertEqual(owned._attempted, {("A", 0)})

    def test_entry_capture_requires_bounded_matching_bytes_and_both_eofs(self):
        base = {"schema": "meg-boundary-shell-capture/v1", "stdout_bytes": 2,
            "stderr_bytes": 0, "stdout_eof": True, "stderr_eof": True, "collectors_exit_codes": [0, 0]}
        cases = [("valid-empty-stderr", b"{}", b"", {}, True),
            ("exact-limits", b"x"*4096, b"y"*8192, {}, True),
            ("stdout-overflow", b"x"*4097, b"", {}, False),
            ("stderr-overflow", b"{}", b"y"*8193, {}, False),
            ("missing-stdout-eof", b"{}", b"", {"stdout_eof": False}, False),
            ("missing-stderr-eof", b"{}", b"", {"stderr_eof": False}, False),
            ("collector-failed", b"{}", b"", {"collectors_exit_codes": [0, 1]}, False),
            ("collector-boolean", b"{}", b"", {"collectors_exit_codes": [False, 0]}, False),
            ("mismatched-count", b"{}", b"", {"stdout_bytes": 1}, False)]
        for name, stdout, stderr, overrides, accepted in cases:
            root = self.scratch / ("capture-" + name)
            root.mkdir(mode=0o700)
            record = {**base, "stdout_bytes": len(stdout), "stderr_bytes": len(stderr), **overrides}
            write_body(root / "RUN_EXIT.json", encoded({"schema": "meg-boundary-shell-exit/v1", "exit_code": 0}))
            write_body(root / "RUN_CAPTURE.json", encoded(record))
            write_body(root / "RUN_STDOUT.json", stdout)
            write_body(root / "RUN_STDERR.log", stderr)
            with self.subTest(case=name):
                if accepted:
                    shell, observed, out, err = entry.capture_observation(root)
                    self.assertEqual(shell["exit_code"], 0)
                    self.assertEqual((observed, out, err), (record, stdout, stderr))
                else:
                    with self.assertRaisesRegex(ValueError, "bounded complete caller pipes"):
                        entry.capture_observation(root)

    def test_entry_process_absence_requires_known_wrappers_and_actual_absence(self):
        generated_transport = SimpleNamespace(_vendor=lambda: SimpleNamespace(
            engine=SimpleNamespace(encoded=entry.encoded)))
        references = mock.patch.multiple(entry, boundary_audit=audit, transport=generated_transport)
        references.start()
        self.addCleanup(references.stop)
        base = os.getpid() + 1000000
        def identity(pid):
            return {"schema": "osl_linux_process_identity_v1", "pid": pid, "pgid": pid,
                "session_id": pid, "uid": 1000, "start_time_ticks": 12345,
                "boot_id": "01234567-89ab-cdef-0123-456789abcdef"}
        def child(pid, index):
            return {"index": index, "phase": "generated-phase", "pid": pid, "pgid": pid,
                "original_end": 1000.0, "independent_group": True, "process_identity": identity(pid),
                "docker_exec_still_gated": True}
        audit_child, provider_child = child(base+1, 0), child(base+2, 1)
        record = {"schema": "osl_transport_journal_v1", "phase_id": "generated-A-fold-00",
            "request_sha256": "a"*64, "index": 1, "event": "CLI-CHILD", "value": provider_child}
        def audit_child_pin(value):
            return entry.pin(audit.encoded({"schema": "meg-boundary-audit-journal/v1", "event": "CLI-CHILD", "value": value}))
        rows = [{"event": "CLI-CHILD", "body": {"pin": audit_child_pin(audit_child), "value": audit_child}},
            {"event": "CLI-CHILD", "body": {"pin": entry.pin(entry.encoded(record)), "record": record}}]
        with mock.patch.object(entry.os, "kill", side_effect=ProcessLookupError) as pid_probe, \
             mock.patch.object(entry.os, "killpg", side_effect=ProcessLookupError) as group_probe:
            observed = entry.observe_process_absence(identity(base), rows)
            self.assertEqual(len(observed), 3)
            self.assertTrue(all(row["pid_absence_observed"] and row["group_absence_observed"] for row in observed))
            self.assertEqual(pid_probe.call_args_list, [mock.call(base+i, 0) for i in range(3)])
            self.assertEqual(group_probe.call_args_list, [mock.call(base+i, 0) for i in range(3)])
        unknown = copy.deepcopy(rows)
        unknown[0]["body"]["value"]["process_identity"]["schema"] = "unknown_identity"
        unknown[0]["body"]["pin"] = audit_child_pin(unknown[0]["body"]["value"])
        for index, message in ((0, "audit child journal pin"), (1, "Provider child journal pin")):
            bad_pin = copy.deepcopy(rows); bad_pin[index]["body"]["pin"]["sha256"] = "0"*64
            with self.subTest(pin=index), mock.patch.object(entry.os, "kill") as pid_probe, \
                 mock.patch.object(entry.os, "killpg") as group_probe:
                with self.assertRaisesRegex(ValueError, message):
                    entry.observe_process_absence(identity(base), bad_pin)
                pid_probe.assert_not_called()
                group_probe.assert_not_called()
        with mock.patch.object(entry.os, "kill", side_effect=ProcessLookupError), \
             mock.patch.object(entry.os, "killpg", side_effect=ProcessLookupError):
            with self.assertRaisesRegex(ValueError, "exact owned independent host session"):
                entry.observe_process_absence(identity(base), unknown)
        for label, pid_effect, group_effect, error in (("unknown", PermissionError, ProcessLookupError, PermissionError),
                ("live-pid", None, ProcessLookupError, ValueError),
                ("live-group", ProcessLookupError, None, ValueError)):
            with self.subTest(case=label), mock.patch.object(entry.os, "kill", side_effect=pid_effect), \
                 mock.patch.object(entry.os, "killpg", side_effect=group_effect):
                with self.assertRaises(error):
                    entry.observe_process_absence(identity(base), [])
        with mock.patch.object(entry.os, "kill") as pid_probe, mock.patch.object(entry.os, "killpg") as group_probe:
            with self.assertRaisesRegex(ValueError, "exact Provider child wrapper"):
                entry.observe_process_absence(identity(base), [{"event": "CLI-CHILD", "body": {"forged": True}}])
            pid_probe.assert_not_called()
            group_probe.assert_not_called()

    def test_entry_audit_continuity_requires_same_daemon_and_host_boot(self):
        root = self.scratch / "continuity"
        root.mkdir(mode=0o700)
        original_root = root / "audit"
        current_root = root / "current"
        drift_root = root / "boot-drift"
        for directory in (original_root, current_root, drift_root):
            directory.mkdir(mode=0o700)
        boot = "01234567-89ab-cdef-0123-456789abcdef"
        observations = entry.encoded({"host": {"boot_id": boot}})
        original = entry.encoded({"observations": entry.pin(observations)})
        write_body(original_root / "AUDIT.json", original)
        write_body(original_root / "OBSERVATIONS.json", observations)
        write_body(current_root / "OBSERVATIONS.json", observations)
        context = {"binary": "/generated/docker", "socket": "/generated/docker.sock",
            "image": audit.IMAGE, "daemon_id": "generated-original-daemon"}
        provisional = {"docker_context": context, "audit_path": str(original_root / "AUDIT.json"),
            "audit_pin": entry.pin(original), "worker_identity": {"boot_id": boot}}
        current = {"docker_context": dict(context), "audit_path": str(current_root / "AUDIT.json"),
            "observations_pin": entry.pin(observations)}
        observed = entry.audit_continuity(provisional, current, root)
        self.assertEqual(observed, {"same_daemon": True, "same_host_boot": True,
            "initial_observations_pin": entry.pin(observations),
            "current_observations_pin": entry.pin(observations)})
        different_daemon = copy.deepcopy(current)
        different_daemon["docker_context"]["daemon_id"] = "generated-other-daemon"
        with self.assertRaisesRegex(ValueError, "same observed daemon"):
            entry.audit_continuity(provisional, different_daemon, root)
        changed_boot = entry.encoded({"host": {"boot_id": "fedcba98-7654-3210-fedc-ba9876543210"}})
        write_body(drift_root / "OBSERVATIONS.json", changed_boot)
        different_boot = {"docker_context": dict(context), "audit_path": str(drift_root / "AUDIT.json"),
            "observations_pin": entry.pin(changed_boot)}
        with self.assertRaisesRegex(ValueError, "same boot"):
            entry.audit_continuity(provisional, different_boot, root)
