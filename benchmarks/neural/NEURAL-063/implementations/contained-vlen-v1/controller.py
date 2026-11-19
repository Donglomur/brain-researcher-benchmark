"""Portable fixed NEURAL-063 contained controller; external authority required.

No import-time operation. The shipped template cannot pass production admission.
This controller never installs, builds images, reads neural arrays on the host,
decodes opaque scientific JSON, or changes an original scientific function.
"""
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
import types
from urllib.parse import urlsplit

THREADS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS",
           "NUMEXPR_NUM_THREADS", "BLIS_NUM_THREADS", "POLARS_MAX_THREADS", "RAYON_NUM_THREADS")
NATIVE_CONTROLLER_PIN = (17596, "a99a83ae6638dbae205badf041230260d4d075dfc3b7e50a50c7bdb87293b761")
CAPTURE_PIN = (7749, "0a9274a1b08b00ee778143aa5ba35e4a3bf6b27dd6e8ea8838428b0652c0949f")
HELPER_PINS = {
    "bank": (31933, "661defbfd525f6ca2fea14cbc077808839b54dd263206008646611b2a95b4b9e"),
    "legacy": (12873, "ca63d4f2f07f9a72471d8ae29c11b853f4b3f52f2b1c1ac48125de985daec0b1"),
    "formats": (5123, "40a250f3742bfadd0af62750d5f8e538b016f26919592c47afb437ca5a108f35"),
}
ORIGINAL = {
    "owner/__init__.py": (80, "d857d613efdca2fad6b20a106349516a410e2837b5f4bff6b6d2db592ba58658"),
    "owner/io.py": (10152, "8e29aa60a95b8433361bda241ee60e25db40c0884547c7bc55d5015c4741ad4e"),
    "owner/scoring.py": (12817, "e85413e3af2b63c919fbfc93fffdb6fc0e37af9d038f693df99da980b04dc0dc"),
    "preparation/__init__.py": (82, "a852591a1dea52c60ea4a6cacb06b150e49397ac9189d2120e8dc7c4f9241d95"),
    "preparation/algorithm.py": (7672, "aa5255ba1d238331cc91122b4b84ce2d90a0d23b7b19964ddb91c72953bac3c8"),
    "preparation/native.py": (8094, "59938e74806637cc3be504a6bcb2a550f1571d22e6d55342abdd048978389c66"),
}
RANGE = {
    "range_io.py": (15515, "73d479623f9fe78f42631aeca49113748791b5737cfe7b6aec43789737ffb7e1"),
    "manifest.py": (7952, "36b7eb96e9d40f808035979b1f30c7e103746d20d670235d8658cda613381205"),
    "pipeline.py": (20502, "ad1e2e80dc8676af208a3fee4bd0977694fc3abf145d883fbb5b8b7a17dd8f42"),
}
SELECTION = (9605316, "d484ac018c7b7a0cc9ed826de5977a9ec9724a82e68126ec7e13be23507c1ab7")
ASSETS = (1485117, "41dc23799cd96d8e9f8bf0aa0961f049187435109454a4055126d51c53f1b7d2")
OUTPUTS = {"plane": "plane_metadata.json", "session": "session_support.json"}
COUNTERS = {"http_requests", "http_response_body_bytes", "http_header_reservation_bytes",
            "logical_read_bytes", "export_read_bytes", "host_write_bytes", "control_bytes",
            "closure_seconds", "worker_artifact_write_bytes", "worker_control_bytes", "source_setup_read_bytes"}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                       allow_nan=False) + "\n").encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def strict(body):
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    def bad(_):
        raise ValueError("nonfinite JSON")
    return json.loads(body, object_pairs_hook=pairs, parse_constant=bad)


def descriptor(ref, cap):
    need(type(ref) is dict and set(ref) == {"path", "bytes", "sha256"}
         and type(ref["path"]) is str and len(ref["path"].encode()) <= 2048
         and type(ref["bytes"]) is int and 0 < ref["bytes"] <= cap
         and type(ref["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", ref["sha256"]), "bounded exact descriptor")
    return ref


def ordinary(path, directory=False):
    p = Path(path)
    need(p.is_absolute() and str(p) == os.path.normpath(str(p))
         and all(not q.is_symlink() for q in (p, *p.parents)), "ordinary canonical path")
    if directory:
        need(p.is_dir(), "ordinary directory")
    return p


def pinned(ref, cap, *, retain=True, charge=None):
    descriptor(ref, cap)
    if charge is not None:
        charge(ref["bytes"] + 1)
    p = ordinary(ref["path"])
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    stamp = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
    body = bytearray() if retain else None
    actual, sha = 0, hashlib.sha256()
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == ref["bytes"], "exact ordinary extent")
        while actual < ref["bytes"]:
            block = os.read(fd, min(65536, ref["bytes"] - actual))
            need(block, "complete pinned input")
            actual += len(block)
            sha.update(block)
            if body is not None:
                body.extend(block)
        need(not os.read(fd, 1) and stamp(before) == stamp(os.fstat(fd)) == stamp(p.lstat()), "same-FD input identity")
    finally:
        os.close(fd)
    need(sha.hexdigest() == ref["sha256"], "input/source SHA256")
    return bytes(body) if retain else None


