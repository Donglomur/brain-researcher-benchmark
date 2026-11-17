"""Bind existing private metadata to the existing complete-census owner.

Creates a request and software lock only. Never acquires data, imports native
libraries, starts the owner, changes Git, or grants scientific qualification.
"""
import argparse
import hashlib
import os
import stat
import types
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CURRENT_MANIFEST = ROOT / "benchmarks/integrity/current-closures/findlay-sleep/source-manifest.json"


def need(ok, message):
    if not ok:
        raise ValueError(message)


def capture(path, cap):
    """Bounded bootstrap read; authenticate the bytes that will actually execute."""
    path = Path(path)
    need(path.is_absolute() and ".." not in path.parts
         and not any(x.is_symlink() for x in (path, *path.parents)), "Ordinary bootstrap path")
    def identity(value):
        return (value.st_dev, value.st_ino, value.st_mode, value.st_nlink,
                value.st_size, value.st_mtime_ns, value.st_ctime_ns)
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
         and 0 < before.st_size <= cap, "Bounded single-link bootstrap source")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    try:
        need(identity(os.fstat(fd)) == identity(before), "Opened bootstrap identity")
        chunks = bytearray()
        while True:
            block = os.read(fd, min(65536, cap + 1 - len(chunks)))
            if not block:
                break
            chunks.extend(block)
            need(len(chunks) <= cap, "Bootstrap body cap")
        need(identity(os.fstat(fd)) == identity(before), "Stable bootstrap descriptor")
    finally:
        os.close(fd)
    need(identity(path.lstat()) == identity(before) and len(chunks) == before.st_size,
         "Stable complete bootstrap path")
    return bytes(chunks)


