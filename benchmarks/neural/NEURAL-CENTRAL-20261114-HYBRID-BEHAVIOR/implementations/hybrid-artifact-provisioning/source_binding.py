"""Literal source loading for the no-refit Hybrid successor. Import is inert."""
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import types


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def exact(path, pin, cap=1048576):
    path = Path(path)
    need(path.is_absolute() and ".." not in path.parts and
         not any(p.is_symlink() for p in (path, *path.parents)), "ordinary absolute source")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
             0 < before.st_size == pin["bytes"] <= cap, "exact bounded source extent")
        with os.fdopen(fd, "rb", closefd=False) as f:
            body = f.read(before.st_size + 1)
        stamp = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size,
                           s.st_mtime_ns, s.st_ctime_ns)
        need(stamp(before) == stamp(os.fstat(fd)) == stamp(path.lstat()), "stable source")
        need(len(body) == pin["bytes"] and hashlib.sha256(body).hexdigest() == pin["sha256"],
             "exact source digest")
        return body
    finally:
        os.close(fd)


def module(name, path, body):
    need(name not in sys.modules, "fresh exact module namespace: " + name)
    obj = types.ModuleType(name)
    obj.__file__ = str(path)
    sys.modules[name] = obj
    try:
        exec(compile(body, str(path), "exec"), obj.__dict__)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return obj


def load(lock_sha, here=None):
    """Authenticate the entire declared union before loading any dependency."""
    here = Path(__file__).absolute().parent if here is None else Path(here)
    lp = here / "SOURCE_LOCK.json"
    st = lp.lstat()
    raw = exact(lp, {"bytes": st.st_size, "sha256": lock_sha}, 262144)
    lock = json.loads(raw)
    need(lock["schema"] == "hybrid-no-refit-complete-operation-source-v1", "successor source lock")
    need(len(lock["files"]) <= 64 and len({x["path"] for x in lock["files"]}) == len(lock["files"]),
         "bounded unique literal source closure")
    bodies = {x["path"]: exact(x["path"], x) for x in lock["files"]}
    need(sum(map(len, bodies.values())) <= 4 * 1048576, "complete source closure cap")
    plan = json.loads(bodies[str(here / "PLAN.json")])
    plan["source_lock_sha256"] = lock_sha
    integration = Path(plan["integration_root"]) / "protected_delivery.py"
    delivery = module("protected_delivery", integration, bodies[str(integration)])
    sources = delivery.Sources(plan["training_root"], plan["runner_root"])
    owner_path = Path(plan["runner_root"]) / "owner_core.py"
    owner = module("hybrid_successor_owner_core", owner_path, bodies[str(owner_path)])
    modules = {}
    for name in ("reuse_delivery", "result_contract"):
        path = here / (name + ".py")
        modules[name] = module(name, path, bodies[str(path)])
    sources.export = modules["reuse_delivery"].HistoricalExportVerifier(sources.export, sources.artifact)
    sources.closure = dict(sources.closure,
        historical_reuse_adapter_sha256=hashlib.sha256(bodies[str(here / "reuse_delivery.py")]).hexdigest())
    need(sources.closure == plan["producer_delivery_source_closure"], "exact selected integration and historical verifier closure")
    for pin in lock["files"]:
        sources.snapshots.append(delivery.Snapshot(pin["path"], (pin["bytes"], pin["sha256"])))
    sources.snapshots.append(delivery.Snapshot(lp, (len(raw), lock_sha)))
    sources.check()
    return plan, lock, bodies, delivery, sources, owner, modules


def recheck(lock):
    for pin in lock["files"]:
        exact(pin["path"], pin)


def emit(path, value, cap=1048576):
    body = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    need(0 < len(body) <= cap, "bounded complete JSON output")
    with Path(path).open("xb") as f:
        f.write(body)
        f.flush()
        os.fsync(f.fileno())
    return {"path": str(path), "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
