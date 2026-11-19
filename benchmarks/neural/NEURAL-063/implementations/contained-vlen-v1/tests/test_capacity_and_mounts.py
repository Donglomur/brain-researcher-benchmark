"""Thirteen generated controls for contained mount validation and settlement.

Run in a caller-provisioned bounded generated-control environment. The caller
supplies authenticated source descriptors. No Docker, original payload or
Unit constructor is used. Generated inspect records exist only in memory. Tiny
inventory records use caller-provisioned external scratch. These are Docker
configuration checks, not evidence of guest mount realization or scientific runs.
"""
import argparse
import builtins
import contextlib
import copy
from collections import Counter
import fcntl
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import time
import types
from urllib.parse import urlsplit
import unittest
from unittest import mock

CONTROLLER_READ_CAP = 131072
RESULT_CAP = 32768
EXPECTED_METHODS = 13
FIXTURE_WRITE_CAP = 65536
THREAD_KEYS = (
    "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS", "BLIS_NUM_THREADS",
    "POLARS_MAX_THREADS", "RAYON_NUM_THREADS",
)
TMPFS = {
    "/tmp": "rw,noexec,nosuid,nodev,size=16777216,mode=1777",
    "/output": "rw,noexec,nosuid,nodev,size=134217728,mode=1777",
}


def _load_module(label, path, expected_bytes, expected_sha256):
    """Execute the complete pinned module under a non-main name, with IO denied."""
    if type(expected_bytes) is not int or not 0 < expected_bytes <= CONTROLLER_READ_CAP:
        raise ValueError("bounded controller descriptor required")
    if not isinstance(expected_sha256, str) or not re.fullmatch(r"[a-f0-9]{64}", expected_sha256):
        raise ValueError("exact controller hash required")
    p = Path(path)
    if not p.is_absolute() or p.is_symlink() or not stat.S_ISREG(p.stat().st_mode):
        raise ValueError("absolute ordinary source required")
    with p.open("rb") as stream:
        source = stream.read(CONTROLLER_READ_CAP + 1)
    if len(source) != expected_bytes or hashlib.sha256(source).hexdigest() != expected_sha256:
        raise ValueError("controller identity mismatch")
    code = compile(source, str(p), "exec")
    module = types.ModuleType("generated_contained_" + label)
    module.__file__ = str(p)
    effects = []

    def deny(name):
        def blocked(*args, **kwargs):
            effects.append(name)
            raise AssertionError("controller import attempted " + name)
        return blocked

    # All imports used by the controller are already loaded above. Reading its
    # bounded, pinned source is completed before this module-initialization guard.
    forbidden = (
        "builtins.open", "io.open", "io.open_code", "os.open", "os.mkdir",
        "os.makedirs", "os.remove", "os.unlink", "os.rename", "os.replace",
        "os.system", "os.write", "subprocess.Popen", "subprocess.run",
        "subprocess.call", "subprocess.check_call", "subprocess.check_output",
        "socket.socket", "socket.create_connection",
    )
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.ExitStack() as stack:
        for name in forbidden:
            stack.enter_context(mock.patch(name, side_effect=deny(name)))
        stack.enter_context(contextlib.redirect_stdout(stdout))
        stack.enter_context(contextlib.redirect_stderr(stderr))
        exec(code, module.__dict__)
    if effects or stdout.getvalue() or stderr.getvalue():
        raise AssertionError("controller import was not inert")
    return module, len(source), effects


