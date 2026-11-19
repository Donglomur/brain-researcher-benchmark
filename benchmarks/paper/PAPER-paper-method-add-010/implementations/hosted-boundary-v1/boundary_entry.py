"""Finite generated MEG boundary qualification using the existing Provider.

No production-data admission, scientific scoring, injected executor or retry.
The run receipt is provisional until the separate verify command observes exit
and exact current ownership closure. Native execution is not implied by source.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import signal
import stat
import sys
import time
import types
import uuid

SCHEDULE = (("A", 0), ("B", 0), ("A", 4), ("B", 4))
IMAGE = "sha256:cf2dad23925ed51a00735f57606b2998aedf4705a1634cb9ae1053b5c145d5ba"
PULL = "docker.io/library/python@sha256:e8c69d86735f6df3efa06b324694fe51f0422785f83a3bd463052636c2421944"
KINDS = ("constant", "probe")
transport = boundary_audit = boundary_fixtures = engineering_probe = generic_contract = None
_SOURCE_HANDLE = None
_CALLER_READ_RESERVED = 0


def require(value, message):
    if not value:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def pin(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def decoded(raw):
    def pairs(rows):
        out = {}
        for key, value in rows:
            require(key not in out, "duplicate JSON key")
            out[key] = value
        return out
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: require(False, "nonfinite JSON"))


def canonical_path(value):
    path = Path(value)
    require(path.is_absolute() and ".." not in path.parts, "absolute canonical path")
    require(not any(p.is_symlink() for p in (path, *path.parents)), "no path aliases")
    return path


def read_file(path, cap, expected=None, allow_empty=False):
    global _CALLER_READ_RESERVED
    path = canonical_path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        first = os.fstat(fd)
        require(stat.S_ISREG(first.st_mode) and first.st_nlink == 1
                and (0 if allow_empty else 1) <= first.st_size <= cap,
                "bounded ordinary single-link input")
        _CALLER_READ_RESERVED += first.st_size + 1
        require(_CALLER_READ_RESERVED <= 16777216, "caller cumulative16MiB read reservation")
        if expected is not None:
            require(first.st_size == expected["bytes"], "selected input extent")
        chunks, count = [], 0
        while count <= first.st_size:
            data = os.read(fd, min(65536, first.st_size + 1 - count))
            if not data:
                break
            chunks.append(data)
            count += len(data)
        stamp = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size,
                           s.st_mtime_ns, s.st_ctime_ns)
        require(stamp(first) == stamp(os.fstat(fd)) == stamp(path.lstat()), "stable input")
        body = b"".join(chunks)
        require(len(body) == first.st_size, "complete bounded input")
        if expected is not None:
            require(pin(body) == expected, "selected input identity")
        return body
    finally:
        os.close(fd)


class Evidence:
    """Only this caller's finite journal and reports; Provider meters are separate."""
    def __init__(self, root, deadline, cap=16777216):
        self.root, self.deadline, self.cap = canonical_path(root), deadline, cap
        self.reserved = 0
        self.journal_bytes = 0
        self.events = 0

    def reserve(self, size):
        require(time.monotonic() < self.deadline, "original caller deadline")
        require(type(size) is int and size >= 0 and self.reserved + size <= self.cap,
                "caller evidence cumulative write ceiling")
        self.reserved += size

    def write(self, relative, document):
        raw = encoded(document)
        self.reserve(len(raw))
        path = canonical_path(self.root / relative)
        require(path.is_relative_to(self.root), "owned evidence destination")
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            at = 0
            while at < len(raw):
                count = os.write(fd, memoryview(raw)[at:])
                require(count > 0, "complete evidence write")
                at += count
            os.fsync(fd)
        finally:
            os.close(fd)
        return {"path": str(path), **pin(raw)}

    def publish(self, event, body):
        require(type(event) is str and len(event) <= 96, "bounded event identity")
        raw = encoded({"index": self.events, "event": event, "body": body})
        require(len(raw) <= 262144 and self.journal_bytes + len(raw) <= 8388608,
                "bounded journal line/total")
        self.reserve(len(raw))
        path = self.root / "JOURNAL.jsonl"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
        try:
            mode = os.fstat(fd)
            require(stat.S_ISREG(mode.st_mode) and mode.st_nlink == 1
                    and mode.st_size == self.journal_bytes, "owned append-only journal")
            at = 0
            while at < len(raw):
                count = os.write(fd, memoryview(raw)[at:])
                require(count > 0, "complete journal write")
                at += count
            os.fsync(fd)
        finally:
            os.close(fd)
        self.journal_bytes += len(raw)
        self.events += 1


def fresh_directory(path):
    path = canonical_path(path)
    require(path.parent.is_dir(), "existing owned parent")
    path.mkdir(mode=0o700)
    require(stat.S_IMODE(path.stat().st_mode) == 0o700, "private fresh directory")
    return path


