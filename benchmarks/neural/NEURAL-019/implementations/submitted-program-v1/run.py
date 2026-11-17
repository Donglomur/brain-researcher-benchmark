#!/usr/bin/env python3
"""NEURAL-019 full-panel submitted program, isolated capture and target-last grade."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import time
import types
import uuid

HERE = Path(__file__).absolute().parent
SOURCE_FILES = ("run.py", "worker.py", "DEPENDENCIES.json")
TRANSPORT = "benchmarks/neural/NEURAL-007/implementations/whole-night-programme/program/vendor_transport"
SCORER = "benchmarks/neural/NEURAL-019/implementations/portable-score-v2"
ASSETS = "benchmarks/neural/NEURAL-019/implementations/registered-runtime/assets.json"
PUBLIC_FILES = {"packet": "public.npz", "manifest": "public_manifest.json"}
RESOURCES = {
    "setup_seconds": 30, "producer_seconds": 20, "capture_seconds": 15, "cleanup_seconds": 15,
    "memory_bytes": 3221225472, "cpu_nanos": 1750000000, "pids": 64, "scratch_bytes": 67108864,
    "max_files": 3, "max_directories": 1, "max_file_bytes": 1048576, "max_output_bytes": 8388608,
    "manifest_bytes": 4096, "max_cli_calls": 128, "max_cli_bytes": 8388608,
    "inventory_bytes": 65536, "source_read_bytes": 268435456, "host_write_bytes": 8388608,
}


def need(ok, text):
    if not ok:
        raise ValueError(text)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def pin(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, "Duplicate JSON key")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: need(False, "Nonfinite JSON"))


def literal(value):
    path = Path(value)
    need(path.is_absolute() and ".." not in path.parts, "Absolute canonical path required")
    need(not any(p.is_symlink() for p in (path, *path.parents)), "No linked path or ancestor")
    return path


def read(path, cap, expected=None):
    path = literal(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        first = os.fstat(fd)
        need(stat.S_ISREG(first.st_mode) and first.st_nlink == 1 and 0 < first.st_size <= cap,
             "Bounded single-link ordinary file")
        chunks, count = [], 0
        while count <= first.st_size:
            raw = os.read(fd, min(65536, first.st_size + 1 - count))
            if not raw:
                break
            chunks.append(raw)
            count += len(raw)
        last = os.fstat(fd)
        fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "st_nlink")
        need(count == first.st_size and all(getattr(first, k) == getattr(last, k) for k in fields)
             and all(getattr(first, k) == getattr(path.lstat(), k) for k in fields), "Stable complete source")
    finally:
        os.close(fd)
    body = b"".join(chunks)
    if expected is not None:
        need(pin(body) == expected, "Source/input pin mismatch")
    return body


def publish(path, raw, mode=0o400):
    need(len(raw) <= 262144, "Bounded task metadata/source publication")
    fd = os.open(literal(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return pin(raw)


def dependency_sources(repository):
    repository = literal(repository)
    manifest = decode(read(HERE / "DEPENDENCIES.json", 65536))
    need(set(manifest) == {"schema", "accepted_commit", "files"}
         and manifest["schema"] == "neural019_source_dependencies_v1", "Exact dependency manifest")
    result = {}
    for name, expected in manifest["files"].items():
        need(not Path(name).is_absolute() and ".." not in Path(name).parts, "Relative dependency")
        result[name] = read(repository / name, 262144, expected)
    return manifest, result


def load_dependencies(repository):
    manifest, bodies = dependency_sources(repository)
    package = "_neural019_transport_" + uuid.uuid4().hex
    module = types.ModuleType(package)
    module.__path__ = []
    sys.modules[package] = module
    result = {}
    for name in ("engine", "bounds", "contract", "archive", "provider"):
        filename = TRANSPORT + "/" + name + ".py"
        obj = types.ModuleType(package + "." + name)
        obj.__package__ = package
        obj.__file__ = str(Path(repository) / filename)
        sys.modules[obj.__name__] = obj
        exec(compile(bodies[filename], obj.__file__, "exec"), obj.__dict__)
        result[name] = obj
    filename = SCORER + "/score.py"
    scorer = types.ModuleType("_neural019_original_scorer")
    scorer.__file__ = str(Path(repository) / filename)
    exec(compile(bodies[filename], scorer.__file__, "exec"), scorer.__dict__)
    return result, scorer, manifest


def file_mount(path, expected, purpose):
    return {"path": str(path), "kind": "file", "purpose": purpose, "files": {Path(path).name: expected}}


def source_identity():
    return {name: pin(read(HERE / name, 65536)) for name in SOURCE_FILES}


def stage(repository, candidate, public_root, output, image):
    """Commit submitted source first; stage no public numerical payload bodies."""
    repository, candidate, output = map(literal, (repository, candidate, output))
    need(re.fullmatch(r"sha256:[0-9a-f]{64}", image), "Immutable already-local image ID required")
    need(output.parent.is_dir() and not output.exists(), "Fresh stage under existing parent")
    candidate_body = read(candidate, 65536)
    candidate_body.decode("utf-8")  # Original single UTF-8 Python source contract.
    sources = source_identity()
    output.mkdir(mode=0o700)
    candidate_pin = publish(output / "program.py", candidate_body, 0o444)
    worker_pin = publish(output / "worker.py", read(HERE / "worker.py", 65536), 0o444)
    source = {"schema": "neural019_frozen_source_v1", "candidate": candidate_pin, "operator": sources}
    source_pin = publish(output / "SOURCE.json", encoded(source))
    publish(output / "PROGRAM_COMMIT.json", encoded({"source": source_pin, "committed_at_monotonic": time.monotonic(),
            "candidate_frozen_before_public_release": True, "blind_authoring_certified": False}))
    # The two public asset identities come from the already accepted scorer.
    # Neither private operand is named or accessed in this preparation phase.
    manifest, bodies = dependency_sources(repository)
    assets = decode(bodies[ASSETS])["public"]
    public_root = literal(public_root)
    mounts = {}
    for name, filename in PUBLIC_FILES.items():
        row = assets[name]
        mounts["/input/" + filename] = file_mount(public_root / filename,
            {k: row[k] for k in ("bytes", "sha256")}, "input")
    mounts["/program/program.py"] = file_mount(output / "program.py", candidate_pin, "program")
    mounts["/program/worker.py"] = file_mount(output / "worker.py", worker_pin, "program")
    command = ["/usr/local/bin/python", "-I", "-B", "/program/worker.py"]
    plan = {"schema": "neural019_frozen_batch_v1", "source": source_pin, "image": image, "command": command,
            "mounts": mounts, "resources": RESOURCES, "source_dependencies": pin(encoded(manifest)),
            "native_execution_qualified": False}
    plan_pin = publish(output / "PLAN.json", encoded(plan))
    # This is a review input, deliberately not an approved exposure assertion.
    publish(output / "EXPOSURE_REQUEST.json", encoded({"schema": "neural019_exposure_review_request_v1",
        "role": "A", "image": image, "source": source_pin, "command": command,
        "mounts": {k: {n: v for n, v in d.items() if n != "path"} for k, d in sorted(mounts.items())},
        "requires_independent_image_inventory_and_boundary_review": True}))
    return plan_pin


def checked_plan(repository, stage_root, expected_plan):
    stage_root = literal(stage_root)
    plan = decode(read(stage_root / "PLAN.json", 65536, expected_plan))
    need(set(plan) == {"schema", "source", "image", "command", "mounts", "resources", "source_dependencies", "native_execution_qualified"}
         and plan["schema"] == "neural019_frozen_batch_v1" and plan["resources"] == RESOURCES,
         "Exact task-local frozen batch")
    source = decode(read(stage_root / "SOURCE.json", 65536, plan["source"]))
    commitment = decode(read(stage_root / "PROGRAM_COMMIT.json", 4096))
    need(commitment["source"] == plan["source"] and commitment["candidate_frozen_before_public_release"] is True,
         "Pre-query program commitment exists")
    need(source == {"schema": "neural019_frozen_source_v1", "candidate": source["candidate"], "operator": source_identity()},
         "Current operator source equals pre-query freeze")
    need(plan["command"] == ["/usr/local/bin/python", "-I", "-B", "/program/worker.py"], "Container-only task worker")
    manifest, bodies = dependency_sources(repository)
    need(plan["source_dependencies"] == pin(encoded(manifest)), "Same accepted source closure")
    assets = decode(bodies[ASSETS])["public"]
    expected = {"/program/program.py": file_mount(stage_root / "program.py", source["candidate"], "program"),
                "/program/worker.py": file_mount(stage_root / "worker.py", source["operator"]["worker.py"], "program")}
    for name, filename in PUBLIC_FILES.items():
        row = assets[name]
        key = "/input/" + filename
        supplied = plan["mounts"][key]
        path = literal(supplied["path"])
        need(path.name == filename, "Exact public filename")
        expected[key] = file_mount(path, {k: row[k] for k in ("bytes", "sha256")}, "input")
    need(plan["mounts"] == expected, "Only two original public assets and committed code mounted")
    read(stage_root / "program.py", 65536, source["candidate"])
    read(stage_root / "worker.py", 65536, source["operator"]["worker.py"])
    return plan


def admit_capture(result, observed, request, mounts, provider, engine):
    receipt = observed["receipt"]
    need(observed["receipt_pin"] == result["receipt_pin"] and pin(engine.encoded(receipt)) == result["receipt_pin"],
         "Independent receipt identity")
    need(receipt["status"] == "captured" and receipt["producer_closed_before_capture"] is True
         and receipt["all_native_resources_closed"] is True and receipt["cli_reaped"] is True,
         "Removed producer and complete owned-resource closure before grading")
    timing = receipt["timing"]
    need(receipt["deadline_exceeded"] is False
         and timing["original_deadline"] == request["clock"]["phase_deadline"]
         and request["clock"]["origin"] <= timing["started"] <= timing["finished"] <= timing["phase_deadline"]
         <= request["clock"]["phase_deadline"], "Completed capture inside unchanged original deadline")
    engine.validate_natural_exit(receipt["natural_exit"])
    for key in ("phase_id", "action", "role", "image", "source", "exposure"):
        need(receipt[key] == request[key], "Exact receipt/request " + key)
    need(receipt["request_sha256"] == pin(engine.encoded(request))["sha256"], "Exact request identity")
    expected = {k: {n: v for n, v in d.items() if n != "path"} for k, d in sorted(mounts.items())}
    need(receipt["input_before"] == receipt["input_after"] == expected, "Unchanged exact public exposure")
    capture = receipt["output_inventory"]
    need(capture["complete"] is True and set(capture["files"]) == {"predictions.npz", "RESULT.json", "OUTPUTS.json"},
         "Complete three-file capture; no diagnostic/private extras")
    root = literal(provider.quarantine_root) / request["phase_id"]
    need(receipt["quarantine_root"] == str(root), "Owned capture root")
    body = read(root / "predictions.npz", 1048576, capture["files"]["predictions.npz"])
    return root / "predictions.npz", body, capture["files"]["predictions.npz"]


def execute(repository, stage_root, expected_plan, configuration, target, reference_grade, reference_commit, output, *, provider_factory=None):
    """Production CLI always chooses concrete Docker; injectable provider is test-only."""
    import signal
    if provider_factory is None:
        timer = signal.getitimer(signal.ITIMER_REAL)
        need(timer[0] > 0 and timer[1] == 0, "Production execution requires the bounded dedicated CLI")
    started = time.monotonic()
    plan = checked_plan(repository, stage_root, expected_plan)
    modules, scorer, dependencies = load_dependencies(repository)
    engine = modules["engine"]
    need(set(configuration) == {"docker_binary", "docker_socket", "control_root", "quarantine_root", "exposure_path", "exposure_pin"},
         "Exact operator transport configuration")
    exposure_path = literal(configuration["exposure_path"])
    exposure = decode(read(exposure_path, 65536, configuration["exposure_pin"]))
    request = {"schema": "osl_owned_phase_request_v1", "phase_id": "neural019-" + uuid.uuid4().hex,
        "action": "held_attempt", "role": "A", "image": plan["image"], "command": plan["command"], "workdir": "/work",
        "source": plan["source"], "exposure": configuration["exposure_pin"],
        "clock": {"origin": started, "phase_deadline": started + 90}, "resources": RESOURCES,
        "output": {"kind": "generic", "manifest": "OUTPUTS.json"}}
    modules["contract"].validate_request(request, plan["mounts"], started + 90)
    modules["contract"].validate_exposure(exposure, request, plan["mounts"])
    output = literal(output)
    need(output.parent.is_dir() and not output.exists(), "Fresh lifecycle output")
    output.mkdir(mode=0o700)
    publish(literal(stage_root) / "ATTEMPT.json", encoded({"request": pin(engine.encoded(request)),
        "phase_id": request["phase_id"], "output": str(output), "automatic_retry": False}))
    publish(output / "REQUEST.json", engine.encoded(request))
    factory = modules["provider"].Provider if provider_factory is None else provider_factory
    provider = factory(configuration["control_root"], configuration["quarantine_root"],
        configuration["docker_binary"], configuration["docker_socket"],
        dependencies["files"][TRANSPORT + "/SOURCE_MANIFEST.json"],
        {configuration["exposure_pin"]["sha256"]: str(exposure_path)},
        RESOURCES["source_read_bytes"] + 262144, RESOURCES["host_write_bytes"])
    journal = []
    receipt = {"schema": "neural019_program_lifecycle_v1", "status": "operator_error", "source": plan["source"],
        "plan": expected_plan, "request": pin(engine.encoded(request)), "private_target_loads": 0,
        "engine_qualification_inherited": False, "native_understanding_measured": False,
        "test_provider": provider_factory is not None, "authentic_performance_established": False}
    try:
        result = provider.execute_phase(request, plan["mounts"], started + 90, lambda name, value: journal.append(name))
        observed = provider.observe(request["phase_id"], pin(engine.encoded(request))["sha256"], result["receipt_pin"], started + 90)
        receipt["transport_receipt"] = result["receipt_pin"]
        submission, body, submission_pin = admit_capture(result, observed, request, plan["mounts"], provider, engine)
        need(time.monotonic() < started + 90, "Grading requires completed original execution clock")
        receipt["submission"] = submission_pin
        # The original scorer copies, binds and validates the complete six-field
        # submission before resolving any private operand. Bind its initial
        # digest to the already captured bytes, rather than accepting a fresh
        # pathname identity after a post-capture substitution.
        old_timer = signal.getitimer(signal.ITIMER_REAL)
        score_started = time.monotonic()
        if provider_factory is None:
            need(old_timer[0] > 0 and old_timer[1] == 0, "Production execution requires the bounded dedicated CLI")
            signal.setitimer(signal.ITIMER_REAL, min(30, old_timer[0]))
        original_sha = scorer.contract.sha
        def bound_sha(path):
            digest = original_sha(path)
            if Path(path) == submission:
                need(digest == submission_pin["sha256"], "Exact captured submission identity")
            return digest
        scorer.contract.sha = bound_sha
        try:
            scored, exit_code = scorer.evaluate("score", submission, plan["mounts"]["/input/public.npz"]["path"],
                private_targets=target, reference_grade=reference_grade, reference_commit=reference_commit)
        finally:
            scorer.contract.sha = original_sha
            if provider_factory is None:
                signal.setitimer(signal.ITIMER_REAL, max(0.001, old_timer[0] - (time.monotonic() - score_started)))
        if scored["prediction_contract_valid"]:
            need(scored["submission_sha256"] == submission_pin["sha256"], "Final score binds the captured prediction")
        receipt.update(status=scored["status"], private_target_loads=scored["target_loader_invocations"],
            scorer_exit_code=exit_code, score=publish(output / "SCORE.json", encoded(scored)))
        return receipt
    except Exception as error:
        receipt["error"] = type(error).__name__ + ": " + str(error)[:1000]
        raise
    finally:
        receipt["wall_seconds"] = time.monotonic() - started
        receipt["transport_events"] = journal
        publish(output / "LIFECYCLE.json", encoded(receipt))


def main():
    import resource
    import signal
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    freeze = commands.add_parser("stage")
    for name in ("repository", "candidate", "public-root", "output", "image"):
        freeze.add_argument("--" + name, required=True)
    run = commands.add_parser("run")
    for name in ("repository", "stage", "plan-sha256", "configuration", "target", "reference-grade", "reference-commit", "output"):
        run.add_argument("--" + name, required=True)
    run.add_argument("--plan-bytes", type=int, required=True)
    args = parser.parse_args()
    for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ[key] = "1"
    need(signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0), "Dedicated operator process required")
    def expired(*_):
        raise TimeoutError("Original 120-second operator deadline; inspect owned transport receipt before recovery")
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, 120)
    soft, hard = resource.getrlimit(resource.RLIMIT_CPU)
    resource.setrlimit(resource.RLIMIT_CPU, (min([20] + [x for x in (soft, hard) if x != resource.RLIM_INFINITY]), hard))
    try:
        if args.command == "stage":
            value = stage(args.repository, args.candidate, args.public_root, args.output, args.image)
        else:
            value = execute(args.repository, args.stage, {"bytes": args.plan_bytes, "sha256": args.plan_sha256},
                decode(read(args.configuration, 65536)), args.target, args.reference_grade, args.reference_commit, args.output)
        print(json.dumps(value, sort_keys=True, allow_nan=False))
        return 0 if args.command == "stage" or value["status"] == "scored" else 2
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == "__main__":
    raise SystemExit(main())
