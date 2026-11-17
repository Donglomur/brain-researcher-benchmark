"""Exact isolated offline-actor Docker profile; numerical profiles are unchanged."""
IMAGE = 'sha256:9aaf44dc64d85d0bbb0ffdd75ff5190ad94eff91d76849d14aea859c930955ff'
MEMORY = 64 * 1024**2
PIDS = 8
NANO_CPUS = 250000000
THREADS = ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "OMP_THREAD_LIMIT",
           "MKL_NUM_THREADS", "NUMBA_NUM_THREADS", "NUMEXPR_NUM_THREADS")
TMPFS = {"/state": "rw,noexec,nosuid,nodev,size=8388608,uid=65534,gid=65534,mode=0700",
         "/tmp": "rw,noexec,nosuid,nodev,size=4194304,mode=1777"}
COMMAND = ["-I", "-B", "/actor/program.py"]
STREAM_LIMITS = {"messages": 1024, "stdout_bytes": 4194304,
                 "stderr_bytes": 16384, "raw_bytes": 8388608, "stdin_bytes": 67108864,
                 "line_bytes": 65536}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def descriptor():
    return {"schema": "isolated-offline-actor-profile/v1", "image": IMAGE,
            "memory_bytes": MEMORY, "pids": PIDS, "nano_cpus": NANO_CPUS,
            "network": "none", "host_sockets": False, "writable_shared_state": False,
            "cpu_charge_kind": "full PIDS times declared arm wall upper bound",
            "model_calls": 0, "stream_limits": dict(STREAM_LIMITS),
            "actor_user_cpu_ulimit_seconds": [20, 22]}


def canonical(role, mounts, profile):
    need(role == "offline_actor" and profile == descriptor(), "Exact actor profile")
    need(type(mounts) is dict and set(mounts) == {"/actor/program.py"},
         "Only this actor's source file may be mounted")
    row = mounts["/actor/program.py"]
    need(type(row) is dict and set(row) == {"type", "source", "rw"} and
         row["type"] == "bind" and row["rw"] is False and
         type(row["source"]) is str and row["source"].startswith("/") and
         not row["source"].startswith("/host_mnt/") and
         not any(c in row["source"] for c in (",", "\n", "\r", "\0")),
         "One literal read-only program bind")
    return True


def argv(name, role, mounts, profile):
    canonical(role, mounts, profile)
    args = ["create", "--pull", "never", "--name", name, "--interactive",
            "--attach", "stdin", "--attach", "stdout", "--attach", "stderr",
            "--ipc", "private", "--cgroupns", "private",
            "--network", "none", "--read-only", "--user", "65534:65534",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
            "--memory", str(MEMORY), "--memory-swap", str(MEMORY),
            "--cpus", "0.25", "--pids-limit", str(PIDS), "--restart", "no",
            "--log-driver", "none", "--ulimit", "cpu=20:22",
            "--ulimit", "nofile=64:64", "--ulimit", "core=0:0",
            "--ulimit", "fsize=1048576:1048576", "--workdir", "/state",
            "--mount", "type=bind,src=" + mounts["/actor/program.py"]["source"] +
            ",dst=/actor/program.py,readonly"]
    for dest, options in TMPFS.items():
        args += ["--tmpfs", dest + ":" + options]
    for key in THREADS:
        args += ["--env", key + "=1"]
    return args + ["--env", "PYTHONDONTWRITEBYTECODE=1", "--entrypoint",
                   "python", IMAGE, *COMMAND]


def source_matches(actual, expected):
    return actual == expected or (expected.startswith("/Users/") and
                                  actual == "/host_mnt" + expected)


