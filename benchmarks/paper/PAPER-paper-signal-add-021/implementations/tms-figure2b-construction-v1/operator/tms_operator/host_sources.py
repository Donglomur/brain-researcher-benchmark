"""Closed source/runtime admission and actual-container comparisons; no native launch."""
import hashlib
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
from .schema import (canonical, body_pin, load, exact_budget, require, keys,
                     integer, positive, execution_plan)
from .host_process import capture, plain_json

PATH_KEYS = {"operator_root", "view", "task", "private", "work", "output", "logs"}
RUNTIME_KEYS = {
    "schema", "stage_root", "arm_paths", "python", "docker", "harbor_root", "harbor_files",
    "image", "image_env", "architecture", "daemon_id", "docker_host", "cgroup_root",
    "host_uid", "host_gid", "supplementary_gids", "container_uid", "container_gid",
    "credential", "command_seconds", "metadata_output_bytes", "journal_bytes",
    "host_read_bytes", "host_write_bytes", "cleanup_read_bytes", "cleanup_write_bytes",
    "child_read_bytes", "child_write_bytes", "lifecycle_read_bytes", "lifecycle_write_bytes",
    "child_receipt_read_bytes", "child_receipt_write_bytes",
    "container_tmpfs_bytes", "container_environment", "keepalive_argv",
    "mountinfo_max_bytes", "storage_access",
}
CRITICAL = {
    "tms_operator/host.py", "tms_operator/host_child.py", "tms_operator/host_bootstrap.py",
    "tms_operator/host_process.py", "tms_operator/host_sources.py",
    "tms_operator/host_cli.py", "tms_operator/qualification.py",
    "tms_operator/host_support/cgroup.py", "tms_operator/host_support/process.py",
    "tms_operator/host_support/common.py", "tms_operator/host_support/__init__.py",
    "tms_operator/terminal.py", "tms_operator/capture_trial.py", "tms_operator/storage.py",
    "tms_operator/agent.py", "tms_operator/responses.py", "tms_operator/schema.py",
    "tms_operator/HARBOR_LOCK.json",
}


def relative(name):
    require(type(name) is str and name and "\\" not in name
            and not any(ord(c) < 32 for c in name), "relative source path")
    p = PurePosixPath(name)
    require(not p.is_absolute() and str(p) == name and ".." not in p.parts,
            "canonical confined source path")
    return p


def absolute(value):
    require(type(value) is str and Path(value).is_absolute()
            and value == os.path.normpath(value), "literal absolute runtime path")
    require(not any(c in value for c in ("\0", "\r", "\n", ",")), "unambiguous runtime path")
    return Path(value)


