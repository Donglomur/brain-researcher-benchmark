"""NuCLR's explicit current setuptools backend entry point; no installer/resolver.

Run only inside the separately admitted offline, quota-limited build sandbox.
This driver does not enforce or establish OS memory/storage/network isolation.
"""
from __future__ import annotations
import argparse
import contextlib
import hashlib
import importlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import platform
import selectors
import signal
import stat
import subprocess
import sys
import time

CONDITION = "nuclr-current-cpu-source-wheels-v1"
SOURCES = {
    "temporaldata": "b0a92bf4f9e36e27c5eddbf02c8acbd5df90ee39",
    "brainsets": "61c8a7bc4fb39412a4d2f12c6209936606d4c12f",
    "pytorch_brain": "d48b0c822fbcaa27e15ba982bd6f619ed4260cd7",
    "antlr4-python3-runtime": "f224469b4168294902bb1efa80a8bf7855f24c99aef99cbefc1bcd3cce77881b",
}
BUILD_BASE = {"setuptools": "80.9.0"}
BRAINSETS_EXTRA = {"setuptools-scm": "10.3.4", "vcs-versioning": "2.5.0", "packaging": "26.3"}
MAX_PROFILE = 2 * 1024 * 1024
MAX_LOG = 1024 * 1024
MAX_WHEEL = 16 * 1024 * 1024
MAX_RECEIPT = 256 * 1024

class Refusal(ValueError):
    pass

class OwnedCancellation(RuntimeError):
    """Cancellation must escape selectors' handling of InterruptedError."""
    pass

def require(value, message):
    if not value:
        raise Refusal(message)

def canonical_name(value):
    return value.lower().replace("_", "-").replace(".", "-")

def descriptor(path, limit=MAX_PROFILE):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), "Expected regular nonsymlink file")
    size = path.stat().st_size
    require(size <= limit, "File extent exceeded")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return {"bytes": size, "sha256": digest.hexdigest()}

def read_pinned(path, pin, limit=MAX_PROFILE):
    require(descriptor(path, limit) == pin, "File identity mismatch: " + str(path))
    return json.loads(Path(path).read_bytes())

def safe_child(root, relative):
    require(isinstance(relative, str) and relative, "Empty member")
    part = PurePosixPath(relative)
    require(not part.is_absolute() and all(x not in (".", "..", "") for x in part.parts), "Unsafe member")
    require(str(part) == relative and "\\" not in relative, "Noncanonical member")
    current = Path(root)
    for item in part.parts:
        current = current / item
        require(not current.is_symlink(), "Symlink member")
    require(current.resolve().is_relative_to(Path(root).resolve()), "Member escaped root")
    return current

def verify_members(root, members):
    require(isinstance(members, list) and 0 < len(members) <= 20000, "Missing/oversized source roster")
    seen = set()
    records = []
    for row in members:
        require(set(row) == {"path", "bytes", "sha256", "mode"}, "Unexpected source descriptor")
        require(row["path"] not in seen, "Duplicate source member")
        seen.add(row["path"])
        path = safe_child(root, row["path"])
        require(descriptor(path, 16 * 1024 * 1024) == {k: row[k] for k in ("bytes", "sha256")}, "Source changed: " + row["path"])
        require(stat.S_IMODE(path.stat().st_mode) == row["mode"], "Source mode changed: " + row["path"])
        records.append(dict(row))
    return records

