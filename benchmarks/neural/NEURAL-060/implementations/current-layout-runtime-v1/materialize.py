"""Materialize the pinned full NEURAL-060 runtime with its current roster locator.

This is an offline source transformation, not a data preparer or run authority.
The predecessor's 18-file closure is authenticated before any output is created.
Only bootstrap.roster's repository-relative locator changes. The successor gets
its own manifest; none of the predecessor's source pins are relabelled.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import types


TASK_ROOT = "benchmarks/neural/NEURAL-060"
PROGRAM = TASK_ROOT + "/implementations/full-central-programme/program"
ROSTER = TASK_ROOT + "/contracts/delivery/REQUIRED_SOURCES.json"
OLD_ROSTER = "authoring/delivery-20261105/neural060/REQUIRED_SOURCES.json"
MANIFEST_PIN = {"bytes": 2492, "sha256": "2ca0f30669eb7ae0a5f0a5bbbe04b6f950fa18bfb709890e817ad574bd04d140"}
BOOTSTRAP_PIN = {"bytes": 4479, "sha256": "3715a7fbb504ebe99703421bed0595f2687f5242a192fe419c36cdff1ded53f1"}
ROSTER_PIN = {"bytes": 17391, "sha256": "c62ba1c5161287d1915d7dd49165be79ca93632dee686be0ea29f0929c1791cf"}


def pin(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def canonical(value):
    """Reject ambiguous spellings; do not silently resolve a symlink or '..'."""
    value = os.fspath(value)
    path = Path(value)
    if (not path.is_absolute() or str(path) != value or value.startswith("//")
            or ".." in path.parts):
        raise ValueError("canonical absolute path required")
    return path


def directories(path):
    for item in (path, *path.parents):
        if not stat.S_ISDIR(os.lstat(item).st_mode):
            raise ValueError("ordinary directory ancestry required")


def capture(path, expected):
    """Bounded regular-file capture without following aliases or trusting a manifest."""
    directories(path.parent)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                or before.st_size != expected["bytes"]):
            raise ValueError("exact ordinary source file required")
        chunks, remaining = [], before.st_size
        while remaining:
            block = os.read(fd, min(65536, remaining))
            if not block:
                raise ValueError("short source capture")
            chunks.append(block)
            remaining -= len(block)
        raw = b"".join(chunks)
        signature = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        if (os.read(fd, 1) or signature(before) != signature(os.fstat(fd))
                or signature(before) != signature(os.lstat(path)) or pin(raw) != expected):
            raise ValueError("source pin or capture stability mismatch")
        return raw
    finally:
        os.close(fd)


def captured_bootstrap(raw, path):
    module = types.ModuleType("neural060_relocation_bootstrap")
    module.__file__ = str(path)
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


def source_plan(repo):
    """Read source only, authenticating the complete original closure and roster."""
    repo = canonical(repo)
    directories(repo)
    root = repo / PROGRAM
    raw = capture(root / "bootstrap.py", BOOTSTRAP_PIN)
    bootstrap = captured_bootstrap(raw, root / "bootstrap.py")
    sources = bootstrap.Sources(root, MANIFEST_PIN)
    roster = capture(repo / ROSTER, ROSTER_PIN)
    # Use the unchanged original roster admission, not a newly invented cohort.
    sources.module("projection").admit_sources(roster)
    old = ("Path(repo)/'" + OLD_ROSTER + "'").encode("ascii")
    new = ("Path(repo)/'" + ROSTER + "'").encode("ascii")
    if sources.bodies["bootstrap.py"].count(old) != 1:
        raise ValueError("exact single predecessor roster locator required")
    bodies = dict(sources.bodies)
    bodies["bootstrap.py"] = bodies["bootstrap.py"].replace(old, new, 1)
    files = {name: pin(body) for name, body in sorted(bodies.items())}
    manifest = encoded({"files": files, "schema": "neural060_runtime_source_v1"})
    return bodies, manifest, {
        "schema": "neural060_current_layout_source_v1",
        "task_id": "NEURAL-060",
        "predecessor_manifest": MANIFEST_PIN,
        "successor_manifest": pin(manifest),
        "roster": {"path": ROSTER, **ROSTER_PIN},
        "change": {"file": "bootstrap.py", "old_locator": OLD_ROSTER, "new_locator": ROSTER,
                   "before": BOOTSTRAP_PIN, "after": files["bootstrap.py"]},
        "unchanged_runtime_files": sorted(set(files) - {"bootstrap.py"}),
    }


def materialize(repo, output):
    """Write a fresh external source tree; retain partial output on an I/O failure."""
    repo, output = canonical(repo), canonical(output)
    directories(output.parent)
    if os.path.lexists(output):
        raise ValueError("fresh output required; no overwrite or automatic retry")
    if output == repo or repo in output.parents or output in repo.parents:
        raise ValueError("output must be disjoint from the repository")
    bodies, manifest, receipt = source_plan(repo)
    # All input authentication precedes the first mutation. There is no download,
    # recording, protected target, authority document, provider or model operand.
    output.mkdir(mode=0o700)
    for relative, raw in [*sorted(bodies.items()), ("SOURCE_MANIFEST.json", manifest)]:
        path = output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(raw)
        os.chmod(path, 0o444)
    # Exercise the same captured loader that the unchanged entry.py will use.
    successor = captured_bootstrap(bodies["bootstrap.py"], output / "bootstrap.py")
    loaded = successor.Sources(output, receipt["successor_manifest"])
    loaded.recheck()
    if successor.roster(repo) != capture(repo / ROSTER, ROSTER_PIN):
        raise ValueError("successor roster capture differs")
    with (output / "RELOCATION.json").open("xb") as stream:
        stream.write(encoded(receipt))
    os.chmod(output / "RELOCATION.json", 0o444)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="canonical repository root")
    parser.add_argument("--output", required=True, help="fresh external runtime directory")
    args = parser.parse_args(argv)
    print(encoded(materialize(args.repo, args.output)).decode("utf-8"), end="")


if __name__ == "__main__":
    main()
