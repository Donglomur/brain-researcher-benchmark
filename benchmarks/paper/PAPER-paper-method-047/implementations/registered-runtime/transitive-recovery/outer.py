"""Complete117 GCaMP8 outer owner and exact daemon recovery, with held failures."""
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import time
import uuid

from n071_linux.filesystem import Directory
from native_owner import NativeOwner, OriginalChildFailure, observe_controller, observe_recovery, drain_original_streams
from resource_journal import Journal, BODY_CAP
from resource_registry import Registry

HERE = Path(__file__).absolute().parent


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


class ChannelPair:
    cleanup_priority = 50
    def __init__(self, parent):
        self.parent, self.sockets, self.tokens = parent, (), []
        self.closed = [False, False]
        self.accounted = [False, False]
        parent.owner.retain(self)
        self.attempt = parent.owner.begin("gcamp8-owned-endpoint-pair")
        try:
            for _ in range(2):
                self.tokens.append(parent.capacity.reserve("live_fds", 1, "gcamp8-endpoint-pair"))
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


def write_original(capture, control, path, raw):
    """Preserve exact original bytes under the unchanged observer disk allowance."""
    need(type(raw) is bytes and len(raw) <= 1048580, "bounded-original-stream-artifact")
    capture.tick()
    capture.writes += len(raw)
    need(capture.writes <= 20000000, "original-observer-write-reservation")
    descriptor = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    if raw:
        need(control.write(path, raw, 1048580) == descriptor, "original-stream-write")
    return descriptor