def validate_binding(binding):
    fields = {"schema", "source_manifest", "image", "immutable_pull_reference", "docker_binary",
              "docker_socket", "phase_resources", "operation_seconds", "verify_seconds",
              "transport_read_bytes", "transport_write_bytes", "audit_read_bytes",
              "audit_write_bytes", "observer_read_bytes", "observer_write_bytes"}
    require(type(binding) is dict and set(binding) == fields, "exact boundary binding")
    require(binding["schema"] == "meg-hosted-boundary-binding/v1", "boundary binding schema")
    descriptor = binding["source_manifest"]
    require(type(descriptor) is dict and set(descriptor) == {"bytes", "sha256"}
            and type(descriptor["bytes"]) is int and 0 < descriptor["bytes"] <= 262144
            and type(descriptor["sha256"]) is str
            and re.fullmatch(r"[0-9a-f]{64}", descriptor["sha256"]), "selected paired manifest pin")
    require(binding["image"] == IMAGE and binding["immutable_pull_reference"] == PULL,
            "selected official runtime identity")
    for key in fields - {"schema", "source_manifest", "image", "immutable_pull_reference",
                         "docker_binary", "docker_socket", "phase_resources"}:
        require(type(binding[key]) is int and binding[key] > 0, "positive finite " + key)
    require(binding["operation_seconds"] <= 720 and binding["verify_seconds"] <= 180,
            "finite hosted active operation")
    require(binding["transport_read_bytes"] <= 134217728
            and binding["transport_write_bytes"] <= 134217728,
            "per-campaign transport envelope")
    require(binding["audit_read_bytes"] <= 201326592 and binding["audit_write_bytes"] <= 16777216
            and binding["observer_read_bytes"] <= 33554432
            and binding["observer_write_bytes"] <= 16777216, "finite audit/observer envelope")
    require(2 * binding["audit_read_bytes"] + 2 * binding["transport_read_bytes"]
            + binding["observer_read_bytes"] + 33554432 + 2097152 <= 536870912,
            "run and verification inside512MiB named-read envelope")
    for key in ("docker_binary", "docker_socket"):
        canonical_path(binding[key])
    phase = binding["phase_resources"]
    phase_keys = {"setup_seconds", "producer_seconds", "capture_seconds", "cleanup_seconds",
                  "memory_bytes", "cpu_nanos", "pids", "scratch_bytes", "max_files",
                  "max_directories", "max_file_bytes", "max_output_bytes", "manifest_bytes",
                  "max_cli_calls", "max_cli_bytes", "inventory_bytes", "source_read_bytes", "host_write_bytes"}
    require(type(phase) is dict and set(phase) == phase_keys
            and all(type(v) is int and v > 0 for v in phase.values()),
            "positive typed phase resource values")
    require(134217728 <= phase["memory_bytes"] <= 268435456 and phase["cpu_nanos"] == 1000000000
            and phase["pids"] <= 64 and phase["scratch_bytes"] <= 1048576
            and phase["max_files"] == 2 and phase["max_directories"] == 1
            and phase["max_file_bytes"] <= 32768 and phase["max_output_bytes"] <= 65536
            and phase["manifest_bytes"] <= 4096 and phase["max_cli_calls"] <= 96
            and phase["max_cli_bytes"] <= 2097152 and phase["inventory_bytes"] <= 131072
            and phase["source_read_bytes"] <= 8388608 and phase["host_write_bytes"] <= 8388608,
            "selected small engineering phase envelope")
    require(8 * sum(phase[k] for k in ("setup_seconds", "producer_seconds", "capture_seconds",
                                      "cleanup_seconds")) + 120 < binding["operation_seconds"],
            "all eight phase ceilings plus final reserve inside original clock")
    require(binding["transport_read_bytes"] > 4 * phase["source_read_bytes"]
            and binding["transport_write_bytes"] > 4 * phase["host_write_bytes"],
            "four phases plus adapter/evidence headroom per fresh transport")
    return binding


def source_module(name, path, body):
    module = types.ModuleType(name)
    module.__file__, module.__package__ = str(path), ""
    sys.modules[name] = module
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


def load_sources(source_root, app_root, manifest_sha256):
    global transport, boundary_audit, boundary_fixtures, engineering_probe, generic_contract, _SOURCE_HANDLE
    source_root, app_root = canonical_path(source_root), canonical_path(app_root)
    raw = read_file(app_root / "SOURCE_MANIFEST.json", 262144)
    require(hashlib.sha256(raw).hexdigest() == manifest_sha256, "externally selected application manifest")
    manifest = decoded(raw)
    require(set(manifest) == {"schema", "application", "paired_dependencies", "sibling_dependencies"}
            and manifest["schema"] == "meg-hosted-boundary-sources/v1", "application source closure")
    require(set(manifest["application"]) >= {"boundary_entry.py", "boundary_fixtures.py",
            "engineering_probe.py", "boundary_audit.py", "AUDIT_POLICY.json", "RUNTIME_IMAGE.json",
            "BOUNDARY_BINDING.json"}, "complete executable application closure")
    bodies = {}
    for relative, expected in manifest["application"].items():
        require(type(relative) is str and relative not in (".", "..")
                and re.fullmatch(r"[A-Za-z0-9_.-]+", relative), "flat application source")
        bodies[relative] = read_file(app_root / relative, 1048576, expected)
    for relative, expected in manifest["paired_dependencies"].items():
        require(type(relative) is str and ".." not in Path(relative).parts
                and not Path(relative).is_absolute(), "relative paired source")
        bodies["paired/" + relative] = read_file(source_root / relative, 1048576, expected)
    for relative, expected in manifest["sibling_dependencies"].items():
        require(type(relative) is str and ".." not in Path(relative).parts
                and not Path(relative).is_absolute(), "relative sibling source")
        read_file(source_root.parent / relative, 1048576, expected)
    # Compile captured authenticated bytes. No unchecked task imports/pyc files.
    sys.dont_write_bytecode = True
    for name in ("storage", "dependencies", "contract", "generic_contract", "transport"):
        module = source_module(name, source_root / (name + ".py"), bodies["paired/" + name + ".py"])
        if name in ("generic_contract", "transport"):
            globals()[name] = module
    for name in ("engineering_probe", "boundary_fixtures", "boundary_audit"):
        globals()[name] = source_module(name, app_root / (name + ".py"), bodies[name + ".py"])
    _SOURCE_HANDLE = {"application_manifest": pin(raw), "source_root": str(source_root),
                      "app_root": str(app_root), "registry_pin": manifest["application"]["RUNTIME_IMAGE.json"],
                      "binding_pin": manifest["application"]["BOUNDARY_BINDING.json"]}
    return _SOURCE_HANDLE


