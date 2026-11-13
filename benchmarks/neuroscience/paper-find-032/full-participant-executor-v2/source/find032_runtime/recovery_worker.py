"""Fixed FIND032 daemon retirement child. No scientific operation is available."""
import argparse
import hashlib
import importlib.util
import json
import os
import math
import stat
from pathlib import Path
import sys
import time

HERE = Path(__file__).absolute().parent


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


SOURCE_ATTEMPTS = []
REQUEST_ATTEMPT = {"raw": bytearray(), "errors": [], "closed": False}
RECOVERY_DEADLINE = None


def ordinary_fd(path, attempt):
    value = str(path)
    need(value.startswith("/") and os.path.normpath(value) == value and "\x00" not in value,
         "absolute-original-source-path")
    current = None
    fd = None
    first = None
    try:
        current = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        attempt["descriptors"].append(current)
        parts = value.split("/")[1:]
        for part in parts[:-1]:
            new = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
            attempt["descriptors"].append(new)
            old = current
            current = new
            os.close(old)
            attempt["closed"].append(old)
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=current)
        attempt["descriptors"].append(fd)
    except BaseException as error:
        first = error
        attempt["errors"].append(error)
    finally:
        if current is not None:
            try:
                os.close(current)
                attempt["closed"].append(current)
            except BaseException as error:
                attempt["errors"].append(error)
                if first is None:
                    first = error
        if first is not None and fd is not None:
            try:
                os.close(fd)
                attempt["closed"].append(fd)
            except BaseException as error:
                attempt["errors"].append(error)
    if first is not None:
        raise first
    return fd


def read_selected(path, expected, retain):
    need(type(expected) is dict and set(expected) == {"bytes", "sha256"} and
         type(expected["bytes"]) is int and expected["bytes"] > 0 and
         type(expected["sha256"]) is str and len(expected["sha256"]) == 64 and
         all(c in "0123456789abcdef" for c in expected["sha256"]), "exact-original-source-pin")
    need(len(SOURCE_ATTEMPTS) < 3, "fixed-two-source-and-one-executable-captures")
    attempt = {"path": str(path), "descriptors": [], "closed": [], "errors": [], "blocks": []}
    SOURCE_ATTEMPTS.append(attempt)
    need(type(RECOVERY_DEADLINE) in (int, float) and time.monotonic() < RECOVERY_DEADLINE,
         "original-recovery-source-clock")
    fd = None
    h = hashlib.sha256()
    total = 0
    first = None
    try:
        fd = ordinary_fd(path, attempt)
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
             before.st_size == expected["bytes"], "ordinary-complete-source-body")
        while total <= expected["bytes"]:
            need(time.monotonic() < RECOVERY_DEADLINE, "original-recovery-source-read-cutoff")
            block = os.read(fd, min(65536, expected["bytes"] + 1 - total))
            if not block:
                break
            total += len(block)
            h.update(block)
            if retain:
                attempt["blocks"].append(block)
        after = os.fstat(fd)
        fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "st_mode", "st_nlink")
        need(all(getattr(before, k) == getattr(after, k) for k in fields) and
             {"bytes": total, "sha256": h.hexdigest()} == expected, "same-captured-source-body")
    except BaseException as error:
        first = error
        attempt["errors"].append(error)
    finally:
        if fd is not None:
            try:
                os.close(fd)
                attempt["closed"].append(fd)
            except BaseException as error:
                attempt["errors"].append(error)
                if first is None:
                    first = error
    if first is not None:
        raise first
    return b"".join(attempt["blocks"]) if retain else None


def selected_source(path, expected):
    need(expected["bytes"] <= 2 * 1024 * 1024, "ordinary-source-member-bound")
    return read_selected(path, expected, True)


def selected_executable(path, expected):
    read_selected(path, expected, False)
    need(os.access(path, os.X_OK), "selected-docker-executable")


def guard_cache():
    need(sys.flags.isolated == 1 and sys.flags.no_site == 1 and
         sys.flags.dont_write_bytecode == 1 and type(sys.pycache_prefix) is str and
         sys._xoptions.get("pycache_prefix") == sys.pycache_prefix,
         "actual-isolated-no-site-fresh-cache-startup")
    p = Path(sys.pycache_prefix)
    need(p.is_absolute() and p.name == "bytecode-cache" and
         all(not ancestor.is_symlink() for ancestor in (p, *p.parents)),
         "explicit-private-cache-ancestry")
    st = p.lstat()
    need(stat.S_ISDIR(st.st_mode) and st.st_uid == 0 and
         stat.S_IMODE(st.st_mode) == 0o550, "root-owned-readonly-cache")
    with os.scandir(p) as entries:
        need(next(entries, None) is None, "empty-selected-cache")


def read_request(fd):
    raw = REQUEST_ATTEMPT["raw"]
    result = None
    first = None
    try:
        while len(raw) <= 4096:
            part = os.read(fd, 4097 - len(raw))
            if not part:
                break
            raw.extend(part)
        need(0 < len(raw) <= 4096, "one-bounded-original-recovery-request")
        def pairs(rows):
            result = {}
            for key, value in rows:
                need(key not in result, "duplicate-recovery-key")
                result[key] = value
            return result
        result = json.loads(raw, object_pairs_hook=pairs,
                            parse_constant=lambda _: need(False, "finite-recovery-json"))
    except BaseException as error:
        first = error
        REQUEST_ATTEMPT["errors"].append(error)
    finally:
        try:
            os.close(fd)
            REQUEST_ATTEMPT["closed"] = True
        except BaseException as error:
            REQUEST_ATTEMPT["errors"].append(error)
            if first is None:
                first = error
    if first is not None:
        raise first
    return result