def validate_profile(profile):
    require(profile.get("schema") == "nuclr-backend-profile/v1", "Wrong build profile")
    require(profile.get("driver") == descriptor(Path(__file__).resolve()), "Build driver identity mismatch")
    require(profile.get("condition") == CONDITION, "Wrong named condition")
    project = profile.get("project")
    require(project in SOURCES, "Unselected project")
    require(profile.get("source_identity") == SOURCES[project], "Wrong original source revision")
    require(profile.get("backend") == "setuptools.build_meta", "Backend substitution")
    require(profile.get("backend_config_settings") is None, "Unreviewed backend configuration")
    require(isinstance(profile.get("interpreter"), dict) and set(profile["interpreter"]) == {"path", "resolved_path", "bytes", "sha256"}, "Missing exact interpreter pin")
    expected = dict(BUILD_BASE)
    if project == "brainsets":
        expected.update(BRAINSETS_EXTRA)
    require(profile.get("build_distributions") == expected, "Build environment differs from selected plan")
    require(profile.get("python") == {"implementation": "CPython", "version": "3.11.18", "system": "Linux", "machine": "x86_64"}, "Wrong CPU runtime profile")
    require(profile.get("max_seconds") == 120 and profile.get("max_log_bytes") == MAX_LOG and profile.get("max_wheel_bytes") == MAX_WHEEL, "Unreviewed resource limits")
    require(isinstance(profile.get("hook_requirement_pins"), dict), "Missing literal requirement pins")
    for literal, row in profile["hook_requirement_pins"].items():
        require(isinstance(literal, str) and len(literal) <= 4096, "Invalid requirement key")
        require(set(row) == {"name", "version", "extras"}, "Invalid requirement pin")
        require(row["name"] in expected and row["version"] == expected[row["name"]], "Requirement is not in admitted environment")
        require(isinstance(row["extras"], list) and all(isinstance(x, str) for x in row["extras"]), "Invalid extras pin")
    require(profile.get("source_root") and Path(profile["source_root"]).is_absolute(), "Source cwd must be absolute")
    require(profile.get("environment_root") and Path(profile["environment_root"]).is_absolute(), "Environment root must be absolute")
    require(profile.get("backend_module") and profile.get("requirement_parser_module"), "Missing authenticated backend/parser module")
    if project == "brainsets":
        require(profile.get("brainsets_context", {}).get("commit") == SOURCES[project], "Missing genuine brainsets context")
        require(profile["brainsets_context"].get("root_tree") == "2ded1667f32794d5fc83ec93d75c558272bc9a10", "Wrong brainsets tree")
        require(profile["brainsets_context"].get("tracked_blobs") == 98, "Incomplete brainsets source")
        require(len(profile.get("source_files", [])) == 98, "Incomplete brainsets source roster")
    return profile

def authenticate_admission(profile, profile_pin, admission):
    require(admission.get("schema") == "nuclr-build-sandbox-admission/v1", "Missing sandbox admission")
    require(admission.get("condition") == CONDITION and admission.get("project") == profile["project"], "Admission identity mismatch")
    require(admission.get("profile") == profile_pin, "Admission profile mismatch")
    require(admission.get("selected_execution") is True, "Build execution not selected")
    require(admission.get("source_materialization_verified") is True, "Source materialization not verified")
    require(admission.get("installed_build_environment_verified") is True, "Build environment not qualified")
    # These are authenticated trusted-controller evidence references, not this
    # program claiming that booleans themselves enforce OS isolation.
    for key in ("source_evidence", "environment_evidence", "os_isolation_evidence"):
        row = admission.get(key)
        require(isinstance(row, dict) and set(row) == {"path", "bytes", "sha256"}, "Missing admission evidence: " + key)
        require(descriptor(row["path"]) == {k: row[k] for k in ("bytes", "sha256")}, "Admission evidence changed")
    if profile["project"] == "brainsets":
        require(admission.get("genuine_git_context_verified") is True, "No authentic complete brainsets Git context")
    return admission

def admit_requirements(literals, pins, installed, requirement_type):
    require(isinstance(literals, list) and len(literals) <= 64 and all(isinstance(x, str) and len(x) <= 4096 for x in literals), "Malformed hook requirement list")
    decisions = []
    for literal in literals:
        require(literal in pins, "Unpinned dynamic requirement: " + literal)
        row = pins[literal]
        item = requirement_type(literal)
        name = canonical_name(item.name)
        require(not item.url, "Direct URL dynamic requirement refused")
        require(name == row["name"] and sorted(item.extras) == sorted(row["extras"]), "Dynamic requirement semantics differ from pin")
        active = item.marker is None or item.marker.evaluate({"extra": ""})
        if active:
            require(installed.get(name) == row["version"], "Dynamic requirement distribution missing/wrong")
            require(item.specifier.contains(row["version"], prereleases=True), "Installed dynamic requirement is unsatisfied")
        decisions.append({"literal": literal, "active": active, "name": name, "version": row["version"], "extras": row["extras"]})
    return decisions

