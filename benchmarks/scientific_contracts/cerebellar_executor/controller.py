"""Strict frozen cerebellar phase controller. No action occurs on import.

Production uses the captured Provider directly. `_run_graph` is also exercised
with an explicitly inert backend in engineering controls; it is not run authority.
"""
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys
import time
import uuid

from . import candidate_views, input_stages

ARMS = ("context_handle", "grc", "cf", "joint")
PHASES = ("select", "fit", "infer")
META_CAP = 1048576


def need(value, message):
    if not value:
        raise ValueError(message)


def closed(value, keys, message):
    need(type(value) is dict and set(value) == set(keys), message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def descriptor(value):
    closed(value, ("bytes", "sha256"), "exact body pin")
    need(type(value["bytes"]) is int and value["bytes"] >= 0, "exact nonnegative body extent")
    h = value["sha256"]
    need(type(h) is str and len(h) == 64 and all(x in "0123456789abcdef" for x in h), "SHA256")
    return value


def decode(body):
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, "duplicate JSON field")
            result[key] = value
        return result
    def real(token):
        value = float(token)
        need(math.isfinite(value), "finite JSON number")
        return value
    def constant(_):
        raise ValueError("nonfinite JSON constant")
    return json.loads(body.decode("utf-8"), object_pairs_hook=pairs, parse_float=real, parse_constant=constant)


class Meter:
    def __init__(self, limits):
        closed(limits, ("read_bytes", "write_bytes"), "explicit host IO limits")
        need(all(type(v) is int and v > 0 for v in limits.values()), "positive IO limits")
        self.limits, self.used = limits, {"read_bytes": 0, "write_bytes": 0}
    def charge(self, key, size):
        need(self.used[key] + size <= self.limits[key], "original host IO envelope")
        self.used[key] += size


def ordinary(path):
    p = Path(path)
    need(p.is_absolute() and not any(q.is_symlink() for q in (p, *p.parents)), "ordinary absolute path")
    return p


def read(path, expected, cap, meter=None):
    descriptor(expected); need(expected["bytes"] <= cap, "prospective read bound")
    p = ordinary(path)
    if meter:
        meter.charge("read_bytes", expected["bytes"] + 1)
    fd = os.open(p, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == expected["bytes"], "ordinary exact input")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            body = stream.read(expected["bytes"] + 1)
        after = os.fstat(fd)
        need((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_nlink) ==
             (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_nlink), "stable input")
    finally:
        os.close(fd)
    need(pin(body) == expected, "exact captured input")
    return body


def operand(value, cap, meter=None):
    closed(value, ("path", "bytes", "sha256"), "exact operand")
    return read(value["path"], {k: value[k] for k in ("bytes", "sha256")}, cap, meter)


def publish(path, body, meter):
    meter.charge("write_bytes", len(body)); p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with p.open("xb") as stream:
        stream.write(body); stream.flush(); os.fsync(stream.fileno())
    p.chmod(0o444)
    return {"path": str(p), **pin(body)}


def file_mount(value, purpose="input"):
    return {"path": value["path"], "kind": "file", "purpose": purpose,
            "files": {Path(value["path"]).name: {k: value[k] for k in ("bytes", "sha256")}}}


