"""Concrete Linux host -> bounded Harbor child -> actual closure, without grading.

The fixed outer supervisor is privileged. The selected host child is not, and
candidate commands only run in the isolated container. External qualifications
are trusted inputs, not produced by this module. No operation runs at import.
"""
import hashlib
import json
import os
from pathlib import Path
import stat
import time
from tms_figure.contract import Budget
from . import schema as s
from . import host_sources
from .host_process import (OwnedHost, HostOwnershipFailure, absolute, atomic,
                           capture, plain_json)
from .host_cli import DockerCommands
from .host_support.common import FailureCarrier
from .storage import admit_storage, recheck_storage


def _pin_body(path, raw, budget, mode=0o444):
    budget.charge(write=len(raw))
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    try:
        os.fchmod(fd, mode)  # Selected mode is independent of the supervisor umask.
        with os.fdopen(fd, "wb", closefd=False) as out:
            out.write(raw); out.flush(); os.fsync(out.fileno())
    finally:
        os.close(fd)
    budget.charge()
    return {"path": str(path), **s.body_pin(raw)}


def _metadata(path, value, budget, cap, mode=0o444):
    body = s.bounded_json(value, cap)
    budget.charge(write=len(body))
    return _pin_body(path, body, budget, mode)


def _empty_root(path, uid=None, mode=None):
    p = absolute(path, True)
    st = p.stat()
    if uid is not None:
        s.require(st.st_uid == uid, "selected root owner")
    if mode is not None:
        s.require(stat.S_IMODE(st.st_mode) == mode, "selected root mode")
    with os.scandir(p) as entries:
        s.require(next(entries, None) is None, "fresh selected root")
    return p


def _mkdir(path, uid, gid, mode):
    path.mkdir(mode=mode)
    os.chown(path, uid, gid)
    os.chmod(path, mode)
    return path


def _cache_identity(runtime, arm, budget):
    """Observe one fixed non-writable empty prefix, never a cache contents tree."""
    budget.charge(read=16384, write=16384)
    stage = absolute(runtime["stage_root"], True)
    st = stage.stat()
    s.require(st.st_uid == 0 and st.st_gid == runtime["host_gid"]
              and stat.S_IMODE(st.st_mode) == 0o710, "root-owned selected-group stage custody")
    root = absolute(stage / ("bytecode-cache-" + arm), True)
    st = root.stat()
    s.require(st.st_uid == 0 and st.st_gid == runtime["host_gid"]
              and stat.S_IMODE(st.st_mode) == 0o550, "root-owned non-writable selected cache prefix")
    with os.scandir(root) as entries:
        s.require(next(entries, None) is None, "selected cache prefix remains empty")
    budget.charge()
    return {"path": str(root), "device": st.st_dev, "inode": st.st_ino,
            "uid": st.st_uid, "gid": st.st_gid, "mode": stat.S_IMODE(st.st_mode)}


def _create_cache_prefix(runtime, arm, budget):
    stage = absolute(runtime["stage_root"], True)
    st = stage.stat()
    s.require(st.st_uid == 0 and st.st_gid == runtime["host_gid"]
              and stat.S_IMODE(st.st_mode) == 0o710, "stage custody before cache creation")
    root = stage / ("bytecode-cache-" + arm)
    s.require(not root.exists() and not root.is_symlink(), "fresh per-arm bytecode prefix")
    root.mkdir(mode=0o700)
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fchown(fd, 0, runtime["host_gid"])
        os.fchmod(fd, 0o550)
    finally:
        os.close(fd)
    return _cache_identity(runtime, arm, budget)