def write_exclusive_json(path, value):
    raw = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    require(len(raw) <= MAX_RECEIPT, "Receipt extent exceeded")
    with Path(path).open("xb") as handle:
        handle.write(raw)

def generated_members(root, source_files):
    """Record generated source outputs separately; never follow symlinks."""
    expected = {row["path"] for row in source_files}
    generated = []
    for directory, dirs, files in os.walk(root, followlinks=False):
        if Path(directory) == Path(root):
            dirs[:] = [name for name in dirs if name != ".git"]
        for name in dirs:
            require(not (Path(directory) / name).is_symlink(), "Generated symlink directory")
        for name in files:
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            if relative not in expected:
                require(not path.is_symlink() and path.is_file(), "Generated nonregular source output")
                generated.append({"path": relative, "bytes": path.stat().st_size})
                require(len(generated) <= 1024, "Generated source output roster exceeded")
    return sorted(generated, key=lambda row: row["path"])

def build_core(backend, requirement_type, profile, installed, outdir, stage):
    """Same source-invariance/hook/output core used by the CLI and doubles."""
    before = verify_members(profile["source_root"], profile["source_files"])
    stage["source_pre"] = before
    stage["preexisting_untracked_members"] = generated_members(Path(profile["source_root"]), profile["source_files"])
    stage["stage"] = "get_requires_for_build_wheel"
    literals = backend.get_requires_for_build_wheel(config_settings=None)
    valid_literals = isinstance(literals, list) and len(literals) <= 64 and all(isinstance(x, str) and len(x) <= 4096 for x in literals) and sum(len(x) for x in literals) <= 16384
    if valid_literals:
        stage["literal_hook_requires"] = literals
    else:
        stage["malformed_hook_return_type"] = type(literals).__name__
    require(valid_literals, "Malformed or oversized hook requirement list")
    # Verify before any build even if requirement admission is about to fail.
    stage["source_after_requirements"] = verify_members(profile["source_root"], profile["source_files"])
    stage["requirement_decisions"] = admit_requirements(literals, profile["hook_requirement_pins"], installed, requirement_type)
    stage["stage"] = "build_wheel"
    wheels = Path(outdir) / "wheels"
    wheels.mkdir()
    wheel = backend.build_wheel(str(wheels), config_settings=None, metadata_directory=None)
    if isinstance(wheel, str) and len(wheel) <= 512:
        stage["build_wheel_return"] = wheel
    else:
        stage["malformed_wheel_return_type"] = type(wheel).__name__
    require(isinstance(wheel, str) and len(wheel) <= 512, "Malformed or oversized wheel name")
    stage["source_post"] = verify_members(profile["source_root"], profile["source_files"])
    stage["generated_source_members"] = generated_members(Path(profile["source_root"]), profile["source_files"])
    require(isinstance(wheel, str) and Path(wheel).name == wheel and wheel.endswith(".whl"), "Unsafe wheel result")
    members = list(wheels.iterdir())
    require(len(members) == 1 and members[0].name == wheel, "Unexpected wheel outputs")
    artifact = safe_child(wheels, wheel)
    stage["wheel"] = {"name": wheel, **descriptor(artifact, profile["max_wheel_bytes"])}
    stage["status"] = "backend_completed_uninstalled_unqualified"
    stage["stage"] = "complete"
    # Wheel RECORD/ABI/discovery/installed source matching are separate admission
    # gates. A filename or a hook result is not wheel validity or runtime parity.
    return stage

def authenticate_runtime(profile):
    observed = {"implementation": platform.python_implementation(), "version": platform.python_version(), "system": platform.system(), "machine": platform.machine()}
    require(observed == profile["python"], "Actual Python/platform mismatch")
    interpreter = profile["interpreter"]
    require(str(Path(sys.executable)) == interpreter["path"] and str(Path(sys.executable).resolve()) == interpreter["resolved_path"], "Actual interpreter path mismatch")
    require(descriptor(interpreter["resolved_path"], 64 * 1024 * 1024) == {k: interpreter[k] for k in ("bytes", "sha256")}, "Actual interpreter identity mismatch")
    actual = {}
    for dist in importlib.metadata.distributions():
        name = canonical_name(dist.metadata["Name"])
        require(name not in actual, "Duplicate installed distribution")
        actual[name] = dist.version
    require(actual == profile["build_distributions"], "Actual build distribution inventory mismatch")
    verify_members(profile["environment_root"], profile["environment_files"])
    return actual

