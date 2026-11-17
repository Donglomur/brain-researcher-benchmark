"""Selected synthetic controls only; never a production admission or runner."""
import contextlib
import hashlib
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import time
import types

MANIFEST_BYTES = 6283
MANIFEST_SHA256 = "987410573a680c23a6e21157b96bc829c1480a5da8c0d8eb7620eee895e16daa"


def require(value, message):
    if not value:
        raise AssertionError(message)


class Meter:
    def __init__(self, transfer, seconds):
        require(type(transfer) is int and transfer > 0 and 0 < seconds <= 120,
                "selected finite engineering envelope")
        self.cap, self.end = transfer, time.monotonic() + seconds
        self.read_used = self.write_used = 0
        self.charges = []

    def check(self):
        require(time.monotonic() < self.end, "original engineering deadline")

    def charge(self, *, read=0, write=0, label):
        self.check()
        require(type(read) is type(write) is int and min(read, write) >= 0,
                "typed nonnegative engineering reservation")
        require(self.read_used + self.write_used + read + write <= self.cap,
                "prospective cumulative engineering transfer")
        self.read_used += read
        self.write_used += write
        require(len(self.charges) < 4096, "finite reservation ledger")
        self.charges.append({"read": read, "write": write, "label": label})

    def read(self, value):
        self.charge(read=value, label="actual storage Budget.read reservation")

    def write(self, value):
        self.charge(write=value, label="actual storage Budget.write reservation")

    def snapshot(self):
        return {"read_reserved": self.read_used, "write_reserved": self.write_used,
                "cap": self.cap, "charges": list(self.charges)}


def read_pin(root, pin, meter):
    p = Path(root) / pin["path"]
    require(p.is_relative_to(root), "selected relative source")
    require(type(pin["bytes"]) is int and 0 < pin["bytes"] <= 2**20, "source member cap")
    meter.charge(read=2 * pin["bytes"] + 1, write=2 * pin["bytes"], label="capture/hash source " + pin["path"])
    for parent in (p.parent, *p.parent.parents):
        require(stat.S_ISDIR(parent.lstat().st_mode) and not parent.is_symlink(), "ordinary source ancestry")
    before = p.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == pin["bytes"], "ordinary pinned source")
    fd, first, secondary, result = None, None, [], None
    try:
        fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        opened = os.fstat(fd)
        body = bytearray()
        while len(body) <= pin["bytes"]:
            part = os.read(fd, min(65536, pin["bytes"] + 1 - len(body)))
            if not part:
                break
            body.extend(part)
        after = os.fstat(fd)
        stamp = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        require(stamp(before) == stamp(opened) == stamp(after) == stamp(p.lstat()), "stable source")
        require(len(body) == pin["bytes"] and hashlib.sha256(body).hexdigest() == pin["sha256"], "exact source pin")
        result = bytes(body)
    except BaseException as exc:
        first = exc
    finally:
        if fd is not None:
            try: os.close(fd)
            except BaseException as exc:
                if first is None: first = exc
                else: secondary.append(exc)
    if first is not None:
        first.morse_control_secondary_errors = tuple(getattr(first, "morse_control_secondary_errors", ())) + tuple(secondary)
        raise first
    return result


class Sources(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """Authenticates all32 bodies; only selected nonnumerical names are loaded."""
    def __init__(self, package, legacy, meter):
        self.meter, self.loaded, self.substituted = meter, set(), {}
        self.package, self.legacy = Path(package), Path(legacy)
        pin = {"path": "SOURCE_MANIFEST.json", "bytes": MANIFEST_BYTES, "sha256": MANIFEST_SHA256}
        self.manifest = json.loads(read_pin(self.package, pin, meter))
        values = {}
        for area, root, rows in (("local", self.package, self.manifest["files"]),
                                 ("legacy", self.legacy, self.manifest["legacy_files"])):
            for row in rows:
                values[area + ":" + row["path"]] = (str(root / row["path"]), read_pin(root, row, meter))
        self.bodies = {n: values[k] for n, k in self.manifest["module_map"].items()}
        self.entry = values["local:operator_entry.py"]
        require(len(values) == 32 and len(self.bodies) == 24, "complete frozen source inventory")
        require(not any(n in sys.modules for n in self.bodies), "clean task namespaces")

    def find_spec(self, fullname, path=None, target=None):
        if fullname in self.bodies:
            return importlib.util.spec_from_loader(fullname, self)
        return None

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        require(module.__name__ not in {"morse_codec", "morse_views", "morse_capture", "morse_reports",
                "provider", "packets", "preprocessing", "baselines", "reference_pipeline", "scorer", "task_operator"},
                "unselected numerical/data module import")
        path, body = self.bodies[module.__name__]
        self.meter.charge(read=len(body), write=len(body), label="compile selected source " + module.__name__)
        module.__file__ = path
        self.loaded.add(module.__name__)
        exec(compile(body, path, "exec"), module.__dict__)

    def load(self, name):
        if name in sys.modules:
            return sys.modules[name]
        spec = self.find_spec(name)
        require(spec is not None, "captured module name")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            self.exec_module(module)
        except BaseException:
            sys.modules.pop(name, None)
            raise
        return module

    def fresh(self, name):
        path, body = self.bodies[name]
        self.meter.charge(read=len(body), write=len(body), label="fresh exact source " + name)
        module = types.ModuleType(name + "_control_fresh")
        module.__file__ = path
        exec(compile(body, path, "exec"), module.__dict__)
        return module

    def shim(self, name, **attrs):
        require(name not in sys.modules, "explicit fresh inert leaf namespace")
        module = types.ModuleType(name)
        module.__dict__.update(attrs)
        self.substituted[name] = module
        sys.modules[name] = module
        return module

    def __enter__(self):
        sys.meta_path.insert(0, self)
        return self

    def __exit__(self, *exc):
        if self in sys.meta_path:
            sys.meta_path.remove(self)
        for name in self.loaded | set(self.substituted):
            sys.modules.pop(name, None)


@contextlib.contextmanager
def patched(obj, **attrs):
    old = {k: getattr(obj, k) for k in attrs}
    try:
        for key, value in attrs.items():
            setattr(obj, key, value)
        yield
    finally:
        for key, value in old.items():
            setattr(obj, key, value)


def refuses(fn, text=None):
    try:
        fn()
    except Exception as exc:
        if text is not None:
            require(text in str(exc), "expected refusal reason: " + text)
        return exc
    raise AssertionError("required refusal was not observed")


class CaseLog:
    def __init__(self):
        self.rows = []

    def passed(self, name, **evidence):
        require(len(self.rows) < 128, "finite case count")
        self.rows.append({"case": name, "status": "PASS", **evidence})
