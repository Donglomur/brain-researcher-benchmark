"""Build a portable, generated-only NEURAL-063 plan without importing science.

The caller supplies an already selected CI/control envelope. Constructing this
plan does not authorize Docker, real inputs, or actual deployment. Interpreter
and source reads are streamed and bounded; distribution metadata startup reads
are outside these explicit source counters. No library import or binary probe.
"""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import stat
import sys

IMMUTABLE = {
    "owner": [
        "owner/__init__.py",
        80,
        "d857d613efdca2fad6b20a106349516a410e2837b5f4bff6b6d2db592ba58658"
    ],
    "owner_io": [
        "owner/io.py",
        8483,
        "3a8c4d0d58be213ab9cbcfcdb2d98781e7bfdedb1839ea109bdc0d9466944f91"
    ],
    "owner_scoring": [
        "owner/scoring.py",
        12817,
        "e85413e3af2b63c919fbfc93fffdb6fc0e37af9d038f693df99da980b04dc0dc"
    ],
    "preparation": [
        "preparation/__init__.py",
        82,
        "a852591a1dea52c60ea4a6cacb06b150e49397ac9189d2120e8dc7c4f9241d95"
    ],
    "algorithm": [
        "preparation/algorithm.py",
        7672,
        "aa5255ba1d238331cc91122b4b84ce2d90a0d23b7b19964ddb91c72953bac3c8"
    ],
    "native": [
        "preparation/native.py",
        8094,
        "59938e74806637cc3be504a6bcb2a550f1571d22e6d55342abdd048978389c66"
    ],
    "range": [
        "range_io.py",
        15515,
        "73d479623f9fe78f42631aeca49113748791b5737cfe7b6aec43789737ffb7e1"
    ],
    "manifest": [
        "manifest.py",
        7952,
        "36b7eb96e9d40f808035979b1f30c7e103746d20d670235d8658cda613381205"
    ],
    "pipeline": [
        "pipeline.py",
        20502,
        "ad1e2e80dc8676af208a3fee4bd0977694fc3abf145d883fbb5b8b7a17dd8f42"
    ]
}
PACKAGES = {
    "aiohappyeyeballs": "2.6.1",
    "aiohttp": "3.14.3",
    "aiosignal": "1.4.0",
    "attrs": "25.4.0",
    "frozenlist": "1.8.0",
    "fsspec": "2026.6.0",
    "h5py": "3.16.0",
    "idna": "3.11",
    "multidict": "6.7.0",
    "numpy": "2.4.6",
    "propcache": "0.4.1",
    "typing-extensions": "4.15.0",
    "yarl": "1.22.0"
}
LOCAL_PACKAGES = {
    "aiohappyeyeballs": "2.7.1",
    "aiohttp": "3.14.3",
    "aiosignal": "1.4.0",
    "attrs": "26.1.0",
    "frozenlist": "1.8.0",
    "fsspec": "2026.6.0",
    "h5py": "3.16.0",
    "idna": "3.18",
    "multidict": "6.9.0",
    "numpy": "2.4.6",
    "propcache": "0.5.4",
    "typing-extensions": "4.15.0",
    "yarl": "1.25.1"
}
PROFILE_PACKAGES = {
    ("darwin", "arm64", "3.11.6"): LOCAL_PACKAGES,
    ("linux", "x86_64", "3.11.18"): PACKAGES,
}


def selected_distributions(profile):
    """Select one complete declared profile; callers also bind the actual host."""
    fields = ("sys_platform", "machine", "python_release")
    if (type(profile) is not dict or set(profile) !=
            {"schema", "python_release", "sys_platform", "machine", "distributions"}
            or profile["schema"] != "neural063-portable-generated-runtime-v1"
            or any(type(profile[field]) is not str for field in fields)):
        raise ValueError("exact complete generated runtime profile required")
    expected = PROFILE_PACKAGES.get(tuple(profile[field] for field in fields))
    if (expected is None or type(profile["distributions"]) is not dict
            or profile["distributions"] != expected):
        raise ValueError("unsupported complete generated runtime profile")
    return dict(expected)


