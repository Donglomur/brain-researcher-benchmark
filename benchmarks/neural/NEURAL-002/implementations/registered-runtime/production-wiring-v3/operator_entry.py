"""Captured-source Morse production entry; no default run or provider settings."""
import argparse
import hashlib
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import time


def require(test, message):
    if not test:
        raise ValueError(message)


def decode(body):
    def pairs(items):
        out = {}
        for k, v in items:
            require(k not in out, "duplicate source/configuration key")
            out[k] = v
        return out
    def bad(value):
        raise ValueError("nonfinite JSON constant")
    return json.loads(body, object_pairs_hook=pairs, parse_constant=bad)


class Capture:
    def __init__(self, maximum, end):
        self.maximum, self.end, self.used = maximum, end, 0

    def read(self, root, pin):
        require(type(pin) is dict and set(pin) == {"path", "bytes", "sha256"}, "source pin schema")
        require(type(pin["bytes"]) is int and 0 < pin["bytes"] <= 2**20, "ordinary source member bound")
        require(type(pin["sha256"]) is str and len(pin["sha256"]) == 64
                and all(c in "0123456789abcdef" for c in pin["sha256"]), "source digest")
        root_value = root
        root, rel = Path(root), Path(pin["path"])
        require(type(root_value) is str and not root_value.startswith("//")
                and str(root) == root_value and ".." not in root.parts
                and root.is_absolute() and not rel.is_absolute() and str(rel) == pin["path"]
                and ".." not in rel.parts and "\\" not in pin["path"], "source path")
        path = root / rel
        for p in (path.parent, *path.parent.parents):
            require(stat.S_ISDIR(p.lstat().st_mode) and not p.is_symlink(), "ordinary source parents")
        require(time.monotonic() < self.end and self.used + pin["bytes"] + 1 <= self.maximum,
                "prospective source deadline/read grant")
        self.used += pin["bytes"] + 1
        before = path.lstat()
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == pin["bytes"],
                "ordinary pinned source")
        fd, first, secondary, body = None, None, [], None
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            opened = os.fstat(fd)
            stamp = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
            require(stamp(opened) == stamp(before), "source changed before open")
            pieces, total = [], 0
            while total <= pin["bytes"]:
                require(time.monotonic() < self.end, "source read deadline")
                part = os.read(fd, min(65536, pin["bytes"] + 1 - total))
                if not part:
                    break
                total += len(part)
                pieces.append(part)
            body = b"".join(pieces)
            require(stamp(opened) == stamp(os.fstat(fd)) == stamp(path.lstat())
                    and len(body) == pin["bytes"]
                    and hashlib.sha256(body).hexdigest() == pin["sha256"], "source capture differs")
        except BaseException as exc:
            first = exc
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except BaseException as exc:
                    if first is None:
                        first = exc
                    else:
                        secondary.append(exc)
        if first is not None:
            first.morse_secondary_errors = tuple(getattr(first, "morse_secondary_errors", ())) + tuple(secondary)
            raise first
        require(time.monotonic() < self.end, "source completion deadline")
        return body