def _audit_expected(source_root, binding, fixture, not_before, attempt_id):
    return {"schema": "meg-boundary-audit-expected/v1", "attempt_id": attempt_id,
            "source_manifest": binding["source_manifest"],
            "registry_metadata": {"path": str(Path(_SOURCE_HANDLE["app_root"]) / "RUNTIME_IMAGE.json"),
                                  "pin": _SOURCE_HANDLE["registry_pin"]},
            "docker_binary": binding["docker_binary"], "docker_socket": binding["docker_socket"],
            "image": binding["image"], "immutable_pull_reference": binding["immutable_pull_reference"],
            "fixture_sha256": hashlib.sha256(boundary_audit.encoded(fixture["audit_view"])).hexdigest(),
            "fixture_not_before_unix": not_before,
            "policy_sha256": boundary_audit.AUDIT_POLICY_PIN["sha256"]}


def execute_campaign(kind, fixture, binding, audit, campaign_root, origin, deadline, evidence):
    require(kind in KINDS, "named engineering campaign")
    campaign_root = fresh_directory(campaign_root)
    exposure_root = fresh_directory(campaign_root / "exposures")
    control_root = fresh_directory(campaign_root / "control")
    quarantine_root = fresh_directory(campaign_root / "quarantine")
    selected = fixture["campaigns"][kind]
    campaign_id = "meg-" + kind + "-" + fixture["nonce"][:16]
    approvals, exposure_pins = {}, {}
    for role, fold in SCHEDULE:
        mounts = selected["mounts"][str(fold)][role]
        approval = boundary_audit.approve_exposure(audit, role, mounts, selected["program_pin"])
        exposure = transport.make_exposure(role, binding["image"], selected["program_pin"], mounts,
                                          **approval)
        raw = transport._vendor().engine.encoded(exposure)
        destination = exposure_root / (role + str(fold) + ".json")
        # The caller's evidence meter reserves the exact source approval body.
        evidence.reserve(len(raw))
        fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            at = 0
            while at < len(raw):
                count = os.write(fd, memoryview(raw)[at:])
                require(count > 0, "complete approval write")
                at += count
            os.fsync(fd)
        finally:
            os.close(fd)
        descriptor = pin(raw)
        approvals[descriptor["sha256"]] = str(destination)
        exposure_pins[(role, fold)] = descriptor
    owned = transport.OwnedTransport(campaign_id=campaign_id, image=binding["image"],
        frozen_programs=selected["frozen_programs"], control_root=control_root,
        quarantine_root=quarantine_root, docker_binary=binding["docker_binary"],
        docker_socket=binding["docker_socket"], trusted_exposures=approvals,
        source_read_limit=binding["transport_read_bytes"], host_write_limit=binding["transport_write_bytes"],
        origin=origin, original_deadline=deadline)
    phases, owners = [], []
    for role, fold in SCHEDULE:
        require(time.monotonic() < deadline - 60, "same-clock final closure reserve")
        evidence.publish("PHASE-SELECTED", {"kind": kind, "role": role, "fold": fold,
                         "campaign_id": campaign_id, "original_deadline": deadline})
        result = owned.execute_fold(role, fold, selected["mounts"][str(fold)][role],
                     exposure_pins[(role, fold)], binding["phase_resources"], deadline, evidence.publish)
        context_info = fixture["contexts"][str(fold)]
        context = decoded(read_file(context_info["path"], 262144,
                                   {k: context_info[k] for k in ("bytes", "sha256")}))
        response = decoded(result["result_bytes"])
        if kind == "constant":
            generic_contract.validate_prediction(response, context, "reproduction")
            require(all(type(value) in (int, float) and value == 0.5
                        for value in response["probabilities"].values()), "unchanged constant response")
            check = {"configuration_response_valid": True, "scientific_evaluation": False}
        else:
            check = engineering_probe.validate_probe_result(response, phase_id=result["phase_id"],
                role=role, fold=fold, context_sha256=context_info["context_sha256"])
            require(check["qualified"] is True, "designated engineering probe failed")
        receipt = result["receipt"]
        ownership_path = campaign_root / "control" / result["phase_id"] / "OWNERSHIP.json"
        ownership_raw = read_file(ownership_path, 262144, receipt["ownership_pin"])
        phase_owners = boundary_audit.owners_from_ownership(decoded(ownership_raw))
        require(not ({row["name"] for row in owners} & {row["name"] for row in phase_owners}),
                "fresh resource identities across every phase")
        owners.extend(phase_owners)
        phases.append({"kind": kind, "role": role, "fold": fold, "phase_id": result["phase_id"],
            "context_pin": {k: context_info[k] for k in ("bytes", "sha256")},
            "request_pin": result["request_pin"], "receipt_pin": result["receipt_pin"],
            "result_pin": result["result_pin"], "ownership_pin": receipt["ownership_pin"],
            "ownership_path": str(ownership_path), "receipt_path": str(ownership_path.parent / "RECEIPT.json"),
            "result_path": str(campaign_root / "quarantine" / result["phase_id"] / "RESULT.json"),
            "checks": check, "resource_owners": phase_owners,
            "transport_counters": result["final_transport_counters"],
            "adapter_read_reserved_bytes": result["adapter_read_reserved_bytes"]})
        evidence.publish("PHASE-ACCEPTED", phases[-1])
    # Deliberately no complete_for_grading(): four is not twenty.
    return {"kind": kind, "campaign_id": campaign_id, "phases": phases,
            "resource_owners": owners, "complete_ten_fold_campaign": False}