def publish(path, value, cap, counters):
    body = canonical(value)
    need(len(body) <= cap, "bounded control serialization")
    ceiling = counters["cap"] - (0 if counters.get("cleanup_mode") else counters.get("protected", 0))
    need(counters["requested"] + len(body) <= ceiling, "reserved control/write cap")
    p = ordinary(path)
    ordinary(p.parent, directory=True)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        offset = 0
        while offset < len(body):
            piece = memoryview(body)[offset:offset + 65536]
            need(counters["requested"] + len(piece) <= ceiling, "requested control-write ceiling")
            counters["requested"] += len(piece)
            counters["uncertain"] = True
            count = os.write(fd, piece)
            need(count > 0, "complete exclusive control write")
            counters["confirmed"] += count
            offset += count
            counters["uncertain"] = False
        os.fsync(fd)
        os.fchmod(fd, 0o444)
    finally:
        os.close(fd)
    dfd = os.open(p.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)
    return {"path": str(p), "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def posix_path(value):
    need(type(value) is str and 0 < len(value.encode()) <= 2048
         and value.startswith("/") and value == os.path.normpath(value)
         and re.fullmatch(r"[A-Za-z0-9_./:@=,+-]+", value), "canonical fixed argv path")
    return value


def endpoint(value):
    need(type(value) is str and value.startswith("unix:///") and len(value) <= 2048,
         "explicit local Unix socket endpoint")
    parsed = urlsplit(value)
    need(parsed.scheme == "unix" and not parsed.netloc and not parsed.query and not parsed.fragment
         and "%" not in value and not any(ord(c) < 32 or ord(c) == 127 for c in value),
         "no remote socket authority or encoded components")
    posix_path(parsed.path)
    need(value == "unix://" + parsed.path, "canonical Unix endpoint")
    return value


def runtime_descriptor(ref):
    need(type(ref) is dict and set(ref) == {"path", "resolved_path", "bytes", "sha256"},
         "exact runtime alias and target")
    descriptor({k: ref[k] for k in ("path", "bytes", "sha256")}, 67108864)
    posix_path(ref["path"])
    posix_path(ref["resolved_path"])


def launcher(value):
    need(type(value) is dict and value.get("kind") in ("direct_python", "qualified_arch"),
         "two typed launchers only")
    if value["kind"] == "direct_python":
        need(set(value) == {"kind"}, "no arbitrary launcher arguments")
    else:
        need(set(value) == {"kind", "executable", "architecture", "qualification"}
             and value["architecture"] == "arm64", "fixed qualified arch mode")
        runtime_descriptor(value["executable"])
        descriptor(value["qualification"], 65536)


def validate_operation(op, *, require_selected=True):
    need(type(op) is dict and set(op) == {"schema", "selected", "runtime_qualified",
         "authority_policy_sha256", "native", "runtime", "deployment", "helpers",
         "sources", "host_inventory", "profile", "inputs", "layout_bank", "output_root",
         "limits", "startup_envelope"}, "exact portable N063 operation")
    need(op["schema"] == "neural063-portable-contained-controller-v1", "operation schema")
    if not require_selected:
        need(op["selected"] is False and op["runtime_qualified"] is False, "inactive preparation only")
        return {"launchable": False}
    need(op["selected"] is True and op["runtime_qualified"] is True
         and type(op["authority_policy_sha256"]) is str
         and re.fullmatch(r"[0-9a-f]{64}", op["authority_policy_sha256"]), "unselected external authority")
    need(type(op["native"]) is dict and type(op["runtime"]) is dict
         and type(op["deployment"]) is dict, "unresolved native/runtime/deployment")
    need(set(op["runtime"]) == {"docker", "host_python", "timer", "launcher", "python_in_image"},
         "exact portable runtime fields")
    for key in ("docker", "host_python", "timer"):
        runtime_descriptor(op["runtime"][key])
    launcher(op["runtime"]["launcher"])
    posix_path(op["runtime"]["python_in_image"])
    posix_path(op["output_root"])
    need(set(op["helpers"]) == set(HELPER_PINS), "three fixed helper roles")
    for key, ref in op["helpers"].items():
        descriptor(ref, 65536)
        need((ref["bytes"], ref["sha256"]) == HELPER_PINS[key], "accepted immutable helper bytes")
    need(set(op["inputs"]) == {"selection", "assets"}, "fixed original inputs")
    for key, wanted in (("selection", SELECTION), ("assets", ASSETS)):
        descriptor(op["inputs"][key], 16777216)
        need((op["inputs"][key]["bytes"], op["inputs"][key]["sha256"]) == wanted, "fixed original input pin")
    descriptor(op["profile"], 65536)
    descriptor(op["layout_bank"], 4194304)
    descriptor(op["host_inventory"], 131072)
    required = {"original/" + k for k in ORIGINAL} | {"range/" + k for k in RANGE}
    required |= {"worker.py", "scientific_adapter.py", "controller.py", "n063_fixed_export.py"}
    need(set(op["sources"]) == required, "exact mounted source closure")
    for name, ref in op["sources"].items():
        descriptor(ref, 131072)
        frozen = ORIGINAL.get(name.removeprefix("original/")) if name.startswith("original/") else RANGE.get(name.removeprefix("range/"))
        if frozen is not None:
            need((ref["bytes"], ref["sha256"]) == frozen, "unchanged original scientific source")
    need(Path(op["sources"]["controller.py"]["path"]).absolute() == Path(__file__).absolute(),
         "executing controller source")
    need(type(op["limits"]) is dict and set(op["limits"]) == {"whole_seconds", "cleanup_seconds",
         "ready_attempts", "ready_interval_seconds"}, "finite fixed limits")
    need(all(type(x) is int and x > 0 for x in op["limits"].values())
         and op["limits"]["whole_seconds"] <= 86400 and op["limits"]["cleanup_seconds"] >= 30
         and op["limits"]["ready_attempts"] <= 1800
         and op["limits"]["whole_seconds"] > op["limits"]["cleanup_seconds"] + 10,
         "bounded work/cleanup/readiness policy")
    need(set(op["startup_envelope"]) == COUNTERS
         and all(type(x) is int and x >= 0 for x in op["startup_envelope"].values()), "finite startup reservation")
    dep = op["deployment"]
    need(set(dep) == {"endpoint", "image_id", "image_env", "runtime_receipt", "mount_receipt", "network_receipt",
         "containment_receipt", "exporter_receipt", "delegation_receipt", "plane_network"}, "exact deployment closure")
    endpoint(dep["endpoint"])
    need(type(dep["image_id"]) is str and re.fullmatch(r"sha256:[0-9a-f]{64}", dep["image_id"]), "unresolved image")
    for key in ("runtime_receipt", "mount_receipt", "network_receipt",
                "containment_receipt", "exporter_receipt", "delegation_receipt"):
        descriptor(dep[key], 65536)
    need(type(dep["plane_network"]) is dict and set(dep["plane_network"]) == {"name", "id"}
         and re.fullmatch(r"n063-[a-z0-9-]{1,48}", dep["plane_network"]["name"])
         and re.fullmatch(r"[0-9a-f]{64}", dep["plane_network"]["id"]), "qualified fixed S3 route unresolved")
    return {"declarations_valid": True, "authority_proven": False}


def validate_authority(policy, op):
    """Pure declaration binding, deliberately not an authorization decision."""
    need(type(policy) is dict and set(policy) == {"schema", "selected", "operator_uid", "workspace",
         "output_parent", "ledger", "controller", "native_controller", "supervisor_python",
         "ps", "capture", "helpers", "runtime", "endpoint", "qualification"},
         "exact independent authority policy")
    need(policy["schema"] == "neural063-native-authority-v1" and policy["selected"] is True,
         "inactive authority policy")
    need(type(policy["operator_uid"]) is int and policy["operator_uid"] >= 0,
         "explicit cooperative operator UID")
    for key in ("workspace", "output_parent", "ledger"):
        posix_path(policy[key])
    descriptor(policy["native_controller"], 65536)
    descriptor(policy["controller"], 131072)
    descriptor(policy["capture"], 16384)
    descriptor(policy["qualification"], 65536)
    need((policy["native_controller"]["bytes"], policy["native_controller"]["sha256"]) == NATIVE_CONTROLLER_PIN,
         "native controller code anchor cannot be replaced by policy")
    need((policy["capture"]["bytes"], policy["capture"]["sha256"]) == CAPTURE_PIN,
         "known safe pre-admission capture source")
    runtime_descriptor(policy["supervisor_python"])
    runtime_descriptor(policy["ps"])
    need(type(policy["helpers"]) is dict and set(policy["helpers"]) == set(HELPER_PINS),
         "authority helper role allowlist")
    for key, ref in policy["helpers"].items():
        descriptor(ref, 65536)
        need((ref["bytes"], ref["sha256"]) == HELPER_PINS[key], "authority helper source anchor")
    need(policy["controller"] == op["sources"]["controller.py"]
         and policy["helpers"] == op["helpers"] and policy["runtime"] == op["runtime"]
         and endpoint(policy["endpoint"]) == endpoint(op["deployment"]["endpoint"]),
         "operation cannot change authority code/runtime/helper/socket allowlist")
    native = op["native"]
    native_declarations(policy, native)
    need(Path(op["output_root"]) == Path(policy["output_parent"]) / native["id"],
         "exact fresh operation namespace under authority output root")
    return {"declarations_valid": True, "authority_proven": False}


def native_declarations(policy, native):
    need(type(native) is dict and set(native) == {"id", "approval_id", "owner", "protocol", "ledger", "cwd", "ram_bytes"}
         and native["owner"] == "root" and native["ledger"] == policy["ledger"]
         and native["cwd"] == policy["workspace"] and native["ram_bytes"] == 2147483648
         and all(type(native[k]) is str and re.fullmatch(r"[A-Za-z0-9_.-]{1,160}", native[k])
                 for k in ("id", "approval_id")), "fixed native authority declarations")
    descriptor(native["protocol"], 8388608)


def validate_native_protocol(protocol, operation, *, operation_path, authority_descriptor, mode):
    """Bind every approved operation field without a protocol/self-hash cycle."""
    need(type(protocol) is dict and set(protocol) == {"schema", "authority", "mode",
         "operation_path", "operation_payload"}
         and protocol["schema"] == "neural063-portable-native-protocol-v1",
         "exact approved portable native protocol")
    need(mode in ("host", "recover") and protocol["mode"] == mode,
         "approved fixed controller entry")
    descriptor(authority_descriptor, 65536)
    need(protocol["authority"] == authority_descriptor
         and protocol["operation_path"] == posix_path(str(operation_path)),
         "approved independent authority and exact operation path")
    need(type(operation) is dict and type(operation.get("native")) is dict
         and "protocol" in operation["native"], "complete actual operation payload")
    # Do not omit source, runtime, input, output, custody, resource or authority
    # selections. Only this one back-reference is filled after protocol hashing.
    reconstructed = dict(operation)
    reconstructed["native"] = {k: v for k, v in operation["native"].items() if k != "protocol"}
    need(canonical(protocol["operation_payload"]) == canonical(reconstructed),
         "approved complete operation payload; only native.protocol omitted")
    return {"approved_payload_equal": True, "authority_proven": False}


def owned(path, uid):
    p = ordinary(path)
    info = p.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == uid
         and not info.st_mode & 0o022, "owned ordinary authority file, no group/other writes")
    return p


def owned_pin(ref, cap, uid):
    owned(ref["path"], uid)
    body = pinned(ref, cap)
    owned(ref["path"], uid)
    return body


def authority_policy(path, sha, op):
    """Caller supplies policy independently; deployment config cannot choose it."""
    p = ordinary(path)
    uid = os.geteuid()
    owned(p, uid)
    need(p.stat().st_size <= 65536, "bounded independent policy")
    policy = strict(pinned({"path": str(p), "bytes": p.stat().st_size, "sha256": sha}, 65536))
    validate_authority(policy, op)
    need(policy["operator_uid"] == uid and op["authority_policy_sha256"] == sha,
         "same external policy and cooperative operator")
    for forbidden in (Path(op["output_root"]), Path(__file__).absolute().parent):
        need(os.path.commonpath([str(p), str(forbidden)]) != str(forbidden),
             "authority policy cannot be generated inside operation/package")
    return policy


def authenticate_runtime(ref, charge=None):
    runtime_descriptor(ref)
    need(str(Path(ref["path"]).resolve(strict=True)) == ref["resolved_path"], "runtime alias target")
    target = {"path": ref["resolved_path"], "bytes": ref["bytes"], "sha256": ref["sha256"]}
    info = ordinary(target["path"]).lstat()
    need(info.st_uid in (0, os.geteuid()) and not info.st_mode & 0o022, "trusted runtime file owner/mode")
    pinned(target, 67108864, retain=False, charge=charge)


def python_command(op, path, sha, authority_path, authority_sha, mode):
    need(mode in ("host", "recover"), "two fixed root-owned entries")
    return [op["runtime"]["host_python"]["path"], "-I", "-S", "-B",
            op["sources"]["controller.py"]["path"], mode,
            "--authority", str(authority_path), "--authority-sha256", authority_sha,
            "--operation", str(path), "--sha256", sha]


def fixed_outer_command(op, path, sha, authority_path, authority_sha, mode="host"):
    args = python_command(op, path, sha, authority_path, authority_sha, mode)
    launch = op["runtime"]["launcher"]
    if launch["kind"] == "qualified_arch":
        args = [launch["executable"]["path"], "-arm64", *args]
    return [op["runtime"]["timer"]["path"], "--signal=TERM", "--kill-after=10s",
            str(op["limits"]["whole_seconds"] - 10) + "s", *args]


def safe_argv(argv):
    need(type(argv) is list and argv and all(type(v) is str and v
         and re.fullmatch(r"[A-Za-z0-9_./:@=,+-]+", v) for v in argv)
         and len(" ".join(argv).encode()) <= 6144, "fixed unambiguous bounded process argv")
    return argv


def authority_read_bound(policy, op):
    refs = [policy[k] for k in ("native_controller", "controller", "capture", "qualification",
                               "supervisor_python", "ps")]
    refs += [op["native"]["protocol"], op["runtime"]["host_python"], op["runtime"]["timer"]]
    if op["runtime"]["launcher"]["kind"] == "qualified_arch":
        refs += [op["runtime"]["launcher"]["executable"], op["runtime"]["launcher"]["qualification"]]
    # Policy/op bootstrap, three ledger snapshots (one finite child-id race),
    # double code/runtime/protocol authentication, six bounded ps captures.
    return 2 * 65537 + 1048577 + 3 * 4194305 + 2 * sum(r["bytes"] + 1 for r in refs) + 6 * 8193