def import_authenticated(module_name, expected, root):
    path = safe_child(root, expected["path"])
    require(descriptor(path) == {k: expected[k] for k in ("bytes", "sha256")}, "Module source mismatch")
    module = importlib.import_module(module_name)
    require(Path(module.__file__).resolve() == path.resolve(), "Imported module shadowed")
    return module

def worker(profile_path, admission_path, outdir, profile_pin, admission_pin):
    stage = {"schema": "nuclr-backend-direct-build/v1", "condition": CONDITION, "status": "failed", "stage": "admission", "profile": profile_pin, "admission": admission_pin, "original_runtime_qualified": False, "scientific_result": False, "os_isolation_enforced_by_driver": False}
    profile = None
    try:
        profile = validate_profile(read_pinned(profile_path, profile_pin))
        stage["project"] = profile["project"]
        authenticate_admission(profile, profile_pin, read_pinned(admission_path, admission_pin))
        os.chdir(profile["source_root"])
        stage["stage"] = "environment_authentication"
        actual = authenticate_runtime(profile)
        stage["actual_build_distributions"] = actual
        stage["stage"] = "backend_import"
        backend = import_authenticated("setuptools.build_meta", profile["backend_module"], profile["environment_root"])
        parser = import_authenticated("setuptools._vendor.packaging.requirements", profile["requirement_parser_module"], profile["environment_root"])
        stage["backend_module"] = profile["backend_module"]
        stage["requirement_parser_module"] = profile["requirement_parser_module"]
        build_core(backend, parser.Requirement, profile, actual, outdir, stage)
    except BaseException as exc:
        stage["status"] = "failed"
        stage["error"] = {"type": type(exc).__name__, "message": str(exc)[:4096]}
        if profile is not None:
            try:
                stage["source_after_failure"] = verify_members(profile["source_root"], profile["source_files"])
            except BaseException as changed:
                stage["source_after_failure_error"] = str(changed)[:4096]
    write_exclusive_json(Path(outdir) / "backend-receipt.json", stage)
    return 0 if stage["status"] == "backend_completed_uninstalled_unqualified" else 1

def clean_environment(outdir, executable):
    home = Path(outdir) / "home"
    temp = Path(outdir) / "tmp"
    home.mkdir(); temp.mkdir()
    return {"PATH": str(Path(executable).parent) + ":/usr/bin:/bin", "HOME": str(home), "TMPDIR": str(temp), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_TERMINAL_PROMPT": "0", "PIP_NO_INDEX": "1", "PIP_DISABLE_PIP_VERSION_CHECK": "1", "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}