INSTALLED_SOURCES = {
    "aiohttp/client.py": {
        "bytes": 64597,
        "sha256": "a5467752c13ae51bf5731a8e3997d5f8b44ab1c0c54b11a906e878ff3cc31701"
    },
    "aiohttp/client_reqrep.py": {
        "bytes": 54704,
        "sha256": "456c97cee222d0d11335eb8d00331b58f19dfa6c5ca552ec550334379f36a54f"
    },
    "fsspec/implementations/http.py": {
        "bytes": 30894,
        "sha256": "d6e5b0c6594e8cf7bc9900f9e08ac261024753561a01787f703997064f80a10f"
    },
    "fsspec/caching.py": {
        "bytes": 34024,
        "sha256": "6099bb4a3413c4e8326af2af004d02493fc64749a99c48e7208582744d506cb9"
    },
    "fsspec/spec.py": {
        "bytes": 78097,
        "sha256": "ec6f041509f780c48c3fa3f168580cf557fddc384573ffb50018af73fd3af5fa"
    },
    "h5py/_hl/files.py": {
        "bytes": 25154,
        "sha256": "926856d56326dbbf8cd6a698169c05e8d6f54932d40dc9989351b308e0358d36"
    }
}
LIMITS = {
    "per_fixture_extent_bytes": 131072,
    "per_fixture_hdf_write_bytes": 1048576,
    "all_fixture_hdf_write_bytes": 5242880,
    "in_memory_inventory_bytes": 4194304,
    "saved_artifact_bytes": 524288,
    "result_bytes": 65536,
    "plan_artifact_bytes": 65536,
    "source_read_bytes": 4194304,
    "interpreter_read_bytes": 67108865,
    "outer_pool_log_cap_bytes": 1048576
}
METHODS = ["test_01_admission","test_02_real_hdf_parity","test_03_scientific_refusals","test_04_session_identity","test_05_inventory","test_06_binary_copyout"]
GRAPH_CASES = ["admission_before_start","unknown_custody_stops_dispatch","incomplete_session_held","recovery_exact_identity","settlement_evidence_refused"]
BINARY_MODES = ["exact", "short", "corrupt", "oversized", "stderr", "nonzero",
                "held_open", "uncertain_write", "selector_close", "cleanup_permission"]
CHANGED = {"adapter": "scientific_adapter.py", "inventory": "host_inventory.py",
    "exporter": "fixed_export.py", "worker": "worker.py", "controller": "controller.py",
    "fixture": "tests/fixture_factory.py", "controller_graph": "tests/controller_graph_controls.py"}


