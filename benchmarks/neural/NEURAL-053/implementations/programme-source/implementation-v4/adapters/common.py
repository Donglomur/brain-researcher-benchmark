"""Bounded artifact/configuration and inherited-budget primitives."""
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import threading
import time


class AdapterError(ValueError):
    def __init__(self, message, evidence=None):
        super().__init__(message)
        self.evidence = evidence or {}


def need(condition, message):
    if not condition:
        raise AdapterError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def integer(value, name, minimum=0):
    need(type(value) is int and value >= minimum, name + " must be an exact nonnegative integer")
    return value


def positive(value, name):
    need(type(value) in (int, float) and math.isfinite(value) and value > 0, name + " must be finite positive")
    return value


def file_pin(path, ceiling=None, budget=None):
    path = Path(path)
    st = path.lstat()
    need(stat.S_ISREG(st.st_mode) and not path.is_symlink(), "ordinary artifact file required")
    if ceiling is not None:
        need(st.st_size <= ceiling, "artifact exceeds declared read cap")
    if budget:
        budget.charge("source_read", st.st_size)
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            h.update(block)
            if budget:
                budget.check_clock()
    after = path.stat()
    need((st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns) ==
         (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), "artifact changed during read")
    return {"path": str(path.resolve()), "bytes": st.st_size, "sha256": h.hexdigest()}


def authenticate(pin, budget=None):
    need(isinstance(pin, dict) and {"path", "bytes", "sha256"} <= set(pin), "complete artifact descriptor")
    integer(pin["bytes"], "artifact size")
    actual = file_pin(pin["path"], pin["bytes"], budget)
    need(actual["bytes"] == pin["bytes"] and actual["sha256"] == pin["sha256"], "artifact identity mismatch")
    return actual


def json_exact(pin, budget=None, cap=16777216):
    authenticate(pin, budget)
    need(pin["bytes"] <= cap, "JSON descriptor cap")
    if budget:
        budget.charge("source_read", pin["bytes"])
    data = Path(pin["path"]).read_bytes()
    need(len(data) == pin["bytes"] and hashlib.sha256(data).hexdigest() == pin["sha256"], "JSON changed after pin")
    return json.loads(data)