def run_owned(argv, cwd, env, log_path, seconds, limit):
    """Own one new worker group; retain the leader until all group signals end.

    No poll()/wait() may reap the leader before the final killpg. Holding its
    unreaped PID prevents a reused PID/PGID from being mistaken for this worker.
    EOF followed by cleanup is expected: the worker writes its receipt and exits.
    The last five seconds are reserved for owned cleanup within the outer limit.
    """
    require(seconds > 5, "No cleanup time reserved")
    process = None
    count = 0
    error = None
    cleanup_error = None
    leader_reaped = False
    started = time.monotonic()
    handlers = {}
    def interrupted(signum, frame):
        raise OwnedCancellation("Owned backend observer received signal " + str(signum))
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        handlers[sig] = signal.signal(sig, interrupted)
    try:
        with Path(log_path).open("xb") as output:
            try:
                process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, close_fds=True, start_new_session=True)
                with selectors.DefaultSelector() as select:
                    select.register(process.stdout, selectors.EVENT_READ)
                    while select.get_map():
                        require(time.monotonic() - started <= seconds - 5, "Backend deadline exceeded")
                        for key, _ in select.select(0.05):
                            chunk = os.read(key.fd, min(65536, limit + 1 - count))
                            if not chunk:
                                select.unregister(key.fileobj); continue
                            count += len(chunk)
                            output.write(chunk)
                            require(count <= limit, "Backend output extent exceeded")
            except BaseException as exc:
                error = type(exc).__name__ + ": " + str(exc)[:4096]
            finally:
                # A second cancellation cannot interrupt the bounded owned reap.
                for sig in handlers:
                    signal.signal(sig, signal.SIG_IGN)
                if process is not None:
                    for stop_signal in (signal.SIGTERM, signal.SIGKILL):
                        try:
                            os.killpg(process.pid, stop_signal)
                        except ProcessLookupError:
                            break
                        except OSError as exc:
                            # Preserve denial; never try another signal/route.
                            cleanup_error = type(exc).__name__ + ": " + str(exc)[:4096]
                            break
                        if stop_signal == signal.SIGTERM:
                            time.sleep(0.05)
                    # First and only wait/reap occurs after the final attempted
                    # group signal, including a refusal. Reaping is not a retry.
                    try:
                        process.wait(timeout=3)
                        leader_reaped = True
                    except subprocess.TimeoutExpired as exc:
                        cleanup_error = (cleanup_error + "; " if cleanup_error else "") + "Owned leader reap timed out after final attempted group signal: " + str(exc)
                    process.stdout.close()
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)
    return {"leader_reaped": leader_reaped, "cleanup_error": cleanup_error, "pid": None if process is None else process.pid, "exit_code": None if process is None else process.returncode, "error": error, "output_bytes": count, "log": descriptor(log_path, limit + 1), "wall_seconds": time.monotonic() - started}

def run(profile_path, admission_path, outdir, profile_pin, admission_pin):
    profile = validate_profile(read_pinned(profile_path, profile_pin))
    authenticate_admission(profile, profile_pin, read_pinned(admission_path, admission_pin))
    output = Path(outdir)
    require(output.is_absolute(), "Output must be absolute")
    require(not output.exists() and not output.is_symlink(), "Output must be a new owned root")
    require(not output.resolve().is_relative_to(Path(profile["source_root"]).resolve()), "Output overlaps source root")
    output.mkdir()
    env = clean_environment(output, sys.executable)
    argv = [sys.executable, "-I", "-B", str(Path(__file__).resolve()), "--worker", "--profile", str(Path(profile_path).resolve()), "--admission", str(Path(admission_path).resolve()), "--output", str(output), "--profile-sha256", profile_pin["sha256"], "--admission-sha256", admission_pin["sha256"]]
    before = verify_members(profile["source_root"], profile["source_files"])
    result = run_owned(argv, profile["source_root"], env, output / "backend.log", profile["max_seconds"], profile["max_log_bytes"])
    result["source_pre"] = before
    result["generated_source_inventory_scope"] = "Names and final logical extents, not cumulative writes or physical quota enforcement"
    try:
        result["source_post"] = verify_members(profile["source_root"], profile["source_files"])
        result["generated_source_members"] = generated_members(Path(profile["source_root"]), profile["source_files"])
    except BaseException as changed:
        result["source_post_error"] = str(changed)[:4096]
        result["error"] = result["error"] or "Source changed after worker termination"
    result.update(schema="nuclr-backend-process/v1", profile=profile_pin, admission=admission_pin, argv=argv, original_runtime_qualified=False, scientific_result=False)
    write_exclusive_json(output / "process-receipt.json", result)
    return 0 if result["exit_code"] == 0 and result["error"] is None and result["cleanup_error"] is None and result["leader_reaped"] else 1

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--admission", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile-sha256", required=True)
    parser.add_argument("--admission-sha256", required=True)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    p = {"bytes": args.profile.stat().st_size, "sha256": args.profile_sha256}
    a = {"bytes": args.admission.stat().st_size, "sha256": args.admission_sha256}
    return (worker if args.worker else run)(args.profile, args.admission, args.output, p, a)

if __name__ == "__main__":
    raise SystemExit(main())
