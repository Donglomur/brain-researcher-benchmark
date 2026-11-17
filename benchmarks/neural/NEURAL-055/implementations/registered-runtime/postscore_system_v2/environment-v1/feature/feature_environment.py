"""Prospective fixed-feature provisioning; not a benchmark or qualification.

lock/verify-wheels use stdlib and never load a checkpoint, image or model.
inspect imports selected native packages only in a separately selected future
provisioning invocation. It never instantiates AlexNet or executes a forward.
No command in this file was run during source authoring.
"""
import argparse
from contextlib import contextmanager
import email.parser
import hashlib
import importlib
import importlib.metadata
import inspect
import json
import os
from pathlib import Path
import platform
import re
import stat
import sys
import zipfile

PYTHON = "3.9.18"
VERSIONS = {"torch": "1.10.1+cpu", "torchvision": "0.11.2+cpu",
            "numpy": "1.21.6", "pillow": "8.4.0", "typing-extensions": "4.7.1",
            "cryptography": "41.0.7", "cffi": "1.16.0", "pycparser": "2.21"}
MAX_FILE = 1024 * 1024 * 1024
MAX_TOTAL = 2 * 1024 * 1024 * 1024
MAX_FILES = 30000
MAX_JSON = 8 * 1024 * 1024


def need(ok, message):
    if not ok:
        raise ValueError(message)


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode("ascii")


def literal(value):
    p = Path(value)
    need(p.is_absolute() and str(p) == value and ".." not in p.parts,
         "literal canonical absolute path required")
    need(not any(x.is_symlink() for x in (p, *p.parents)), "no symbolic ancestry")
    return p


@contextmanager
def owned(resource):
    """Close independently while retaining the original and raw secondary errors."""
    first = None
    try:
        yield resource
    except BaseException as error:
        first = error
    finally:
        try:
            resource.close()
        except BaseException as error:
            if first is None:
                first = error
            else:
                first.__dict__.setdefault("cleanup_failures", []).append(error)
    if first is not None:
        raise first


def identity(value):
    return tuple(getattr(value, k) for k in
                 ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns", "st_nlink"))


def hash_open(stream, before, remaining):
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1,
         "ordinary single-link selected file")
    need(before.st_size <= min(MAX_FILE, remaining), "selected file byte ceiling")
    need(identity(os.fstat(stream.fileno())) == identity(before), "same selected opened file")
    digest = hashlib.sha256(); count = 0
    while True:
        block = stream.read(min(65536, before.st_size + 1 - count))
        count += len(block); digest.update(block)
        need(count <= before.st_size, "selected file grew")
        if not block:
            break
    need(count == before.st_size and identity(os.fstat(stream.fileno())) == identity(before),
         "selected opened file changed while hashing")
    return {"bytes": count, "sha256": digest.hexdigest()}


def pin_file(path, remaining):
    path = literal(str(path)); before = path.stat()
    with owned(path.open("rb")) as stream:
        descriptor = hash_open(stream, before, remaining)
        need(identity(path.stat()) == identity(before), "selected pathname changed while hashing")
    return descriptor


def wheel_record(path, remaining, expected):
    path = literal(str(path)); before = path.stat()
    with owned(path.open("rb")) as stream:
        descriptor = hash_open(stream, before, remaining)
        need(re.fullmatch(r"[0-9a-f]{64}", expected["sha256"]) is not None
             and descriptor["sha256"] == expected["sha256"]
             and (expected["bytes"] is None or descriptor["bytes"] == expected["bytes"]),
             "selected publisher wheel bytes before ZIP metadata")
        stream.seek(0)
        # ZIP metadata comes from the same held, authenticated ordinary handle.
        with owned(zipfile.ZipFile(stream)) as archive:
            members = archive.infolist()
            need(len(members) <= MAX_FILES, "bounded wheel member metadata")
            choices = [m for m in members if m.filename.endswith(".dist-info/METADATA")]
            need(len(choices) == 1 and choices[0].file_size <= 262144,
                 "one bounded distribution metadata record")
            with owned(archive.open(choices[0])) as member:
                metadata = member.read(262145)
            need(len(metadata) <= 262144, "bounded uncompressed wheel metadata")
        need(identity(os.fstat(stream.fileno())) == identity(before) and
             identity(path.stat()) == identity(before), "same wheel through metadata extraction")
    return descriptor, metadata