def run_qualification(source_root, output_root, binding):
    require(_SOURCE_HANDLE is not None, "authenticated executable source closure")
    validate_binding(binding)
    require(platform.system() == "Linux", "actual Linux operator required")
    output_root = fresh_directory(output_root)
    origin = time.monotonic()
    deadline = origin + binding["operation_seconds"]
    evidence = Evidence(output_root, deadline)
    expected, fixture, audit = None, None, None
    try:
        engine = transport._vendor().engine
        identity_reads = [0]
        def reserve_identity(n):
            require(identity_reads[0] + n <= 32768, "bounded initial identity reservation")
        def read_identity(n):
            identity_reads[0] += n
            require(identity_reads[0] <= 32768, "bounded initial identity bytes")
        worker_identity = engine.process_identity(os.getpid(), deadline, read_identity, reserve_identity)
        evidence.write("WORKER_IDENTITY.json", worker_identity)
        not_before = time.time()
        nonce = uuid.uuid4().hex
        fixture = boundary_fixtures.build_fixture(source_root, output_root / "fixtures",
                     Path(_SOURCE_HANDLE["app_root"]) / "engineering_probe.py", nonce)
        fixture_receipt = evidence.write("FIXTURE_BINDING.json", fixture)
        expected = _audit_expected(source_root, binding, fixture, not_before, "meg-" + nonce)
        expected_receipt = evidence.write("EXPECTED_AUDIT.json", expected)
        evidence.write("CUSTODY.json", {"fixture_binding": fixture_receipt,
            "expected_audit": expected_receipt, "worker_identity": worker_identity,
            "origin": origin, "original_deadline": deadline})
        audit = boundary_audit.audit_environment(source_root, output_root / "audit", expected,
            fixture["audit_view"], deadline, binding["audit_read_bytes"], binding["audit_write_bytes"],
            evidence.publish)
        campaigns_root = fresh_directory(output_root / "campaigns")
        campaigns = [execute_campaign(kind, fixture, binding, audit, campaigns_root / kind,
                      origin, deadline, evidence) for kind in KINDS]
        owners = [row for campaign in campaigns for row in campaign["resource_owners"]]
        require(len(owners) == 24 and len({row["name"] for row in owners}) == 24,
                "two fresh four-phase namespaces and24 unique resources")
        read_file(fixture["audit_view"]["private"]["sentinel"]["path"], 4096,
                  fixture["audit_view"]["private"]["sentinel"]["pin"])
        provisional = {"schema": "meg-boundary-provisional/v1", "status": "awaiting_external_exit_and_closure",
            "source": _SOURCE_HANDLE, "binding": binding, "worker_identity": worker_identity,
            "origin": origin, "original_deadline": deadline, "finished": time.monotonic(),
            "fixture_binding": fixture_receipt, "expected_audit": expected_receipt,
            "audit_pin": audit["audit_pin"],
            "audit_path": audit["audit_path"], "docker_context": audit["docker_context"],
            "campaigns": campaigns, "resource_owners": owners,
            "configuration_phase_count": 4, "probe_phase_count": 4,
            "production_authentic_admission": False, "scientific_evaluation": False,
            "caller_evidence_reserved_bytes_before_report": evidence.reserved}
        require(provisional["finished"] < deadline - 30, "unrefreshed final observation reserve")
        return evidence.write("PROVISIONAL.json", provisional)
    except BaseException as error:
        failure = {"schema": "meg-boundary-worker-failure/v1", "status": "failed",
            "error_type": type(error).__name__, "message": str(error)[:2048],
            "cleanup_errors": getattr(error, "cleanup_errors", []), "origin": origin,
            "original_deadline": deadline, "automatic_retry": False,
            "closure_claimed": False, "scientific_evaluation": False}
        try:
            evidence.write("FAILURE.json", failure)
        except BaseException as publication_error:
            error.add_note("Failure receipt unavailable: " + type(publication_error).__name__
                           + ": " + str(publication_error)[:512])
        raise


def journal_rows(root):
    raw = read_file(Path(root) / "JOURNAL.jsonl", 8388608)
    lines = raw.splitlines()
    require(0 < len(lines) <= 10000 and raw.endswith(b"\n"), "complete bounded journal")
    rows = []
    for index, line in enumerate(lines):
        require(len(line) <= 262144, "bounded journal event")
        row = decoded(line)
        require(type(row) is dict and set(row) == {"index", "event", "body"}
                and row["index"] == index and type(row["event"]) is str, "ordered exact journal")
        rows.append(row)
    return rows


