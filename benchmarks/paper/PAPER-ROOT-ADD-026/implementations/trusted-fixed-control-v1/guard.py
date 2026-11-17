"""Stdlib-only admission for the trusted temporal fixed control.

This is a cooperative control guard, not a hostile-code sandbox. Runtime pins
cover selected Python/framework/watchdog and the installed NumPy distribution,
not the OS or complete standard-library dependency closure. No scientific data
is read here. Physical loader/import I/O is outside the logical read meters.
"""
from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import resource
import signal
import stat
import sys
import time

MIB = 1024 ** 2
THREAD_ENV = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
              "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS", "BLIS_NUM_THREADS",
              "POLARS_MAX_THREADS", "RAYON_NUM_THREADS")
CONTROLLER_SHA = "a99a83ae6638dbae205badf041230260d4d075dfc3b7e50a50c7bdb87293b761"
RUNTIME_SHA = "3ca5b9bdd9350453396ece1bdbc24517a89fe8271de33c3f9bdc95b4924d2771"
RUNTIME_BYTES = 100563
AUTHORITY = Path("/Users/nicholas/Documents/Codex/benchmark-engineering-evidence/comprehensive-revision-20261116-v2")
LIMITS = {"threads": 1, "ram_bytes": 1024 ** 3,
          "cpu_soft_seconds": 840, "cpu_hard_seconds": 850,
          "worker_wall_seconds": 900, "metadata_read_cap_bytes": 64 * MIB,
          "runtime_read_cap_bytes": 64 * MIB}


class GuardError(ValueError):
    pass


def require(ok, reason):
    if not ok:
        raise GuardError(reason)


def integer(value, lower=0, upper=2 ** 63 - 1):
    require(type(value) is int and lower <= value <= upper, "invalid bounded integer")
    return value


def digest(value):
    require(isinstance(value, str) and len(value) == 64 and
            all(c in "0123456789abcdef" for c in value), "invalid SHA256")
    return value


def unique_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key: " + key)
            result[key] = value
        return result
    def bad_constant(value):
        raise GuardError("nonfinite JSON: " + value)
    try:
        return json.loads(data, object_pairs_hook=pairs, parse_constant=bad_constant)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise GuardError("invalid JSON") from exc


def canonical(path, exists=True):
    require(isinstance(path, (str, Path)), "invalid path")
    p = Path(path)
    require(p.is_absolute() and str(p) == str(path), "path must be absolute and normalized")
    require(p.resolve(strict=exists) == p, "symlink or noncanonical path")
    return p


class ReadMeters:
    """Precharge maximum attempted bytes; retain charge even on any failure."""
    def __init__(self):
        self.buckets = {name: {"cap_bytes": 64 * MIB, "attempts": 0,
                              "reserved_attempt_bytes": 0, "returned_bytes": 0,
                              "failed_attempts": 0}
                        for name in ("metadata", "runtime")}

    def begin(self, kind, limit):
        row = self.buckets[kind]
        integer(limit, 0, 8 * MIB)
        charge = limit + 1  # one-byte overlength probe, also charged on failure
        require(row["reserved_attempt_bytes"] + charge <= row["cap_bytes"],
                kind + " logical read allowance exhausted")
        row["reserved_attempt_bytes"] += charge
        row["attempts"] += 1
        return row

    def snapshot(self):
        return {"logical_reads": {k: dict(v) for k, v in self.buckets.items()},
                "physical_io_measured": False,
                "unmetered_io": "interpreter/stdlib/shared-library/import loader reads; filesystem metadata",
                "scientific_reads": "separately metered by fixed control core"}


def bounded_read(path, limit, meters, kind="metadata", expected_size=None):
    row = meters.begin(kind, limit)
    fd = None
    try:
        p = canonical(path)
        fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1,
                "read requires ordinary single-link file")
        require(before.st_size <= limit, "file exceeds declared read bound")
        if expected_size is not None:
            require(before.st_size == expected_size, "file size changed")
        with os.fdopen(fd, "rb") as handle:
            fd = None
            data = handle.read(limit + 1)
            row["returned_bytes"] += len(data)
            after = os.fstat(handle.fileno())
        require(len(data) <= limit, "read exceeds bound")
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns,
                 before.st_ctime_ns) ==
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns,
                 after.st_ctime_ns), "file mutated during read")
        require(len(data) == before.st_size, "short read")
        return data
    except BaseException:
        row["failed_attempts"] += 1
        raise
    finally:
        if fd is not None:
            os.close(fd)


