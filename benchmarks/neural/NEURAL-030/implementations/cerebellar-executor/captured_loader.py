"""Closed captured-source import map. Importing this file runs no component."""
import builtins
import hashlib
import importlib
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import uuid

MEMBERS = frozenset(("captured_loader.py", "controller.py", "input_stages.py", "phase_worker.py",
    "candidate_views.py", "candidate_contract.py", "score.py", "vendor_transport/SOURCE_MANIFEST.json",
    "vendor_transport/__init__.py", "vendor_transport/engine.py", "vendor_transport/bounds.py",
    "vendor_transport/contract.py", "vendor_transport/archive.py", "vendor_transport/holder.py", "vendor_transport/provider.py"))


def capture(path, expected):
    p = Path(path)
    if not p.is_absolute() or any(q.is_symlink() for q in (p, *p.parents)):
        raise ValueError("ordinary absolute source path")
    if set(expected) != {"bytes", "sha256"} or type(expected["bytes"]) is not int or not 0 < expected["bytes"] <= 1048576:
        raise ValueError("bounded source pin")
    fd = os.open(p, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != expected["bytes"]:
            raise ValueError("ordinary exact source body")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            body = stream.read(expected["bytes"] + 1)
        after = os.fstat(fd)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_nlink) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_nlink):
            raise ValueError("source changed during capture")
    finally:
        os.close(fd)
    if len(body) != expected["bytes"] or hashlib.sha256(body).hexdigest() != expected["sha256"]:
        raise ValueError("captured source pin mismatch")
    body.decode("utf-8")
    return body


class Context(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def __init__(self, root, manifest, source_pin, bodies):
        self.root, self.manifest, self.source_pin, self.bodies = root, manifest, source_pin, bodies
        self.prefix = "_neural030_captured_" + uuid.uuid4().hex
        self.modules = set()

    def _name(self, fullname):
        if fullname == self.prefix:
            return "", True
        if not fullname.startswith(self.prefix + "."):
            return None
        relative = fullname[len(self.prefix) + 1:].replace(".", "/")
        for name, package in ((relative + "/__init__.py", True), (relative + ".py", False)):
            if name in self.bodies:
                return name, package
        raise ImportError("uncaptured component module")

    def find_spec(self, fullname, path=None, target=None):
        found = self._name(fullname)
        return None if found is None else importlib.util.spec_from_loader(fullname, self, is_package=found[1])

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        name, package = self._name(module.__name__)
        self.modules.add(module.__name__)
        if not name:
            module.__path__ = [str(self.root)]
            return
        module.__file__ = str(self.root / name)
        if package:
            module.__path__ = [str((self.root / name).parent)]
        original_import = builtins.__import__
        def owned_import(target, globals=None, locals=None, fromlist=(), level=0):
            # The unchanged accepted companion uses these two absolute names.
            # Resolve them inside this captured namespace without global aliases.
            if level == 0 and target in ("candidate_views", "score"):
                return importlib.import_module(self.prefix + "." + target)
            return original_import(target, globals, locals, fromlist, level)
        module.__dict__["__builtins__"] = {**vars(builtins), "__import__": owned_import}
        exec(compile(self.bodies[name], "<captured:" + name + ">", "exec"), module.__dict__)

    def module(self, name):
        return importlib.import_module(self.prefix + "." + name)

    def worker_source(self):
        return {"path": str(self.root / "phase_worker.py"), **self.manifest["files"]["phase_worker.py"]}

    def close(self):
        if self in sys.meta_path:
            sys.meta_path.remove(self)
        for name in self.modules:
            sys.modules.pop(name, None)


def load(root, expected):
    root = Path(root)
    raw = capture(root / "SOURCE_MANIFEST.json", expected)
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result: raise ValueError("duplicate source manifest key")
            result[key] = value
        return result
    manifest = json.loads(raw, object_pairs_hook=pairs)
    if set(manifest) != {"schema", "files", "scientific_qualification", "native_qualification"} or manifest["schema"] != "neural030_frozen_executor_source_v1":
        raise ValueError("source manifest schema")
    if manifest["scientific_qualification"] is not False or manifest["native_qualification"] is not False or set(manifest["files"]) != MEMBERS:
        raise ValueError("exact inactive source closure")
    if sum(row["bytes"] for row in manifest["files"].values()) > 16777216:
        raise ValueError("whole captured source ceiling")
    bodies = {name: capture(root / name, manifest["files"][name]) for name in sorted(MEMBERS)}
    context = Context(root, manifest, expected, bodies)
    sys.meta_path.insert(0, context)
    return context
