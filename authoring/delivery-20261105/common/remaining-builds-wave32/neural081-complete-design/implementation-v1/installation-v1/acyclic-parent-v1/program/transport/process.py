"""Bounded observation without numeric child/process-group mutation.

Positive closure requires a supported, separately qualified Linux procfs view.
Timeout, residual/reused/unknown identities, nonzero status or late closure fail.
The observer never signals a child or group. Failed active handles remain in a
process-local quarantine for separate authorized inspection, not as a retirement
claim. Interpreter exit can close those descriptors; quarantine is not durable.
"""
import hashlib
import json
import os
from pathlib import Path
import selectors
import stat
import subprocess
import time
import uuid

from .common import AdapterError, authenticate, canonical, integer, need, positive


PROC_STAT_CAP = 4096
PROC_SCAN_CAP = 4096
MAX_UNRESOLVED = 16
_UNRESOLVED = {}


def _read_process_identity(pid, budget):
    """Read a bounded Linux proc record; never mutate a process by numeric ID."""
    if type(pid) is not int or pid <= 0:
        return {"state": "unknown", "reason": "invalid_numeric_identity"}
    try:
        budget.check_clock()
        budget.charge("source_read", PROC_STAT_CAP + 1)
        with Path(f"/proc/{pid}/stat").open("rb") as stream:
            body = stream.read(PROC_STAT_CAP + 1)
        if len(body) > PROC_STAT_CAP:
            return {"state": "unknown", "reason": "proc_record_cap"}
        text = body.decode("utf-8", errors="strict")
        close = text.rfind(")")
        fields = text[close + 2:].split()
        observed_pid = int(text.split("(", 1)[0].strip())
        if close < 0 or len(fields) < 20 or observed_pid != pid:
            return {"state": "unknown", "reason": "malformed_proc_record"}
        return {"state": "present", "pid": pid, "parent_pid": int(fields[1]),
                "process_group": int(fields[2]), "session": int(fields[3]),
                "birth_ticks": int(fields[19]), "proc_bytes": len(body)}
    except FileNotFoundError:
        return {"state": "absent"}
    except (OSError, UnicodeError, ValueError, AdapterError) as exc:
        return {"state": "unknown", "reason": type(exc).__name__}


def observe_process_group(identity, budget):
    """Bounded read-only snapshot; unknown or a reused leader ID cannot pass.

    Group absence is not proof that no descendant escaped into another session.
    Qualified namespace/container ownership remains a separate required gate.
    """
    if not isinstance(identity, dict) or identity.get("state") != "present":
        return {"state": "unknown", "reason": "initial_leader_identity_unavailable", "members": []}
    proc = Path("/proc")
    if not proc.is_dir():
        return {"state": "unknown", "reason": "supported_linux_procfs_required", "members": []}
    pid, group = identity["pid"], identity["process_group"]
    current = _read_process_identity(pid, budget)
    if current["state"] == "unknown":
        return {"state": "unknown", "reason": "leader_reobservation_unavailable", "members": []}
    if current["state"] == "present" and any(current[k] != identity[k] for k in ("birth_ticks", "parent_pid", "process_group", "session")):
        return {"state": "unknown", "reason": "leader_pid_reused_or_identity_changed", "members": []}
    members = []; scanned = 0; incomplete = False
    try:
        with os.scandir(proc) as entries:
            for entry in entries:
                if not entry.name.isdecimal():
                    continue
                scanned += 1
                if scanned > PROC_SCAN_CAP:
                    return {"state": "unknown", "reason": "proc_scan_cap", "members": members, "scanned": scanned}
                record = _read_process_identity(int(entry.name), budget)
                if record["state"] == "unknown":
                    incomplete = True
                elif record["state"] == "present" and record["process_group"] == group:
                    members.append({k: record[k] for k in ("pid", "birth_ticks", "parent_pid", "session")})
    except (OSError, AdapterError) as exc:
        return {"state": "unknown", "reason": type(exc).__name__, "members": members, "scanned": scanned}
    # Reobserve the numeric leader after scanning so a visible reused PID never
    # becomes an absent-group success. No action is taken on any observed PID.
    final = _read_process_identity(pid, budget)
    if final["state"] == "unknown" or (final["state"] == "present" and
            any(final[k] != identity[k] for k in ("birth_ticks", "parent_pid", "process_group", "session"))):
        return {"state": "unknown", "reason": "leader_identity_changed_during_scan", "members": members, "scanned": scanned}
    return {"state": "present" if members else ("unknown" if incomplete else "absent"),
            "reason": "observed_members" if members else ("incomplete_proc_snapshot" if incomplete else "bounded_proc_snapshot"),
            "members": members, "scanned": scanned, "complete_scan": not incomplete,
            "escaped_descendants": "not_established_by_group_snapshot"}