def observe_process_absence(worker_identity, rows):
    """Read-only independent post-exit observations; never signal numeric PIDs."""
    identities = [worker_identity]
    for row in rows:
        if row["event"] == "CLI-CHILD":
            body = row["body"]
            require(type(body) is dict, "typed CLI child wrapper")
            if set(body) == {"pin", "value"}:
                child = body["value"]
                require(body["pin"] == pin(boundary_audit.encoded({"schema": "meg-boundary-audit-journal/v1",
                        "event": row["event"], "value": child})), "audit child journal pin")
            else:
                require(set(body) == {"record", "pin"}, "exact Provider child wrapper")
                record = body["record"]
                require(type(record) is dict and set(record) == {"schema", "phase_id", "request_sha256",
                        "index", "event", "value"} and record["schema"] == "osl_transport_journal_v1"
                        and record["event"] == row["event"], "authenticated Provider journal event")
                require(body["pin"] == pin(transport._vendor().engine.encoded(record)), "Provider child journal pin")
                child = record["value"]
            require(type(child) is dict and set(child) == {"index", "phase", "pid", "pgid", "original_end",
                    "independent_group", "process_identity", "docker_exec_still_gated"}
                    and child["independent_group"] is True and child["docker_exec_still_gated"] is True
                    and type(child["pid"]) is int and type(child["pgid"]) is int
                    and child["pid"] == child["pgid"] == child["process_identity"]["pid"],
                    "exact gated independently owned CLI process")
            identities.append(child["process_identity"])
    require(len(identities) <= 1000, "bounded known host process set")
    result = []
    seen = set()
    for token in identities:
        require(type(token) is dict and set(token) == {"schema", "pid", "pgid", "session_id", "uid",
                "start_time_ticks", "boot_id"} and token.get("schema") == "osl_linux_process_identity_v1"
                and type(token.get("pid")) is int and token["pid"] > 1
                and type(token["uid"]) is int and type(token["start_time_ticks"]) is int
                and type(token["boot_id"]) is str
                and token.get("pgid") == token["pid"] == token.get("session_id"),
                "exact owned independent host session")
        key = (token["pid"], token.get("start_time_ticks"), token.get("boot_id"))
        if key in seen:
            continue
        seen.add(key)
        require(token["pid"] != os.getpid(), "external observer differs from worker")
        try:
            os.kill(token["pid"], 0)
        except ProcessLookupError:
            pid_absent = True
        else:
            pid_absent = False
        try:
            os.killpg(token["pgid"], 0)
        except ProcessLookupError:
            group_absent = True
        else:
            group_absent = False
        result.append({"process_identity": token, "pid_absence_observed": pid_absent,
                       "group_absence_observed": group_absent})
        require(pid_absent and group_absent, "old host PID/group is absent; reused/unknown is not success")
    return result


def _receipt_owners(source_root, output_root, provisional, fixture, deadline):
    """Revalidate saved strict receipts and result identities without scientific grading."""
    owners = []
    require(len(provisional["campaigns"]) == 2, "two completed engineering campaigns")
    ids = set()
    for campaign, kind in zip(provisional["campaigns"], KINDS):
        require(campaign["kind"] == kind and len(campaign["phases"]) == 4,
                "two named four-phase campaigns")
        require(campaign["campaign_id"] not in ids, "fresh campaign namespace")
        ids.add(campaign["campaign_id"])
        for saved, (role, fold) in zip(campaign["phases"], SCHEDULE):
            phase = transport.phase_id(campaign["campaign_id"], role, fold)
            require((saved["role"], saved["fold"], saved["phase_id"]) == (role, fold, phase),
                    "exact selected phase order")
            phase_root = output_root / "campaigns" / kind / "control" / phase
            require(saved["receipt_path"] == str(phase_root / "RECEIPT.json")
                    and saved["ownership_path"] == str(phase_root / "OWNERSHIP.json"),
                    "exact saved private paths")
            receipt = decoded(read_file(saved["receipt_path"], 1048576, saved["receipt_pin"]))
            request = decoded(read_file(phase_root / "REQUEST.json", 262144, saved["request_pin"]))
            result_pin = transport.validate_closed_receipt(receipt, request,
                fixture["campaigns"][kind]["mounts"][str(fold)][role], provisional["original_deadline"])
            require(result_pin == saved["result_pin"], "same captured result pin")
            ownership = decoded(read_file(saved["ownership_path"], 262144, saved["ownership_pin"]))
            actual_owners = boundary_audit.owners_from_ownership(ownership)
            require(actual_owners == saved["resource_owners"], "exact acknowledged ownership triples")
            owners.extend(actual_owners)
            expected_result_path = output_root / "campaigns" / kind / "quarantine" / phase / "RESULT.json"
            require(saved["result_path"] == str(expected_result_path), "exact result location")
            body = decoded(read_file(expected_result_path, 32768, result_pin))
            ctxinfo = fixture["contexts"][str(fold)]
            context = decoded(read_file(ctxinfo["path"], 262144,
                                       {k: ctxinfo[k] for k in ("bytes", "sha256")}))
            if kind == "constant":
                generic_contract.validate_prediction(body, context, "reproduction")
                require(all(type(v) in (int, float) and v == 0.5 for v in body["probabilities"].values()),
                        "saved constant response")
            else:
                checked = engineering_probe.validate_probe_result(body, phase_id=phase, role=role, fold=fold,
                    context_sha256=ctxinfo["context_sha256"])
                require(checked["qualified"] is True and checked == saved["checks"], "saved probe observations")
            require(time.monotonic() < deadline, "same original final observation clock")
    require(len(owners) == 24 and len({r["name"] for r in owners}) == 24, "24 unique acknowledged resources")
    require(owners == provisional["resource_owners"], "complete saved resource census")
    return owners


