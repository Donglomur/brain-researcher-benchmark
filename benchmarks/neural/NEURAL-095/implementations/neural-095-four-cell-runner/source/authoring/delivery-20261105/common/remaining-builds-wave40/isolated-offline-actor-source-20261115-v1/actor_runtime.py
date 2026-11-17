"""Concrete isolated actor ownership and N017 integration; no provider service."""
from hashlib import sha256
import os
from pathlib import Path
import re
import socket
import sys
import time
from types import SimpleNamespace
import uuid

import actor_contract
import actor_stream


def need(ok, message):
    if not ok:
        raise ValueError(message)


def folder_for(config, mode):
    values = config.value
    contexts = values["actor"]["arms"]
    need(type(contexts) is dict and 1 <= len(contexts) <= 4 and
         type(mode) is str and re.fullmatch("[A-Za-z0-9_][A-Za-z0-9_-]{0,63}", mode) and
         mode in contexts, "Exact source-admitted offline context")
    folder = Path(values["output_root"]) / "actors" / mode
    need(values["actor"]["arms"][mode]["context_dir"] == str(folder),
         "Exact source-bound actor journal directory")
    return folder


def task_config(config, stack, body, mode):
    value = stack.operator_config.decode(body)
    need(type(value) is dict and set(value) == {"schema", "mode", "tool_id", "policy"} and
         value["mode"] == mode and all(type(v) is str and
         re.fullmatch("[A-Za-z0-9_][A-Za-z0-9_.:/@-]{0,255}", v) for v in value.values()),
         "Four source-admitted public scalar fields, never operator paths or receipts")
    # Each concrete driver validates schema/tool/policy/budget semantics before
    # runtime admission. N017 does so in operation_admission; this transport is
    # also reusable by the separately reviewed four-cell DMFC driver.
    return value


def reserve_actor(session):
    need(session.state == "preparation" and session.used.calls == 0 and
         not getattr(session, "_isolated_actor_reserved", False),
         "Reserve actor before any candidate operation")
    usage_type = type(session.used)  # The exact existing broker ABI, never reimported.
    total = usage_type(cpu_us=actor_contract.PIDS * session.limits.wall_us)
    preparation = usage_type(cpu_us=actor_contract.PIDS * session.limits.preparation_wall_us)
    need(session.used.add(total).within(session.limits.total) and
         session.preparation_used.add(preparation).within(session.limits.preparation),
         "Full actor reservations fit the original common budgets")
    # Each actor cgroup's memory includes its tmpfs; the independent numerical
    # volume has its own 40 MiB bound. The sum remains within the existing 4 GiB.
    aggregate = 3 * 1024**3 + 256 * 1024**2 + 40 * 1024**2 + actor_contract.MEMORY
    need(aggregate <= session.limits.max_memory_bytes, "Complete simultaneous memory ceilings")
    session._isolated_actor_reserved = True
    session.used = session.used.add(total)
    session.preparation_used = session.preparation_used.add(preparation)
    session._event("offline_actor_reserved", total_cpu_us=total.cpu_us,
                   preparation_cpu_us=preparation.cpu_us, cpu_kind="PID-times-whole-wall upper bound",
                   memory_bound_bytes=actor_contract.MEMORY, measured_compute=False)


def actor_engine(stack, runtime, until, folder, budget):
    cls = actor_contract.engine_class(runtime.qualified_core.BaseEngine, runtime.engines.identity)
    return cls(until, folder, budget)


def read_intent(config, stack, mode):
    folder = folder_for(config, mode)
    value = stack.operator_config.decode(stack.operator_config.capture(folder / "actor_intent.json", 65536))
    need(type(value) is dict and set(value) == {"schema", "mode", "config_sha256",
         "request_sha256", "context", "name", "program", "actor_config", "deadline_us",
         "child_argv", "controller"} and value["schema"] == "isolated-offline-actor-intent/v1" and
         value["mode"] == mode and value["config_sha256"] == config.sha256 and
         value["request_sha256"] == config.request_sha256 and
         value["context"] == config.value["actor"]["arms"][mode] and
         re.fullmatch("offline-actor-[a-f0-9]{32}", value["name"]) is not None and
         type(value["deadline_us"]) is int,
         "Exact immutable actor origin and horizon")
    for key, filename in (("program", "program.py"), ("actor_config", "config.json")):
        pin = value[key]
        original = config.value["actor"]["arms"][mode]["program" if key == "program" else "config"]
        need(pin == {"path": str(folder / filename), "bytes": original["bytes"],
                     "sha256": original["sha256"]}, "Captured actor input equals admitted source")
    return value