def read_pin(pin, meters, kind="metadata"):
    require(isinstance(pin, dict), "invalid file pin")
    size = integer(pin.get("bytes"), 0, 8 * MIB)
    sha = digest(pin.get("sha256"))
    data = bounded_read(pin["path"], size, meters, kind, expected_size=size)
    require(hashlib.sha256(data).hexdigest() == sha, "file hash mismatch: " + pin["path"])
    return data


def _one(rows, item_id, label):
    require(isinstance(rows, list), label + " list missing")
    selected = [r for r in rows if isinstance(r, dict) and r.get("id") == item_id]
    require(len(selected) == 1, label + " id absent or duplicated")
    return selected[0]


def check_ledger(document, protocol, protocol_path, sha, parent_pid):
    """Return False only for the controller's narrow pre-child-pid window."""
    require(document.get("schema") == "comprehensive_revision_resources_v1", "ledger schema")
    owner = protocol["owner"]
    pin = {"path": str(protocol_path), "sha256": sha}
    approval = _one(document.get("approved_native_protocols"), protocol["approval_id"], "approval")
    require(approval.get("owner") == owner and approval.get("approved_by") == "/root" and
            approval.get("protocol") == pin, "root approval does not match exact protocol")
    native = _one(document.get("native_runs"), protocol["native_run_id"], "native run")
    running = [r for r in document["native_runs"] if r.get("status") == "running"]
    require(len(running) == 1 and running[0] == native, "exclusive native lease missing")
    require(native.get("owner") == owner and native.get("approval_id") == protocol["approval_id"]
            and native.get("protocol") == pin, "native owner or protocol mismatch")
    template = protocol["launch"]["native_command"]
    require(isinstance(template, list) and all(isinstance(v, str) for v in template)
            and template.count("{protocol_sha256}") == 1, "exact launch template required")
    command = [sha if v == "{protocol_sha256}" else v for v in template]
    require(native.get("command") == command, "native command mismatch")
    require(native.get("cwd") == protocol["launch"]["cwd"] == str(Path.cwd()), "native cwd mismatch")
    require(native.get("requested_threads") == 1 and
            native.get("declared_max_working_ram_bytes") == 1024 ** 3,
            "native resources mismatch")
    integer(native.get("coordinator_pid"), 1)
    require(document.get("native_execution", {}).get("maximum_concurrent_heavy_jobs") == 1,
            "native concurrency changed")
    output = protocol["output"]
    reservation = _one(document.get("reservations"), output["reservation_id"], "artifact reservation")
    require(reservation.get("status") == "active" and reservation.get("kind") == "artifact" and
            reservation.get("owner") == owner and reservation.get("destination") == output["path"] and
            reservation.get("reserved_bytes") == output["reserved_bytes"],
            "output reservation not exact and active")
    if "child_pid" not in native:
        return False
    require(type(native["child_pid"]) is int and native["child_pid"] == parent_pid and parent_pid > 1,
            "worker is not child of registered watchdog")
    return True


def await_ledger(protocol, path, sha, meters, *, monotonic=time.monotonic,
                 sleep=time.sleep, parent_pid=None):
    parent_pid = os.getppid() if parent_pid is None else parent_pid
    stop = monotonic() + 1.0
    for attempt in range(21):
        require(monotonic() < stop, "controller child-pid registration deadline")
        document = unique_json(bounded_read(protocol["resource_ledger"], 2 * MIB, meters))
        ready = check_ledger(document, protocol, path, sha, parent_pid)
        require(monotonic() <= stop, "controller child-pid registration deadline")
        if ready:
            return {"ledger_attempts": attempt + 1, "registered_watchdog_pid": parent_pid}
        remaining = stop - monotonic()
        require(remaining > 0 and attempt < 20, "controller child-pid registration deadline")
        sleep(min(0.05, remaining))
    raise GuardError("unreachable ledger poll state")