def audit_continuity(provisional, current_audit, output_root):
    require(current_audit["docker_context"] == provisional["docker_context"],
            "same observed daemon, CLI/socket and image for final ownership closure")
    original_path = Path(provisional["audit_path"])
    require(original_path == Path(output_root) / "audit" / "AUDIT.json", "exact original audit location")
    original = decoded(read_file(original_path, 524288, provisional["audit_pin"]))
    initial = decoded(read_file(original_path.parent / "OBSERVATIONS.json", 524288, original["observations"]))
    current = decoded(read_file(Path(current_audit["audit_path"]).parent / "OBSERVATIONS.json",
                               524288, current_audit["observations_pin"]))
    require(initial["host"]["boot_id"] == current["host"]["boot_id"]
            == provisional["worker_identity"]["boot_id"], "same boot for original clock and owned process tokens")
    return {"same_daemon": True, "same_host_boot": True, "initial_observations_pin": original["observations"],
            "current_observations_pin": current_audit["observations_pin"]}


def capture_observation(capture_root):
    shell = decoded(read_file(capture_root / "RUN_EXIT.json", 4096))
    require(type(shell) is dict and set(shell) == {"schema", "exit_code"}
            and shell["schema"] == "meg-boundary-shell-exit/v1"
            and type(shell["exit_code"]) is int, "external shell wait receipt")
    capture = decoded(read_file(capture_root / "RUN_CAPTURE.json", 4096))
    require(type(capture) is dict and set(capture) == {"schema", "stdout_bytes", "stderr_bytes",
            "stdout_eof", "stderr_eof", "collectors_exit_codes"}
            and capture["schema"] == "meg-boundary-shell-capture/v1", "external capture receipt")
    stdout = read_file(capture_root / "RUN_STDOUT.json", 4097, allow_empty=True)
    stderr = read_file(capture_root / "RUN_STDERR.log", 8193, allow_empty=True)
    require(type(capture["stdout_bytes"]) is int and capture["stdout_bytes"] == len(stdout) <= 4096
            and type(capture["stderr_bytes"]) is int and capture["stderr_bytes"] == len(stderr) <= 8192
            and capture["stdout_eof"] is True and capture["stderr_eof"] is True
            and type(capture["collectors_exit_codes"]) is list
            and len(capture["collectors_exit_codes"]) == 2
            and all(type(code) is int and code == 0 for code in capture["collectors_exit_codes"]),
            "bounded complete caller pipes")
    return shell, capture, stdout, stderr


def output_census(root):
    """Finite ordinary-file metadata census; no assertion about unobserved daemon storage."""
    rows, total, directory_count = [], 0, 0
    for parent, directories, files in os.walk(root, followlinks=False):
        directories.sort(); files.sort()
        directory_count += len(directories)
        require(len(rows) + directory_count + len(files) <= 4096, "bounded evidence tree")
        for name in directories:
            path = Path(parent) / name
            require(not path.is_symlink() and path.is_dir(), "ordinary evidence directories")
        for name in files:
            path = Path(parent) / name
            meta = path.lstat()
            require(stat.S_ISREG(meta.st_mode) and meta.st_nlink == 1, "ordinary evidence files")
            total += meta.st_size
            require(total <= 268435456, "256MiB retained evidence ceiling")
            rows.append({"path": str(path.relative_to(root)), "bytes": meta.st_size})
    return {"files": rows, "file_count": len(rows), "retained_bytes": total,
            "metadata_only": True, "excludes_reports_written_after_census": True}


def publish_public(evidence, status, binding, result_pin=None):
    return evidence.write("PUBLIC_RESULT.json", {"schema": "meg-hosted-boundary-public/v1",
        "status": status, "qualified": status == "qualified_for_selected_checks",
        "application_manifest": _SOURCE_HANDLE["application_manifest"],
        "paired_source_manifest": binding["source_manifest"], "image": binding["image"],
        "immutable_pull_reference": binding["immutable_pull_reference"], "operator_python": platform.python_version(),
        "result_pin": result_pin, "configuration_schedule": [[r, f] for r, f in SCHEDULE],
        "probe_schedule": [[r, f] for r, f in SCHEDULE],
        "identical_programme_across_roles_within_each_campaign": True,
        "checks": ["designated_private_sentinel_open_denial", "readonly_input_write_denial",
                   "reserved_address_network_policy_denial", "fresh_work_marker"],
        "scientific_evaluation": False, "production_authentic_admission": False,
        "full_coordinator_or_ten_fold_qualification": False,
        "universal_escape_or_image_filesystem_absence_claim": False})


