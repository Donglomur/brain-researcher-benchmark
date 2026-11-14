"""Fixed Linux host ownership, derived from the captured V4 barrier and voice cgroup.

No native operation occurs at import. The accounting parent stays process-free;
the fixed host leaf receives the bootstrap before its controller activation.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import stat
import subprocess
import time
import uuid
from tms_figure.contract import Budget
from .schema import canonical, body_pin, exact_budget, require, save, bounded_json
from .host_support.cgroup import Cgroup
from .host_support.common import FailureCarrier


def stamp(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def absolute(path, directory=False):
    p = Path(path)
    require(p.is_absolute() and str(p) == os.path.normpath(str(p)), "literal absolute host path")
    for part in (p, *p.parents):
        require(not part.is_symlink(), "no host path aliases")
    s = p.lstat()
    require(stat.S_ISDIR(s.st_mode) if directory else stat.S_ISREG(s.st_mode) and s.st_nlink == 1,
            "ordinary host path")
    return p


def capture(path, cap, budget):
    p = absolute(path)
    s = p.lstat()
    require(0 <= s.st_size <= cap, "host capture extent")
    budget.charge(read=s.st_size + 1)
    fd = os.open(p, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        require(stamp(os.fstat(fd)) == stamp(s), "opened host capture identity")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            body = stream.read(s.st_size + 1)
        require(len(body) == s.st_size and stamp(s) == stamp(os.fstat(fd)) == stamp(p.lstat()),
                "stable host capture")
        return body
    finally:
        os.close(fd)


def plain_json(body):
    def pairs(rows):
        require(len({k for k, _ in rows}) == len(rows), "duplicate host metadata key")
        return dict(rows)
    value = json.loads(body, object_pairs_hook=pairs,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite host JSON")))
    canonical(value)
    return value


class CgroupBudget:
    """Exact numerical Budget adapter for the unchanged captured Cgroup API.

    Its entire read/write allocation is charged to the caller before creation.
    Original returned prefixes survive internal deadline failures in Cgroup events.
    """
    def __init__(self, parent, read_bytes, write_bytes, deadline, receipt_reserve):
        exact_budget(parent)
        require(time.monotonic() < deadline <= parent.deadline, "original owner deadline")
        parent.charge(read=read_bytes, write=write_bytes)
        self.meter = Budget(read_bytes, write_bytes, deadline - time.monotonic())
        self.meter.deadline = deadline
        self.deadline = deadline
        self.limits = {"read_bytes": read_bytes, "write_bytes": write_bytes}
        self.read_bytes = self.write_bytes = 0
        self.receipt_reserve = receipt_reserve
        self.unknown = []
        self.scope = None

    def clock(self):
        return time.monotonic()

    def check(self, stage, deadline=None):
        require(time.monotonic() < min(self.deadline, deadline or self.deadline),
                "fixed cgroup deadline: " + stage)
        self.meter.charge()
        require(self.read_bytes <= self.limits["read_bytes"] and
                self.write_bytes + self.meter.writes <= self.limits["write_bytes"],
                "cgroup cumulative kernel and metadata extent")
        if self.scope is not None:
            require(len(self.scope.events) * 512 <= self.receipt_reserve,
                    "finite cgroup event roster reservation")

    def admit_read(self, n):
        require(type(n) is int and 0 <= n <= self.limits["read_bytes"] - self.read_bytes,
                "cgroup read reservation")
        # Reserve maximum retained hex/text event representation before kernel read.
        self.meter.charge(write=3 * n + 512)

    def read(self, n):
        self.read_bytes += n
        self.meter.charge(read=n)

    def reserved(self):
        return self.receipt_reserve + self.meter.writes, 1

    def failed_write(self, label, error, remaining):
        n = getattr(error, "characters_written", None)
        if type(n) is int and 0 <= n <= remaining:
            return n
        self.uncertain(label, "write_tail", error)
        return None

    def write_count(self, label, n, remaining):
        if type(n) is int and 0 <= n <= remaining:
            return n
        self.uncertain(label, "write_count", ValueError("invalid kernel write count"))
        return None

    def uncertain(self, label, quantity, error, **details):
        self.unknown.append({"stage": label, "quantity": quantity,
                             "error_type": type(error).__name__, **details})


class HostOwnershipFailure(RuntimeError):
    def __init__(self, carrier, record):
        self.carrier, self.record = carrier, record
        super().__init__("fixed TMS host ownership failed; original observations retained")


def atomic(root, name, value, budget, cap=None):
    require("/" not in name and name.endswith(".json"), "fixed journal basename")
    cap = (budget.write_limit - budget.writes) // 2 if cap is None else cap
    body = bounded_json(value, cap)
    budget.charge(write=2 * len(body))
    fd = os.open(root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    try:
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(body); stream.flush(); os.fsync(stream.fileno())
    finally:
        os.close(fd)
    pin = body_pin(body)
    os.chmod(root / name, 0o400)
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return {"path": str(root / name), **pin}


def inspect_process(pid, budget):
    require(type(pid) is int and pid > 1, "owned PID")
    # proc counters are bounded kernel metadata, not ordinary pinned user files.
    rows = {}
    for name in ("stat", "cmdline", "cgroup", "status"):
        budget.charge(read=16385)
        fd = os.open(f"/proc/{pid}/{name}", os.O_RDONLY | os.O_NOFOLLOW)
        try:
            raw = os.read(fd, 16385)
            require(len(raw) <= 16384, "bounded owned proc metadata")
        finally:
            os.close(fd)
        rows[name] = raw
    status = rows["stat"].decode("ascii")
    closing = status.rfind(")")
    require(closing > 0, "kernel process stat shape")
    fields = status[closing + 2:].split()
    require(len(fields) >= 20, "kernel process stat fields")
    return {"pid": pid, "pgid": int(fields[2]), "session": int(fields[3]),
            "start_ticks": fields[19], "state": fields[0],
            "argv": [x.decode("utf-8", "strict") for x in rows["cmdline"].split(b"\0") if x],
            "cgroup": rows["cgroup"].decode("ascii"),
            "status": rows["status"].decode("ascii"),
            "kernel_bodies": {name: {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                                      "hex": raw.hex()} for name, raw in rows.items()}}


class OwnedHost:
    """One fixed bootstrap/controller; no caller-selected executable code."""
    def __init__(self, runtime, plan, arm, private, child_configuration, bytecode_cache, budget):
        exact_budget(budget)
        require(os.uname().sysname == "Linux" and os.geteuid() == 0,
                "selected Linux root supervisor; agent controller will be unprivileged")
        self.runtime, self.plan, self.arm = runtime, plan, arm
        self.private = absolute(private, True)
        require(stat.S_IMODE(self.private.stat().st_mode) == 0o700
                and self.private.stat().st_uid == 0, "private root-owned owner journal")
        self.budget = budget
        self.end = min(budget.deadline, time.monotonic() + plan["limits"]["seconds"])
        self.actor_end = self.end - plan["limits"]["cleanup_seconds"]
        require(time.monotonic() < self.actor_end < self.end, "actor and closure windows")
        budget.charge(read=runtime["cleanup_read_bytes"], write=runtime["cleanup_write_bytes"])
        self.cleanup_budget = Budget(runtime["cleanup_read_bytes"], runtime["cleanup_write_bytes"],
                                     self.end - time.monotonic())
        self.cleanup_budget.deadline = self.end
        self.token = uuid.uuid4().hex
        self.name = "tms-" + plan["trials"][arm] + "-" + self.token[:12]
        self.cg_budget = CgroupBudget(budget, runtime["host_read_bytes"], runtime["host_write_bytes"],
                                     self.end, runtime["journal_bytes"])
        self.scope = Cgroup(runtime["cgroup_root"], self.name, self.cg_budget, self.end)
        self.cg_budget.scope = self.scope
        self.leaf = None
        self.leaf_removed = False
        self.proc = None
        self.selector = None
        self.streams = {"stdout": bytearray(), "stderr": bytearray()}
        self.child_configuration = child_configuration
        self.bytecode_cache = dict(bytecode_cache)
        self.errors = FailureCarrier()
        self.record = {"schema": "tms_figure2b_owned_host_v1", "token": self.token,
                       "arm": arm, "trial_id": plan["trials"][arm],
                       "intent": None, "owner": None, "completion": None,
                       "bootstrap": None, "host_leaf": None, "host_group": None,
                       "cgroup": None, "streams": None, "source_only_qualification": False}

    def create_scope(self):
        require(self.scope.created is False, "one owned cgroup creation")
        self.scope.create(self.plan["limits"]["ram_bytes"], self.plan["limits"]["pids"])
        quota = self.plan["limits"]["cpu"] * 100000
        require(quota == int(quota) and quota >= 1000, "exact supported cgroup CPU period/quota")
        self.scope.write("cpu.max", f"{int(quota)} 100000")
        self.leaf = self.scope.path / "host"
        self.leaf.mkdir(mode=0o700)
        s = self.leaf.lstat()
        require(s.st_uid == 0 and stat.S_IMODE(s.st_mode) == 0o700, "root-only fixed host leaf")
        self.record["host_leaf"] = {"path": str(self.leaf), "device": s.st_dev, "inode": s.st_ino}
        return str(self.scope.path.relative_to("/sys/fs/cgroup"))

    def launch(self):
        require(self.scope.created and self.leaf is not None and self.proc is None, "scope before bootstrap")
        source = Path(__file__).resolve().parent
        argv = [self.runtime["python"]["path"], "-I", "-B", str(source / "host_bootstrap.py"),
                "--owner", str(self.private / "OWNER.json"), "--token", self.token,
                "--deadline", repr(self.actor_end)]
        argv[3:3] = ["-X", "pycache_prefix=" + self.bytecode_cache["path"]]
        argv.extend(["--cache-prefix", self.bytecode_cache["path"]])
        self.record["intent"] = atomic(self.private, "INTENT.json",
            {"schema": "tms_figure2b_host_intent_v1", "token": self.token,
             "bootstrap_argv": argv, "child_configuration": self.child_configuration,
             "activation_requires_fsynced_owner_and_leaf": True}, self.budget)
        # No provider credential is placed in the argv or environment.
        env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}
        self.proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, start_new_session=True, env=env, bufsize=0)
        self.record["bootstrap"] = {"pid": self.proc.pid, "argv": argv}
        self.selector = selectors.DefaultSelector()
        for key, stream in (("stdout", self.proc.stdout), ("stderr", self.proc.stderr)):
            os.set_blocking(stream.fileno(), False)
            self.selector.register(stream, selectors.EVENT_READ, key)
        ready_path = self.private / "READY.json"
        while not ready_path.exists():
            require(self.proc.poll() is None and time.monotonic() < self.actor_end,
                    "initialized bootstrap ready before work")
            self.drain(.01)
        ready = plain_json(capture(ready_path, self.runtime["journal_bytes"], self.budget))
        require(ready == {"schema": "tms_figure2b_bootstrap_ready_v1", "token": self.token,
                          "pid": self.proc.pid, "pgid": self.proc.pid}, "exact initialized bootstrap")
        observed = inspect_process(self.proc.pid, self.budget)
        require(observed["pid"] == observed["pgid"] == observed["session"] == self.proc.pid
                and observed["argv"] == argv, "observed exact bootstrap before cgroup placement")
        raw = str(self.proc.pid).encode("ascii")
        self.budget.charge(write=len(raw))
        fd = os.open(self.leaf / "cgroup.procs", os.O_WRONLY | os.O_NOFOLLOW)
        try:
            require(os.write(fd, raw) == len(raw), "complete host leaf placement")
        finally:
            os.close(fd)
        placed = inspect_process(self.proc.pid, self.budget)
        relative = "/" + str(self.leaf.relative_to("/sys/fs/cgroup"))
        require(placed["start_ticks"] == observed["start_ticks"]
                and placed["cgroup"].strip() == "0::" + relative, "actual preactivation leaf membership")
        owner = {"schema": "tms_figure2b_host_owner_v1", "token": self.token,
                 "bootstrap": placed, "child_configuration": self.child_configuration,
                 "bytecode_cache": self.bytecode_cache,
                 "python": self.runtime["python"]["path"],
                 "controller": str(source / "host_child.py"),
                 "host_uid": self.runtime["host_uid"], "host_gid": self.runtime["host_gid"],
                 "supplementary_gids": self.runtime["supplementary_gids"],
                 "child_read_bytes": self.runtime["child_read_bytes"],
                 "child_write_bytes": self.runtime["child_write_bytes"],
                 "actor_deadline": self.actor_end, "closure_deadline": self.end}
        self.record["owner"] = atomic(self.private, "OWNER.json", owner, self.budget)
        self.record["gate"] = atomic(self.private, "ACTIVATE.json",
                                    {"token": self.token, "activate": True}, self.budget)
        return self.record["owner"]

    def drain(self, seconds, cleanup=False):
        if self.selector is None:
            return
        cap = self.runtime["metadata_output_bytes"]
        for key, _ in self.selector.select(seconds):
            used = sum(len(v) for v in self.streams.values())
            request = min(8192, cap + 1 - used)
            require(request > 0, "host stream allowance")
            meter = self.cleanup_budget if cleanup else self.budget
            meter.charge(read=request, write=2 * request)
            try:
                block = os.read(key.fileobj.fileno(), request)
            except BlockingIOError:
                continue
            if not block:
                self.selector.unregister(key.fileobj)
                continue
            self.streams[key.data].extend(block)  # Original prefix retained before refusal.
            require(sum(len(v) for v in self.streams.values()) <= cap, "host combined stream cap")

    def wait(self):
        require(self.proc is not None and self.record.get("gate"), "activated owned host")
        completion_path = self.private / "COMPLETION.json"
        while True:
            require(time.monotonic() < self.actor_end, "completion before original actor deadline")
            if completion_path.exists():
                break
            require(self.proc.poll() is None, "bootstrap cannot exit before token-bound child completion")
            remaining = self.actor_end - time.monotonic()
            require(remaining > 0, "poll before original actor deadline")
            self.drain(min(.05, remaining))
            require(time.monotonic() < self.actor_end, "poll preserves original cleanup interval")
            require(self.scope.sample() <= self.plan["limits"]["cpu"] * self.plan["limits"]["seconds"],
                    "owned subtree CPU ceiling")
        body = capture(completion_path, self.runtime["journal_bytes"], self.budget)
        result = plain_json(body)
        require(set(result) == {"schema", "token", "child_pid", "returncode", "natural_wait",
                                "leader_waits_for_owner_stop"} and
                result["schema"] == "tms_figure2b_controller_completion_v1" and
                result["token"] == self.token and type(result["child_pid"]) is int and
                result["child_pid"] > 1 and type(result["returncode"]) is int and
                result["natural_wait"] is True and result["leader_waits_for_owner_stop"] is True,
                "real token-bound controller wait")
        require(time.monotonic() < self.actor_end, "admitted completion before original actor deadline")
        self.record["completion"] = {"path": str(completion_path), **body_pin(body), "value": result}
        require(result["returncode"] == 0, "natural controller zero required")
        return self.record["completion"]

    def stop_host(self):
        """Stop only the exact observed group; cgroup closure follows Docker retirement."""
        row = {"pid": None, "group_absent": False, "reaped": False, "streams_closed": False}
        first = None
        try:
            if self.proc is not None:
                row["pid"] = self.proc.pid
                if self.proc.poll() is None:
                    observed = inspect_process(self.proc.pid, self.cleanup_budget)
                    original = self.record["bootstrap"]
                    require(observed["pgid"] == self.proc.pid and observed["argv"] == original["argv"],
                            "exact owned leader before stop")
                    if self.record.get("owner"):
                        owner = plain_json(capture(self.private / "OWNER.json",
                                                   self.runtime["journal_bytes"], self.cleanup_budget))
                        require(observed["start_ticks"] == owner["bootstrap"]["start_ticks"],
                                "same original bootstrap start")
                    os.killpg(self.proc.pid, signal.SIGKILL)
                self.proc.wait(timeout=max(.001, self.end - time.monotonic()))
                row["reaped"] = True
                while self.selector is not None and self.selector.get_map() and time.monotonic() < self.end:
                    self.drain(.01, cleanup=True)
                try:
                    os.killpg(self.proc.pid, 0)
                except ProcessLookupError:
                    row["group_absent"] = True
                require(row["group_absent"], "owned host group absent")
        except BaseException as error:
            first = error
            self.errors.fail(error, "stop-owned-host")
        finally:
            closed = True
            for stream in (() if self.proc is None else (self.proc.stdout, self.proc.stderr)):
                try:
                    stream.close()
                except BaseException as error:
                    closed = False
                    self.errors.fail(error, "close-host-stream")
                    if first is None:
                        first = error
            if self.selector is not None:
                try:
                    self.selector.close()
                except BaseException as error:
                    closed = False
                    self.errors.fail(error, "close-host-selector")
                    if first is None:
                        first = error
            row["streams_closed"] = closed
            self.record["host_group"] = row
            self.record["streams"] = {key: {"bytes": len(value), "sha256": hashlib.sha256(value).hexdigest(),
                                           "base64": base64.b64encode(value).decode("ascii")}
                                      for key, value in self.streams.items()}
        if first is not None:
            raise first

    def finish_scope(self):
        require(self.scope.created and self.leaf is not None, "created owned scope")
        expected = self.record["host_leaf"]
        if self.leaf_removed:
            require(not self.leaf.exists() and not self.leaf.is_symlink(),
                    "previously removed original host leaf remains absent")
        else:
            s = self.leaf.lstat()
            require((s.st_dev, s.st_ino) == (expected["device"], expected["inode"]), "same fixed host leaf")
            self.cleanup_budget.charge(read=16385)
            fd = os.open(self.leaf / "cgroup.procs", os.O_RDONLY | os.O_NOFOLLOW)
            try:
                body = os.read(fd, 16385)
                require(len(body) <= 16384 and not body.strip(), "all direct host-leaf processes absent")
            finally:
                os.close(fd)
            self.leaf.rmdir()
            self.leaf_removed = True
            self.record["host_leaf_removal"] = dict(expected)
        self.record["cgroup"] = self.scope.finish()
        require(not self.cg_budget.unknown and self.record["cgroup"]["complete"]
                and self.record["cgroup"]["populated"] is False, "complete actual owned subtree absence")
        return self.record["cgroup"]

    def recover_scope(self):
        """One bounded recovery after failure; never erases the original failure.

        Uses only the original selected cgroup/cleanup allocations and deadline.
        Exhausted allowance or unverifiable population remains unknown failure.
        The unchanged donor keeps every actual kernel event, including errors.
        """
        observation = {"schema": "tms_figure2b_failed_scope_recovery_v1",
                       "kill_sent": False, "empty_observed": False,
                       "final_counter_removal_attempted": False, "complete": False,
                       "error_type": None, "changes_original_run_status": False}
        self.record["scope_recovery"] = observation
        try:
            require(self.scope.created, "only original created scope recovery")
            if self.scope.closed:
                observation["already_removed_by_original_finish"] = True
                require(not self.cg_budget.unknown and self.scope.final["complete"] is True,
                        "original removed scope still requires known accounting")
                observation["complete"] = True
                return observation
            self.cleanup_budget.charge()
            require(time.monotonic() < self.end, "original cleanup deadline before kill")
            self.scope.emergency_kill()
            observation["kill_sent"] = True
            while True:
                self.cleanup_budget.charge()
                require(time.monotonic() < self.end, "original bounded population re-observation")
                text = self.scope.read("cgroup.events")
                entries = [line.split() for line in text.splitlines()]
                require(all(len(row) == 2 for row in entries)
                        and len({row[0] for row in entries}) == len(entries),
                        "complete unique actual population fields")
                fields = dict(entries)
                require(fields.get("populated") in ("0", "1"), "known actual descendant population")
                if fields["populated"] == "0":
                    observation["empty_observed"] = True
                    break
                remaining = self.end - time.monotonic()
                require(remaining > 0, "remaining original cleanup time")
                time.sleep(min(.01, remaining))
            observation["final_counter_removal_attempted"] = True
            self.finish_scope()
            observation["complete"] = True
            return observation
        except BaseException as error:
            observation["error_type"] = type(error).__name__
            self.errors.fail(error, "failed-scope-recovery")
            raise