def fresh_output(output):
    require(output.get("reserved_bytes") == 128 * MIB, "artifact reservation must be 128 MiB")
    p = canonical(output["path"], exists=False)
    require(not p.exists() and not p.is_symlink(), "output already exists; resume forbidden")
    if not p.parent.exists():
        require(output.get("allow_create_parent") is True and p.parent.parent.is_dir(),
                "only one missing output parent may be created")
        canonical(p.parent.parent)
    else:
        require(p.parent.is_dir(), "output parent is not directory")
        canonical(p.parent)
    return p


def record_inventory(site, rows, pyc_pins):
    """Resolve a bounded, duplicate-free RECORD; no arbitrary ../ traversal."""
    site = canonical(site)
    require(isinstance(rows, list) and len(rows) <= 2048, "RECORD row limit")
    pins = {p["path"]: p for p in pyc_pins}
    require(len(pins) == len(pyc_pins), "duplicate pyc pin")
    allowed_outside = {"../../../bin/f2py", "../../../bin/numpy-config"}
    members, internal, blanks, seen = [], set(), set(), set()
    total = 0
    for row in rows:
        require(len(row) == 3, "RECORD row width")
        rel, encoded, size_text = row
        require(rel not in seen, "duplicate RECORD path")
        seen.add(rel)
        if rel in allowed_outside:
            p = (site / rel).resolve(strict=True)
            require(p == Path("/opt/homebrew/bin") / PurePosixPath(rel).name,
                    "unexpected entrypoint target")
        else:
            pure = PurePosixPath(rel)
            require(not pure.is_absolute() and ".." not in pure.parts and "." not in pure.parts
                    and str(pure) == rel and len(pure.parts) >= 2 and
                    pure.parts[0] in {"numpy", "numpy-2.4.6.dist-info"}, "unallowed RECORD path")
            p = canonical(site / rel)
            internal.add(rel)
        if encoded:
            require(encoded.startswith("sha256=") and len(encoded) == 50,
                    "RECORD must use SHA256")
            token = encoded[7:]
            try:
                decoded = base64.b64decode(token + "=", altchars=b"-_", validate=True)
            except ValueError as exc:
                raise GuardError("invalid RECORD digest") from exc
            require(len(decoded) == 32 and base64.urlsafe_b64encode(decoded).decode().rstrip("=") == token,
                    "noncanonical RECORD digest")
            require(size_text.isascii() and size_text.isdecimal(), "RECORD size invalid")
            size = integer(int(size_text), 0, 8 * MIB)
            members.append({"path": str(p), "bytes": size, "sha256": decoded.hex()})
            total += size
        else:
            require(size_text == "", "blank digest must have blank size")
            blanks.add(rel)
            if rel == "numpy-2.4.6.dist-info/RECORD":
                continue
            require(rel.endswith(".pyc") and rel in pins, "unhashed member is not pinned pyc")
            pin = pins[rel]
            members.append({"path": str(p), "bytes": integer(pin["bytes"], 0, 8 * MIB),
                            "sha256": digest(pin["sha256"])})
    require(blanks == set(pins) | {"numpy-2.4.6.dist-info/RECORD"}, "pyc pin coverage differs")
    observed = set()
    visits = 0
    for root in (site / "numpy", site / "numpy-2.4.6.dist-info"):
        require(root.is_dir() and not root.is_symlink(), "package root is not ordinary directory")
        pending = [root]
        while pending:
            with os.scandir(pending.pop()) as entries:
                for entry in entries:
                    visits += 1
                    require(visits <= 4096, "package inventory limit")
                    p = Path(entry.path)
                    mode = entry.stat(follow_symlinks=False).st_mode
                    require(not stat.S_ISLNK(mode), "package inventory contains symlink")
                    if stat.S_ISDIR(mode):
                        pending.append(p)
                    else:
                        require(stat.S_ISREG(mode) and p.stat().st_nlink == 1, "special package member")
                        observed.add(p.relative_to(site).as_posix())
    require(observed == internal, "package has missing or extra files")
    return members, {"record_rows": len(rows), "hashed_member_count": len(rows) - len(blanks),
                     "hashed_member_bytes": total, "pyc_member_count": len(pins),
                     "pyc_member_bytes": sum(p["bytes"] for p in pyc_pins),
                     "complete_internal_inventory_count": len(internal)}