def preflight(request_path, request_pin, authority_path, authority_pin, source_pin):
    """Authority pins come from the trusted launcher, never candidate input.

    This verifies a supplied operator admission, not the truth of its scientific
    or platform judgment. No Provider or work directory is constructed here.
    """
    request = decode(read(request_path, request_pin, META_CAP))
    authority = decode(read(authority_path, authority_pin, META_CAP))
    closed(authority, ("schema", "request", "source", "authorized", "native_runtime_qualified",
                       "input_preparation_admitted", "capacity_qualified", "qualification_record", "commitment"), "operator authority fields")
    need(authority["schema"] == "neural030_frozen_authority_v1" and authority["request"] == request_pin
         and authority["source"] == source_pin, "externally selected authority/request/source binding")
    need(all(authority[k] is True for k in ("authorized", "native_runtime_qualified", "input_preparation_admitted", "capacity_qualified")),
         "unqualified host/input/grant; no Provider construction")
    descriptor(authority["qualification_record"])
    keys = ("schema", "mode", "mismatch", "root", "public", "procedure", "sources", "commitment", "private_evaluation",
            "clock", "io", "native", "phase_limits", "stdout_bytes", "stderr_bytes", "public_bytes_limit")
    closed(request, keys, "frozen request fields")
    need(request["schema"] == "neural030_frozen_execution_v1" and request["mode"] == "frozen_program"
         and request["mismatch"] is False, "adaptive and mismatch execution are disabled")
    closed(request["clock"], ("origin", "deadline"), "original campaign clock")
    need(all(type(v) in (int, float) and math.isfinite(v) for v in request["clock"].values())
         and 0 <= request["clock"]["origin"] < request["clock"]["deadline"], "finite original clock")
    for key in ("stdout_bytes", "stderr_bytes", "public_bytes_limit"):
        need(type(request[key]) is int and request[key] > 0, "explicit task bound: " + key)
    closed(request["phase_limits"], PHASES, "all three phase resource profiles")
    from .vendor_transport.contract import RESOURCE_KEYS
    for limits in request["phase_limits"].values():
        closed(limits, RESOURCE_KEYS, "complete resource profile")
        need(all(type(v) is int and v > 0 for v in limits.values()), "explicit positive phase bounds")
        need(limits["memory_bytes"] >= 134217728 and limits["scratch_bytes"] % 4096 == 0
             and limits["max_output_bytes"] % 4096 == 0, "existing transport page/minimum constraints")
        need(limits["manifest_bytes"] <= limits["max_file_bytes"] <= limits["max_output_bytes"]
             and limits["inventory_bytes"] >= 4096, "nested explicit capture limits")
        need(max(request["stdout_bytes"], request["stderr_bytes"]) <= limits["max_file_bytes"]
             and request["stdout_bytes"] + request["stderr_bytes"] < limits["max_output_bytes"],
             "stream limits fit each original phase envelope before Provider construction")
        need(limits["producer_seconds"] > 1, "existing Provider requires a producer interval greater than one second")
    native = request["native"]
    closed(native, ("docker_binary", "docker_socket", "image", "transport_source", "read_bytes", "write_bytes", "image_inventory_sha256"), "native dependency profile")
    need(native["transport_source"] == {"bytes": 987, "sha256": "93df92be5b388f4b2896805c8e02f0c41f301d1c86e6b06709444c1075ade0e4"}, "exact existing transport dependency")
    for key in ("read_bytes", "write_bytes"):
        need(type(native[key]) is int and native[key] > 0, "explicit native IO envelope")
    descriptor({"bytes": 0, "sha256": native["image_inventory_sha256"]})
    need(type(native["image"]) is str and native["image"].startswith("sha256:"), "immutable image identity")
    descriptor({"bytes": 0, "sha256": native["image"][7:]})
    ordinary(native["docker_binary"]); ordinary(native["docker_socket"])
    root = ordinary(request["root"]); need(not root.exists(), "fresh execution root")
    meter = Meter(request["io"])
    meter.charge("read_bytes", request_pin["bytes"] + authority_pin["bytes"] + 2)
    commitment_body = operand(request["commitment"], META_CAP, meter)
    need(pin(commitment_body) == authority["commitment"], "independent pre-data commitment pin")
    commitment = decode(commitment_body)
    closed(commitment, ("schema", "procedure", "sources", "sealed_before_input_access"), "pre-data source commitment")
    need(commitment["schema"] == "neural030_frozen_commitment_v1" and commitment["sealed_before_input_access"] is True,
         "operator pre-data source admission required")
    procedure_body = operand(request["procedure"], META_CAP, meter); procedure = decode(procedure_body)
    input_stages.validate_procedure(procedure)
    need(pin(procedure_body) == commitment["procedure"], "frozen procedure/grid")
    closed(request["sources"], PHASES, "same three source roles")
    sources = {role: operand(request["sources"][role], META_CAP, meter) for role in PHASES}
    need({role: pin(body) for role, body in sources.items()} == commitment["sources"], "same committed source bundle")
    need(sum(len(body) for body in sources.values()) + len(procedure_body) <= META_CAP, "whole frozen source/grid ceiling")
    for body in sources.values():
        ast.parse(body.decode("utf-8"))
    # The trusted operator can see queries; no candidate is running or receives
    # any query operand while this complete input plan is authenticated.
    public = decode(operand(request["public"], request["public_bytes_limit"], meter))
    panel = candidate_views.compile_panel(public)
    input_stages.validate_panel(panel, candidate_views=candidate_views)
    closed(request["private_evaluation"], ("expected", "mouse_binding", "fixed_reference"), "private evaluation operands")
    for value in request["private_evaluation"].values():
        closed(value, ("path", "bytes", "sha256"), "private operand descriptor")
        descriptor({k: value[k] for k in ("bytes", "sha256")}); ordinary(value["path"])
    minimum = 64 * sum(sum(limits[k] for k in ("setup_seconds", "producer_seconds", "capture_seconds", "cleanup_seconds"))
                       for limits in request["phase_limits"].values())
    now = time.monotonic()
    need(request["clock"]["origin"] <= now and now + minimum <= request["clock"]["deadline"],
         "whole192-phase minimum reserve inside original clock; no smaller fallback")
    return {"request": request, "authority": authority, "authority_pin": authority_pin, "source_pin": source_pin,
            "meter": meter, "panel": panel, "procedure": procedure, "procedure_body": procedure_body,
            "sources": sources, "root": root}