def write_fresh(path, data, budget):
    path = Path(path)
    need(isinstance(data, bytes), "bytes-only write")
    budget.charge("artifact_write", len(data))
    with path.open("xb") as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())
    budget.check_clock()
    return {"path": str(path.resolve()), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def copy_exact(pin, destination, budget):
    """One authenticated copy; original descriptor never replaced by current hash."""
    source = Path(pin["path"])
    st = source.lstat()
    need(stat.S_ISREG(st.st_mode) and not source.is_symlink() and st.st_size == pin["bytes"], "staged exact ordinary source")
    budget.charge("source_read", st.st_size)
    budget.charge("artifact_write", st.st_size)
    h = hashlib.sha256(); count = 0
    with source.open("rb") as inp, Path(destination).open("xb") as out:
        for block in iter(lambda: inp.read(65536), b""):
            budget.check_clock(); count += len(block)
            need(count <= pin["bytes"], "source grew during staging")
            h.update(block); out.write(block)
        out.flush(); os.fsync(out.fileno())
    need(count == pin["bytes"] and h.hexdigest() == pin["sha256"], "staged source differs from approved pin")
    Path(destination).chmod(0o444)
    return {"path": str(Path(destination).resolve()), "bytes": count, "sha256": h.hexdigest()}


class CaseBudget:
    """Equal per-case envelope nested inside the unchanged whole-study ledger."""
    def __init__(self, parent, limits, wall_seconds):
        self.parent = parent
        self.origin_monotonic = parent.origin_monotonic
        self.started_monotonic = time.monotonic()
        self.deadline_monotonic = min(parent.deadline_monotonic, self.started_monotonic + positive(wall_seconds, "case wall"))
        self.limits = dict(limits)
        need(all(type(v) is int and v >= 0 for v in self.limits.values()), "exact case counters")
        self.used = {k: 0 for k in self.limits}
        self._lock = threading.Lock()

    def check_clock(self):
        self.parent.check_clock()
        need(time.monotonic() <= self.deadline_monotonic, "original/case deadline expired; no reset")

    def charge(self, name, amount=1):
        self.check_clock(); integer(amount, "resource charge")
        with self._lock:
            need(name in self.limits and self.used[name] + amount <= self.limits[name], "case budget exhausted: " + name)
            self.parent.charge(name, amount)
            self.used[name] += amount

    def snapshot(self):
        return {"origin_monotonic": self.origin_monotonic, "started_monotonic": self.started_monotonic,
                "deadline_monotonic": self.deadline_monotonic, "limits": self.limits, "used": dict(self.used)}


ADAPTER_FILES = ("__init__.py", "common.py", "process.py", "provider.py", "contexts.py", "worker.py")


class BoundAdapter:
    def __init__(self, config, budget, authorization, phase):
        need(isinstance(authorization, dict) and isinstance(authorization.get("approved"), frozenset), "protected operator approval set required")
        receipt = authorization.get("receipt")
        need(isinstance(receipt, dict) and digest(receipt) in authorization["approved"], "unapproved adapter activation")
        need(receipt.get("schema") == "neural053_full_run_admission_v1" and
             receipt.get("decision") == "accepted_exact_canonical_full_run", "canonical independently approved phase authority")
        bindings = receipt.get("bindings", {})
        need(bindings.get("phase") == phase and bindings.get("adapter_config_sha256") == digest(config), "phase/config binding mismatch")
        self.config = json.loads(canonical(config)); self.budget = budget
        self._validate_config()
        need(bindings.get("adapter_source_manifest_sha256") == digest(self.source_manifest()), "current concrete source manifest mismatch")
        self._bound_source_digest = bindings["adapter_source_manifest_sha256"]
        self._bound_config_digest = bindings["adapter_config_sha256"]
        self._authority_digest = digest(receipt)
        budget.check_clock()

    def _validate_config(self):
        c = self.config
        need(c.get("schema") == "neural053_production_adapters_v2", "explicit adapter config schema")
        need(set(c) == {"schema", "provider", "sandbox", "source", "workspace_root", "case_limits"}, "unknown/missing adapter config field")
        need(Path(c["workspace_root"]).is_absolute(), "absolute operator workspace root")
        s = c["sandbox"]
        need(set(s) == {"docker_binary", "docker_endpoint", "image_digest", "python", "memory_bytes", "cpus", "pids_limit", "tmpfs_bytes", "tool_seconds", "cleanup_seconds", "stream_cap_bytes", "workspace_cap_bytes", "poll_seconds"}, "exact sandbox configuration")
        need(type(s["docker_endpoint"]) is str and s["docker_endpoint"].startswith("unix:///"), "explicit local Docker socket required")
        need(s["image_digest"].startswith("sha256:") and len(s["image_digest"]) == 71, "immutable Docker image digest required")
        need(s["python"].startswith("/") and ".." not in Path(s["python"]).parts, "absolute container Python path")
        for name in ("memory_bytes", "pids_limit", "tmpfs_bytes", "stream_cap_bytes", "workspace_cap_bytes"):
            integer(s[name], name, 1)
        for name in ("cpus", "tool_seconds", "cleanup_seconds", "poll_seconds"):
            positive(s[name], name)
        required = {"provider_calls", "provider_tokens", "tool_calls", "source_read", "artifact_write", "stream_bytes", "wall_seconds"}
        need(set(c["case_limits"]) == required, "same explicit whole-case resource fields for both modes")
        for name in required - {"wall_seconds"}:
            integer(c["case_limits"][name], name)
        positive(c["case_limits"]["wall_seconds"], "case wall_seconds")
        need(s["tool_seconds"] >= c["case_limits"]["wall_seconds"],
             "one fixed program must be allowed the same whole-case wall envelope as investigation tools")

    def current_config(self):
        return json.loads(canonical(self.config))

    def source_manifest(self):
        return current_source_manifest(self.config, self.budget)

    def verify_current(self):
        need(digest(self.current_config()) == self._bound_config_digest and
             digest(self.source_manifest()) == self._bound_source_digest, "adapter source/config changed after admission")
        self.budget.check_clock()

    def new_budget(self):
        limits = dict(self.config["case_limits"]); wall = limits.pop("wall_seconds")
        return CaseBudget(self.budget, limits, wall)

    def stage_source(self, destination, budget):
        destination.mkdir(mode=0o755)
        for item in self.config["source"]["files"]:
            path = destination / item["path"]
            path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
            copy_exact({**item, "path": str(Path(self.config["source"]["root"]) / item["path"])}, path, budget)
        return destination

    def verify_staged_source(self, destination, budget):
        for item in self.config["source"]["files"]:
            authenticate({**item, "path": str(Path(destination) / item["path"])}, budget)


def current_source_manifest(config, budget):
        local = Path(__file__).resolve().parent
        adapter = [file_pin(local / name, 262144, budget) for name in ADAPTER_FILES]
        source = config["source"]
        need(set(source) == {"root", "files"} and Path(source["root"]).is_absolute(), "exact source closure root/files")
        rows, names = [], set()
        for item in source["files"]:
            name = item["path"]
            need(type(name) is str and name not in names and not Path(name).is_absolute() and ".." not in Path(name).parts, "unique relative source member")
            names.add(name)
            row = {**item, "path": str(Path(source["root"]) / name)}
            authenticate(row, budget)
            rows.append({"path": name, "bytes": item["bytes"], "sha256": item["sha256"]})
        need(rows, "complete nonempty captured source required")
        return {"schema": "neural053_adapter_source_manifest_v2", "adapters": adapter,
                "benchmark_root": source["root"], "benchmark": sorted(rows, key=lambda x: x["path"])}

