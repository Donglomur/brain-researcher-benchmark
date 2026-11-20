"""Bounded artifact and authenticated-source utilities for generated controls.

This module does not qualify physical participant transport. ARTIFACT_DIR is
trusted operator configuration and must be outside every source tree.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import types


MAX_SOURCE_BYTES = 131072
MAX_OUTPUT_BYTES = 32768
MAX_TOTAL_OUTPUT_BYTES = 131072
MAX_OUTPUT_FILES = 8
MAX_OUTPUT_ENTRIES = 24


class ControlBoundaryError(ValueError):
    pass


def _require(condition, code):
    if not condition:
        raise ControlBoundaryError(code)


def _path(value):
    text = os.fspath(value)
    _require(type(text) is str and 0 < len(text) <= 4096, "path:bounded_text")
    path = Path(text)
    _require(path.is_absolute() and len(path.parts) <= 64, "path:absolute_bounded")
    _require(".." not in path.parts, "path:parent_traversal")
    return path


def _no_symlink_components(path):
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            info = current.lstat()
        except FileNotFoundError:
            break
        _require(not stat.S_ISLNK(info.st_mode), "output:symlink_component")


def validate_artifact_root(value, source_roots):
    """Refuse source descendants, ancestors, aliases, and symlink components.

    Validation creates nothing. The final directory must be created separately
    by prepare_artifact_root, or by the one wrong-output-root generated control.
    """
    requested = _path(value)
    roots = tuple(source_roots)
    _require(0 < len(roots) <= 16, "source:root_count")
    resolved = requested.resolve(strict=False)
    for root in roots:
        source = _path(root).resolve(strict=True)
        _require(source.is_dir(), "source:not_directory")
        _require(not (resolved == source or resolved in source.parents or
                      source in resolved.parents), "output:source_overlap")
    _no_symlink_components(requested)
    _require(requested.parent.is_dir(), "output:parent_missing")
    if requested.exists():
        _require(requested.is_dir(), "output:not_directory")
    return resolved


def prepare_artifact_root(value, source_roots):
    root = validate_artifact_root(value, source_roots)
    _require(not root.exists(), "output:already_exists")
    root.mkdir(mode=0o700)
    _require(root.resolve(strict=True) == root, "output:changed")
    return root


def _stamp(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def read_pinned_source(path, pin):
    size, sha256 = pin
    _require(type(size) is int and 0 < size <= MAX_SOURCE_BYTES,
             "source:unsealed_size")
    _require(type(sha256) is str and len(sha256) == 64 and
             all(c in "0123456789abcdef" for c in sha256), "source:unsealed_sha256")
    path = _path(path)
    before = path.lstat()
    _require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
             not before.st_mode & 0o022 and before.st_size == size, "source:custody")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        _require(_stamp(os.fstat(fd)) == _stamp(before), "source:open_changed")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            body = stream.read(size + 1)
        _require(_stamp(os.fstat(fd)) == _stamp(before) == _stamp(path.lstat()),
                 "source:changed")
    finally:
        os.close(fd)
    _require(len(body) == size and hashlib.sha256(body).hexdigest() == sha256,
             "source:digest")
    return body


def load_pinned_source(name, path, pin):
    body = read_pinned_source(path, pin)
    module = types.ModuleType(name)
    module.__file__ = str(path)
    exec(compile(body, str(path), "exec", dont_inherit=True), module.__dict__)
    return module


def artifact_inventory(root):
    """Inspect only the fresh owned artifact tree, with bounded traversal."""
    root_info = root.lstat()
    _require(stat.S_ISDIR(root_info.st_mode) and not root.is_symlink(), "output:root_changed")
    total, files, entries = 0, 0, 0
    pending = [root]
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as children:
            for child in children:
                entries += 1
                _require(entries <= MAX_OUTPUT_ENTRIES, "output:entry_count")
                info = child.stat(follow_symlinks=False)
                if stat.S_ISDIR(info.st_mode):
                    pending.append(Path(child.path))
                else:
                    _require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
                             "output:unexpected_entry")
                    files += 1
                    total += info.st_size
                    _require(files <= MAX_OUTPUT_FILES and total <= MAX_TOTAL_OUTPUT_BYTES,
                             "output:bounded_inventory")
    return files, total


def stage_portable_sources(root, sources):
    """Copy only five authenticated source files into an owned generated tree.

    These are generated software fixtures inside ARTIFACT_DIR, never mutations
    of the supplied source trees. Report files remain outside this staged tree.
    """
    _require(type(sources) is dict and len(sources) == 5, "stage:exact_source_count")
    bodies = {}
    for relative, (original, pin) in sources.items():
        rel = Path(relative)
        _require(not rel.is_absolute() and ".." not in rel.parts and
                 1 <= len(rel.parts) <= 5, "stage:relative_source_path")
        bodies[relative] = read_pinned_source(original, pin)
    files, total = artifact_inventory(root)
    _require(files + len(bodies) + 1 <= MAX_OUTPUT_FILES and
             total + sum(map(len, bodies.values())) + MAX_OUTPUT_BYTES <= MAX_TOTAL_OUTPUT_BYTES,
             "stage:artifact_capacity")
    stage = root / "portable-implementations"
    stage.mkdir(mode=0o700)
    for relative, body in bodies.items():
        target = stage / relative
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                     getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(body)
    artifact_inventory(root)
    return stage


def write_summary(root, report):
    """Write one bounded new JSON artifact, never a source file or a payload."""
    body = (json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    _require(len(body) <= MAX_OUTPUT_BYTES, "output:file_byte_limit")
    files, total = artifact_inventory(root)
    _require(files < MAX_OUTPUT_FILES, "output:file_count")
    _require(total + len(body) <= MAX_TOTAL_OUTPUT_BYTES, "output:total_byte_limit")
    path = root / "generated-control-summary.v1.json"
    directory_fd = os.open(root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) |
                           getattr(os, "O_NOFOLLOW", 0))
    try:
        _require(_stamp(os.fstat(directory_fd)) == _stamp(root.lstat()), "output:root_changed")
        fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                     getattr(os, "O_NOFOLLOW", 0), 0o600, dir_fd=directory_fd)
        with os.fdopen(fd, "wb") as stream:
            stream.write(body)
    finally:
        os.close(directory_fd)
    return {"name": path.name, "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest()}