def preflight_observer_namespace(budget):
    """Refuse unsupported host observability before launching any child."""
    identity = _read_process_identity(os.getpid(), budget)
    need(identity.get("state") == "present", "supported readable Linux procfs required before launch")
    observed = observe_process_group(identity, budget)
    need(observed.get("complete_scan") is True and observed.get("state") == "present",
         "complete qualified host process namespace must be observable before launch")
    return {"self_identity": identity, "namespace_observation": observed}


def inspect_unresolved(token, budget):
    """Read-only operator inspection; no closure, signal, release or approval."""
    need(token in _UNRESOLVED, "process-local inspection token unavailable")
    held = _UNRESOLVED[token]
    return {"token": token, "leader_poll_code": held["process"].poll(),
            "group_observation": observe_process_group(held["identity"], budget),
            "retired": False, "separate_authorized_inspection_required": True,
            "quarantine_persistence": "only_this_interpreter_lifetime"}


class ProcessObserver:
    """Observe an owned launch; never mutate numeric child/group identities."""
    def run(self, argv, *, cwd, env, budget, seconds, cleanup_seconds, stream_cap,
            monitor=None, pass_fds=()):
        need(isinstance(argv, list) and argv and all(type(x) is str and x for x in argv), "literal nonempty argv")
        need(Path(argv[0]).is_absolute(), "absolute executable")
        need(monitor is None or type(monitor) is DockerMonitor, "no caller observer callback")
        need(type(pass_fds) is tuple and len(set(pass_fds)) == len(pass_fds) and all(type(fd) is int and fd > 2 for fd in pass_fds), "explicit unique inherited issuer descriptors")
        integer(stream_cap, "stream cap", 1); positive(seconds, "process seconds")
        positive(cleanup_seconds, "reserved inspection seconds")
        need(len(_UNRESOLVED) < MAX_UNRESOLVED, "unresolved observations require separate inspection before more launches")
        budget.check_clock()
        preflight = preflight_observer_namespace(budget)
        start = time.monotonic()
        end = min(start + seconds, budget.deadline_monotonic - cleanup_seconds)
        need(end > start, "no original-clock room for process and separate inspection")
        budget.charge("stream_bytes", 2 * (stream_cap + 1))
        # Initialize failure evidence before launch. Once Popen returns an owned
        # child, identity reads and selector construction must share the guarded
        # path so setup failure cannot lose the unknown-survivor observation.
        identity = {"state": "unknown", "reason": "postlaunch_identity_not_observed"}
        selector = None
        buffers = {"stdout": bytearray(), "stderr": bytearray()}
        stream_counts = {"stdout": 0, "stderr": 0}
        stream_hashes = {"stdout": hashlib.sha256(), "stderr": hashlib.sha256()}
        eof = {"stdout": False, "stderr": False}
        failed = None; natural_code = None; last_poll = start; snapshots = []
        group = {"state": "unknown", "reason": "not_yet_observed", "members": []}
        selector_closed = False
        process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   start_new_session=True, close_fds=True, pass_fds=pass_fds)
        try:
            identity = _read_process_identity(process.pid, budget)
            identity_valid = (identity.get("state") == "present" and
                              identity.get("parent_pid") == os.getpid() and
                              identity.get("process_group") == process.pid and identity.get("session") == process.pid)
            selector = selectors.DefaultSelector()
            need(identity_valid, "initial leader identity unavailable or unsupported Linux procfs namespace")
            for name, pipe in (("stdout", process.stdout), ("stderr", process.stderr)):
                os.set_blocking(pipe.fileno(), False); selector.register(pipe, selectors.EVENT_READ, name)
            while selector.get_map() or process.poll() is None:
                now = time.monotonic()
                need(now < end, "process normal deadline exceeded")
                budget.check_clock()
                if monitor is not None and now - last_poll >= monitor.poll_seconds:
                    if end - now > 2 * cleanup_seconds:
                        snapshots.append(monitor.snapshot(end)); last_poll = now
                for key, _ in selector.select(min(0.1, end - now)):
                    chunk = os.read(key.fileobj.fileno(), min(65536, stream_cap + 1))
                    if not chunk:
                        eof[key.data] = True
                        selector.unregister(key.fileobj); key.fileobj.close(); continue
                    stream_counts[key.data] += len(chunk); stream_hashes[key.data].update(chunk)
                    available = max(0, stream_cap - len(buffers[key.data]))
                    buffers[key.data].extend(chunk[:available])
                    need(stream_counts[key.data] <= stream_cap, "per-stream process cap exceeded")
            remaining = end - time.monotonic()
            need(remaining > 0, "normal endpoint passed before final wait")
            natural_code = process.wait(timeout=remaining)
            need(type(natural_code) is int and natural_code == 0, "exact natural integer-zero leader required")
            need(all(eof.values()), "both streams must reach genuine EOF")
            group = observe_process_group(identity, budget)
            need(group["state"] == "absent", "residual/reused/unknown group requires separate inspection")
        except BaseException as exc:
            failed = type(exc).__name__ + ": " + str(exc)
        finally:
            if selector is not None:
                try:
                    selector.close(); selector_closed = True
                except BaseException as exc:
                    failed = failed or (type(exc).__name__ + ": selector closure failed")
        # Observing poll/reap does not confer authority to signal a now-reusable
        # numeric PID. No failure path closes a still-open child read handle.
        try:
            observed_code = process.poll()
        except BaseException:
            observed_code = None
            failed = failed or "leader poll unavailable"
        ended = time.monotonic()
        if ended > end:
            failed = failed or "final wait/EOF/group/observer closure exceeded selected normal endpoint"
        if type(observed_code) is not int or observed_code != 0:
            failed = failed or "final leader completion unavailable or nonzero"
        if group["state"] != "absent" or not all(eof.values()) or not selector_closed:
            failed = failed or "complete natural stream/group closure unavailable"
        token = None
        if failed is not None:
            token = uuid.uuid4().hex
            _UNRESOLVED[token] = {"process": process, "identity": identity,
                                  "reason": failed, "originating_interpreter_pid": os.getpid()}
        observation = {"schema": "neural053_host_process_observation_v3", "argv": argv,
                       "pid": process.pid, "process_group": process.pid, "leader_identity": identity,
                       "prelaunch_namespace_observation": preflight,
                       "started_monotonic": start, "ended_monotonic": ended,
                       "normal_deadline_monotonic": end, "original_deadline_monotonic": budget.deadline_monotonic,
                       "natural_exit_code": natural_code, "observed_leader_exit_code": observed_code,
                       "process_reaped": type(observed_code) is int,
                       "process_group_absent": group["state"] == "absent", "group_observation": group,
                       "streams_closed": all(eof.values()), "stream_eof_observed": eof,
                       "observer_selector_closed": selector_closed, "child_mutation_attempted": False,
                       "quarantine_token": token, "quarantine_persistence": "process_local_not_durable_across_interpreter_exit",
                       "survivor_disposition": "group_absence_observed_not_universal_descendant_retirement" if failed is None else "unknown_or_residual_survivors_require_separate_inspection",
                       "separate_authorized_inspection_required": failed is not None,
                       "interpreter_exit_may_close_descriptors": True,
                       "failure": failed, "container_samples": snapshots,
                       "stream_reservation_bytes": 2 * (stream_cap + 1), "per_stream_cap": stream_cap, "passed_descriptor_count": len(pass_fds), "unused_stream_reservation_refunded": False,
                       "streams": {name: {"bytes": stream_counts[name], "retained_bytes": len(data),
                                          "sha256": stream_hashes[name].hexdigest(),
                                          "retained_sha256": hashlib.sha256(data).hexdigest()}
                                   for name, data in buffers.items()}}
        finalized = time.monotonic()
        observation["ended_monotonic"] = finalized
        if finalized > end:
            failed = failed or "receipt finalization exceeded selected normal endpoint"
            if token is None:
                token = uuid.uuid4().hex
                _UNRESOLVED[token] = {"process": process, "identity": identity,
                                      "reason": failed, "originating_interpreter_pid": os.getpid()}
            observation.update({"failure": failed, "quarantine_token": token,
                "survivor_disposition": "unknown_or_residual_survivors_require_separate_inspection",
                "separate_authorized_inspection_required": True})
        if failed is not None:
            # Preserve exactly the available bounded raw buffers. On overflow,
            # timeout or missing EOF these are explicitly partial, never a
            # reconstructed complete stream or a successful process closure.
            observation["retained_failure_streams_hex"] = {name: bytes(data).hex() for name, data in buffers.items()}
            observation["failure_streams_complete"] = all(eof.values()) and all(stream_counts[name] == len(data) for name, data in buffers.items())
            raise AdapterError("host process natural closure not admitted; no child action taken", observation)
        return {"stdout": bytes(buffers["stdout"]), "stderr": bytes(buffers["stderr"]), "observation": observation}


