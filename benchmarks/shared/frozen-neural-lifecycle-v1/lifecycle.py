"""Trusted operator lifecycle for two complete, exposed neural development panels.

No scientific scorer is implemented here. Public staging and native submission
assembly use only the standard library. The original pinned scorer remains the
only scientific grading route. This is not a hostile-code or authoring sandbox.
"""
from pathlib import Path
import argparse
import ast
import contextlib
import hashlib
import json
import math
import os
import shutil
import signal
import stat
import struct
import subprocess
import sys
import time
import zipfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CASES = ("development-001", "development-002")
COUNTS = {"NEURAL-007": (2780, 2670), "NEURAL-077": (200, 200)}
CLASSES = ("W", "N1", "N2", "N3", "R")
PUBLIC_PINS = {
    "NEURAL-007": ("public_assets.json", 11568, "d5ea2b631dc3c6f6776b99ae9b40d7a9b049ec6d12552476e84b3b504e4c8274"),
    "NEURAL-077": ("assets.json", 5887, "1204a0ebffbede10db2071c7e58837b5190726470d9db125072a455d6629f387"),
}
THREADS = ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "OMP_THREAD_LIMIT", "MKL_NUM_THREADS", "NUMBA_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")


class Rejected(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise Rejected(message)


def decode(body):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            require(key not in out, "Duplicate JSON key")
            out[key] = value
        return out
    def bad_constant(value):
        raise Rejected("Nonfinite JSON constant: " + value)
    return json.loads(body, object_pairs_hook=unique, parse_constant=bad_constant)


def regular(path, cap=512 * 1024**2, empty=False):
    path = Path(path).absolute()
    require(all(not p.is_symlink() for p in (path, *path.parents)), "Linked paths rejected")
    st = path.stat()
    require(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and (0 if empty else 1) <= st.st_size <= cap,
            "Bounded single-link regular file required: " + str(path))
    return path


def pin(path, cap=512 * 1024**2, empty=False):
    path = regular(path, cap, empty)
    before = path.stat()
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024**2), b""):
            h.update(block)
    after = path.stat()
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), "File changed while pinning")
    return {"bytes": after.st_size, "sha256": h.hexdigest()}


def verify(path, expected):
    require(pin(path) == {k: expected[k] for k in ("bytes", "sha256")}, "Pinned bytes changed: " + str(path))


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8") as f:
        json.dump(value, f, sort_keys=True, indent=2, allow_nan=False)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())


def read_json(path, cap=4 * 1024**2):
    return decode(regular(path, cap).read_bytes())


def inventory(root):
    root = Path(root)
    require(root.is_dir() and not root.is_symlink(), "Ordinary directory required")
    files = {}
    for p in sorted(root.rglob("*")):
        require(not p.is_symlink(), "No source/input symlinks")
        if p.is_dir():
            continue
        files[p.relative_to(root).as_posix()] = pin(p, empty=True)
    require(0 < len(files) <= 2000 and sum(x["bytes"] for x in files.values()) <= 512 * 1024**2,
            "Bounded nonempty source/input tree")
    return files


def verify_tree(root, expected):
    require(inventory(root) == expected, "Source/input tree changed: " + str(root))


def copy_pinned(source, destination, expected):
    verify(source, expected)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with regular(source).open("rb") as src, destination.open("xb") as dst:
        shutil.copyfileobj(src, dst)
    verify(destination, expected)


def events(root):
    rows = []
    previous = None
    for index, path in enumerate(sorted((Path(root) / "events").glob("*.json"))):
        row = read_json(path)
        require(path.name == f"{index:04d}.json" and row["sequence"] == index and row["previous"] == previous,
                "Broken event chain")
        rows.append(row)
        previous = pin(path)["sha256"]
    return rows


def record(root, kind, **details):
    rows = events(root)
    previous = None if not rows else pin(Path(root) / "events" / f"{len(rows)-1:04d}.json")["sha256"]
    write_json(Path(root) / "events" / f"{len(rows):04d}.json",
               {"sequence": len(rows), "previous": previous, "event": kind, "time_ns": time.time_ns(), **details})


