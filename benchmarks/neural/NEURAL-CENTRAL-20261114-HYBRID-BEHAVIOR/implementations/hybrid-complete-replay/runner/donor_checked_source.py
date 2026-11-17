"""Standard-library custody helpers; no native imports or ambient source paths."""
import hashlib
import json
import os
from pathlib import Path
import stat
import types
import sys


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def strict(body):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    return json.loads(body, object_pairs_hook=pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def stamp(s):
    return {k: getattr(s, k) for k in ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")}


def ordinary_path(path):
    path = Path(path)
    need(path.is_absolute(), "absolute selected path")
    need(not any(p.is_symlink() for p in (path, *path.parents)), "selected ancestor symlink")
    return path


def exact(path, descriptor, cap=1048576):
    path = ordinary_path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        first = os.fstat(fd)
        need(stat.S_ISREG(first.st_mode) and first.st_nlink == 1 and
             first.st_size == descriptor["bytes"] <= cap, "ordinary exact finite source")
        body = bytearray()
        while len(body) < first.st_size:
            part = os.read(fd, min(65536, first.st_size - len(body)))
            need(part, "source premature EOF")
            body.extend(part)
        need(not os.read(fd, 1) and stamp(first) == stamp(os.fstat(fd)), "source stability/tail")
        need(hashlib.sha256(body).hexdigest() == descriptor["sha256"], "source SHA256")
        return bytes(body)
    finally:
        os.close(fd)


def load_graph(here, lock_sha):
    p = ordinary_path(here / "SOURCE_LOCK.json")
    raw = exact(p, {"bytes": p.lstat().st_size, "sha256": lock_sha}, 65536)
    lock = strict(raw)
    need(lock["schema"] == "compositional_native_source_lock_v1", "source lock schema")
    bodies = {}
    total = len(raw)
    for name, row in lock["files"].items():
        need(Path(name).name == name and name not in bodies, "flat unique source graph")
        total += row["bytes"]
        need(total <= 1048576, "whole source graph one MiB")
        bodies[name] = exact(here / name, row)
    return bodies, total


def module(name, sources, here):
    m = types.ModuleType(name)
    m.__file__ = str(here / (name + ".py"))
    need(name not in sys.modules, "source module already loaded")
    sys.modules[name] = m
    try:
        exec(compile(sources[name + ".py"], m.__file__, "exec"), m.__dict__)
    except BaseException:
        del sys.modules[name]
        raise
    return m


def encode(obj):
    return (json.dumps(obj, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n").encode()


def write_new(path, body, cap):
    ordinary_path(path)
    need(len(body) <= cap, "complete output cap")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        view = memoryview(body)
        while view:
            n = os.write(fd, view)
            need(n > 0, "complete owned write")
            view = view[n:]
        os.fsync(fd)
        os.fchmod(fd, 0o400)
    finally:
        os.close(fd)