def verify_failed(source_root, output_root, binding, shell, capture):
    """Observe known failed-prefix ownership; unknown creation is never converted to closure."""
    verification = fresh_directory(output_root / "verification")
    evidence = Evidence(verification, time.monotonic() + binding["verify_seconds"])
    report = {"schema": "meg-boundary-failed-operation-observation/v1", "status": "failed",
        "external_worker_exit": shell, "capture": capture, "qualified": False,
        "automatic_recovery": False, "unknown_creation_resolved": False,
        "production_authentic_admission": False, "scientific_evaluation": False}
    try:
        custody = decoded(read_file(output_root / "CUSTODY.json", 262144))
        deadline = min(custody["original_deadline"], evidence.deadline)
        rows = journal_rows(output_root)
        report["known_host_absence"] = observe_process_absence(custody["worker_identity"], rows)
        require(time.monotonic() < deadline, "original cutoff prevents further failed-prefix native observation")
        fb, eb = custody["fixture_binding"], custody["expected_audit"]
        fixture = decoded(read_file(fb["path"], 1048576, {k: fb[k] for k in ("bytes", "sha256")}))
        expected = decoded(read_file(eb["path"], 262144, {k: eb[k] for k in ("bytes", "sha256")}))
        audit = boundary_audit.audit_environment(source_root, verification / "audit", expected,
            fixture["audit_view"], deadline, binding["audit_read_bytes"], binding["audit_write_bytes"],
            evidence.publish)
        owners = []
        for kind in KINDS:
            campaign_id = "meg-" + kind + "-" + fixture["nonce"][:16]
            for role, fold in SCHEDULE:
                phase = transport.phase_id(campaign_id, role, fold)
                path = output_root / "campaigns" / kind / "control" / phase / "OWNERSHIP.json"
                if path.exists():
                    owners.extend(boundary_audit.owners_from_ownership(decoded(read_file(path, 262144))))
        report["known_resources"] = owners
        if owners:
            report["known_resource_observation"] = boundary_audit.observe_owned_resources(audit, owners,
                verification / "resources", deadline, binding["observer_read_bytes"],
                binding["observer_write_bytes"], evidence.publish)
        report["failed_campaign_closure_established"] = False
    except BaseException as error:
        report["observation_error"] = {"type": type(error).__name__, "message": str(error)[:2048]}
        report["failed_campaign_closure_established"] = False
    saved = evidence.write("FAILED_OPERATION.json", report)
    publish_public(evidence, "failed", binding, {k: saved[k] for k in ("bytes", "sha256")})
    raise ValueError("failed worker retained; exact known-prefix observations saved without qualification")


def verify_saved(source_root, output_root, binding):
    require(_SOURCE_HANDLE is not None and platform.system() == "Linux", "authenticated Linux observer")
    validate_binding(binding)
    output_root = canonical_path(output_root)
    capture_root = output_root.parent
    shell, capture, stdout, stderr = capture_observation(capture_root)
    if shell["exit_code"] != 0:
        return verify_failed(source_root, output_root, binding, shell, capture)
    require(not stderr, "successful selected caller has no unexplained stderr")
    returned = decoded(stdout)
    require(type(returned) is dict and set(returned) == {"path", "bytes", "sha256"}
            and returned["path"] == str(output_root / "PROVISIONAL.json"), "external stdout result pin")
    provisional = decoded(read_file(returned["path"], 1048576,
                                  {k: returned[k] for k in ("bytes", "sha256")}))
    require(provisional["schema"] == "meg-boundary-provisional/v1"
            and provisional["status"] == "awaiting_external_exit_and_closure"
            and provisional["binding"] == binding and provisional["source"] == _SOURCE_HANDLE,
            "same selected source/runtime and provisional operation")
    deadline = min(provisional["original_deadline"], time.monotonic() + binding["verify_seconds"])
    require(provisional["origin"] <= provisional["finished"] < deadline, "unrefreshed verification deadline")
    verification = fresh_directory(output_root / "verification")
    evidence = Evidence(verification, deadline)
    try:
        rows = journal_rows(output_root)
        host_absence = observe_process_absence(provisional["worker_identity"], rows)
        fb = provisional["fixture_binding"]
        require(fb["path"] == str(output_root / "FIXTURE_BINDING.json"), "exact frozen fixture record")
        fixture = decoded(read_file(fb["path"], 1048576, {k: fb[k] for k in ("bytes", "sha256")}))
        eb = provisional["expected_audit"]
        require(eb["path"] == str(output_root / "EXPECTED_AUDIT.json"), "exact expected audit location")
        expected = decoded(read_file(eb["path"], 262144, {k: eb[k] for k in ("bytes", "sha256")}))
        audit = boundary_audit.audit_environment(source_root, verification / "audit", expected,
            fixture["audit_view"], deadline, binding["audit_read_bytes"], binding["audit_write_bytes"],
            evidence.publish)
        continuity = audit_continuity(provisional, audit, output_root)
        owners = _receipt_owners(source_root, output_root, provisional, fixture, deadline)
        closure = boundary_audit.observe_owned_resources(audit, owners, verification / "resources", deadline,
            binding["observer_read_bytes"], binding["observer_write_bytes"], evidence.publish)
        require(closure["all_exact_owned_resources_absent"] is True, "current exact owned resource absence")
        census = evidence.write("OUTPUT_CENSUS.json", output_census(output_root))
        final = {"schema": "meg-hosted-boundary-result/v1", "status": "qualified_for_selected_checks",
            "source": _SOURCE_HANDLE, "binding": binding, "provisional_pin": pin(encoded(provisional)),
            "external_worker_exit": shell, "capture": capture, "host_process_absence": host_absence,
            "audit_continuity": continuity,
            "original_deadline": provisional["original_deadline"], "finished": time.monotonic(),
            "configuration_phases": 4, "probe_phases": 4, "resource_closure": closure,
            "verification_audit_pin": audit["audit_pin"], "output_census": census, "scientific_evaluation": False,
            "production_authentic_admission": False, "complete_ten_fold_campaign": False,
            "scope": "Exact selected image/operator: readonly role mounts and designated generated-sentinel,"
                     " input-write, reserved-address and fresh-work-state probes; no universal escape guarantee."}
        require(final["finished"] < deadline, "final receipt within original cutoff")
        saved = evidence.write("RESULT.json", final)
        publish_public(evidence, final["status"], binding, {k: saved[k] for k in ("bytes", "sha256")})
        return saved
    except BaseException as error:
        try:
            evidence.write("FAILURE.json", {"schema": "meg-boundary-verification-failure/v1", "status": "failed",
                "error_type": type(error).__name__, "message": str(error)[:2048],
                "original_deadline": provisional["original_deadline"], "qualified": False})
        except BaseException as publication_error:
            error.add_note("Verification failure publication unavailable: " + type(publication_error).__name__)
        try:
            publish_public(evidence, "failed", binding)
        except BaseException as publication_error:
            error.add_note("Public failure publication unavailable: " + type(publication_error).__name__)
        raise


