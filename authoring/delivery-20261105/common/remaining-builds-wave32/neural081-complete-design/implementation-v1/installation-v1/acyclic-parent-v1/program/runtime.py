"""Source-owned direct local engine execution; nothing launches on import.

No Docker CLI or numeric PID/PGID mutation. Original opaque input bodies are
never opened for content, hashed or copied here. All deployment qualification
must be independently admitted by the parent before Runtime construction.
"""
import hashlib
import http.client
import json
import math
import os
from pathlib import Path
import re
import socket
import stat
import struct
import threading
import time
import uuid
from urllib.parse import quote

import common as c
from transport.common import AdapterError

TRUSTED_KINDS = ("reference", "preparation", "grader")
TRUSTED_MODULES = {
    "reference": {"common", "protocol", "arrays", "custody", "model_io", "outputs", "numeric_worker", "numeric"},
    "preparation": {"common", "protocol", "arrays", "custody", "outputs", "preparation", "preparation_worker"},
    "grader": {"common", "protocol", "arrays", "custody", "outputs", "metrics", "grading", "closure", "schedule",
               "runtime", "host_observation", "candidate_runner", "transport", "transport.common", "transport.provider",
               "transport.process", "authority"},
}
KINDS = (*TRUSTED_KINDS, "fixed", "investigate", "author")
CANDIDATES = ("fixed", "investigate", "author")
FIELDS = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "st_mode", "st_nlink")
MASKED = ["/proc", "/sys", "/dev/mqueue", "/dev/shm"]
ENV = ["PATH=/usr/local/bin:/usr/bin:/bin", "HOME=/workspace", "TMPDIR=/workspace",
       "PYTHONDONTWRITEBYTECODE=1", "PYTHONNOUSERSITE=1", "OMP_NUM_THREADS=1",
       "OPENBLAS_NUM_THREADS=1", "MKL_NUM_THREADS=1", "NUMEXPR_NUM_THREADS=1"]


class Bridge:
    MAP = {"source_read": "read_bytes", "artifact_write": "write_bytes",
           "provider_calls": "provider_requests", "provider_tokens": "provider_tokens",
           "stream_bytes": "stream_bytes", "tool_calls": "native_processes"}
    def __init__(self, parent):
        self.parent = parent; self.origin_monotonic = parent.origin; self.deadline_monotonic = parent.end
    def check_clock(self): self.parent.check_clock()
    def charge(self, name, amount=1):
        c.need(name in self.MAP, "known transport counter"); self.parent.charge(self.MAP[name], amount)
    def snapshot(self): return self.parent.snapshot()


def validate_config(config):
    c.exact(config, ("engine_socket", "engine_api_version", "image_digest", "python", "user",
                    "pids_limit", "cpus", "tmpfs_bytes", "stream_cap_bytes", "workspace_cap_bytes",
                    "workspace_entry_cap", "cleanup_seconds", "poll_seconds", "engine_response_cap_bytes",
                    "engine_control_seconds", "qualification"))
    c.exact(config["engine_socket"], ("path", "device", "inode", "owner_uid"))
    c.absolute(config["engine_socket"]["path"])
    for key in ("device", "inode", "owner_uid"): c.integer(config["engine_socket"][key])
    c.need(type(config["engine_api_version"]) is str and re.fullmatch(r"v1\.\d{2}", config["engine_api_version"]), "selected exact engine API")
    c.need(type(config["image_digest"]) is str and config["image_digest"].startswith("sha256:"), "immutable installed image")
    c.digest(config["image_digest"][7:]); c.absolute(config["python"])
    c.need(type(config["user"]) is str and re.fullmatch(r"[1-9]\d*:\d+", config["user"]), "explicit nonroot UID:GID")
    c.need(os.geteuid() != 0 and config["user"] == str(os.geteuid()) + ":" + str(os.getegid()), "matched nonroot host/container ownership")
    c.need(type(config["pids_limit"]) is int and config["pids_limit"] == 1 and type(config["cpus"]) is int and config["cpus"] == 1, "one process and one CPU")
    c.need(config["stream_cap_bytes"] == 262144 and type(config["stream_cap_bytes"]) is int, "exact per-stream cap")
    c.need(type(config["cleanup_seconds"]) is int and config["cleanup_seconds"] == 120, "fixed failure closeout")
    for key in ("tmpfs_bytes", "workspace_cap_bytes", "workspace_entry_cap", "engine_response_cap_bytes"):
        c.integer(config[key], 1)
    c.need(config["engine_response_cap_bytes"] <= 2097152, "bounded engine response")
    for key in ("poll_seconds", "engine_control_seconds"):
        c.need(0 < c.finite(config[key]) <= 30, "bounded native control interval")
    c.exact(config["qualification"], ("engine", "clock", "namespace", "physical_io"))
    for value in config["qualification"].values(): c.descriptor(value)
    return config


def stamp(desc):
    """Open/fstat only: no original scientific body read or hash."""
    c.descriptor(desc, True); p = c.absolute(desc["path"])
    c.need(not any(q.is_symlink() for q in (p, *p.parents)), "ordinary exact mounted path")
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd); named = p.lstat()
        c.need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == desc["bytes"], "exact ordinary mounted extent")
        c.need(all(getattr(before, k) == getattr(named, k) for k in FIELDS), "opened mount identity")
        return {k: getattr(before, k) for k in FIELDS}
    finally: os.close(fd)


def relative(value):
    c.need(type(value) is str and value and not value.startswith("/") and "\\" not in value and
           all(part not in ("", ".", "..") for part in value.split("/")), "ordinary relative artifact path")
    return value


def _generic(target, kind):
    c.absolute(target)
    if kind == "author":
        c.need(target.startswith(("/tools/", "/action/", "/programme/")), "data-free author namespace")
    else:
        c.need(target.startswith(("/input/", "/models/", "/tools/", "/programme/", "/action/")), "candidate generic namespace")
    if target.startswith("/input/"):
        c.need(target in ("/input/query.npy", "/input/train.npy", "/input/train_labels.npy", "/input/train_rows.json", "/input/context.json"), "one query and complete training only")
    if target.startswith("/models/"):
        c.need(len(target.split("/")) >= 4 and target.split("/")[2] in ("BP_LDA", "TM_LDA", "RBF_KRR", "HISTORICAL_BP_LDA"), "current four model handles only")
    c.need(not target.endswith("/") and "," not in target, "canonical file mount")