def ledger_snapshot(policy):
    p = owned(policy["ledger"], policy["operator_uid"])
    count = p.stat().st_size
    need(0 < count <= 4194304, "bounded mutable native ledger")
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    stamp = lambda x: (x.st_dev, x.st_ino, x.st_size, x.st_mtime_ns, x.st_ctime_ns, x.st_uid)
    try:
        before = os.fstat(fd)
        data = bytearray()
        while len(data) < count:
            block = os.read(fd, min(65536, count - len(data)))
            need(block, "complete mutable-ledger snapshot")
            data.extend(block)
        need(not os.read(fd, 1) and stamp(before) == stamp(os.fstat(fd)) == stamp(p.lstat()),
             "stable ordinary ledger snapshot, never a replaced prefix")
    finally:
        os.close(fd)
    value = strict(data)
    need(value.get("schema") == "comprehensive_revision_resources_v1"
         and value.get("native_execution", {}).get("maximum_concurrent_heavy_jobs") == 1,
         "known registered native lease schema")
    return value


def lease_contended(policy):
    """Contention alone is not ownership; native_gate also proves live lineage."""
    p = owned(Path(policy["ledger"]).parent / "native-execution.lock", policy["operator_uid"])
    fd = os.open(p, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK)
    busy = False
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            busy = True
        else:
            fcntl.flock(fd, fcntl.LOCK_UN)
        need(busy, "actual exclusive native lease must already be held")
    finally:
        os.close(fd)


def registered_row(doc, op, command):
    native = op["native"]
    approvals = [r for r in doc.get("approved_native_protocols", []) if r.get("id") == native["approval_id"]]
    rows = [r for r in doc.get("native_runs", []) if r.get("id") == native["id"]]
    pin = {"path": native["protocol"]["path"], "sha256": native["protocol"]["sha256"]}
    need(len(approvals) == len(rows) == 1 and approvals[0].get("owner") == "root"
         and approvals[0].get("protocol") == pin and approvals[0].get("approved_by") == "/root",
         "registered root-reviewed exact protocol")
    row = rows[0]
    need(row.get("owner") == "root" and row.get("status") == "running"
         and row.get("approval_id") == native["approval_id"] and row.get("protocol") == pin
         and row.get("command") == command and row.get("cwd") == native["cwd"]
         and row.get("requested_threads") == 1
         and row.get("declared_max_working_ram_bytes") == native["ram_bytes"],
         "registered running command, not a self-asserted operation receipt")
    return row


def sample_process(pid, policy, capture_module):
    """One finite owned ps invocation, no signal to an observed ancestor."""
    need(type(pid) is int and pid > 1, "finite observed PID")
    command = [policy["ps"]["path"], "-ww", "-p", str(pid),
               "-o", "pid=,ppid=,pgid=,uid=,lstart=,state=,command="]
    proc = capture = None
    error = None
    end = time.monotonic() + 1
    try:
        proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, close_fds=True, start_new_session=False,
            env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"})
        capture = capture_module.BoundedCapture(proc, retained_per_stream=8192, read_ceiling=8193)
        while proc.poll() is None or not capture.summary()["all_eof_observed"]:
            need(time.monotonic() < end, "bounded identity sample deadline")
            capture.pump(min(.025, max(0, end - time.monotonic())))
            need(not capture.read_ceiling_exhausted, "complete bounded identity output")
        proc.wait(timeout=max(.001, end - time.monotonic()))
        need(proc.returncode == 0 and time.monotonic() < end, "complete timely identity sample")
    except BaseException as exc:
        error = exc
    finally:
        if proc is not None and proc.poll() is None:
            # Only this Popen-owned observer may be signaled; permission refusal
            # is not retried through another route. Outer native owner remains.
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=.2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=.3)
            except BaseException as exc:
                error = error or exc
        if capture is not None:
            try:
                if proc.poll() is None:
                    raise ValueError("identity observer reaping unknown")
                capture.finish(proc, time.monotonic() + .3)
            except BaseException as exc:
                error = error or exc
            try:
                capture.close()
            except BaseException as exc:
                error = error or exc
        if proc is not None:
            for stream in (proc.stdout, proc.stderr):
                try:
                    if stream is not None and not stream.closed:
                        stream.close()
                except BaseException as exc:
                    error = error or exc
    if error is not None:
        raise ValueError("identity sampling failed closed") from error
    summary = capture.summary()
    need(summary["all_eof_observed"] and not summary["storage_truncated"]
         and not summary["read_ceiling_exhausted"] and not summary["closed_without_eof"]
         and not summary["stream_close_errors"], "complete identity capture/closure")
    body = capture.lanes["stdout"].retained()
    need(not capture.lanes["stderr"].retained(), "no identity diagnostic ambiguity")
    line = body.decode("ascii", "strict")
    match = re.fullmatch(r"\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+"
        r"([A-Za-z]{3}\s+[A-Za-z]{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+\d{4})\s+"
        r"(\S+)\s+([^\r\n]+)\n?", line)
    need(match is not None, "qualified complete process identity format")
    a, b, c, d, start, state, command = match.groups()
    row = {"pid": int(a), "ppid": int(b), "pgid": int(c), "uid": int(d),
           "start": " ".join(start.split()), "state": state, "command": command}
    need(row["pid"] == pid and row["uid"] == policy["operator_uid"]
         and not any(x in state for x in ("Z", "X")), "same live cooperative-UID process")
    return row


def native_gate(op, path, sha, *, authority, authority_path, authority_sha, mode="host", operation_payload=None):
    """Prove a registered live native owner. Policy declarations alone never do."""
    policy, native = authority, op["native"]
    native_declarations(policy, native)
    need(op["authority_policy_sha256"] == authority_sha
         and native["ledger"] == policy["ledger"] and native["cwd"] == policy["workspace"],
         "external policy bound to fixed invocation")
    need(Path.cwd() == ordinary(policy["workspace"], directory=True)
         and all(os.environ.get(k) == "1" for k in THREADS), "actual native cwd/thread environment")
    command = safe_argv(fixed_outer_command(op, path, sha, authority_path, authority_sha, mode))
    owner_command = safe_argv([policy["supervisor_python"]["path"], "-I", "-S", "-B",
        policy["native_controller"]["path"], "--ledger", policy["ledger"], "native-run",
        "--id", native["id"], "--owner", "root", "--protocol", native["protocol"]["path"],
        "--approval-id", native["approval_id"], "--threads", "1", "--ram-bytes", str(native["ram_bytes"]),
        "--cwd", native["cwd"], "--wait-seconds", "0", "--", *command])
    need((policy["native_controller"]["bytes"], policy["native_controller"]["sha256"]) == NATIVE_CONTROLLER_PIN,
         "known native controller source anchor")
    uid = policy["operator_uid"]
    qualification = strict(owned_pin(policy["qualification"], 65536, uid))
    need(qualification.get("schema") == "neural063-native-runtime-qualification-v1"
         and qualification.get("qualified") is True and qualification.get("platform") == sys.platform
         and qualification.get("ps_format") == "c-pid-ppid-pgid-uid-lstart-state-command-v1"
         and qualification.get("timer_semantics") == "gnu-timeout-v1"
         and qualification.get("timer_child_ppid_verified") is True
         and qualification.get("controller") == policy["controller"]
         and qualification.get("native_controller") == policy["native_controller"]
         and qualification.get("supervisor_python") == policy["supervisor_python"]
         and qualification.get("ps") == policy["ps"] and qualification.get("capture") == policy["capture"]
         and qualification.get("runtime") == op["runtime"]
         and qualification.get("endpoint") == policy["endpoint"],
         "independent platform/exec/observer qualification unresolved")
    launch = op["runtime"]["launcher"]
    if launch["kind"] == "qualified_arch":
        proof = strict(owned_pin(launch["qualification"], 65536, uid))
        need(proof.get("schema") == "neural063-exec-launcher-qualification-v1"
             and proof.get("qualified") is True and proof.get("exec_preserves_pid") is True
             and proof.get("executable") == launch["executable"]
             and proof.get("architecture") == "arm64", "qualified fixed exec launcher only")
    def anchors():
        protocol_body = None
        for ref in (policy["native_controller"], policy["controller"], native["protocol"]):
            body = owned_pin(ref, 8388608, uid)
            if ref is native["protocol"]:
                protocol_body = body
        for ref in (policy["supervisor_python"], policy["ps"],
                    op["runtime"]["host_python"], op["runtime"]["timer"]):
            authenticate_runtime(ref)
        if launch["kind"] == "qualified_arch":
            authenticate_runtime(launch["executable"])
        return protocol_body
    protocol_body = anchors()
    validate_native_protocol(strict(protocol_body), op if operation_payload is None else operation_payload,
        operation_path=path, authority_descriptor={"path": str(authority_path),
            "bytes": Path(authority_path).stat().st_size, "sha256": authority_sha}, mode=mode)
    del protocol_body
    row = registered_row(ledger_snapshot(policy), op, command)
    if type(row.get("child_pid")) is not int:
        time.sleep(.1)
        row = registered_row(ledger_snapshot(policy), op, command)
    need(type(row.get("coordinator_pid")) is int and row["coordinator_pid"] > 1
         and type(row.get("child_pid")) is int and row["child_pid"] > 1
         and os.getpgrp() == row["child_pid"] and os.getppid() == row["child_pid"],
         "actual inherited native timer group and direct child relation")
    lease_contended(policy)
    # This is the sole pre-admission module load; its immutable safe source pin
    # is embedded in trusted controller code, not replaceable by configuration.
    body = owned_pin(policy["capture"], 16384, uid)
    capture = loaded("_n063_authority_capture", body, policy["capture"]["path"])
    ids = (row["coordinator_pid"], row["child_pid"], os.getpid())
    first = [sample_process(pid, policy, capture) for pid in ids]
    expected = [owner_command, command,
                safe_argv(python_command(op, path, sha, authority_path, authority_sha, mode))]
    for observed, argv in zip(first, expected):
        need(observed["command"] == " ".join(argv), "live exact qualified executable argv")
    need(first[1]["ppid"] == first[0]["pid"] and first[1]["pgid"] == first[1]["pid"]
         and first[2]["ppid"] == first[1]["pid"] and first[2]["pgid"] == first[1]["pid"],
         "live coordinator-to-timer-to-controller ancestry")
    second = [sample_process(pid, policy, capture) for pid in ids]
    for before, after in zip(first, second):
        need(all(before[k] == after[k] for k in ("pid", "ppid", "pgid", "uid", "start", "command")),
             "stable live identities across admission")
    final = registered_row(ledger_snapshot(policy), op, command)
    need(final["child_pid"] == row["child_pid"] and final["coordinator_pid"] == row["coordinator_pid"],
         "same actual registered native lease")
    lease_contended(policy)
    anchors()
    need(strict(owned_pin({"path": str(authority_path), "bytes": Path(authority_path).stat().st_size,
                         "sha256": authority_sha}, 65536, uid)) == policy,
         "stable external authority policy after observations")
    return {"native_id": native["id"], "owned_pgid": row["child_pid"],
        "coordinator_pid": row["coordinator_pid"], "authority_policy_sha256": authority_sha,
        "protocol": {"path": native["protocol"]["path"], "sha256": native["protocol"]["sha256"]},
        "live_identity_sha256": digest(second), "registered_live_lease_verified": True,
        "trust_boundary": "cooperative same-UID operator; not hostile-owner cryptographic authorization",
        "outer_final_group_absence_required": True, "outer_final_container_absence_required": True}


