"""Concrete whole132 paired controller owner; no scientific code or grants."""
from dataclasses import dataclass, field
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import socket
import stat
import time
import uuid

from .n071_linux.filesystem import Directory, FilePin, capture, acquire_fd
from .native_owner import NativeOwner, observe_controller, observe_recovery, drain_original_streams
from .resource_journal import Journal, BODY_CAP
from .resource_registry import Registry

HERE = Path(__file__).absolute().parent
SOURCE_ROOT = HERE.parent


def need(value, reason):
    if not value:
        raise ValueError(reason)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode()


def pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def pin_shape(value):
    need(type(value) is dict and set(value) == {"bytes", "sha256", "mode"} and
         type(value["bytes"]) is int and value["bytes"] >= 0 and
         type(value["sha256"]) is str and len(value["sha256"]) == 64 and
         all(c in "0123456789abcdef" for c in value["sha256"]) and
         type(value["mode"]) is int and value["mode"] in (0o400, 0o444, 0o500, 0o555, 0o644, 0o755),
         "exact-selected-body-pin-and-mode")


def absolute(value):
    need(type(value) is str and value.startswith("/") and os.path.normpath(value) == value and
         "\x00" not in value, "absolute-normal-operand")
    return Path(value)


@dataclass(eq=False)
class OuterOutcome:
    owner: object
    registry: object = None
    journal: object = None
    controller: object = None
    recovery_child: object = None
    source_captures: list = field(default_factory=list)
    observations: dict = field(default_factory=dict)
    publications: list = field(default_factory=list)
    closed: bool = False

    def require_closed(self):
        parent = self.owner
        need(type(parent) is NativeOwner and parent.owner_pid == os.getpid() and
             parent.first is None and parent.owner.closed and self.closed and
             type(self.registry) is Registry and self.registry.natural_complete() and
             self.journal is self.registry.journal and self.journal.closed and
             self.journal.first is None and self.controller in parent.children,
             "actual-original-owner-and-registry-closure")
        child = self.controller
        need(child.waited and child.exit_code == 0 and type(child.exit_code) is int and
             child.activated and not child.kill_sent and child.streams_closed and
             child.stream_eof == {"stdout", "stderr"} and child.group.closed and
             child.group.final is not None and not child.group.final.populated,
             "actual-natural-controller-stream-and-descendant-closure")
        need(all(group.closed for group in parent.groups), "all-original-host-scopes-closed")
        return self


class OuterFailure(RuntimeError):
    def __init__(self, outcome):
        self.outcome = outcome
        self.original = outcome.owner.first
        super().__init__("FIND032 original owner failed; original objects and prefixes retained")


class ChannelPair:
    cleanup_priority = 50
    def __init__(self, parent):
        self.parent, self.sockets, self.tokens = parent, (), []
        self.closed = [False, False]
        self.accounted = [False, False]
        parent.owner.retain(self)
        self.attempt = parent.owner.begin("find032-owned-endpoint-pair")
        try:
            for _ in range(2):
                self.tokens.append(parent.capacity.reserve("live_fds", 1, "find032-endpoint-pair"))
            mask = signal.pthread_sigmask(signal.SIG_BLOCK,
                                          {signal.SIGALRM, signal.SIGTERM, signal.SIGINT})
            try:
                self.sockets = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
            finally:
                signal.pthread_sigmask(signal.SIG_SETMASK, mask)
            for index, token in enumerate(self.tokens):
                parent.capacity.settle(token, 1)
                self.accounted[index] = True
            self.attempt.returned.append(self.sockets)
            self.attempt.finish()
        except BaseException as error:
            self.attempt.fail(error, "endpoint-pair")
            parent.fail(error, "endpoint-pair")
            raise

    def close_one(self, index):
        if self.closed[index]:
            return
        self.closed[index] = True
        known = False
        try:
            if index < len(self.sockets):
                self.sockets[index].close()
            known = True
        except BaseException as error:
            self.parent.fail(error, "endpoint-close")
        if self.accounted[index]:
            try:
                self.parent.capacity.release_live("live_fds", 1, known=known)
            except BaseException as error:
                self.parent.fail(error, "endpoint-accounting")

    def close(self):
        for index in range(2):
            self.close_one(index)