def _fixture(module, phase, scratch=(), kind="session"):
    unit = object.__new__(module.Unit)
    unit.kind = kind
    unit.identity = "generated-session"
    unit.owner = "generated-owner"
    unit.name = "n063-generated-owned-session"
    unit.cid = "a" * 64
    unit.reservation = {"reservation_sha256": "b" * 64}
    unit.op = {
        "runtime": {"python_in_image": "/usr/local/bin/python3"},
        "deployment": {
            "image_id": "sha256:" + "c" * 64,
            "image_env": ["PATH=/usr/local/bin:/usr/bin:/bin"],
            "plane_network": {"name": "generated-owned-network"},
        },
    }
    unit.mounts = {
        "/operator": "/generated/source",
        "/inputs": "/generated/inputs",
    }
    value = {
        "id": unit.cid, "name": "/" + unit.name,
        "image": unit.op["deployment"]["image_id"],
        "labels": {
            "n063.owner": unit.owner, "n063.kind": unit.kind,
            "n063.identity": unit.identity,
            "n063.reservation": unit.reservation["reservation_sha256"],
        },
        "entry": ["/usr/local/bin/python3"],
        "cmd": ["-I", "-S", "-B", "/operator/controller.py", "start"],
        "user": "65534:65534", "workdir": "/tmp", "tty": False,
        "stdin": False,
        "network": "none" if kind == "session" else "generated-owned-network",
        "readonly": True,
        "privileged": False, "capdrop": ["ALL"],
        "security": ["no-new-privileges:true"],
        "memory": 1879048192, "swap": 1879048192,
        "cpus": 1000000000, "pids": 32, "shm": 1048576,
        "tmpfs": copy.deepcopy(TMPFS), "log": {"Type": "none", "Config": {}},
        "volumes": None, "capadd": None, "devices": None,
        "requests": None, "rules": None, "ports": None,
        "pidmode": "", "ipcmode": "private", "restart": {"Name": "no"},
        "env": ["PATH=/usr/local/bin:/usr/bin:/bin"]
               + [key + "=1" for key in THREAD_KEYS]
               + ["PYTHONDONTWRITEBYTECODE=1", "TMPDIR=/tmp"],
        "ulimits": [
            {"Name": key, "Soft": n, "Hard": n}
            for key, n in (("nofile", 1024), ("core", 0),
                           ("fsize", 100663296), ("cpu", 1800))
        ],
        "declaredmounts": [
            {"Target": target, "Type": "bind", "Source": source, "ReadOnly": True}
            for target, source in unit.mounts.items()
        ],
        "mounts": [
            {"Destination": target, "Type": "bind", "Source": source,
             "RW": False, "Propagation": "rprivate"}
            for target, source in unit.mounts.items()
        ] + [{"Destination": target, "Type": "tmpfs", "RW": True} for target in scratch],
        "state": {"Status": phase, "OOMKilled": False, "Error": "",
                  "Running": phase == "running", "Pid": 123 if phase == "running" else 0,
                  "ExitCode": 0},
    }
    if len(json.dumps(value)) > 8192:
        raise AssertionError("generated fixture exceeds declared bound")
    return unit, value