def _task(plan, paths, runtime, capsule, budget):
    # Only two generated files and an empty environment directory. The fixed
    # trial supplies verifier.disable=True; neither normal nor recovery can copy.
    root = Path(paths["task"])
    s.require(not root.exists(), "fresh generated task")
    _mkdir(root, 0, 0, 0o755)
    _mkdir(root / "environment", 0, 0, 0o755)
    cpu = plan["limits"]["cpu"]
    s.require(type(cpu) is int, "pinned Harbor task CPU field requires integer")
    lines = [
        'schema_version = "1.4"',
        '[agent]', 'network_mode = "no-network"',
        'timeout_sec = ' + repr(plan["limits"]["seconds"]),
        '[environment]', 'os = "linux"', 'network_mode = "no-network"',
        'docker_image = ' + json.dumps(runtime["image"]),
        'build_timeout_sec = ' + repr(runtime["command_seconds"]),
        'cpus = ' + str(cpu), 'gpus = 0', 'workdir = "/work"',
    ]
    text = "\n".join(lines) + "\n"
    budget.charge(write=4 * len(capsule["instruction"]) + len(text))
    result = {}
    for name, body in (("instruction.md", capsule["instruction"].encode("utf-8")),
                       ("task.toml", text.encode("utf-8"))):
        descriptor = _pin_body(root / name, body, budget)
        result[name] = {k: descriptor[k] for k in ("bytes", "sha256")}
    return result


def _mount(source, target, readonly=False):
    return {"type": "bind", "source": str(source), "target": target,
            "read_only": readonly, "bind": {"create_host_path": False}}


def _policy(plan, arm, paths, runtime, owned, budget):
    logs = Path(paths["logs"])
    trial = logs / "trials" / plan["trials"][arm]
    mounts = [_mount(paths["view"], "/inputs", True),
              _mount(paths["work"], "/work"), _mount(paths["output"], "/output"),
              _mount(trial / "agent", "/logs/agent"),
              _mount(trial / "verifier", "/logs/verifier"),
              _mount(trial / "artifacts" / "logs" / "artifacts", "/logs/artifacts")]
    # These last three finite paths are created by the pinned Trial constructor;
    # its private logs/host-private sibling is never mounted in the container.
    policy = {
        "docker_path": runtime["docker"]["path"], "docker_host": runtime["docker_host"],
        "docker_env": {"PATH": "/usr/bin:/bin", "HOME": str(logs / "host-private"),
                       "DOCKER_CONFIG": str(logs / "host-private" / "docker-config")},
        "compose_project": plan["trials"][arm] + "__env",
        "compose_file": None, "image_id": runtime["image"],
        "image_environment": runtime["image_env"], "keepalive_argv": runtime["keepalive_argv"],
        "docker_cgroup_parent": str(owned.scope.path.relative_to("/sys/fs/cgroup")),
        "container_user": str(runtime["container_uid"]) + ":" + str(runtime["container_gid"]),
        "cpu_count": plan["limits"]["cpu"], "memory_bytes": plan["limits"]["ram_bytes"],
        "memory_swap_bytes": plan["limits"]["ram_bytes"], "pids_limit": plan["limits"]["pids"],
        "mounts": mounts, "tmpfs_bytes": runtime["container_tmpfs_bytes"],
        "container_environment": runtime["container_environment"],
        "lifecycle_read_bytes": runtime["lifecycle_read_bytes"],
        "lifecycle_write_bytes": runtime["lifecycle_write_bytes"],
        "lifecycle_deadline_monotonic": owned.actor_end,
        "cleanup_read_bytes": runtime["cleanup_read_bytes"],
        "cleanup_write_bytes": runtime["cleanup_write_bytes"],
        "cleanup_deadline_monotonic": owned.end,
        "metadata_output_cap": runtime["metadata_output_bytes"],
        "metadata_timeout_seconds": runtime["command_seconds"],
    }
    compose = {"services": {"main": {
        "image": policy["image_id"], "entrypoint": [], "command": policy["keepalive_argv"],
        "network_mode": "none", "cgroup_parent": policy["docker_cgroup_parent"],
        "user": policy["container_user"], "cpus": policy["cpu_count"],
        "mem_limit": policy["memory_bytes"], "memswap_limit": policy["memory_swap_bytes"],
        "pids_limit": policy["pids_limit"], "read_only": True,
        "security_opt": ["no-new-privileges:true"], "cap_drop": ["ALL"], "init": True,
        "logging": {"driver": "none"}, "restart": "no",
        "volumes": mounts, "tmpfs": ["/tmp:rw,nosuid,nodev,size=" + str(policy["tmpfs_bytes"])],
        "environment": policy["container_environment"],
    }}}
    policy["compose_file"] = _metadata(logs / "host-private" / "COMPOSE.json", compose,
                                       budget, runtime["journal_bytes"])
    return policy