def verify(info, name, role, mounts, profile):
    canonical(role, mounts, profile)
    h, c, s = info["HostConfig"], info["Config"], info["State"]
    need(info["Name"] == "/" + name and info["Image"] == c["Image"] == IMAGE and
         c["Entrypoint"] == ["python"] and c["Cmd"] == COMMAND and
         c["WorkingDir"] == "/state", "Exact actor image/command/location")
    need(s["Status"] == "created" and s["Running"] is False and s["Pid"] == 0,
         "Inspect before starting the actor")
    need(c["Tty"] is False and c["OpenStdin"] is True and
         all(c[k] is True for k in ("AttachStdin", "AttachStdout", "AttachStderr")) and
         type(c["StdinOnce"]) is bool, "Non-TTY interactive streams")
    need(h["NetworkMode"] == "none" and h["ReadonlyRootfs"] is True and
         h["Privileged"] is False and c["User"] == "65534:65534",
         "Offline nonroot readonly actor")
    need(h.get("CapDrop") == ["ALL"] and not h.get("CapAdd") and
         "no-new-privileges:true" in h.get("SecurityOpt", []) and
         not h.get("Devices") and not h.get("DeviceRequests") and not h.get("PortBindings") and
         h.get("PidMode") == "" and h.get("UTSMode") == "" and
         h.get("IpcMode") == "private" and h.get("CgroupnsMode") == "private" and
         not h.get("Binds") and not h.get("VolumesFrom"),
         "No extra device, bind, inherited volume or host namespace")
    need(set(info.get("NetworkSettings", {}).get("Networks", {})) <= {"none"} and
         h["AutoRemove"] is False and h["RestartPolicy"]["Name"] in ("", "no"),
         "Single owned lifecycle")
    need(h["Memory"] == h["MemorySwap"] == MEMORY and h["NanoCpus"] == NANO_CPUS and
         h["PidsLimit"] == PIDS and (h.get("Tmpfs") or {}) == TMPFS,
         "Exact actor resource and scratch limits")
    need(h["LogConfig"]["Type"] == "none" and not h["LogConfig"].get("Config"),
         "No daemon actor log store")
    need(len(h["Ulimits"]) == 4 and
         {x["Name"]: (x["Soft"], x["Hard"]) for x in h["Ulimits"]} ==
         {"cpu": (20, 22), "nofile": (64, 64), "core": (0, 0), "fsize": (1048576, 1048576)},
         "Exact actor ulimits")
    env = [x.split("=", 1) for x in c["Env"]]
    need(len(env) == len({x[0] for x in env}), "Unique actor environment")
    env = dict(env)
    need(all(env.get(k) == "1" for k in THREADS) and env.get("PYTHONDONTWRITEBYTECODE") == "1",
         "Actor thread limits")
    for rows, key in ((h.get("Mounts", []), "Target"),
                      ([x for x in info["Mounts"] if x["Type"] != "tmpfs"], "Destination")):
        need(len(rows) == 1 and rows[0][key] == "/actor/program.py" and
             rows[0]["Type"] == "bind" and
             source_matches(rows[0]["Source"], mounts["/actor/program.py"]["source"]),
             "Only this actor's exact source mount")
        need(rows[0].get("ReadOnly", False) is True if key == "Target" else
             rows[0]["RW"] is False, "Read-only actor source")
    effective = info["Mounts"]
    need(len({x["Destination"] for x in effective}) == len(effective) and
         all(x["Destination"] in TMPFS and x["RW"] is True
             for x in effective if x["Type"] == "tmpfs"), "No extra effective mount")
    return {"boundary": "exact_offline_actor", "profile": descriptor()}


def engine_class(BaseEngine, identity):
    """Reuse the admitted lifecycle/journal and captured-ID recovery unchanged."""
    class ActorEngine(BaseEngine):
        def __init__(self, end, out, budget):
            super().__init__(end, out, budget)
            self.profile = descriptor()

        def create(self, name, role, mounts):
            args = argv(name, role, mounts, self.profile)
            self.own("container", name, args)
            result = self.run(args)
            need(result.returncode == 0, "Actor creation")
            info = self.inspect("container", name)
            return info, verify(info, name, role, mounts, self.profile)

        def expected(self, name, mounts):
            kind, captured_name, args = identity.capture_request(
                ActorEngine, "create", (name, "offline_actor", mounts), profile=self.profile)
            need(kind == "container" and captured_name == name, "Exact actor constructor capture")
            # The module object is supplied without importing a second runtime ABI.
            import sys
            return {"kind": kind, "name": name, "argv": args,
                    "role": "offline_actor", "mounts": mounts, "profile": self.profile,
                    "module": sys.modules[__name__]}

        def recover(self, name, mounts):
            rows = [x for x in self.owned if x.get("kind") == "container" and x.get("name") == name]
            need(len(rows) == 1, "Exactly one owned actor identity")
            return identity.recover_one(self, self.out, rows[0], self.expected(name, mounts))
    return ActorEngine