class NativeBackend:
    kind = "native_provider"
    def __init__(self, prepared, worker_source):
        from .vendor_transport.provider import Provider
        self.p, self.worker_source = prepared, worker_source
        r = prepared["request"]; self.root = prepared["root"]; self.meter = prepared["meter"]
        self.exposures = {}
        # Provider requires a nonempty trusted registry at construction. The
        # first exact source-derived phase is registered before constructing it.
        self.provider_class, self.provider = Provider, None
        self.native = r["native"]
        self.journal_count = {}

    def run(self, phase, job, mounts, identity):
        from .vendor_transport.bounds import mount_identity
        r = self.p["request"]; limits = r["phase_limits"][phase]
        now = time.monotonic(); deadline = r["clock"]["deadline"]
        need(now >= r["clock"]["origin"] and now + sum(limits[k] for k in ("setup_seconds", "producer_seconds", "capture_seconds", "cleanup_seconds")) <= deadline,
             "full phase remains inside original campaign deadline")
        job_operand = publish(self.root / "jobs" / identity / "JOB.json", encoded(job), self.meter)
        mounts = {**mounts, "/job.json": file_mount(job_operand, "contract"),
                  "/library/phase_worker.py": file_mount(self.worker_source, "program")}
        command = ["/usr/local/bin/python", "-I", "-B", "/library/phase_worker.py"]
        exposure = {"schema": "osl_transport_exposure_v1", "role": "A", "image": self.native["image"],
                    "source": self.p["source_pin"], "command": command, "mounts": mount_identity(mounts),
                    "approved_image_inventory_sha256": self.native["image_inventory_sha256"],
                    "boundary_audit": self.p["authority"]["qualification_record"], "role_boundary_verified": True}
        e = publish(self.root / "jobs" / identity / "EXPOSURE.json", encoded(exposure), self.meter)
        self.exposures[e["sha256"]] = e["path"]
        if self.provider is None:
            self.provider = self.provider_class(self.root / "control", self.root / "quarantine", self.native["docker_binary"],
                self.native["docker_socket"], self.native["transport_source"], self.exposures,
                self.native["read_bytes"], self.native["write_bytes"])
        self.provider.exposures[e["sha256"]] = e["path"]
        request = {"schema": "osl_owned_phase_request_v1", "phase_id": identity, "action": "held_attempt", "role": "A",
                   "image": self.native["image"], "command": command, "workdir": "/work", "source": self.p["source_pin"],
                   "exposure": {k: e[k] for k in ("bytes", "sha256")},
                   "clock": {"origin": r["clock"]["origin"], "phase_deadline": deadline}, "resources": limits,
                   "output": {"kind": "generic", "manifest": "OUTPUTS.json"}}
        def journal(name, value):
            index = self.journal_count.get(identity, 0)
            self.journal_count[identity] = index + 1
            publish(self.root / "journals" / identity / (str(index) + ".json"), encoded({"event": name, "value": value}), self.meter)
        result = self.provider.execute_phase(request, mounts, deadline, journal)
        observed = self.provider.observe(identity, pin(encoded(request))["sha256"], result["receipt_pin"], deadline)
        need(observed["receipt"] == result["receipt"], "independent exact phase observation")
        return {"receipt": observed["receipt"], "receipt_pin": result["receipt_pin"], "request_pin": pin(encoded(request)), "job": job}


