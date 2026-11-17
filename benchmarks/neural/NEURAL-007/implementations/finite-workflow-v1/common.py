"""Bounded operator metadata and authenticated original scientific source.

These helpers do not authorize execution. Source roots and descriptor pins are
trusted operator inputs; participant code is never imported into this process.
"""
import hashlib
import importlib.util
from importlib import import_module
import json
import os
from pathlib import Path
import re
import stat
import sys
import types

HERE = Path(__file__).resolve().parent
IMPL = HERE.parent
SPEC_CASES = (("development-001", 2780), ("development-002", 2670))
IMAGE = "sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156"
RUNTIME_FILES = {"common.py", "workflow.py", "producer.py", "provenance.py", "grading.py", "SOURCE_BINDINGS.json"}
PROGRAMME_COMMAND = ["/usr/local/bin/python", "-I", "-B", "/trusted/producer.py"]
PROGRAMME_RESOURCES = {
    "setup_seconds": 30, "producer_seconds": 20, "capture_seconds": 30, "cleanup_seconds": 20,
    "memory_bytes": 3 * 2**30, "cpu_nanos": 1750000000, "pids": 64, "scratch_bytes": 64 * 2**20,
    "max_files": 3, "max_directories": 1, "max_file_bytes": 400000, "max_output_bytes": 8 * 2**20,
    "manifest_bytes": 4096, "max_cli_calls": 100, "max_cli_bytes": 2 * 2**20,
    "inventory_bytes": 32768, "source_read_bytes": 32 * 2**20, "host_write_bytes": 8 * 2**20,
}
GLOBAL_SECONDS = 260


def need(value, message):
    if not value:
        raise ValueError(message)


def pin(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode() + b"\n"


def plain(value):
    return {key: value[key] for key in ("bytes", "sha256")}


def checked_pin(value, cap=2**20):
    need(type(value) is dict and set(value) == {"bytes", "sha256"}
         and type(value["bytes"]) is int and 0 < value["bytes"] <= cap
         and type(value["sha256"]) is str and re.fullmatch("[0-9a-f]{64}", value["sha256"]),
         "exact bounded descriptor")
    return value


def path(value):
    value = Path(os.path.abspath(value))
    need(all(not p.is_symlink() for p in (value, *value.parents)), "no linked path")
    return value


def read(file, expected, cap=2**20):
    checked_pin(expected, cap)
    file = path(file)
    fd = os.open(file, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and before.st_size == expected["bytes"], "ordinary exact input")
        raw = bytearray()
        while len(raw) <= before.st_size:
            block = os.read(fd, min(65536, before.st_size + 1 - len(raw)))
            if not block:
                break
            raw.extend(block)
        stamp = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mode, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
        need(stamp(before) == stamp(os.fstat(fd)) == stamp(file.lstat()), "stable exact input")
    finally:
        os.close(fd)
    raw = bytes(raw)
    need(pin(raw) == expected, "input pin mismatch")
    return raw


def snapshot(file, cap):
    """Freeze newly supplied programme/output bytes; never an authorization pin."""
    file = path(file)
    fd = os.open(file, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap,
             "bounded ordinary snapshot")
        raw = bytearray()
        while len(raw) <= before.st_size:
            block = os.read(fd, min(65536, before.st_size + 1 - len(raw)))
            if not block:
                break
            raw.extend(block)
        stamp = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mode, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
        need(stamp(before) == stamp(os.fstat(fd)) == stamp(file.lstat()) and len(raw) == before.st_size,
             "stable complete snapshot")
        return bytes(raw)
    finally:
        os.close(fd)


def descriptor_read(value, cap=2**20):
    need(type(value) is dict and set(value) == {"path", "bytes", "sha256"}, "path and exact pin")
    return read(value["path"], plain(value), cap)


def write(file, raw, mode=0o600):
    need(type(raw) is bytes and len(raw) <= 2**20, "bounded publication")
    file = path(file)
    fd = os.open(file, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    try:
        at = 0
        while at < len(raw):
            count = os.write(fd, raw[at:])
            need(count > 0, "complete publication")
            at += count
        os.fchmod(fd, mode)
        os.fsync(fd)
    finally:
        os.close(fd)
    directory = os.open(file.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return {"path": str(file), **pin(raw)}


def _module(name, file, expected):
    raw = read(file, expected)
    module = types.ModuleType(name)
    module.__file__ = str(file)
    sys.modules[name] = module
    exec(compile(raw, str(file), "exec"), module.__dict__)
    return module


def bindings():
    # This file is authenticated by the enclosing source freeze before execution.
    raw = HERE.joinpath("SOURCE_BINDINGS.json").read_bytes()
    need(len(raw) <= 32768, "bounded source bindings")
    return json.loads(raw)


def original(name):
    item = bindings()["original"][name]
    file = path(IMPL / item["path"])
    need(file.is_relative_to(IMPL), "task-local scientific source")
    return file, plain(item)


def load_sources():
    file, expected = original("adapter")
    adapter = _module("candidate_adapter", file, expected)
    file, expected = original("helper")
    helper = _module("_sleep_finite_target_helper", file, expected)
    assets = json.loads(read(*original("assets")))
    profile = json.loads(read(*original("profile")))
    need(tuple((c["case_id"], c["epochs"]) for c in assets["cases"]) == SPEC_CASES
         and assets["class_order"] == list(adapter.CLASS_ORDER), "original two-person scientific panel")
    return adapter, helper, assets, profile


def authenticate_sources(freeze):
    value = json.loads(descriptor_read(freeze, 32768))
    need(set(value) == {"schema", "files"} and value["schema"] == "sleep007_finite_source_v1"
         and set(value["files"]) == RUNTIME_FILES, "complete finite workflow source freeze")
    for name, expected in value["files"].items():
        read(HERE / name, expected)
    for name in bindings()["original"]:
        read(*original(name))
    return value


def load_provider():
    value = bindings()
    root = path(IMPL / value["provider_package_relative"])
    need(root.is_relative_to(IMPL), "task-local canonical provider")
    manifest = json.loads(read(root / "SOURCE_MANIFEST.json", value["provider_manifest"], 32768))
    need(set(manifest["files"]) == {"__init__.py", "provider.py", "engine.py", "bounds.py", "contract.py", "archive.py", "holder.py"},
         "complete canonical provider")
    for name, expected in manifest["files"].items():
        read(root / name, expected)
    name = "_sleep_finite_transport"
    need(not any(key == name or key.startswith(name + ".") for key in sys.modules), "fresh canonical package namespace")
    spec = importlib.util.spec_from_file_location(name, root / "__init__.py", submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return import_module(name + ".provider")