def _mount_contract(mounts, kind, approved_sources, script):
    c.need(type(mounts) is list and mounts, "complete explicit file mount roster")
    targets = set(); sources = {}; script_source = None
    for item in mounts:
        c.exact(item, ("source", "target", "opaque_host")); c.descriptor(item["source"], True)
        c.need(type(item["opaque_host"]) is bool, "explicit host opacity")
        target = item["target"]; c.absolute(target)
        c.need(target not in targets, "unique mount target"); targets.add(target)
        path = item["source"]["path"]
        c.need(path not in sources or c.typed_equal(sources[path], item["source"]), "same source exact pin")
        sources[path] = item["source"]
        if kind in CANDIDATES:
            _generic(target, kind)
            if target.startswith("/models/") or target.endswith(".npy"):
                c.need(item["opaque_host"] is True, "original numerical/model input stays host opaque")
        else:
            c.need(target == path or target.startswith(("/source/", "/input/")), "trusted worker exact selected alias")
        if target == script:
            c.need(not item["opaque_host"] and target.endswith(".py"), "selected trusted Python entry point")
            script_source = item["source"]
    c.need(script_source is not None and any(c.typed_equal(script_source, d) for d in approved_sources), "entry point belongs to admitted trusted source closure")
    if kind in ("fixed", "investigate"):
        c.need({"/input/query.npy", "/input/train.npy", "/input/train_labels.npy", "/input/train_rows.json"} <= targets, "complete one-query training projection")
    return targets


class OperationBudget:
    def __init__(self, parent, endpoint):
        self.parent = parent; self.origin = parent.origin; self.end = min(parent.end, endpoint)
        self.clock = time.monotonic; self.limits = parent.limits
    def check_clock(self):
        self.parent.check_clock(); c.need(self.clock() < self.end, "original operation endpoint")
    def charge(self, key, amount):
        self.check_clock(); self.parent.charge(key, amount)
    def snapshot(self):
        return {"operation_deadline": self.end, "parent": self.parent.snapshot()}


class FailureBudget:
    """Prepaid fixed closeout; cannot turn a failed operation into normal work."""
    def __init__(self, parent, endpoint, byte_cap):
        self.origin = parent.origin; self.end = endpoint; self.clock = time.monotonic
        self.limits = {"read_bytes": byte_cap, "write_bytes": byte_cap}; self.used = {k: 0 for k in self.limits}
        for key, amount in self.limits.items(): parent.charge(key, amount)
    def check_clock(self): c.need(self.clock() < self.end, "original fixed failure closeout exceeded")
    def charge(self, key, amount):
        self.check_clock(); c.integer(amount); c.need(key in self.used and self.used[key] + amount <= self.limits[key], "prepaid closeout exhausted")
        self.used[key] += amount
    def snapshot(self): return {"failed_closeout_endpoint": self.end, "prepaid_limits": self.limits, "used": self.used, "normal_work_authorized": False}


