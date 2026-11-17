"""Paired whole-programme FIND032 Docker owner; no execution on import.

The enclosing captured controller supplies an admitted frozen programme, full
staged view and exact existing runtime. This module never supplies qualifications,
decodes arrays, evaluates a candidate artifact, or opens protected grading data.
"""
import base64
import hashlib
import math
import os
import re
import stat
import time
from pathlib import Path

from . import docker_transport as transport


CONFIG_KEYS = frozenset(("binary", "socket", "image", "memory_bytes", "nano_cpus",
                         "pids_limit", "scratch_bytes", "volume_bytes", "stdio_bytes",
                         "fd_limit", "member_bytes", "metadata_bytes", "file_count"))
CHUNK = 65536
CHUNK_REPLY = 2048 + 4 * ((CHUNK + 2) // 3)
THREAD_ENV = {key: "1" for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                                  "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
                                  "VECLIB_MAXIMUM_THREADS")}
FIXED_ENV = {**THREAD_ENV, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1"}
IMAGE_ENV_KEYS = frozenset(("PATH", "LANG", "LC_ALL", "PYTHON_VERSION", "PYTHON_SHA256",
                            "GPG_KEY", "PYTHON_SETUPTOOLS_VERSION", "PYTHON_PIP_VERSION",
                            "PYTHON_GET_PIP_URL", "PYTHON_GET_PIP_SHA256", *FIXED_ENV))


def require(ok, why):
    if not ok:
        raise ValueError(why)


def pin(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def environment(rows):
    require(type(rows) is list, "explicit image environment")
    result = {}
    for value in rows:
        require(type(value) is str and "=" in value and "\x00" not in value,
                "ordinary environment entry")
        key, value = value.split("=", 1)
        require(key in IMAGE_ENV_KEYS and key not in result and len(value) <= 4096,
                "closed noncredential environment keys")
        result[key] = value
    require(result.get("PATH"), "fixed image Python lookup path")
    return result


def ordinary_path(value, directory=False):
    require(isinstance(value, (str, Path)) and Path(value).is_absolute(), "absolute path")
    result = transport.path(value)
    observed = result.lstat()
    require(stat.S_ISDIR(observed.st_mode) if directory else
            stat.S_ISREG(observed.st_mode) and observed.st_nlink == 1,
            "ordinary unaliased file/directory")
    return result


def names_empty(directory):
    # Stop on the first entry; do not enumerate an ambient config directory.
    with os.scandir(directory) as entries:
        require(next(entries, None) is None, "fresh empty controller Docker config")


def config(value):
    require(type(value) is dict and set(value) == CONFIG_KEYS, "closed Docker profile")
    result = dict(value)
    for key in CONFIG_KEYS - {"binary", "socket", "image"}:
        require(type(result[key]) is int and result[key] > 0, "positive selected " + key)
    require(type(result["image"]) is str and re.fullmatch(r"sha256:[0-9a-f]{64}", result["image"]),
            "immutable supplied local image digest")
    result["binary"] = str(ordinary_path(result["binary"]))
    require(os.access(result["binary"], os.X_OK), "existing executable Docker CLI")
    require(type(result["socket"]) is str and Path(result["socket"]).is_absolute(), "absolute socket")
    socket = transport.path(result["socket"])
    require(stat.S_ISSOCK(socket.lstat().st_mode), "existing local Docker socket")
    result["socket"] = str(socket)
    require(result["metadata_bytes"] <= result["member_bytes"] <= result["volume_bytes"],
            "nested selected output bounds")
    require(result["metadata_bytes"] >= 128 and result["fd_limit"] >= 16,
            "usable selected fixed metadata/descriptor envelope")
    return result


class ArmFailure(RuntimeError):
    def __init__(self, session):
        super().__init__("FIND032 arm failed; original errors and partial ownership retained")
        self.session = session
        self.first = session.first
        self.secondary = tuple(session.errors[1:])


class ArmSession:
    """Strong lifetime owner; report() is evidence, never closure authority."""
    def __init__(self, cfg, arm, ownership, budget, custody, stage_root, output_root,
                 normal_end, cleanup_end, cleanup_budget, attach_receipt):
        self.input_cfg = cfg
        self.arm = arm
        self.ownership = ownership
        self.budget = budget
        self.cleanup_budget = cleanup_budget
        self.attach_receipt = attach_receipt
        self.custody = custody
        self.stage_root = stage_root
        self.output_root = output_root
        self.normal_end = normal_end
        self.cleanup_end = cleanup_end
        self.cfg = None
        self.docker = None
        self.rows = {}
        self.closures = {}
        self.retirement_attempted = set()
        self.originals = []
        self.original_stdio = None
        self.errors = []
        self.first = None
        self.natural_exit = None
        self.candidate_closed = False
        self.inventory_rows = None
        self.inventory_attempted = False
        self.members_attempted = set()
        self.metadata_captured = False
        self.captured = []
        self.close_attempted = False
        self.closed = False
        self.image_environment = None
        self.stage_identity = None
        self.config_identity = None

    def _error(self, boundary, error):
        self.errors.append({"boundary": boundary, "raw": error,
                            "traceback": error.__traceback__})
        if self.first is None:
            self.first = error
        # Cleanup's independent budget is deliberately not poisoned by this
        # parent error occurrence; all later cleanup attempts remain selected.
        try:
            self.custody.catch(boundary, error)
        except BaseException as publication:
            self.errors.append({"boundary": boundary + " custody publication",
                                "raw": publication, "traceback": publication.__traceback__})

    def _command(self, args, end, phase, cap=131072, *, cleanup=False):
        budget = self.cleanup_budget if cleanup else self.budget
        require(type(cap) is int and cap > 0, "selected CLI byte cap")
        require(end <= (self.cleanup_end if cleanup else self.normal_end), "no renewed deadline")
        end = min(end, budget.deadline)
        token = budget.reserve("read", cap + 1)
        # Both streams and a possible returned immutable stdout copy remain
        # charged. The carrier is retained until the parent closes its owner.
        memory = budget.reserve("write", 2 * (cap + 1))
        previous = self.docker.last_original
        raw = None
        first = None
        try:
            raw = self.docker(args, end, phase, cap)
        except BaseException as error:
            first = error
        finally:
            original = self.docker.last_original
            if original is not None and original is not previous:
                self.originals.append(original)
                if phase == "candidate_attach":
                    self.original_stdio = original
                # Do this only after the strong original is held. A refusal
                # before a new CLI carrier leaves its reservation unknown.
                observed = len(original["rawstdout"]) + len(original["rawstderr"])
                try:
                    budget.observed(token, observed)
                    budget.observed(memory, observed + len(original["original_result"] or b""))
                except BaseException as accounting:
                    if first is None:
                        first = accounting
                    else:
                        # Preserve chronology when accounting itself fails;
                        # the CLI exception is already the first failure.
                        if self.first is None:
                            self._error(phase, first)
                        self._error(phase + " accounting", accounting)
        if first is not None:
            raise first
        return raw

    def _normal(self, args, end, phase, cap=131072):
        return self._command(args, end, phase, cap)

    def _cleanup(self, args, end, phase, cap=131072):
        return self._command(args, end, phase, cap, cleanup=True)

    def _reserve(self, role, kind):
        row = self.ownership.reserve(role)
        require(type(row) is dict and set(row) == {"case_index", "role", "kind", "name",
                                                  "owner", "attempted", "acknowledged"},
                "parent-only original ownership row")
        require(row["role"] == role and row["kind"] == kind and row["attempted"] is False
                and row["acknowledged"] is False and type(row["case_index"]) is int
                and row["case_index"] in (0, 1), "fresh parent ownership intent")
        require(re.fullmatch(r"slicetca-[0-9a-f]{24}-" + role, row["name"])
                and row["owner"] == row["name"].rsplit("-", 1)[0] + "/" + role,
                "unchanged exact owner/name namespace")
        self.rows[role] = dict(row)
        return self.rows[role]

    def _before(self, row):
        require(transport.resource_inventory(self._normal, row, row["owner"], self.normal_end,
                                             "before_" + row["role"]) == [],
                "fresh exact empty label/name; collision not deleted")

    def _attempt(self, row):
        # Parent persists intent before acknowledgment; if the channel fails,
        # local attempted=True conservatively retains possible creation duty.
        row["attempted"] = True
        self.ownership.attempt(row["role"])

    def _ack(self, row, identifier):
        # A lost ack never resets attempted. Recovery can discover an exact
        # owned resource from parent intent even without the returned ID.
        self.ownership.ack(row["role"], identifier)
        row["acknowledged"] = True
        if row["kind"] == "container":
            row["id"] = identifier

    def _retire(self, role, end):
        require(role not in self.retirement_attempted, "no automatic resource retirement retry")
        self.retirement_attempted.add(role)
        row = self.rows[role]
        try:
            result = transport.retire(self._cleanup, row, end)
        except BaseException as original:
            self._error("retire " + role, original)
            failed = {"kind": row["kind"], "name": row["name"], "closed": False,
                      "error_type": type(original).__name__}
            self.closures[role] = failed
            try:
                self.ownership.retired(role, failed)
            except BaseException as publication:
                self._error("retire " + role + " publication", publication)
            raise
        self.closures[role] = result
        self.ownership.retired(role, result)
        require(result["closed"] is True, "resource closure not established")
        return result

    def _helper_command(self, action, extra=()):
        result = ["python", "-I", "-B", "/trusted/holder.py", action]
        for key in ("member_bytes", "metadata_bytes", "file_count", "volume_bytes"):
            result += ["--" + key.replace("_", "-"), str(self.cfg[key])]
        return result + list(extra)

    def _container_args(self, row, role, mounts):
        cfg = self.cfg
        nano = cfg["nano_cpus"]
        cpus = str(nano // 1000000000) + "." + str(nano % 1000000000).zfill(9)
        command = (self._helper_command("hold") if role == "holder" else
                   ["python", "-I", "-B", "/candidate.py", "--view", "/view",
                    "--contract", "/contract.json", "--output", "/output"])
        result = ["container", "create", "--pull", "never", "--name", row["name"],
                  "--label", transport.LABEL + "=" + row["owner"],
                  "--network", "none", "--read-only", "--user", "65534:65534",
                  "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                  "--cgroupns", "private", "--ipc", "private", "--restart", "no",
                  "--log-driver", "none", "--memory", str(cfg["memory_bytes"]),
                  "--memory-swap", str(cfg["memory_bytes"]), "--cpus", cpus,
                  "--pids-limit", str(cfg["pids_limit"]), "--shm-size", str(cfg["scratch_bytes"]),
                  "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=" + str(cfg["scratch_bytes"]),
                  "--ulimit", "core=0:0", "--ulimit", "nofile=" + str(cfg["fd_limit"]) + ":" + str(cfg["fd_limit"]),
                  "--ulimit", "fsize=" + str(cfg["member_bytes"]) + ":" + str(cfg["member_bytes"]),
                  "--workdir", "/tmp", "--no-healthcheck"]
        for key, value in sorted(FIXED_ENV.items()):
            result += ["--env", key + "=" + value]
        return result + transport.mounts_argv(mounts) + ["--entrypoint", "python", cfg["image"], *command[1:]]

    def _admit_container(self, value, row, role, mounts):
        transport.owned(value, row, row["owner"])
        host = value["HostConfig"]
        conf = value["Config"]
        cfg = self.cfg
        expected = (self._helper_command("hold")[1:] if role == "holder" else
                    ["-I", "-B", "/candidate.py", "--view", "/view", "--contract", "/contract.json",
                     "--output", "/output"])
        require(value["Image"] == conf["Image"] == cfg["image"] and conf["Entrypoint"] == ["python"]
                and conf["Cmd"] == expected and conf["User"] == "65534:65534"
                and conf["WorkingDir"] == "/tmp", "exact fixed image/user/command")
        require(environment(conf["Env"]) == {**self.image_environment, **FIXED_ENV}, "exact closed runtime environment")
        require(conf.get("Healthcheck", {}).get("Test") == ["NONE"] and not conf.get("Volumes")
                and conf.get("OpenStdin") is False and conf.get("Tty") is False,
                "no implicit volume, stdin, TTY or health programme")
        for key, selected in (("Memory", "memory_bytes"), ("MemorySwap", "memory_bytes"),
                              ("NanoCpus", "nano_cpus"), ("PidsLimit", "pids_limit"),
                              ("ShmSize", "scratch_bytes")):
            require(type(host[key]) is int and host[key] == cfg[selected], "actual " + key)
        require(host["NetworkMode"] == "none" and host["ReadonlyRootfs"] is True
                and host["CgroupnsMode"] == "private" and host["LogConfig"] == {"Type": "none", "Config": {}},
                "no network, mutable root or daemon logs")
        require(host.get("Privileged") is False and not host.get("CapAdd") and not host.get("Devices")
                and not host.get("DeviceRequests") and host.get("PidMode") in ("", "private")
                and host.get("IpcMode") == "private" and not host.get("VolumesFrom")
                and not host.get("Links") and not host.get("ExtraHosts") and not host.get("GroupAdd"),
                "no elevated caps, devices, host namespaces or implicit bindings")
        require(host["CapDrop"] == ["ALL"] and host["SecurityOpt"] in (["no-new-privileges"], ["no-new-privileges=true"])
                and host["RestartPolicy"] == {"Name": "no", "MaximumRetryCount": 0}
                and host["AutoRemove"] is False, "fixed security/restart/removal policy")
        require(host["Tmpfs"] == {"/tmp": "rw,nosuid,nodev,noexec,size=" + str(cfg["scratch_bytes"])},
                "only bounded scratch tmpfs")
        limits = host["Ulimits"]
        require(type(limits) is list and len(limits) == 3
                and {x["Name"]: (x["Soft"], x["Hard"]) for x in limits} ==
                {"core": (0, 0), "nofile": (cfg["fd_limit"], cfg["fd_limit"]),
                 "fsize": (cfg["member_bytes"], cfg["member_bytes"])}, "exact descriptor/file/core limits")
        actual = value["Mounts"]
        require(type(actual) is list and len(actual) == len(mounts)
                and all(type(x["RW"]) is bool for x in actual), "finite actual mount set")
        observed = {x["Destination"]: (x["Type"], x["Name"] if x["Type"] == "volume" else x["Source"], x["RW"])
                    for x in actual}
        require(observed == {k: (kind, str(source), rw) for k, (kind, source, rw) in mounts.items()}
                and all(not rw for kind, source, rw in mounts.values() if kind == "bind"),
                "exact readonly host bindings and selected output volume only")
        state = value["State"]
        require(state["Status"] == "created" and state["Running"] is False and state["Pid"] == 0,
                "inspect actual created container before start")

    def _create_container(self, role, mounts):
        row = self._reserve(role, "container")
        self._before(row)
        self._attempt(row)
        raw = transport.call(self._normal, self._container_args(row, role, mounts), self.normal_end,
                             "create_" + role, 4096, 12)
        identifier = raw.decode("ascii").strip()
        require(re.fullmatch(r"[0-9a-f]{64}", identifier), "exact returned container identifier")
        self._ack(row, identifier)
        self._admit_container(transport.inspect(self._normal, "container", identifier, self.normal_end,
                                                "admit_" + role), row, role, mounts)
        return row

    def start(self):
        require(self.arm in ("A", "B") and type(self.arm) is str, "one exact paired arm")
        require(self.cleanup_budget is not self.budget
                and self.cleanup_budget.custody is not self.budget.custody
                and self.cleanup_budget.custody is not self.custody, "independent precreated cleanup budget")
        require(all(type(x) in (int, float) and math.isfinite(x) for x in (self.normal_end, self.cleanup_end))
                and time.monotonic() < self.normal_end < self.cleanup_end
                and self.budget.deadline <= self.normal_end
                and self.cleanup_budget.deadline == self.cleanup_end,
                "original work and cleanup cutoffs, no renewed clock")
        self.cfg = config(self.input_cfg)
        self.stage_root = ordinary_path(self.stage_root, True)
        self.output_root = ordinary_path(self.output_root, True)
        require(self.output_root == self.stage_root / "captured",
                "exact private parent capture directory, never mounted")
        self.stage_identity = (self.stage_root.stat().st_dev, self.stage_root.stat().st_ino)
        view = ordinary_path(self.stage_root / "view", True)
        program = ordinary_path(self.stage_root / "program.py")
        contract = ordinary_path(self.stage_root / "contract.json")
        # The controller writes its exact captured source bytes here before this
        # call; mounting the original source path would re-read an uncaptured body.
        helper = ordinary_path(self.stage_root / "holder.py")
        require(stat.S_IMODE(helper.stat().st_mode) == 0o444, "frozen captured holder source")
        config_root = ordinary_path(self.stage_root / "docker-config", True)
        config_stat = config_root.stat()
        require(stat.S_IMODE(config_stat.st_mode) == 0o700 and config_stat.st_uid == os.geteuid(),
                "controller-only empty Docker configuration")
        names_empty(config_root)
        self.config_identity = (config_stat.st_dev, config_stat.st_ino)
        self.docker = transport.Docker(self.cfg["binary"], self.cfg["socket"])
        self.docker.env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "DOCKER_CONFIG": str(config_root)}
        image = transport.parse(transport.call(self._normal, ["image", "inspect", self.cfg["image"], "--format", "{{json .}}"],
                                              self.normal_end, "image", 131072))
        require(image["Id"] == self.cfg["image"] and not image["Config"].get("Volumes")
                and (not image["Config"].get("Healthcheck")
                     or image["Config"]["Healthcheck"].get("Test") == ["NONE"]),
                "existing pinned image without implicit volumes/health programmes")
        self.image_environment = environment(image["Config"]["Env"])
        volume = self._reserve("volume", "volume")
        self._before(volume)
        self._attempt(volume)
        volume_options = "size=" + str(self.cfg["volume_bytes"]) + ",uid=65534,gid=65534,mode=0770,noexec,nosuid,nodev"
        returned = transport.call(self._normal, ["volume", "create", "--driver", "local", "--label",
                                  transport.LABEL + "=" + volume["owner"], "--opt", "type=tmpfs", "--opt", "device=tmpfs",
                                  "--opt", "o=" + volume_options, volume["name"]], self.normal_end, "create_volume", 4096).decode("ascii").strip()
        require(returned == volume["name"], "exact volume acknowledgment")
        self._ack(volume, returned)
        value = transport.inspect(self._normal, "volume", volume["name"], self.normal_end, "admit_volume")
        transport.owned(value, volume, volume["owner"])
        require(value["Driver"] == "local" and value["Options"] ==
                {"type": "tmpfs", "device": "tmpfs", "o": volume_options}, "exact bounded tmpfs output volume")
        holder_mounts = {"/trusted/holder.py": ("bind", helper, False), "/capture": ("volume", volume["name"], False)}
        holder = self._create_container("holder", holder_mounts)
        started = transport.call(self._normal, ["container", "start", holder["id"]], self.normal_end, "start_holder", 4096)
        require(started.decode("ascii").strip() == holder["id"], "exact holder start acknowledgment")
        ready = transport.parse(transport.call(self._normal, ["exec", holder["id"], *self._helper_command("ready")],
                                              self.normal_end, "holder_ready", self.cfg["metadata_bytes"]))
        require(ready == {"schema": "find032_holder_ready_v1", "ready": True}, "actual fixed live holder")
        mounts = {"/view": ("bind", view, False), "/candidate.py": ("bind", program, False),
                  "/contract.json": ("bind", contract, False), "/output": ("volume", volume["name"], True)}
        candidate = self._create_container("candidate", mounts)
        try:
            self._command(["container", "start", "--attach", candidate["id"]], self.normal_end,
                          "candidate_attach", self.cfg["stdio_bytes"])
        except BaseException as error:
            self._error("original candidate attach", error)
        # This happens before inspection or run_arm's possibly long retirement.
        # The precreated receipt has independent resources and an inner reserve
        # before the parent's original normal-admission cutoff.
        if self.original_stdio is not None:
            try:
                self.attach_receipt.publish(self.original_stdio, self.first)
            except BaseException as error:
                self._error("original attach evidence publication", error)
        if self.first is not None:
            raise self.first
        require(self.original_stdio is not None, "strong original candidate streams")
        value = transport.inspect(self._normal, "container", candidate["id"], self.normal_end, "candidate_exit")
        transport.owned(value, candidate, candidate["owner"])
        state = value["State"]
        require(state["Status"] == "exited" and state["Running"] is False and state["Dead"] is False
                and type(state["Pid"]) is int and state["Pid"] == 0
                and type(state["ExitCode"]) is int and state["ExitCode"] == 0 and state["OOMKilled"] is False,
                "observed natural zero non-OOM candidate exit")
        self.natural_exit = {k: state[k] for k in ("Status", "Running", "Dead", "Pid", "ExitCode", "OOMKilled")}
        self._retire("candidate", self.normal_end)
        require(self.docker.reaped, "all owned CLI groups closed before output capture")
        self.candidate_closed = True
        self.budget.checkpoint()
        return self

    def _capture_ready(self):
        require(self.candidate_closed and not self.close_attempted and self.first is None
                and self.closures.get("candidate", {}).get("closed") is True,
                "candidate removal and absence precede output access")
        self.budget.checkpoint()

    def inventory(self):
        try:
            self._capture_ready()
            require(not self.inventory_attempted, "single exact output inventory; no automatic retry")
            self.inventory_attempted = True
            bound = min(self.cfg["volume_bytes"], self.cfg["file_count"] * self.cfg["member_bytes"])
            content = self.budget.reserve("read", bound)
            entries = self.budget.reserve("files", self.cfg["file_count"])
            raw = transport.call(self._normal, ["exec", self.rows["holder"]["id"], *self._helper_command("inventory")],
                                 self.normal_end, "output_inventory", self.cfg["metadata_bytes"],
                                 max(1, self.normal_end - time.monotonic()))
            value = transport.parse(raw)
            require(type(value) is dict and set(value) == {"schema", "files", "body_bytes_read"}
                    and value["schema"] == "find032_holder_inventory_v1", "closed holder inventory")
            rows = value["files"]
            require(type(rows) is list and 0 < len(rows) <= self.cfg["file_count"], "whole bounded output inventory")
            for row in rows:
                require(type(row) is dict and set(row) == {"name", "bytes", "sha256"}
                        and type(row["name"]) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", row["name"])
                        and type(row["bytes"]) is int and 0 < row["bytes"] <= self.cfg["member_bytes"]
                        and type(row["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", row["sha256"]),
                        "exact ordinary output descriptor")
            require([x["name"] for x in rows] == sorted({x["name"] for x in rows})
                    and type(value["body_bytes_read"]) is int
                    and value["body_bytes_read"] == sum(x["bytes"] for x in rows) <= bound,
                    "complete sorted unique inventory and observed content bytes")
            self.budget.observed(content, value["body_bytes_read"])
            self.budget.observed(entries, len(rows))
            self.inventory_rows = tuple(dict(x) for x in rows)
            return [dict(x) for x in rows]
        except BaseException as error:
            self._error("output inventory", error)
            raise ArmFailure(self) from self.first

    def read_member(self, row):
        try:
            self._capture_ready()
            require(self.inventory_rows is not None and type(row) is dict
                    and any(row == selected for selected in self.inventory_rows), "exact inventoried request")
            member = row["name"]
            require(member not in self.members_attempted, "no automatic output read retry")
            if not self.metadata_captured:
                require(member.endswith(".json") and row["bytes"] <= self.cfg["metadata_bytes"],
                        "bounded result metadata must be captured first")
            else:
                require(member.endswith((".json", ".npz", ".pdf")), "metadata or exact selected product request")
                if member.endswith(".json"):
                    require(row["bytes"] <= self.cfg["metadata_bytes"], "bounded additional metadata")
            self.members_attempted.add(member)
            retain = self.budget.reserve("write", 2 * row["bytes"])
            blocks = []
            offset = 0
            digest = hashlib.sha256()
            while offset < row["bytes"]:
                length = min(CHUNK, row["bytes"] - offset)
                remote = self.budget.reserve("read", length)
                extra = ["--name", member, "--offset", str(offset), "--length", str(length),
                         "--expected-bytes", str(row["bytes"])]
                raw = transport.call(self._normal, ["exec", self.rows["holder"]["id"],
                                                   *self._helper_command("chunk", extra)],
                                     self.normal_end, "capture_" + member, CHUNK_REPLY)
                obj = transport.parse(raw)
                require(type(obj) is dict and set(obj) == {"schema", "name", "file_bytes", "offset", "chunk_bytes", "chunk_sha256", "base64"}
                        and obj["schema"] == "find032_holder_chunk_v1" and obj["name"] == member
                        and type(obj["file_bytes"]) is int and obj["file_bytes"] == row["bytes"]
                        and type(obj["offset"]) is int and obj["offset"] == offset
                        and type(obj["chunk_bytes"]) is int and obj["chunk_bytes"] == length
                        and type(obj["base64"]) is str and len(obj["base64"]) == 4 * ((length + 2) // 3),
                        "exact fixed holder chunk response")
                body = base64.b64decode(obj["base64"], validate=True)
                require(len(body) == length and hashlib.sha256(body).hexdigest() == obj["chunk_sha256"],
                        "actual opaque captured chunk")
                self.budget.observed(remote, len(body))
                blocks.append(body)
                digest.update(body)
                offset += length
            require(digest.hexdigest() == row["sha256"], "full opaque member joins original inventory")
            result = b"".join(blocks)
            self.budget.observed(retain, 2 * len(result))
            self.budget.checkpoint()
            self.metadata_captured = True
            self.captured.append(dict(row))
            return result
        except BaseException as error:
            self._error("output member capture", error)
            raise ArmFailure(self) from self.first

    def close(self):
        if self.close_attempted:
            if self.first is not None or not self.closed:
                raise ArmFailure(self) from self.first
            return
        self.close_attempted = True
        for role in ("candidate", "holder", "volume"):
            if role in self.rows and role not in self.retirement_attempted:
                try:
                    self._retire(role, self.cleanup_end)
                except BaseException as error:
                    self._error("retire " + role, error)
        self.closed = (all(self.closures.get(role, {}).get("closed") is True for role in self.rows)
                       and (self.docker is None or self.docker.reaped))
        if not self.closed and self.first is None:
            self._error("whole arm close", RuntimeError("resource or CLI closure remains unknown"))
        if self.first is not None:
            raise ArmFailure(self) from self.first

    def report(self):
        originals = []
        for original in self.originals:
            originals.append({"command": list(original["command"]), "record": original["record"],
                              "stdout": pin(original["rawstdout"]), "stderr": pin(original["rawstderr"]),
                              "error_type": type(original["exception"]).__name__ if original["exception"] else None,
                              "secondary_error_types": [type(x).__name__ for x in original["secondary_exceptions"]],
                              "wait_returns": list(original["wait_returns"]), "eof": original["eof"]})
        resource = None if self.cfg is None else {
            "concurrent_memory_bytes": 2 * self.cfg["memory_bytes"],
            "concurrent_nano_cpus": 2 * self.cfg["nano_cpus"],
            "concurrent_pids_limit": 2 * self.cfg["pids_limit"],
            "tmp_and_shm_bytes": 4 * self.cfg["scratch_bytes"],
            "output_volume_bytes": self.cfg["volume_bytes"],
            "tmpfs_accounting": "separately reserved conservatively; image/runtime qualification remains external"}
        return {"schema": "find032_arm_lifecycle_v1", "arm": self.arm,
                "normal_end": self.normal_end, "cleanup_end": self.cleanup_end,
                "rows": {key: dict(value) for key, value in self.rows.items()},
                "closures": dict(self.closures), "candidate_closed_before_capture": self.candidate_closed,
                "natural_exit": self.natural_exit, "all_resources_closed": self.closed,
                "cli_reaped": self.docker.reaped if self.docker is not None else None,
                "captured": list(self.captured), "commands": originals,
                "errors": [{"boundary": x["boundary"], "type": type(x["raw"]).__name__} for x in self.errors],
                "normal_accounting": self.budget.report(), "cleanup_accounting": self.cleanup_budget.report(),
                "selected_resource_sum": resource, "scientific_or_native_qualification": False,
                "authority": "report is not a replacement for live parent ownership and native closure observations"}


def run_arm(cfg, arm, ownership, budget, custody, stage_root, output_root, normal_end,
            cleanup_end, *, cleanup_budget, attach_receipt):
    session = ArmSession(cfg, arm, ownership, budget, custody, stage_root, output_root,
                         normal_end, cleanup_end, cleanup_budget, attach_receipt)
    try:
        return session.start()
    except BaseException as error:
        session._error("arm startup or candidate", error)
        # One original close pass, independent of failed normal Budget. The
        # exception retains the session; subsequent close() never retries it.
        try:
            session.close()
        except ArmFailure:
            pass
        raise ArmFailure(session) from session.first