def verify_distribution(spec, meters):
    numpy = spec["numpy"]
    record_data = read_pin(numpy["record"], meters, "runtime")
    rows = list(csv.reader(io.StringIO(record_data.decode("utf-8"))))
    members, counts = record_inventory(numpy["site_packages"], rows, numpy["pyc_pins"])
    for name, count in counts.items():
        require(numpy[name] == count, "NumPy inventory count mismatch: " + name)
    for pin in members:
        read_pin(pin, meters, "runtime")
    return counts


def apply_limits():
    require(sys.flags.isolated == 1 and sys.flags.no_site == 1 and sys.flags.dont_write_bytecode == 1,
            "worker requires Python -I -S -B")
    require(not any(k == "numpy" or k.startswith("numpy.") for k in sys.modules),
            "NumPy was imported before admission")
    require(all(os.environ.get(k) == "1" for k in THREAD_ENV), "one-thread environment missing")
    soft, hard = resource.getrlimit(resource.RLIMIT_CPU)
    finite = lambda value, wanted: wanted if value == resource.RLIM_INFINITY else min(value, wanted)
    new_hard = finite(hard, 850)
    resource.setrlimit(resource.RLIMIT_CPU, (min(finite(soft, 840), new_hard), new_hard))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    def deadline(signum, frame):
        raise GuardError("worker deadline or termination signal")
    for sig in (signal.SIGALRM, signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, deadline)
    signal.setitimer(signal.ITIMER_REAL, 900)
    return time.monotonic()


class Admission:
    def __init__(self, protocol, path, sha, meters, started, runtime, runtime_counts, lease):
        self.protocol = protocol
        self.protocol_path = path
        self.protocol_sha256 = sha
        self.meters = meters
        self.started = started
        self.runtime = runtime
        self.runtime_counts = runtime_counts
        self.lease = lease
        self.output_path = fresh_output(protocol["output"])
        self.created = False
        self.numpy_activated = False

    def checkpoint(self):
        require(time.monotonic() - self.started <= 900, "worker wall deadline")
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        peak_bytes = int(peak if sys.platform == "darwin" else peak * 1024)
        require(peak_bytes <= 1024 ** 3, "observed peak RSS exceeds 1 GiB")
        return {"wall_seconds": time.monotonic() - self.started, "peak_rss_bytes": peak_bytes,
                "ram_enforcement": "observed peak-RSS checkpoints; not an OS hard RAM limit"}

    def read_pin(self, pin, kind="metadata"):
        self.checkpoint()
        result = read_pin(pin, self.meters, kind)
        self.checkpoint()
        return result

    def create_output(self):
        self.checkpoint()
        require(not self.created, "output already admitted")
        # Recheck the active lease/reservation after runtime authentication.
        document = unique_json(bounded_read(self.protocol["resource_ledger"], 2 * MIB, self.meters))
        require(check_ledger(document, self.protocol, self.protocol_path,
                             self.protocol_sha256, os.getppid()),
                "registered child PID disappeared after initial admission")
        p = fresh_output(self.protocol["output"])
        if not p.parent.exists():
            p.parent.mkdir(mode=0o700)
        p.mkdir(mode=0o700)  # exclusive; races fail instead of reusing an existing path
        self.created = True
        return p

    def activate_numpy(self):
        self.checkpoint()
        require(self.created and not self.numpy_activated, "NumPy requires new admitted output")
        require("numpy" not in sys.modules, "NumPy already imported")
        site = self.runtime["numpy"]["site_packages"]
        require(site not in sys.path, "site was activated before admission")
        sys.path.append(site)  # no site module, .pth processing, or search-path precedence change
        import numpy
        require(numpy.__version__ == self.runtime["numpy"]["version"] and
                Path(numpy.__file__).resolve() == Path(site) / "numpy" / "__init__.py",
                "activated NumPy identity mismatch")
        self.numpy_activated = True
        self.checkpoint()
        return numpy

    def report(self):
        return {"runtime_verified": self.runtime_counts, "numpy_activated": self.numpy_activated,
                "runtime_scope": self.runtime["scope"], "lease": self.lease,
                "resources": self.checkpoint(), **self.meters.snapshot()}