def bootstrap_image(source_root, output_root, binding):
    """Future separately authorized fixed-image acquisition, using existing CLI ownership."""
    require(_SOURCE_HANDLE is not None and platform.system() == "Linux", "authenticated Linux bootstrap")
    validate_binding(binding)
    root = fresh_directory(output_root)
    deadline = time.monotonic() + 180
    evidence = Evidence(root, deadline, 4194304)
    vendor = transport._vendor()
    meter = vendor.bounds.Meter(4194304, 4194304, deadline)
    caps = {"bootstrap_pull": 16384, "bootstrap_image": 131072}
    docker = vendor.engine.Docker(binding["docker_binary"], binding["docker_socket"], max_calls=2,
        reply_budget=sum(caps.values()), phase_caps=caps, publish=evidence.publish,
        account_read=meter.read, reserve_read=meter.ensure_read)
    try:
        pulled = docker(["pull", "--quiet", "--platform", "linux/amd64", binding["immutable_pull_reference"]],
                        deadline - 10, "bootstrap_pull", caps["bootstrap_pull"])
        inspected = docker(["image", "inspect", binding["image"]], deadline,
                           "bootstrap_image", caps["bootstrap_image"])
        rows = decoded(inspected)
        require(type(rows) is list and len(rows) == 1 and rows[0]["Id"] == binding["image"]
                and rows[0]["Os"] == "linux" and rows[0]["Architecture"] == "amd64",
                "exact installed immutable image")
        require(type(rows[0]["Size"]) is int and rows[0]["Size"] <= 1073741824,
                "observed post-acquisition image size inside selected conservative daemon envelope")
        vendor.engine.validate_cli_records(docker.records, caps)
        return evidence.write("BOOTSTRAP.json", {"schema": "meg-boundary-image-bootstrap/v1", "status": "complete",
            "image": binding["image"], "pull_reference": binding["immutable_pull_reference"],
            "pull_stdout_pin": pin(pulled), "inspect_pin": pin(inspected), "image_inspect": rows[0],
            "cli_records": docker.records, "cli_reaped": docker.reaped,
            "observed_image_size": rows[0]["Size"], "hard_daemon_storage_bound": False,
            "role_boundary_qualified": False})
    except BaseException as error:
        try:
            evidence.write("FAILURE.json", {"schema": "meg-boundary-bootstrap-failure/v1", "status": "failed",
                "error_type": type(error).__name__, "message": str(error)[:2048],
                "cli_records": docker.records, "cli_reaped": docker.reaped,
                "daemon_cache_cleanup_or_absence_claimed": False})
        except BaseException as publication_error:
            error.add_note("Bootstrap failure publication unavailable: " + type(publication_error).__name__)
        raise


class BoundaryCancelled(BaseException):
    pass


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("bootstrap-image", "run", "verify"))
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--binding", required=True)
    parser.add_argument("--binding-sha256", required=True)
    parser.add_argument("--source-manifest-sha256", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    require(platform.python_version() == "3.11.18", "selected hosted CPython3.11.18 operator")
    app_root = Path(__file__).resolve().parent
    output = canonical_path(args.output)
    source = canonical_path(args.source_root)
    require(not output.is_relative_to(app_root) and not output.is_relative_to(source), "external fresh output")
    raw = read_file(args.binding, 65536)
    require(hashlib.sha256(raw).hexdigest() == args.binding_sha256, "externally selected binding")
    binding = validate_binding(decoded(raw))
    load_sources(source, app_root, args.source_manifest_sha256)
    require(pin(raw) == _SOURCE_HANDLE["binding_pin"], "binding belongs to selected application closure")
    # The worker is an independently identified session. Existing engine code
    # owns/signals each Docker CLI by pidfd; this entry never signals numeric groups.
    require(platform.system() == "Linux", "actual Linux entry")
    if os.getpgrp() != os.getpid() or os.getsid(0) != os.getpid():
        os.setsid()
    require(os.getpgrp() == os.getsid(0) == os.getpid(), "independent operator session")
    def cancelled(signum, frame):
        raise BoundaryCancelled("operator signal " + str(signum))
    signal.signal(signal.SIGTERM, cancelled)
    signal.signal(signal.SIGINT, cancelled)
    function = {"bootstrap-image": bootstrap_image, "run": run_qualification, "verify": verify_saved}[args.command]
    result = function(source, output, binding)
    raw = encoded(result)
    require(len(raw) <= 4096, "bounded caller stdout")
    require(os.write(1, raw) == len(raw), "complete caller stdout")


if __name__ == "__main__":
    try:
        main()
    except BaseException as error:
        message = encoded({"status": "failed", "error_type": type(error).__name__,
                           "message": str(error)[:2048], "notes": getattr(error, "__notes__", [])[:4]})
        if len(message) > 8192:
            message = b'{"status":"failed","error_type":"bounded-error-report"}\n'
        os.write(2, message)
        raise SystemExit(1)