def loaded(name, body, path):
    module = types.ModuleType(name)
    module.__file__ = path
    sys.modules[name] = module
    exec(compile(body, path, "exec"), module.__dict__)
    return module


def inside_start():
    p = Path("/inputs/DIGESTS.json")
    size = p.lstat().st_size
    need(0 < size <= 256, "small root-owned digest sidecar")
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        st = os.fstat(fd)
        need(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and st.st_size == size, "ordinary digest sidecar")
        body = os.read(fd, size + 1)
    finally:
        os.close(fd)
    need(len(body) == size, "complete digest sidecar")
    row = strict(body)
    need(set(row) == {"contract_sha256", "admission_sha256"}
         and all(type(v) is str and re.fullmatch(r"[0-9a-f]{64}", v) for v in row.values()), "fixed root digests")
    os.execv(sys.executable, [sys.executable, "-I", "-B", "/operator/worker.py",
             "--contract-sha256", row["contract_sha256"], "--admission-sha256", row["admission_sha256"]])


def inside_ready():
    p = Path("/output/READY.json")
    if not p.exists():
        return 75
    need(not p.is_symlink(), "ordinary ready control")
    size = p.lstat().st_size
    need(0 < size <= 8192, "bounded complete ready control")
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        st = os.fstat(fd)
        need(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and st.st_size == size
             and st.st_mode & 0o222 == 0, "sealed ready descriptor")
        body = os.read(fd, size + 1)
        need(len(body) == size and os.fstat(fd).st_size == size, "complete ready read")
    finally:
        os.close(fd)
    body.decode("utf-8", "strict")
    strict(body)
    need(os.write(1, body) == len(body), "complete ready export")
    return 0


class UnitJournal:
    """Small fixed call journal; complete maxima reserved by Inventory first."""
    def __init__(self, root, counters, normal_calls):
        self.root, self.normal_calls = root, normal_calls
        self.counters = counters
        self.errors = []
        self.cleanup_start = None

    def write(self, name, value, cap=65536, reserved=False):
        need(re.fullmatch(r"cli-[0-9]{2,4}-(intent|result)\.json", name), "fixed CLI journal namespace")
        body = canonical(value)
        need(len(body) <= min(cap, 65536), "bounded transport record")
        if not reserved:
            need(self.counters["requested"] + len(body) <= self.counters["cap"] - 262144,
                 "cleanup journal reserve")
        return publish(self.root / name, value, min(cap, 65536), self.counters)


class Unit:
    def __init__(self, operation, inventory, profile, adapter, exporter, bank, legacy, formats,
                 kind, identity, root, host_deadline, owner):
        self.op, self.inventory, self.profile = operation, inventory, profile
        self.adapter, self.exporter, self.bank, self.legacy, self.formats = adapter, exporter, bank, legacy, formats
        self.kind, self.identity, self.root, self.deadline, self.owner = kind, identity, root, host_deadline, owner
        self.name = "n063-" + owner[:16] + "-" + kind + "-" + identity
        self.cid = None
        self.create_attempted = False
        self.create_verified = False
        self.transport_unknown = False
        self.sequence = 0
        self.cleanup_calls = 0
        self.errors = []
        self.receipts = {}
        self.mounts = {}
        self.reservation = inventory.reserve(kind, identity)
        need(self.reservation["envelope"]["source_setup_read_bytes"] >=
             67108864 + 257 + 8193 * operation["limits"]["ready_attempts"],
             "worker setup plus fixed bootstrap/READY reads fully reserved")
        cap = self.reservation["envelope"]["control_bytes"]
        controller_cap = cap - cap // 2 - 1024
        need(controller_cap >= 4194304 + operation["limits"]["ready_attempts"] * 81920,
             "complete controller/journal maxima reserved")
        root.mkdir(mode=0o700)
        (root / "cli").mkdir(mode=0o700)
        (root / "inputs").mkdir(mode=0o755)
        self.control = {"cap": controller_cap, "protected": 262144, "cleanup_mode": False,
                        "requested": 0, "confirmed": 0, "uncertain": False}
        self.journal = UnitJournal(root / "cli", self.control, operation["limits"]["ready_attempts"] + 15)
        self.docker = bank.Docker(self.journal, bank.stop_cli_leader)

    def record(self, name, value, cap=8192):
        if self.cleanup_calls == 0:
            need(self.control["requested"] + len(canonical(value)) <= self.control["cap"] - 262144, "cleanup control reserve")
        ref = publish(self.root / name, value, cap, self.control)
        self.receipts[name] = ref
        return ref

    def call(self, argv, *, cap=8192, cleanup=False, allow_return=False):
        if cleanup:
            need(self.cleanup_calls < 3 and (argv[:2] == ["rm", "--force"]
                 or argv[:3] == ["inspect", "--type", "container"]), "only three owned cleanup calls")
            self.cleanup_calls += 1
            self.control["cleanup_mode"] = True
            end = min(self.deadline, time.monotonic() + 8)
        else:
            need(self.cleanup_calls == 0, "no new work after cleanup starts")
            need(self.sequence < self.op["limits"]["ready_attempts"] + 15, "finite fixed normal calls")
            self.sequence += 1
            end = min(self.deadline - self.op["limits"]["cleanup_seconds"], time.monotonic() + 10)
        need(time.monotonic() + 1 < end, "host-owned command deadline")
        try:
            row = self.docker.call(argv, end, cap=cap, cleanup=cleanup)
        except BaseException as exc:
            self.errors.append(type(exc).__name__)
            self.transport_unknown = True
            raise
        if row.get("cleanup", {}).get("leader_reaped") is not True or row.get("error_type"):
            self.transport_unknown = True
            raise ValueError("CLI leader closure unknown")
        if row.get("diagnostic_publication_errors"):
            self.transport_unknown = True
            self.errors.extend(row["diagnostic_publication_errors"])
            need(cleanup, "complete command custody")
        if not allow_return:
            need(row["returncode"] == 0 and not row["stderr"], "successful fixed control command")
        return row

    def ownership(self, value, identifier=None):
        cid = value.get("id")
        labels = value.get("labels")
        need(type(cid) is str and re.fullmatch(r"[0-9a-f]{64}", cid)
             and (identifier is None or cid == identifier)
             and value.get("name") == "/" + self.name and value.get("image") == self.op["deployment"]["image_id"]
             and type(labels) is dict and labels.get("n063.owner") == self.owner
             and labels.get("n063.kind") == self.kind and labels.get("n063.identity") == self.identity
             and labels.get("n063.reservation") == self.reservation["reservation_sha256"], "exact owned unit container")
        return cid

    def inspect(self, *, cleanup=False, ownership_only=False):
        target = self.cid or self.name
        fmt = self.formats["container_ownership" if ownership_only else "container_full"]
        row = self.call(["inspect", "--type", "container", target, "--format", fmt],
                        cleanup=cleanup, cap=32768 if not cleanup else 8192, allow_return=cleanup)
        if cleanup and self.legacy.absent(row, target):
            return None
        need(row["returncode"] == 0 and not row["stderr"], "complete owned-container inspection")
        value = strict(row["stdout"])
        self.ownership(value, self.cid)
        return value

    def create_args(self):
        op = self.op
        network = "none" if self.kind == "session" else op["deployment"]["plane_network"]["name"]
        args = ["create", "--name", self.name, "--pull", "never", "--network", network,
                "--memory", "1879048192", "--memory-swap", "1879048192", "--cpus", "1",
                "--pids-limit", "32", "--user", "65534:65534", "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges:true", "--ipc", "private", "--read-only",
                "--log-driver", "none", "--shm-size", "1048576", "--workdir", "/tmp",
                "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=16777216,mode=1777",
                "--tmpfs", "/output:rw,noexec,nosuid,nodev,size=134217728,mode=1777",
                "--ulimit", "nofile=1024:1024", "--ulimit", "core=0:0",
                "--ulimit", "fsize=100663296:100663296", "--ulimit", "cpu=1800:1800",
                "--entrypoint", op["runtime"]["python_in_image"],
                "--label", "n063.owner=" + self.owner, "--label", "n063.kind=" + self.kind,
                "--label", "n063.identity=" + self.identity,
                "--label", "n063.reservation=" + self.reservation["reservation_sha256"]]
        for key in THREADS:
            args += ["--env", key + "=1"]
        args += ["--env", "PYTHONDONTWRITEBYTECODE=1", "--env", "TMPDIR=/tmp"]
        for target, source in sorted(self.mounts.items()):
            need("," not in source and "," not in target, "unambiguous fixed mount")
            args += ["--mount", "type=bind,src=" + source + ",dst=" + target + ",readonly"]
        return args + [op["deployment"]["image_id"], "-I", "-S", "-B", "/operator/controller.py", "start"]

    def verify_config(self, value, state):
        self.ownership(value, self.cid)
        network = "none" if self.kind == "session" else self.op["deployment"]["plane_network"]["name"]
        wanted = {"entry": [self.op["runtime"]["python_in_image"]],
                  "cmd": ["-I", "-S", "-B", "/operator/controller.py", "start"],
                  "user": "65534:65534", "workdir": "/tmp", "tty": False, "stdin": False,
                  "network": network, "readonly": True, "privileged": False,
                  "capdrop": ["ALL"], "security": ["no-new-privileges:true"],
                  "memory": 1879048192, "swap": 1879048192, "cpus": 1000000000,
                  "pids": 32, "shm": 1048576,
                  "tmpfs": {"/tmp": "rw,noexec,nosuid,nodev,size=16777216,mode=1777",
                            "/output": "rw,noexec,nosuid,nodev,size=134217728,mode=1777"},
                  "log": {"Type": "none", "Config": {}}}
        need(all(type(value.get(k)) is type(v) and value[k] == v for k, v in wanted.items()), "exact effective isolation/configuration")
        for key in ("volumes", "capadd", "devices", "requests", "rules", "ports"):
            need(value.get(key) in (None, [], {}) and not isinstance(value.get(key), (str, bool, int)), "no extra writable authority")
        need(value.get("pidmode") in ("", "private") and value.get("ipcmode") in ("private", "none")
             and value.get("restart", {}).get("Name") in ("", "no"), "private namespaces/no restart")
        env = dict(item.split("=", 1) for item in value["env"])
        base = dict(item.split("=", 1) for item in self.op["deployment"]["image_env"])
        base.update({key: "1" for key in THREADS}, PYTHONDONTWRITEBYTECODE="1", TMPDIR="/tmp")
        need(len(env) == len(value["env"]) and env == base, "exact inherited image/thread environment")
        limits = value.get("ulimits")
        need(type(limits) is list and len(limits) == 4
             and all(set(x) == {"Name", "Soft", "Hard"} and type(x["Soft"]) is int and type(x["Hard"]) is int for x in limits)
             and {x["Name"]: (x["Soft"], x["Hard"]) for x in limits} ==
             {"nofile": (1024, 1024), "core": (0, 0), "fsize": (100663296, 100663296), "cpu": (1800, 1800)}, "exact finite ulimits")
        declared = value.get("declaredmounts")
        need(type(declared) is list and len(declared) == len(self.mounts), "complete declared mounts")
        seen = set()
        for row in declared:
            target = row.get("Target")
            need(target in self.mounts and target not in seen and row.get("Type") == "bind"
                 and row.get("Source") == self.mounts[target] and row.get("ReadOnly") is True, "exact readonly mount declaration")
            seen.add(target)
        # create_args uses legacy --tmpfs, reported in HostConfig.Tmpfs rather
        # than inspect .Mounts. Its exact options are checked above in every
        # state; .Mounts must contain only the complete readonly bind roster.
        mounts = value.get("mounts")
        need(type(mounts) is list and len(mounts) == len(self.mounts),
             "complete inspected source/input bind roster")
        mounted = set()
        for row in mounts:
            target = row.get("Destination")
            need(target in self.mounts and target not in mounted and row.get("Type") == "bind"
                 and row.get("Source") == self.mounts[target] and row.get("RW") is False
                 and row.get("Propagation") == "rprivate", "exact inspected readonly bind")
            mounted.add(target)
        need(mounted == set(self.mounts), "complete inspected source/input bind closure")
        current = value.get("state", {})
        need(current.get("Status") == state and current.get("OOMKilled") is False and not current.get("Error"), "known non-OOM container state")
        if state == "created":
            need(current.get("Running") is False and current.get("Pid") == 0, "unstarted owned container")
        elif state == "exited":
            need(current.get("Running") is False and current.get("ExitCode") == 0, "complete zero-exit producer")
        else:
            need(current.get("Running") is True and type(current.get("Pid")) is int and current["Pid"] > 0, "live bounded export barrier")

    def remove(self):
        if not self.create_attempted:
            return {"absent": True, "id": None, "no_owned_create_attempt": True}
        value = self.inspect(cleanup=True, ownership_only=True)
        if value is None:
            return {"absent": True, "id": self.cid, "already_absent": True}
        self.cid = self.ownership(value, self.cid)
        removal_error = None
        try:
            self.call(["rm", "--force", self.cid], cleanup=True)
        except BaseException as exc:
            removal_error = type(exc).__name__
        row = self.call(["inspect", "--type", "container", self.cid, "--format", self.formats["container_absence"]], cleanup=True, allow_return=True)
        absent = self.legacy.absent(row, self.cid)
        need(absent, "exact owned-container absence")
        return {"id": self.cid, "absent": absent, "removal_error": removal_error}


