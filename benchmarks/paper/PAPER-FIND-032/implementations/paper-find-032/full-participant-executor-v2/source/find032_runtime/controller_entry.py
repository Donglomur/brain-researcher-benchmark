"""Fixed original controller child. No project import precedes source admission."""
import argparse
import hashlib
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys
import time


def require(value, message):
    if not value:
        raise RuntimeError(message)


def json_object(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, "duplicate source/config key")
            out[key] = value
        return out
    def bad(value):
        raise RuntimeError("nonfinite source/config number")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=bad)


def capture(name, extent, digest, deadline):
    require(type(extent) is int and 0 < extent <= 1048576 and
            type(digest) is str and re.fullmatch("[0-9a-f]{64}", digest), "bounded exact source descriptor")
    p = Path(name)
    require(p.is_absolute() and not any(x.is_symlink() for x in (p, *p.parents)), "unlinked source operand")
    before = p.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == extent,
            "ordinary exact source/config extent")
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    parts = []
    primary = None
    secondaries = []
    try:
        left = extent
        while left:
            require(time.monotonic() < deadline, "same source bootstrap deadline")
            block = os.read(fd, min(left, 65536))
            require(bool(block), "short exact source read")
            parts.append(block); left -= len(block)
        identity = lambda x: (x.st_dev, x.st_ino, x.st_mode, x.st_nlink, x.st_size, x.st_mtime_ns, x.st_ctime_ns)
        require(identity(before) == identity(os.fstat(fd)) == identity(p.lstat()), "source stable through capture")
    except BaseException as error:
        primary = error
    finally:
        try:
            os.close(fd)
        except BaseException as error:
            secondaries.append(error)
            if primary is None:
                primary = error
    if primary is not None:
        # Strong globals retain raw bootstrap failures until this original exits.
        BOOTSTRAP_FAILURES.append((primary, tuple(secondaries), tuple(parts)))
        raise primary
    raw = b"".join(parts)
    try:
        require(len(raw) == extent and hashlib.sha256(raw).hexdigest() == digest, "exact authenticated source body")
    except BaseException as error:
        BOOTSTRAP_FAILURES.append((error, (), (raw,)))
        raise
    return raw


BOOTSTRAP_FAILURES = []


class CapturedProjects(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """Only the two fixed task namespaces resolve from already captured bytes."""
    def __init__(self, root, bodies):
        self.root, self.bodies = root, bodies
        self.selected = {}

    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] not in ("find032", "find032_runtime"):
            return None
        stem = fullname.replace(".", "/")
        choices = [(stem + "/__init__.py", True), (stem + ".py", False)]
        found = [(name, package) for name, package in choices if name in self.bodies]
        require(len(found) == 1, "no ambient or ambiguous task import")
        self.selected[fullname] = found[0]
        return importlib.util.spec_from_loader(fullname, self, is_package=found[0][1])

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        name, package = self.selected[module.__name__]
        module.__file__ = str(self.root / name)
        if package:
            module.__path__ = [str((self.root / name).parent)]
        exec(compile(self.bodies[name], module.__file__, "exec"), module.__dict__)


def main():
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--config", required=True)
    parser.add_argument("--config-bytes", type=int, required=True)
    parser.add_argument("--config-sha256", required=True)
    parser.add_argument("--source-manifest", required=True)
    parser.add_argument("--source-manifest-bytes", type=int, required=True)
    parser.add_argument("--source-manifest-sha256", required=True)
    parser.add_argument("--ownership-fd", type=int, required=True)
    parser.add_argument("--original-endpoint", type=float, required=True)
    parser.add_argument("--cleanup-endpoint", type=float, required=True)
    args = parser.parse_args()
    require(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode and
            not sys.flags.optimize and time.monotonic() < args.original_endpoint < args.cleanup_endpoint,
            "fixed isolated original child scope")
    cache = sys.pycache_prefix
    require(type(cache) is str and sys._xoptions.get("pycache_prefix") == cache,
            "explicit original empty cache prefix")
    cache_path = Path(cache)
    require(cache_path.is_absolute() and not any(x.is_symlink() for x in (cache_path, *cache_path.parents)),
            "unlinked private cache prefix")
    info = cache_path.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == 0 and stat.S_IMODE(info.st_mode) == 0o550,
            "original root-owned readonly cache prefix")
    with os.scandir(cache_path) as entries:
        require(next(entries, None) is None, "empty cache prefix")
    require(not any(n == "find032" or n.startswith("find032.") or n == "find032_runtime" or
                    n.startswith("find032_runtime.") for n in sys.modules), "no preloaded task namespace")
    raw = capture(args.source_manifest, args.source_manifest_bytes, args.source_manifest_sha256, args.original_endpoint)
    selection = json_object(raw)
    require(type(selection) is dict and set(selection) == {"schema", "root", "files"} and
            selection["schema"] == "find032_captured_runtime_sources_v1", "fixed parent source capture")
    root = Path(selection["root"])
    require(root == Path(__file__).absolute().parent.parent and root.is_absolute(), "same complete runtime source root")
    rows = selection["files"]
    require(type(rows) is dict and 0 < len(rows) <= 256 and
            sum(row["bytes"] for row in rows.values()) <= 4194304, "finite captured source graph")
    bodies = {}
    for name, row in rows.items():
        require(type(name) is str and name.startswith(("find032/", "find032_runtime/")) and
                name.endswith(".py") and "\\" not in name and "\x00" not in name and
                all(part not in ("", ".", "..") for part in name.split("/")), "closed source-relative member")
        require(type(row) is dict and set(row) == {"bytes", "sha256", "mode"} and row["mode"] in (0o444, 0o644),
                "exact physical source mode descriptor")
        require(stat.S_IMODE((root / name).lstat().st_mode) == row["mode"], "selected source mode")
        bodies[name] = capture(root / name, row["bytes"], row["sha256"], args.original_endpoint)
    require("find032_runtime/controller_entry.py" in bodies, "original controller source included")
    config_raw = capture(args.config, args.config_bytes, args.config_sha256, args.original_endpoint)
    finder = CapturedProjects(root, bodies)
    sys.meta_path.insert(0, finder)
    from find032_runtime.controller import run
    return run(config_raw, args.ownership_fd, args.original_endpoint, args.cleanup_endpoint,
               source_pins=rows, holder_source=bodies["find032_runtime/holder.py"])


if __name__ == "__main__":
    raise SystemExit(main())