class _UnixConnection(http.client.HTTPConnection):
    def __init__(self, spec, timeout):
        super().__init__("localhost", timeout=timeout); self.spec = spec; self.peer = None
    def connect(self):
        p = c.absolute(self.spec["path"]); before = p.lstat()
        c.need(stat.S_ISSOCK(before.st_mode) and not p.is_symlink() and
               before.st_dev == self.spec["device"] and before.st_ino == self.spec["inode"] and
               before.st_uid == self.spec["owner_uid"], "selected daemon socket identity")
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); sock.settimeout(self.timeout)
        try:
            sock.connect(str(p)); after = p.lstat()
            c.need((before.st_dev, before.st_ino, before.st_ctime_ns) == (after.st_dev, after.st_ino, after.st_ctime_ns), "daemon socket unchanged at connect")
            c.need(hasattr(socket, "SO_PEERCRED"), "qualified Linux Unix peer credentials required")
            pid, uid, gid = struct.unpack("3i", sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")))
            c.need(uid == self.spec["owner_uid"], "selected daemon peer UID")
            self.peer = {"pid_observed_only": pid, "uid": uid, "gid": gid}; self.sock = sock
        except BaseException:
            sock.close(); raise


class DirectEngine:
    """Bounded original HTTP records, no shell/CLI/process launch."""
    def __init__(self, config, budget, evidence_root, deadline):
        self.config = config; self.budget = budget; self.root = evidence_root; self.deadline = deadline; self.records = []; self.closeout_budget = None
    def _connection(self, deadline):
        remaining = min(deadline, self.budget.end) - time.monotonic()
        c.need(remaining > 0, "original native endpoint")
        return _UnixConnection(self.config["engine_socket"], remaining)
    def request(self, method, endpoint, body=None, statuses=(200,), *, closeout=None):
        budget = self.budget if closeout is None else closeout
        deadline = min(budget.end, self.deadline if closeout is None else budget.end, time.monotonic() + self.config["engine_control_seconds"])
        cap = self.config["engine_response_cap_bytes"]; budget.charge("read_bytes", cap + 1)
        raw_request = b"" if body is None else c.encoded(body, False)
        c.need(len(raw_request) <= cap, "engine request cap")
        sequence = len(self.records); record = {"sequence": sequence, "method": method, "endpoint": endpoint,
            "started_monotonic": time.monotonic(), "deadline": deadline, "request": c.pin(raw_request),
            "response_complete": False, "status": "entered"}; self.records.append(record)
        connection = _UnixConnection(self.config["engine_socket"], max(0.001, deadline-time.monotonic()))
        response = None; raw = bytearray()
        record["request_artifact"] = c.publish(self.root / ("engine-%05d-request.bin" % sequence), raw_request, budget)
        try:
            connection.request(method, "/" + self.config["engine_api_version"] + endpoint, body=raw_request,
                               headers={"Content-Type": "application/json", "Connection": "close"})
            response = connection.getresponse(); record["http_status"] = response.status; record["peer"] = connection.peer
            while True:
                budget.check_clock(); remaining = deadline-time.monotonic(); c.need(remaining > 0, "engine response original deadline")
                if connection.sock is not None: connection.sock.settimeout(remaining)
                block = response.read(min(65536, cap + 1 - len(raw)))
                if not block: record["response_complete"] = True; break
                raw.extend(block); c.need(len(raw) <= cap, "engine response overflow")
            c.need(response.status in statuses, "engine operation HTTP status")
            record["status"] = "completed"
            return None if not raw else c.parse(bytes(raw))
        except BaseException as error:
            record.update(status="failed", failure_type=type(error).__name__); raise
        finally:
            if response is not None: response.close()
            connection.close(); record["connection_closed"] = True; record["ended_monotonic"] = time.monotonic()
            publication_budget = self.closeout_budget if self.closeout_budget is not None and (record["status"] == "failed" or time.monotonic() >= budget.end) else budget
            record["response_artifact"] = c.publish(self.root / ("engine-%05d-response.bin" % sequence), bytes(raw), publication_budget)
    def inspect(self, ident, *, closeout=None):
        c.need(type(ident) is str and re.fullmatch("[0-9a-f]{64}", ident), "exact immutable owned container ID")
        value = self.request("GET", "/containers/" + ident + "/json", closeout=closeout)
        c.need(type(value) is dict and value.get("Id") == ident, "same owned engine object")
        return value
    def attach(self, ident):
        """A raw upgraded stream is attached before start; logging driver is none."""
        self.budget.charge("read_bytes", 2 * (self.config["stream_cap_bytes"] + 1))
        self.budget.charge("stream_bytes", 2 * (self.config["stream_cap_bytes"] + 1))
        connection = self._connection(self.deadline)
        endpoint = "/" + self.config["engine_api_version"] + "/containers/" + ident + "/attach?stream=1&stdout=1&stderr=1&logs=0"
        connection.request("POST", endpoint, headers={"Connection": "Upgrade", "Upgrade": "tcp", "Content-Length": "0"})
        response = connection.getresponse()
        try:
            c.need(response.status == 101 and response.getheader("Upgrade", "").lower() == "tcp", "qualified raw attach upgrade required before start")
            return StreamObserver(connection, response, self.deadline, self.config["stream_cap_bytes"], ident)
        except BaseException:
            response.close(); connection.close(); raise


class StreamObserver:
    """One bounded host thread, zero host child processes; exact Docker frames."""
    def __init__(self, connection, response, deadline, cap, ident):
        self.ident = ident
        self.connection = connection; self.response = response; self.deadline = deadline; self.cap = cap
        self.buffers = {"stdout": bytearray(), "stderr": bytearray()}; self.counts = {k: 0 for k in self.buffers}
        self.failure = None; self.eof = False; self.started = time.monotonic(); self.ended = None
        self.thread = threading.Thread(target=self._read, name="owned-neural081-stream", daemon=True)
        self.thread.start()
    def _exact(self, size, allow_eof=False):
        result = bytearray()
        while len(result) < size:
            c.need(time.monotonic() < self.deadline, "stream original deadline")
            block = self.response.fp.read(size-len(result))
            if not block:
                c.need(allow_eof and not result, "complete raw stream frame")
                return b""
            result.extend(block)
        return bytes(result)
    def _read(self):
        try:
            while True:
                header = self._exact(8, True)
                if not header: self.eof = True; break
                c.need(header[0] in (1, 2) and header[1:4] == b"\x00\x00\x00", "non-TTY stdout/stderr frame")
                name = "stdout" if header[0] == 1 else "stderr"; length = int.from_bytes(header[4:], "big")
                remaining = self.cap - self.counts[name]
                chunk = self._exact(min(length, remaining + 1)) if length else b""
                self.counts[name] += len(chunk); self.buffers[name].extend(chunk)
                c.need(length <= remaining, "strict original per-stream cap exceeded")
        except BaseException as error:
            self.failure = type(error).__name__
        finally:
            self.ended = time.monotonic()
    def finish(self, deadline):
        self.thread.join(max(0, deadline-time.monotonic()))
        joined = not self.thread.is_alive()
        if joined:
            self.response.close(); self.connection.close()
        return {"container_id": self.ident, "attach_http_status": 101, "attach_peer": self.connection.peer,
                "started_monotonic": self.started, "ended_monotonic": self.ended,
                "normal_deadline_monotonic": self.deadline, "thread_joined": joined, "raw_eof": self.eof,
                "failure": self.failure, "connection_closed": joined,
                "streams": {name: {**c.pin(bytes(raw)), "observed_bytes": self.counts[name], "complete": self.eof and self.failure is None}
                            for name, raw in self.buffers.items()}}
    def failure_close(self, deadline):
        try:
            if self.connection.sock is not None: self.connection.sock.shutdown(socket.SHUT_RDWR)
        except OSError: pass
        self.connection.close()
        return self.finish(deadline)


def _inspect_policy(value, payload, ident):
    c.need(value.get("Id") == ident and value.get("Image") == payload["Image"], "exact container/image identity")
    host = value["HostConfig"]; expected = payload["HostConfig"]; config = value["Config"]
    for key in ("NetworkMode", "ReadonlyRootfs", "Memory", "MemorySwap", "NanoCpus", "PidsLimit", "IpcMode", "CgroupnsMode"):
        c.need(c.typed_equal(host.get(key), expected[key]), "actual engine policy: " + key)
    c.need(set(host.get("CapDrop", [])) == {"ALL"} and "no-new-privileges:true" in host.get("SecurityOpt", []), "actual no-privilege policy")
    c.need(set(host.get("MaskedPaths", [])) == set(MASKED), "actual hidden process/host metadata paths")
    c.need(c.typed_equal(host.get("Ulimits"), expected["Ulimits"]) and host.get("RestartPolicy", {}).get("Name") == "no" and host.get("AutoRemove") is False and host.get("PidMode", "") == "", "actual CPU hard bound/no-restart/private process namespace")
    c.need(host.get("LogConfig", {}).get("Type") == "none" and not host.get("Privileged") and not host.get("Devices") and not host.get("DeviceRequests"), "no log loss, privilege or devices")
    c.need(config.get("User") == payload["User"] and config.get("WorkingDir") == "/workspace" and config.get("Tty") is False and
           config.get("Entrypoint") == payload["Entrypoint"] and config.get("Cmd") == payload["Cmd"] and
           sorted(config.get("Env", [])) == sorted(ENV), "exact source argv/cwd/environment")
    actual = {(m["Source"], m["Destination"], not m["RW"]) for m in value.get("Mounts", []) if m["Type"] == "bind"}
    wanted = {(m["Source"], m["Target"], m["ReadOnly"]) for m in expected["Mounts"]}
    c.need(actual == wanted and len(value.get("Mounts", [])) == len(wanted), "complete exact file/workspace mounts")
    return True


def live_extent(root, config, budget):
    pending = [root]; count = total = 0
    while pending:
        budget.check_clock(); directory = pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                count += 1; c.need(count <= config["workspace_entry_cap"], "live workspace entry bound")
                info = entry.stat(follow_symlinks=False)
                if stat.S_ISDIR(info.st_mode): pending.append(Path(entry.path))
                else:
                    c.need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "ordinary live workspace file")
                    total += info.st_size; c.need(total <= config["workspace_cap_bytes"], "live workspace extent bound")
    return total


def census(root, config, budget):
    root = c.absolute(str(root)); pending = [root]; found = []; count = total = 0; directories = []
    while pending:
        directory = pending.pop(); directories.append(directory); budget.check_clock()
        with os.scandir(directory) as entries:
            for entry in entries:
                count += 1; c.need(count <= config["workspace_entry_cap"], "complete workspace entry bound")
                value = entry.stat(follow_symlinks=False); path = Path(entry.path)
                if stat.S_ISDIR(value.st_mode): pending.append(path)
                else:
                    c.need(stat.S_ISREG(value.st_mode) and value.st_nlink == 1, "ordinary private output, no aliases")
                    total += value.st_size; c.need(total <= config["workspace_cap_bytes"], "whole private output byte bound")
                    desc = {"path": str(path), "bytes": value.st_size, "sha256": "0" * 64}; current = stamp(desc)
                    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                    try: os.fsync(fd)
                    finally: os.close(fd)
                    c.need(stamp(desc) == current, "durable output metadata unchanged")
                    found.append({"relative_path": str(path.relative_to(root)), "bytes": value.st_size, "stat": current})
    for directory in reversed(directories): c.sync_directory(directory)
    return {"files": sorted(found, key=lambda row: row["relative_path"]), "bytes": total,
            "entries": count, "directories": len(directories), "body_bytes_read": 0, "durable": True}