def build_packet(unit, layouts):
    op, kind, identity = unit.op, unit.kind, unit.identity
    target = unit.root / "inputs"
    profile_ref = publish(target / "profile.json", unit.profile, 65536, unit.control)
    sources = {name: {**ref, "path": "/operator/" + name} for name, ref in op["sources"].items()
               if name != "controller.py" and name != "n063_fixed_export.py"}
    packet = {"schema": "neural063-contained-worker-contract-v1", "execute": True, "sources": sources,
              "profile": {**profile_ref, "path": "/inputs/profile.json"},
              "selection": {**op["inputs"]["selection"], "path": "/inputs/selection.json"},
              "assets": {**op["inputs"]["assets"], "path": "/inputs/assets.json"},
              "layout": None, "plane_inputs": None, "completed_inventory": None}
    unit.mounts = {"/operator/" + name: ref["path"] for name, ref in op["sources"].items()}
    unit.mounts.update({"/inputs": str(target), "/inputs/selection.json": op["inputs"]["selection"]["path"],
                       "/inputs/assets.json": op["inputs"]["assets"]["path"]})
    plane_refs = []
    if kind == "plane":
        layout = layouts[identity]
        packet["layout"] = {"path": "/inputs/layout.json", "bytes": layout["bytes"], "sha256": layout["sha256"]}
        unit.mounts["/inputs/layout.json"] = layout["path"]
        custody_sha = unit.inventory.initial_ref["sha256"]
    else:
        saved = unit.inventory.session_custody(identity)
        custody_ref, custody = saved["receipt"], saved["value"]
        for row in custody["plane_custody"]:
            eid, artifact = row["experiment"], row["artifact"]
            source = unit.inventory.root / ("plane-" + eid) / "plane_metadata.json"
            ordinary(source)
            st = source.lstat()
            need(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and st.st_size == artifact["bytes"]
                 and st.st_mode & 0o222 == 0, "immutable prior opaque plane output")
            path = "/inputs/planes/" + eid + ".json"
            unit.mounts[path] = str(source)
            plane_refs.append({"experiment": eid, "path": path, "bytes": artifact["bytes"], "sha256": artifact["sha256"]})
        custody_local = publish(target / "completed_inventory.json", custody, 1048576, unit.control)
        need(custody_local["sha256"] == custody_ref["sha256"], "exact readonly custody copy")
        refs = publish(target / "plane_inputs.json", plane_refs, 1048576, unit.control)
        packet["plane_inputs"] = {**refs, "path": "/inputs/plane_inputs.json"}
        packet["completed_inventory"] = {**custody_local, "path": "/inputs/completed_inventory.json"}
        custody_sha = custody_ref["sha256"]
    contract_ref = publish(target / "worker_contract.json", packet, 32768, unit.control)
    return contract_ref, custody_sha, digest(plane_refs)