def recovery_request(parent, raw):
    need(type(raw) is bytes and 0 < len(raw) <= 4096, "bounded-original-recovery-input")
    read, write = parent.pipe("find032-recovery-input", cleanup=True)
    token = parent.recovery_capacity.reserve("write_bytes", len(raw),
                                             "find032-recovery-input", cleanup=True)
    count = 0
    pending = False
    attempt = parent.owner.begin("find032-recovery-input-write", cleanup=True)
    attempt.returned.append(raw)
    try:
        need(len(raw) <= os.fpathconf(write.fd, "PC_PIPE_BUF"), "atomic-owned-pipe-request")
        os.set_blocking(write.fd, False)
        pending = True
        count = os.write(write.fd, raw)
        pending = False
        need(count == len(raw), "complete-recovery-request")
    except BaseException as error:
        attempt.fail(error, "recovery-input")
        parent.fail(error, "recovery-input")
    finally:
        try:
            parent.recovery_capacity.settle(token, count, unknown=pending)
        except BaseException as error:
            parent.fail(error, "recovery-input-settlement")
        try:
            write.close()
        except BaseException as error:
            parent.fail(error, "recovery-input-writer-close")
    attempt.raise_first()
    return read


def verify_recovery(value, rows):
    need(type(value) is dict and set(value) == {
        "schema", "results", "commands", "cli_groups_closed", "original_error_types",
        "original_command_evidence",
        "original_retirement_error_evidence",
        "study_failure_unchanged", "automatic_retry", "runtime_or_scientific_qualification_added"},
        "fixed-original-recovery-result")
    need(value["schema"] == "find032_original_daemon_recovery_result_v1" and
         value["study_failure_unchanged"] is True and value["automatic_retry"] is False and
         value["runtime_or_scientific_qualification_added"] is False and
         type(value["results"]) is list and len(value["results"]) == len(rows),
         "complete-original-recovery-result")
    indices = set()
    closed = True
    for item in value["results"]:
        need(type(item) is dict and set(item) == {"original_index", "resource", "result"} and
             type(item["original_index"]) is int and 0 <= item["original_index"] < len(rows) and
             item["original_index"] not in indices, "each-original-recovery-row-once")
        index = item["original_index"]
        indices.add(index)
        row, result = rows[index], item["result"]
        need(item["resource"] == row and type(result) is dict and
             result.get("kind") == row["kind"] and result.get("name") == row["name"] and
             type(result.get("closed")) is bool, "exact-original-resource-recovery-join")
        if result["closed"]:
            if row["attempted"]:
                unknown = not row["acknowledged"] and not result.get("removed", False)
                need(result.get("absence_observed") is True and
                     result.get("creation_outcome_unknown") is unknown and not unknown,
                     "no-closed-unacknowledged-absence")
            else:
                need(result.get("create_not_attempted") is True and
                     result.get("removed") is False and result.get("observed_namespace_empty") is True,
                     "not-attempted-resource-preserved")
        closed = closed and result["closed"]
    need(type(value["commands"]) is list and type(value["cli_groups_closed"]) is bool,
         "original-cli-observations")
    cli = value["cli_groups_closed"] and (not rows or bool(value["commands"])) and all(
        type(x) is dict and x.get("client_reaped") is True and
        x.get("cleanup_complete") is True and x.get("owned_group_absence_observed") is True and
        x.get("cleanup_before_original_cutoff") is True
        for x in value["commands"])
    return {"all_known_daemon_resources_closed": closed and cli,
            "original_result": value, "study_failure_unchanged": True}

def _capture_absolute(parent, name, expected):
    path = absolute(name)
    pin_shape(expected)
    parent.tick()
    directory = Directory.open_absolute(parent.owner, parent.capacity, str(path.parent))
    body = None
    first = None
    try:
        body = capture(directory, FilePin(path.name, expected["bytes"],
                                        expected["sha256"], expected["mode"]))
    except BaseException as error:
        first = error
        parent.fail(error, "selected-operand-capture")
    finally:
        try:
            directory.fd.close()
        except BaseException as error:
            parent.fail(error, "selected-operand-parent-close")
            if first is None:
                first = error
    if first is not None:
        raise first
    parent.tick()
    return body