def workspace_extent(root, entry_cap, budget):
    integer(entry_cap, "workspace entry cap", 1)
    total = 0; count = 0; pending = [Path(root)]
    while pending:
        directory = pending.pop(); budget.check_clock()
        with os.scandir(directory) as entries:
            for entry in entries:
                budget.check_clock(); count += 1
                need(count <= entry_cap, "workspace complete entry cap exceeded; no zero-byte bypass")
                st = entry.stat(follow_symlinks=False)
                need(not stat.S_ISLNK(st.st_mode), "workspace symlink refused")
                if stat.S_ISREG(st.st_mode):
                    need(st.st_nlink == 1, "workspace hardlink refused"); total += st.st_size
                else:
                    need(stat.S_ISDIR(st.st_mode), "workspace special file refused"); pending.append(Path(entry.path))
    budget.check_clock()
    return total


class DockerMonitor:
    def __init__(self, sandbox, name, work_root):
        self.sandbox, self.name, self.work_root = sandbox, name, work_root
        self.poll_seconds = sandbox.config["poll_seconds"]

    def snapshot(self, deadline):
        inspect = self.sandbox.inspect(self.name, seconds=min(5, deadline-time.monotonic()))
        stats = self.sandbox.command(["stats", "--no-stream", "--format", "{{json .}}", self.name], seconds=min(5, deadline-time.monotonic()))
        extent = workspace_extent(self.work_root, self.sandbox.config["workspace_entry_cap"], self.sandbox.budget)
        need(extent <= self.sandbox.config["workspace_cap_bytes"], "owned workspace extent exceeded")
        return {"monotonic": time.monotonic(), "state": inspect["State"],
                "docker_stats": stats["stdout"].decode("utf-8", errors="strict").strip(),
                "workspace_logical_bytes": extent}