def run_unit(operation, *, inventory, profile, adapter, exporter, bank, legacy, formats,
             kind, identity, layouts, host_deadline, operation_sha):
    unit = Unit(operation, inventory, profile, adapter, exporter, bank, legacy, formats, kind, identity,
                Path(operation["output_root"]) / ("control-" + kind + "-" + identity), host_deadline, operation_sha)
    result = {"kind": kind, "identity": identity, "success": False, "container_absent": False, "safe_for_further_dispatch": False,
              "reservation_sha256": unit.reservation["reservation_sha256"], "outer_group_absence_required": True}
    copied = ready = closure = None
    try:
        image_row = unit.call(["image", "inspect", operation["deployment"]["image_id"], "--format", formats["image_full"]], cap=32768)
        image_value = strict(image_row["stdout"])
        need(image_value.get("Id") == operation["deployment"]["image_id"]
             and image_value.get("Os") == "linux" and image_value.get("Architecture") == "arm64"
             and image_value.get("Env") == operation["deployment"]["image_env"], "exact qualified image/runtime environment")
        unit.record("IMAGE.json", image_value, 32768)
        if kind == "plane":
            net = operation["deployment"]["plane_network"]
            net_row = unit.call(["network", "inspect", net["name"], "--format", "{{json .Id}}"], cap=1024)
            need(strict(net_row["stdout"]) == net["id"], "exact qualified provider route identity")
        contract_ref, custody_sha, refs_sha = build_packet(unit, layouts)
        unit.record("CREATE_INTENT.json", {"owner": unit.owner, "name": unit.name, "kind": kind,
                    "identity": identity, "reservation_sha256": unit.reservation["reservation_sha256"]})
        collision = unit.call(["inspect", "--type", "container", unit.name, "--format", formats["container_absence"]], allow_return=True)
        need(legacy.absent(collision, unit.name), "fresh owned container namespace before create")
        unit.create_attempted = True
        created = unit.call(unit.create_args())
        cid = created["stdout"].strip()
        need(re.fullmatch(r"[0-9a-f]{64}", cid), "complete immutable create ID")
        unit.cid = cid
        unit.record("CREATED.json", {"id": cid})
        before = unit.inspect()
        unit.verify_config(before, "created")
        unit.create_verified = True
        config_ref = unit.record("CONFIG.json", before, 32768)
        admission = {"schema": "neural063-contained-admission-v1", "kind": kind, "identity": identity,
            "profile_sha256": adapter.sha(profile), "reservation_sha256": unit.reservation["reservation_sha256"],
            "container_id": cid, "deployment_sha256": adapter.sha(profile["deployment"]),
            "effective_controls_sha256": config_ref["sha256"],
            "host_deadline_receipt_sha256": digest({"host_deadline_monotonic": host_deadline,
                    "native_id": operation["native"]["id"], "clock_domain": "host_monotonic"}),
            "selection_sha256": SELECTION[1], "assets_sha256": inventory.assets_canonical_sha256,
            "completed_inventory_sha256": custody_sha, "plane_inputs_sha256": refs_sha,
            "worker_duration_seconds": profile["unit_seconds"][kind]}
        admission_ref = publish(unit.root / "inputs/admission.json", admission, 8192, unit.control)
        publish(unit.root / "inputs/DIGESTS.json", {"contract_sha256": contract_ref["sha256"],
                "admission_sha256": admission_ref["sha256"]}, 256, unit.control)
        unit.call(["start", cid])
        for attempt in range(operation["limits"]["ready_attempts"]):
            row = unit.call(["exec", "--user", "65534:65534", cid, operation["runtime"]["python_in_image"],
                 "-I", "-S", "-B", "/operator/controller.py", "ready"], allow_return=True, cap=8193)
            if row["returncode"] == 75 and not row["stdout"] and not row["stderr"]:
                need(time.monotonic() + operation["limits"]["ready_interval_seconds"] < host_deadline - operation["limits"]["cleanup_seconds"], "readiness wait within host deadline")
                time.sleep(operation["limits"]["ready_interval_seconds"])
                continue
            need(row["returncode"] == 0 and not row["stderr"], "complete ready descriptor transport")
            row["stdout"].encode("ascii", "strict")
            ready = strict(row["stdout"])
            break
        need(ready is not None and ready.get("schema") == "neural063-contained-ready-v1"
             and ready.get("kind") == kind and ready.get("identity") == identity and ready.get("container_id") == cid
             and ready.get("reservation_sha256") == unit.reservation["reservation_sha256"]
             and ready.get("producer_returned_successfully") is True, "same complete producer result")
        ready_ref = unit.record("READY.json", ready, 8192)
        live = unit.inspect()
        unit.verify_config(live, "running")
        owner_ref = unit.record("OWNERSHIP.json", {k: live[k] for k in ("id", "name", "image", "labels")})
        expected = ready["result"]["output"]
        need(expected["name"] == OUTPUTS[kind], "fixed unit artifact")
        lease = inventory.claim_export(kind, identity, expected=expected, container_id=cid,
            producer_receipt_sha256=ready_ref["sha256"], ownership_receipt_sha256=owner_ref["sha256"],
            host_deadline_monotonic=host_deadline)
        dep = operation["deployment"]
        export_deployment = {"docker": operation["runtime"]["docker"], "endpoint": dep["endpoint"],
            "python_in_image": operation["runtime"]["python_in_image"], "exporter_in_image": "/operator/n063_fixed_export.py",
            "image_id": dep["image_id"], "runtime_receipt_sha256": dep["runtime_receipt"]["sha256"],
            "exporter_receipt_sha256": dep["exporter_receipt"]["sha256"],
            "delegation_receipt_sha256": dep["delegation_receipt"]["sha256"], "stop_helper_sha256": operation["helpers"]["bank"]["sha256"]}
        try:
            copied = exporter.copyout(lease, expected, deployment=export_deployment, stop_cli_leader=bank.stop_cli_leader)
        except BaseException:
            unit.transport_unknown = True
            raise
        if (copied.get("cli_cleanup", {}).get("leader_reaped") is not True
                or copied.get("streams_eof") is not True or copied.get("cleanup_errors")):
            unit.transport_unknown = True
        copy_ref = unit.record("COPYOUT.json", copied, 8192)
        need(copied.get("verified") is True, "complete verified opaque copyout")
        # Reprove ownership immediately before the fixed normal stop.
        unit.inspect(ownership_only=True)
        unit.call(["stop", "--time", "2", cid])
        exited = unit.inspect()
        unit.verify_config(exited, "exited")
        exit_ref = unit.record("EXIT.json", exited, 32768)
        absent = unit.remove()
        absence_ref = unit.record("ABSENCE.json", absent)
        need(absent["absent"] is True and absent.get("removal_error") is None
             and not unit.errors and not unit.transport_unknown and unit.docker.quiescent is True and time.monotonic() < host_deadline,
             "all owned unit lifecycle and publication observations complete")
        closure = {"kind": kind, "identity": identity, "reservation_sha256": lease["reservation_sha256"],
            "container_id": cid, "producer_receipt_sha256": ready_ref["sha256"],
            "ownership_receipt_sha256": owner_ref["sha256"], "export_receipt_sha256": digest(copied),
            "artifact": expected, "proofs": {k: True for k in ("producer_complete", "producer_zero_exit", "oom_absent",
                "timeout_absent", "copyout_verified", "streams_eof", "cli_reaped", "ownership_verified", "container_absence_verified")}}
        need(not unit.control["uncertain"] and unit.control["requested"] == unit.control["confirmed"],
             "complete exact controller requested-write counters before success settlement")
        usage = ready["result"]["source_usage"]
        settlement = {"schema": "neural063_unit_success_settlement_v1", "kind": kind, "identity": identity,
            "reservation_sha256": lease["reservation_sha256"], "container_id": cid, "output": expected,
            "worker_output": usage["worker_output"], "range": usage["range"],
            "session_input_bytes_read_including_EOF_probes": usage["session_input_bytes_read_including_EOF_probes"],
            "source_setup_read_bytes": ready["source_setup_read_bytes"], "copyout": copied,
            "controller_requested_write_bytes": unit.control["requested"],
            "controller_control_bytes": unit.control["requested"],
            "receipt_hashes": {"ready": ready_ref["sha256"], "configuration": config_ref["sha256"],
                "exit": exit_ref["sha256"], "absence": absence_ref["sha256"], "copyout": copy_ref["sha256"]},
            "unmeasured_residuals_stay_reserved": True}
        inventory.finish_unit(kind, identity, artifact=expected, closure=closure, copyout_result=copied,
                              settlement_receipt=settlement)
        result.update(success=True, container_absent=True, safe_for_further_dispatch=True)
    except BaseException as exc:
        result["failure"] = type(exc).__name__ + ": " + str(exc)[:256]
        try:
            if unit.cleanup_calls == 0:
                absent = unit.remove()
                result["container_absent"] = absent["absent"]
                unit.record("FAILURE_ABSENCE.json", absent)
        except BaseException as cleanup_error:
            result["cleanup_failure"] = type(cleanup_error).__name__ + ": " + str(cleanup_error)[:256]
        result["safe_for_further_dispatch"] = (result["container_absent"] is True
            and not unit.transport_unknown and unit.docker.quiescent is True
            and (not unit.create_attempted or unit.create_verified))
        failure_closure = {"kind": kind, "identity": identity,
            "reservation_sha256": unit.reservation["reservation_sha256"], "container_id": unit.cid,
            "observations": {"container_absent": result["container_absent"],
                "cli_custody_unknown": unit.transport_unknown, "all_known_cli_leaders_reaped": unit.docker.quiescent,
                "create_identity_verified": unit.create_verified,
                "safe_for_further_dispatch": result["safe_for_further_dispatch"]},
            "failure": result["failure"], "cleanup_failure": result.get("cleanup_failure"),
            "outer_native_group_absence_required": True,
            "outer_owned_container_recovery_and_absence_required": True}
        try:
            if inventory.active == (kind, identity):
                inventory.finish_unit(kind, identity, closure=failure_closure, copyout_result=copied,
                                      failure="cleanup_unknown" if not result["safe_for_further_dispatch"] else "worker_failed")
        except BaseException as custody_error:
            result["failure_custody_error"] = type(custody_error).__name__
    return result


