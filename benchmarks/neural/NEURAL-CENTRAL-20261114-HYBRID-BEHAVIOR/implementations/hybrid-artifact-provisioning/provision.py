"""Hybrid-only source provisioning. Never dispatch, fit, install or read models.

`locations` reads the operator's exact existing reference metadata. `bind` reads
only pinned source and binds the operator-provided location-map descriptor. Both
are prospective operator commands; source tests use invented metadata only.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import stat
import types

HERE = Path(__file__).absolute().parent

def verified_bootstrap():
    # The entry script is the selected trust root. Authenticate the only local
    # bootstrap helper before executing any of its code or loading a manifest.
    path = HERE / "source_binding.py"
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("bootstrap ordinary path")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        stamp = lambda x: (x.st_dev, x.st_ino, x.st_mode, x.st_nlink, x.st_size, x.st_mtime_ns, x.st_ctime_ns)
        if not (stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == 4147):
            raise ValueError("bootstrap exact ordinary extent")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            body = stream.read(4148)
        if not (len(body) == 4147 and stamp(before) == stamp(os.fstat(fd)) == stamp(path.lstat()) and
                hashlib.sha256(body).hexdigest() == "1079a68cb275a35543f02dff2ad973ef2ae2e89b85c72fab9263d00eee89c3ce"):
            raise ValueError("bootstrap stable literal identity")
    finally:
        os.close(fd)
    if "source_binding" in sys.modules:
        raise ValueError("bootstrap fresh module namespace")
    module = types.ModuleType("source_binding")
    module.__file__ = str(path)
    sys.modules["source_binding"] = module
    try:
        exec(compile(body, str(path), "exec"), module.__dict__)
    except BaseException:
        sys.modules.pop("source_binding", None)
        raise
    return module


binding = verified_bootstrap()
PREDECESSOR_LOCK = (14901, "3d32d30be647607107223ef71d043c0c6d8ac11b66cd05162aeed07becba78d2")
REFERENCE = (351850, "f9bb15d421d9182b594225c501214269af86ea9b89c83480bd4320efd1d702d5")
REPLACEMENTS = {"reuse_delivery.py", "operation_worker.py", "operation_outer.py"}
ADAPTER_PINS = {
    "reuse_delivery.py": (17665, "73fcc337a6fbb9c57fb5a5b223f0d612549a9b7fe1b6dd2e2a7e037e7b5f9e50"),
    "operation_worker.py": (6106, "b1d123b1acde34b0189a9890b18b9988ceefa249d34d04a48cf351d5cdb75002"),
    "operation_outer.py": (13045, "5983c0067d9d3a441025d792518f17a38ecf31eaabba6683ac99b6dbfee0a350"),
}
MAX_MAP = 131072


def sha(body):
    return hashlib.sha256(body).hexdigest()


def canonical(value):
    # Exact producer canonicalization used for historical_record_sha256.
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def strict(body):
    def pairs(rows):
        result = {}
        for key, value in rows:
            binding.need(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    return json.loads(body, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def absolute(value):
    binding.need(type(value) is str and 0 < len(value) <= 4096 and "\x00" not in value,
                 "bounded absolute selected path")
    p = Path(value)
    binding.need(p.is_absolute() and ".." not in p.parts and str(p) == value and
                 not any(x.is_symlink() for x in (p, *p.parents)), "ordinary canonical path")
    return p


def descriptor(path, size, digest, cap):
    absolute(path)
    binding.need(type(size) is int and 0 < size <= cap and type(digest) is str and
                 re.fullmatch("[0-9a-f]{64}", digest) is not None, "typed exact selected descriptor")
    return {"path": path, "bytes": size, "sha256": digest}


def write(path, body):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    return {"path": str(path), "bytes": len(body), "sha256": sha(body)}


def admit_source(expected):
    manifest = HERE / "SOURCE_MANIFEST.json"
    raw = binding.exact(manifest, {"bytes": manifest.lstat().st_size, "sha256": expected}, 65536)
    value = strict(raw)
    binding.need(value["schema"] == "hybrid-relocation-source-v1", "source manifest schema")
    members = value["files"]
    binding.need(len(members) <= 12 and len({p["name"] for p in members}) == len(members), "finite source roster")
    bodies = {}
    for pin in members:
        name = pin["name"]
        binding.need(type(name) is str and Path(name).name == name, "flat source member")
        bodies[name] = binding.exact(HERE / name, pin, 262144)
    binding.need({"provision.py", "source_binding.py", "test_provision.py"} <= bodies.keys(), "complete required source")
    return bodies


def locations_from_reference(value, artifact_directory, reference_pin):
    """No outcome extraction; preserve names, full80 records and original hashes."""
    root = absolute(str(artifact_directory))
    binding.need(value["schema"] == "hybrid-complete-train-only-reference-v1" and
                 type(value["complete_outer_folds"]) is int and value["complete_outer_folds"] == 80 and
                 value["inner_ridge_fits"] == 720 and value["final_ridge_fits"] == 80,
                 "complete historical reference metadata")
    records = value["artifact_manifest_private"]
    binding.need(type(records) is list and len(records) == 80, "all80 historical records")
    rows, names, keys = [], set(), set()
    for record in records:
        pin = record["artifacts"]["family_train_selected"]
        binding.need(type(pin) is dict and set(pin) == {"path", "bytes", "sha256"}, "historical artifact pin")
        descriptor(pin["path"], pin["bytes"], pin["sha256"], 65536)
        name, key = Path(pin["path"]).name, sha(canonical(record))
        binding.need(name not in names and key not in keys, "unique unchanged artifact basenames and records")
        names.add(name); keys.add(key)
        rows.append({"historical_record_sha256": key,
                     "location": descriptor(str(root / name), pin["bytes"], pin["sha256"], 65536)})
    result = {"schema": "hybrid-historical-artifact-locations-v1",
              "reference_result": {"bytes": reference_pin[0], "sha256": reference_pin[1]}, "folds": rows}
    binding.need(len(canonical(result)) + 1 <= MAX_MAP, "complete location-map cap")
    return result


def admit_predecessor(directory):
    """Read exact external source, never import it or read its data operands.

    Operation-local files may be held at the supplied directory. Other43-lock
    dependencies remain at their exact paths in the operator's private lock.
    """
    root = absolute(directory)
    raw = binding.exact(root / "SOURCE_LOCK.json", {"bytes": PREDECESSOR_LOCK[0], "sha256": PREDECESSOR_LOCK[1]}, 262144)
    lock = strict(raw)
    binding.need(lock["member_count"] == 43 and len(lock["files"]) == 43 and
                 len({p["path"] for p in lock["files"]}) == 43, "exact prior43-source closure")
    origins = [Path(p["path"]).parent for p in lock["files"] if Path(p["path"]).name == "source_binding.py" and
               p["bytes"] == 4147 and p["sha256"] == "1079a68cb275a35543f02dff2ad973ef2ae2e89b85c72fab9263d00eee89c3ce"]
    binding.need(len(origins) == 1, "unique bound predecessor operation origin")
    origin = origins[0]
    old = {}
    for pin in lock["files"]:
        original = Path(pin["path"])
        selected = root / original.name if original.parent == origin else original
        old[pin["path"]] = binding.exact(selected, pin)
    binding.need(sum(map(len, old.values())) == lock["member_bytes"] == 365603,
                 "complete unchanged predecessor source extent")
    return lock, old, origin


def admit_adapters(directory):
    root = absolute(directory)
    return {name: binding.exact(root / name, {"bytes": pin[0], "sha256": pin[1]}, 262144)
            for name, pin in ADAPTER_PINS.items()}


def compose(admitted, bodies, destination, locations, output, caller, capacity, token, cases_path, reference_path):
    """Copy the existing43-source operation; change only named provisioning fields."""
    binding.need(type(locations) is dict and set(locations) == {"path", "bytes", "sha256"}, "closed selected location descriptor")
    locations = descriptor(locations["path"], locations["bytes"], locations["sha256"], MAX_MAP)
    binding.need(re.fullmatch("nb-hybrid-[a-z0-9-]{1,48}", token) is not None, "bounded operation token")
    dest, out, call, cap = map(absolute, (destination, output, caller, capacity))
    chosen = [dest, out, call, cap, absolute(locations["path"])]
    binding.need(len(set(chosen)) == len(chosen) and all(a not in b.parents for a in chosen for b in chosen if a != b),
                 "distinct nonoverlapping source/map/output/caller/capacity paths")
    binding.need(all(not p.exists() for p in (dest, out, call, cap)), "fresh selected namespaces")
    lock, old, origin = admitted
    # A fresh local object prevents the caller's admitted record being changed.
    lock = strict(canonical(lock))
    plan = strict(old[str(origin / "PLAN.json")])
    plan["cases"]["path"] = str(absolute(cases_path))
    plan["references"]["path"] = str(absolute(reference_path))
    plan.update(output=str(out), caller=str(call), capacity_binding=str(cap), operation_token=token,
                historical_artifact_locations=locations)
    plan["docker_prefix"][-1] = str(out / "empty-docker-config")
    plan["producer_delivery_source_closure"]["historical_reuse_adapter_sha256"] = sha(bodies["reuse_delivery.py"])
    bounds = strict(old[str(origin / "READ_BOUNDS.json")])
    bounds["components"].append({"name": "exact_external_historical_artifact_locations", "maximum_bytes": MAX_MAP,
                                "derivation": "One bounded worker read; subsequent map snapshot check is metadata-only. Source growth remains within unchanged64MiB source union allowance; signed reuse still capped1MiB."})
    bounds["sum_maximum_bytes"] += MAX_MAP
    binding.need(bounds["sum_maximum_bytes"] <= bounds["selected_proposal_ceiling_bytes"], "unchanged whole read ceiling")
    dest.mkdir(mode=0o700)
    selected = []
    for pin in lock["files"]:
        path = Path(pin["path"])
        if path.parent != origin:
            selected.append(pin)
            continue
        name = path.name
        body = bodies[name] if name in REPLACEMENTS else old[str(path)]
        if name == "PLAN.json":
            body = (json.dumps(plan, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
        elif name == "READ_BOUNDS.json":
            body = (json.dumps(bounds, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
        selected.append(write(dest / name, body))
    lock.update(files=selected, member_count=len(selected), member_bytes=sum(p["bytes"] for p in selected))
    binding.need(lock["member_bytes"] < 4 * 1048576, "unchanged source union ceiling")
    lock_pin = write(dest / "SOURCE_LOCK.json", (json.dumps(lock, indent=2, sort_keys=True) + "\n").encode())
    proposal = {"schema": "hybrid-relocated-no-refit-replay-proposal-v1", "selected_for_execution": False,
        "source_lock": lock_pin, "historical_artifact_locations": locations,
        "argv": [plan["base_entry"]["path"], "-I", "-S", "-B", str(dest / "operation_outer.py"), "--lock-sha256", lock_pin["sha256"]],
        "unchanged_scope": plan["scope"], "unchanged_image": plan["image"], "new_fits": 0,
        "required_before_selection": ["independently reviewed composed proposal and exact current runtime/physical endpoint",
            "operator-authorized private cases/reference/all80 artifact provision", "fresh capacity record bound to this source lock",
            "complete24GiB output reservation and unchanged whole-operation deadlines"],
        "limits": "Location map has not been opened by bind; exact schema/all80 record/byte/hash/selection checks happen in unchanged-scope preparation. No availability or runtime qualification is asserted."}
    write(dest / "NEXT_OPERATION_PROPOSAL.json", (json.dumps(proposal, indent=2, sort_keys=True) + "\n").encode())
    return proposal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest-sha256", required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    loc = sub.add_parser("locations")
    loc.add_argument("--reference", required=True)
    loc.add_argument("--artifact-directory", required=True)
    loc.add_argument("--output", required=True)
    bind = sub.add_parser("bind")
    for name in ("locations", "locations-sha256", "destination", "output", "caller", "capacity-binding", "operation-token", "predecessor-directory", "adapters-directory", "cases", "reference"):
        bind.add_argument("--" + name, required=True)
    bind.add_argument("--locations-bytes", required=True, type=int)
    args = parser.parse_args()
    bodies = admit_source(args.source_manifest_sha256)
    if args.command == "locations":
        raw = binding.exact(absolute(args.reference), {"bytes": REFERENCE[0], "sha256": REFERENCE[1]}, 2 * 1048576)
        result = locations_from_reference(strict(raw), args.artifact_directory, REFERENCE)
        path = absolute(args.output)
        pin = write(path, canonical(result) + b"\n")
        print(json.dumps({"location_map": pin, "model_bodies_read": False, "availability_verified": False}))
    else:
        locations = descriptor(args.locations, args.locations_bytes, args.locations_sha256, MAX_MAP)
        predecessor = admit_predecessor(args.predecessor_directory)
        adapters = admit_adapters(args.adapters_directory)
        result = compose(predecessor, adapters, args.destination, locations, args.output, args.caller,
                         args.capacity_binding, args.operation_token, args.cases, args.reference)
        print(json.dumps({"source_lock": result["source_lock"], "argv": result["argv"], "selected_for_execution": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