def decode(body):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            need(key not in value, "Duplicate software manifest key")
            value[key] = item
        return value
    return json.loads(body, object_pairs_hook=unique,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Nonfinite manifest")))


def load(name, path, body):
    value = types.ModuleType(name)
    value.__file__ = str(path)
    exec(compile(body, str(path), "exec"), value.__dict__)
    return value


def build(arguments):
    root = ROOT
    manifest_body = capture(CURRENT_MANIFEST, 65536)
    need(len(manifest_body) <= 65536, "Finite software manifest")
    manifest = decode(manifest_body)
    need(set(manifest) == {"schema", "execution_authority", "entrypoint", "worker", "files"}
         and manifest["schema"] == "findlay-portable-source-manifest/v1"
         and manifest["execution_authority"] is False and len(manifest["files"]) == 14,
         "Complete nonauthorizing fourteen-file software closure")
    # Bootstrap the selected owner only after authenticating its software body.
    entry = manifest["entrypoint"]
    need(type(entry) is dict and set(entry) == {"path", "bytes", "sha256"}
         and type(entry["path"]) is str and not Path(entry["path"]).is_absolute()
         and ".." not in Path(entry["path"]).parts
         and type(entry["bytes"]) is int and 0 < entry["bytes"] <= 262144
         and type(entry["sha256"]) is str and re.fullmatch("[a-f0-9]{64}", entry["sha256"]),
         "Exact bounded owner source pin")
    path = root / entry["path"]
    need(not any(x.is_symlink() for x in (path, *path.parents)), "Ordinary owner path")
    body = capture(path, 262144)
    need(len(body) == entry["bytes"] and hashlib.sha256(body).hexdigest() == entry["sha256"],
         "Exact portable owner source")
    owner = load("_findlay_binding_owner", path, body)
    need(re.fullmatch("[a-f0-9]{40}", arguments.commit), "Selected public adoption commit")
    write_dir = owner.absolute(arguments.write_dir)
    need(write_dir.is_dir() and not write_dir.is_relative_to(root)
         and not any(x.is_symlink() for x in (write_dir, *write_dir.parents)),
         "Existing private unlinked binding directory outside checkout")
    for name in ("source-lock.json", "request.json"):
        need(not (write_dir / name).exists(), "Fresh binding outputs")
    output = owner.absolute(arguments.operation_output)
    need(output.is_relative_to(root / "artifacts-build") and output != root / "artifacts-build",
         "Owner output remains private artifacts-build")
    need(not output.exists() and output.parent.is_dir(), "Fresh operation output with existing parent")
    captured = {}
    for relative, pin in manifest["files"].items():
        owner.relpath(relative)
        captured[relative] = owner.checked({"path": str(root / relative), **pin})
    worker = manifest["worker"]
    contract_path = worker["path"].rsplit("/", 1)[0] + "/external_contract.py"
    need(contract_path in manifest["files"], "External validator belongs to software closure")
    contract = load("_findlay_binding_contract", root / contract_path, captured[contract_path])
    task = {}; metadata = {}
    for key in contract.PINS:
        path = owner.absolute(getattr(arguments, key))
        need(not path.is_relative_to(root), "Private metadata outside checkout")
        body = owner.capture(path, 262144)
        metadata[key] = contract.authenticate(key, body)
        task[key] = {"path": str(path), "bytes": len(body), "sha256": owner.sha(body)}
    contract.join(metadata)

    def external_pin(value, cap):
        path = owner.absolute(value)
        need(not path.is_relative_to(root), "Private operator material outside checkout")
        body = owner.capture(path, cap)
        return {"path": str(path), "bytes": len(body), "sha256": owner.sha(body)}, owner.decode(body)

    archive_path = getattr(arguments, "original_archive", None)
    prior_path = getattr(arguments, "prior_attempt", None)
    need(bool(archive_path) != bool(prior_path), "Choose original archive or prior manifest, never both")
    if archive_path:
        path = owner.absolute(archive_path)
        need(not path.is_relative_to(root)
             and not any(x.is_symlink() for x in (path, *path.parents)), "External unlinked original archive")
        observed = path.lstat()
        need(stat.S_ISREG(observed.st_mode) and observed.st_nlink == 1
             and observed.st_size == contract.ARCHIVE_PIN["bytes"], "Complete original archive extent")
        task["original_archive"] = {"path": str(path), **contract.ARCHIVE_PIN}
        contract.validate_archive_pin(task["original_archive"])
        request_schema = "findlay-portable-first-intake-request/v1"
    else:
        prior, prior_value = external_pin(prior_path, 262144)
        need(prior_value.get("schema") == "findlay-census-continuation-inputs/v1"
             and prior_value.get("prior_status") == "REFUSED",
             "Previously reviewed retained-input manifest required; no fabricated history")
        task["prior_attempt"] = prior
        request_schema = "findlay-portable-census-continuation-request/v1"
    runtime, runtime_value = external_pin(arguments.runtime_manifest, 2 * 1024**2)
    need(type(runtime_value) is dict, "Existing runtime inventory object required")
    task.update(data_read_cap=33554432, worker_output_cap=33554432)
    lock = {"schema": "findlay-intake-source-lock/v1", "repository_root": str(root),
            "execution_authority": False, "entrypoint": entry, "worker": worker,
            "files": manifest["files"]}
    lock_body = owner.canonical(lock)
    lock_pin = {"path": str(write_dir / "source-lock.json"),
                "bytes": len(lock_body), "sha256": owner.sha(lock_body)}
    request = {"schema": request_schema,
        "execution": {"repository_root": str(root), "output_root": str(output),
            "source_lock": lock_pin, "runtime_manifest": runtime,
            "source_adoption": {"commit": arguments.commit, "worker": worker},
            "profile": owner.PROFILE}, "task": task}
    # Fresh, private, no-clobber writes. A failed second write preserves the first.
    written_lock = owner.write(write_dir / "source-lock.json", lock)
    need(written_lock == lock_pin, "Exact generated software lock")
    request_pin = owner.write(write_dir / "request.json", request)
    owner.load_request(Path(request_pin["path"]), request_pin["sha256"])
    owner.source_lock(request)
    return {"schema": "findlay-bound-request/v1", "request": request_pin,
            "source_lock": lock_pin, "owner_entrypoint": entry["path"],
            "executed": False, "scientific_qualification": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("commit", "input-ledger", "published-families", "private-policy",
                 "runtime-manifest", "operation-output", "write-dir"):
        parser.add_argument("--" + name, required=True)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--prior-attempt")
    inputs.add_argument("--original-archive")
    args = parser.parse_args()
    print(json.dumps(build(args), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

