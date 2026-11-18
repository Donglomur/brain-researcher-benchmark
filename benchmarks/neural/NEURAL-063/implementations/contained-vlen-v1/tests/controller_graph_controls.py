"""Five bounded mocked controller-graph cases. No standalone executor.

The sole reviewed combined worker supplies already pinned modules. These cases
replace only trusted admission/IO/engine boundaries; real controller ordering,
dispatch, recovery identity checks and Inventory reservation/settlement run.
They neither qualify Docker/kernel behavior nor import scientific dependencies.
"""
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

NAMES = ("admission_before_start", "unknown_custody_stops_dispatch",
         "incomplete_session_held", "recovery_exact_identity",
         "settlement_evidence_refused")
SHA = "a" * 64
CID = "b" * 64
IMAGE = "sha256:" + "c" * 64
PAYLOAD = b"{}\n"
ARTIFACT = {"name": "plane_metadata.json", "bytes": len(PAYLOAD),
            "sha256": hashlib.sha256(PAYLOAD).hexdigest()}


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode()


def sha(value):
    return hashlib.sha256(encoded(value)).hexdigest()


class Memory:
    def __init__(self, root, shared):
        self.root, self.shared = Path(root), shared
        self.used = 0
        self.files, self.tokens = {}, {}
        self.events, self.calls = [], []
        self.fail_name = None

    def charge(self, body):
        count = len(body)
        require(self.used + count <= 1048576, "one MiB cumulative graph fake-byte cap")
        require(self.shared["used"] + count <= self.shared["limit"],
                "shared cumulative fake-byte budget")
        self.used += count
        self.shared["used"] += count

    def save(self, path, body):
        path = str(path)
        require(path not in self.files, "exclusive fake publication")
        self.charge(body)
        self.files[path] = body
        self.events.append(("write", Path(path).name))
        return {"path": path, "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest()}

    def fixture(self, path, value):
        return self.save(path, encoded(value))

    def publish(self, path, value, cap, counters):
        body = encoded(value)
        ceiling = counters["cap"] - (0 if counters.get("cleanup_mode")
                    else counters.get("protected", 0))
        require(len(body) <= cap and counters["requested"] + len(body) <= ceiling,
                "fake publication remains within real pre-reserved counters")
        counters["requested"] += len(body)
        if Path(path).name == self.fail_name:
            counters["uncertain"] = True
            raise OSError("invented admission publication failure")
        ref = self.save(path, body)
        counters["confirmed"] += len(body)
        return ref

    def inventory_write(self, path, body):
        ref = self.save(path, body)
        return {"name": Path(path).name, "bytes": ref["bytes"], "sha256": ref["sha256"]}

    def pinned(self, ref, cap, *, retain=True, charge=None):
        require(ref["bytes"] <= cap, "bounded mocked pin")
        if charge:
            charge(ref["bytes"] + 1)
        if not retain:
            return None
        require(ref["path"] in self.files, "named fake metadata input only")
        return self.files[ref["path"]]

    def stat(self, path, *args, **kwargs):
        return SimpleNamespace(st_size=len(self.files.get(str(path), b"")),
            st_mode=0o100444, st_nlink=1, st_dev=1, st_ino=1,
            st_mtime_ns=0, st_ctime_ns=0)

    def patches(self, controller, inventory):
        stack = ExitStack()
        stack.enter_context(patch.object(controller, "publish", self.publish))
        stack.enter_context(patch.object(controller, "ordinary",
                                         lambda path, directory=False: Path(path)))
        stack.enter_context(patch.object(controller, "pinned", self.pinned))
        stack.enter_context(patch.object(inventory, "exclusive_bytes", self.inventory_write))
        stack.enter_context(patch.object(Path, "mkdir", lambda *a, **k: None))
        stack.enter_context(patch.object(Path, "exists", lambda *a, **k: False))
        stack.enter_context(patch.object(Path, "stat", lambda p, *a, **k: self.stat(p)))
        stack.enter_context(patch.object(Path, "lstat", lambda p, *a, **k: self.stat(p)))
        stack.enter_context(patch.object(controller.time, "monotonic", lambda: 100.0))
        stack.enter_context(patch.object(controller.time, "sleep", lambda n: None))
        return stack


def profile_for_graph(adapter, profile_factory):
    value = deepcopy(profile_factory(adapter))
    for kind in ("plane", "session"):
        cap = value["unit_caps"][kind]
        cap["control_bytes"] = 16777216
        cap["host_write_bytes"] = value["output_caps"][kind] + cap["control_bytes"]
        cap["worker_artifact_write_bytes"] = value["output_caps"][kind] + 32
        cap["source_setup_read_bytes"] = 67108864 + 257 + 8193 * 2
    for key in value["global_caps"]:
        value["global_caps"][key] = max(value["global_caps"][key],
            sum(value["unit_caps"][k][key] for k in ("plane", "session")) * 10000 + 9377792)
    return value


def admitted_inventory(module, rows, raw, profile, root):
    """Explicit post-admission state double; constructor is covered elsewhere."""
    obj = object.__new__(module.Inventory)
    obj.root, obj.profile, obj.owner = Path(root), deepcopy(profile), SHA
    obj.planes, obj.sessions, obj.members = {}, {}, {}
    for row in rows:
        eid, sid = row["experiment"], row["session"]
        obj.planes[eid] = {"session": sid, "mouse": row["mouse"], "split": row["split"],
            "state": "unattempted", "reason": "not_attempted", "artifact": None}
        obj.sessions[sid] = {"state": "held", "reason": "awaiting_complete_session",
                            "artifact": None}
        obj.members.setdefault(sid, []).append(eid)
    require(len(obj.planes) == 1936 and len(obj.sessions) == 703,
            "complete generated post-admission inventory")
    obj.spent = {k: 0 for k in module.COUNTERS}
    obj.initial_reserved_cumulative = dict(obj.spent)
    obj.settlements, obj.reservations, obj.reservation_refs = {}, {}, {}
    obj.unit_control_written, obj.export_claims = {}, {}
    obj.control_written = 0
    obj.active, obj.stopped, obj.finalized = None, False, False
    obj.publication_failures = []
    obj.terminal = profile["terminal_inventory_bytes"]
    obj.initial_ref = {"name": "INITIAL.json", "bytes": 1, "sha256": SHA}
    obj.assets_canonical_sha256 = sha(json.loads(raw))
    return obj


def operation(controller, memory, profile, inv, label):
    root = inv.root
    def ref(path, count=1, digest=SHA):
        return {"path": str(path), "bytes": count, "sha256": digest}
    sources = {key: ref(root / "sources" / key) for key in
               ("worker.py", "scientific_adapter.py", "controller.py", "n063_fixed_export.py")}
    sources.update({"original/" + k: ref(root / "sources/original" / k, *v)
                    for k, v in controller.ORIGINAL.items()})
    sources.update({"range/" + k: ref(root / "sources/range" / k, *v)
                    for k, v in controller.RANGE.items()})
    runtime = {k: {**ref("/fake-runtime/" + k), "resolved_path": "/fake-runtime/" + k}
               for k in ("docker", "host_python", "timer")}
    runtime["python_in_image"] = "/usr/local/bin/python3"
    runtime["launcher"] = {"kind": "direct_python"}
    dep = {"image_id": IMAGE, "endpoint": "unix:///invented/docker.sock", "image_env": [], "plane_network": {"name": "n063-invented", "id": "d" * 64}}
    dep.update({k: ref(root / (k + ".json"), 1, profile["deployment"][k + "_sha256"])
        for k in ("runtime_receipt", "mount_receipt", "network_receipt",
                  "containment_receipt", "exporter_receipt", "delegation_receipt")})
    profile["deployment"]["image_id"] = IMAGE
    profile["deployment"]["endpoint"] = dep["endpoint"]
    inv.profile = deepcopy(profile)
    op = {"schema": "neural063-portable-contained-controller-v1", "selected": True,
        "runtime_qualified": True, "native": {"id": root.name,
            "approval_id": "invented-approval", "owner": "root",
            "protocol": ref(root / "native-protocol.json"), "cwd": str(root),
            "ledger": "/invented-ledger", "ram_bytes": 2147483648},
        "runtime": runtime, "deployment": dep, "sources": sources,
        "authority_policy_sha256": SHA,
        "helpers": {k: ref(root / "helpers" / k, *v) for k, v in controller.HELPER_PINS.items()},
        "host_inventory": ref(root / "inventory-source.py"),
        "profile": ref(root / "profile-input.json"),
        "inputs": {"selection": ref(root / "selection.json", *controller.SELECTION),
                   "assets": ref(root / "assets.json", *controller.ASSETS)},
        "layout_bank": ref(root / "layout-bank.json"),
        "output_root": str(root),
        "limits": {"whole_seconds": 1800, "cleanup_seconds": 30,
                   "ready_attempts": 2, "ready_interval_seconds": 1},
        "startup_envelope": {k: 0 for k in inv.spent}}
    op["startup_envelope"].update(control_bytes=1048576, host_write_bytes=1048576,
                                  source_setup_read_bytes=134217728, closure_seconds=30)
    return op


def authority_fixture(controller, op):
    """Invented declarations only; no live/native authority is manufactured."""
    root = Path(op["output_root"]).parent
    def ref(name, pin=(1, SHA)):
        return {"path": str(root / name), "bytes": pin[0], "sha256": pin[1]}
    return {"schema": "neural063-native-authority-v1", "selected": True,
        "operator_uid": 0, "workspace": op["native"]["cwd"],
        "output_parent": str(root), "ledger": op["native"]["ledger"],
        "controller": deepcopy(op["sources"]["controller.py"]),
        "native_controller": ref("invented-native-controller.py", controller.NATIVE_CONTROLLER_PIN),
        "capture": ref("invented-capture.py", controller.CAPTURE_PIN),
        "qualification": ref("invented-authority-qualification.json"),
        "supervisor_python": deepcopy(op["runtime"]["host_python"]),
        "ps": {"path": "/invented/ps", "resolved_path": "/invented/ps", "bytes": 1, "sha256": SHA},
        "helpers": deepcopy(op["helpers"]), "runtime": deepcopy(op["runtime"]),
        "endpoint": op["deployment"]["endpoint"]}


def writer_usage(requested):
    return {"bytes_requested": requested, "bytes_confirmed": len(PAYLOAD),
        "write_calls": 2, "exclusive_append_only": True, "same_fd_path": True,
        "fsync": True, "complete": True, "sha256": ARTIFACT["sha256"]}


def range_usage():
    return {"failed": False, "request_unresolved": False, "requests_admitted": 0,
        "records_count": 0, "range_receipt_bytes_reserved": 0,
        "complete_response_body_bytes_observed": 0,
        "response_body_bytes_reserved_including_failures": 0,
        "range_records_sha256": SHA, "logical_bytes_requested": 0}


class Engine:
    def __init__(self, controller, memory, op, inv, *, unknown_start=False):
        self.c, self.mem, self.op, self.inv = controller, memory, op, inv
        self.unknown_start = unknown_start
        self.state, self.config, self.start_count = "absent", None, 0
        self.quiescent = True
        self.unit_calls = []

    def bank(self):
        return SimpleNamespace(Docker=lambda journal, stop: self,
                               stop_cli_leader=lambda p: (_ for _ in ()).throw(
                                   AssertionError("no real Popen handle permitted")))

    @staticmethod
    def legacy():
        return SimpleNamespace(absent=lambda row, target:
            row.get("missing") == target and row["returncode"] == 1)

    @staticmethod
    def formats():
        return {"container_full": "FULL", "container_ownership": "OWN",
                "container_absence": "ABSENT", "image_full": "IMAGE"}

    def row(self, value="", code=0, missing=None):
        return {"stdout": value if isinstance(value, str) else encoded(value).decode(),
            "stderr": "", "returncode": code, "cleanup": {"leader_reaped": True},
            "error_type": None, "diagnostic_publication_errors": [], "missing": missing}

    def call(self, argv, end, cap=8192, cleanup=False):
        require(len(self.mem.calls) < 64, "finite 64-call fake engine envelope")
        require(end > 100, "real controller supplies a live bounded deadline")
        self.mem.calls.append(tuple(argv[:3]))
        self.unit_calls.append(tuple(argv[:3]))
        verb = argv[0]
        if argv[:2] == ["image", "inspect"]:
            return self.row({"Id": IMAGE, "Os": "linux", "Architecture": "arm64", "Env": []})
        if argv[:2] == ["network", "inspect"]:
            return self.row(encoded(self.op["deployment"]["plane_network"]["id"]).decode())
        if verb == "create":
            require(self.inv.active is not None, "real reservation precedes create")
            values = {}
            for index, word in enumerate(argv[:-1]):
                if word.startswith("--"):
                    values.setdefault(word, []).append(argv[index + 1])
            single = lambda key: values[key][0]
            self.config = {
                "id": CID, "name": "/" + single("--name"), "image": IMAGE,
                "labels": dict(v.split("=", 1) for v in values["--label"]),
                "entry": [single("--entrypoint")], "cmd": argv[argv.index(IMAGE) + 1:],
                "env": values["--env"], "user": single("--user"), "workdir": single("--workdir"),
                "volumes": None, "tty": False, "stdin": False,
                "network": single("--network"), "readonly": "--read-only" in argv,
                "privileged": False, "capdrop": values["--cap-drop"],
                "capadd": None, "security": values["--security-opt"],
                "devices": None, "requests": None, "rules": None, "ports": None,
                "pidmode": "", "ipcmode": single("--ipc"), "restart": {"Name": "no"},
                "memory": int(single("--memory")), "swap": int(single("--memory-swap")),
                "cpus": int(single("--cpus")) * 1000000000,
                "pids": int(single("--pids-limit")), "shm": int(single("--shm-size")),
                "tmpfs": dict(v.split(":", 1) for v in values["--tmpfs"]),
                "log": {"Type": single("--log-driver"), "Config": {}},
                "ulimits": [], "declaredmounts": [], "mounts": []}
            for v in values["--ulimit"]:
                key, pair = v.split("=")
                soft, hard = map(int, pair.split(":"))
                self.config["ulimits"].append({"Name": key, "Soft": soft, "Hard": hard})
            for v in values["--mount"]:
                fields = dict(x.split("=", 1) if "=" in x else (x, True) for x in v.split(","))
                self.config["declaredmounts"].append({"Type": fields["type"],
                    "Source": fields["src"], "Target": fields["dst"], "ReadOnly": fields["readonly"]})
                self.config["mounts"].append({"Type": fields["type"], "Source": fields["src"],
                    "Destination": fields["dst"], "RW": False, "Propagation": "rprivate"})
            for target in self.config["tmpfs"]:
                self.config["mounts"].append({"Type": "tmpfs", "Destination": target, "RW": True})
            self.state = "created"
            return self.row(CID + "\n")
        if verb == "inspect":
            target = argv[3]
            if self.state == "absent":
                return self.row(code=1, missing=target)
            if argv[-1] == "ABSENT":
                return self.row(encoded(CID).decode())
            value = deepcopy(self.config)
            if argv[-1] == "OWN":
                value = {k: value[k] for k in ("id", "name", "image", "labels")}
            else:
                value["state"] = {"Status": self.state, "OOMKilled": False, "Error": "",
                    "Running": self.state == "running", "Pid": 1 if self.state == "running" else 0,
                    "ExitCode": 0}
            return self.row(value)
        if verb == "start":
            self.start_count += 1
            eid = self.inv.active[1]
            path = self.inv.root / ("control-plane-" + eid) / "inputs/admission.json"
            require(str(path) in self.mem.files, "admission publication before start")
            admission = json.loads(self.mem.files[str(path)])
            require(admission["container_id"] == CID and admission["reservation_sha256"] ==
                    self.inv.reservation_refs["plane-" + eid]["sha256"],
                    "start admission binds actual reservation and created identity")
            self.state = "running"
            if self.unknown_start:
                # Deliberately leave bank.quiescent true, matching the old dangerous gap.
                raise RuntimeError("invented unknown CLI custody after daemon side effect")
            return self.row()
        if verb == "exec":
            eid = self.inv.active[1]
            return self.row({"schema": "neural063-contained-ready-v1", "kind": "plane",
                "identity": eid, "container_id": CID,
                "reservation_sha256": self.inv.reservation_refs["plane-" + eid]["sha256"],
                "producer_returned_successfully": True, "source_setup_read_bytes": 1,
                "result": {"output": ARTIFACT, "source_usage": {"worker_output": writer_usage(7),
                    "range": range_usage(), "session_input_bytes_read_including_EOF_probes": 0}}})
        if verb == "stop":
            self.state = "exited"
            return self.row()
        if argv[:2] == ["rm", "--force"]:
            self.state = "absent"
            return self.row()
        raise AssertionError("unexpected fake command")

    def exporter(self):
        def copyout(lease, expected, **kwargs):
            require(self.state == "running" and expected == ARTIFACT,
                    "export follows live admitted producer")
            return {"verified": True, "identity": lease["identity"], "artifact": dict(expected),
                "container_id": CID, "reservation_sha256": lease["reservation_sha256"],
                "cli_cleanup": {"leader_reaped": True}, "streams_eof": True, "cleanup_errors": [],
                "confirmed_written_bytes": len(PAYLOAD), "requested_write_bytes": 5,
                "read_bytes": len(PAYLOAD), "write_usage": writer_usage(5)}
        return SimpleNamespace(copyout=copyout)


def run_cases(controller, inventory_module, adapter, exporter, *, profile_factory,
              assets_factory, evidence_root, artifact_guard, memory_budget):
    """Exactly five case functions; caught failures are retained, never retried."""
    memory = Memory(evidence_root, memory_budget)
    raw, identity = assets_factory(inventory_module)
    require(len(raw) == identity["bytes"] and hashlib.sha256(raw).hexdigest() == identity["sha256"],
            "complete generated ASSETS fixture")
    memory.charge(raw)
    rows = json.loads(raw)["assets"]
    base_profile = profile_for_graph(adapter, profile_factory)
    original_strict = controller.strict

    def make(label):
        inv = admitted_inventory(inventory_module, rows, raw, base_profile,
                                 memory.root / label)
        p = deepcopy(base_profile)
        op = operation(controller, memory, p, inv, label)
        return inv, p, op

    def run_plane(label, *, fail_admission=False, unknown_start=False):
        inv, p, op = make(label)
        eid = sorted(inv.planes)[0]
        engine = Engine(controller, memory, op, inv, unknown_start=unknown_start)
        layouts = {eid: {"path": str(inv.root / "layout.json"), "bytes": 1, "sha256": SHA}}
        memory.fail_name = "admission.json" if fail_admission else None
        try:
            with memory.patches(controller, inventory_module):
                outcome = controller.run_unit(op, inventory=inv, profile=p, adapter=adapter,
                    exporter=engine.exporter(), bank=engine.bank(), legacy=engine.legacy(),
                    formats=engine.formats(), kind="plane", identity=eid, layouts=layouts,
                    host_deadline=1000.0, operation_sha=SHA)
        finally:
            memory.fail_name = None
        return inv, engine, outcome

    def admission():
        inv, engine, outcome = run_plane("admitted")
        require(outcome["success"] is True and engine.start_count == 1 and inv.settlements,
                "full real controller path reaches witnessed settlement")
        refused, failed_engine, failure = run_plane("admission-failed", fail_admission=True)
        require(failure["success"] is False and failed_engine.start_count == 0
                and not refused.settlements, "publication refusal prevents start and settlement")
        return {"positive_complete": True, "failed_admission_start_calls": 0,
                "subcases": 2}

    def install_host_inputs(inv, p, op, engine):
        # These trusted bootstrap doubles isolate the actual host dispatch loop.
        modules = {"_n063_controller_adapter": adapter,
            "_n063_controller_export": engine.exporter(), "_n063_verified_bank": engine.bank(),
            "_n063_verified_absence": engine.legacy()}
        inv.finalize = lambda **kwargs: (setattr(inv, "finalized", True) or
            {"name": "MOCK_FINAL.json", "bytes": 1, "sha256": SHA})
        modules["_n063_controller_inventory"] = SimpleNamespace(
            reserve_startup=lambda *a: {"receipt": {"bytes": 1}},
            Inventory=lambda *a, **kw: inv)
        op["profile"] = memory.fixture(inv.root / "profile-input.json", p)
        memory.save(op["inputs"]["assets"]["path"], b"MOCK_POST_ADMISSION_ASSETS")
        for ref in list(op["sources"].values()) + [op["host_inventory"]]:
            if ref["path"] not in memory.files:
                memory.save(ref["path"], b"# mocked trusted source\n")
        for key, ref in op["helpers"].items():
            if ref["path"] not in memory.files:
                memory.save(ref["path"], encoded(engine.formats()) if key == "formats" else b"# mocked helper\n")
        bank = {"schema": "neural063_range_layout_bank_v1",
            "selection_sha256": controller.SELECTION[1], "assets_sha256": inv.assets_canonical_sha256,
            "source_counts": {"experiments": 1936, "mice": 107, "sessions": 703, "rois": 133066},
            "array_values_decoded": False, "full_object_BLAKE2b_verified": False,
            "entries": [{"experiment": eid, "layout": {"path": str(inv.root / ("l-" + eid)),
                "bytes": 1, "sha256": SHA, "role": "range_layout", "visibility": "operator"}}
                for eid in inv.planes]}
        token = b"MOCK_POST_ADMISSION_LAYOUT_BANK"
        memory.save(op["layout_bank"]["path"], token)
        memory.tokens[token] = bank
        for key, ref in op["deployment"].items():
            if not key.endswith("_receipt"):
                continue
            value = {"qualified": True, "image_id": IMAGE,
                     "qualification_kind": key.removesuffix("_receipt"),
                     "endpoint": op["deployment"]["endpoint"],
                     "python_in_image": op["runtime"]["python_in_image"],
                     "docker": deepcopy(op["runtime"]["docker"]),
                     "host_python": deepcopy(op["runtime"]["host_python"])}
            if key == "network_receipt":
                value.update(network=op["deployment"]["plane_network"],
                             range_guards_unchanged=True, session_network="none")
            if key == "mount_receipt":
                value.update(source_identities={k: {x: v[x] for x in ("bytes", "sha256")}
                        for k, v in op["sources"].items()},
                    input_identities={k: {x: v[x] for x in ("bytes", "sha256")}
                        for k, v in op["inputs"].items()}, readonly_nonroot_access_verified=True)
            if key == "delegation_receipt":
                value.update(native_id=op["native"]["id"], outer_group_absence_mandatory=True,
                    outer_container_recovery_mandatory=True, controller_hard_kill_covered=True,
                    recovery_receipt_required_after_every_outcome=True, recovery_output_root=str(inv.root),
                    external_cleanup_reserved=True, external_cleanup_envelope_sha256=SHA,
                    recovery_deadline_seconds=180, recovery_entry="recover",
                    recovery_operator=op["sources"]["controller.py"],
                    recovery_protocol={"path": str(inv.root / "recipe.json"), "bytes": 1, "sha256": SHA})
            memory.fixture(ref["path"], value)
        path = inv.root / "operation.json"
        ref = memory.fixture(path, op)
        return path, ref, modules

    def unknown():
        inv, p, op = make("unknown-dispatch")
        engine = Engine(controller, memory, op, inv, unknown_start=True)
        path, ref, modules = install_host_inputs(inv, p, op, engine)
        with memory.patches(controller, inventory_module), \
             patch.object(controller, "validate_operation", lambda *a, **k: {"launchable": True}), \
             patch.object(controller, "authority_policy", lambda *a, **k: authority_fixture(controller, op)), \
             patch.object(controller, "native_gate", lambda *a, **k: {"owned_pgid": 1}), \
             patch.object(controller, "authenticate_runtime", lambda *a, **k: None), \
             patch.object(controller, "loaded", lambda name, body, source: modules[name]), \
             patch.object(controller, "strict", lambda body: memory.tokens[body]
                          if isinstance(body, bytes) and body in memory.tokens else original_strict(body)):
            code = controller.host_main(path, ref["sha256"],
                authority_path=inv.root / "authority.json", authority_sha=SHA)
        created = sum(row[0] == "create" for row in engine.unit_calls)
        first = sorted(inv.planes)[0]
        receipt = json.loads(memory.files[str(inv.root / ("plane-" + first + "-result.json"))])
        require(code == 1 and created == 1 and inv.stopped is True
                and engine.state == "absent" and engine.quiescent is True,
                "real dispatch loop stops despite observed absence and bank flag")
        require(receipt["closure"]["observations"]["cli_custody_unknown"] is True
                and receipt["closure"]["observations"]["safe_for_further_dispatch"] is False
                and sum(r["state"] == "unattempted" for r in inv.planes.values()) == 1935,
                "unknown custody retains explicit failed/held full inventory")
        return {"create_calls": created, "later_planes_unattempted": 1935,
                "observed_absence_did_not_resume": True}

    def incomplete():
        inv, p, op = make("incomplete-session")
        sid = sorted(inv.sessions)[0]
        members = inv.members[sid]
        require(len(members) >= 2, "generated multi-plane session")
        inv.planes[members[0]].update(state="complete", artifact=dict(ARTIFACT))
        before = deepcopy(inv.spent)
        member_ids = tuple(members)
        member_states = deepcopy({eid: inv.planes[eid] for eid in members})
        engine = Engine(controller, memory, op, inv)
        with memory.patches(controller, inventory_module):
            try:
                controller.run_unit(op, inventory=inv, profile=p, adapter=adapter,
                    exporter=engine.exporter(), bank=engine.bank(), legacy=engine.legacy(),
                    formats=engine.formats(), kind="session", identity=sid, layouts={},
                    host_deadline=1000.0, operation_sha=SHA)
            except ValueError as exc:
                require(str(exc) == "session held until every original plane is complete",
                        "specific missing-member admission refusal")
            else:
                raise AssertionError("incomplete session admitted")
            require(inv.active is None and inv.spent == before and not inv.reservations
                    and not engine.unit_calls,
                    "incomplete session refused before engine/publication/reservation")
            require(tuple(inv.members[sid]) == member_ids and
                    {eid: inv.planes[eid] for eid in member_ids} == member_states,
                    "refusal preserves every original member state and artifact")
            inv.finalize()
        final = json.loads(memory.files[str(inv.root / "FINAL.json")])
        require(final["metadata_support_complete"] is False
                and final["sessions"][sid]["state"] == "held"
                and final["sessions"][sid]["reason"] == "awaiting_complete_session",
                "incomplete session cannot become complete or scientific exclusion")
        require(all(final["planes"][eid] == member_states[eid] for eid in member_ids),
                "terminal report preserves every target plane")
        return {"full_member_count": len(members), "session_worker_calls": 0,
                "reservation_created": False, "terminal_complete": False}

    def recovery_once(label, wrong_owner):
        inv, p, op = make(label)
        eid = sorted(inv.planes)[0]
        reservation = {"owner": SHA, "kind": "plane", "identity": eid,
                       "envelope": p["unit_caps"]["plane"], "no_refund": True}
        rr = memory.fixture(inv.root / ("plane-" + eid + "-reservation.json"), reservation)
        name = "n063-" + SHA[:16] + "-plane-" + eid
        control = inv.root / ("control-plane-" + eid)
        intent = {"owner": SHA, "name": name, "kind": "plane", "identity": eid,
                  "reservation_sha256": rr["sha256"]}
        ir = memory.fixture(control / "CREATE_INTENT.json", intent)
        startup = memory.fixture(inv.root / "STARTUP.json", {"schema": "neural063-startup-reservation-v1",
            "owner": SHA, "envelope": op["startup_envelope"], "no_refund": True})
        created = memory.fixture(control / "CREATED.json", {"id": CID})
        oldgroup = memory.fixture(inv.root / "old-group.json", {
            "schema": "neural063-native-group-closure-v1", "operation_sha256": SHA,
            "native_id": op["native"]["id"], "identity_verified": True, "group_absent": True,
             "authority_policy_sha256": SHA})
        opref = memory.fixture(inv.root / "old-operation.json", op)
        # Owner digest is mocked at trusted original-operation pin admission.
        opref["sha256"] = SHA
        recovery = {"schema": "neural063-portable-contained-recovery-v1", "selected": True,
            "authority_policy_sha256": SHA,
            "runtime_qualified": True, "original_operation": opref,
            "native": {**op["native"], "id": "invented-recovery-" + label},
            "kind": "plane", "identity": eid, "startup": startup, "reservation": rr,
            "create_intent": ir, "created": created, "prior_group_closure": oldgroup,
            "output_root": str(inv.root / ("recovery-invented-recovery-" + label)),
            "envelope": {k: 0 for k in inv.spent}}
        recovery["envelope"].update(control_bytes=1048576, host_write_bytes=1048576,
                                    source_setup_read_bytes=134217728, closure_seconds=30)
        record = memory.fixture(inv.root / "recovery-plan.json", recovery)
        engine = Engine(controller, memory, op, inv)
        engine.state = "running"
        engine.config = {"id": CID, "name": "/" + name, "image": IMAGE,
            "labels": {"n063.owner": "e" * 64 if wrong_owner else SHA,
                       "n063.kind": "plane", "n063.identity": eid,
                       "n063.reservation": rr["sha256"]}}
        modules = {"_n063_recovery_bank": engine.bank(), "_n063_recovery_absence": engine.legacy()}
        for key, ref in op["helpers"].items():
            if ref["path"] not in memory.files:
                memory.save(ref["path"], encoded(engine.formats()) if key == "formats" else b"# helper\n")
        with memory.patches(controller, inventory_module), \
             patch.object(controller, "validate_operation", lambda *a, **k: {"launchable": True}), \
             patch.object(controller, "authority_policy", lambda *a, **k: authority_fixture(controller, op)), \
             patch.object(controller, "native_gate", lambda *a, **k: {"owned_pgid": 2}), \
             patch.object(controller, "authenticate_runtime", lambda *a, **k: None), \
             patch.object(controller, "loaded", lambda name, body, source: modules[name]):
            code = controller.recover_main(record["path"], record["sha256"],
                authority_path=inv.root / "authority.json", authority_sha=SHA)
        result = json.loads(memory.files[str(Path(recovery["output_root"]) / "RECOVERY_RESULT.json")])
        removes = sum(row[:2] == ("rm", "--force") for row in engine.unit_calls)
        return code, result, removes

    def recovery():
        code, good, removes = recovery_once("recover-owned", False)
        require(code == 0 and good["container_recovery_complete"] is True and removes == 1,
                "real recovery consumes matching intent and owns removal")
        code, bad, removes = recovery_once("recover-foreign", True)
        require(code == 1 and bad["container_recovery_complete"] is False and removes == 0,
                "foreign ownership refused before any removal")
        return {"matching_identity_removed": True, "foreign_removals": 0,
                "outer_group_closure_still_required": True, "subcases": 2}

    def settlement():
        def attempt(label, mutation):
            inv, p, op = make(label)
            eid = sorted(inv.planes)[0]
            with memory.patches(controller, inventory_module):
                reservation = inv.reserve("plane", eid)
                lease = inv.claim_export("plane", eid, expected=ARTIFACT, container_id=CID,
                    producer_receipt_sha256=SHA, ownership_receipt_sha256="f" * 64,
                    host_deadline_monotonic=1000)
                copied = {"verified": True, "identity": eid, "artifact": dict(ARTIFACT),
                    "container_id": CID, "reservation_sha256": reservation["reservation_sha256"],
                    "write_usage": writer_usage(5), "read_bytes": len(PAYLOAD),
                    "confirmed_written_bytes": len(PAYLOAD)}
                closed = {"kind": "plane", "identity": eid, "reservation_sha256": lease["reservation_sha256"],
                    "container_id": CID, "producer_receipt_sha256": SHA,
                    "ownership_receipt_sha256": "f" * 64, "export_receipt_sha256": sha(copied),
                    "artifact": dict(ARTIFACT), "proofs": {k: True for k in
                    ("producer_complete", "producer_zero_exit", "oom_absent", "timeout_absent",
                     "copyout_verified", "streams_eof", "cli_reaped", "ownership_verified",
                     "container_absence_verified")}}
                evidence = {"schema": "neural063_unit_success_settlement_v1", "kind": "plane",
                    "identity": eid, "reservation_sha256": lease["reservation_sha256"],
                    "container_id": CID, "output": dict(ARTIFACT), "worker_output": writer_usage(7),
                    "range": range_usage(), "session_input_bytes_read_including_EOF_probes": 0,
                    "source_setup_read_bytes": 1, "copyout": copied,
                    "controller_requested_write_bytes": 10, "controller_control_bytes": 10,
                    "unmeasured_residuals_stay_reserved": True,
                    "receipt_hashes": {"ready": SHA, "configuration": SHA, "exit": SHA,
                                       "absence": SHA, "copyout": sha(copied)}}
                before = deepcopy(inv.spent)
                if mutation:
                    mutation(evidence, closed)
                    try:
                        inv.finish_unit("plane", eid, artifact=ARTIFACT, closure=closed,
                                        copyout_result=copied, settlement_receipt=evidence)
                    except ValueError:
                        pass
                    else:
                        raise AssertionError("contradictory settlement accepted")
                    require(not inv.settlements and inv.spent == before
                            and inv.planes[eid]["state"] == "dispatched",
                            "refusal cannot refund or mark unit complete")
                else:
                    inv.finish_unit("plane", eid, artifact=ARTIFACT, closure=closed,
                                    copyout_result=copied, settlement_receipt=evidence)
                    require(inv.spent["worker_artifact_write_bytes"] == 7
                            and inv.spent["host_write_bytes"] == 5 + p["unit_caps"]["plane"]["control_bytes"],
                            "requested totals, not retained artifact size, settle")
        attempt("settle-positive", None)
        attempt("settle-missing", lambda e, c: e["worker_output"].pop("bytes_requested"))
        attempt("settle-contradictory", lambda e, c: e["worker_output"].update(bytes_requested=1))
        attempt("settle-unclosed", lambda e, c: c["proofs"].update(container_absence_verified=False))
        return {"valid_requested_totals_retained": True, "refusals": 3, "subcases": 4}

    cases = []
    for name, callback in zip(NAMES, (admission, unknown, incomplete, recovery, settlement)):
        try:
            details = callback()
            cases.append({"name": name, "passed": True, **details})
        except Exception as exc:
            cases.append({"name": name, "passed": False,
                          "error": type(exc).__name__ + ": " + str(exc)[:320]})
    return {"passed": sum(r["passed"] for r in cases),
            "failed": sum(not r["passed"] for r in cases), "cases": cases,
            "actual_processes": 0, "signals": 0, "provider_requests": 0,
            "actual_container_lifecycle": False, "actual_recovery": False,
            "scope": "mocked real controller/Inventory graph; trusted admission, IO and engine doubled",
            "mocked_transport_calls": len(memory.calls), "cumulative_fake_bytes": memory.used,
            "saved_artifact_bytes": 0, "controller_graph_executed": False,
            "recovery_graph_executed": False, "mocked_graph_cases_attempted": 5}