def read_json(path):
    p = literal(path); need(p.stat().st_size <= MAX_JSON, "bounded selected JSON")
    def pairs(rows):
        out = {}
        for key, value in rows:
            need(key not in out, "duplicate JSON key"); out[key] = value
        return out
    with owned(p.open("rb")) as stream:
        body = stream.read(MAX_JSON + 1)
    need(len(body) <= MAX_JSON, "JSON byte ceiling")
    return json.loads(body, object_pairs_hook=pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))


def exclusive(path, body):
    need(len(body) <= MAX_JSON, "output byte ceiling")
    p = literal(path)
    with owned(p.open("xb")) as stream:
        count = stream.write(body); need(count == len(body), "complete metadata write")
        stream.flush(); os.fsync(stream.fileno())


def platform_check():
    need(platform.system() == "Linux" and platform.machine() == "x86_64"
         and platform.python_version() == PYTHON and sys.implementation.name == "cpython",
         "selected Linux x86_64 CPython 3.9.18")


def inventory_wheels(directory):
    root = literal(directory); need(root.is_dir(), "selected wheel directory")
    entries = []
    for entry in root.iterdir():
        need(len(entries) < len(VERSIONS), "at most eight selected directory entries")
        entries.append(entry)
    entries.sort()
    need(len(entries) == len(VERSIONS), "exact eight selected wheels, no extra members")
    selected = read_json(str(Path(__file__).absolute().with_name("WHEEL_ARTIFACTS.json")))
    need(selected["schema"] == "n055_fixed_feature_selected_wheel_artifacts_v1"
         and selected["python"] == PYTHON and selected["platform"] == "linux-x86_64",
         "exact selected artifact profile")
    chosen = {row["name"]: row for row in selected["files"]}
    need(len(chosen) == len(selected["files"]) == len(VERSIONS)
         and set(chosen) == set(VERSIONS), "complete preselected wheel identities")
    by_filename = {row["filename"]: row for row in chosen.values()}
    need(len(by_filename) == len(VERSIONS), "unique preselected wheel filenames")
    result = {}; total = 0
    for path in entries:
        need(path.suffix == ".whl" and path.name in by_filename, "exact selected wheel filename")
        descriptor, metadata = wheel_record(path, MAX_TOTAL - total, by_filename[path.name])
        total += descriptor["bytes"]
        msg = email.parser.Parser().parsestr(metadata.decode("utf-8"))
        need(type(msg["Name"]) is str and type(msg["Version"]) is str,
             "explicit package identity")
        name = re.sub(r"[-_.]+", "-", msg["Name"].lower())
        need(name in VERSIONS and name not in result and msg["Version"] == VERSIONS[name],
             "exact selected package and version")
        expected = chosen[name]
        need(expected["version"] == VERSIONS[name] and expected["filename"] == path.name
             and re.fullmatch(r"[0-9a-f]{64}", expected["sha256"]) is not None
             and descriptor["sha256"] == expected["sha256"]
             and (expected["bytes"] is None or descriptor["bytes"] == expected["bytes"]),
             "actual complete wheel matches preselected primary release identity")
        result[name] = {"filename": path.name, "version": VERSIONS[name], **descriptor,
                        "requires_python": msg.get("Requires-Python"),
                        "requires_dist": msg.get_all("Requires-Dist", [])}
    need(set(result) == set(VERSIONS), "complete selected wheel set")
    return {"schema": "n055_fixed_feature_wheel_lock_v1", "python": PYTHON,
            "platform": "linux-x86_64", "packages": result,
            "identity_basis": "actual complete local wheel bytes; not a publisher-signature claim",
            "runtime_or_scientific_qualification": False}


def requirements(lock):
    return "".join("%s==%s --hash=sha256:%s\n" %
                   (name, VERSIONS[name], lock["packages"][name]["sha256"])
                   for name in sorted(VERSIONS)).encode("ascii")