def bootstrap(protocol_path, expected_sha):
    meters = ReadMeters()
    try:
        started = apply_limits()
        return _bootstrap_verified(protocol_path, expected_sha, started, meters)
    except BaseException as exc:
        # The entry must include this snapshot in its bounded failure receipt.
        # Charges survive authentication, deadline, filesystem and import errors.
        exc.guard_read_meters = meters.snapshot()
        raise


def _bootstrap_verified(protocol_path, expected_sha, started, meters):
    path = canonical(protocol_path)
    sha = digest(expected_sha)
    raw = bounded_read(path, 256 * 1024, meters)
    require(hashlib.sha256(raw).hexdigest() == sha, "frozen protocol mismatch")
    protocol = unique_json(raw)
    require(protocol.get("schema") == "temporal026-full-fixed-control-protocol/v1" and
            protocol.get("owner") == "build_temporal_prediction", "protocol schema or owner mismatch")
    require(protocol.get("limits") == LIMITS, "protocol resource limits differ from guard")
    require(protocol.get("resource_ledger") == str(AUTHORITY / "RESOURCES.json"),
            "resource ledger is not the authoritative coordinator ledger")
    fresh_output(protocol["output"])
    require(protocol["resource_controller"]["sha256"] == CONTROLLER_SHA and
            protocol["resource_controller"]["path"] == str(AUTHORITY / "resource_control.py"),
            "controller identity changed")
    read_pin(protocol["resource_controller"], meters)
    lease = await_ledger(protocol, path, sha, meters)
    runtime_pin = protocol["runtime_spec"]
    require(runtime_pin.get("sha256") == RUNTIME_SHA and runtime_pin.get("bytes") == RUNTIME_BYTES,
            "runtime specification differs from frozen construction")
    runtime = unique_json(read_pin(runtime_pin, meters))
    require(runtime["schema"] == "temporal026-fixed-control-runtime-spec/v1", "runtime schema")
    require(Path(sys.executable).resolve() == Path(runtime["python"]["path"]) and
            sys.version == runtime["python_full_version"], "interpreter identity mismatch")
    for name in ("python", "python_framework", "watchdog"):
        read_pin(runtime[name], meters, "runtime")
    launch = protocol["launch"]["native_command"]
    expected_prefix = [runtime["watchdog"]["path"], "--signal=TERM", "--kill-after=10s", "900s",
                       runtime["python"]["path"], "-I", "-S", "-B"]
    require(launch[:8] == expected_prefix and len(launch) == 13 and
            launch[9:] == ["--protocol", str(path), "--protocol-sha256", "{protocol_sha256}"],
            "watchdog/Python/entry invocation differs")
    require(Path(launch[8]).name == "run_control.py", "unexpected worker entry")
    files = protocol["source_files"]
    require(isinstance(files, list) and 2 <= len(files) <= 32, "source pin count")
    paths = [pin["path"] for pin in files]
    require(len(set(paths)) == len(paths) and str(Path(__file__).resolve()) in paths and
            launch[8] in paths, "guard and entry must be uniquely pinned")
    require(sum(integer(p["bytes"], 0, 8 * MIB) for p in files) <= 4 * MIB, "source pin bytes limit")
    for pin in files:
        read_pin(pin, meters)
    counts = verify_distribution(runtime, meters)
    admission = Admission(protocol, path, sha, meters, started, runtime, counts, lease)
    admission.checkpoint()
    return admission