def recover_mode(config, stack, runtime, mode, budget, until, proc=None):
    """Stop the exact separate creator group before captured-ID container recovery."""
    folder = folder_for(config, mode)
    result = {"mode": mode, "absence_verified": False}
    try:
        marks = stack.entrypoint.MARKERS
        if not folder.exists():
            return dict(result, absence_verified=True, never_launched=True)
        if not (folder / "actor_intent.json").exists():
            need(not any((folder / "owner" / x).exists() for x in marks) and
                 not (folder / "engine" / "resource_ownership.json").exists(),
                 "No actor creator/resource may exist without its source-bound intent")
            return dict(result, absence_verified=True, never_launched=True)
        intent = read_intent(config, stack, mode)
        group = stack.entrypoint.group_stop(runtime.owner, folder / "owner", until, proc)
        result["group"] = group
        if group.get("absence_verified") is not True:
            return result
        journal = folder / "engine" / "resource_ownership.json"
        if not journal.exists():
            result.update(absence_verified=True, no_container_dispatch=True)
            return result
        owned = runtime.engines.identity.read_json(journal, 65536)
        need(type(owned) is dict and set(owned) == {"owned"} and type(owned["owned"]) is list and
             len(owned["owned"]) == 1 and owned["owned"][0].get("name") == intent["name"],
             "Exactly one source-bound actor create")
        engine = actor_engine(stack, runtime, until, folder / "engine", budget)
        engine.owned = owned["owned"]
        mounts = {"/actor/program.py": {"type": "bind", "source": intent["program"]["path"], "rw": False}}
        result["container"] = engine.recover(intent["name"], mounts)
        result["absence_verified"] = result["container"].get("absence_verified") is True
        result["profile"] = actor_contract.descriptor()
    except BaseException as error:
        result["error_type"] = type(error).__name__
    return result


class Supervisor:
    def __init__(self, config, stack, runtime, session, budget, work_end):
        self.config, self.stack, self.runtime = config, stack, runtime
        self.session, self.budget, self.work_end = session, budget, work_end
        self.folder = folder_for(config, session.mode)
        self.proc, self.receipt, self.launched, self.closed = None, None, False, False

    def launch(self):
        need(not self.closed and not self.launched and not self.folder.exists(), "Fresh one-shot actor context")
        self.launched = True
        self.folder.mkdir(mode=0o700)
        for name in ("owner", "engine"):
            (self.folder / name).mkdir(mode=0o700)
        config, stack, mode = self.config, self.stack, self.session.mode
        values = config.value
        source_root = Path(values["repository_root"])
        context = values["actor"]["arms"][mode]
        pins = {}
        for key, filename in (("program", "program.py"), ("config", "config.json")):
            body = stack.operator_config.checked(source_root, context[key], 65536)
            if key == "config":
                task_config(config, stack, body, mode)
            target = self.folder / filename
            self.budget.write(target, body, mode=0o444)
            pins[key] = {"path": str(target), "bytes": len(body), "sha256": sha256(body).hexdigest()}
        descriptor = stack.entrypoint.captured_descriptor(stack, "actor_service", source_root)
        deadline_us = self.session.started + self.session.limits.wall_us
        need(deadline_us / 1000000 <= self.work_end, "Actor uses original candidate horizon")
        argv = [sys.executable, str(source_root / descriptor["path"]), "--config",
                str(config.source_path), "--config-sha256", config.sha256, "--mode", mode,
                "--owner-directory", str(self.folder / "owner")]
        stack.entrypoint.durable(self.folder / "actor_intent.json", {
            "schema": "isolated-offline-actor-intent/v1", "mode": mode,
            "config_sha256": config.sha256, "request_sha256": config.request_sha256,
            "context": context, "name": "offline-actor-" + uuid.uuid4().hex,
            "program": pins["program"], "actor_config": pins["config"],
            "deadline_us": deadline_us, "child_argv": argv, "controller": descriptor}, self.budget)
        remaining = deadline_us / 1000000 - time.monotonic()
        need(remaining >= 1, "Original positive remaining horizon; no actor clock restart")
        # The admitted owner enforces its reviewed maximum. N017's source gate
        # still limits its owner to300s; a separately reviewed owner may differ.
        self.proc = self.runtime.owner.launch(argv, self.folder / "owner", remaining, descriptor)

    def stop(self):
        self.closed = True
        if self.receipt is not None:
            return self.receipt
        until = min(self.work_end, (self.session.started + self.session.limits.wall_us) / 1000000)
        receipt = recover_mode(self.config, self.stack, self.runtime, self.session.mode,
                               self.budget, until, self.proc)
        self.receipt = receipt
        if self.folder.exists():
            self.stack.entrypoint.durable(self.folder / "actor_cleanup.json", receipt, self.budget)
        need(receipt["absence_verified"] is True, "Actor absence required before commit/grade")
        self.session._event("offline_actor_absent", receipt=receipt)
        return receipt