def _receipt(path, cap, budget):
    raw = capture(path, cap, budget)
    budget.charge(read=len(raw), write=len(raw))
    value = plain_json(raw)
    s.require(s.canonical(value) == raw, "canonical captured private receipt")
    return {"path": str(path), **s.body_pin(raw)}, value


def _reauth(descriptor, budget, cap):
    s.keys(descriptor, {"path", "bytes", "sha256"})
    s.require(descriptor["bytes"] <= cap, "bounded observed metadata descriptor")
    raw = capture(descriptor["path"], descriptor["bytes"], budget)
    budget.charge(read=len(raw), write=len(raw))
    s.require(s.body_pin(raw) == {k: descriptor[k] for k in ("bytes", "sha256")},
              "actual retained receipt body")
    return plain_json(raw)


def _child_semantics(child, cfg, plan, runtime, budget):
    """Concrete source-defined child/agent/tool joins, no completion boolean API."""
    from . import responses
    # This helper has no Harbor import. The fixed child tool join below is
    # duplicated as data comparisons, not an arbitrary imported validator.
    binding = {"execution_plan_sha256": s.body_pin(s.canonical(plan))["sha256"],
               "arm": cfg["arm"], "trial_id": plan["trials"][cfg["arm"]]}
    s.require(child["schema"] == "tms_figure2b_child_terminal_v1"
              and child["binding"] == binding and child["status"] == "completed"
              and child["errors"] == [] and child["private_grading_performed"] is False
              and child["native_qualification_created"] is False,
              "complete fixed child without authority or grading")
    s.require(child["task_files"] == cfg["task_files"], "actual child task pins")
    s.require(child["bytecode_cache"] == cfg["bytecode_cache"], "actual early child cache observation")
    summary = child["capture_summary"]
    s.require(summary["trial_name"] == binding["trial_id"]
              and summary["exception_info"] is None, "actual framework result without exception")
    agent = child["agent_result"]
    journal_path = Path(cfg["paths"]["logs"]) / "host-private"
    s.require(agent["path"] == str(journal_path / "AGENT_RESULT.json"), "fixed agent journal")
    actual = _reauth({"path": agent["path"], **agent["pin"]}, budget, runtime["journal_bytes"])
    s.require(actual == agent["receipt"], "captured agent result join")
    responses.admit_result(actual, cfg["capsule"], plan["limits"], binding, journal_path, budget)
    s.require(summary["agent_result_raw"]["n_input_tokens"] == actual["observed_input_tokens"]
              and summary["agent_result_raw"]["n_output_tokens"] == actual["observed_output_tokens"],
              "real AgentContext usage")
    activated = child["container_activation"]
    s.require(host_sources.admit_container(activated["inspection"], cfg["terminal_policy"])
              == activated["admitted_projection"], "actual container policy admission")
    cid = activated["inspection"]["Id"]
    journal = child["terminal_journal"]
    s.require(journal["schema"] == "figure_terminal_journal_v1"
              and journal["container_id"] == cid and journal["arm_fatal"] is False
              and journal["container_closed_observed"] is True,
              "same successful bounded terminal transport")
    rows = [x for x in journal["events"] if x["kind"] == "terminal_completed"]
    tools = [(call["number"], i, tool) for call in actual["calls"]
             for i, tool in enumerate(call["tools"])]
    s.require(len(rows) == len(tools) == actual["terminal_calls"]
              and not any(x["kind"] == "terminal_failed" for x in journal["events"]),
              "complete actual model-tool ancestry")
    import base64
    for sequence, ((number, index, tool), observed) in enumerate(zip(tools, rows), 1):
        path = journal_path / (str(number) + ".tool-" + str(index) + ".json")
        value = _reauth({"path": str(path), **tool["result"]}, budget, runtime["journal_bytes"])
        command = tool["arguments"]["command"].encode("utf-8")
        budget.charge(write=len(command))
        s.require(value["schema"] == "figure_terminal_completed_v1"
                  and value["sequence"] == observed["sequence"] == sequence
                  and value["command_sha256"] == observed["command_sha256"]
                  == hashlib.sha256(command).hexdigest(), "exact actual requested command")
        count = 0
        for name in ("stdout", "stderr"):
            encoded = value[name + "_b64"]
            budget.charge(read=len(encoded), write=len(encoded))
            raw = base64.b64decode(encoded, validate=True)
            count += len(raw)
            s.require(s.body_pin(raw) == observed[name]
                      and raw.decode("utf-8", "replace") == value[name], "actual raw terminal stream")
        for key in ("return_code", "raw_output_bytes", "read_reserved_bytes"):
            s.require(type(value[key]) is int and value[key] == observed[key],
                      "actual terminal outcome")
        s.require(count == value["raw_output_bytes"] <= tool["arguments"]["max_output_bytes"],
                  "bounded full output")
    absent = child["container_absence"]
    s.require(absent["schema"] == "figure_terminal_absence_observation_v1"
              and absent["container_id"] == cid
              and absent["compose_project"] == cfg["terminal_policy"]["compose_project"]
              and absent["docker_host"] == runtime["docker_host"] and len(absent["queries"]) == 2,
              "independent same-container absence queries")
    expected_args = [["ps", "-aq", "--no-trunc", "--filter", "id=" + cid],
                     ["ps", "-aq", "--no-trunc", "--filter",
                      "label=com.docker.compose.project=" + absent["compose_project"]]]
    for row, argv in zip(absent["queries"], expected_args):
        s.require(row["argv_suffix"] == argv and row["return_code"] == 0
                  and row["stdout"] == s.body_pin(b""), "actual empty exact-ID/project query")
    return binding