def observe_environment(memory_bytes, image_bytes, image_pixels):
    platform_check()
    need(1024**3 <= memory_bytes <= 16*1024**3, "fixed producer address-space range")
    need(1 <= image_bytes <= 16*1024**2 and 1 <= image_pixels <= 20000000,
         "fixed producer image ceilings")
    total = 0; count = 0; distributions = {}
    for name in sorted(VERSIONS):
        dist = importlib.metadata.distribution(name)
        need(dist.version == VERSIONS[name], "actual exact installed distribution")
        members = list(dist.files or ())
        need(members and count + len(members) <= MAX_FILES, "complete bounded installed file list")
        rows = []
        for relative in sorted(members, key=str):
            path = Path(os.path.normpath(str(Path(dist.locate_file(relative)).absolute())))
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            item = pin_file(path, MAX_TOTAL - total); total += item["bytes"]; count += 1
            rows.append({"path": str(path), **item})
        distributions[name] = {"version": dist.version, "files": rows}
    # Native imports are prospective provisioning work, never a source check.
    torch = importlib.import_module("torch")
    tv = importlib.import_module("torchvision")
    np = importlib.import_module("numpy")
    pil = importlib.import_module("PIL")
    ed = importlib.import_module("cryptography.hazmat.primitives.asymmetric.ed25519")
    need(torch.__version__ == VERSIONS["torch"] and tv.__version__ == VERSIONS["torchvision"]
         and np.__version__ == VERSIONS["numpy"] and pil.__version__ == VERSIONS["pillow"],
         "actual imported module versions")
    need(torch.version.cuda is None and torch.get_default_dtype() == torch.float32,
         "CPU build with fixed float32 default")
    need(callable(torch.use_deterministic_algorithms) and
         {"pretrained", "progress"} <= set(inspect.signature(tv.models.alexnet).parameters)
         and callable(ed.Ed25519PublicKey.from_public_bytes), "actual required feature/authority APIs")
    executable = literal(str(Path(sys.executable).absolute()))
    python_pin = pin_file(executable, MAX_TOTAL - total); total += python_pin["bytes"]
    environment = {"python": PYTHON, "torch": "1.10.1", "torchvision": "0.11.2",
                   "numpy": VERSIONS["numpy"], "Pillow": VERSIONS["pillow"], "device": "cpu",
                   "memory_bytes": memory_bytes, "network_isolated": True,
                   "maximum_image_bytes": image_bytes, "maximum_image_pixels": image_pixels}
    return {"schema": "n055_fixed_feature_environment_observation_v1", "environment": environment,
            "environment_role": "prepare-features only; never ingestion or campaign",
            "network_isolated_is_required_plan_declaration_not_this_observers_attestation": True,
            "python_executable": {"path": str(executable), **python_pin},
            "distributions": distributions, "alexnet_signature": str(inspect.signature(tv.models.alexnet)),
            "fixed_resize_signature": str(inspect.signature(tv.transforms.Resize)),
            "explicit_file_body_read_bytes": total,
            "read_scope": "explicit package/executable hashes; imports and OS internal I/O excluded",
            "model_instantiated": False, "checkpoint_or_images_opened": False,
            "feature_forward_performed": False, "native_parity_established": False,
            "runtime_qualification_granted": False, "scientific_qualification": False}


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("lock"); p.add_argument("wheelhouse"); p.add_argument("lock"); p.add_argument("requirements")
    p = sub.add_parser("verify-wheels"); p.add_argument("wheelhouse"); p.add_argument("lock"); p.add_argument("requirements")
    p = sub.add_parser("inspect"); p.add_argument("output")
    p.add_argument("--memory-bytes", type=int, required=True)
    p.add_argument("--maximum-image-bytes", type=int, required=True)
    p.add_argument("--maximum-image-pixels", type=int, required=True)
    args = parser.parse_args()
    if args.command in ("lock", "verify-wheels"):
        lock = inventory_wheels(args.wheelhouse); body = requirements(lock)
        if args.command == "lock":
            exclusive(args.lock, encode(lock)); exclusive(args.requirements, body)
        else:
            platform_check(); need(lock == read_json(args.lock), "exact content-locked wheel set")
            p = literal(args.requirements); need(p.stat().st_size <= 4096, "bounded lock text")
            need(p.read_bytes() == body, "exact hash requirements")
    else:
        result = observe_environment(args.memory_bytes, args.maximum_image_bytes, args.maximum_image_pixels)
        exclusive(args.output, encode(result))
    print(json.dumps({"command": args.command, "benchmark_started": False,
                      "feature_forward_performed": False, "qualification_granted": False}, sort_keys=True))


if __name__ == "__main__":
    main()