def host_main(path, sha, *, authority_path, authority_sha):
    # Root has already reserved this bounded trusted bootstrap before launch.
    # Only bounded metadata and the known capture anchor precede live authority.
    # Operation-supplied modules load only after registered native admission.
    started = time.monotonic()
    p = ordinary(path)
    operation = strict(pinned({"path": str(p), "bytes": p.stat().st_size, "sha256": sha}, 1048576))
    validate_operation(operation)
    setup = operation["startup_envelope"]
    need(setup["source_setup_read_bytes"] >= 1048577 + 65537, "pre-reserved initial policy/operation metadata")
    authority = authority_policy(authority_path, authority_sha, operation)
    setup_read = authority_read_bound(authority, operation)
    need(setup_read <= setup["source_setup_read_bytes"], "complete authority bootstrap reserved before dependent reads")
    context = native_gate(operation, p, sha, authority=authority,
                          authority_path=authority_path, authority_sha=authority_sha)
    def charge(count):
        nonlocal setup_read
        setup_read += count
        need(setup_read <= setup["source_setup_read_bytes"], "startup read reservation")
    profile = strict(pinned(operation["profile"], 65536, charge=charge))
    aref = operation["sources"]["scientific_adapter.py"]
    adapter = loaded("_n063_controller_adapter", pinned(aref, 131072, charge=charge), aref["path"])
    iref = operation["host_inventory"]
    inv_module = loaded("_n063_controller_inventory", pinned(iref, 131072, charge=charge), iref["path"])
    adapter.validate_profile(profile)
    need(profile["deployment"]["endpoint"] == operation["deployment"]["endpoint"] == authority["endpoint"],
         "same authorized profile/socket endpoint")
    for kind in ("plane", "session"):
        need(profile["unit_caps"][kind]["source_setup_read_bytes"] >=
             67108864 + 257 + 8193 * operation["limits"]["ready_attempts"],
             "complete worker/control read envelope before startup")
    deadline = started + operation["limits"]["whole_seconds"] - 10
    need(time.monotonic() + operation["limits"]["cleanup_seconds"] < deadline, "bootstrap within common deadline")
    root = ordinary(operation["output_root"])
    ordinary(root.parent, directory=True)
    startup = inv_module.reserve_startup(profile, root, sha, setup, adapter.validate_profile)
    # STARTUP's own bounded writer remains included, without recursive accounting.
    counters = {"cap": min(setup["control_bytes"], setup["host_write_bytes"]) - 8192,
                "requested": 0, "confirmed": 0, "uncertain": False}
    inventory = None
    try:
        for key in ("docker", "host_python", "timer"):
            authenticate_runtime(operation["runtime"][key], charge)
        if operation["runtime"]["launcher"]["kind"] == "qualified_arch":
            authenticate_runtime(operation["runtime"]["launcher"]["executable"], charge)
        helpers = operation["helpers"]
        source_bodies = {k: pinned(ref, 131072, charge=charge) for k, ref in operation["sources"].items()}
        exporter = loaded("_n063_controller_export", source_bodies["n063_fixed_export.py"], operation["sources"]["n063_fixed_export.py"]["path"])
        bank = loaded("_n063_verified_bank", pinned(helpers["bank"], 65536, charge=charge), helpers["bank"]["path"])
        legacy = loaded("_n063_verified_absence", pinned(helpers["legacy"], 65536, charge=charge), helpers["legacy"]["path"])
        formats = strict(pinned(helpers["formats"], 8192, charge=charge))
        bank.DOCKER, bank.ENDPOINT = operation["runtime"]["docker"]["path"], operation["deployment"]["endpoint"]
        pinned(operation["inputs"]["selection"], 16777216, retain=False, charge=charge)
        assets_body = pinned(operation["inputs"]["assets"], 2097152, charge=charge)
        inventory = inv_module.Inventory(assets_body, assets_identity={"bytes": ASSETS[0], "sha256": ASSETS[1]},
            profile=profile, validate_profile=adapter.validate_profile, root=root, owner_sha256=sha, startup=startup)
        charge(startup["receipt"]["bytes"] + 1)
        layouts = strict(pinned(operation["layout_bank"], 4194304, charge=charge))
        need(layouts.get("schema") == "neural063_range_layout_bank_v1"
             and layouts.get("selection_sha256") == SELECTION[1]
             and layouts.get("assets_sha256") == inventory.assets_canonical_sha256
             and layouts.get("source_counts") == {"experiments": 1936, "mice": 107, "sessions": 703, "rois": 133066}
             and layouts.get("array_values_decoded") is False and layouts.get("full_object_BLAKE2b_verified") is False,
             "authenticated complete original layout bank")
        refs = {row["experiment"]: row["layout"] for row in layouts["entries"]}
        need(len(layouts["entries"]) == len(refs) == 1936 and set(refs) == set(inventory.planes), "all original layout identities")
        for ref in refs.values():
            need(ref.get("role") == "range_layout" and ref.get("visibility") == "operator"
                 and type(ref.get("bytes")) is int and 0 < ref["bytes"] <= 4194304
                 and type(ref.get("sha256")) is str and re.fullmatch(r"[0-9a-f]{64}", ref["sha256"]),
                 "bounded complete layout descriptor")
            ordinary(ref["path"])
        for key in ("runtime_receipt", "mount_receipt", "network_receipt", "containment_receipt", "exporter_receipt", "delegation_receipt"):
            ref = operation["deployment"][key]
            need(profile["deployment"][key + "_sha256"] == ref["sha256"], "same profile-qualified deployment receipt")
            value = strict(pinned(ref, 65536, charge=charge))
            need(value.get("qualified") is True and value.get("image_id") == operation["deployment"]["image_id"]
                 and value.get("qualification_kind") == key.removesuffix("_receipt")
                 and value.get("endpoint") == authority["endpoint"]
                 and value.get("python_in_image") == operation["runtime"]["python_in_image"]
                 and value.get("docker") == operation["runtime"]["docker"]
                 and value.get("host_python") == operation["runtime"]["host_python"],
                 "authenticated task-specific endpoint/interpreter/deployment qualification")
            if key == "network_receipt":
                need(value.get("network") == operation["deployment"]["plane_network"]
                     and value.get("range_guards_unchanged") is True and value.get("session_network") == "none", "qualified exact version-bound route")
            if key == "mount_receipt":
                need(value.get("source_identities") == {k: {x: v[x] for x in ("bytes", "sha256")} for k, v in operation["sources"].items()}
                     and value.get("input_identities") == {k: {x: v[x] for x in ("bytes", "sha256")} for k, v in operation["inputs"].items()}
                     and value.get("readonly_nonroot_access_verified") is True, "qualified accessible immutable source/input deployment")
            if key == "delegation_receipt":
                need(value.get("native_id") == operation["native"]["id"]
                     and value.get("outer_group_absence_mandatory") is True
                     and value.get("outer_container_recovery_mandatory") is True
                     and value.get("controller_hard_kill_covered") is True
                     and value.get("recovery_receipt_required_after_every_outcome") is True
                     and value.get("recovery_output_root") == str(root)
                     and value.get("external_cleanup_reserved") is True,
                     "independent qualified outer group AND daemon-container recovery")
                need(type(value.get("external_cleanup_envelope_sha256")) is str
                     and re.fullmatch(r"[0-9a-f]{64}", value["external_cleanup_envelope_sha256"])
                     and type(value.get("recovery_deadline_seconds")) is int
                     and value["recovery_deadline_seconds"] == 180
                     and value.get("recovery_entry") == "recover"
                     and value.get("recovery_operator") == operation["sources"]["controller.py"],
                     "separately reserved finite independent outer cleanup")
                # The native PGID timer cannot remove Docker-daemon containers.
                # These authenticated external capabilities remain null/unqualified
                # in preparation; no in-process finally is a hard-kill guarantee.
                pinned(value["recovery_operator"], 131072, retain=False, charge=charge)
                pinned(value["recovery_protocol"], 1048576, retain=False, charge=charge)
        need(profile["deployment"]["image_id"] == operation["deployment"]["image_id"], "same scientific and operator image")
        del assets_body, layouts, source_bodies
        for kind, table in (("plane", inventory.planes), ("session", inventory.sessions)):
            for identity in sorted(table):
                if inventory.stopped or time.monotonic() >= deadline - operation["limits"]["cleanup_seconds"]:
                    break
                if kind == "session" and not all(inventory.planes[e]["state"] == "complete" for e in inventory.members[identity]):
                    continue
                outcome = run_unit(operation, inventory=inventory, profile=profile, adapter=adapter,
                    exporter=exporter, bank=bank, legacy=legacy, formats=formats, kind=kind, identity=identity,
                    layouts=refs, host_deadline=deadline, operation_sha=sha)
                if outcome.get("safe_for_further_dispatch") is not True:
                    inventory.stopped = True
                    break
        report = inventory.finalize()
        publish(root / "CONTROLLER_PENDING.json", {"operation_sha256": sha, "inventory": report,
            "source_setup_read_bytes_charged": setup_read, "startup_requested_write_bytes": counters["requested"],
            "native_context": context, "outer_native_group_absence_required": True,
            "outer_owned_container_recovery_and_absence_required": True,
            "surviving_recovery_records": "control-{plane|session}-{original_id}/{CREATE_INTENT,CREATED,CONFIG,ABSENCE}.json",
            "benchmark_ready": False}, 8192, counters)
        return 0 if all(r["state"] == "complete" for r in inventory.sessions.values()) else 1
    except BaseException as exc:
        if inventory is not None and not inventory.finalized:
            try:
                inventory.finalize(interrupted=True)
            except BaseException:
                pass
        try:
            publish(root / "CONTROLLER_FAILURE.json", {"operation_sha256": sha,
                "error": type(exc).__name__ + ": " + str(exc)[:256], "inventory_initialized": inventory is not None,
                "source_setup_read_bytes_charged": setup_read, "closure_unknown": True,
                "outer_native_group_absence_required": True,
                "outer_owned_container_recovery_and_absence_required": True}, 8192, counters)
        except BaseException:
            pass
        return 1


