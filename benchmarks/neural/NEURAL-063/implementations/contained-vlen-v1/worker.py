"""Fixed NEURAL-063 contained worker entry; deployment remains unselected.

The future authenticated operator supplies two exact SHA256 arguments after
owning the container. This file does not launch Docker or prove kernel controls.
The Linux-local work/export duration is additional to the authoritative host
deadline, whose monotonic epoch is deliberately never compared here.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import stat
import sys
import time
import types

ORIGINAL = {
    "owner/__init__.py": (80, "d857d613efdca2fad6b20a106349516a410e2837b5f4bff6b6d2db592ba58658"),
    "owner/io.py": (10152, "8e29aa60a95b8433361bda241ee60e25db40c0884547c7bc55d5015c4741ad4e"),
    "owner/scoring.py": (12817, "e85413e3af2b63c919fbfc93fffdb6fc0e37af9d038f693df99da980b04dc0dc"),
    "preparation/__init__.py": (82, "a852591a1dea52c60ea4a6cacb06b150e49397ac9189d2120e8dc7c4f9241d95"),
    "preparation/algorithm.py": (7672, "aa5255ba1d238331cc91122b4b84ce2d90a0d23b7b19964ddb91c72953bac3c8"),
    "preparation/native.py": (8094, "59938e74806637cc3be504a6bcb2a550f1571d22e6d55342abdd048978389c66"),
}
RANGE = {
    "range_io.py": (15515, "73d479623f9fe78f42631aeca49113748791b5737cfe7b6aec43789737ffb7e1"),
    "manifest.py": (7952, "36b7eb96e9d40f808035979b1f30c7e103746d20d670235d8658cda613381205"),
    "pipeline.py": (20502, "ad1e2e80dc8676af208a3fee4bd0977694fc3abf145d883fbb5b8b7a17dd8f42"),
}
SELECTION = (9605316, "d484ac018c7b7a0cc9ed826de5977a9ec9724a82e68126ec7e13be23507c1ab7")
ASSETS = (1485117, "41dc23799cd96d8e9f8bf0aa0961f049187435109454a4055126d51c53f1b7d2")
SETUP_READ_LIMIT = 67108864
SETUP_READ_REQUESTED = 0


def need(ok, message):
    if not ok:
        raise ValueError(message)


def strict(body):
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    def bad(_):
        raise ValueError("nonfinite JSON")
    return json.loads(body, object_pairs_hook=pairs, parse_constant=bad)


def read_pinned(path, count, digest, cap):
    global SETUP_READ_REQUESTED
    p = Path(path)
    need(type(count) is int and 0 < count <= cap and type(digest) is str
         and re.fullmatch(r"[0-9a-f]{64}", digest), "finite pinned input")
    need(p.is_absolute() and str(p) == os.path.normpath(str(p))
         and all(not x.is_symlink() for x in (p, *p.parents)), "ordinary exact mounted input")
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    stamp = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == count,
             "complete regular input extent")
        body = bytearray()
        while len(body) < count:
            requested = min(65536, count - len(body))
            need(SETUP_READ_REQUESTED + requested <= SETUP_READ_LIMIT, "finite source setup-read envelope")
            SETUP_READ_REQUESTED += requested
            block = os.read(fd, requested)
            need(block, "complete mounted input")
            body.extend(block)
        need(SETUP_READ_REQUESTED + 1 <= SETUP_READ_LIMIT, "setup EOF reservation")
        SETUP_READ_REQUESTED += 1
        need(not os.read(fd, 1) and stamp(before) == stamp(os.fstat(fd)) == stamp(p.lstat()),
             "same-FD complete mounted input")
    finally:
        os.close(fd)
    need(hashlib.sha256(body).hexdigest() == digest, "mounted input/source SHA256")
    return bytes(body)


def input_json(ref, path, cap):
    need(type(ref) is dict and set(ref) == {"path", "bytes", "sha256"}
         and ref["path"] == path, "fixed input descriptor")
    return strict(read_pinned(path, ref["bytes"], ref["sha256"], cap))


def unwrap_selection(value):
    """Retain the authenticated wrapper identity; use its original science table."""
    need(type(value) is dict and type(value.get("original_selection")) is dict,
         "authenticated original-selection wrapper required")
    return value["original_selection"]


def load_sources(contract):
    """Authenticate all bytes before compiling any scientific module; no pyc."""
    expected = {"original/" + name: pin for name, pin in ORIGINAL.items()}
    expected.update({"range/" + name: pin for name, pin in RANGE.items()})
    need(set(contract["sources"]) == set(expected) | {"scientific_adapter.py", "worker.py"},
         "exact nine frozen dependencies plus reviewed adapter/entry")
    bodies = {}
    for name, ref in contract["sources"].items():
        need(set(ref) == {"path", "bytes", "sha256"} and ref["path"] == "/operator/" + name,
             "fixed source mount")
        if name in expected:
            need((ref["bytes"], ref["sha256"]) == expected[name], "unchanged scientific source pin")
        bodies[name] = read_pinned(ref["path"], ref["bytes"], ref["sha256"], 131072)
    need(Path(__file__).absolute() == Path("/operator/worker.py"), "fixed worker entry origin")
    order = [("owner", "original/owner/__init__.py"), ("owner.io", "original/owner/io.py"),
             ("owner.scoring", "original/owner/scoring.py"), ("preparation", "original/preparation/__init__.py"),
             ("preparation.algorithm", "original/preparation/algorithm.py"),
             ("preparation.native", "original/preparation/native.py"),
             ("range_io", "range/range_io.py"), ("manifest", "range/manifest.py"),
             ("pipeline", "range/pipeline.py"), ("n063_adapter", "scientific_adapter.py")]
    need(not any(name in sys.modules for name, _ in order), "fresh verified module namespace")
    loaded = {}
    for name, relative in order:
        module = types.ModuleType(name)
        module.__file__ = "/operator/" + relative
        module.__package__ = name if name in ("owner", "preparation") else name.rpartition(".")[0]
        if name in ("owner", "preparation"):
            module.__path__ = []
        sys.modules[name] = module
        loaded[name] = module
        exec(compile(bodies[relative], module.__file__, "exec"), module.__dict__)
    deps = types.SimpleNamespace(native=loaded["preparation.native"], algorithm=loaded["preparation.algorithm"],
        pipeline=loaded["pipeline"], range=loaded["range_io"], manifest=loaded["manifest"])
    return loaded["n063_adapter"], deps


def finite_export_barrier(end, publish_ready):
    """A bounded one-shot hold, never a persistent service or success certificate."""
    released = False
    def release(_number, _frame):
        nonlocal released
        released = True
    previous = signal.signal(signal.SIGTERM, release)
    try:
        publish_ready()
        while not released:
            need(time.monotonic() < end, "container-local export barrier expired")
            time.sleep(min(0.05, max(0, end - time.monotonic())))
        need(time.monotonic() < end, "late export release")
    finally:
        signal.signal(signal.SIGTERM, previous)



def seal_ready(body):
    """Small fixed control output; its whole 16 KiB allowance stays charged."""
    need(type(body) is bytes and 0 < len(body) <= 8192, "bounded READY control body")
    path = Path("/output/READY.json")
    need(not path.parent.is_symlink() and path.parent.is_dir(), "owned output tmpfs")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        need(os.write(fd, body) == len(body), "complete exclusive READY write")
        os.fsync(fd)
        os.fchmod(fd, 0o444)
        before, named = os.fstat(fd), path.lstat()
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and (before.st_dev, before.st_ino, before.st_size) ==
                 (named.st_dev, named.st_ino, len(body)), "same-FD sealed READY")
    finally:
        os.close(fd)
    parent_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)


def main(argv=None):
    started = time.monotonic()
    args = sys.argv[1:] if argv is None else argv
    try:
        need(len(args) == 4 and args[0] == "--contract-sha256" and args[2] == "--admission-sha256"
             and all(re.fullmatch(r"[0-9a-f]{64}", args[i]) for i in (1, 3)), "fixed worker CLI")
        # Descriptor sizes are in small sidecars supplied by the authenticated
        # operator after container ownership. Their SHA arguments bind content.
        cp, ap = Path("/inputs/worker_contract.json"), Path("/inputs/admission.json")
        contract = strict(read_pinned(cp, cp.lstat().st_size, args[1], 32768))
        admission = strict(read_pinned(ap, ap.lstat().st_size, args[3], 8192))
        need(set(contract) == {"schema", "execute", "sources", "profile", "selection", "assets",
             "layout", "plane_inputs", "completed_inventory"}, "exact fixed worker contract")
        need(contract["schema"] == "neural063-contained-worker-contract-v1" and contract["execute"] is True,
             "inactive worker preparation")
        profile = input_json(contract["profile"], "/inputs/profile.json", 65536)
        need(profile.get("selected") is True and profile.get("runtime_qualified") is True,
             "unresolved source-only deployment")
        need("container_deadline_monotonic" not in admission and "clock_domain" not in admission,
             "host must not supply a cross-kernel monotonic timestamp")
        duration = admission.pop("worker_duration_seconds")
        need(type(duration) is int and 0 < duration <= 1800
             and admission.get("kind") in ("plane", "session")
             and duration <= profile["unit_seconds"][admission["kind"]], "finite worker-local duration")
        admission["container_deadline_monotonic"] = started + duration
        admission["clock_domain"] = "linux_container_monotonic"
        adapter, deps = load_sources(contract)
        adapter.validate_profile(profile)
        adapter.admitted(profile, admission, admission["kind"], admission["identity"])
        need((contract["selection"]["bytes"], contract["selection"]["sha256"]) == SELECTION
             and (contract["assets"]["bytes"], contract["assets"]["sha256"]) == ASSETS,
             "original full-scope input pins")
        selection = unwrap_selection(input_json(contract["selection"], "/inputs/selection.json", 16777216))
        assets_manifest = input_json(contract["assets"], "/inputs/assets.json", 2097152)
        rows = deps.manifest.full_scope(selection)
        assets = deps.manifest.validate_assets(assets_manifest, selection)
        need(admission["selection_sha256"] == deps.manifest.SELECTION_SHA256
             and admission["assets_sha256"] == deps.pipeline.digest(assets_manifest), "full-scope admission binding")
        identity = admission["identity"]
        if admission["kind"] == "plane":
            matching = [r for r in rows if r["ophys_experiment_id"] == identity]
            need(len(matching) == 1, "one original plane")
            layout = input_json(contract["layout"], "/inputs/layout.json", 4194304)
            budget = deps.range.Budget(deps.range.Limits(**profile["plane_range_limits"]))
            result = adapter.decode_plane(assets[identity], matching[0], layout, deps=deps,
                ranges=budget, runtime=profile["runtime_versions"], profile=profile, admission=admission)
        else:
            refs = input_json(contract["plane_inputs"], "/inputs/plane_inputs.json", 1048576)
            custody = input_json(contract["completed_inventory"], "/inputs/completed_inventory.json", 1048576)
            need(contract["completed_inventory"]["sha256"] == admission["completed_inventory_sha256"]
                 and custody["kind"] == "session" and custody["identity"] == identity,
                 "same authenticated complete-plane custody record")
            custody_rows = {r["experiment"]: r for r in custody["plane_custody"]}
            expected = {r["ophys_experiment_id"] for r in rows if r["ophys_session_id"] == identity}
            need(len(custody["plane_custody"]) == len(expected) and set(custody_rows) == expected,
                 "complete original session custody")
            for ref in refs:
                saved = custody_rows[ref["experiment"]]
                need(saved["state"] == "complete" and saved["artifact"] == {
                     "name": "plane_metadata.json", "bytes": ref["bytes"], "sha256": ref["sha256"]},
                     "completed host inventory and mounted plane artifact agree")
            result = adapter.derive_complete_session(selection, assets_manifest, identity, refs,
                deps=deps, profile=profile, admission=admission)
        ready = adapter.canonical({"schema": "neural063-contained-ready-v1", "kind": admission["kind"],
            "identity": identity, "container_id": admission["container_id"],
            "reservation_sha256": admission["reservation_sha256"], "result": result,
            "source_setup_read_bytes": SETUP_READ_REQUESTED,
            "producer_returned_successfully": True, "container_exit_or_export_not_yet_proven": True})
        need(len(ready) <= 8192, "bounded ready descriptor")
        finite_export_barrier(admission["container_deadline_monotonic"], lambda: seal_ready(ready))
        return 0
    except BaseException as exc:
        os.write(2, ("N063 worker refused: " + type(exc).__name__ + "\n").encode())
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