def install(config, stack, runtime, root, budget, work_end):
    """Install the concrete actor server in a new stack; original transport is immutable."""
    need(actor_contract.STREAM_LIMITS == actor_stream.STREAM_LIMITS, "Same admitted actor stream limits")
    original = stack.unix_arm
    class Policy(original.ReservationPolicy):
        def descriptor(self):
            return dict(super().descriptor(), isolated_offline_actor=actor_contract.descriptor())

    class Server(original.UnixArmServer):
        def __init__(self, path, session, policy, expected_uid):
            reserve_actor(session)
            super().__init__(path, session, policy, expected_uid=expected_uid)
            self.actor = Supervisor(config, stack, runtime, session, budget, work_end)

        def _dispatch(self, message, sequence):
            # Authenticate and exact-envelope check BEFORE invoking terminal cleanup.
            need(type(message) is dict, "Actor envelope object")
            if message.get("op") in ("finish", "close"):
                import hmac
                need(type(message) is dict and set(message) == {"seq", "token", "op"} and
                     type(message["seq"]) is int and message["seq"] == sequence and
                     type(message["token"]) is str and hmac.compare_digest(message["token"], self.token),
                     "Authenticated actor terminal request")
                need(self.actor.stop().get("absence_verified") is True,
                     "Actor must be absent before the terminal operation")
            return super()._dispatch(message, sequence)

        def serve_one(self):
            try:
                self.actor.launch()
                return super().serve_one()
            finally:
                result = self.actor.stop()
                need(result["absence_verified"] is True, "Actor cleanup gates successful arm")

    clone = SimpleNamespace(**vars(stack))
    clone.unix_arm = SimpleNamespace(ReservationPolicy=Policy, UnixArmServer=Server)
    return clone


def run_owned_actor(config, stack, runtime, mode, owner_directory):
    folder = folder_for(config, mode)
    need(Path(owner_directory) == folder / "owner", "Exact actor owner directory")
    owner, unused = runtime.owner.expected(folder / "owner")
    need(os.getpgrp() == owner["pgid"] and os.getppid() == owner["pid"] and
         owner["child_argv"] == [sys.executable, str(Path(stack.actor_service.__file__).absolute()), *sys.argv[1:]],
         "Actual owned actor process/argv, not a caller claim")
    intent = read_intent(config, stack, mode)
    need(intent["child_argv"] == owner["child_argv"] and intent["controller"] == owner["controller"],
         "Owner matches original actor intent")
    until = intent["deadline_us"] / 1000000
    need(time.monotonic() < until, "Original actor horizon")
    values = config.value
    budget = runtime.HostBudget(Path(values["output_root"]), values["host_budget"]["artifact_bytes"],
                                values["host_budget"]["receipt_bytes"])
    for key in ("program", "actor_config"):
        b = stack.operator_config.capture(intent[key]["path"], 65536)
        need(len(b) == intent[key]["bytes"] and sha256(b).hexdigest() == intent[key]["sha256"],
             "Exact immutable actor snapshot")
        if key == "actor_config":
            actor_config = task_config(config, stack, b, mode)
    invitation_path = Path(values["output_root"]) / "invitations" / (mode + ".json")
    invitation = stack.operator_config.decode(stack.operator_config.capture(invitation_path, 65536))
    arm_path = Path(values["output_root"]) / "arms" / mode / "arm.sock"
    need(invitation.get("mode") == mode and invitation.get("socket") == str(arm_path) and
         invitation.get("actor_binding") == values["actor"]["arms"][mode] and
         invitation.get("candidate_deadline_us") == intent["deadline_us"],
         "Exact admitted arm invitation")
    engine = actor_engine(stack, runtime, until, folder / "engine", budget)
    mounts = {"/actor/program.py": {"type": "bind", "source": intent["program"]["path"], "rw": False}}
    info, boundary = engine.create(intent["name"], "offline_actor", mounts)
    need(re.fullmatch("[a-f0-9]{64}", info.get("Id", "")) is not None, "Captured actor immutable ID")
    endpoint = runtime.qualified_core.BaseEngine.run.__globals__["ENV"]["DOCKER_HOST"]
    need(type(endpoint) is str and endpoint.startswith("unix:///"), "Actual admitted engine daemon endpoint")
    docker = stack.wire.DockerHTTP(endpoint[len("unix://"):])
    actor_wire = actor_stream.attach(docker, info["Id"], until, stack.wire.Wire)
    arm = None
    try:
        started = engine.run(["start", info["Id"]], timeout=3)
        need(started.returncode == 0, "Start only inspected captured actor after attaching")
        while True:
            need(time.monotonic() < until, "No endpoint waiting clock reset")
            arm = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            arm.settimeout(max(.001, until - time.monotonic()))
            try:
                arm.connect(str(arm_path))
                break
            except (FileNotFoundError, ConnectionRefusedError):
                arm.close()
                time.sleep(min(.01, max(0, until - time.monotonic())))
        pump = actor_stream.ActorPump(actor_wire, stack.wire.decode)
        def terminal(value):
            stack.entrypoint.durable(folder / "terminal_intent.json", {
                **value, "config_sha256": config.sha256, "mode": mode,
                "actor_id": info["Id"], "profile": actor_contract.descriptor(),
                "actor_stream": pump.report()}, budget)
        result = actor_stream.relay(pump, stack.wire.Wire(arm, until), invitation["token"],
                                    actor_config, stack.wire.encode,
                                    response_cap=values["limits"]["response_bytes"],
                                    terminal_intent=terminal)
        # Parent may stop this group immediately after the terminal dispatch.
        # A missing later return receipt is never silently invented.
        return result
    finally:
        if arm is not None:
            arm.close()
        actor_wire.sock.close()