def _artifacts(work, directory, kind, config, budget):
    extent = census(work, config, budget)
    by_name = {row["relative_path"]: row for row in extent["files"]}
    c.need("runtime-artifacts.json" in by_name, "trusted worker artifact manifest required")
    manifest_path = work / "runtime-artifacts.json"; size = by_name["runtime-artifacts.json"]["bytes"]
    c.need(0 < size <= 2097152, "bounded artifact metadata")
    # This is metadata, not a scientific array/model/label body.
    budget.charge("read_bytes", size + 1)
    fd = os.open(manifest_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        with os.fdopen(fd, "rb", closefd=False) as stream: raw = stream.read(size + 1)
    finally: os.close(fd)
    c.need(len(raw) == size, "complete manifest extent")
    manifest = c.parse(raw); c.exact(manifest, ("schema", "artifacts", "operation_result"))
    c.need(manifest["schema"] == "neural081_runtime_artifacts_v1" and manifest["operation_result"] == "RESULT.json", "exact artifact/result schema")
    c.need(type(manifest["artifacts"]) is list, "complete output roster")
    names = []; artifacts = []
    for row in manifest["artifacts"]:
        c.exact(row, ("relative_path", "bytes", "sha256")); name = relative(row["relative_path"]); names.append(name)
        c.integer(row["bytes"]); c.digest(row["sha256"])
        c.need(name in by_name and by_name[name]["bytes"] == row["bytes"], "manifest joins original output metadata")
        artifacts.append({"path": str(work / name), "bytes": row["bytes"], "sha256": row["sha256"]})
    c.need(names == sorted(set(names)) and set(names) == set(by_name) - {"runtime-artifacts.json"} and "RESULT.json" in names, "complete unique output census")
    manifest_pin = c.publish(directory / "runtime-artifacts.json", raw, budget)
    snapshots = []
    if kind in CANDIDATES:
        output = c.new_directory(directory / "artifacts", budget)
        for row, desc in zip(manifest["artifacts"], artifacts):
            target = output / row["relative_path"]
            for parent in reversed(target.parents):
                if parent != output and parent.is_relative_to(output) and not parent.exists(): c.new_directory(parent, budget)
            # Host verification is required: dynamic candidate code may monkeypatch its runner.
            snapshots.append(c.copy_stream(desc, target, budget, [work]))
    c.need(census(work, config, budget) == extent, "closed workspace stable through artifact admission")
    return extent, manifest_pin, artifacts, snapshots


def _trusted_request(record, budget):
    """Admit source-owned request metadata before a trusted worker is started."""
    argv = record["argv"]
    c.need(len(argv) % 2 == 0, "complete trusted worker flag/value argv")
    arguments = {}
    for index in range(0, len(argv), 2):
        flag = argv[index]
        c.need(flag.startswith("--") and flag not in arguments, "unique trusted worker CLI flag")
        arguments[flag] = argv[index + 1]
    c.exact(arguments, ("--request", "--request-bytes", "--request-sha256", "--bootstrap",
                        "--bootstrap-bytes", "--bootstrap-sha256", "--read-cap", "--write-cap",
                        "--origin", "--deadline", "--entry-bytes"))
    mounts = {item["target"]: item for item in record["mounts"]}
    c.need(arguments["--request"] in mounts, "exact mounted request argv")
    selected = mounts[arguments["--request"]]
    c.need(selected["opaque_host"] is False, "trusted request is source metadata")
    request_pin = selected["source"]
    c.need(request_pin["bytes"] <= 16 * 2**20 and int(arguments["--request-bytes"]) == request_pin["bytes"] and
           arguments["--request-sha256"] == request_pin["sha256"], "exact request extent/hash argv")
    request = c.capture_json(request_pin, budget, [Path(request_pin["path"]).parent])
    keys = ("schema", "job", "source", "payload", "output_root", "allowed", "protected", "source_manifest", "clock", "worker_io")
    if record["kind"] == "reference": keys += ("operation", "generation", "limits")
    c.exact(request, keys)
    expected_schema = "neural081_" + record["kind"] + "_worker_request_v1"
    c.need(request["schema"] == expected_schema and request["output_root"] == record["work_root"], "same trusted role and allocated output")
    job = request["job"]
    c.need((type(job) is str and job == record["job_id"]) or
           (type(job) is dict and job.get("id") == record["job_id"]), "same exact selected worker job")
    c.descriptor(request["source"]); c.exact(request["clock"], ("origin", "deadline"))
    c.finite(request["clock"]["origin"], 0); c.finite(request["clock"]["deadline"], 0)
    c.need(c.typed_equal(request["worker_io"], record["worker_io"]) and
           request["clock"]["origin"] == record["original_origin"] and
           request["clock"]["deadline"] == record["normal_deadline"] == record["supplied_original_deadline"] and
           float(arguments["--origin"]) == request["clock"]["origin"] and
           float(arguments["--deadline"]) == request["clock"]["deadline"] and
           int(arguments["--read-cap"]) == record["worker_io"]["read_bytes"] and
           int(arguments["--write-cap"]) == record["worker_io"]["write_bytes"], "same original clock and complete managed IO reservation")
    manifest_pin = request["source_manifest"]; c.descriptor(manifest_pin)
    c.need(manifest_pin["bytes"] <= 2**20 and manifest_pin["path"] in mounts and
           mounts[manifest_pin["path"]]["opaque_host"] is False and
           c.typed_equal(mounts[manifest_pin["path"]]["source"], manifest_pin), "exact selected source manifest mount")
    manifest = c.capture_json(manifest_pin, budget, [Path(manifest_pin["path"]).parent])
    c.exact(manifest, ("schema", "entry", "bootstrap", "modules", "dependency_qualification", "installed_versions"))
    c.need(manifest["schema"] == "neural081_" + record["kind"] + "_source_manifest_v1", "same source manifest role")
    c.need(manifest["entry"]["path"] == record["script"] and int(arguments["--entry-bytes"]) == manifest["entry"]["bytes"], "same selected trusted entry")
    c.need(manifest["bootstrap"]["path"] == arguments["--bootstrap"] and
           manifest["bootstrap"]["bytes"] == int(arguments["--bootstrap-bytes"]) and
           manifest["bootstrap"]["sha256"] == arguments["--bootstrap-sha256"], "same exact captured bootstrap")
    c.need(type(manifest["modules"]) is list and manifest["modules"], "complete declared source module closure")
    names = []; members = [manifest["entry"], manifest["bootstrap"]]
    for row in manifest["modules"]:
        c.exact(row, ("name", "source")); c.need(type(row["name"]) is str and row["name"] in TRUSTED_MODULES[record["kind"]], "exact source-owned role module name")
        names.append(row["name"]); members.append(row["source"])
    c.need(len(names) == len(set(names)) and set(names) == TRUSTED_MODULES[record["kind"]], "complete unique source-owned role module roster")
    for desc in members:
        c.descriptor(desc)
        c.need(desc["path"] in mounts and mounts[desc["path"]]["opaque_host"] is False and
               c.typed_equal(mounts[desc["path"]]["source"], desc) and
               any(c.typed_equal(desc, item) for item in record["source_files"]), "full source manifest belongs to actual selected readonly source closure")
    if record["kind"] == "reference":
        c.need(any(row["name"] == "numeric" and c.typed_equal(row["source"], request["source"]) for row in manifest["modules"]), "same operative numerical source")
    qualification = manifest["dependency_qualification"]; c.descriptor(qualification)
    c.need(qualification["path"] in mounts and mounts[qualification["path"]]["opaque_host"] is False and
           c.typed_equal(mounts[qualification["path"]]["source"], qualification), "same selected dependency qualification metadata")
    header_keys = ("schema", "job", "source", "output_root", "source_manifest", "clock", "worker_io")
    if record["kind"] == "grader":
        _grader_targets(request["protected"], mounts)
        header_keys += ("protected",)
    return {"request": request_pin, "header": {key: request[key] for key in header_keys},
            "source_manifest": manifest_pin, "source_manifest_body": manifest, "arguments": arguments}


def _trusted_completion(record, budget):
    """Reopen real worker metadata; never open scientific array/model/label bodies."""
    path = str(Path(record["work_root"]) / "COMPLETE.json")
    rows = [desc for desc in record["artifacts"] if desc["path"] == path]
    c.need(len(rows) == 1 and rows[0]["bytes"] <= 2**20, "one bounded actual worker COMPLETE.json")
    complete_pin = rows[0]
    complete = c.capture_json(complete_pin, budget, [Path(record["work_root"])])
    manifest = c.capture_json(record["artifact_manifest"], budget, [Path(record["artifact_manifest"]["path"]).parent])
    c.exact(manifest, ("schema", "artifacts", "operation_result"))
    expected_rows = [{"relative_path": str(Path(desc["path"]).relative_to(Path(record["work_root"]))),
                      "bytes": desc["bytes"], "sha256": desc["sha256"]} for desc in record["artifacts"]]
    c.need(manifest["schema"] == "neural081_runtime_artifacts_v1" and manifest["operation_result"] == "RESULT.json" and
           c.typed_equal(manifest["artifacts"], expected_rows), "actual full runtime manifest and exact closed output descriptor roster")
    selected = record["trusted_request"]
    c.capture(selected["request"], budget, [Path(selected["request"]["path"]).parent])
    c.capture(selected["source_manifest"], budget, [Path(selected["source_manifest"]["path"]).parent])
    observed = {"descriptor": complete_pin, "body": complete, "runtime_artifact_manifest": record["artifact_manifest"],
                "source_manifest": selected["source_manifest"], "request": selected["request"],
                "complete_output_roster": expected_rows}
    record["worker_complete"] = observed
    _admit_trusted_worker(record)
    return observed


def _grader_targets(protected, mounts):
    c.need(type(protected) is list and len(protected) == 2, "exactly two protected G5 targets")
    paths = []
    for desc in protected:
        c.descriptor(desc); paths.append(desc["path"])
        c.need(desc["path"] in mounts and mounts[desc["path"]]["opaque_host"] is True and
               c.typed_equal(mounts[desc["path"]]["source"], desc), "exact host-opaque protected G5 mount")
    c.need(len(set(paths)) == 2, "distinct protected G5 descriptors")


def _admit_trusted_worker(record):
    selected = record["trusted_request"]; header = selected["header"]; observed = record["worker_complete"]; complete = observed["body"]
    c.exact(selected, ("request", "header", "source_manifest", "source_manifest_body", "arguments"))
    header_keys = ("schema", "job", "source", "output_root", "source_manifest", "clock", "worker_io")
    if record["kind"] == "grader": header_keys += ("protected",)
    c.exact(header, header_keys)
    if record["kind"] == "grader":
        _grader_targets(header["protected"], {item["target"]: item for item in record["mounts"]})
    c.exact(observed, ("descriptor", "body", "runtime_artifact_manifest", "source_manifest", "request", "complete_output_roster"))
    c.descriptor(selected["request"]); c.descriptor(selected["source_manifest"]); c.descriptor(observed["descriptor"])
    job = header["job"]
    c.need((type(job) is str and job == record["job_id"]) or (type(job) is dict and job.get("id") == record["job_id"]), "completion retains exact native job")
    c.need(header["output_root"] == record["work_root"] and c.typed_equal(header["source_manifest"], selected["source_manifest"]), "same native output/source manifest")
    c.need(header["schema"] == "neural081_" + record["kind"] + "_worker_request_v1", "same trusted request role")
    c.need(len(record["argv"]) % 2 == 0, "complete source worker arguments")
    actual_arguments = {record["argv"][index]: record["argv"][index + 1] for index in range(0, len(record["argv"]), 2)}
    c.need(len(actual_arguments) * 2 == len(record["argv"]) and c.typed_equal(actual_arguments, selected["arguments"]), "same complete source-owned request argv")
    c.exact(header["clock"], ("origin", "deadline"))
    c.finite(header["clock"]["origin"], 0); c.finite(header["clock"]["deadline"], 0)
    c.exact(complete, ("schema", "job", "request", "numeric_source", "original_origin", "original_deadline",
                       "observed_before_publication", "managed_requested_io", "reservation", "eof_probe_demand_included",
                       "physical_library_IO_or_RSS_measured"))
    c.need(complete["schema"] == "neural081_worker_complete_v1" and c.typed_equal(complete["job"], header["job"]) and
           c.typed_equal(complete["request"], selected["request"]) and
           c.typed_equal(complete["numeric_source"], header["source"]), "genuine completion job/request/source joins")
    c.need(c.typed_equal(complete["reservation"], header["worker_io"]) and
           c.typed_equal(complete["reservation"], record["worker_io"]), "complete original worker IO reservation")
    c.exact(complete["managed_requested_io"], ("read_bytes", "write_bytes"))
    for key in ("read_bytes", "write_bytes"):
        c.integer(complete["reservation"][key], 1); c.integer(complete["managed_requested_io"][key], 0, complete["reservation"][key])
    for key in ("original_origin", "original_deadline", "observed_before_publication"): c.finite(complete[key], 0)
    c.need(complete["original_origin"] == header["clock"]["origin"] == record["original_origin"] and
           complete["original_deadline"] == header["clock"]["deadline"] == record["normal_deadline"] == record["supplied_original_deadline"] and
           complete["original_origin"] <= complete["observed_before_publication"] <= record["normal_deadline"], "completion retains original shared clock")
    if "ended_monotonic" in record:
        c.need(complete["observed_before_publication"] <= record["ended_monotonic"], "worker completion precedes native terminal observation")
    c.need(complete["eof_probe_demand_included"] is True and complete["physical_library_IO_or_RSS_measured"] is False, "complete managed demand without fabricated physical measurement")
    c.need(c.typed_equal(observed["runtime_artifact_manifest"], record["artifact_manifest"]) and
           c.typed_equal(observed["source_manifest"], selected["source_manifest"]) and
           c.typed_equal(observed["request"], selected["request"]), "full manifest/request pins retained in completion")
    expected = [{"relative_path": str(Path(desc["path"]).relative_to(Path(record["work_root"]))),
                 "bytes": desc["bytes"], "sha256": desc["sha256"]} for desc in record["artifacts"]]
    c.need(c.typed_equal(observed["complete_output_roster"], expected) and
           any(c.typed_equal(observed["descriptor"], desc) and desc["path"] == str(Path(record["work_root"]) / "COMPLETE.json") for desc in record["artifacts"]), "COMPLETE is an actual full-manifest output")
    return True


def admit_closure(record):
    c.need(type(record) is dict and record.get("schema") == "neural081_direct_native_closure_v1", "source native closure schema")
    c.need(record.get("failure") is None and record.get("forced_action") is False and record.get("status") == "completed", "natural operation, no cleanup-to-success")
    c.need(type(record.get("returncode")) is int and record["returncode"] == 0, "strict natural integer zero")
    c.need(record["kind"] in KINDS, "exact selected native kind")
    c.integer(record["cpu_reservation"], 1, 7200); c.integer(record["memory_reservation"], 1)
    if record["kind"] == "grader":
        c.need(record["cpu_reservation"] <= 3600 and record["memory_reservation"] <= 8 * 2**30, "bounded protected G5 action")
    payload = record["create_payload"]; host = payload["HostConfig"]
    c.need(host["PidsLimit"] == 1 and host["NanoCpus"] == 1000000000 and host["Memory"] == host["MemorySwap"] == record["memory_reservation"] and
           c.typed_equal(host["Ulimits"], [{"Name":"cpu","Soft":record["cpu_reservation"],"Hard":record["cpu_reservation"]}]), "exact selected CPU/process/memory reservations")
    c.need(payload["Image"] == record["execution_config"]["image_digest"] and payload["User"] == record["execution_config"]["user"] and
           record["qualified_mechanisms"] == record["execution_config"]["qualification"], "same exact selected execution configuration")
    ident = record["container_id"]; c.need(re.fullmatch("[0-9a-f]{64}", ident) is not None, "immutable owned ID")
    c.need(record["wait"]["StatusCode"] == 0 and type(record["wait"]["StatusCode"]) is int and not record["wait"].get("Error"), "daemon wait confirms reaping")
    final = record["final_inspection"]; state = final["State"]
    c.need(final["Id"] == ident and state.get("Status") == "exited" and state.get("Running") is False and
           state.get("Paused") is False and state.get("Restarting") is False and state.get("OOMKilled") is False and
           type(state.get("ExitCode")) is int and state["ExitCode"] == 0 and type(state.get("Pid")) is int and state["Pid"] == 0,
           "complete stopped single-process namespace")
    c.need(not state.get("Error") and record["container_absent"] is True and record["removed_container_id"] == ident, "exact owned object retired after natural stop")
    _inspect_policy(final, record["create_payload"], ident)
    observed = record["stream_observation"]
    starts = [row for row in record["engine_operations"] if row["method"] == "POST" and row["endpoint"] == "/containers/" + ident + "/start"]
    c.need(len(starts) == 1 and observed["started_monotonic"] <= starts[0]["started_monotonic"] and observed["normal_deadline_monotonic"] == record["normal_deadline"], "same original attach-before-start endpoint")
    c.need(record["supplied_original_deadline"] is None or record["normal_deadline"] <= record["supplied_original_deadline"], "earlier serialized-request deadline retained")
    c.need(observed["container_id"] == ident and observed["attach_http_status"] == 101, "stream attached to exact owned object before start")
    c.need(observed["raw_eof"] is True and observed["thread_joined"] is True and observed["connection_closed"] is True and observed["failure"] is None, "complete original EOF and observer closure")
    for name in ("stdout", "stderr"):
        stream = observed["streams"][name]; retained = record["raw_streams"][name]
        c.need(stream["complete"] is True and type(stream["bytes"]) is int and stream["bytes"] <= 262144 and
               stream["bytes"] == stream["observed_bytes"] == retained["bytes"] and stream["sha256"] == retained["sha256"], "original complete stream pin")
    c.need(record["started_monotonic"] <= record["ended_monotonic"] <= record["normal_deadline"] <= record["original_deadline"] and
           observed["ended_monotonic"] <= record["normal_deadline"], "all closure inside original normal endpoint")
    c.need(record["source_before"] == record["source_after"] == record["source_files"] and record["nonopaque_before"] == record["nonopaque_after"] == [item["source"] for item in record["mounts"] if not item["opaque_host"]] and record["opaque_before"] == record["opaque_after"], "immutable source and opaque-input custody")
    c.need(record["workspace_census"]["durable"] is True and record["workspace_census"]["body_bytes_read"] == 0, "complete metadata durability")
    c.need(record["host_child_processes"] == 0 and record["numeric_pid_mutation"] is False and
           record["cpu_reservation_refunded"] is False and record["worker_io_refunded"] is False, "exact resource/topology semantics")
    c.need(all(x["status"] == "completed" and x["response_complete"] and x["connection_closed"] and
               x["ended_monotonic"] <= x["deadline"] for x in record["engine_operations"]), "complete original engine operations")
    if record["kind"] in TRUSTED_KINDS:
        _admit_trusted_worker(record)
    return record


class Runtime:
    def __init__(self, config, budget, source_files, root):
        self.config = c.parse(c.encoded(validate_config(config), False)); self.budget = budget; self.root = c.absolute(str(root))
        c.need(type(source_files) is list and source_files and len({d["path"] for d in source_files}) == len(source_files), "complete unique trusted source closure")
        self.source_files = [dict(d) for d in source_files]
        for desc in self.source_files: c.descriptor(desc)
        self.owned = {}; self.jobs = set(); self.records = []
        c.need(self.root.is_dir() and not any(p.is_symlink() for p in (self.root, *self.root.parents)), "fresh owned runtime root supplied by parent")
    def allocate(self, job_id):
        c.need(type(job_id) is str and job_id and len(job_id) <= 512 and job_id not in self.jobs, "fresh source-owned job identity")
        self.jobs.add(job_id); directory = c.new_directory(self.root / uuid.uuid4().hex, self.budget)
        work = c.new_directory(directory / "workspace", self.budget)
        self.owned[str(work)] = {"owner": job_id, "directory": directory, "attempts": 0, "used_jobs": set(), "blocked": False}
        c.publish_json(directory / "ALLOCATION.json", {"job_id": job_id, "work_root": str(work), "original_deadline": self.budget.end}, self.budget)
        return work
    def run(self, job_id, script, mounts, argv, *, seconds, memory_bytes, kind, worker_io=None, workspace=None, original_deadline=None):
        c.need(kind in KINDS, "selected native role"); c.integer(seconds, 1, 7200); c.integer(memory_bytes, 1)
        if kind == "grader": c.need(seconds <= 3600 and memory_bytes <= 8 * 2**30, "bounded protected G5 action")
        c.need(type(argv) is list and all(type(x) is str for x in argv), "literal native argv")
        work = self.allocate(job_id) if workspace is None else c.absolute(str(workspace))
        c.need(str(work) in self.owned, "only runtime-allocated workspaces")
        owned = self.owned[str(work)]; owner = owned["owner"]
        c.need(not owned["blocked"] and job_id not in owned["used_jobs"] and
               (job_id == owner or (kind in ("investigate", "author") and re.fullmatch(re.escape(owner) + r"/action-00[1-8]", job_id))), "same current owned case, unique selected action")
        _mount_contract(mounts, kind, self.source_files, script)
        if kind in CANDIDATES:
            c.need(script.startswith("/tools/") and all(not token.startswith("/") or token.startswith(("/action/", "/input/", "/workspace/")) for token in argv), "candidate generic trusted argv")
            c.need(not any(d["source"]["path"] in token or str(self.root) in token for d in mounts for token in argv), "no private path in candidate argv")
            c.need(seconds <= (60 if kind == "author" else 480) and memory_bytes <= (4 if kind == "author" else 8) * 2**30, "equal bounded candidate action")
            c.need(worker_io is None, "candidate arbitrary IO is not falsely instrumented")
        else:
            c.exact(worker_io, ("read_bytes", "write_bytes"))
            for key in ("read_bytes", "write_bytes"): self.budget.charge(key, c.integer(worker_io[key], 1))
        self.budget.charge("native_processes", 1); self.budget.charge("native_cpu_seconds", seconds)
        if kind in ("investigate", "author"): self.budget.charge("tool_processes", 1)
        started = time.monotonic(); deadline = min(self.budget.end, started + seconds)
        if original_deadline is not None:
            c.finite(original_deadline, 0); deadline = min(deadline, original_deadline)
        c.need(started < deadline, "original pre-allocation native endpoint already exhausted")
        parent_deadline = self.budget.end
        budget = OperationBudget(self.budget, deadline)
        workspace_config = dict(self.config, workspace_cap_bytes=min(self.config["workspace_cap_bytes"], (256 * 2**20 if kind == "author" else 16 * 2**30)))
        failed_budget = FailureBudget(budget, deadline + 120, 12 * (self.config["engine_response_cap_bytes"] + 1) + 2097152)
        directory = c.new_directory(owned["directory"] / ("attempt-%03d" % owned["attempts"]), budget)
        owned["attempts"] += 1; owned["used_jobs"].add(job_id); owned["blocked"] = True
        record = {"schema": "neural081_direct_native_closure_v1", "job_id": job_id, "kind": kind,
                  "work_root": str(work), "original_origin": budget.origin, "started_monotonic": started, "normal_deadline": deadline,
                  "original_deadline": parent_deadline, "supplied_original_deadline": original_deadline, "status": "entered", "failure": None,
                  "source_files": self.source_files, "mounts": mounts, "script": script, "argv": argv,
                  "worker_io": worker_io, "worker_io_refunded": False, "cpu_reservation": seconds, "memory_reservation": memory_bytes, "execution_config": self.config,
                  "cpu_reservation_refunded": False, "host_child_processes": 0, "host_observer_threads_maximum": 1,
                  "numeric_pid_mutation": False, "forced_action": False, "opaque_host_body_reads": 0,
                  "physical_io_or_rss_qualification_created": False, "qualified_mechanisms": self.config["qualification"]}
        self.records.append(record); record["intent"] = c.publish_json(directory / "INTENT.json", record, budget)
        engine = DirectEngine(self.config, budget, directory, deadline); engine.closeout_budget = failed_budget
        ident = None; observer = None; create_entered = False; attach_entered = False
        name = "neural081-" + uuid.uuid4().hex; record["container_name"] = name
        try:
            source_before = []; opaque_before = []
            for desc in self.source_files:
                c.capture(desc, budget, [Path(desc["path"]).parent]); source_before.append(desc)
            for item in mounts:
                if item["opaque_host"]: opaque_before.append({"source": item["source"], "stat": stamp(item["source"])})
                else: c.capture(item["source"], budget, [Path(item["source"]["path"]).parent], empty=True)
            record["source_before"] = source_before; record["opaque_before"] = opaque_before
            record["nonopaque_before"] = [item["source"] for item in mounts if not item["opaque_host"]]
            if kind in TRUSTED_KINDS:
                record["trusted_request"] = _trusted_request(record, budget)
            image = engine.request("GET", "/images/" + quote(self.config["image_digest"], safe="") + "/json")
            c.need(image["Id"] == self.config["image_digest"], "already present immutable image; no pull")
            actual_argv = [x.replace("{WORK}", "/workspace" if kind in CANDIDATES else str(work)) for x in argv]
            native_mounts = [{"Type": "bind", "Source": row["source"]["path"], "Target": row["target"], "ReadOnly": True} for row in mounts]
            native_mounts.append({"Type": "bind", "Source": str(work), "Target": "/workspace", "ReadOnly": False})
            if kind not in CANDIDATES: native_mounts.append({"Type": "bind", "Source": str(work), "Target": str(work), "ReadOnly": False})
            payload = {"Image": self.config["image_digest"], "Entrypoint": [self.config["python"]],
                       "Cmd": ["-I", "-B", script, *actual_argv], "User": self.config["user"], "Env": ENV,
                       "WorkingDir": "/workspace", "Tty": False, "OpenStdin": False, "AttachStdout": True, "AttachStderr": True,
                       "Labels": {"neural081.owned": name},
                       "HostConfig": {"NetworkMode": "none", "ReadonlyRootfs": True, "CapDrop": ["ALL"],
                           "SecurityOpt": ["no-new-privileges:true"], "Memory": memory_bytes, "MemorySwap": memory_bytes,
                           "NanoCpus": 1000000000, "PidsLimit": 1, "IpcMode": "private", "CgroupnsMode": "private",
                           "MaskedPaths": MASKED, "Mounts": native_mounts, "LogConfig": {"Type": "none", "Config": {}},
                           "Ulimits": [{"Name": "cpu", "Soft": seconds, "Hard": seconds}],
                           "AutoRemove": False, "RestartPolicy": {"Name": "no"}}}
            record["create_payload"] = payload
            c.publish_json(directory / "CREATE_INTENT.json", {"name": name, "payload": payload}, budget)
            create_entered = True
            created = engine.request("POST", "/containers/create?name=" + name, payload, (201,))
            ident = created["Id"]; c.need(re.fullmatch("[0-9a-f]{64}", ident) is not None, "immutable created ID")
            record["container_id"] = ident; _inspect_policy(engine.inspect(ident), payload, ident)
            attach_entered = True
            observer = engine.attach(ident)
            engine.request("POST", "/containers/" + ident + "/start", statuses=(204,))
            while True:
                c.need(time.monotonic() < deadline and observer.failure is None, "native normal deadline/stream cap")
                current = engine.inspect(ident)
                if current["State"]["Running"] is False: break
                statistics = engine.request("GET", "/containers/" + ident + "/stats?stream=false")
                usage = statistics["cpu_stats"]["cpu_usage"]["total_usage"]
                c.need(type(usage) is int and usage <= seconds * 1000000000, "cumulative native CPU reservation")
                live_extent(work, workspace_config, budget)
                time.sleep(min(self.config["poll_seconds"], max(0, deadline-time.monotonic())))
            record["wait"] = engine.request("POST", "/containers/" + ident + "/wait?condition=not-running")
            record["final_inspection"] = engine.inspect(ident)
            record["stream_observation"] = observer.finish(deadline)
            c.need(record["stream_observation"]["thread_joined"] and observer.failure is None and observer.eof, "complete native streams")
            record["raw_streams"] = {key: c.publish(directory / (key + ".bin"), bytes(raw), budget) for key, raw in observer.buffers.items()}
            # Never remove a running/uncertain container on the successful route.
            state = record["final_inspection"]["State"]
            c.need(state.get("Status") == "exited" and state.get("Running") is False and type(state.get("ExitCode")) is int and state["ExitCode"] == 0 and not state.get("OOMKilled"), "natural native integer zero")
            engine.request("DELETE", "/containers/" + ident, statuses=(204,))
            absent = engine.request("GET", "/containers/" + ident + "/json", statuses=(404,))
            record["container_absent"] = type(absent) is dict; record["removed_container_id"] = ident
            source_after = []
            for desc in self.source_files:
                c.capture(desc, budget, [Path(desc["path"]).parent]); source_after.append(desc)
            for item in mounts:
                if not item["opaque_host"]: c.capture(item["source"], budget, [Path(item["source"]["path"]).parent], empty=True)
            record["source_after"] = source_after
            record["nonopaque_after"] = [item["source"] for item in mounts if not item["opaque_host"]]
            record["opaque_after"] = [{"source": item["source"], "stat": stamp(item["source"])} for item in mounts if item["opaque_host"]]
            extent, manifest, artifacts, snapshots = _artifacts(work, directory, kind, workspace_config, budget)
            record.update(workspace_census=extent, artifact_manifest=manifest, artifacts=artifacts,
                          candidate_artifact_snapshots=snapshots, returncode=0, status="completed")
            if kind in TRUSTED_KINDS:
                _trusted_completion(record, budget)
        except BaseException as error:
            record.update(status="failed", failure={"type": type(error).__name__, "message": str(error)}, unknown_survivors=True)
            daemon_closed = False; observer_closed = False
            try:
                if not create_entered or record.get("container_absent") is True:
                    record["failure_retirement"] = {"no_create_invoked": not create_entered, "already_observed_absent": record.get("container_absent") is True}
                else:
                    self._retire_failure(engine, ident, name, failed_budget, record)
                daemon_closed = True
            except BaseException as close_error:
                record["failure_retirement"] = {"unknown": True, "error_type": type(close_error).__name__}
            record["failure_daemon_closed"] = daemon_closed
            observer_closure = {"attach_entered": attach_entered, "observer_returned": observer is not None,
                                "thread_joined": False, "connection_closed": False, "closed": False}
            record["failure_observer_closure"] = observer_closure
            if observer is None:
                observer_closed = not attach_entered
                observer_closure["not_created"] = not attach_entered
            else:
                try:
                    observed = observer.failure_close(failed_budget.end)
                    record["stream_observation"] = observed
                    observer_closure["thread_joined"] = observed.get("thread_joined") is True
                    observer_closure["connection_closed"] = observed.get("connection_closed") is True
                    observer_closed = observer_closure["thread_joined"] and observer_closure["connection_closed"]
                except BaseException as close_error:
                    observer_closure["error_type"] = type(close_error).__name__
                publication = {"complete": False, "observer_joined_before_snapshot": observer_closure["thread_joined"], "artifacts": {}}
                record["failure_stream_publication"] = publication
                try:
                    for key, raw in observer.buffers.items():
                        publication["artifacts"][key] = c.publish(directory / (key + "-failure.bin"), bytes(raw), failed_budget)
                    publication["complete"] = True
                    record["raw_streams"] = publication["artifacts"]
                except BaseException as close_error:
                    publication["error_type"] = type(close_error).__name__
            observer_closure["closed"] = observer_closed
            record["unknown_survivors"] = not (daemon_closed and observer_closed)
            raise AdapterError("native operation failed; original reservations and uncertainty retained", record) from error
        finally:
            try:
                record["engine_operations"] = engine.records; record["ended_monotonic"] = time.monotonic()
                record["budget"] = budget.snapshot(); record["failure_closeout"] = failed_budget.snapshot()
                publication_budget = budget if record["status"] == "completed" else failed_budget
                record["receipt"] = c.publish_json(directory / "NATIVE.json", record, publication_budget)
            except BaseException as close_error:
                record["receipt_publication_uncertain"] = True
                record["receipt_publication_error_type"] = type(close_error).__name__
                if record["status"] == "completed": raise
        admit_closure(record); budget.check_clock(); owned["blocked"] = False
        return record

    def _retire_failure(self, engine, ident, name, failed_budget, record):
        if ident is None:
            # A failed create response may still have created this exact predeclared name.
            recovered = engine.request("GET", "/containers/" + name + "/json", closeout=failed_budget)
            c.need(recovered["Name"] == "/" + name and recovered["Config"]["Labels"].get("neural081.owned") == name, "exact failed-create owned resource")
            ident = recovered["Id"]; c.need(re.fullmatch("[0-9a-f]{64}", ident), "recovered immutable resource ID")
        current = engine.inspect(ident, closeout=failed_budget)
        if current["State"]["Running"]:
            record["forced_action"] = True
            engine.request("POST", "/containers/" + ident + "/kill?signal=SIGKILL", statuses=(204,), closeout=failed_budget)
        engine.request("POST", "/containers/" + ident + "/wait?condition=not-running", closeout=failed_budget)
        final = engine.inspect(ident, closeout=failed_budget)
        c.need(final["State"]["Running"] is False, "stopped owned failure resource")
        engine.request("DELETE", "/containers/" + ident, statuses=(204,), closeout=failed_budget)
        engine.request("GET", "/containers/" + ident + "/json", statuses=(404,), closeout=failed_budget)
        record["failure_retirement"] = {"container_id": ident, "absent": True}