def run_arm(plan, arm, paths, runtime, budget):
    """Run one concrete selected arm; success returns only root-sealed evidence."""
    s.exact_budget(budget); s.execution_plan(plan); host_sources.runtime_shape(runtime, plan)
    s.require(arm in ("A", "B") and paths == runtime["arm_paths"][arm], "fixed arm paths")
    s.require(os.uname().sysname == "Linux" and os.geteuid() == 0, "Linux root host owner")
    from .qualification import admit_qualification
    qualification = admit_qualification(plan, runtime, budget)
    sources = host_sources.admit(plan, runtime, budget)
    capsule = s.load(Path(runtime["stage_root"]) / "CAPSULE.json", plan["capsule"], budget,
                     cap=runtime["journal_bytes"])
    s.capsule(capsule)
    python = capture(runtime["python"]["path"], runtime["python"]["bytes"], budget)
    s.require(s.body_pin(python) == {k: runtime["python"][k] for k in ("bytes", "sha256")}
              and os.access(runtime["python"]["path"], os.X_OK), "exact selected Python executable")
    private = _empty_root(paths["private"], 0, 0o700)
    bytecode_cache = _create_cache_prefix(runtime, arm, budget)
    storage_paths = {k: paths[k] for k in ("work", "output", "logs")}
    storage_policy = host_sources.storage_limits(plan, runtime)
    before = admit_storage(storage_paths, storage_policy, budget)
    for key in ("work", "output", "logs"):
        _empty_root(paths[key])
    for key in ("work", "output"):
        s.require(runtime["storage_access"][key]["candidate_uid"] == runtime["container_uid"]
                  and runtime["storage_access"][key]["candidate_gids"] == [runtime["container_gid"]]
                  and runtime["storage_access"][key]["candidate_access"] == "write", "candidate tmpfs policy")
    s.require(runtime["storage_access"]["logs"]["candidate_access"] == "none",
              "private host logs never accessible as a whole")
    logs = Path(paths["logs"])
    logstat = logs.stat()
    hostgroups = set(runtime["supplementary_gids"]) | {runtime["host_gid"]}
    hostbits = ((logstat.st_mode >> 6) & 7 if logstat.st_uid == runtime["host_uid"] else
                (logstat.st_mode >> 3) & 7 if logstat.st_gid in hostgroups else logstat.st_mode & 7)
    s.require(hostbits & 3 == 3, "actual unprivileged controller log-root access")
    _mkdir(logs / "host-private", runtime["host_uid"], runtime["host_gid"], 0o700)
    _mkdir(logs / "host-private" / "docker-config", runtime["host_uid"], runtime["host_gid"], 0o700)
    _mkdir(logs / "trials", runtime["host_uid"], runtime["host_gid"], 0o700)
    # Each complete child allocation is charged once before any child code.
    budget.charge(read=runtime["child_read_bytes"], write=runtime["child_write_bytes"])
    reservation = atomic(private, "CHILD_RESERVATION.json", {
        "schema": "tms_figure2b_child_reservation_v1", "arm": arm,
        "read_bytes": runtime["child_read_bytes"], "write_bytes": runtime["child_write_bytes"],
        "refunded": False, "caller_deadline_monotonic": budget.deadline}, budget)
    owned = OwnedHost(runtime, plan, arm, private, None, bytecode_cache, budget)
    commands = DockerCommands(runtime, private, budget, owned.actor_end)
    errors = FailureCarrier()
    state = {"schema": "tms_figure2b_host_arm_v1", "execution_plan": s.body_pin(s.canonical(plan)),
             "arm": arm, "trial_id": plan["trials"][arm], "runtime": plan["runtime"],
             "view": plan["views"][arm], "capsule": plan["capsule"],
             "bytecode_cache": bytecode_cache,
             "qualification": qualification, "source_admission": sources,
             "storage_before": before, "storage_after": None, "preflight": None,
             "owned_host": None, "child_configuration": None, "child_terminal": None,
             "container_observations": None, "costs": None, "status": "failed"}
    cfg = None
    project = plan["trials"][arm] + "__env"
    first = None
    try:
        commands.admit_executable()
        state["preflight"] = commands.preflight(project)
        owned.create_scope()
        task_files = _task(plan, paths, runtime, capsule, budget)
        policy = _policy(plan, arm, paths, runtime, owned, budget)
        binding = {"execution_plan_sha256": state["execution_plan"]["sha256"],
                   "arm": arm, "trial_id": plan["trials"][arm]}
        agent_config = {"schema": "tms_figure2b_agent_configuration_v1", "binding": binding,
                        "capsule": capsule, "limits": plan["limits"],
                        "credential": runtime["credential"], "journal": str(logs / "host-private")}
        operator_configuration = _metadata(logs / "host-private" / "AGENT_CONFIGURATION.json",
                                            agent_config, budget, runtime["journal_bytes"])
        cfg = {"schema": "tms_figure2b_host_child_v1", "plan": plan, "runtime": runtime,
               "arm": arm, "paths": paths, "capsule": capsule,
               "operator_configuration": operator_configuration, "task_files": task_files,
               "bytecode_cache": bytecode_cache,
               "terminal_policy": policy, "accounting_parent": reservation,
               "deadline": owned.actor_end, "read_bytes": runtime["child_read_bytes"],
               "write_bytes": runtime["child_write_bytes"],
               "close_read_bytes": runtime["child_receipt_read_bytes"],
               "close_write_bytes": runtime["child_receipt_write_bytes"], "close_deadline": owned.end}
        descriptor = _metadata(logs / "host-private" / "CHILD_CONFIGURATION.json", cfg,
                               budget, runtime["journal_bytes"])
        owned.child_configuration = descriptor
        state["child_configuration"] = descriptor
        owned.launch()
        owned.wait()
    except BaseException as error:
        first = error; errors.fail(error, "owned-arm")
    finally:
        # Independent cleanup allowances survive investigation exhaustion. Stop
        # the host actor first so it cannot issue another container/model request.
        try:
            owned.stop_host()
        except BaseException as error:
            errors.fail(error, "host-stop")
            if first is None: first = error
        commands.budget = owned.cleanup_budget
        commands.deadline = owned.end  # Only retirement may use the original cleanup interval.
        try:
            if commands.executable_identity is not None and state["preflight"] is not None:
                state["container_observations"] = commands.retire(project)
        except BaseException as error:
            errors.fail(error, "container-retirement")
            if first is None: first = error
        if owned.scope.created:
            try:
                # A successful child also requires the complete accounting parent
                # to empty; setsid descendants cannot escape this cgroup boundary.
                owned.finish_scope()
            except BaseException as error:
                errors.fail(error, "cgroup-close")
                if first is None: first = error
                try:
                    owned.recover_scope()
                except BaseException as second:
                    errors.fail(second, "failed-scope-recovery-not-run-success")
        state["owned_host"] = owned.record
    if first is None:
        try:
            descriptor, child = _receipt(logs / "host-private" / "CHILD_TERMINAL.json",
                                          runtime["journal_bytes"], budget)
            s.require(child["configuration"] == {k: state["child_configuration"][k]
                                                  for k in ("bytes", "sha256")}, "child configuration pin")
            _child_semantics(child, cfg, plan, runtime, budget)
            state["child_terminal"] = {"descriptor": descriptor, "value": child}
            state["storage_after"] = recheck_storage(before, storage_paths, storage_policy, budget)
            state["status"] = "closed_ungraded"
        except BaseException as error:
            first = error; errors.fail(error, "terminal-admission")
    state["costs"] = {"read_limit": budget.read_limit, "write_limit": budget.write_limit,
                      "reads_before_publication": budget.reads, "writes_before_publication": budget.writes,
                      "deadline_monotonic": budget.deadline,
                      "child_reservation": reservation, "host_cleanup_reservation": {
                          "read": runtime["cleanup_read_bytes"], "write": runtime["cleanup_write_bytes"]},
                      "includes_all_Harbor_or_kernel_IO": False}
    if first is not None:
        # The first real exception survives publication/cleanup errors. No failed
        # record can become a passing closed record through a caller flag.
        try:
            state["failure_types"] = [type(first).__name__]
            atomic(private, "FAILED.json", state, owned.cleanup_budget)
        except BaseException as publication:
            errors.fail(publication, "failure-publication")
        raise HostOwnershipFailure(errors, state) from first
    receipt = atomic(private, "CLOSED.json", state, budget)
    budget.charge()
    return {"schema": "tms_figure2b_closed_host_envelope_v1", "receipt": receipt,
            "arm": arm, "trial_id": plan["trials"][arm], "status": "closed_ungraded"}


