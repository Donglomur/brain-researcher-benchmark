"""Linux-only fixed-source Horrocks engineering owner; no scientific execution.

No arbitrary command is accepted. prepare/finish run on the CI host; inner runs
as UID/GID65534 PID1 in a new network/PID namespace with no capabilities.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import selectors
import signal
import stat
import subprocess
import sys
import time

TOTAL_BYTES = 2 * 1024 * 1024
ATTEMPT_SECONDS = 30.0
CLOSURE_SECONDS = 5.0
PYTHON_VERSION = (3, 11, 18)


def require(value, message):
    if not value:
        raise RuntimeError(message)


def encode(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def put(path, value):
    with path.open("xb") as stream:
        stream.write(encode(value))


def inventory(root):
    rows = []
    total = 0
    for parent, directories, names in os.walk(root, followlinks=False):
        for name in directories + names:
            path = Path(parent) / name
            meta = path.lstat()
            relative = str(path.relative_to(root))
            if stat.S_ISREG(meta.st_mode):
                total += meta.st_size
                rows.append({"path": relative, "kind": "regular", "bytes": meta.st_size})
            elif stat.S_ISLNK(meta.st_mode):
                # The unchanged Horrocks harness intentionally creates a test symlink.
                target = os.readlink(path)
                total += len(os.fsencode(target))
                rows.append({"path": relative, "kind": "synthetic_symlink",
                             "target": target, "bytes": len(os.fsencode(target))})
            elif not stat.S_ISDIR(meta.st_mode):
                raise RuntimeError("nonordinary scratch object")
    return total, sorted(rows, key=lambda row: row["path"])


def group_present(pgid):
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    return True


def execute_one(name, argv, root, start, deadline, library_dir):
    directory = root / name
    directory.mkdir()
    require(type(start) is float and type(deadline) is float and math.isfinite(start)
            and math.isfinite(deadline) and 0 < start <= time.monotonic() < deadline
            and deadline == start + ATTEMPT_SECONDS, "original absolute deadline")
    request = {"argv": argv, "cwd": str(directory), "environment": {
        "PATH": "/usr/bin:/bin", "LANG": "C.UTF-8",
        "LD_LIBRARY_PATH": library_dir},
        "start_monotonic": start, "absolute_deadline": deadline,
        "attempt_seconds": ATTEMPT_SECONDS, "whole_packet_byte_cap": TOTAL_BYTES,
        "fixture_identity": "EXPLICITLY_SYNTHETIC", "automatic_retries": 0}
    put(directory / "REQUEST.json", request)
    # All mutable ownership bookkeeping exists before any child can be created.
    process = None
    sel = None
    outputs = {}
    failure = None
    original_exception = None
    closure_errors = []
    forced_signals = []
    closed_streams = []
    discarded_stream_bytes = 0
    try:
        process = subprocess.Popen(argv, cwd=directory, env=request["environment"],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, start_new_session=True)
        # Ownership protection includes every post-Popen setup operation.
        sel = selectors.DefaultSelector()
        for kind, pipe in (("stdout", process.stdout), ("stderr", process.stderr)):
            os.set_blocking(pipe.fileno(), False)
            sel.register(pipe, selectors.EVENT_READ, kind)
            outputs[kind] = (directory / (kind + ".bin")).open("xb")
        while sel.get_map() or process.poll() is None:
            now = time.monotonic()
            used, _ = inventory(root)
            if now >= deadline:
                raise RuntimeError("absolute_deadline")
            if used > TOTAL_BYTES - 65536:
                raise RuntimeError("packet_byte_cap")
            for key, _ in sel.select(min(0.01, max(0, deadline - now))):
                data = os.read(key.fileobj.fileno(), 16384)
                if data:
                    used, _ = inventory(root)
                    if used + len(data) > TOTAL_BYTES - 65536:
                        discarded_stream_bytes += len(data)
                        raise RuntimeError("packet_byte_cap_incomplete_stream_failure")
                    outputs[key.data].write(data)
                    outputs[key.data].flush()
                else:
                    sel.unregister(key.fileobj)
                    key.fileobj.close()
                    closed_streams.append(key.data)
        process.wait(timeout=max(0.001, deadline - time.monotonic()))
        if process.returncode != 0:
            raise RuntimeError("nonzero_exit")
        if time.monotonic() >= deadline:
            raise RuntimeError("absolute_deadline")
        if group_present(process.pid):
            raise RuntimeError("unexpected_descendants")
    except BaseException as exc:
        failure = type(exc).__name__ + ": " + str(exc)
        original_exception = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        # Cleanup is bounded independently and cannot turn a failed attempt into success.
        closure_deadline = time.monotonic() + CLOSURE_SECONDS
        if process is not None:
            try:
                if group_present(process.pid):
                    os.killpg(process.pid, signal.SIGKILL)
                    forced_signals.append("SIGKILL")
                process.wait(timeout=max(0.001, closure_deadline - time.monotonic()))
                while group_present(process.pid) and time.monotonic() < closure_deadline:
                    time.sleep(0.005)
                if group_present(process.pid):
                    closure_errors.append("process_group_still_present")
            except BaseException as exc:
                closure_errors.append(type(exc).__name__ + ": " + str(exc))
        if sel is not None:
            try:
                sel.close()
            except BaseException as exc:
                closure_errors.append("selector_close: " + type(exc).__name__)
        for output in outputs.values():
            try:
                output.close()
            except BaseException as exc:
                closure_errors.append("output_close: " + type(exc).__name__)
        if process is not None:
            for pipe in (process.stdout, process.stderr):
                try:
                    if pipe is not None and not pipe.closed:
                        pipe.close()
                except BaseException as exc:
                    closure_errors.append("pipe_close: " + type(exc).__name__)
    finish = time.monotonic()
    absent = process is not None and not group_present(process.pid)
    observation = {"returncode": None if process is None else process.returncode,
                   "failure": failure, "original_exception": original_exception,
                   "pid": None if process is None else process.pid,
                   "start_monotonic": start, "end_monotonic": finish,
                   "elapsed_seconds": finish - start, "absolute_deadline": deadline,
                   "forced_signals": forced_signals, "streams_eof": sorted(closed_streams),
                   "complete_streams": sorted(closed_streams) == ["stderr", "stdout"]
                                       and discarded_stream_bytes == 0,
                   "discarded_stream_bytes": discarded_stream_bytes,
                   "direct_child_reaped": process is not None and process.returncode is not None,
                   "process_group_absent": absent, "closure_errors": closure_errors}
    put(directory / "OBSERVATION.json", observation)
    if (failure is not None or closure_errors or not absent or
            not observation["complete_streams"] or forced_signals):
        raise RuntimeError(name + " engineering attempt failed: " + str(failure))
    return observation


def read_json(path):
    require(path.is_file() and not path.is_symlink(), "ordinary JSON operand")
    body = path.read_bytes()
    require(len(body) <= 262144, "JSON bound")
    return json.loads(body)


def authenticate(source, selection_sha):
    path = source / "CI_SOURCE_SELECTION.json"
    require(path.is_file() and not path.is_symlink(), "source selection ordinary")
    body = path.read_bytes()
    require(len(body) < 65536 and hashlib.sha256(body).hexdigest() == selection_sha,
            "source selection identity")
    selection = json.loads(body)
    require(selection["schema"] == "horrocks-linux-ci-source-selection-v1", "selection schema")
    seen = set()
    for row in selection["files"]:
        name = row["path"]
        require(type(name) is str and Path(name).name == name and name not in seen,
                "flat unique source name")
        seen.add(name)
        path = source / name
        require(path.is_file() and not path.is_symlink(), "ordinary selected source")
        payload = path.read_bytes()
        require(len(payload) == row["bytes"] < 1048576 and
                hashlib.sha256(payload).hexdigest() == row["sha256"], "selected source identity")
    require({"ci_owner.py", "engineering_controls_v1.py", "horrocks_contract_v2.py",
             "EXPECTED_CONTROLS.json"} <= seen, "required source members")
    return selection, body


def selected_python_library():
    # Runtime binary operand only, not a source/data read: at most64MiB per check.
    prefix = Path(sys.base_prefix).resolve(strict=True)
    library_dir = (prefix / "lib").resolve(strict=True)
    require(library_dir.parent == prefix and ":" not in str(library_dir) and
            "\n" not in str(library_dir) and "\r" not in str(library_dir), "selected runtime libdir")
    library = (library_dir / "libpython3.11.so.1.0").resolve(strict=True)
    require(library.parent == library_dir and library.is_file(), "selected libpython file")
    before = library.stat()
    require(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= 64 * 1024 * 1024,
            "runtime library operand bound")
    sha = hashlib.sha256()
    count = 0
    with library.open("rb") as stream:
        while True:
            block = stream.read(1048576)
            if not block:
                break
            count += len(block)
            require(count <= before.st_size, "runtime library grew")
            sha.update(block)
    after = library.stat()
    require(count == before.st_size and
            (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), "runtime library changed")
    with Path("/proc/self/maps").open("rb") as stream:
        maps = stream.read(1048577)
    require(len(maps) <= 1048576, "runtime maps metadata bound")
    loaded = set()
    for line in maps.decode().splitlines():
        parts = line.split(None, 5)
        if len(parts) == 6 and "libpython3.11.so" in parts[5]:
            loaded.add(str(Path(parts[5]).resolve(strict=True)))
    require(loaded == {str(library)}, "loaded libpython must be the selected interpreter operand")
    return {"directory": str(library_dir), "file": str(library), "bytes": count,
            "sha256": sha.hexdigest(), "loaded_mapping_verified": True}


def identity():
    require(sys.platform == "linux" and sys.version_info[:3] == PYTHON_VERSION,
            "exact selected Linux Python")
    return {"executable": sys.executable, "version": sys.version, "platform": sys.platform,
            "uid": os.getuid(), "gid": os.getgid(), "pid": os.getpid(),
            "net_namespace": os.readlink("/proc/self/ns/net"),
            "pid_namespace": os.readlink("/proc/self/ns/pid"),
            "python_library": selected_python_library()}


def prepare(root, selection_sha):
    runtime = identity()
    require(runtime["uid"] != 0 and not root.exists() and not root.is_symlink(),
            "fresh ordinary host scratch")
    source = Path(__file__).resolve().parent
    selection, body = authenticate(source, selection_sha)
    require(root.is_absolute() and source not in root.parents, "external absolute scratch")
    root.mkdir(mode=0o755)
    (root / "outer").mkdir(mode=0o755)
    (root / "inner").mkdir(mode=0o755)
    copied = root / "source"
    copied.mkdir(mode=0o755)
    for row in selection["files"]:
        path = copied / row["path"]
        with path.open("xb") as stream:
            stream.write((source / row["path"]).read_bytes())
        path.chmod(0o444)
    with (copied / "CI_SOURCE_SELECTION.json").open("xb") as stream:
        stream.write(body)
    (copied / "CI_SOURCE_SELECTION.json").chmod(0o444)
    copied.chmod(0o555)
    authenticate(copied, selection_sha)
    namespace_argv = ["/usr/bin/sudo", "-n", "/usr/bin/timeout", "--signal=KILL", "40s",
        "/usr/bin/unshare", "--fork", "--pid", "--net", "--mount-proc", "--kill-child=KILL",
        "/usr/bin/setpriv", "--reuid=65534", "--regid=65534", "--clear-groups",
        "--inh-caps=-all", "--ambient-caps=-all", "--bounding-set=-all", "--no-new-privs",
        "--pdeathsig=KILL", "/usr/bin/env", "-i", "PATH=/usr/bin:/bin", "LANG=C.UTF-8",
        "LD_LIBRARY_PATH=" + runtime["python_library"]["directory"],
        sys.executable, "-I", "-S", "-B", str(copied / "ci_owner.py"), "inner",
        "--root", str(root), "--selection-sha256", selection_sha]
    with (root / "PYTHON_LIBRARY_DIR.txt").open("x") as stream:
        stream.write(runtime["python_library"]["directory"] + "\n")
    start = time.monotonic()
    put(root / "PREPARE.json", {"runtime": runtime, "source_selection_sha256": selection_sha,
        "original_start": start, "original_deadline": start + ATTEMPT_SECONDS,
        "attempt_seconds": ATTEMPT_SECONDS, "outer_cleanup_timeout_seconds": 40,
        "namespace_argv": namespace_argv,
        "selected_uid": 65534, "selected_gid": 65534, "retries": 0,
        "harness": "engineering_controls_v1.py", "fixture_identity": "EXPLICITLY_SYNTHETIC"})


def inner(root, selection_sha):
    require(root.is_dir() and not root.is_symlink(), "ordinary scratch")
    pre = read_json(root / "PREPARE.json")
    runtime = identity()
    require(runtime["uid"] == runtime["gid"] == 65534 and runtime["pid"] == 1,
            "nonroot namespace init required")
    require(os.getgroups() == [], "supplementary groups cleared")
    require(runtime["python_library"] == pre["runtime"]["python_library"] and
            os.environ.get("LD_LIBRARY_PATH") == runtime["python_library"]["directory"],
            "exact selected loader operand; no inherited library search path")
    require(runtime["net_namespace"] != pre["runtime"]["net_namespace"] and
            runtime["pid_namespace"] != pre["runtime"]["pid_namespace"], "new namespaces required")
    fields = dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines()
                  if ":" in line)
    require(fields["NoNewPrivs"].strip() == "1", "no_new_privs required")
    for field in ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb"):
        require(int(fields[field].strip(), 16) == 0, "capabilities must be empty")
    require(pre["source_selection_sha256"] == selection_sha, "preparation binding")
    source = root / "source"
    authenticate(source, selection_sha)
    put(root / "inner" / "ISOLATION.json", {"runtime": runtime,
        "no_new_privs": True, "empty_capabilities": True, "empty_supplementary_groups": True,
        "original_start": pre["original_start"], "original_deadline": pre["original_deadline"],
        "source_selection_sha256": selection_sha, "network_namespace_distinct": True,
        "fixed_command_only": True, "scientific_results": False})
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    observation = execute_one("inner/attempt", [sys.executable, "-I", "-S", "-B",
        str(source / "engineering_controls_v1.py"), "--work-dir",
        str(root / "inner" / "attempt" / "fixtures")], root,
        pre["original_start"], pre["original_deadline"], runtime["python_library"]["directory"])
    authenticate(source, selection_sha)
    put(root / "inner" / "OWNER_RESULT.json", {"status": "NATURAL_ZERO_PENDING_OUTER_ADMISSION",
        "observation": observation, "source_selection_sha256": selection_sha,
        "network_calls": 0, "authentic_data_reads": 0, "model_calls": 0,
        "scientific_runs": 0, "scientifically_qualified": False})


def finish(root, selection_sha, outer_status):
    require(root.is_dir() and not root.is_symlink(), "ordinary existing scratch")
    end = time.monotonic()
    outer = {"outer_exit_status": outer_status, "observed_end": end,
             "original_start": None, "original_deadline": None, "elapsed_seconds": None,
             "runtime": {"executable": sys.executable, "version": sys.version, "platform": sys.platform},
             "namespace_closure": "not admitted until all joins succeed"}
    try:
        runtime = identity()
        require(runtime["uid"] != 0, "ordinary host admission")
        pre = read_json(root / "PREPARE.json")
        outer.update(original_start=pre["original_start"], original_deadline=pre["original_deadline"],
                     elapsed_seconds=end - pre["original_start"], runtime=runtime)
        require(outer_status == 0 and end < pre["original_deadline"], "natural timely outer exit")
        authenticate(root / "source", selection_sha)
        owner = read_json(root / "inner" / "OWNER_RESULT.json")
        isolation = read_json(root / "inner" / "ISOLATION.json")
        observation = read_json(root / "inner" / "attempt" / "OBSERVATION.json")
        result = read_json(root / "inner" / "attempt" / "fixtures" / "RESULT.json")
        expected = read_json(root / "source" / "EXPECTED_CONTROLS.json")
        require(owner["status"] == "NATURAL_ZERO_PENDING_OUTER_ADMISSION" and
                owner["observation"] == observation and
                owner["source_selection_sha256"] == isolation["source_selection_sha256"] == selection_sha,
                "inner owner joins")
        require(observation["returncode"] == 0 and observation["failure"] is None and
                observation["direct_child_reaped"] and observation["process_group_absent"] and
                observation["complete_streams"] and not observation["forced_signals"] and
                not observation["closure_errors"] and
                observation["absolute_deadline"] == pre["original_start"] + 30.0 == pre["original_deadline"],
                "complete original lifecycle")
        controls = result["controls"]
        require([row["name"] for row in controls] == expected["names"] and
                all(row["status"] == "PASS" for row in controls) and
                result["passed"] == 42 and result["failed"] == 0 and
                result["synthetic"] is True and result["scientific_results"] is False and
                result["new_ready_benchmarks"] == 0 and result["within_selected_limits"] is True and
                result["source_sha256"] == expected["expected_core_sha256"], "exact42 controls")
        require((root / "inner" / "attempt" / "stderr.bin").stat().st_size == 0,
                "unexpected child stderr")
        status = "PASSED_42_SYNTHETIC_CONTROLS_ONLY"
        error = None
    except Exception as exc:
        status = "FAILED_NO_RETRY"
        error = type(exc).__name__ + ": " + str(exc)
    outer["namespace_closure"] = ("admitted from natural outer status0 and completed PID1 owner"
                                  if status.startswith("PASSED") else "unestablished: failed admission")
    put(root / "outer" / "OBSERVATION.json", outer)
    total, rows = inventory(root)
    # Determine complete encoded artifact size before publishing any PASSED report.
    artifact = root / "artifact"
    artifact.mkdir()
    originals = []
    regular_payload_bytes = 0
    for row in rows:
        item = dict(row)
        if row["kind"] == "regular":
            body = (root / row["path"]).read_bytes()
            require(len(body) == row["bytes"], "original artifact changed")
            item["sha256"] = hashlib.sha256(body).hexdigest()
            regular_payload_bytes += len(body)
        originals.append(item)
    report = {"status": status, "error": error, "outer": outer,
        "namespace_closure_basis": "Observed natural outer status0 and inner PID1 completion plus kernel PID-namespace termination semantics" if status.startswith("PASSED") else "Unestablished; retain failure",
        "original_bytes_before_artifact": total, "original_members": originals,
        "artifact_complete": True, "symlinks_followed": False,
        "source_selection_sha256": selection_sha,
        "new_tasks": 0, "scientifically_qualified": 0, "model_calls": 0, "scientific_runs": 0}
    if total + regular_payload_bytes + len(encode(report)) > TOTAL_BYTES:
        report.update(status="FAILED_NO_RETRY", error="aggregate original plus artifact byte cap",
                      artifact_complete=False)
        report["namespace_closure_basis"] = "No passing admission; original lifecycle evidence retained separately"
        require(total + len(encode(report)) <= TOTAL_BYTES, "no bounded failure-report allowance")
        put(artifact / "ADMISSION.json", report)
        raise RuntimeError(report["error"])
    # Never dereference the one intentional synthetic symlink.
    for row in originals:
        if row["kind"] != "regular":
            continue
        body = (root / row["path"]).read_bytes()
        require(len(body) == row["bytes"] and hashlib.sha256(body).hexdigest() == row["sha256"],
                "original artifact identity changed")
        destination = artifact / row["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as stream:
            stream.write(body)
    before_report, _ = inventory(root)
    require(before_report + len(encode(report)) <= TOTAL_BYTES, "final artifact admission bound")
    put(artifact / "ADMISSION.json", report)
    require(status.startswith("PASSED"), error or "failed")
    print(json.dumps({"status": status,
                      "retained_bytes_including_original_and_artifact": before_report + len(encode(report))}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "inner", "finish"))
    parser.add_argument("--root", required=True)
    parser.add_argument("--selection-sha256", required=True)
    parser.add_argument("--outer-status", type=int)
    args = parser.parse_args()
    root = Path(args.root).absolute()
    if args.mode == "prepare":
        prepare(root, args.selection_sha256)
    elif args.mode == "inner":
        inner(root, args.selection_sha256)
    else:
        require(args.outer_status is not None, "outer status required")
        finish(root, args.selection_sha256, args.outer_status)


if __name__ == "__main__":
    main()