def runtime_shape(runtime, plan):
    keys(runtime, RUNTIME_KEYS)
    require(runtime["schema"] == "tms_linux_harbor_runtime_v1", "fixed Linux Harbor runtime")
    keys(runtime["arm_paths"], {"A", "B"})
    stage = absolute(runtime["stage_root"])
    for arm in ("A", "B"):
        paths = runtime["arm_paths"][arm]
        keys(paths, PATH_KEYS)
        for value in paths.values():
            absolute(value)
        require(Path(paths["view"]) == stage / "views" / arm, "exact staged arm view")
        for key in ("task", "private", "work", "output", "logs"):
            require(paths[key] != runtime["arm_paths"]["B" if arm == "A" else "A"][key],
                    "independent arm custody")
        for i, a in enumerate(("view", "task", "private", "work", "output", "logs")):
            for b in ("view", "task", "private", "work", "output", "logs")[i + 1:]:
                pa, pb = Path(paths[a]), Path(paths[b])
                require(not pa.is_relative_to(pb) and not pb.is_relative_to(pa),
                        "disjoint selected arm roots")
    require(runtime["arm_paths"]["A"]["operator_root"] ==
            runtime["arm_paths"]["B"]["operator_root"], "shared exact source package")
    for key in ("python", "docker"):
        d = runtime[key]
        keys(d, {"path", "bytes", "sha256"})
        absolute(d["path"]); integer(d["bytes"])
        require(type(d["sha256"]) is str and re.fullmatch("[a-f0-9]{64}", d["sha256"]),
                "selected executable SHA")
    for key in ("harbor_root", "cgroup_root"):
        absolute(runtime[key])
    require(type(runtime["harbor_files"]) is dict and runtime["harbor_files"], "exact Harbor closure")
    require(type(runtime["image"]) is str and re.fullmatch("sha256:[a-f0-9]{64}", runtime["image"]),
            "immutable image identity")
    require(runtime["architecture"] in ("amd64", "arm64"), "selected image architecture")
    require(type(runtime["daemon_id"]) is str and 0 < len(runtime["daemon_id"]) <= 128,
            "selected local daemon identity")
    require(type(runtime["docker_host"]) is str and runtime["docker_host"].startswith("unix:///"),
            "selected local daemon socket")
    absolute(runtime["docker_host"][7:])
    for key in ("host_uid", "host_gid", "container_uid", "container_gid"):
        integer(runtime[key], 1, 2**32 - 2)
    require(runtime["host_uid"] != runtime["container_uid"]
            and runtime["host_gid"] != runtime["container_gid"],
            "separate trusted host and candidate identities")
    groups = runtime["supplementary_gids"]
    require(type(groups) is list and groups == sorted(set(groups))
            and all(type(x) is int and 0 < x < 2**32 - 1 for x in groups), "explicit host groups")
    for key in ("metadata_output_bytes", "journal_bytes", "host_read_bytes", "host_write_bytes",
                "cleanup_read_bytes", "cleanup_write_bytes", "child_read_bytes", "child_write_bytes",
                "lifecycle_read_bytes", "lifecycle_write_bytes", "container_tmpfs_bytes",
                "child_receipt_read_bytes", "child_receipt_write_bytes",
                "mountinfo_max_bytes"):
        integer(runtime[key])
    positive(runtime["command_seconds"])
    require(runtime["command_seconds"] < plan["limits"]["cleanup_seconds"], "command cleanup horizon")
    require(type(runtime["image_env"]) is list and all(type(x) is str and "=" in x
            and "\0" not in x for x in runtime["image_env"]), "exact image environment")
    require(type(runtime["container_environment"]) is dict
            and all(type(k) is str and type(v) is str and "\0" not in k + v
                    for k, v in runtime["container_environment"].items()),
            "explicit nonsecret container environment")
    require(type(runtime["keepalive_argv"]) is list and runtime["keepalive_argv"]
            and all(type(x) is str and x and "\0" not in x for x in runtime["keepalive_argv"]),
            "selected image keepalive command")
    keys(runtime["credential"], {"path", "device", "inode", "uid", "mode", "bytes", "mtime_ns", "ctime_ns"})
    absolute(runtime["credential"]["path"])
    require(runtime["credential"]["uid"] == runtime["host_uid"], "selected child-readable credential owner")
    require(type(runtime["storage_access"]) is dict, "explicit prepared storage policy")
    return runtime


def storage_limits(plan, runtime):
    return {k: plan["limits"][k] for k in ("work_bytes", "output_bytes", "log_bytes")} | {
        "mountinfo_max_bytes": runtime["mountinfo_max_bytes"], "access": runtime["storage_access"]}


def admit(plan, runtime, budget):
    """Reauthenticate source and staged operand bodies; never issues qualification."""
    exact_budget(budget); execution_plan(plan); runtime_shape(runtime, plan)
    stage = Path(runtime["stage_root"])
    staged_plan = plain_json(capture(stage / "EXECUTION_PLAN.json", runtime["journal_bytes"], budget))
    require(staged_plan == plan, "exact staged pre-release plan")
    for name, descriptor, expected in (
        ("RUNTIME.json", plan["runtime"], runtime),
        ("CAPSULE.json", plan["capsule"], None),
        ("QUALIFICATION.json", plan["qualification"], None),
    ):
        value = load(stage / name, descriptor, budget, cap=runtime["journal_bytes"])
        if expected is not None:
            require(value == expected, "literal staged operand join")
    root = Path(runtime["arm_paths"]["A"]["operator_root"])
    operator = load(root / "OPERATOR_LOCK.json", plan["operator_lock"], budget,
                    cap=runtime["journal_bytes"])
    keys(operator, {"schema", "files", "inherited_source_commit"})
    require(operator["schema"] == "tms_figure2b_operator_source_lock_v1"
            and operator["inherited_source_commit"] == "33986480f8347ce2923bea79319749166e8ae1ae"
            and type(operator["files"]) is dict and CRITICAL <= set(operator["files"]),
            "complete selected operator source lock")
    require("OPERATOR_LOCK.json" not in operator["files"], "no cyclic operator self-pin")
    for name, descriptor in operator["files"].items():
        relative(name)
        raw = capture(root / name, descriptor["bytes"], budget)
        require(body_pin(raw) == descriptor, "exact selected operator member")
    numerical = load(root / "SOURCE_LOCK.json", plan["source_lock"], budget,
                     cap=runtime["journal_bytes"])
    keys(numerical, {"schema", "files"})
    require(numerical["schema"] == "tms_figure2b_source_lock_v1" and type(numerical["files"]) is dict,
            "unchanged numerical source lock")
    for name, descriptor in numerical["files"].items():
        relative(name)
        require(body_pin(capture(root / "tms_figure" / name, descriptor["bytes"], budget)) == descriptor,
                "unchanged numerical module")
    harbor_path = "tms_operator/HARBOR_LOCK.json"
    harbor = load(root / harbor_path, operator["files"][harbor_path], budget,
                  cap=runtime["journal_bytes"])
    keys(harbor, {"schema", "version", "files"})
    require(harbor["schema"] == "tms_figure2b_harbor_source_lock_v1" and harbor["version"] == "0.21.0"
            and harbor["files"] == runtime["harbor_files"], "fixed reviewed Harbor closure")
    harbor_root = Path(runtime["harbor_root"])
    for name, descriptor in harbor["files"].items():
        relative(name)
        require(body_pin(capture(harbor_root / name, descriptor["bytes"], budget)) == descriptor,
                "installed Harbor source bytes")
    return {"operator_lock": plan["operator_lock"], "source_lock": plan["source_lock"],
            "harbor_lock": operator["files"][harbor_path],
            "authenticated_files": len(operator["files"]) + len(numerical["files"]) + len(harbor["files"])}


