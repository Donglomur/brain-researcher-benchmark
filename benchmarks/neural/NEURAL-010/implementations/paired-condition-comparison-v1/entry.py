"""Pinned stdlib-only operator entry for joint NEURAL-010 campaign scoring."""
import argparse
import builtins
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time
import types

NAMES = (
    "entry.py", "captured_replay.py", "paired_conditions.py",
    "vendor/event-campaign-v1/SOURCE_MANIFEST.json",
    "vendor/event-campaign-v1/entry.py", "vendor/event-campaign-v1/common.py",
    "vendor/event-campaign-v1/compatibility.py", "vendor/event-campaign-v1/provider.py",
    "vendor/event-campaign-v1/exchange.py", "vendor/event-campaign-v1/campaign.py",
    "vendor/event-campaign-v1/vendor/detection-interface-v1/interface.py",
    "vendor/event-campaign-v1/vendor/scientific-scorer-v2/scorer.py",
    "vendor/event-campaign-v1/vendor/programme-source/implementation-v1/program/public/event_protocol.py",
)


def need(ok, message):
    if not ok:
        raise ValueError(message)


def parse(raw):
    def pairs(items):
        result = {}
        for k, v in items:
            need(k not in result, "duplicate JSON key")
            result[k] = v
        return result
    def bad(_):
        raise ValueError("nonfinite JSON")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=bad)


def capture(path, size, digest, maximum):
    need(type(size) is int and 0 < size <= maximum and type(digest) is str
         and len(digest) == 64 and all(c in "0123456789abcdef" for c in digest),
         "bounded exact selected bytes")
    path = Path(path)
    need(path.is_absolute() and str(path) == str(path.absolute())
         and ".." not in path.parts and not any(p.is_symlink() for p in (path, *path.parents)),
         "ordinary absolute selected path")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        a = os.fstat(fd)
        need(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and a.st_size == size,
             "ordinary exact selected extent")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read(size + 1)
        z, named = os.fstat(fd), path.lstat()
        fields = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")
        need(all(getattr(a, k) == getattr(z, k) == getattr(named, k) for k in fields)
             and len(raw) == size and hashlib.sha256(raw).hexdigest() == digest,
             "stable exact selected bytes")
        return raw
    finally:
        os.close(fd)


def bootstrap(size, digest):
    root = Path(__file__).absolute().parent
    raw = capture(root / "SOURCE_MANIFEST.json", size, digest, 1048576)
    doc = parse(raw)
    need(type(doc) is dict and set(doc) == {"schema", "files", "qualification"}
         and doc["schema"] == "neural010-paired-condition-source-v1"
         and doc["qualification"] is False, "exact unqualified paired source manifest")
    need(type(doc["files"]) is list and len(doc["files"]) == len(NAMES), "complete source roster")
    pins = {}
    for row in doc["files"]:
        need(type(row) is dict and set(row) == {"name", "bytes", "sha256"}
             and type(row["name"]) is str and row["name"] in NAMES and row["name"] not in pins,
             "fixed unique source names")
        need(type(row["bytes"]) is int and 0 < row["bytes"] <= 2097152, "bounded source member")
        pins[row["name"]] = row
    need(set(pins) == set(NAMES) and sum(r["bytes"] for r in pins.values()) <= 4194304,
         "complete bounded source closure")
    bodies = {name: capture(root / name, row["bytes"], row["sha256"], 2097152)
              for name, row in pins.items()}
    need(bodies["entry.py"] == capture(Path(__file__).absolute(), pins["entry.py"]["bytes"],
                                      pins["entry.py"]["sha256"], 2097152), "actual entry body")
    modules = {}
    original = builtins.__import__
    def load(name):
        need(name in ("captured_replay", "paired_conditions"), "fixed operator module")
        if name not in modules:
            path = name + ".py"
            module = types.ModuleType("neural010_paired_" + name)
            module.__file__ = str(root / path)
            module.__package__ = ""
            modules[name] = module
            def importer(n, g=None, l=None, fromlist=(), level=0):
                need(level == 0, "no relative plugin import")
                return load(n) if n in ("captured_replay", "paired_conditions") else original(n, g, l, fromlist, 0)
            module.__dict__["__builtins__"] = {**vars(builtins), "__import__": importer}
            exec(compile(bodies[path], module.__file__, "exec"), module.__dict__)
        return modules[name]
    reads = len(raw) + 1 + sum(len(b) + 1 for b in bodies.values()) + len(bodies["entry.py"]) + 1
    return root, load, reads, {"bytes": size, "sha256": digest}


def reserve(root, request_digest, source_digest, output):
    need(all(type(v) is str and len(v) == 64 and all(c in "0123456789abcdef" for c in v)
             for v in (request_digest, source_digest)), "selected reservation identities")
    root = Path(root)
    need(root.is_absolute() and ".." not in root.parts and root.is_dir()
         and not any(p.is_symlink() for p in (root, *root.parents)), "preexisting ordinary reservation root")
    raw = (json.dumps({"schema": "neural010-paired-invocation-reservation-v1",
                      "request_sha256": request_digest, "source_sha256": source_digest,
                      "output": output, "preflight_read_reserved_bytes": 12582912,
                      "preflight_write_reserved_bytes": 16384, "charge_retained_on_failure": True},
                     sort_keys=True) + "\n").encode()
    need(len(raw) <= 16384, "bounded invocation reservation")
    fd = os.open(root / (request_digest + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    try:
        todo = memoryview(raw)
        while todo:
            n = os.write(fd, todo)
            need(n > 0, "complete reservation write")
            todo = todo[n:]
        os.fsync(fd)
    finally:
        os.close(fd)


def main(argv=None):
    origin = time.monotonic()
    parser = argparse.ArgumentParser(description="Joint zero-training NEURAL-010 condition comparison")
    for name in ("source", "request", "authority"):
        if name != "source":
            parser.add_argument("--" + name, required=True)
        parser.add_argument("--" + name + "-bytes", type=int, required=True)
        parser.add_argument("--" + name + "-sha256", required=True)
    parser.add_argument("--read-root", action="append", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--reservation-root", required=True)
    args = parser.parse_args(argv)
    reserve(args.reservation_root, args.request_sha256, args.source_sha256, args.output)
    root, load, reads, source_pin = bootstrap(args.source_bytes, args.source_sha256)
    for path in (args.request, args.authority):
        need(Path(path).name.casefold() not in ("assessment.json", "train.json", "validation.json"),
             "selection metadata must not be a protected body")
    request = capture(args.request, args.request_bytes, args.request_sha256, 1048576)
    authority = capture(args.authority, args.authority_bytes, args.authority_sha256, 1048576)
    result = load("paired_conditions").compare(request, authority,
        {"bytes": args.authority_bytes, "sha256": args.authority_sha256},
        source_pin=source_pin, source_root=root, output_root=args.output,
        read_roots=args.read_root, initial_source_reads=reads, started_monotonic=origin)
    sys.stdout.write(json.dumps({"status": "complete_generated_or_operator_selected_source_comparison",
                                "result": result, "scientific_qualification": False}, sort_keys=True) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        sys.stderr.write(json.dumps({"status": "incomplete", "error_type": type(error).__name__,
                                    "comparison_must_not_be_inferred": True}) + "\n")
        raise SystemExit(2)