class CapturedModules(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def __init__(self, bodies):
        self.bodies = bodies

    def find_spec(self, fullname, path=None, target=None):
        if fullname in self.bodies:
            return importlib.util.spec_from_loader(fullname, self, origin=self.bodies[fullname][0])
        return None

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        path, body = self.bodies[module.__name__]
        module.__file__ = path
        exec(compile(body, path, "exec"), module.__dict__)


def main():
    require(sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode,
            "actual -I -S -B startup required")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("inspect", "run"))
    p.add_argument("--legacy-root", required=True)
    p.add_argument("--manifest-bytes", type=int, required=True)
    p.add_argument("--manifest-sha256", required=True)
    p.add_argument("--read-bytes", type=int, required=True)
    p.add_argument("--write-bytes", type=int, required=True)
    p.add_argument("--seconds", type=float, required=True)
    for name in ("evidence-root", "authorization-path", "authorization-sha256", "config-root", "config-path", "config-sha256"):
        p.add_argument("--" + name)
    p.add_argument("--authorization-bytes", type=int)
    p.add_argument("--config-bytes", type=int)
    a = p.parse_args()
    require(not a.legacy_root.startswith("//") and Path(a.legacy_root).is_absolute()
            and str(Path(a.legacy_root)) == a.legacy_root
            and ".." not in Path(a.legacy_root).parts, "canonical absolute legacy source root")
    require(a.read_bytes > 0 and a.write_bytes > 0 and 0 < a.seconds < float("inf"),
            "explicit positive source/metadata/deadline operands")
    deadline = time.monotonic() + a.seconds
    reader = Capture(a.read_bytes, deadline)
    here = Path(__file__).absolute().parent
    raw = reader.read(str(here), {"path": "SOURCE_MANIFEST.json", "bytes": a.manifest_bytes,
                                  "sha256": a.manifest_sha256})
    manifest = decode(raw)
    require(type(manifest) is dict and set(manifest) == {"schema", "files", "legacy_files", "module_map", "scope"}
            and manifest["schema"] == "morse-production-source-v1", "production source manifest")
    bodies = {}
    for area, root, rows in (("local", here, manifest["files"]),
                             ("legacy", Path(a.legacy_root), manifest["legacy_files"])):
        require(type(rows) is list and len(rows) <= 64, "finite exact source selection")
        for row in rows:
            key = area + ":" + row["path"]
            require(key not in bodies, "duplicate selected source")
            bodies[key] = (str(root / row["path"]), reader.read(str(root), row))
    require(type(manifest["module_map"]) is dict and manifest["module_map"], "closed task module mapping")
    mapped = {}
    for name, key in manifest["module_map"].items():
        require(name.isidentifier() and name not in sys.modules and key in bodies,
                "reserved source namespace already imported or missing")
        mapped[name] = bodies[key]
    if a.action == "inspect":
        require(all(getattr(a, n) is None for n in ("evidence_root", "authorization_path", "authorization_sha256",
                "config_root", "config_path", "config_sha256", "authorization_bytes", "config_bytes")),
                "inspect accepts no data/authorization operands")
        print(json.dumps({"schema": "morse-production-source-inspection-v1", "files": len(bodies),
            "source_read_reserved": reader.used, "scope": manifest["scope"],
            "task_modules_imported": False, "scientific_qualification": False,
            "native_execution_performed": False}, sort_keys=True))
        return
    require(all(getattr(a, n) is not None for n in ("evidence_root", "authorization_path", "authorization_sha256",
            "config_root", "config_path", "config_sha256", "authorization_bytes", "config_bytes")),
            "run requires separately selected configuration and authorization pins")
    # Dedicated trusted process only. All task imports use captured exact text;
    # no ordinary .pyc/extension/cwd selection can replace a reserved module.
    finder = CapturedModules(mapped)
    sys.meta_path.insert(0, finder)
    from production_budget import Budget
    from production_policy import document, ordinary_directory
    from production_operation import run_configuration
    budget = Budget(a.read_bytes, a.write_bytes, a.seconds)
    budget.end, budget.read_reserved = deadline, reader.used
    budget.check()
    require(str(ordinary_directory(a.config_root)) == a.config_root
            and str(ordinary_directory(a.evidence_root)) == a.evidence_root
            and a.config_root == a.evidence_root,
            "one canonical ordinary private configuration/evidence root required")
    config_pin = {"path": a.config_path, "bytes": a.config_bytes, "sha256": a.config_sha256}
    config = document(a.config_root, config_pin, 2**20, budget)
    legacy_pins = {row["path"]: row for row in manifest["legacy_files"]}
    result = run_configuration(config, evidence_root=a.evidence_root,
        authorization_pin={"path": a.authorization_path, "bytes": a.authorization_bytes,
                           "sha256": a.authorization_sha256},
        source_sha256=a.manifest_sha256, legacy_root=a.legacy_root,
        legacy_pins=legacy_pins, budget=budget)
    budget.write(65536)
    output = json.dumps(result, sort_keys=True)
    require(len(output.encode()) + 1 <= 65536, "final result output bound")
    budget.check()
    print(output)


if __name__ == "__main__":
    main()