def admit_closed(record, plan, arm, paths, runtime, budget):
    """Reauthenticate root-custodied actual closure; never launches or grades.

    These receipts are observations from the fixed run above, not cryptographic
    attestation against a hostile host root. External qualification/custody is
    still required. Re-reading cannot independently certify provider internals.
    """
    s.exact_budget(budget); s.execution_plan(plan); host_sources.runtime_shape(runtime, plan)
    s.require(arm in ("A", "B") and paths == runtime["arm_paths"][arm], "selected arm")
    s.keys(record, {"schema", "receipt", "arm", "trial_id", "status"})
    s.require(record["schema"] == "tms_figure2b_closed_host_envelope_v1"
              and record["arm"] == arm and record["trial_id"] == plan["trials"][arm]
              and record["status"] == "closed_ungraded", "actual closure envelope")
    private = absolute(paths["private"], True)
    s.require(private.stat().st_uid == 0 and stat.S_IMODE(private.stat().st_mode) == 0o700,
              "independently custodied root journal")
    receipt = record["receipt"]
    s.require(receipt["path"] == str(private / "CLOSED.json"), "fixed original closed receipt")
    info = absolute(receipt["path"]).stat()
    s.require(info.st_uid == 0 and stat.S_IMODE(info.st_mode) == 0o400,
              "sealed original root-only closure body")
    state = _reauth(receipt, budget, runtime["journal_bytes"])
    from .qualification import admit_qualification
    s.require(state["qualification"] == admit_qualification(plan, runtime, budget),
              "same external assessment operands")
    s.require(state["source_admission"] == host_sources.admit(plan, runtime, budget),
              "same complete source chain")
    s.require(state["schema"] == "tms_figure2b_host_arm_v1"
              and state["execution_plan"] == s.body_pin(s.canonical(plan))
              and state["arm"] == arm and state["trial_id"] == plan["trials"][arm]
              and state["runtime"] == plan["runtime"] and state["view"] == plan["views"][arm]
              and state["capsule"] == plan["capsule"] and state["status"] == "closed_ungraded",
              "exact pre-release plan and selected arm closure")
    owned = state["owned_host"]
    intent = _reauth(owned["intent"], budget, runtime["journal_bytes"])
    owner = _reauth(owned["owner"], budget, runtime["journal_bytes"])
    gate = _reauth(owned["gate"], budget, runtime["journal_bytes"])
    completion = _reauth({k: owned["completion"][k] for k in ("path", "bytes", "sha256")},
                          budget, runtime["journal_bytes"])
    s.require(intent["token"] == owner["token"] == owned["token"] == gate["token"]
              == completion["token"] and gate["activate"] is True
              and completion == owned["completion"]["value"]
              and completion["natural_wait"] is True and completion["returncode"] == 0
              and owner["bootstrap"]["pid"] == owned["bootstrap"]["pid"]
              == owned["host_group"]["pid"] and owned["host_group"]["reaped"] is True
              and owned["host_group"]["group_absent"] is True
              and owned["host_group"]["streams_closed"] is True,
              "actual token-bound initialized owner and naturally completed child")
    s.require(owned["cgroup"]["complete"] is True and owned["cgroup"]["populated"] is False
              and owned["cgroup"]["cpu_complete"] is True
              and 0 <= owned["cgroup"]["cpu_seconds"] <= plan["limits"]["cpu"] * plan["limits"]["seconds"]
              and not Path(owned["host_leaf"]["path"]).parent.exists(),
              "closed original complete accounting subtree and CPU counter")
    commands = state["container_observations"]
    s.require(commands["schema"] == "tms_figure2b_docker_absence_v1"
              and commands["project"] == plan["trials"][arm] + "__env"
              and commands["containers_stdout"] == commands["networks_stdout"] == "",
              "actual owned project absence")
    for descriptor in commands["command_receipts"]:
        row = _reauth(descriptor, budget, runtime["journal_bytes"])
        process = row["process"]
        s.require(row["error_type"] is None and process["natural_exit"] is True
                  and process["exit_code"] == 0 and process["process_reaped"] is True
                  and process["process_group_absent"] is True and process["streams_closed"] is True,
                  "actual bounded metadata child closure")
    cfg = _reauth(state["child_configuration"], budget, runtime["journal_bytes"])
    s.require(cfg["plan"] == plan and cfg["runtime"] == runtime and cfg["paths"] == paths
              and cfg["accounting_parent"] == state["costs"]["child_reservation"],
              "fixed child source/configuration/reservation joins")
    s.require(state["bytecode_cache"] == cfg["bytecode_cache"] == owner["bytecode_cache"]
              == _cache_identity(runtime, arm, budget), "same actual isolated cache-prefix identity")
    child = _reauth(state["child_terminal"]["descriptor"], budget, runtime["journal_bytes"])
    s.require(child == state["child_terminal"]["value"], "unchanged full child terminal record")
    _child_semantics(child, cfg, plan, runtime, budget)
    # Fresh storage identity/capacity observation also protects delayed capture;
    # it is an actual kernel metadata operation, not an actor launch.
    after = recheck_storage(state["storage_before"], {k: paths[k] for k in ("work", "output", "logs")},
                            host_sources.storage_limits(plan, runtime), budget)
    s.require(after["prior_observation_pin"] == state["storage_before"]["pin"],
              "same actual storage custody")
    budget.charge()
    return state