def admit_container(row, policy):
    """Validate the actual Docker inspect record against the fixed generated policy."""
    require(type(row) is dict and re.fullmatch("[a-f0-9]{64}", row.get("Id", "")),
            "actual exact container ID")
    cfg, host = row["Config"], row["HostConfig"]
    require(row["Image"] == policy["image_id"] and cfg["Image"] == policy["image_id"]
            and cfg["Labels"]["com.docker.compose.project"] == policy["compose_project"]
            and cfg["Labels"]["com.docker.compose.service"] == "main", "actual selected image/owner/service")
    require(cfg["User"] == policy["container_user"] and cfg.get("Entrypoint") in (None, [])
            and cfg["Cmd"] == policy["keepalive_argv"], "actual selected process/user")
    expected_env = {}
    for value in policy["image_environment"]:
        key, text = value.split("=", 1)
        require(key not in expected_env, "unique image environment")
        expected_env[key] = text
    expected_env.update(policy["container_environment"])
    actual_env = {}
    for value in cfg.get("Env") or []:
        key, text = value.split("=", 1)
        require(key not in actual_env, "unique actual environment")
        actual_env[key] = text
    require(actual_env == expected_env, "actual closed container environment")
    require(host["NetworkMode"] == "none" and host["ReadonlyRootfs"] is True
            and host["Privileged"] is False and not host.get("CapAdd")
            and host["CapDrop"] == ["ALL"] and host.get("PidMode", "") != "host"
            and host.get("IpcMode", "") != "host", "actual privilege and network boundary")
    require(host["SecurityOpt"] in (["no-new-privileges"], ["no-new-privileges:true"]),
            "actual no-new-privileges")
    require(host["LogConfig"]["Type"] == "none"
            and host["RestartPolicy"]["Name"] == "no", "no daemon log growth or restart actor")
    require(host["CgroupParent"] == policy["docker_cgroup_parent"], "actual owned accounting parent")
    require(host["Memory"] == policy["memory_bytes"] and
            host["MemorySwap"] == policy["memory_swap_bytes"] and
            host["PidsLimit"] == policy["pids_limit"], "actual memory/swap/PID limits")
    want_cpu = policy["cpu_count"] * 1_000_000_000
    require(host.get("NanoCpus") == want_cpu or
            (host.get("CpuPeriod", 0) > 0 and
             host.get("CpuQuota") == host["CpuPeriod"] * policy["cpu_count"]),
            "actual CPU limit")
    expected = {m["target"]: (m["source"], not m["read_only"]) for m in policy["mounts"]}
    observed = {}
    for mount in row["Mounts"]:
        if mount["Type"] == "tmpfs":
            require(mount["Destination"] == "/tmp", "only selected temporary mount")
            continue
        require(mount["Type"] == "bind" and mount["Destination"] not in observed,
                "ordinary unique bind mounts only")
        observed[mount["Destination"]] = (mount["Source"], mount["RW"])
    require(observed == expected and expected["/inputs"][1] is False, "exact candidate visibility")
    require(not host.get("Devices") and not host.get("DeviceRequests") and not host.get("PortBindings")
            and not cfg.get("Volumes"), "no implicit devices/ports/volumes")
    require(not cfg.get("Healthcheck") or cfg["Healthcheck"].get("Test") == ["NONE"],
            "no unselected healthcheck producer")
    require(row["State"]["Running"] is True and not row["State"].get("OOMKilled", False),
            "observed live candidate before model phase")
    return {"container_id": row["Id"], "compose_project": policy["compose_project"],
            "image": row["Image"], "user": cfg["User"], "mounts": row["Mounts"],
            "host_config": host, "state": row["State"], "config": cfg}