def run_controls(controller_path, expected_bytes, expected_sha256, *,
                 inventory_path, inventory_bytes, inventory_sha256, scratch_root):
    """Run only the thirteen source controls in the caller's bounded environment."""
    module, source_read_bytes, import_effects = _load_module(
        "controller", controller_path, expected_bytes, expected_sha256
    )
    inventory, inventory_read_bytes, inventory_import_effects = _load_module(
        "inventory", inventory_path, inventory_bytes, inventory_sha256
    )
    scratch = Path(scratch_root)
    if (not scratch.is_absolute() or scratch.exists() or scratch.is_symlink()
            or not scratch.parent.is_dir()
            or any(p.is_symlink() for p in (scratch.parent, *scratch.parent.parents))):
        raise ValueError("fresh absolute scratch root with ordinary existing parent required")
    scratch.mkdir(mode=0o700)
    fixture_usage = {"attempted_write_bytes": 0, "confirmed_file_bytes": 0,
                     "writer_calls": 0, "partial_failure_injections": 0}
    actual_writer = inventory.exclusive_bytes

    def bounded_writer(path, body):
        # Only the publication boundary is wrapped. Inventory admission,
        # precharge, finish and settlement logic remain the actual source.
        path = Path(path)
        if path.parent.parent != scratch or not isinstance(body, bytes):
            raise AssertionError("finite generated fixture namespace required")
        if fixture_usage["attempted_write_bytes"] + len(body) > FIXTURE_WRITE_CAP:
            raise AssertionError("cumulative generated fixture write cap")
        fixture_usage["attempted_write_bytes"] += len(body)
        fixture_usage["writer_calls"] += 1
        result = actual_writer(path, body)
        fixture_usage["confirmed_file_bytes"] += result["bytes"]
        return result

    def fresh_inventory(label, *, narrow_control_headroom=False):
        folder = scratch / label
        folder.mkdir(mode=0o700)
        obj = object.__new__(inventory.Inventory)
        cap = {
            "http_requests": 4, "http_response_body_bytes": 4096,
            "http_header_reservation_bytes": 131072, "logical_read_bytes": 8192,
            "export_read_bytes": 4096, "host_write_bytes": 133120,
            "control_bytes": 131072, "closure_seconds": 10,
            "worker_artifact_write_bytes": 2048, "worker_control_bytes": 8192,
            "source_setup_read_bytes": 65536,
        }
        if set(cap) != inventory.COUNTERS:
            raise AssertionError("fixed fixture covers every inventory counter")
        obj.root, obj.owner = folder, "a" * 64
        obj.terminal = 8192
        global_caps = {key: 2 * value for key, value in cap.items()}
        for key in ("control_bytes", "host_write_bytes"):
            global_caps[key] += obj.terminal
            if narrow_control_headroom:
                global_caps[key] = cap[key] + 65536 + obj.terminal
        obj.profile = {"global_caps": global_caps,
                       "unit_caps": {"plane": dict(cap), "session": dict(cap)},
                       "terminal_inventory_bytes": obj.terminal}
        obj.planes = {identity: {"state": "unattempted", "reason": "not_attempted",
                                 "artifact": None} for identity in ("1", "2")}
        obj.sessions, obj.members = {}, {}
        obj.spent = {key: 0 for key in cap}
        obj.initial_reserved_cumulative = dict(obj.spent)
        obj.settlements, obj.reservations, obj.reservation_refs = {}, {}, {}
        obj.unit_control_written, obj.export_claims = {}, {}
        obj.control_written = 0
        obj.active = None
        obj.stopped = obj.finalized = False
        obj.publication_failures = []
        return obj

    def successful_evidence(obj):
        reserved = obj.reserve("plane", "1")
        artifact = {"name": "plane_metadata.json", "bytes": 17, "sha256": "c" * 64}
        lease = {"reservation_sha256": reserved["reservation_sha256"],
                 "container_id": "d" * 64, "producer_receipt_sha256": "e" * 64,
                 "ownership_receipt_sha256": "f" * 64}
        obj.export_claims["plane-1"] = {"lease": lease, "expected": artifact}
        worker = {"bytes_requested": 19, "bytes_confirmed": 17, "write_calls": 1,
                  "exclusive_append_only": True, "same_fd_path": True,
                  "fsync": True, "complete": True, "sha256": artifact["sha256"]}
        copyout = {"verified": True, "identity": "1", "artifact": artifact,
                   "container_id": lease["container_id"],
                   "reservation_sha256": lease["reservation_sha256"],
                   "write_usage": {**worker, "bytes_requested": 128}, "read_bytes": 64}
        closure = {"kind": "plane", "identity": "1", **lease, "artifact": artifact,
                   "export_receipt_sha256": hashlib.sha256(inventory.encoded(copyout)).hexdigest(),
                   "proofs": {name: True for name in (
                       "producer_complete", "producer_zero_exit", "oom_absent", "timeout_absent",
                       "copyout_verified", "streams_eof", "cli_reaped", "ownership_verified",
                       "container_absence_verified")}}
        receipt = {
            "schema": "neural063_unit_success_settlement_v1", "kind": "plane", "identity": "1",
            "reservation_sha256": lease["reservation_sha256"], "container_id": lease["container_id"],
            "output": artifact, "worker_output": worker,
            "range": {"failed": False, "request_unresolved": False, "requests_admitted": 1,
                      "records_count": 1, "range_receipt_bytes_reserved": 512,
                      "complete_response_body_bytes_observed": 64,
                      "response_body_bytes_reserved_including_failures": 64,
                      "range_records_sha256": "1" * 64, "logical_bytes_requested": 128},
            "session_input_bytes_read_including_EOF_probes": 0, "source_setup_read_bytes": 17,
            "copyout": copyout, "controller_requested_write_bytes": 1250,
            "controller_control_bytes": 1250, "unmeasured_residuals_stay_reserved": True,
            "receipt_hashes": {"ready": lease["producer_receipt_sha256"],
                              "configuration": "2" * 64, "exit": "3" * 64,
                              "absence": "4" * 64, "copyout": closure["export_receipt_sha256"]},
        }
        return artifact, closure, copyout, receipt

    def expected_success_charge(obj):
        # Hand-derived policy witness: 1250 controller + 32768 for two future
        # publications + 1024 marker = 35042, plus the actual precharged prefix.
        used = dict(obj.reservations["plane-1"])
        retained_control = 35042 + obj.unit_control_written["plane-1"]
        used.update(control_bytes=retained_control, host_write_bytes=retained_control + 128,
                    export_read_bytes=82, worker_artifact_write_bytes=19, http_requests=1,
                    http_response_body_bytes=64, http_header_reservation_bytes=32768,
                    logical_read_bytes=128)
        return used

    class MountPhaseControls(unittest.TestCase):
        def accept(self, phase, kind):
            unit, value = _fixture(module, phase, kind=kind)
            self.assertIsNone(unit.verify_config(value, phase))

        def refuse_mutation(self, phase, mutate):
            unit, value = _fixture(module, phase)
            mutate(value)
            with self.assertRaises(ValueError):
                unit.verify_config(value, phase)

        def test_00_complete_module_import_is_inert(self):
            self.assertEqual(import_effects, [])
            self.assertEqual(module.Unit.verify_config.__module__, module.__name__)
            self.assertEqual(module.Unit.ownership.__module__, module.__name__)

        def test_01_all_phases_accept_configured_tmpfs_and_bind_only_inspection(self):
            for phase in ("created", "running", "exited"):
                for kind in ("session", "plane"):
                    with self.subTest(phase=phase, kind=kind):
                        self.accept(phase, kind)

        def test_02_legacy_tmpfs_entries_are_not_allowed_in_inspected_mounts(self):
            for phase in ("created", "running", "exited"):
                for scratch in (("/tmp",), ("/output",), ("/tmp", "/output")):
                    with self.subTest(phase=phase, scratch=scratch):
                        unit, value = _fixture(module, phase, scratch)
                        with self.assertRaises(ValueError):
                            unit.verify_config(value, phase)

        def test_03_inspected_bind_roster_is_complete_and_unique(self):
            mutations = {
                "absent": lambda v: v.pop("mounts"),
                "null": lambda v: v.update(mounts=None),
                "wrong-type": lambda v: v.update(mounts=tuple(v["mounts"])),
                "missing": lambda v: v["mounts"].pop(),
                "extra": lambda v: v["mounts"].append(
                    {"Destination": "/unexpected", "Type": "bind", "Source": "/generated/extra",
                     "RW": False, "Propagation": "rprivate"}),
                "duplicate-same-count": lambda v: v["mounts"].__setitem__(1, copy.deepcopy(v["mounts"][0])),
                "volume-type": lambda v: v["mounts"][0].update(Type="volume"),
            }
            for phase in ("created", "running", "exited"):
                for name, change in mutations.items():
                    with self.subTest(phase=phase, mutation=name):
                        self.refuse_mutation(phase, change)

        def test_04_configured_tmpfs_remains_exact_in_every_phase(self):
            mutations = {
                "absent": lambda v: v.pop("tmpfs"),
                "missing": lambda v: v["tmpfs"].pop("/output"),
                "extra": lambda v: v["tmpfs"].update({"/unexpected": TMPFS["/tmp"]}),
                "size": lambda v: v["tmpfs"].update({"/tmp": TMPFS["/tmp"].replace("16777216", "33554432")}),
                "noexec": lambda v: v["tmpfs"].update({"/tmp": TMPFS["/tmp"].replace("noexec", "exec")}),
            }
            for phase in ("created", "running", "exited"):
                for name, change in mutations.items():
                    with self.subTest(phase=phase, mutation=name):
                        self.refuse_mutation(phase, change)

        def test_05_declared_and_inspected_binds_remain_exact_in_every_phase(self):
            mutations = {
                "missing-declaration": lambda v: v["declaredmounts"].pop(),
                "writable-declaration": lambda v: v["declaredmounts"][0].update(ReadOnly=False),
                "wrong-declared-source": lambda v: v["declaredmounts"][0].update(Source="/generated/other"),
                "writable-inspected": lambda v: v["mounts"][0].update(RW=True),
                "wrong-inspected-source": lambda v: v["mounts"][0].update(Source="/generated/other"),
                "shared-propagation": lambda v: v["mounts"][0].update(Propagation="shared"),
            }
            for phase in ("created", "running", "exited"):
                for name, change in mutations.items():
                    with self.subTest(phase=phase, mutation=name):
                        self.refuse_mutation(phase, change)

        def test_06_exact_container_ownership_remains_required(self):
            mutations = {
                "id": lambda v: v.update(id="d" * 64),
                "name": lambda v: v.update(name="/another-owned-looking-unit"),
                "image": lambda v: v.update(image="sha256:" + "d" * 64),
                "owner": lambda v: v["labels"].update({"n063.owner": "other-owner"}),
                "identity": lambda v: v["labels"].update({"n063.identity": "other-session"}),
                "reservation": lambda v: v["labels"].update({"n063.reservation": "d" * 64}),
            }
            for phase in ("created", "running", "exited"):
                for name, change in mutations.items():
                    with self.subTest(phase=phase, mutation=name):
                        self.refuse_mutation(phase, change)

        def test_07_container_phase_and_completion_checks_are_preserved(self):
            for phase in ("created", "running", "exited"):
                for name, values in (
                    ("status", {"Status": "paused"}),
                    ("oom", {"OOMKilled": True}),
                    ("error", {"Error": "generated failure"}),
                    ("running-flag", {"Running": phase != "running"}),
                ):
                    with self.subTest(phase=phase, mutation=name):
                        self.refuse_mutation(phase, lambda v, x=values: v["state"].update(x))
            self.refuse_mutation("created", lambda v: v["state"].update(Pid=123))
            self.refuse_mutation("running", lambda v: v["state"].update(Pid=0))
            self.refuse_mutation("exited", lambda v: v["state"].update(ExitCode=1))

    class SettlementControls(unittest.TestCase):
        def test_08_durable_success_settles_measured_control_then_admits_next_unit(self):
            obj = fresh_inventory("durable-success", narrow_control_headroom=True)
            artifact, closure, copyout, receipt = successful_evidence(obj)
            cap = dict(obj.reservations["plane-1"])
            prefix = obj.unit_control_written["plane-1"]
            self.assertEqual(prefix, obj.reservation_refs["plane-1"]["bytes"])
            expected = expected_success_charge(obj)
            self.assertEqual(obj._success_usage("plane", "1", artifact, closure, copyout, receipt), expected)
            self.assertGreater(cap["control_bytes"] * 2,
                               obj.profile["global_caps"]["control_bytes"] - obj.terminal)
            observed = []

            def observe_publication(path, body):
                self.assertEqual(obj.spent, cap, "no release before both durable publications")
                ref = bounded_writer(path, body)
                self.assertEqual(obj.spent, cap, "publication itself cannot release charge")
                observed.append(Path(path).name)
                return ref

            with mock.patch.object(inventory, "exclusive_bytes", side_effect=observe_publication):
                obj.finish_unit("plane", "1", artifact=artifact, closure=closure,
                                copyout_result=copyout, settlement_receipt=receipt)
            self.assertEqual(observed, ["plane-1-result.json", "plane-1-settlement.json"])
            self.assertEqual(obj.spent, expected)
            self.assertEqual(obj.planes["1"]["state"], "complete")
            self.assertIn("plane-1", obj.settlements)
            self.assertEqual(obj.spent["worker_control_bytes"], 8192)
            self.assertEqual(obj.spent["source_setup_read_bytes"], 65536)
            self.assertEqual(obj.spent["closure_seconds"], 10)
            next_unit = obj.reserve("plane", "2")
            self.assertEqual(next_unit["envelope"], cap)
            self.assertEqual(obj.spent, {key: expected[key] + cap[key] for key in cap})
            self.assertEqual(obj.initial_reserved_cumulative, {key: 2 * cap[key] for key in cap})

        def test_09_failure_and_uncertain_closure_keep_full_reservation(self):
            for reason in ("worker_failed", "cleanup_unknown"):
                with self.subTest(reason=reason):
                    obj = fresh_inventory(reason)
                    reserve = obj.reserve("plane", "1")
                    obj.finish_unit("plane", "1", failure=reason,
                                    closure={"kind": "plane", "identity": "1", "unknown": True})
                    self.assertEqual(obj.spent, reserve["envelope"])
                    self.assertEqual(obj.settlements, {})
                    self.assertEqual(obj.planes["1"]["state"], "failed")
                    self.assertEqual(obj.planes["1"]["reason"], reason)

        def test_10_partial_settlement_publication_cannot_release_any_charge(self):
            obj = fresh_inventory("partial-settlement")
            artifact, closure, copyout, receipt = successful_evidence(obj)
            cap = dict(obj.reservations["plane-1"])

            def fail_after_durable_prefix(path, body):
                if Path(path).name.endswith("-settlement.json"):
                    if fixture_usage["attempted_write_bytes"] + len(body) > FIXTURE_WRITE_CAP:
                        raise AssertionError("complete failed attempt must fit fixture allowance")
                    fixture_usage["attempted_write_bytes"] += len(body)
                    fixture_usage["writer_calls"] += 1
                    actual_writer(path, body[:1])
                    fixture_usage["confirmed_file_bytes"] += 1
                    fixture_usage["partial_failure_injections"] += 1
                    raise OSError("generated failure after durable one-byte settlement prefix")
                return bounded_writer(path, body)

            with mock.patch.object(inventory, "exclusive_bytes", side_effect=fail_after_durable_prefix):
                with self.assertRaises(OSError):
                    obj.finish_unit("plane", "1", artifact=artifact, closure=closure,
                                    copyout_result=copyout, settlement_receipt=receipt)
            self.assertEqual(obj.spent, cap)
            self.assertEqual(obj.settlements, {})
            self.assertTrue(obj.stopped)
            self.assertEqual(obj.publication_failures, ["plane-1-settlement.json"])
            self.assertEqual(obj.planes["1"]["reason"], "dispatch_publication_failed")
            self.assertGreater((obj.root / "plane-1-result.json").stat().st_size, 1)
            self.assertEqual((obj.root / "plane-1-settlement.json").stat().st_size, 1)
            with self.assertRaises(ValueError):
                obj.reserve("plane", "2")

        def test_11_counter_or_identity_mismatches_refuse_before_release(self):
            obj = fresh_inventory("counter-mismatch")
            artifact, closure, copyout, receipt = successful_evidence(obj)
            original_spent = dict(obj.spent)
            mutations = {
                "controller-disagreement": lambda r: r.update(controller_control_bytes=1249),
                "controller-over-cap": lambda r: r.update(controller_control_bytes=131072,
                                                           controller_requested_write_bytes=131072),
                "wrong-reservation": lambda r: r.update(reservation_sha256="0" * 64),
                "worker-over-cap": lambda r: r["worker_output"].update(bytes_requested=2049),
                "unconfirmed-worker": lambda r: r["worker_output"].update(bytes_confirmed=16),
                "unfinished-worker": lambda r: r["worker_output"].update(complete=False),
                "setup-over-cap": lambda r: r.update(source_setup_read_bytes=65537),
                "unresolved-range": lambda r: r["range"].update(request_unresolved=True),
                "body-counter-disagreement": lambda r: r["range"].update(complete_response_body_bytes_observed=63),
            }
            for name, mutate in mutations.items():
                with self.subTest(mutation=name):
                    changed = copy.deepcopy(receipt)
                    mutate(changed)
                    with self.assertRaises(ValueError):
                        obj.finish_unit("plane", "1", artifact=artifact, closure=closure,
                                        copyout_result=copyout, settlement_receipt=changed)
                    self.assertEqual(obj.spent, original_spent)
                    self.assertEqual(obj.active, ("plane", "1"))
                    self.assertEqual(obj.settlements, {})
            saved_prefix = obj.unit_control_written["plane-1"]
            obj.unit_control_written["plane-1"] = 65537
            try:
                with self.assertRaises(ValueError):
                    obj._success_usage("plane", "1", artifact, closure, copyout, receipt)
            finally:
                obj.unit_control_written["plane-1"] = saved_prefix
            self.assertEqual(obj.spent, original_spent)

        def test_12_exact_quota_is_admitted_and_next_unit_exhaustion_refuses_before_dispatch(self):
            obj = fresh_inventory("quota-boundary")
            cap = obj.profile["unit_caps"]["plane"]
            obj.profile["global_caps"] = {
                key: value + (obj.terminal if key in ("control_bytes", "host_write_bytes") else 0)
                for key, value in cap.items()
            }
            first = obj.reserve("plane", "1")
            self.assertEqual(first["envelope"], cap)
            self.assertEqual(obj.spent, cap)
            obj.finish_unit("plane", "1", failure="worker_failed")
            before = dict(obj.spent)
            with self.assertRaisesRegex(ValueError, "global reservation exhausted before dispatch"):
                obj.reserve("plane", "2")
            self.assertEqual(obj.spent, before)
            self.assertTrue(obj.stopped)
            self.assertEqual(obj.planes["2"]["reason"], "global_budget_exhausted")
            self.assertNotIn("plane-2", obj.reservations)
            self.assertFalse((obj.root / "plane-2-reservation.json").exists())

    suite = unittest.TestSuite([
        unittest.defaultTestLoader.loadTestsFromTestCase(MountPhaseControls),
        unittest.defaultTestLoader.loadTestsFromTestCase(SettlementControls),
    ])
    if suite.countTestCases() != EXPECTED_METHODS:
        raise AssertionError("fixed thirteen-method group required")
    with mock.patch.object(inventory, "exclusive_bytes", side_effect=bounded_writer):
        result = unittest.TextTestRunner(stream=sys.stderr, verbosity=1).run(suite)
    record = {
        "schema": "contained-mount-phase-controls/v1",
        "controller": {"bytes": expected_bytes, "sha256": expected_sha256},
        "inventory": {"bytes": inventory_bytes, "sha256": inventory_sha256},
        "methods_run": result.testsRun, "expected_methods": EXPECTED_METHODS,
        "failures": len(result.failures), "errors": len(result.errors),
        "skips": len(result.skipped),
        "passed": result.wasSuccessful() and result.testsRun == EXPECTED_METHODS and not result.skipped,
        "failure_details": [{"test": str(test), "traceback": detail[-2048:]}
                            for test, detail in (result.failures + result.errors)[:8]],
        "source_read_bytes": source_read_bytes + inventory_read_bytes,
        "fixture_file_bytes": fixture_usage["confirmed_file_bytes"],
        "fixture_requested_write_cap_bytes": FIXTURE_WRITE_CAP,
        "fixture_usage": fixture_usage,
        "fixture_record_json_cap_bytes": 8192,
        "mount_fixture_records_live_at_once_max": 2,
        "result_write_cap_bytes": RESULT_CAP,
        "cumulative_generated_write_cap_bytes": FIXTURE_WRITE_CAP + RESULT_CAP,
        "docker_calls": 0, "native_calls": 0, "original_payload_reads": 0,
        "import_forbidden_operations": import_effects,
        "inventory_import_forbidden_operations": inventory_import_effects,
        "proof_scope": "Generated Docker configuration records and tiny inventory settlement publications; no guest mount realization or scientific execution proof",
    }
    body = (json.dumps(record, sort_keys=True, indent=2) + "\n").encode()
    if len(body) > RESULT_CAP:
        raise AssertionError("bounded control result required")
    with (scratch / "RESULT.json").open("xb") as stream:
        stream.write(body)
    os.chmod(scratch / "RESULT.json", 0o600)
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--controller", required=True)
    parser.add_argument("--controller-bytes", required=True, type=int)
    parser.add_argument("--controller-sha256", required=True)
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--inventory-bytes", required=True, type=int)
    parser.add_argument("--inventory-sha256", required=True)
    parser.add_argument("--scratch-dir", required=True)
    args = parser.parse_args(argv)
    record = run_controls(str(Path(args.controller).absolute()), args.controller_bytes,
                          args.controller_sha256, inventory_path=str(Path(args.inventory).absolute()),
                          inventory_bytes=args.inventory_bytes, inventory_sha256=args.inventory_sha256,
                          scratch_root=str(Path(args.scratch_dir).absolute()))
    print(json.dumps({"passed": record["passed"], "methods_run": record["methods_run"],
                      "result": str(Path(args.scratch_dir).absolute() / "RESULT.json")}, sort_keys=True))
    return 0 if record["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
