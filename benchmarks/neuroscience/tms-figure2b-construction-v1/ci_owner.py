"""Linux-only fixed-source TMS Figure2B engineering owner; no scientific execution.

No arbitrary command is accepted. prepare/finish run on the CI host; inner runs
as UID/GID65534 PID1 in a new network/PID namespace with no capabilities.
The exact trusted host finish collector uses root solely to read 0600/0700
synthetic fixtures, never to execute them; no arbitrary command is accepted.
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

TOTAL_BYTES = 768 * 1024 * 1024
ORIGINAL_BYTES = 384 * 1024 * 1024
MEMBER_BYTES = 16 * 1024 * 1024
STREAM_BYTES = 256 * 1024
ATTEMPT_SECONDS = 180.0
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
                require(meta.st_nlink == 1 and meta.st_size <= MEMBER_BYTES, "ordinary bounded single-link scratch member")
                total += meta.st_size
                rows.append({"path": relative, "kind": "regular", "bytes": meta.st_size})
            elif stat.S_ISLNK(meta.st_mode):
                # Inventory any symlink as metadata only; the TMS fixture admission rejects them.
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
        "LD_LIBRARY_PATH": library_dir, "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"},
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
            if used > ORIGINAL_BYTES - 65536:
                raise RuntimeError("packet_byte_cap")
            for key, _ in sel.select(min(0.01, max(0, deadline - now))):
                data = os.read(key.fileobj.fileno(), 16384)
                if data:
                    used, _ = inventory(root)
                    if used + len(data) > ORIGINAL_BYTES - 65536 or outputs[key.data].tell() + len(data) > STREAM_BYTES:
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
    require(selection["schema"] == "tms-figure2b-linux-ci-source-selection-v1", "selection schema")
    seen = set()
    for row in selection["files"]:
        name = row["path"]
        require(type(name) is str and not Path(name).is_absolute() and Path(name).parts and ".." not in Path(name).parts and str(Path(name)) == name and name not in seen,
                "relative unique source name")
        seen.add(name)
        path = source / name
        require(all(not parent.is_symlink() for parent in path.parents if parent == source or source in parent.parents), "no source ancestor symlink")
        require(path.is_file() and not path.is_symlink(), "ordinary selected source")
        payload = path.read_bytes()
        require(len(payload) == row["bytes"] < 1048576 and
                hashlib.sha256(payload).hexdigest() == row["sha256"], "selected source identity")
    require({"ci_owner.py", "run_synthetic.py", "test_source_positions.py",
             "operator/tms_figure/derivative.py", "EXPECTED_CONTROLS.json"} <= seen,
            "required source members")
    actual = {str(p.relative_to(source)) for p in source.rglob("*") if p.is_file()}
    require(actual == seen | {"CI_SOURCE_SELECTION.json"}, "closed source census")
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
    require(count == 23050048 and sha.hexdigest() == "bb41a7ec12bb82772ffb9099b944d2d338a357318548a260a58385f7e802730f", "selected observed Linux CPython library identity")
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
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write((source / row["path"]).read_bytes())
        path.chmod(0o444)
    with (copied / "CI_SOURCE_SELECTION.json").open("xb") as stream:
        stream.write(body)
    (copied / "CI_SOURCE_SELECTION.json").chmod(0o444)
    for directory in sorted((p for p in copied.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        directory.chmod(0o555)
    copied.chmod(0o555)
    authenticate(copied, selection_sha)
    namespace_argv = ["/usr/bin/sudo", "-n", "/usr/bin/timeout", "--signal=KILL", "190s",
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
        "attempt_seconds": ATTEMPT_SECONDS, "outer_cleanup_timeout_seconds": 190,
        "namespace_argv": namespace_argv,
        "selected_uid": 65534, "selected_gid": 65534, "retries": 0,
        "harness": "test_source_positions.py", "fixture_identity": "EXPLICITLY_SYNTHETIC"})


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
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_CPU, (180, 180))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MEMBER_BYTES,) * 2)
    resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
    observation = execute_one("inner/attempt", [sys.executable, "-I", "-B",
        str(source / "run_synthetic.py"), "--out",
        str(root / "inner" / "attempt" / "fixtures"), "--runtime-output",
        str(root / "inner" / "attempt" / "RUNTIME.json")], root,
        pre["original_start"], pre["original_deadline"], runtime["python_library"]["directory"])
    authenticate(source, selection_sha)
    put(root / "inner" / "OWNER_RESULT.json", {"status": "NATURAL_ZERO_PENDING_OUTER_ADMISSION",
        "observation": observation, "source_selection_sha256": selection_sha,
        "network_calls": 0, "authentic_data_reads": 0, "model_calls": 0,
        "scientific_runs": 0, "scientifically_qualified": False})


def validate_synthetic_result(root, result, expected):
    source = root / "source"
    fixtures = root / "inner" / "attempt" / "fixtures"
    require(result["schema"] == "tms_source_position_synthetic_result_v1" and
            result["status"] == "PASS", "synthetic result schema")
    names = expected["control_names"]
    require(len(names) == len(set(names)) == expected["control_count"] == 146 and
            [row["name"] for row in result["checks"]] == names and
            all(row["pass"] is True for row in result["checks"]) and
            result["passed"] == 146 and result["failed"] == 0, "exact146 semantic controls")
    require(result["complete_shape"] == [62, 53, 200, 15] and
            result["conditions"] == 4 and result["fields"] == 36 and
            result["primary_reads"] == result["model_calls"] == result["real_or_native_arithmetic_runs"] == 0 and
            result["scientifically_qualified"] is False and result["authentic_pin_restored"] is True,
            "complete synthetic-only source-position scope")
    require(type(result["peak_self_rss_bytes"]) is int and
            0 < result["peak_self_rss_bytes"] <= 2 * 1024**3, "original observed RSS cap")
    require(hashlib.sha256((source / "test_source_positions.py").read_bytes()).hexdigest()
            == expected["original_harness_sha256"], "unchanged146-control harness")
    stdout = read_json(root / "inner" / "attempt" / "stdout.bin")
    result_body = (fixtures / "RESULT.json").read_bytes()
    require(stdout["status"] == "PASS" and stdout["passed"] == 146 and stdout["failed"] == 0 and
            stdout["result_pin"] == {"bytes": len(result_body), "sha256": hashlib.sha256(result_body).hexdigest()} and
            stdout["peak_self_rss_bytes"] == result["peak_self_rss_bytes"] and
            stdout["retained_bytes_before_result"] == result["retained_bytes_before_result"],
            "complete original stdout-result join")
    total, rows = inventory(fixtures)
    require(len(rows) == expected["fixture_member_count"] == 258 and
            all(row["kind"] == "regular" for row in rows) and
            {row["path"] for row in rows} == set(expected["fixture_members"]),
            "complete258-file synthetic support; no thinning")
    require(result["retained_bytes_before_result"] + len(result_body) == total and
            total < ORIGINAL_BYTES, "all original fixture bytes retained")
    captures = read_json(fixtures / "CAPTURE_RECORDS.json")
    require(captures["invented_only"] is True and captures["both_complete_producer_outputs_preserved"] is True,
            "explicit invented capture provenance")
    require(set(captures["captures"]) == {"A", "B"}, "both real capture paths")
    for arm in ("A", "B"):
        producer = fixtures / arm
        captured = fixtures / ("captured_" + arm)
        body = (producer / "OUTPUT.json").read_bytes()
        manifest = json.loads(body)
        cp = captures["captures"][arm]
        require(cp["schema"] == "tms_figure2b_sealed_capture_v1" and cp["member_count"] == 37 and
                cp["directory"] == str(captured) and len(cp["members"]) == 36 and
                cp["output"] == captures["producer_output_pins"][arm] ==
                {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}, "complete capture manifest")
        require(len(manifest["fields"]) == 36 and manifest["schema"] == "tms_figure2b_source_position_full_output_v1",
                "complete36-field actual output")
        for key in ("physical_id_map_verified",):
            require(manifest["identity"]["participant_axis_identity"][key] is False, "no physical-person mapping claim")
        require(manifest["identity"]["provenance"]["upstream_preprocessing_verified"] is False and
                manifest["identity"]["provenance"]["paired_person_inference_admitted"] is False,
                "original provenance gates unchanged")
        expected_names = {name + ".bin" for name in manifest["fields"]} | {"OUTPUT.json"}
        require({p.name for p in producer.iterdir()} == {p.name for p in captured.iterdir()} == expected_names,
                "exact37 producer and capture files")
        for name in sorted(expected_names):
            left = (producer / name).read_bytes()
            right = (captured / name).read_bytes()
            require(left == right, "complete producer/capture byte equality")
            if name != "OUTPUT.json":
                row = manifest["fields"][name[:-4]]
                require(len(left) == row["bytes"] == cp["members"][name]["bytes"] and
                        hashlib.sha256(left).hexdigest() == row["sha256"] == cp["members"][name]["sha256"],
                        "all captured original field identities")
    grade = read_json(fixtures / "invented_grade" / "REPORT.json")
    require(grade["scientifically_qualified"] is False and
            grade["arms"]["A"]["all_elements_pass"] is True and len(grade["arms"]["A"]["fields"]) == 36 and
            grade["arms"]["B"]["all_elements_pass"] is False and len(grade["arms"]["B"]["fields"]) == 36 and
            sum(row["fail_count"] for row in grade["arms"]["B"]["fields"].values()) == 1 and
            grade["arms"]["B"]["fields"]["window.T.delay2.value"]["fail_count"] == 1,
            "real paired scorer detects exactly the planted error")
    runtime = read_json(root / "inner" / "attempt" / "RUNTIME.json")
    require(runtime["schema"] == "tms-linux-synthetic-runtime-v1" and
            runtime["python_version"] == "3.11.18" and runtime["machine"] == "x86_64" and
            runtime["numpy_version"] == "2.4.6" and runtime["h5py_version"] == "3.16.0" and
            runtime["scientifically_qualified"] is False and runtime["native_matlab_parity"] is False,
            "actual explicit Linux runtime versions")
    return {"controls_passed": 146, "complete_shape": [62, 53, 200, 15],
            "conditions": 4, "fields": 36, "stored_positions": 15,
            "complete_fixture_bytes": total, "fixture_regular_files": len(rows),
            "both_complete37_file_captures": True, "A_all36_fields_pass": True,
            "B_exactly_one_planted_failure": "window.T.delay2.value",
            "observed_harness_peak_rss_bytes": result["peak_self_rss_bytes"], "runtime": runtime}


def finish(root, selection_sha, outer_status):
    require(root.is_dir() and not root.is_symlink(), "ordinary existing scratch")
    os.umask(0o022)
    end = time.monotonic()
    synthetic_summary = None
    outer = {"outer_exit_status": outer_status, "observed_end": end,
             "original_start": None, "original_deadline": None, "elapsed_seconds": None,
             "runtime": {"executable": sys.executable, "version": sys.version, "platform": sys.platform},
             "namespace_closure": "not admitted until all joins succeed"}
    try:
        runtime = identity()
        require(runtime["uid"] == 0, "trusted root collector for private synthetic fixtures")
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
                observation["absolute_deadline"] == pre["original_start"] + ATTEMPT_SECONDS == pre["original_deadline"],
                "complete original lifecycle")
        synthetic_summary = validate_synthetic_result(root, result, expected)
        require((root / "inner" / "attempt" / "stderr.bin").stat().st_size == 0,
                "unexpected child stderr")
        status = "PASSED_146_SYNTHETIC_CONTROLS_ONLY"
        error = None
    except Exception as exc:
        status = "FAILED_NO_RETRY"
        error = type(exc).__name__ + ": " + str(exc)
    outer["namespace_closure"] = ("admitted from natural outer status0 and completed PID1 owner"
                                  if status.startswith("PASSED") else "unestablished: failed admission")
    put(root / "outer" / "OBSERVATION.json", outer)
    total, rows = inventory(root)
    require(total <= ORIGINAL_BYTES, "complete original384MiB bound")
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
        "synthetic_summary": synthetic_summary,
        "collector_privilege": "Exact pinned trusted host collector only; no fixture content execution",
        "new_tasks": 0, "scientifically_qualified": 0, "model_calls": 0, "scientific_runs": 0}
    if total + regular_payload_bytes + len(encode(report)) > TOTAL_BYTES:
        report.update(status="FAILED_NO_RETRY", error="aggregate original plus artifact byte cap",
                      artifact_complete=False)
        report["namespace_closure_basis"] = "No passing admission; original lifecycle evidence retained separately"
        require(total + len(encode(report)) <= TOTAL_BYTES, "no bounded failure-report allowance")
        put(artifact / "ADMISSION.json", report)
        raise RuntimeError(report["error"])
    # Never dereference a symlink while collecting any failed or successful attempt.
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
    # The whole original attempt includes complete collection and admission publication.
    final_end = time.monotonic()
    report["finalization"] = {"observed_before_admission": final_end,
        "original_deadline": outer["original_deadline"], "within_original_deadline":
        type(outer["original_deadline"]) is float and final_end < outer["original_deadline"]}
    if status.startswith("PASSED") and not report["finalization"]["within_original_deadline"]:
        status = "FAILED_NO_RETRY"
        report.update(status=status, error="original deadline exceeded during complete collection")
    require(before_report + len(encode(report)) + 8192 <= TOTAL_BYTES, "finalization reserve inside aggregate cap")
    put(artifact / "ADMISSION.json", report)
    after_publication = time.monotonic()
    if status.startswith("PASSED") and after_publication >= outer["original_deadline"]:
        put(artifact / "FINAL_DEADLINE_FAILURE.json", {"status": "FAILED_NO_RETRY",
            "overrides_admission": True, "observed_after_admission": after_publication,
            "original_deadline": outer["original_deadline"], "scientifically_qualified": False})
        raise RuntimeError("original deadline exceeded during final publication")
    require(status.startswith("PASSED"), error or "failed")
    print(json.dumps({"status": status,
                      "retained_bytes_including_original_and_artifact": before_report + len(encode(report))}))


def diagnostics(root):
    """Retain bounded, explicitly incomplete evidence after setup/collector failure."""
    require(os.getuid() == 0, "trusted diagnostic collector")
    os.umask(0o022)
    require(root.parent == Path("/tmp") and
            root.name.startswith("tms-figure2b-controls-") and
            not root.is_symlink(), "fixed owned diagnostic root")
    root.mkdir(mode=0o755, exist_ok=True)
    artifact = root / "artifact"
    require(not artifact.is_symlink(), "ordinary diagnostic artifact")
    artifact.mkdir(mode=0o755, exist_ok=True)
    if (artifact / "ADMISSION.json").is_file() and not (artifact / "ADMISSION.json").is_symlink():
        return
    findings = []
    copied = 0
    for relative in ("PREPARE.json", "outer/namespace.stdout", "outer/namespace.stderr",
            "outer/namespace.status", "outer/OBSERVATION.json", "inner/ISOLATION.json",
            "inner/OWNER_RESULT.json", "inner/attempt/REQUEST.json",
            "inner/attempt/OBSERVATION.json", "inner/attempt/RUNTIME.json", "inner/attempt/stdout.bin",
            "inner/attempt/stderr.bin", "inner/attempt/fixtures/RESULT.json",
            "inner/attempt/fixtures/FAILURE.json"):
        path = root / relative
        if any(parent.is_symlink() for parent in path.parents if parent != root and root in parent.parents):
            findings.append({"path": relative, "status": "ancestor_symlink_not_followed"})
            continue
        if not path.exists():
            continue
        meta = path.lstat()
        if not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1 or meta.st_size > 131072:
            findings.append({"path": relative, "status": "nonordinary_or_oversized_not_copied"})
            continue
        body = path.read_bytes()
        used, _ = inventory(root)
        if copied + len(body) > 1048576 or used + len(body) + 16384 > TOTAL_BYTES:
            findings.append({"path": relative, "status": "diagnostic_byte_bound"})
            continue
        destination = artifact / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() or destination.is_symlink():
            findings.append({"path": relative, "status": "original_existing_destination_preserved"})
            continue
        with destination.open("xb") as stream:
            stream.write(body)
        copied += len(body)
        findings.append({"path": relative, "status": "copied", "bytes": len(body),
                         "sha256": hashlib.sha256(body).hexdigest()})
    marker = {"status": "FAILED_OR_INCOMPLETE", "passing_result": False,
              "artifact_complete": False, "controls_passed": None,
              "note": "No admitted result. Read original full job logs; diagnostics do not establish a146-control pass.",
              "diagnostic_bytes_copied": copied, "findings": findings,
              "scientifically_qualified": False}
    target = artifact / "FAILED_SETUP.json"
    if not target.exists():
        used, _ = inventory(root)
        require(used + len(encode(marker)) <= TOTAL_BYTES, "bounded failure diagnostic marker")
        put(target, marker)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "inner", "finish", "diagnostics"))
    parser.add_argument("--root", required=True)
    parser.add_argument("--selection-sha256", required=True)
    parser.add_argument("--outer-status", type=int)
    args = parser.parse_args()
    root = Path(args.root).absolute()
    if args.mode == "prepare":
        prepare(root, args.selection_sha256)
    elif args.mode == "inner":
        inner(root, args.selection_sha256)
    elif args.mode == "diagnostics":
        diagnostics(root)
    else:
        require(args.outer_status is not None, "outer status required")
        finish(root, args.selection_sha256, args.outer_status)


if __name__ == "__main__":
    main()