def _captured(result, prepared, phase, identity, job):
    r = result["receipt"]
    need(r["status"] == "captured" and r["producer_closed_before_capture"] is True and r["all_native_resources_closed"] is True,
         "producer and all owned resources must close before phase admission")
    need(r["phase_id"] == identity and r["request_sha256"] == result["request_pin"]["sha256"], "phase/request identity")
    inventory = r["output_inventory"]
    need(inventory["complete"] is True, "complete output capture")
    files = inventory["files"]; root = ordinary(r["quarantine_root"])
    need(root == prepared["root"] / "quarantine" / identity, "owned phase capture root")
    base = {"OUTPUTS.json", "RESULT.json", "STDOUT.txt", "STDERR.txt"}
    required = base | ({"artifacts/SELECTION.json"} if phase == "select" else {"artifacts/PREDICTIONS.json"} if phase == "infer" else set())
    if phase == "fit":
        model_names = set(files) - base
        need(base <= set(files) and model_names and any(files[name]["bytes"] > 0 for name in model_names)
             and all(name.startswith("artifacts/model/") and len(name) > len("artifacts/model/") for name in model_names), "only complete nonempty model tree from fit")
    else:
        need(set(files) == required, "only phase-permitted artifacts")
    for name, expected in files.items():
        need(not Path(name).is_absolute() and ".." not in Path(name).parts, "ordinary relative captured member")
        read(root / name, expected, prepared["request"]["phase_limits"][phase]["max_file_bytes"], prepared["meter"])
    completion = decode(read(root / "RESULT.json", files["RESULT.json"], META_CAP, prepared["meter"]))
    expected_completion = {"schema": "neural030_trusted_phase_completion_v1", "phase_id": identity,
        "request_sha256": result["request_pin"]["sha256"], "phase": phase, "session_id": job["session_id"], "arm": job["arm"],
        "procedure_pin": job["procedure_pin"], "producer_completed": True, "scientific_qualification": False}
    need(completion == expected_completion, "trusted worker completion joins")
    return root, files