def _capture_sources(parent, selection):
    need(type(selection) is dict and 1 <= len(selection) <= 256,
         "finite-complete-source-selection")
    rows = {}
    for name, expected in selection.items():
        need(type(name) is str and len(name) <= 240 and
             name.startswith(("find032_runtime/", "find032/")) and
             all(part not in ("", ".", "..") for part in name.split("/")) and
             "\\" not in name and "\x00" not in name, "fixed-two-package-source-member")
        pin_shape(expected)
        need(expected["bytes"] <= 2 * 1024 * 1024, "ordinary-source-member-bound")
        rows[name] = dict(expected)
    required = {"find032_runtime/controller_entry.py", "find032_runtime/recovery_worker.py",
                "find032_runtime/docker_transport.py", "find032_runtime/failure_evidence.py",
                "find032_runtime/outer.py", "find032_runtime/native_owner.py"}
    need(required <= set(rows), "complete-actual-child-and-recovery-source")
    root = Directory.open_absolute(parent.owner, parent.capacity, str(SOURCE_ROOT))
    captures = []
    parent.raw_returns.append(captures)
    first = None
    try:
        for name in sorted(rows):
            parent.tick()
            p = rows[name]
            captures.append(capture(root, FilePin(name, p["bytes"], p["sha256"], p["mode"])))
    except BaseException as error:
        first = error
        parent.fail(error, "whole-runtime-source-capture")
    finally:
        try:
            root.fd.close()
        except BaseException as error:
            parent.fail(error, "runtime-source-root-close")
            if first is None:
                first = error
    if first is not None:
        raise first
    return rows, captures


def _publish(parent, directory, name, raw, outcome):
    """One bounded cleanup-reserved publication; partial effects remain owned."""
    need(type(raw) is bytes and len(raw) <= 1048576 and
         type(name) is str and name and "/" not in name and name not in (".", ".."),
         "fixed-bounded-owner-publication")
    capacity = parent.recovery_capacity
    attempt = parent.owner.begin("find032-owner-publication:" + name, cleanup=True)
    attempt.returned.append(raw)
    token = fd = None
    count = 0
    pending = False
    result = {"path": str(Path(directory.absolute) / name), "complete": False,
              "bytes_written": 0, "uncertain_suffix": False}
    outcome.publications.append(result)
    try:
        need(time.monotonic() < parent.final_endpoint, "same-final-publication-cutoff")
        memory = capacity.reserve("rss_bytes", len(raw), "owner-publication-buffer", cleanup=True)
        capacity.settle(memory, len(raw))
        token = capacity.reserve("write_bytes", len(raw), "owner-publication-body", cleanup=True)
        capacity.consume_attempt("creation_attempts", "owner-publication-create", cleanup=True)
        fd = acquire_fd(parent.owner, capacity, name, os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                        parent=directory.fd.require_live(), mode=0o600, cleanup=True)
        while count < len(raw):
            need(time.monotonic() < parent.final_endpoint, "original-publication-write-cutoff")
            pending = True
            n = os.write(fd.require_live(), memoryview(raw)[count:])
            count += n
            result["bytes_written"] = count
            pending = False
            need(0 < n and count <= len(raw), "complete-owned-publication-write")
        pending = True
        os.fsync(fd.require_live())
        os.fchmod(fd.require_live(), 0o400)
        os.fsync(directory.fd.require_live())
        pending = False
        result.update(pin(raw))
    except BaseException as error:
        attempt.fail(error, "owner-publication")
        parent.fail(error, "owner-publication:" + name)
        if pending:
            result["uncertain_suffix"] = True
            attempt.uncertain("publication-effect", {"known_bytes": count})
    finally:
        if token is not None:
            try:
                capacity.settle(token, count, unknown=pending)
            except BaseException as error:
                attempt.fail(error, "publication-settlement")
                parent.fail(error, "publication-settlement")
        if fd is not None:
            try:
                fd.close()
            except BaseException as error:
                attempt.fail(error, "publication-close")
                parent.fail(error, "publication-close")
    attempt.raise_first()
    attempt.finish()
    result["complete"] = True
    return result