def recovery_request(parent, raw):
    need(type(raw) is bytes and 0 < len(raw) <= 4096, "bounded-original-recovery-input")
    read, write = parent.pipe("gcamp8-recovery-input", cleanup=True)
    token = parent.recovery_capacity.reserve("write_bytes", len(raw),
                                             "gcamp8-recovery-input", cleanup=True)
    count = 0
    pending = False
    attempt = parent.owner.begin("gcamp8-recovery-input-write", cleanup=True)
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
    need(value["schema"] == "gcamp8_original_daemon_recovery_result_v1" and
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


def execute(plan, binding, control, adapter, capture, expected, host_selection, runtime, origin,
            failure_source_pin):
    end = origin + plan["whole"]
    normal_end, cleanup_end = end - 120, end - 60
    need(time.monotonic() < origin + 60 < normal_end, "same-original-source-preflight")
    capture.end = end
    signal.setitimer(signal.ITIMER_REAL, end - time.monotonic())
    available = control.shutil.disk_usage(plan["output"].parent).free
    need(available >= control.FLOOR + plan["selection"]["other_reserved_bytes"] + 33020000000,
         "unchanged-complete33.02GB-plus-floor-and-OTHER")
    plan["output"].mkdir(mode=0o700)
    metadata = plan["output"] / "observer"
    metadata.mkdir(mode=0o700)
    parent = NativeOwner(host_selection, origin, end)
    journal = registry = channel = controller = recovery_child = None
    result = None
    recovery = {"all_known_daemon_resources_closed": False, "not_attempted": True}
    evidence = {"scope": {"neurons": 117, "tracks": 2, "arms": ["A", "B"], "outputs": 468},
                "source": expected, "original_failure_preserved": True,
                "runtime_qualification_added": False, "scientific_qualification_added": False}
    try:
        parent.prepare()
        root = Directory.open_absolute(parent.owner, parent.capacity, str(metadata))
        journal = Journal(root, "RESOURCE_JOURNAL.jsonl", end, BODY_CAP)
        registry = Registry(journal, uuid.uuid4().hex[:24])
        capture.write(metadata / "START.json", {
            "schema": "gcamp8_transitive_outer_start_v1", **evidence,
            "origin_monotonic": origin, "normal_endpoint": normal_end,
            "cleanup_endpoint": cleanup_end, "final_endpoint": end,
            "source_selected_host_limits": host_selection,
            "historical105_reproduced": False, "external_wrapper_exit_required": True})
        channel = ChannelPair(parent)
        server, client = channel.sockets
        argv = adapter.child_argv(plan, binding) + [
            "--ownership-fd", str(client.fileno()), "--original-endpoint", str(normal_end)]
        controller = parent.spawn(argv,
            {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C", "PYTHONDONTWRITEBYTECODE": "1"},
            parent.controller_group, min(origin + 60, normal_end), inherited=(client.fileno(),))
        channel.close_one(1)
        observe_controller(parent, controller, server, registry, normal_end)
        if parent.first is None:
            sample = parent.controller_group.sample(cleanup=True)
            need(not sample.populated, "natural-controller-exit-with-no-surviving-descendants")
    except BaseException as error:
        parent.fail(error, "complete-controller-or-admission")
    finally:
        if controller is None and parent.children:
            controller = parent.children[0]
        if parent.controller_group is not None:
            parent.close_group(parent.controller_group, cleanup_end)
        if controller is not None:
            controller.retire(cleanup_end)
            drain_original_streams(controller, cleanup_end)
            controller.close_streams()
        if channel is not None:
            channel.close()

    # Recovery is a distinct, pre-reserved child, never a scientific replay.
    rows = () if registry is None else registry.recovery_rows()
    if parent.first is not None and rows and parent.controller_group is not None and parent.controller_group.closed:
        try:
            need(time.monotonic() < cleanup_end - 10, "original-recovery-and-final-wait-reserve")
            # Once-only allocation-inclusive reserve inside the existing
            # observer ceiling. Failed and partial writes are never refunded.
            capture.writes += 1048576
            need(capture.writes <= 20000000, "precharged-recovery-evidence-retention")
            request = {"schema": "gcamp8_original_daemon_recovery_v1", "rows": list(rows),
                       "docker": plan["cfg"]["docker"], "socket": plan["cfg"]["socket"],
                       "docker_pin": runtime["executable_pins"]["docker"],
                       "executor_pin": {k: binding["dependencies"]["slice_executor"][k]
                                        for k in ("bytes", "sha256")},
                       "deadline": cleanup_end - 10,
                       "failure_source_pin": failure_source_pin,
                       "failure_directory": str(metadata / "recovery-command-failures"),
                       "failure_byte_cap": 1048576}
            raw = json.dumps(request, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
            request_pipe = recovery_request(parent, raw)
            recovery_child = parent.spawn(
                [plan["cfg"]["python"], "-I", "-S", "-B", str(HERE / "recovery_worker.py"),
                 "--request-fd", str(request_pipe.fd)],
                {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C", "PYTHONDONTWRITEBYTECODE": "1"},
                parent.recovery_group, cleanup_end - 10, inherited=(request_pipe.fd,), cleanup=True)
            request_pipe.close()
            observed_error = observe_recovery(parent, recovery_child, cleanup_end - 10)
            if observed_error is None:
                need(not parent.recovery_group.sample(cleanup=True).populated,
                     "natural-recovery-exit-with-empty-host-tree")
                recovery = verify_recovery(control.parse(bytes(recovery_child.stdout)), list(rows))
        except BaseException as error:
            parent.fail(error, "original-daemon-recovery")
    elif parent.first is not None and not rows:
        recovery = {"all_known_daemon_resources_closed": True, "known_resources": 0,
                    "study_failure_unchanged": True}
    try:
        if recovery_child is None:
            recovery_child = next((child for child in parent.children if child.cleanup), None)
        if parent.recovery_group is not None:
            parent.close_group(parent.recovery_group, cleanup_end)
        if recovery_child is not None:
            recovery_child.retire(cleanup_end)
            drain_original_streams(recovery_child, cleanup_end)
            recovery_child.close_streams()
        if journal is not None:
            journal.close()
            # Journal is part of the existing observer disk allowance.
            capture.writes += journal.offset
            need(capture.writes <= 20000000, "original-journal-plus-observer-write-reserve")
        for name, child in (("controller", controller), ("recovery", recovery_child)):
            if child is not None:
                evidence[name] = {"process": child.projection(),
                    "stdout": write_original(capture, control, metadata / (name + "-stdout.bin"), bytes(child.stdout)),
                    "stderr": write_original(capture, control, metadata / (name + "-stderr.bin"), bytes(child.stderr))}
        if journal is not None:
            evidence["journal"] = journal.projection()
        evidence["recovery"] = recovery
        evidence["failed_command_evidence"] = {
            "controller_fixed_location": "controller/cases/<original-index>/original-command-failures",
            "controller_reservation_bytes": 8388608,
            "recovery_fixed_location": "observer/recovery-command-failures",
            "recovery_reservation_bytes": 1048576 if recovery_child is not None else 0,
            "partial_products_retained": True,
            "structural_evidence_is_not_python_object_identity": True,
            "external_artifact_authentication_required": True}
        evidence["native_parent_budget"] = parent.capacity.report()
        evidence["preselected_recovery_budget"] = parent.recovery_capacity.report()
        evidence["original_error_types"] = [{"stage": stage, "type": type(error).__name__}
                                             for stage, error in parent.errors]
        if parent.first is None:
            parent.tick()
            need(registry is not None and registry.natural_complete(), "full468-original-lifecycle")
            observed = controller.projection()
            completed = adapter.accept(plan, capture, bytes(controller.stdout), observed)
            for path, pin in plan["operands"]:
                capture.read(path, 65536, pin)
            evidence["complete_original_collection"] = completed
            evidence["status"] = "natural_full468_pending_external_wrapper_exit"
        else:
            evidence["status"] = "failed_original_preserved"
        result = capture.write(metadata / "TRANSITIVE_OBSERVATION.json", {
            "schema": "gcamp8_transitive_original_observation_v1", **evidence})
    except BaseException as error:
        parent.fail(error, "original-outer-evidence-or-acceptance")
    finally:
        try:
            parent.finish()
        except BaseException as error:
            # The identical first object is preserved; cleanup does not replace it.
            if parent.first is None:
                parent.fail(error, "outer-native-finalization")
    if parent.first is not None:
        raise parent.first
    return result

