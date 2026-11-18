"""Generated-only guard controls. No NumPy import, package execution, or neural data."""
import base64
import copy
import csv
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("temporal_guard", HERE / "guard.py")
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
def choose_fixture_root(environment):
    value = environment.get("TEMPORAL_GUARD_FIXTURE_ROOT", str(HERE / "generated_guard_controls_v4"))
    # An explicit path must be absolute and canonical. Creation below remains
    # exclusive: a selected existing attempt is never cleaned or reused.
    return guard.canonical(value, exists=False)


ROOT = choose_fixture_root(os.environ)
ROOT.mkdir()  # one immutable generated attempt, never silently reuse fixtures
WRITES = {"files": 0, "cumulative_bytes": 0}


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        data = data.encode()
    WRITES["files"] += 1
    WRITES["cumulative_bytes"] += len(data)
    path.write_bytes(data)
    return {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def sample_protocol(base):
    return {"owner": "build_temporal_prediction", "approval_id": "approval1",
            "native_run_id": "run1", "resource_ledger": str(base / "ledger.json"),
            "launch": {"native_command": ["watchdog", "{protocol_sha256}"], "cwd": str(Path.cwd())},
            "output": {"path": str(base / "output"), "reservation_id": "artifact1",
                       "reserved_bytes": 128 * guard.MIB, "allow_create_parent": True}}


def sample_ledger(protocol, path, sha, pid=54321):
    pin = {"path": str(path), "sha256": sha}
    return {"schema": "comprehensive_revision_resources_v1",
            "native_execution": {"maximum_concurrent_heavy_jobs": 1},
            "approved_native_protocols": [{"id": "approval1", "owner": protocol["owner"],
                                          "approved_by": "/root", "protocol": pin}],
            "native_runs": [{"id": "run1", "owner": protocol["owner"], "protocol": pin,
                             "approval_id": "approval1", "status": "running", "command": ["watchdog", sha],
                             "cwd": str(Path.cwd()), "requested_threads": 1,
                             "declared_max_working_ram_bytes": 1024 ** 3,
                             "coordinator_pid": 23456, "child_pid": pid}],
            "reservations": [{"id": "artifact1", "owner": protocol["owner"], "kind": "artifact",
                              "status": "active", "destination": protocol["output"]["path"],
                              "reserved_bytes": 128 * guard.MIB}]}


class GuardControls(unittest.TestCase):
    def setUp(self):
        self.base = ROOT / self._testMethodName
        self.base.mkdir()
        self.protocol = sample_protocol(self.base)
        self.path = self.base / "protocol.json"
        self.sha = "a" * 64
        self.ledger = sample_ledger(self.protocol, self.path, self.sha)

    def test_exact_ledger_accepts_and_missing_pid_is_only_wait_case(self):
        self.assertTrue(guard.check_ledger(self.ledger, self.protocol, self.path, self.sha, 54321))
        del self.ledger["native_runs"][0]["child_pid"]
        self.assertFalse(guard.check_ledger(self.ledger, self.protocol, self.path, self.sha, 54321))
        for field, value in (("owner", "other"), ("command", ["other"]),
                             ("requested_threads", 2), ("declared_max_working_ram_bytes", 2048),
                             ("protocol", {"path": str(self.path), "sha256": "b" * 64}),
                             ("status", "succeeded"), ("cwd", "/")):
            row = copy.deepcopy(self.ledger)
            row["native_runs"][0][field] = value
            with self.subTest(field=field), self.assertRaises(guard.GuardError):
                guard.check_ledger(row, self.protocol, self.path, self.sha, 54321)

    def test_foreign_pid_and_null_pid_fail_immediately(self):
        for pid in (None, 12345, True):
            self.ledger["native_runs"][0]["child_pid"] = pid
            with self.subTest(pid=pid), self.assertRaises(guard.GuardError):
                guard.check_ledger(self.ledger, self.protocol, self.path, self.sha, 54321)

    def test_approval_reservation_and_duplicate_lease_fail(self):
        for field, value in (("owner", "other"), ("status", "completed"),
                             ("destination", str(self.base / "wrong")),
                             ("kind", "download"), ("reserved_bytes", 1)):
            row = copy.deepcopy(self.ledger)
            row["reservations"][0][field] = value
            with self.subTest(field=field), self.assertRaises(guard.GuardError):
                guard.check_ledger(row, self.protocol, self.path, self.sha, 54321)
        self.ledger["approved_native_protocols"][0]["approved_by"] = "/other"
        with self.assertRaises(guard.GuardError):
            guard.check_ledger(self.ledger, self.protocol, self.path, self.sha, 54321)
        self.ledger["approved_native_protocols"][0]["approved_by"] = "/root"
        self.ledger["native_runs"].append(copy.deepcopy(self.ledger["native_runs"][0]))
        with self.assertRaises(guard.GuardError):
            guard.check_ledger(self.ledger, self.protocol, self.path, self.sha, 54321)

    def test_poll_records_every_read_and_waits_only_for_pid(self):
        missing = copy.deepcopy(self.ledger)
        del missing["native_runs"][0]["child_pid"]
        write(Path(self.protocol["resource_ledger"]), json.dumps(missing))
        clock = [0.0]
        def sleep(seconds):
            clock[0] += seconds
            write(Path(self.protocol["resource_ledger"]), json.dumps(self.ledger))
        meters = guard.ReadMeters()
        result = guard.await_ledger(self.protocol, self.path, self.sha, meters,
                                    monotonic=lambda: clock[0], sleep=sleep, parent_pid=54321)
        self.assertEqual(result["ledger_attempts"], 2)
        self.assertEqual(meters.buckets["metadata"]["reserved_attempt_bytes"], 2 * (2 * guard.MIB + 1))
        self.assertEqual(clock[0], 0.05)

    def test_poll_deadline_is_finite_and_no_mismatch_retry(self):
        del self.ledger["native_runs"][0]["child_pid"]
        write(Path(self.protocol["resource_ledger"]), json.dumps(self.ledger))
        clock = [0.0]
        def sleep(seconds):
            clock[0] += seconds
        meters = guard.ReadMeters()
        with self.assertRaises(guard.GuardError):
            guard.await_ledger(self.protocol, self.path, self.sha, meters,
                               monotonic=lambda: clock[0], sleep=sleep, parent_pid=54321)
        self.assertLessEqual(clock[0], 1.0)
        self.assertLessEqual(meters.buckets["metadata"]["attempts"], 21)
        self.ledger["reservations"][0]["status"] = "completed"
        write(Path(self.protocol["resource_ledger"]), json.dumps(self.ledger))
        meters = guard.ReadMeters()
        with self.assertRaises(guard.GuardError):
            guard.await_ledger(self.protocol, self.path, self.sha, meters,
                               monotonic=lambda: clock[0], sleep=sleep, parent_pid=54321)
        self.assertEqual(meters.buckets["metadata"]["attempts"], 1)

    def test_read_pin_tamper_and_failed_reads_keep_charge(self):
        pin = write(self.base / "small.bin", b"abc")
        meters = guard.ReadMeters()
        self.assertEqual(guard.read_pin(pin, meters), b"abc")
        write(self.base / "small.bin", b"abd")
        with self.assertRaises(guard.GuardError):
            guard.read_pin(pin, meters)
        pin["bytes"] = 2
        with self.assertRaises(guard.GuardError):
            guard.read_pin(pin, meters)
        self.assertEqual(meters.buckets["metadata"]["reserved_attempt_bytes"], 11)
        self.assertEqual(meters.buckets["metadata"]["returned_bytes"], 6)
        self.assertEqual(meters.buckets["metadata"]["failed_attempts"], 1)

    def test_duplicate_nonfinite_json_and_read_budget_reject(self):
        for data in (b'{"a":1,"a":2}', b'{"a":NaN}'):
            with self.assertRaises(guard.GuardError):
                guard.unique_json(data)
        meters = guard.ReadMeters()
        meters.buckets["metadata"]["cap_bytes"] = 2
        pin = write(self.base / "small.bin", b"abc")
        with self.assertRaises(guard.GuardError):
            guard.read_pin(pin, meters)
        self.assertEqual(meters.buckets["metadata"]["attempts"], 0)

    def test_symlink_hardlink_and_existing_output_reject(self):
        pin = write(self.base / "small.bin", b"abc")
        linked = self.base / "alias.bin"
        linked.symlink_to("small.bin")
        with self.assertRaises(guard.GuardError):
            guard.bounded_read(linked, 3, guard.ReadMeters())
        linked.unlink()
        os.link(pin["path"], linked)
        with self.assertRaises(guard.GuardError):
            guard.read_pin(pin, guard.ReadMeters())
        output = guard.fresh_output(self.protocol["output"])
        self.assertFalse(output.exists())
        output.mkdir()
        with self.assertRaises(guard.GuardError):
            guard.fresh_output(self.protocol["output"])

    def fake_distribution(self):
        site = self.base / "site"
        source = b"# tiny generated fake source; never imported\n"
        bytecode = b"fake-bytecode-is-never-loaded"
        py = write(site / "numpy/__init__.py", source)
        pyc = write(site / "numpy/__pycache__/__init__.cpython-311.pyc", bytecode)
        pyc["path"] = "numpy/__pycache__/__init__.cpython-311.pyc"
        stream = io.StringIO()
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["numpy/__init__.py", "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(source).digest()).decode().rstrip("="), len(source)])
        writer.writerow([pyc["path"], "", ""])
        writer.writerow(["numpy-2.4.6.dist-info/RECORD", "", ""])
        record = write(site / "numpy-2.4.6.dist-info/RECORD", stream.getvalue())
        return {"numpy": {"site_packages": str(site), "record": record, "pyc_pins": [pyc],
                           "record_rows": 3, "hashed_member_count": 1,
                           "hashed_member_bytes": len(source), "pyc_member_count": 1,
                           "pyc_member_bytes": len(bytecode), "complete_internal_inventory_count": 3}}

    def test_complete_record_and_bytecode_verification_counts(self):
        spec = self.fake_distribution()
        meters = guard.ReadMeters()
        counts = guard.verify_distribution(spec, meters)
        self.assertEqual(counts["pyc_member_count"], 1)
        self.assertEqual(meters.buckets["runtime"]["attempts"], 3)
        self.assertEqual(meters.buckets["metadata"]["attempts"], 0)
        self.assertNotIn("numpy", sys.modules)

    def test_extra_package_member_and_bytecode_tamper_reject(self):
        spec = self.fake_distribution()
        site = Path(spec["numpy"]["site_packages"])
        extra = site / "numpy/extra.py"
        write(extra, b"# injected\n")
        with self.assertRaises(guard.GuardError):
            guard.verify_distribution(spec, guard.ReadMeters())
        extra.unlink()
        write(site / spec["numpy"]["pyc_pins"][0]["path"], b"fake-bytecode-is-never-LoAded")
        with self.assertRaises(guard.GuardError):
            guard.verify_distribution(spec, guard.ReadMeters())

    def test_record_path_escape_and_duplicate_member_reject(self):
        spec = self.fake_distribution()
        numpy = spec["numpy"]
        rows = list(csv.reader(io.StringIO(Path(numpy["record"]["path"]).read_text())))
        for bad in (rows + [rows[0]], [["../../escape.py", "", ""]]):
            with self.assertRaises(guard.GuardError):
                guard.record_inventory(numpy["site_packages"], bad, numpy["pyc_pins"])

    def test_unadmitted_numpy_activation_cannot_import(self):
        admission = guard.Admission(self.protocol, self.path, self.sha, guard.ReadMeters(),
                                    guard.time.monotonic(), {"numpy": {}}, {}, {})
        with self.assertRaises(guard.GuardError):
            admission.activate_numpy()
        self.assertNotIn("numpy", sys.modules)
        self.assertFalse(admission.output_path.exists())

    def test_output_recheck_refuses_missing_pid_without_retry(self):
        self.ledger["native_runs"][0].pop("child_pid")
        write(Path(self.protocol["resource_ledger"]), json.dumps(self.ledger))
        admission = guard.Admission(self.protocol, self.path, self.sha, guard.ReadMeters(),
                                    guard.time.monotonic(), {}, {}, {})
        with patch.object(guard.os, "getppid", return_value=54321):
            with self.assertRaises(guard.GuardError):
                admission.create_output()
        self.assertEqual(admission.meters.buckets["metadata"]["attempts"], 1)
        self.assertFalse(admission.output_path.exists())

    def test_bootstrap_rejects_fabricated_authority_before_any_output(self):
        self.protocol.update(schema="temporal026-full-fixed-control-protocol/v1", limits=guard.LIMITS)
        pin = write(self.path, json.dumps(self.protocol))
        with patch.object(guard, "apply_limits", return_value=guard.time.monotonic()):
            with self.assertRaisesRegex(guard.GuardError, "authoritative coordinator ledger") as caught:
                guard.bootstrap(str(self.path), pin["sha256"])
        snapshot = caught.exception.guard_read_meters["logical_reads"]["metadata"]
        self.assertEqual(snapshot["attempts"], 1)
        self.assertEqual(snapshot["reserved_attempt_bytes"], 256 * 1024 + 1)
        self.assertEqual(snapshot["returned_bytes"], pin["bytes"])
        self.assertFalse(Path(self.protocol["output"]["path"]).exists())

    def test_poll_cannot_accept_readiness_after_deadline(self):
        write(Path(self.protocol["resource_ledger"]), json.dumps(self.ledger))
        clock = iter((0.0, 0.0, 1.001))
        meters = guard.ReadMeters()
        with self.assertRaisesRegex(guard.GuardError, "registration deadline"):
            guard.await_ledger(self.protocol, self.path, self.sha, meters,
                               monotonic=lambda: next(clock), sleep=lambda _: self.fail("unexpected wait"),
                               parent_pid=54321)
        self.assertEqual(meters.buckets["metadata"]["attempts"], 1)

    def test_mocked_process_limits_are_set_without_numpy(self):
        flags = SimpleNamespace(isolated=1, no_site=1, dont_write_bytecode=1)
        with patch.object(guard.sys, "flags", flags), \
             patch.dict(guard.os.environ, {k: "1" for k in guard.THREAD_ENV}), \
             patch.object(guard.resource, "getrlimit", return_value=(guard.resource.RLIM_INFINITY,) * 2), \
             patch.object(guard.resource, "setrlimit") as setlimit, \
             patch.object(guard.signal, "signal") as setsignal, \
             patch.object(guard.signal, "setitimer") as settime:
            guard.apply_limits()
            setlimit.assert_any_call(guard.resource.RLIMIT_CPU, (840, 850))
            setlimit.assert_any_call(guard.resource.RLIMIT_CORE, (0, 0))
            settime.assert_called_once_with(guard.signal.ITIMER_REAL, 900)
            self.assertEqual(setsignal.call_count, 4)
        self.assertNotIn("numpy", sys.modules)

    def test_mocked_process_rejects_flags_and_thread_environment(self):
        with patch.object(guard.resource, "setrlimit") as setlimit:
            for flag in ("isolated", "no_site", "dont_write_bytecode"):
                flags = dict(isolated=1, no_site=1, dont_write_bytecode=1)
                flags[flag] = 0
                with patch.object(guard.sys, "flags", SimpleNamespace(**flags)):
                    with self.subTest(flag=flag), self.assertRaises(guard.GuardError):
                        guard.apply_limits()
            with patch.dict(guard.os.environ, {"OMP_NUM_THREADS": "2"}):
                with self.assertRaises(guard.GuardError):
                    guard.apply_limits()
            setlimit.assert_not_called()

    def test_fixture_root_override_is_explicit_and_canonical(self):
        selected = self.base / "fresh-attempt"
        self.assertEqual(choose_fixture_root({"TEMPORAL_GUARD_FIXTURE_ROOT": str(selected)}), selected)
        self.assertEqual(choose_fixture_root({}), HERE / "generated_guard_controls_v4")
        self.assertFalse(selected.exists())
        with self.assertRaises(guard.GuardError):
            choose_fixture_root({"TEMPORAL_GUARD_FIXTURE_ROOT": "relative-attempt"})
        with self.assertRaises(FileExistsError):
            ROOT.mkdir()


if __name__ == "__main__":
    try:
        program = unittest.main(verbosity=2, exit=False)
    finally:
        print("GENERATED_FIXTURE_WRITES=" + json.dumps(WRITES, sort_keys=True))
        print("NO_NUMPY_IMPORT=" + str("numpy" not in sys.modules))
    sys.exit(0 if program.result.wasSuccessful() else 1)