def execute(*, python, python_pin, controller_config, config_pin, source_selection,
            host_selection, observation_root, origin, normal_end, cleanup_end,
            final_end, docker, docker_pin, socket):
    """Fixed two-arm controller plus owned daemon recovery; returns original objects.

    The caller authenticates this imported source and selects every input/budget.
    controller_entry authenticates the emitted whole source map before imports.
    No target/reference location is added to the child configuration here.
    """
    need(os.uname().sysname == "Linux" and os.geteuid() == 0, "selected-Linux-root-owner")
    need(all(type(x) in (int, float) and math.isfinite(x)
             for x in (origin, normal_end, cleanup_end, final_end)) and
         origin <= time.monotonic() < normal_end < cleanup_end < final_end,
         "one-original-normal-recovery-final-interval")
    parent = NativeOwner(host_selection, origin, final_end)
    outcome = OuterOutcome(parent)
    observation = channel = controller = recovery_child = None
    rows = ()
    recovery = {"all_known_daemon_resources_closed": False, "not_attempted": True}
    source_map = None
    cache_path = None
    recovery_config = None
    try:
        source_map, captured = _capture_sources(parent, source_selection)
        outcome.source_captures.extend(captured)
        for path, expected in ((python, python_pin), (docker, docker_pin),
                               (controller_config, config_pin)):
            outcome.source_captures.append(_capture_absolute(parent, path, expected))
        need(os.access(python, os.X_OK) and os.access(docker, os.X_OK),
             "selected-executable-paths")
        absolute(socket)
        target = absolute(observation_root)
        base = Directory.open_absolute(parent.owner, parent.capacity, str(target.parent))
        observation_error = None
        try:
            observation = base.child(target.name, create=True)
        except BaseException as error:
            observation_error = error
            parent.fail(error, "observation-root-create")
        finally:
            try:
                base.fd.close()
            except BaseException as error:
                parent.fail(error, "observation-parent-close")
                if observation_error is None:
                    observation_error = error
        if observation_error is not None:
            raise observation_error
        st = os.fstat(observation.fd.require_live())
        need(st.st_uid == 0 and stat.S_IMODE(st.st_mode) == 0o700,
             "fresh-root-owned-observation-directory")
        cache = observation.child("bytecode-cache", create=True)
        cache_error = None
        try:
            os.fchmod(cache.fd.require_live(), 0o550)
            need(not os.listdir(cache.fd.require_live()), "fresh-empty-bytecode-cache")
            cache_path = cache.absolute
            cache_state = os.fstat(cache.fd.require_live())
            outcome.observations["bytecode_cache"] = {
                "path": cache_path, "device": cache_state.st_dev, "inode": cache_state.st_ino,
                "uid": cache_state.st_uid, "gid": cache_state.st_gid, "mode": 0o550}
        except BaseException as error:
            cache_error = error
            parent.fail(error, "private-cache-creation")
        finally:
            try:
                cache.fd.close()
            except BaseException as error:
                parent.fail(error, "private-cache-close")
                if cache_error is None:
                    cache_error = error
        if cache_error is not None:
            raise cache_error
        config_directory = observation.child("recovery-docker-config", create=True)
        config_error = None
        try:
            config_state = os.fstat(config_directory.fd.require_live())
            need(config_state.st_uid == 0 and stat.S_IMODE(config_state.st_mode) == 0o700,
                 "private original recovery Docker configuration")
            with os.scandir(config_directory.fd.require_live()) as entries:
                need(next(entries, None) is None, "fresh empty recovery Docker configuration")
            recovery_config = {"path": config_directory.absolute, "device": config_state.st_dev,
                               "inode": config_state.st_ino, "uid": config_state.st_uid,
                               "gid": config_state.st_gid, "mode": 0o700}
            outcome.observations["recovery_docker_config"] = recovery_config
        except BaseException as error:
            config_error = error
            parent.fail(error, "recovery-config-creation")
        finally:
            try:
                config_directory.fd.close()
            except BaseException as error:
                parent.fail(error, "recovery-config-close")
                if config_error is None:
                    config_error = error
        if config_error is not None:
            raise config_error
        manifest = {"schema": "find032_captured_runtime_sources_v1", "root": str(SOURCE_ROOT),
                    "files": source_map}
        descriptor = _publish(parent, observation, "source-capture.json", encoded(manifest), outcome)
        # The fixed child's complete source/config/bootstrap reads are a separate
        # actual effect, precharged before launch and never refunded on failure.
        bootstrap_read = (sum(row["bytes"] + 1 for row in source_map.values()) +
                          descriptor["bytes"] + 1 + config_pin["bytes"] + 1)
        token = parent.capacity.reserve("read_bytes", bootstrap_read,
                                        "complete-child-source-and-config-bootstrap")
        parent.capacity.settle(token, token.capacity)
        outcome.observations["child_bootstrap_read_reservation"] = bootstrap_read
        parent.prepare()
        journal = Journal(observation, "RESOURCE_JOURNAL.jsonl", final_end, BODY_CAP)
        outcome.journal = journal
        registry = Registry(journal, uuid.uuid4().hex[:24])
        outcome.registry = registry
        channel = ChannelPair(parent)
        server, client = channel.sockets
        argv = [python, "-I", "-S", "-B", "-X", "pycache_prefix=" + cache_path,
                str(HERE / "controller_entry.py"),
                "--config", controller_config, "--config-bytes", str(config_pin["bytes"]),
                "--config-sha256", config_pin["sha256"],
                "--source-manifest", descriptor["path"],
                "--source-manifest-bytes", str(descriptor["bytes"]),
                "--source-manifest-sha256", descriptor["sha256"],
                "--ownership-fd", str(client.fileno()), "--original-endpoint", str(normal_end),
                "--cleanup-endpoint", str(cleanup_end)]
        controller = parent.spawn(argv, {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
                                  parent.controller_group, normal_end,
                                  inherited=(client.fileno(),))
        outcome.controller = controller
        channel.close_one(1)
        observe_controller(parent, controller, server, registry, normal_end)
        if parent.first is None:
            need(not parent.controller_group.sample(cleanup=True).populated,
                 "natural-controller-completion-with-empty-descendant-tree")
    except BaseException as error:
        if parent.owner.custody.first is not None:
            parent.fail(parent.owner.custody.first, "original-acquisition-first")
        parent.fail(error, "whole132-controller-or-admission")
    finally:
        if controller is None and parent.children:
            controller = parent.children[0]
            outcome.controller = controller
        if parent.controller_group is not None:
            try:
                parent.close_group(parent.controller_group, cleanup_end)
            except BaseException as error:
                parent.fail(error, "controller-cgroup-retirement")
        if controller is not None:
            for name, operation in (("controller-wait", lambda: controller.retire(cleanup_end)),
                                    ("controller-stream-drain", lambda: drain_original_streams(controller, cleanup_end)),
                                    ("controller-stream-close", controller.close_streams)):
                try:
                    operation()
                except BaseException as error:
                    parent.fail(error, name)
        if channel is not None:
            try:
                channel.close()
            except BaseException as error:
                parent.fail(error, "ownership-channel-close")
    if outcome.registry is not None:
        rows = outcome.registry.recovery_rows()
    if parent.first is not None and rows and parent.controller_group is not None and parent.controller_group.closed:
        try:
            need(time.monotonic() < cleanup_end and observation is not None,
                 "original-daemon-recovery-reserve-remains")
            request = {"schema": "find032_original_daemon_recovery_v1", "rows": list(rows),
                       "docker": docker, "socket": socket,
                       "docker_config": recovery_config,
                       "docker_pin": {k: docker_pin[k] for k in ("bytes", "sha256")},
                       "executor_pin": {k: source_map["find032_runtime/docker_transport.py"][k]
                                        for k in ("bytes", "sha256")},
                       "deadline": cleanup_end,
                       "failure_source_pin": {k: source_map["find032_runtime/failure_evidence.py"][k]
                                              for k in ("bytes", "sha256")},
                       "failure_directory": str(Path(observation.absolute) / "recovery-command-failures"),
                       "failure_byte_cap": 1048576}
            reserve = parent.recovery_capacity.reserve("write_bytes", request["failure_byte_cap"],
                                                       "complete-recovery-evidence-envelope", cleanup=True)
            parent.recovery_capacity.settle(reserve, reserve.capacity)
            source_reads = (request["executor_pin"]["bytes"] +
                            request["failure_source_pin"]["bytes"] + request["docker_pin"]["bytes"] + 4099)
            token = parent.recovery_capacity.reserve("read_bytes", source_reads,
                                                      "fixed-recovery-source-and-binary-recapture", cleanup=True)
            parent.recovery_capacity.settle(token, token.capacity)
            raw = encoded(request)
            request_pipe = recovery_request(parent, raw)
            recovery_child = parent.spawn(
                [python, "-I", "-S", "-B", "-X", "pycache_prefix=" + cache_path,
                 str(HERE / "recovery_worker.py"), "--request-fd", str(request_pipe.fd)],
                {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
                parent.recovery_group, cleanup_end, inherited=(request_pipe.fd,), cleanup=True)
            outcome.recovery_child = recovery_child
            request_pipe.close()
            error = observe_recovery(parent, recovery_child, cleanup_end)
            if error is None:
                need(not parent.recovery_group.sample(cleanup=True).populated,
                     "natural-recovery-with-empty-descendant-tree")
                recovery = verify_recovery(json.loads(bytes(recovery_child.stdout)), list(rows))
        except BaseException as error:
            parent.fail(error, "original-daemon-recovery")
    elif parent.first is not None and not rows:
        recovery = {"all_known_daemon_resources_closed": True, "known_resources": 0,
                    "study_failure_unchanged": True}
    if recovery_child is None:
        recovery_child = next((child for child in parent.children if child.cleanup), None)
        outcome.recovery_child = recovery_child
    if parent.recovery_group is not None:
        try:
            parent.close_group(parent.recovery_group, final_end)
        except BaseException as error:
            parent.fail(error, "recovery-cgroup-retirement")
    if recovery_child is not None:
        for name, operation in (("recovery-wait", lambda: recovery_child.retire(final_end)),
                                ("recovery-drain", lambda: drain_original_streams(recovery_child, final_end)),
                                ("recovery-stream-close", recovery_child.close_streams)):
            try:
                operation()
            except BaseException as error:
                parent.fail(error, name)
    if outcome.journal is not None:
        try:
            outcome.journal.close()
        except BaseException as error:
            parent.fail(error, "journal-close")
    if observation is not None:
        for name, child in (("controller", controller), ("recovery", recovery_child)):
            if child is None:
                continue
            for stream in ("stdout", "stderr"):
                try:
                    _publish(parent, observation, name + "-" + stream + ".bin",
                             bytes(getattr(child, stream)), outcome)
                except BaseException as error:
                    parent.fail(error, "original-stream-publication")
            outcome.observations[name] = child.projection()
        outcome.observations.update({"schema": "find032_whole132_owner_observation_v1",
            "scope": {"arms": ["A", "B"], "recordings_per_arm": 132},
            "source_manifest": source_map,
            "journal": None if outcome.journal is None else outcome.journal.projection(),
            "recovery": recovery, "original_error_types": [
                {"stage": stage, "type": type(error).__name__} for stage, error in parent.errors],
            "normal_endpoint": normal_end, "cleanup_endpoint": cleanup_end,
            "final_endpoint": final_end, "native_parent_budget": parent.capacity.report(),
            "recovery_budget": parent.recovery_capacity.report(),
            "final_owner_retirement_pending": True, "scientific_qualification": False,
            "external_enclosing_exit_required": True})
        try:
            _publish(parent, observation, "OWNER_OBSERVATION.json", encoded(outcome.observations), outcome)
        except BaseException as error:
            parent.fail(error, "owner-observation-publication")
    try:
        parent.finish()
    except BaseException as error:
        if parent.first is None:
            parent.fail(error, "final-owner-retirement")
    if parent.first is None:
        try:
            # Final cgroup samples and actual owner cleanup may add CPU/wall
            # after the last observer tick. Admit those original counters too.
            parent.tick()
            outcome.closed = True
            outcome.require_closed()
            need(time.monotonic() < final_end, "whole-original-owner-cutoff")
        except BaseException as error:
            parent.fail(error, "actual-final-outcome-admission")
            outcome.closed = False
    if parent.first is not None:
        raise OuterFailure(outcome) from parent.first
    return outcome