class DockerSandbox:
    def __init__(self, config, budget, namespace_root):
        self.config, self.budget = config, budget
        self.root = Path(namespace_root)
        self.empty_config = self.root / "docker-config"
        self.empty_config.mkdir(mode=0o700)
        self.observer = ProcessObserver()
        self.env = {"PATH": "/usr/bin:/bin"}
        self.resources = []
        self._binary_stat = None

    def command(self, arguments, *, seconds=None, monitor=None):
        executable = Path(self.config["docker_binary"]["path"])
        st = executable.stat()
        identity = (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)
        if self._binary_stat is None:
            authenticate(self.config["docker_binary"], self.budget); self._binary_stat = identity
        else:
            need(identity == self._binary_stat, "pinned Docker executable stat changed")
        argv = [self.config["docker_binary"]["path"], "--host", self.config["docker_endpoint"],
                "--config", str(self.empty_config)] + arguments
        return self.observer.run(argv, cwd=str(self.root), env=self.env, budget=self.budget,
                                 seconds=seconds or self.config["tool_seconds"],
                                 cleanup_seconds=self.config["cleanup_seconds"],
                                 stream_cap=self.config["stream_cap_bytes"], monitor=monitor)

    def inspect(self, name, seconds=5):
        value = json.loads(self.command(["inspect", name], seconds=seconds)["stdout"])
        need(type(value) is list and len(value) == 1 and value[0]["Name"] == "/" + name, "exact owned container inspect")
        return value[0]

    def run_python(self, script, *, mounts, work_root, args=()):
        """Create, observe, inspect and remove one owned network-disabled container."""
        self.budget.charge("tool_calls")
        image = json.loads(self.command(["image", "inspect", self.config["image_digest"]], seconds=5)["stdout"])
        need(len(image) == 1 and image[0]["Id"] == self.config["image_digest"], "pinned already-present image required; no pull")
        name = "neural010-" + uuid.uuid4().hex
        arguments = ["create", "--pull", "never", "--name", name, "--network", "none", "--read-only",
                     "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true", "--user", self.config["user"],
                     "--pids-limit", str(self.config["pids_limit"]), "--memory", str(self.config["memory_bytes"]),
                     "--memory-swap", str(self.config["memory_bytes"]), "--cpus", str(self.config["cpus"]),
                     "--tmpfs", "/tmp:rw,noexec,nosuid,size=" + str(self.config["tmpfs_bytes"]),
                     "--workdir", "/work", "--env", "PYTHONDONTWRITEBYTECODE=1"]
        destinations = set()
        for host, target, readonly in mounts:
            need(Path(host).is_absolute() and target.startswith("/") and target not in destinations, "exact unique mount")
            need("," not in str(host) and "," not in target, "mount delimiter refused")
            destinations.add(target)
            arguments += ["--mount", f"type=bind,src={host},dst={target}" + (",readonly" if readonly else "")]
        arguments += ["--entrypoint", self.config["python"], self.config["image_digest"], "-I", "-B", script, *list(args)]
        created = False; final = None; failure = None; start_observation = None
        record = {"container_name": name, "image_digest": self.config["image_digest"]}
        self.resources.append(record)
        try:
            create = self.command(arguments, seconds=10)
            created = True
            record["container_id"] = create["stdout"].decode().strip()
            current = self.inspect(name)
            host = current["HostConfig"]
            need(current["Id"] == record["container_id"] and current["Image"] == self.config["image_digest"] and
                 host["NetworkMode"] == "none" and host["ReadonlyRootfs"] is True and
                 host["Memory"] == self.config["memory_bytes"] and host["MemorySwap"] == self.config["memory_bytes"] and
                 host["NanoCpus"] == int(self.config["cpus"] * 1000000000) and
                 host["PidsLimit"] == self.config["pids_limit"] and current["Config"]["User"] == self.config["user"],
                 "actual Docker resource/isolation configuration mismatch")
            actual_mounts = {(m["Source"], m["Destination"], not m["RW"]) for m in current["Mounts"] if m["Type"] == "bind"}
            need(actual_mounts == {(str(Path(h).resolve()), t, ro) for h, t, ro in mounts}, "actual mounted artifact set mismatch")
            start_observation = self.command(["start", "--attach", name], monitor=DockerMonitor(self, name, work_root))
            final = self.inspect(name)
            state = final["State"]
            need(state["Running"] is False and state["OOMKilled"] is False and
                 type(state["ExitCode"]) is int and state["ExitCode"] == 0, "container did not naturally complete int0")
            need(workspace_extent(work_root, self.config["workspace_entry_cap"], self.budget) <= self.config["workspace_cap_bytes"], "final workspace extent cap")
        except BaseException as exc:
            failure = {"type": type(exc).__name__, "message": str(exc), "evidence": getattr(exc, "evidence", {})}
        finally:
            if created:
                try:
                    removal = self.command(["rm", "--force", name], seconds=self.config["cleanup_seconds"])
                    names = self.command(["ps", "--all", "--filter", "name=^/" + name + "$", "--format", "{{.ID}}"], seconds=5)
                    record["owned_container_absent"] = names["stdout"].strip() == b""
                    record["retirement_observation"] = removal["observation"]
                except BaseException as exc:
                    record["owned_container_absent"] = False
                    record["retirement_failure"] = str(exc)
            else:
                # The unique name was recorded before create. A failed CLI can
                # still have created the daemon resource, so inspect/remove that
                # exact owned name rather than assuming no resource exists.
                try:
                    names = self.command(["ps", "--all", "--filter", "name=^/" + name + "$", "--format", "{{.ID}}"], seconds=5)
                    if names["stdout"].strip():
                        self.command(["rm", "--force", name], seconds=self.config["cleanup_seconds"])
                        names = self.command(["ps", "--all", "--filter", "name=^/" + name + "$", "--format", "{{.ID}}"], seconds=5)
                    record["owned_container_absent"] = names["stdout"].strip() == b""
                except BaseException as exc:
                    record["owned_container_absent"] = False
                    record["retirement_failure"] = str(exc)
        record.update({"final_inspection": final, "failure": failure,
                       "natural_exit_code": None if final is None else final["State"].get("ExitCode"),
                       "workload_observation": None if start_observation is None else start_observation["observation"],
                       "memory_peak_and_physical_IO_complete": False})
        if failure or record["owned_container_absent"] is not True:
            raise AdapterError("owned container attempt failed or retirement unknown", record)
        authenticate(self.config["docker_binary"], self.budget)
        self.budget.check_clock()
        return {**start_observation, "container_observation": record}

    def verify_shared_clock(self, work_root):
        observed = self.run_python("-c", mounts=[(str(work_root), "/work", False)], work_root=work_root,
                                   args=("import time; print(time.monotonic())",))
        value = float(observed["stdout"].decode().strip())
        host = observed["observation"]
        need(host["started_monotonic"] <= value <= host["ended_monotonic"],
             "container and original host monotonic clock domains differ; no deadline translation/reset")
        self.budget.check_clock()
        return {"container_monotonic": value, "host_observation": host,
                "clock_domain": "observed shared monotonic interval; external runtime qualification also required"}