@contextlib.contextmanager
def operation(root, name):
    root = Path(root).absolute()
    fd = os.open(root / ".operator-lock", os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        rows = events(root)
        require(not any(r["event"] == "operation_failed" for r in rows), "Failed lifecycle is terminal; retain it and start a new registered attempt")
        yield root
    except BaseException as exc:
        record(root, "operation_failed", operation=name, error_type=type(exc).__name__, error=str(exc)[:2000])
        raise
    finally:
        os.close(fd)
        (root / ".operator-lock").unlink()


def _unicode_array(path, key, count):
    """Read only a bounded, source-pinned NPY Unicode identity vector."""
    with zipfile.ZipFile(regular(path, 4 * 1024**2)) as z:
        matches = [r for r in z.infolist() if r.filename == key + ".npy"]
        require(len(matches) == 1 and matches[0].file_size <= 256000, "One bounded identity member")
        data = z.read(matches[0])
    require(data[:6] == b"\x93NUMPY" and data[6:8] in (b"\x01\x00", b"\x02\x00"), "NPY identity header")
    width = 2 if data[6] == 1 else 4
    length = int.from_bytes(data[8:8+width], "little")
    require(0 < length <= 4096, "Bounded NPY header")
    start = 8 + width + length
    header = ast.literal_eval(data[8+width:start].decode("latin1"))
    require(set(header) == {"descr", "fortran_order", "shape"} and header["shape"] == (count,), "Complete identity geometry")
    dtype = header["descr"]
    require(isinstance(dtype, str) and dtype[:2] in ("<U", ">U") and dtype[2:].isdigit(), "Unicode IDs required")
    chars = int(dtype[2:])
    require(0 < chars <= 128 and len(data) == start + count * chars * 4, "Bounded exact identity payload")
    codec = "utf-32-le" if dtype[0] == "<" else "utf-32-be"
    ids = [data[start+i*chars*4:start+(i+1)*chars*4].decode(codec).rstrip("\0") for i in range(count)]
    require(all(ids) and len(set(ids)) == count, "Complete unique IDs")
    return ids


def prepare(task_id, asset_root, output):
    """Copy exactly public feature-condition files; never traverse private data."""
    require(task_id in COUNTS, "Supported task required")
    source = REPO / "benchmarks/neural" / task_id / "implementations/registered-runtime"
    filename, size, sha = PUBLIC_PINS[task_id]
    verify(source / filename, {"bytes": size, "sha256": sha})
    public = read_json(source / filename)
    asset_root, output = Path(asset_root).absolute(), Path(output).absolute()
    require(not output.exists(), "Fresh lifecycle directory required")
    output.mkdir(parents=True)
    (output / "events").mkdir()
    try:
        files, cases = [], {}
        if task_id == "NEURAL-077":
            for case, entries in public["public_training_lazy"].items():
                files.append((entries["features"], "training/" + case + "/features.npz"))
            for case in CASES:
                p = public["public"]["cases"][case]["features"]
                logical = "development/" + case + "/features.npz"
                files.append((p, logical))
                cases[case] = {"count": 200, "identity_file": logical, "identity_key": "trial_ids"}
        else:
            for p in public["files"]:
                role, case = p["role"], p.get("case_id")
                if role.startswith("training_"):
                    logical = "training/" + case + "/" + Path(p["logical_path"]).name
                elif role.startswith("development_"):
                    logical = "development/" + case + "/" + Path(p["logical_path"]).name
                elif role == "common_model_reader":
                    logical = p["logical_path"]
                else:
                    raise Rejected("Unexpected public asset role")
                files.append((p, logical))
                if role == "development_features":
                    cases[case] = {"count": COUNTS[task_id][CASES.index(case)], "identity_file": logical, "identity_key": "epoch_id"}
        for asset, logical in files:
            relative = Path(asset["path"])
            require(not relative.is_absolute() and ".." not in relative.parts, "Relative pinned public path")
            copy_pinned(asset_root / relative, output / "inputs" / logical, asset)
        for case in CASES:
            cases[case]["ids"] = _unicode_array(output / "inputs" / cases[case]["identity_file"], cases[case]["identity_key"], cases[case]["count"])
        require(len({i for c in cases.values() for i in c["ids"]}) == sum(COUNTS[task_id]), "Unique complete panel")
        packet = {"schema": "frozen_neural_lifecycle_v1", "task_id": task_id, "evidence_kind": "authentic_public_inputs",
                  "condition": "feature_programme", "case_order": list(CASES), "cases": cases,
                  "public_descriptor": {"path": str(source / filename), "bytes": size, "sha256": sha},
                  "inputs": inventory(output / "inputs"), "scorer_memory_bytes": 4 * 1024**3,
                  "scorer_source": inventory(source)}
        write_json(output / "packet.json", packet)
        record(output, "prepared", packet=pin(output / "packet.json"), population=sum(COUNTS[task_id]))
        return packet
    except Exception as exc:
        record(output, "operation_failed", operation="prepare", error_type=type(exc).__name__, error=str(exc)[:2000])
        raise


def packet(root):
    rows = events(root)
    require(rows and rows[0]["event"] == "prepared", "Prepared lifecycle required")
    verify(Path(root) / "packet.json", rows[0]["packet"])
    p = read_json(Path(root) / "packet.json")
    require(p["task_id"] in COUNTS and p["case_order"] == list(CASES), "Exact task/case identity")
    require([p["cases"][case]["count"] for case in CASES] == list(COUNTS[p["task_id"]]), "Complete canonical panel")
    verify_tree(Path(root) / "inputs", p["inputs"])
    return p


def commit(root, source, entrypoint="candidate.py"):
    """Commit all method/code/fitted files before any development process."""
    with operation(root, "commit") as root:
        p = packet(root)
        require([r["event"] for r in events(root)] == ["prepared"], "One method commitment before execution only")
        source = Path(source).absolute()
        relative = Path(entrypoint)
        require(not relative.is_absolute() and ".." not in relative.parts and relative.suffix == ".py", "Relative Python entrypoint")
        require(source != root and root not in source.parents and source not in root.parents, "Separate method and lifecycle directories")
        source_files = inventory(source)
        require("METHOD.md" in source_files and entrypoint in source_files, "METHOD.md and declared entrypoint required")
        require(source_files["METHOD.md"]["bytes"] > 0, "Nonempty frozen method declaration")
        shutil.copytree(source, root / "method")
        verify_tree(root / "method", source_files)
        python = str(Path(sys.executable).resolve())
        frozen = {"source_origin": str(source), "files": source_files, "entrypoint": entrypoint,
                  "packet": pin(root / "packet.json"), "controller": pin(HERE / "lifecycle.py"),
                  "bootstrap": pin(HERE / "candidate_entry.py"), "python": pin(python),
                  "python_path": python, "memory_bytes": 2 * 1024**3, "cpu_threads": 2,
                  "wall_seconds_per_person": 120, "authoring_access": "policy_only_shared_host",
                  "task_id": p["task_id"]}
        write_json(root / "method_commit.json", frozen)
        record(root, "method_committed", commitment=pin(root / "method_commit.json"))
        return frozen


def method(root):
    rows = [r for r in events(root) if r["event"] == "method_committed"]
    require(len(rows) == 1, "Exactly one pre-execution method commitment")
    verify(Path(root) / "method_commit.json", rows[0]["commitment"])
    m = read_json(Path(root) / "method_commit.json")
    verify_tree(Path(root) / "method", m["files"])
    verify_tree(m["source_origin"], m["files"])
    verify(HERE / "lifecycle.py", m["controller"])
    verify(HERE / "candidate_entry.py", m["bootstrap"])
    verify(m["python_path"], m["python"])
    return m


def response(path, ids, task_id):
    body = read_json(path, 2 * 1024**2)
    require(type(body) is dict and set(body) == {"ids", "probabilities"}, "Exact per-person response keys")
    got, probabilities = body["ids"], body["probabilities"]
    require(type(got) is list and all(type(i) is str for i in got) and len(got) == len(ids)
            and len(set(got)) == len(got) and set(got) == set(ids), "Exact complete person identity set")
    require(type(probabilities) is list and len(probabilities) == len(ids), "Complete probabilities")
    width = 5 if task_id == "NEURAL-007" else 1
    for row in probabilities:
        values = row if width == 5 else [row]
        require(type(values) is list and len(values) == width and all(type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 1 for v in values),
                "Finite numeric probabilities in [0,1]; booleans rejected")
        if width == 5:
            require(abs(sum(values) - 1) <= 1e-6, "Five-class simplex required; no normalization")
    positions = {i: n for n, i in enumerate(got)}
    return [probabilities[positions[i]] for i in ids]


def _group_alive(pid):
    try:
        os.killpg(pid, 0)
        return True
    except ProcessLookupError:
        return False


def _kill_group(pid):
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _process(root, case_root, request, m, generated=False):
    """One fresh/reaped process group. Generated controls can use observed memory.

    Authentic execution requires Linux RLIMIT_AS; unsupported hosts fail closed.
    Group closure is cooperative containment, not hostile-process isolation.
    """
    env = {"PATH": os.defpath, "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1",
           "HOME": str(case_root / "scratch"), "TMPDIR": str(case_root / "scratch"), **{k: "2" for k in THREADS}}
    argv = [m["python_path"], "-I", "-B", str(HERE / "candidate_entry.py"),
            str(case_root / "source" / m["entrypoint"]), str(request), str(case_root / "output" / "predictions.json"),
            str(case_root / "resources.json"), str(m["memory_bytes"]), "generated" if generated else "hard"]
    started = time.monotonic()
    with (case_root / "stdout.log").open("xb") as out, (case_root / "stderr.log").open("xb") as err:
        proc = subprocess.Popen(argv, cwd=case_root / "scratch", env=env, stdout=out, stderr=err, start_new_session=True)
        try:
            request_pin = pin(request)
            record(root, "case_started", case_id=case_root.name, pid=proc.pid, request=request_pin)
            try:
                code = proc.wait(timeout=m["wall_seconds_per_person"])
            except subprocess.TimeoutExpired:
                record(root, "case_failed", case_id=case_root.name, reason="wall_timeout", pid=proc.pid)
                raise Rejected("Candidate wall limit exceeded")
            descendants = _group_alive(proc.pid)
            elapsed = time.monotonic() - started
            record(root, "case_exited", case_id=case_root.name, pid=proc.pid, returncode=code,
                   elapsed_seconds=elapsed, reaped=True, remaining_group=descendants,
                   resources=pin(case_root / "resources.json") if (case_root / "resources.json").exists() else None,
                   stdout=pin(case_root / "stdout.log", empty=True), stderr=pin(case_root / "stderr.log", empty=True))
            require(code == 0 and not descendants, "Candidate failed or left live descendants; retained terminal failure")
            verify(request, request_pin)
        finally:
            # Covers receipt failures, interruption and unexpected wait errors as
            # well as timeout. No failed invocation may leave its parent alive.
            _kill_group(proc.pid)
            proc.wait(timeout=5)


def execute(root):
    with operation(root, "execute") as root:
        p, m = packet(root), method(root)
        require([r["event"] for r in events(root)] == ["prepared", "method_committed"], "Execute exactly once after commitment")
        record(root, "execution_started", commitment=pin(root / "method_commit.json"))
        for case in CASES:
            packet(root)
            method(root)
            case_root = root / "processes" / case
            case_root.mkdir(parents=True)
            for directory in ("scratch", "output"):
                (case_root / directory).mkdir()
            shutil.copytree(root / "method", case_root / "source")
            shutil.copytree(root / "inputs" / "training", case_root / "training")
            shutil.copytree(root / "inputs" / "development" / case, case_root / "case")
            if (root / "inputs" / "helpers").exists():
                shutil.copytree(root / "inputs" / "helpers", case_root / "helpers")
            copied = ["source", "training", "case"] + (["helpers"] if (case_root / "helpers").exists() else [])
            before = {key: inventory(case_root / key) for key in copied}
            request = case_root / "request.json"
            write_json(request, {"task_id": p["task_id"], "case_id": case, "ids": p["cases"][case]["ids"],
                                 "training_directory": str(case_root / "training"), "case_directory": str(case_root / "case"),
                                 "helpers_directory": str(case_root / "helpers") if (case_root / "helpers").exists() else None,
                                 "response": "JSON object with exactly ids and probabilities; complete person"})
            _process(root, case_root, request, m, generated=p["evidence_kind"] == "generated_engineering_control")
            packet(root)
            method(root)
            for key, expected in before.items():
                verify_tree(case_root / key, expected)
            output = case_root / "output" / "predictions.json"
            require({x.name for x in (case_root / "output").iterdir()} == {"predictions.json"}, "Exactly one candidate output")
            response(output, p["cases"][case]["ids"], p["task_id"])
            record(root, "case_admitted", case_id=case, output=pin(output), count=p["cases"][case]["count"])
        record(root, "execution_completed", persons=len(CASES))


def _npy(values, shape, unicode=False):
    if unicode:
        width = max(len(x) for x in values)
        dtype = "<U" + str(width)
        body = b"".join(x.encode("utf-32-le").ljust(width * 4, b"\0") for x in values)
    else:
        dtype = "<f8"
        flat = [v for row in values for v in row] if len(shape) == 2 else values
        body = struct.pack("<" + "d" * len(flat), *flat)
    header = repr({"descr": dtype, "fortran_order": False, "shape": shape}).encode("ascii")
    header += b" " * ((-(10 + len(header) + 1)) % 64) + b"\n"
    return b"\x93NUMPY\x01\x00" + struct.pack("<H", len(header)) + header + body


def native_submission(path, p, values):
    with zipfile.ZipFile(path, "x", compression=zipfile.ZIP_STORED) as z:
        def put(key, body):
            item = zipfile.ZipInfo(key + ".npy", date_time=(1980, 1, 1, 0, 0, 0))
            item.external_attr = (stat.S_IFREG | 0o600) << 16
            z.writestr(item, body)
        if p["task_id"] == "NEURAL-077":
            ids = [i for case in CASES for i in p["cases"][case]["ids"]]
            probabilities = [v for case in CASES for v in values[case]]
            put("trial_ids", _npy(ids, (len(ids),), True))
            put("target_probability", _npy(probabilities, (len(ids),)))
        else:
            put("class_order", _npy(list(CLASSES), (5,), True))
            for case in CASES:
                ids = p["cases"][case]["ids"]
                put(case + "__epoch_id", _npy(ids, (len(ids),), True))
                put(case + "__probabilities", _npy(values[case], (len(ids), 5)))


def freeze(root):
    with operation(root, "freeze") as root:
        p, m = packet(root), method(root)
        rows = events(root)
        require(rows[-1]["event"] == "execution_completed", "Finish both producers before freezing")
        admitted = [r for r in rows if r["event"] == "case_admitted"]
        require([r["case_id"] for r in admitted] == list(CASES), "Both complete people required")
        values = {}
        for row in admitted:
            case = row["case_id"]
            path = root / "processes" / case / "output" / "predictions.json"
            verify(path, row["output"])
            values[case] = response(path, p["cases"][case]["ids"], p["task_id"])
        native_submission(root / "submission.npz", p, values)
        record(root, "submission_frozen", submission=pin(root / "submission.npz"),
               population=sum(COUNTS[p["task_id"]]), commitment=pin(root / "method_commit.json"),
               evidence_kind=p["evidence_kind"])
        return pin(root / "submission.npz")


def _grade_gate(root, callback, memory_budget_bytes):
    """Internal test seam; public grade() always dispatches the pinned native CLI."""
    with operation(root, "grade") as root:
        p = packet(root)
        method(root)
        rows = events(root)
        require(rows[-1]["event"] == "submission_frozen", "Exactly one grade after complete submission freeze")
        expected = rows[-1]["submission"]
        verify(root / "submission.npz", expected)
        require(memory_budget_bytes >= p["scorer_memory_bytes"], "Native scorer requires 4 GiB; current budget is insufficient; no scorer dispatched")
        record(root, "grade_started", submission=expected)
        callback(root, p)
        verify(root / "submission.npz", expected)
        packet(root)
        method(root)
        record(root, "grade_finished", submission=expected)


def grade(root, runtime_root, memory_budget_bytes=2 * 1024**3):
    """Native historical-layout dispatch. No score/target/source-pin overrides."""
    def native(root, p):
        require(p["evidence_kind"] == "authentic_public_inputs", "Generated controls cannot invoke a scientific scorer")
        runtime = Path(runtime_root).absolute()
        package = runtime / "benchmarks/neuroscience" / ("neural-007-whole-night-sleep-scoring" if p["task_id"] == "NEURAL-007" else "neural-077")
        current = REPO / "benchmarks/neural" / p["task_id"] / "implementations/registered-runtime"
        # Exact published closure, including unmodified historical pins. The CLI
        # performs its own native dependency, mount, source and target admission.
        verify_tree(current, p["scorer_source"])
        verify_tree(package, p["scorer_source"])
        args = [sys.executable, "-I", "-B", str(package / "score.py")]
        if p["task_id"] == "NEURAL-077":
            args.append("score")
        args += ["--submission", str(root / "submission.npz"), "--output", str(root / "native-score")]
        record(root, "native_grader_dispatch", source=inventory(package), argv=args,
               resource_admission="existing native Docker scorer, 4 GiB, unchanged")
        completed = subprocess.run(args, cwd=runtime, capture_output=True, timeout=90, check=False,
                                   env={"PATH": os.environ.get("PATH", os.defpath), **{k: "2" for k in THREADS}})
        (root / "grader.stdout").write_bytes(completed.stdout)
        (root / "grader.stderr").write_bytes(completed.stderr)
        record(root, "native_grader_exited", returncode=completed.returncode,
               stdout=pin(root / "grader.stdout", empty=True), stderr=pin(root / "grader.stderr", empty=True))
        require(completed.returncode == 0, "Native grader failed; retained operator failure, no fallback score")
    _grade_gate(root, native, memory_budget_bytes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--task", choices=sorted(COUNTS), required=True)
    p.add_argument("--asset-root", required=True)
    p.add_argument("--run", required=True)
    p = sub.add_parser("commit")
    p.add_argument("--run", required=True)
    p.add_argument("--source", required=True)
    p.add_argument("--entrypoint", default="candidate.py")
    for action in ("execute", "freeze", "inspect"):
        sub.add_parser(action).add_argument("--run", required=True)
    p = sub.add_parser("grade")
    p.add_argument("--run", required=True)
    p.add_argument("--runtime-root", required=True)
    p.add_argument("--memory-budget-bytes", type=int, default=2 * 1024**3)
    args = parser.parse_args()
    if args.action == "prepare":
        prepare(args.task, args.asset_root, args.run)
    elif args.action == "commit":
        commit(args.run, args.source, args.entrypoint)
    elif args.action == "execute":
        execute(args.run)
    elif args.action == "freeze":
        freeze(args.run)
    elif args.action == "grade":
        grade(args.run, args.runtime_root, args.memory_budget_bytes)
    else:
        print(json.dumps(events(args.run), indent=2))


if __name__ == "__main__":
    main()