def _run_graph(prepared, backend, worker_source):
    """Actual source graph; backend is native in production, explicit inert in tests."""
    r, root, meter = prepared["request"], prepared["root"], prepared["meter"]
    need(backend.kind in ("native_provider", "inert_engineering"), "declared backend realm")
    root.mkdir(mode=0o700)
    for name in ("control", "quarantine", "stages", "jobs", "journals", "procedure"):
        (root / name).mkdir(mode=0o700)
    source_operands = {role: publish(root / "procedure" / (role + ".py"), body, meter) for role, body in prepared["sources"].items()}
    procedure = publish(root / "procedure" / "PROCEDURE.json", prepared["procedure_body"], meter)
    procedure_mount = {"path": str(root / "procedure"), "kind": "directory", "purpose": "program",
                       "files": {Path(a["path"]).name: {k: a[k] for k in ("bytes", "sha256")} for a in [*source_operands.values(), procedure]}}
    (root / "procedure").chmod(0o555)
    outputs = {arm: [] for arm in ARMS}; lineage = []; completed = 0
    from . import candidate_contract
    try:
        for view in prepared["panel"]["views"]:
            packets = input_stages.stage_packets(view, candidate_views=candidate_views)
            model = None; selected = None; selection_receipt = None; fit_receipt = None
            for phase, packet_key in (("select", "calibration"), ("fit", "training"), ("infer", "query")):
                identity = uuid.uuid4().hex
                packet = publish(root / "stages" / identity / "VIEW.json", encoded(packets[packet_key]), meter)
                mounts = {"/view/VIEW.json": file_mount(packet, "contract"), "/candidate/main.py": file_mount(source_operands[phase], "program"),
                          "/procedure": procedure_mount}
                if selected is not None:
                    recipe = publish(root / "stages" / identity / "RECIPE.json", encoded(selected), meter)
                    mounts["/recipe.json"] = file_mount(recipe, "contract")
                if phase == "infer":
                    need(model is not None and fit_receipt is not None, "captured fit required before query staging")
                    mounts["/model"] = model
                job = {"schema": "neural030_frozen_phase_job_v1", "phase": phase, "session_id": view["session_id"], "arm": view["arm"],
                       "procedure_pin": pin(prepared["procedure_body"]), "recipe_index": None if selected is None else selected["recipe_index"],
                       "stdout_bytes": r["stdout_bytes"], "stderr_bytes": r["stderr_bytes"]}
                result = backend.run(phase, job, mounts, identity)
                captured, files = _captured(result, prepared, phase, identity, job)
                completed += 1
                if phase == "select":
                    value = decode(read(captured / "artifacts/SELECTION.json", files["artifacts/SELECTION.json"], META_CAP, meter))
                    selected = input_stages.validate_selection(value, prepared["procedure"], view["session_id"], view["arm"])
                    selection_receipt = result["receipt_pin"]
                elif phase == "fit":
                    model_files = {name.removeprefix("artifacts/model/"): value for name, value in files.items() if name.startswith("artifacts/model/")}
                    model_root = captured / "artifacts/model"
                    for name in model_files:
                        (model_root / name).chmod(0o444)
                    for path in sorted(model_root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
                        if path.is_dir(): path.chmod(0o555)
                    model_root.chmod(0o555)
                    model = {"path": str(model_root), "kind": "directory", "purpose": "input", "files": model_files}
                    fit_receipt = result["receipt_pin"]
                else:
                    response = decode(read(captured / "artifacts/PREDICTIONS.json", files["artifacts/PREDICTIONS.json"], META_CAP, meter))
                    case = next(c for c in prepared["panel"]["plan"]["cases"] if c["session_id"] == view["session_id"])
                    candidate_contract.validate_response(response, case, view["arm"])
                    outputs[view["arm"]].append(response)
                    lineage.append({"session_id": view["session_id"], "arm": view["arm"], "source_bundle": {k: pin(v) for k, v in prepared["sources"].items()},
                        "procedure": job["procedure_pin"], "selection": selection_receipt, "recipe": selected,
                        "fit": fit_receipt, "model": pin(encoded(model["files"])), "inference": result["receipt_pin"], "query_view": {k: packet[k] for k in ("bytes", "sha256")}})
        need(completed == 192 and len(lineage) == 64 and all(len(outputs[arm]) == 16 for arm in ARMS), "full frozen support before private scoring")
        # Commit the entire candidate panel before opening any evaluator target.
        output_pin = publish(root / "CANDIDATE_OUTPUTS.json", encoded({"outputs": outputs, "lineage": lineage}), meter)
        private = {key: decode(operand(value, value["bytes"], meter)) for key, value in r["private_evaluation"].items()}
        score = candidate_contract.score_matched_panel(prepared["panel"]["plan"], private["expected"], outputs,
            fixed_reference_predictions=private["fixed_reference"], mouse_binding=private["mouse_binding"])
        result = {"schema": "neural030_frozen_collection_v1", "backend": backend.kind, "completed_phases": completed, "case_arm_cells": 64,
                  "candidate_outputs": output_pin, "evaluation": score, "mismatch_status": "disabled_state_equivalence_unqualified",
                  "adaptive_status": "disabled_separate_specification_required", "scientific_qualification": False,
                  "semantic_model_consumption_verified": False, "operator_qualification_authenticity_verified_by_code": False,
                  "host_io_reserved": meter.used.copy()}
        publish(root / "RESULT.json", encoded(result), meter)
        return result
    except BaseException as exc:
        try:
            publish(root / "FAILED.json", encoded({"schema": "neural030_frozen_failure_v1", "type": type(exc).__name__,
                "completed_phases": completed, "completed_predictions": len(lineage), "backend": backend.kind,
                "score_unavailable": True, "automatic_retry": False}), meter)
        except BaseException:
            pass
        raise


def run_frozen(request_path, request_pin, authority_path, authority_pin, source_pin, worker_source):
    prepared = preflight(request_path, request_pin, authority_path, authority_pin, source_pin)
    need(sys.platform.startswith("linux") and hasattr(os, "pidfd_open"), "native host remains unqualified on this platform")
    backend = NativeBackend(prepared, worker_source)
    return _run_graph(prepared, backend, worker_source)