def recover_main(path, sha, *, authority_path, authority_sha):
    """One selected pending unit only; no create/start/exec/provider path.

    A separate root-native operation must already have reserved this recovery.
    It authenticates the old group's closure and exact immutable intent. An
    absence snapshot without a saved CREATED or observed owned object cannot
    settle a potentially unfinished daemon create. There is no polling retry.
    """
    started = time.monotonic()
    rp = ordinary(path)
    recovery = strict(pinned({"path": str(rp), "bytes": rp.stat().st_size, "sha256": sha}, 65536))
    need(set(recovery) == {"schema", "selected", "runtime_qualified", "authority_policy_sha256", "original_operation", "native", "kind", "identity",
         "startup", "reservation", "create_intent", "created", "prior_group_closure", "output_root", "envelope"}
         and recovery["schema"] == "neural063-portable-contained-recovery-v1"
         and recovery["selected"] is True and recovery["runtime_qualified"] is True,
         "inactive or unresolved fixed recovery")
    cap = recovery["envelope"]
    need(set(cap) == COUNTERS and all(type(v) is int and v >= 0 for v in cap.values())
         and 270336 <= cap["control_bytes"] <= 1048576
         and cap["host_write_bytes"] >= cap["control_bytes"]
         and 0 < cap["source_setup_read_bytes"] <= 268435456 and cap["closure_seconds"] >= 30
         and all(cap[k] == 0 for k in ("http_requests", "http_response_body_bytes", "http_header_reservation_bytes",
                 "logical_read_bytes", "export_read_bytes", "worker_artifact_write_bytes", "worker_control_bytes")),
         "complete finite externally reserved cleanup envelope")
    descriptor(recovery["original_operation"], 1048576)
    descriptor(recovery["native"]["protocol"], 8388608)
    bootstrap = (65537 + recovery["original_operation"]["bytes"] + 1
                 + 2 * (4194304 + 1) + recovery["native"]["protocol"]["bytes"] + 1)
    need(bootstrap <= cap["source_setup_read_bytes"],
         "full root-pre-reserved recovery/op/protocol/ledger bootstrap before further reads")
    owner = recovery["original_operation"]["sha256"]
    op = strict(pinned(recovery["original_operation"], 1048576))
    validate_operation(op)
    need(recovery["authority_policy_sha256"] == authority_sha == op["authority_policy_sha256"],
         "recovery uses the same independent operation authority")
    authority = authority_policy(authority_path, authority_sha, op)
    need(recovery["native"]["id"] != op["native"]["id"], "independent new root-native recovery")
    scope = {**op, "native": recovery["native"],
             "limits": {"whole_seconds": 180, "cleanup_seconds": 30,
                        "ready_attempts": 1, "ready_interval_seconds": 1}}
    bootstrap = max(bootstrap, authority_read_bound(authority, scope) + 65537)
    need(bootstrap <= cap["source_setup_read_bytes"], "complete portable recovery authority bootstrap")
    context = native_gate(scope, rp, sha, authority=authority, authority_path=authority_path,
                          authority_sha=authority_sha, mode="recover", operation_payload=recovery)
    end = started + 170
    kind, identity = recovery["kind"], recovery["identity"]
    need(kind in ("plane", "session") and type(identity) is str and re.fullmatch(r"[0-9]{1,20}", identity),
         "one exact pending original unit")
    oldroot = ordinary(op["output_root"], directory=True)
    root = ordinary(recovery["output_root"])
    need(root == oldroot / ("recovery-" + recovery["native"]["id"]) and not root.exists(), "one fresh exact recovery namespace")
    root.mkdir(mode=0o700)
    # All preceding writers share C-8192; exactly one final-result attempt owns the rest.
    counters = {"cap": cap["control_bytes"] - 8192, "requested": 0, "confirmed": 0, "uncertain": False,
                "cleanup_mode": True}
    publish(root / "RECOVERY_RESERVATION.json", {"owner": "root", "recovery_sha256": sha,
        "original_operation_sha256": owner, "envelope": cap, "no_refund": True,
        "native_context": context}, 8192, counters)
    read_charged = bootstrap
    def charge(n):
        nonlocal read_charged
        read_charged += n
        need(read_charged <= cap["source_setup_read_bytes"], "bounded recovery input/source reads")
    result = {"schema": "neural063-contained-recovery-result-v1", "recovery_sha256": sha,
              "original_operation_sha256": owner, "kind": kind, "identity": identity,
              "container_absent_observed": False, "create_identity_resolved": False,
              "cli_custody_complete": False, "container_recovery_complete": False,
              "outer_recovery_group_absence_required": True, "no_refund": True}
    docker = None
    errors = []
    try:
        charge(0)
        for key in ("docker", "host_python", "timer"):
            authenticate_runtime(op["runtime"][key], charge)
        if op["runtime"]["launcher"]["kind"] == "qualified_arch":
            authenticate_runtime(op["runtime"]["launcher"]["executable"], charge)
        helpers = op["helpers"]
        pinned(op["sources"]["controller.py"], 131072, retain=False, charge=charge)
        old_control = oldroot / ("control-" + kind + "-" + identity)
        for key, expected in (("startup", oldroot / "STARTUP.json"),
                              ("reservation", oldroot / (kind + "-" + identity + "-reservation.json")),
                              ("create_intent", old_control / "CREATE_INTENT.json")):
            need(recovery[key]["path"] == str(expected), "exact durable original custody path")
        startup = strict(pinned(recovery["startup"], 8192, charge=charge))
        need(startup.get("schema") == "neural063-startup-reservation-v1" and startup.get("owner") == owner
             and startup.get("envelope") == op["startup_envelope"] and startup.get("no_refund") is True,
             "same root-reserved original operation")
        reservation = strict(pinned(recovery["reservation"], 8192, charge=charge))
        need(reservation.get("owner") == owner and reservation.get("kind") == kind
             and reservation.get("identity") == identity and reservation.get("no_refund") is True,
             "same dispatched original unit")
        reservation_sha = recovery["reservation"]["sha256"]
        name = "n063-" + owner[:16] + "-" + kind + "-" + identity
        intent = strict(pinned(recovery["create_intent"], 8192, charge=charge))
        need(intent == {"owner": owner, "name": name, "kind": kind, "identity": identity,
                        "reservation_sha256": reservation_sha}, "exact durable single-create intent")
        oldgroup = strict(pinned(recovery["prior_group_closure"], 65536, charge=charge))
        need(oldgroup.get("schema") == "neural063-native-group-closure-v1"
             and oldgroup.get("operation_sha256") == owner and oldgroup.get("native_id") == op["native"]["id"]
             and oldgroup.get("identity_verified") is True and oldgroup.get("group_absent") is True
             and oldgroup.get("authority_policy_sha256") == authority_sha,
             "original native group already independently closed")
        cid = None
        if recovery["created"] is not None:
            need(recovery["created"]["path"] == str(old_control / "CREATED.json"), "exact saved created-ID path")
            created = strict(pinned(recovery["created"], 8192, charge=charge))
            need(set(created) == {"id"} and type(created["id"]) is str and re.fullmatch(r"[0-9a-f]{64}", created["id"]),
                 "complete original returned create ID")
            cid = created["id"]
            result["create_identity_resolved"] = True
        bank = loaded("_n063_recovery_bank", pinned(helpers["bank"], 65536, charge=charge), helpers["bank"]["path"])
        legacy = loaded("_n063_recovery_absence", pinned(helpers["legacy"], 65536, charge=charge), helpers["legacy"]["path"])
        formats = strict(pinned(helpers["formats"], 8192, charge=charge))
        bank.DOCKER, bank.ENDPOINT = op["runtime"]["docker"]["path"], op["deployment"]["endpoint"]
        (root / "cli").mkdir(mode=0o700)
        journal = UnitJournal(root / "cli", counters, 0)
        docker = bank.Docker(journal, bank.stop_cli_leader)
        calls = 0
        custody = True
        def call(argv):
            nonlocal calls, custody
            need(calls < 3 and (argv[:2] == ["rm", "--force"] or argv[:3] == ["inspect", "--type", "container"]),
                 "only three fixed owned recovery calls")
            calls += 1
            need(time.monotonic() + 2 < end, "independent recovery common deadline")
            try:
                row = docker.call(argv, min(end - 1, time.monotonic() + 10), cap=8192, cleanup=True)
            except BaseException:
                custody = False
                raise
            if row.get("cleanup", {}).get("leader_reaped") is not True or row.get("error_type") or row.get("diagnostic_publication_errors"):
                custody = False
            return row
        target = cid or name
        first = call(["inspect", "--type", "container", target, "--format", formats["container_ownership"]])
        if legacy.absent(first, target):
            result["container_absent_observed"] = True
            # No CREATED + no observed object: daemon create could still be unresolved.
        else:
            need(first["returncode"] == 0 and not first["stderr"], "complete recovery ownership inspection")
            value = strict(first["stdout"])
            probe = types.SimpleNamespace(op=op, name=name, owner=owner, kind=kind, identity=identity,
                      reservation={"reservation_sha256": reservation_sha})
            cid = Unit.ownership(probe, value, cid)
            result["create_identity_resolved"] = True
            result["container_id"] = cid
            # Publication failure is retained but cannot prevent owned cleanup.
            try:
                publish(root / "RECOVERY_OWNERSHIP.json", value, 8192, counters)
            except BaseException as exc:
                custody = False
                errors.append(type(exc).__name__)
            try:
                removed = call(["rm", "--force", cid])
                if removed["returncode"] != 0 or removed["stderr"]:
                    errors.append("owned removal command incomplete")
            except BaseException as exc:
                errors.append(type(exc).__name__)
            final = call(["inspect", "--type", "container", cid, "--format", formats["container_absence"]])
            result["container_absent_observed"] = legacy.absent(final, cid)
        result["cli_custody_complete"] = custody and docker.quiescent is True
        result["container_recovery_complete"] = (result["container_absent_observed"]
             and result["create_identity_resolved"] and result["cli_custody_complete"]
             and not errors and time.monotonic() < end)
    except BaseException as exc:
        errors.append(type(exc).__name__ + ": " + str(exc)[:256])
    result.update(errors=errors[:8], source_setup_bytes_charged=read_charged,
                  source_control_requested_bytes=counters["requested"],
                  source_control_confirmed_bytes=counters["confirmed"])
    counters["cap"] = cap["control_bytes"]
    publish(root / "RECOVERY_RESULT.json", result, 8192, counters)
    return 0 if result["container_recovery_complete"] else 1


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if args == ["start"]:
        inside_start()
    if args == ["ready"]:
        return inside_ready()
    need(len(args) == 9 and args[0] in ("host", "recover") and args[1] == "--authority"
         and args[3] == "--authority-sha256" and args[5] == "--operation" and args[7] == "--sha256"
         and all(re.fullmatch(r"[0-9a-f]{64}", args[i]) for i in (4, 8)), "fixed externally authorized entry")
    call = host_main if args[0] == "host" else recover_main
    return call(args[6], args[8], authority_path=args[2], authority_sha=args[4])


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        os.write(2, ("N063 controller refused: " + type(exc).__name__ + "\n").encode())
        raise SystemExit(1)