def strict(body):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    return json.loads(body, object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode()


def ordinary(value, *, directory=False):
    path = Path(value).expanduser().resolve(strict=True)
    if len(str(path).encode()) > 2048:
        raise ValueError("bounded source path required")
    kind = path.stat().st_mode
    if not (stat.S_ISDIR(kind) if directory else stat.S_ISREG(kind)):
        raise ValueError("ordinary named source required")
    return path


def capture(value, *, counters, interpreter=False, retain=True, cap=131072):
    path = ordinary(value)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= cap:
            raise ValueError("bounded ordinary source extent")
        key = "interpreter" if interpreter else "source"
        ceiling = LIMITS["interpreter_read_bytes" if interpreter else "source_read_bytes"]
        counters[key] += before.st_size + 1
        if counters[key] > ceiling:
            raise ValueError("plan construction read reservation exhausted")
        digest, body, remaining = hashlib.sha256(), bytearray(), before.st_size
        while remaining:
            piece = os.read(fd, min(65536, remaining))
            if not piece:
                raise ValueError("source incomplete")
            digest.update(piece)
            if retain:
                body.extend(piece)
            remaining -= len(piece)
        eof = os.read(fd, 1)
        after, named = os.fstat(fd), path.lstat()
        stamp = lambda item: (item.st_dev, item.st_ino, item.st_size,
                              item.st_mtime_ns, item.st_ctime_ns)
        if eof or stamp(before) != stamp(after) or stamp(before) != stamp(named):
            raise ValueError("source changed during bounded same-FD capture")
        return {"path": str(path), "bytes": before.st_size,
                "sha256": digest.hexdigest()}, bytes(body) if retain else None
    finally:
        os.close(fd)


def build_plan(component_root, range_source_root, original_root, evidence_root, *,
               python, runtime_profile):
    """Return a fully bound local generated plan; no writes, target imports or run."""
    component = ordinary(component_root, directory=True)
    ranges = ordinary(range_source_root, directory=True)
    original = ordinary(original_root, directory=True)
    evidence = Path(evidence_root).expanduser()
    if evidence.exists() or evidence.is_symlink() or evidence.name in ("", ".", ".."):
        raise ValueError("fresh generated evidence directory required")
    evidence = ordinary(evidence.parent, directory=True) / evidence.name
    if len(str(evidence).encode()) > 2048:
        raise ValueError("bounded generated output path")
    selected_python = ordinary(python)
    if selected_python != Path(sys.executable).resolve(strict=True):
        raise ValueError("plan-maker must use the explicitly selected interpreter")
    counts = {"source": 0, "interpreter": 0}
    profile_ref, profile_body = capture(runtime_profile, counters=counts, cap=65536)
    profile = strict(profile_body)
    expected = selected_distributions(profile)
    if (profile["python_release"] != sys.version.split()[0]
            or profile["sys_platform"] != sys.platform
            or profile["machine"] != os.uname().machine
            or sys.version_info[:2] != (3, 11)):
        raise ValueError("selected runtime profile differs before scientific imports")
    versions = {name: importlib.metadata.version(name) for name in expected}
    if versions != expected:
        raise ValueError("installed distribution declarations differ")
    sources = {}
    for key, relative in CHANGED.items():
        sources[key], _ = capture(component / relative, counters=counts, retain=False)
    for key, (relative, size, sha) in IMMUTABLE.items():
        root = ranges if key in ("range", "manifest", "pipeline") else original
        ref, _ = capture(root / relative, counters=counts, retain=False)
        if (ref["bytes"], ref["sha256"]) != (size, sha):
            raise ValueError("unchanged scientific/range source identity mismatch")
        sources[key] = ref
    tools = {}
    for name in ("test_contained_generated.py", "make_generated_plan.py", "run_generated_ci.py"):
        tools[name], _ = capture(component / "tests" / name, counters=counts, retain=False)
    if ordinary(__file__) != Path(tools["make_generated_plan.py"]["path"]):
        raise ValueError("plan-maker belongs to the selected component")
    roots = {}
    for package in ("numpy", "h5py", "fsspec", "aiohttp"):
        roots[package] = str(ordinary(importlib.metadata.distribution(package).locate_file(package),
                                      directory=True))
    installed = {}
    for relative, expected in INSTALLED_SOURCES.items():
        package, suffix = relative.split("/", 1)
        ref, _ = capture(Path(roots[package]) / suffix, counters=counts, retain=False)
        if {key: ref[key] for key in ("bytes", "sha256")} != expected:
            raise ValueError("maintained installed pure-Python source differs")
        installed[relative] = ref
    python_ref, _ = capture(selected_python, counters=counts, interpreter=True,
                            retain=False, cap=67108864)
    return {"schema": "neural063-portable-contained-generated-controls-v1",
        "selected": True, "generated_only": True, "authentic_provider_requests": False,
        "docker_allowed": False, "network_allowed": False, "original_array_reads": False,
        "kernel_tests": False, "model_runs": False, "controller_graph_executed": False,
        "recovery_graph_executed": False, "evidence_root": str(evidence),
        "runner": tools["test_contained_generated.py"],
        "plan_builder": tools["make_generated_plan.py"], "ci_entry": tools["run_generated_ci.py"],
        "sources": sources, "runtime": {"python": python_ref,
            "profile": profile_ref, "python_release": profile["python_release"],
            "sys_platform": profile["sys_platform"], "machine": profile["machine"],
            "distributions": versions, "package_roots": roots, "installed_sources": installed},
        "construction": {"source_read_bytes_reserved": counts["source"],
            "interpreter_read_bytes_reserved": counts["interpreter"],
            "plan_requested_write_reservation_bytes": LIMITS["plan_artifact_bytes"],
            "metadata_startup_read_bytes_measured": False,
            "entry_source_read_reservation_bytes": 163842},
        "limits": LIMITS, "methods": METHODS, "binary_modes": BINARY_MODES,
        "planned_mocked_controller_graph_cases": GRAPH_CASES}


def publish_plan(path, plan):
    """Exclusive append-only, requested writes capped including short writes."""
    path = Path(path)
    if not path.is_absolute() or path.exists() or path.is_symlink() or not path.parent.is_dir():
        raise ValueError("fresh plan output file under existing ordinary parent")
    body = canonical(plan)
    if not 0 < len(body) <= LIMITS["plan_artifact_bytes"]:
        raise ValueError("bounded generated plan")
    requested = 0
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    try:
        offset = 0
        while offset < len(body):
            piece = memoryview(body)[offset:]
            requested += len(piece)
            if requested > LIMITS["plan_artifact_bytes"]:
                raise ValueError("plan requested-write reserve exhausted")
            count = os.write(fd, piece)
            if not 0 < count <= len(piece):
                raise OSError("incomplete generated plan publication")
            offset += count
        os.fsync(fd)
    finally:
        os.close(fd)
    return {"path": str(path), "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(),
            "requested_write_bytes": requested}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("component-root", "range-source-root", "original-root", "evidence-root",
                 "python", "runtime-profile", "output"):
        parser.add_argument("--" + flag, required=True)
    args = parser.parse_args(argv)
    plan = build_plan(args.component_root, args.range_source_root, args.original_root,
        args.evidence_root, python=args.python, runtime_profile=args.runtime_profile)
    publish_plan(Path(args.output).absolute(), plan)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
