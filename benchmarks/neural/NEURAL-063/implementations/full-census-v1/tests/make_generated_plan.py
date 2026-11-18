"""Construct a local, generated-only NEURAL-063 test plan; never run it."""
import argparse
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import stat
import sys


RUNTIME = {"h5py": "3.16.0", "fsspec": "2026.6.0", "aiohttp": "3.14.3"}
RANGE_FILES = {"manifest.py", "pipeline.py", "range_io.py", "ORIGINAL_SOURCES.json", "RUNTIME_SOURCES.json"}
ORIGINAL_FILES = {"owner/__init__.py", "owner/io.py", "owner/scoring.py",
                  "preparation/__init__.py", "preparation/algorithm.py", "preparation/native.py"}
STAGES = ("layouts", "metadata_support", "chunks")


def _json(body):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    def bad(_):
        raise ValueError("nonfinite JSON literal")
    return json.loads(body, object_pairs_hook=pairs, parse_constant=bad)


def _path(value, *, directory=False):
    p = Path(value).expanduser().resolve(strict=True)
    if len(str(p).encode()) > 1024:
        raise ValueError("bounded local source path required")
    mode = p.stat().st_mode
    if not (stat.S_ISDIR(mode) if directory else stat.S_ISREG(mode)):
        raise ValueError("ordinary local source path required")
    return p


def _capture(value, *, cap=4 * 1024 * 1024):
    p = _path(value)
    before = p.stat()
    if before.st_nlink != 1 or before.st_size > cap:
        raise ValueError("bounded unaliased source file required")
    body = p.read_bytes()
    after = p.stat()
    fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "st_nlink")
    if any(getattr(before, key) != getattr(after, key) for key in fields) or len(body) != before.st_size:
        raise ValueError("source changed during plan construction")
    return {"path": str(p), "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}, body


def build_plan(core_source, wrapper_source, range_source, original_root,
               operation_profiles, evidence_root, worker_source):
    """Return pinned generated-test inputs, with no writes or source imports."""
    if sys.version_info[:2] != (3, 11):
        raise ValueError("the selected generated-control profile requires Python3.11")
    core = _path(core_source, directory=True)
    wrapper = _path(wrapper_source)
    ranges = _path(range_source, directory=True)
    original = _path(original_root, directory=True)
    worker = _path(worker_source)
    if wrapper.name != "run.py" or worker.name != "test_census_generated.py":
        raise ValueError("fixed census wrapper and generated worker names required")
    if worker.parent not in (core, core / "tests"):
        raise ValueError("generated worker must belong to the selected census component")
    for root in (core, wrapper.parent, ranges):
        if (root / "__pycache__").exists():
            raise ValueError("uncached source roots required")
    raw_evidence = Path(evidence_root).expanduser()
    if raw_evidence.exists() or raw_evidence.is_symlink():
        raise ValueError("fresh generated evidence directory required")
    evidence = _path(raw_evidence.parent, directory=True) / raw_evidence.name
    if not raw_evidence.name or raw_evidence.name in (".", "..") or len(str(evidence).encode()) > 1024:
        raise ValueError("bounded fresh generated output name required")
    paths = {}

    def add(path, expected=None, cap=4 * 1024 * 1024):
        descriptor, body = _capture(path, cap=cap)
        if expected is not None and {key: descriptor[key] for key in ("bytes", "sha256")} != expected:
            raise ValueError("unchanged scientific/range dependency pin differs")
        paths[descriptor["path"]] = descriptor
        return body

    closure = _json(add(wrapper.parent / "DEPENDENCIES.json", cap=65536))
    if (closure.get("schema") != "neural063-full-census-source-dependency-closure-v1"
            or closure.get("runtime_versions") != RUNTIME
            or set(closure.get("range_source_files", {})) != RANGE_FILES
            or set(closure.get("original_files", {})) != ORIGINAL_FILES):
        raise ValueError("exact unchanged range/scientific dependency closure required")
    add(core / "census.py")
    add(wrapper)
    add(worker)
    helper = _path(__file__)
    add(helper)
    for name, expected in sorted(closure["range_source_files"].items()):
        add(ranges / name, expected)
    for name, expected in sorted(closure["original_files"].items()):
        target = original / name
        if (target.parent / "__pycache__").exists():
            raise ValueError("uncached original scientific source required")
        add(target, expected)
    if not isinstance(operation_profiles, (tuple, list)) or len(operation_profiles) != 3:
        raise ValueError("exact three unselected census profiles required")
    profiles = []
    for stage, path in zip(STAGES, operation_profiles):
        p = _path(path)
        if p.name != stage + ".json":
            raise ValueError("fixed census profile order and names required")
        value = _json(add(p, cap=65536))
        if (value.get("schema") != "neural063_full_census_operation_profile_v1"
                or value.get("stage") != stage or value.get("selected") is not False
                or value.get("runtime_qualified") is not False
                or value.get("core", {}).get("stage") != stage
                or value.get("core", {}).get("runtime_versions") != RUNTIME):
            raise ValueError("generated controls require disabled operation profiles")
        profiles.append(str(p))
    observed_versions = {name: version(name) for name in RUNTIME}
    if observed_versions != RUNTIME:
        raise ValueError("installed maintained-library versions differ")
    # Interpreter bytes are bounded static identity capture, not a binary probe
    # or a complete dynamic-loader/ABI certificate. No package is imported here.
    python_pin, _ = _capture(sys.executable, cap=64 * 1024 * 1024)
    paths[python_pin["path"]] = python_pin
    return {
        "schema": "neural063-full-census-generated-plan-v1",
        "source_files": [paths[key] for key in sorted(paths)],
        "evidence_root": str(evidence), "range_source": str(ranges),
        "original_root": str(original), "core_source": str(core),
        "wrapper_source": str(wrapper), "worker_source": str(worker),
        "plan_builder_source": str(helper), "operation_profiles": profiles,
        "runtime": {"python": python_pin, "python_release": sys.version.split()[0],
                    "maintained_versions": observed_versions,
                    "complete_environment_or_ABI_certificate": False},
        "generated_only": True, "authentic_execution_selected": False,
        "authentic_provider_requests": False, "original_array_reads": False,
        "model_runs": False, "network_allowed": False,
        "limits": {"declared_ram_bytes": 1073741824, "seconds": 180,
                   "application_artifact_bytes": 458752, "fixture_bytes": 131072,
                   "terminal_generated_reserve_bytes": 98304},
        "scope": "Only the fixed generated census worker is named; this plan contains no command to execute. The caller must supply the reviewed bounded source-control or CI execution envelope. No authentic identity manifests or data payloads are inputs.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component-root", required=True)
    parser.add_argument("--range-source-root", required=True)
    parser.add_argument("--original-root", required=True)
    parser.add_argument("--evidence-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    component = _path(args.component_root, directory=True)
    plan = build_plan(component, component / "run.py", args.range_source_root,
                      args.original_root, [component / "profiles" / (s + ".json") for s in STAGES],
                      args.evidence_root, component / "tests/test_census_generated.py")
    raw_output = Path(args.output).expanduser()
    if raw_output.exists() or raw_output.is_symlink():
        raise ValueError("fresh plan output file required")
    output = _path(raw_output.parent, directory=True) / raw_output.name
    if output == Path(plan["evidence_root"]):
        raise ValueError("plan file and generated evidence directory must differ")
    body = (json.dumps(plan, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    if len(body) > 65536:
        raise ValueError("complete generated plan exceeds its bounded extent")
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    with os.fdopen(fd, "wb") as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    print(hashlib.sha256(body).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