def recover(request):
    global RECOVERY_DEADLINE
    need(type(request) is dict and set(request) == {
        "schema", "rows", "docker", "socket", "docker_pin", "executor_pin", "deadline",
        "failure_source_pin", "failure_directory", "failure_byte_cap", "docker_config"},
        "fixed-recovery-request")
    need(request["schema"] == "find032_original_daemon_recovery_v1" and
         type(request["rows"]) is list and len(request["rows"]) <= 6 and
         type(request["deadline"]) in (int, float) and math.isfinite(request["deadline"]) and
         time.monotonic() < request["deadline"], "original-recovery-interval")
    RECOVERY_DEADLINE = request["deadline"]
    cfg = request["docker_config"]
    need(type(cfg) is dict and set(cfg) == {"path", "device", "inode", "uid", "gid", "mode"},
         "exact parent-created recovery configuration")
    config_path = Path(cfg["path"])
    need(config_path.is_absolute() and os.path.normpath(str(config_path)) == str(config_path) and
         not any(p.is_symlink() for p in (config_path, *config_path.parents)),
         "unlinked original recovery configuration")
    config_state = config_path.lstat()
    need(stat.S_ISDIR(config_state.st_mode) and config_state.st_uid == cfg["uid"] == 0 and
         stat.S_IMODE(config_state.st_mode) == cfg["mode"] == 0o700 and
         config_state.st_gid == cfg["gid"] and config_state.st_dev == cfg["device"] and
         config_state.st_ino == cfg["inode"], "same original private recovery configuration")
    with os.scandir(config_path) as entries:
        need(next(entries, None) is None, "no ambient recovery Docker configuration")
    rows = request["rows"]
    need(all(type(row) is dict for row in rows) and
         len({row["name"] for row in rows}) == len(rows),
         "known-unique-original-resource-rows")
    source = HERE / "docker_transport.py"
    raw = selected_source(source, request["executor_pin"])
    need({"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()} ==
         request["executor_pin"], "exact-original-retirement-source")
    specification = importlib.util.spec_from_file_location("_find032_recovery_executor", source)
    module = importlib.util.module_from_spec(specification)
    # Execute the exact already-captured body, without a second import read.
    exec(compile(raw, str(source), "exec"), module.__dict__)
    failure_source = HERE / "failure_evidence.py"
    failure_raw = selected_source(failure_source, request["failure_source_pin"])
    need({"bytes": len(failure_raw), "sha256": hashlib.sha256(failure_raw).hexdigest()} ==
         request["failure_source_pin"], "exact-original-failure-evidence-source")
    specification = importlib.util.spec_from_file_location("_find032_recovery_failure", failure_source)
    failure_module = importlib.util.module_from_spec(specification)
    exec(compile(failure_raw, str(failure_source), "exec"), failure_module.__dict__)
    need(request["failure_byte_cap"] == 1048576, "precharged-original-recovery-evidence")
    if rows:
        selected_executable(request["docker"], request["docker_pin"])
    docker = module.Docker(request["docker"], request["socket"]) if rows else None
    if docker is not None:
        docker.env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "DOCKER_CONFIG": str(config_path)}
    results, original_errors = [], []
    # Exactly one independent retirement per known obligation; containers first.
    ordered = sorted(enumerate(rows), key=lambda item:
                     (item[1]["kind"] == "volume", -item[0]))
    for original_index, row in ordered:
        try:
            need(time.monotonic() < request["deadline"], "same-original-recovery-cutoff")
            result = module.retire(docker, row, request["deadline"])
        except BaseException as error:
            original_errors.append(error)  # Keep raw objects through all independent cleanup.
            result = {"kind": row["kind"], "name": row["name"], "closed": False,
                      "error_type": type(error).__name__}
        results.append({"original_index": original_index, "resource": row, "result": result})
    retirement_error_evidence = None
    try:
        retirement_error_evidence = failure_module.describe_original_errors(original_errors)
    except BaseException as error:
        original_errors.append(error)
    original_evidence = None
    if docker is not None and docker.original_failures:
        try:
            original_evidence = failure_module.persist(request["failure_directory"],
                docker.original_failures, request["failure_byte_cap"], request["deadline"])
            original_errors.extend(original_evidence["publication_errors"])
        except BaseException as error:
            original_errors.append(error)
    summary = {"schema": "find032_original_daemon_recovery_result_v1",
            "results": results, "commands": [] if docker is None else docker.records,
            "cli_groups_closed": True if docker is None else docker.reaped,
            "original_error_types": [type(x).__name__ for x in original_errors],
            "original_command_evidence": (None if original_evidence is None else
                                          original_evidence["summary"]),
            "original_retirement_error_evidence": retirement_error_evidence,
            "study_failure_unchanged": True, "automatic_retry": False,
            "runtime_or_scientific_qualification_added": False}
    # Retain these originals through serialization/flushing in main. Only the
    # bounded summary crosses the process boundary.
    return {"summary": summary, "original_errors": tuple(original_errors),
            "original_evidence": original_evidence, "docker": docker}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request-fd", type=int, required=True)
    args = parser.parse_args()
    guard_cache()
    held = recover(read_request(args.request_fd))
    raw = (json.dumps(held["summary"], sort_keys=True, separators=(",", ":"),
                      allow_nan=False) + "\n").encode()
    need(len(raw) <= 65536, "original-recovery-result-cap")
    sys.stdout.buffer.write(raw)
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()

