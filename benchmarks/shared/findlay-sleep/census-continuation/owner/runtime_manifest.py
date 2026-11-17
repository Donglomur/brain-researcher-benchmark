"""Prospective runtime inventory, verification and third-party import boundary.

No native package is imported here. Preparing and independently verifying a
manifest are distinct complete 192 MiB passes. They are not run by source tests.
The OS loader/system libraries and CPython base/stdlib remain trusted.
"""
from pathlib import Path
import argparse
import email.parser
import hashlib
import importlib.machinery
import json
import os
import resource
import signal
import stat
import sys
import sysconfig
import time

CAP = 192 * 1024 * 1024
MANIFEST_CAP = 2 * 1024 * 1024
FIXED_VERSION = [3, 11, 6]
NAMES = ("pyarrow", "numpy")
TRUST = ["OS loader and system native libraries", "CPython base and standard library"]


def need(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def absolute(value):
    p = Path(value)
    need(p.is_absolute() and ".." not in p.parts and str(p) == str(value), "Canonical absolute path")
    return p


def ordinary(path):
    p = absolute(str(path))
    need(not any(x.is_symlink() for x in (p, *p.parents)), "No symlink in selected file")
    s = p.lstat()
    need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1, "Ordinary single-link file")
    return s


def physical(s):
    return (s.st_dev, s.st_ino, s.st_size, s.st_mode, s.st_nlink, s.st_mtime_ns, s.st_ctime_ns)


class Reader:
    def __init__(self, cap=CAP, deadline=None):
        need(type(cap) is int and 0 < cap <= CAP, "Runtime read ceiling")
        self.cap, self.bytes, self.deadline = cap, 0, deadline

    def check(self):
        if self.deadline is not None:
            need(time.monotonic() < self.deadline, "Original work deadline")

    def pin(self, path, body=False):
        self.check()
        p = absolute(str(path)); before = ordinary(p)
        need(self.bytes + before.st_size <= self.cap, "Runtime pass exceeds reserved 192 MiB")
        fd = os.open(p, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        pieces = [] if body else None
        h = hashlib.sha256(); size = 0
        try:
            need(physical(os.fstat(fd)) == physical(before), "Runtime opened identity")
            while True:
                self.check()
                data = os.read(fd, min(1024 * 1024, self.cap - self.bytes + 1))
                if not data:
                    break
                self.bytes += len(data); size += len(data)
                need(self.bytes <= self.cap, "Runtime read ceiling")
                h.update(data)
                if body:
                    need(size <= MANIFEST_CAP, "Bounded metadata body")
                    pieces.append(data)
            need(physical(os.fstat(fd)) == physical(before), "Runtime file changed during capture")
        finally:
            os.close(fd)
        need(physical(ordinary(p)) == physical(before) and size == before.st_size, "Stable runtime file")
        result = {"bytes": size, "sha256": h.hexdigest(),
                  "identity": {"device": str(before.st_dev), "inode": str(before.st_ino)}}
        return (result, b"".join(pieces)) if body else result


def aliases(path):
    need(len(path.parts) <= 64, "Bounded executable alias")
    return [(str(p), *physical(p.lstat()), os.readlink(p) if p.is_symlink() else None)
            for p in reversed((path, *path.parents))]


def python_pin(reader):
    need(list(sys.version_info[:3]) == FIXED_VERSION, "Selected Python 3.11.6")
    reported = absolute(sys.executable); before = aliases(reported)
    selected = reported.resolve(strict=True)
    pin = reader.pin(selected)
    need(aliases(reported) == before and reported.resolve(strict=True) == selected
         and os.path.samefile(reported, selected), "Stable interpreter alias")
    return {"path": str(selected), **pin, "version": list(sys.version_info[:3])}


def verify_python(value, reader):
    need(type(value) is dict and set(value) == {"path", "bytes", "sha256", "identity", "version"},
         "Exact interpreter descriptor")
    reported = absolute(sys.executable); before = aliases(reported)
    selected = absolute(value["path"])
    need(value["version"] == FIXED_VERSION == list(sys.version_info[:3]), "Exact Python version")
    need(reported.resolve(strict=True) == selected and os.path.samefile(reported, selected),
         "Selected canonical interpreter file")
    actual = reader.pin(selected)
    need(actual == {key: value[key] for key in ("bytes", "sha256", "identity")}, "Interpreter pin")
    need(aliases(reported) == before and reported.resolve(strict=True) == selected
         and sys.executable == str(reported), "Stable reported alias")
    return {"reported_executable": str(reported), "canonical_executable": str(selected), **actual,
            "version": value["version"], "reported_alias_preserved": True,
            "host_admin_TOCTOU_guarantee": False}


def inventory(root):
    root = absolute(str(root))
    need(root.is_dir() and not any(p.is_symlink() for p in (root, *root.parents)), "Ordinary runtime root")
    result = []
    for folder, directories, files in os.walk(root, followlinks=False):
        need(len(result) <= 12000, "Runtime inventory count")
        for name in directories:
            p = Path(folder) / name
            need(not p.is_symlink() and p.is_dir(), "No linked runtime directory")
        for name in files:
            p = Path(folder) / name
            ordinary(p)
            rel = p.relative_to(root).as_posix()
            need(len(rel.encode()) <= 1024, "Runtime member path bound")
            result.append(rel)
    need(0 < len(result) <= 12000, "Complete bounded runtime inventory")
    return sorted(result)


def discover(site):
    site = absolute(str(site)).resolve(strict=True)
    need(site.is_dir(), "Selected site-packages directory")
    bundles = {}
    for name in NAMES:
        root = site / name
        need(root.is_dir() and not root.is_symlink(), "Required package root: " + name)
        matches = sorted(site.glob(name + "-*.dist-info"))
        need(len(matches) == 1 and matches[0].is_dir() and not matches[0].is_symlink(),
             "Exactly one installed distribution: " + name)
        bundles[name] = str(root)
        bundles[name + ".dist-info"] = str(matches[0])
        libs = site / (name + ".libs")
        if libs.exists():
            need(libs.is_dir() and not libs.is_symlink(), "Ordinary bundled libraries")
            bundles[name + ".libs"] = str(libs)
    return {"site_packages": str(site), "bundles": bundles}


def prepare(site, cap=CAP, deadline=None):
    reader = Reader(cap, deadline)
    descriptor = python_pin(reader)
    discovered = discover(site)
    bundles = {}
    versions = {}
    for name, path in sorted(discovered["bundles"].items()):
        files = {}
        for rel in inventory(path):
            pin, body = reader.pin(Path(path) / rel, body=(rel == "METADATA" and name.endswith(".dist-info"))) if rel == "METADATA" and name.endswith(".dist-info") else (reader.pin(Path(path) / rel), None)
            files[rel] = pin
            if body is not None:
                meta = email.parser.BytesParser().parsebytes(body, headersonly=True)
                package = name.split(".")[0]
                need(meta.get("Name", "").lower().replace("-", "_") == package, "Distribution name")
                versions[package] = meta.get("Version")
        bundles[name] = {"root": path, "files": files}
    need(set(versions) == set(NAMES) and versions["pyarrow"] == "24.0.0"
         and all(type(x) is str and 0 < len(x) <= 80 for x in versions.values()),
         "Concrete selected package versions")
    result = {"schema": "findlay-runtime-manifest/v1", "python": descriptor,
              "site_packages": discovered["site_packages"], "packages": versions,
              "bundles": bundles, "runtime_bytes": reader.bytes,
              "trusted_base": TRUST, "full_platform_lock": False}
    need(len(canonical(result)) <= MANIFEST_CAP, "Runtime manifest cap")
    return result


def verify(value, deadline=None):
    need(type(value) is dict and set(value) == {"schema", "python", "site_packages", "packages", "bundles",
         "runtime_bytes", "trusted_base", "full_platform_lock"}, "Exact runtime manifest")
    need(value["schema"] == "findlay-runtime-manifest/v1" and value["trusted_base"] == TRUST
         and value["full_platform_lock"] is False, "Runtime trust boundary")
    reader = Reader(CAP, deadline)
    observation = verify_python(value["python"], reader)
    discovered = discover(value["site_packages"])
    need(discovered["bundles"] == {k: v["root"] for k, v in value["bundles"].items()},
         "Exact package and bundled-native-library inventory")
    versions = {}
    for name, bundle in sorted(value["bundles"].items()):
        need(set(bundle) == {"root", "files"} and inventory(bundle["root"]) == sorted(bundle["files"]),
             "Complete runtime member inventory")
        for rel, expected in sorted(bundle["files"].items()):
            metadata = rel == "METADATA" and name.endswith(".dist-info")
            actual, body = reader.pin(Path(bundle["root"]) / rel, body=True) if metadata else (reader.pin(Path(bundle["root"]) / rel), None)
            need(actual == expected, "Concrete runtime member pin: " + name + "/" + rel)
            if body is not None:
                meta = email.parser.BytesParser().parsebytes(body, headersonly=True)
                package = name.split(".")[0]
                need(meta.get("Name", "").lower().replace("-", "_") == package, "Distribution name")
                versions[package] = meta.get("Version")
    need(versions == value["packages"] and versions["pyarrow"] == "24.0.0"
         and set(versions) == set(NAMES) and reader.bytes == value["runtime_bytes"],
         "Version and runtime accounting parity")
    return {"verified": True, "managed_read_bytes": reader.bytes, "python": observation,
            "package_versions": versions, "full_platform_lock": False,
            "native_import_executed": False}


def install_import_guard(value, allowed_source_files=()):
    """Reject unlisted third-party imports before native package loading/GET.

    System extension modules and stdlib/base are explicitly trusted. Dlopen
    dependencies of a pinned extension are part of the disclosed OS boundary.
    """
    allowed = {str(Path(bundle["root"]) / rel)
               for bundle in value["bundles"].values() for rel in bundle["files"]}
    allowed.update(str(absolute(str(p))) for p in allowed_source_files)
    standard = Path(sysconfig.get_path("stdlib")).resolve()
    site = Path(value["site_packages"])
    def permitted(origin):
        if origin in (None, "built-in", "frozen"):
            return True
        p = Path(origin).resolve()
        return str(p) in allowed or (p.is_relative_to(standard) and
               "site-packages" not in p.parts and "dist-packages" not in p.parts)
    for name, module in tuple(sys.modules.items()):
        origin = getattr(getattr(module, "__spec__", None), "origin", None)
        need(permitted(origin), "Unexpected already-imported package: " + name)
    class Guard:
        @staticmethod
        def find_spec(fullname, path=None, target=None):
            spec = importlib.machinery.PathFinder.find_spec(fullname, path, target)
            if spec is not None:
                need(permitted(spec.origin), "Unpinned third-party import: " + fullname)
                if spec.origin is None:
                    need(all(str(Path(p).resolve()).startswith(str(site) + os.sep) is False
                             for p in (spec.submodule_search_locations or ())), "Unpinned namespace package")
            return spec
    guard = Guard()
    sys.meta_path.insert(0, guard)
    return guard


def verify_imported_runtime(value):
    """Post-import, pre-GET version/origin joins; never imports a native module."""
    files = {str(Path(bundle["root"]) / relative)
             for bundle in value["bundles"].values() for relative in bundle["files"]}
    rows = {}
    for name in ("pyarrow", "pyarrow.parquet", "numpy"):
        item = sys.modules.get(name)
        if item is None:
            need(name == "numpy", "Required pre-GET import: " + name)
            rows[name] = {"imported": False}
            continue
        origin = str(Path(getattr(item, "__file__", "")).resolve())
        need(origin in files, "Imported pinned package origin: " + name)
        row = {"imported": True, "origin": origin}
        if name in NAMES:
            need(getattr(item, "__version__", None) == value["packages"][name], "Imported package version")
            row["version"] = value["packages"][name]
        rows[name] = row
    standard = Path(sysconfig.get_path("stdlib")).resolve()
    observed = 0
    for name, item in tuple(sys.modules.items()):
        origin = getattr(getattr(item, "__spec__", None), "origin", None)
        if origin in (None, "built-in", "frozen"):
            continue
        p = Path(origin).resolve()
        if "site-packages" in p.parts or "dist-packages" in p.parts:
            need(str(p) in files, "Unexpected loaded third-party module: " + name)
            observed += 1
    return {"verified": True, "modules": rows, "loaded_third_party_modules": observed,
            "native_import_preceded_GET": True, "full_platform_lock": False}


def preparation_receipt_body(receipt, manifest_bytes):
    body = canonical(receipt)
    need(type(manifest_bytes) is int and 0 <= manifest_bytes <= MANIFEST_CAP,
         "Preparation manifest extent")
    need(len(body) <= 65536 and manifest_bytes + len(body) <= 3*1024*1024,
         "Separate complete runtime-preparation retention ceiling")
    return body


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--site-packages", required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--receipt", type=Path, required=True)
    a = p.parse_args(argv)
    started = time.monotonic(); deadline = started + 55
    for path in (a.output, a.receipt):
        absolute(str(path)); need(not path.exists() and path.parent.is_dir()
            and not any(x.is_symlink() for x in (path.parent, *path.parent.parents)), "Fresh private preparation outputs")
    need(a.output != a.receipt, "Separate manifest and complete preparation receipt")
    resource.setrlimit(resource.RLIMIT_CPU, (30, 35))
    def alarm(*unused):
        raise TimeoutError("Original runtime-preparation boundary")
    signals = (signal.SIGALRM, signal.SIGINT, signal.SIGTERM, signal.SIGXCPU)
    handlers = {sig: signal.signal(sig, alarm) for sig in signals}
    signal.setitimer(signal.ITIMER_REAL, max(.001, deadline-time.monotonic()))
    receipt = {"schema": "findlay-runtime-preparation/v1", "status": "REFUSED",
               "wall_seconds": 60, "work_seconds": 55, "cpu_seconds": [30, 35], "runtime_read_cap": CAP,
               "native_imports": False, "children": 0, "full_platform_lock": False}
    try:
        result = prepare(a.site_packages, deadline=deadline)
        body = canonical(result)
        with a.output.open("xb") as f:
            f.write(body); f.flush(); os.fsync(f.fileno())
        os.chmod(a.output, 0o400)
        need(time.monotonic() < deadline, "Preparation original deadline")
        receipt.update(status="RUNTIME_MANIFEST_PREPARED_NOT_INDEPENDENTLY_VERIFIED",
                       manifest={"path": str(a.output), "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()},
                       managed_runtime_read_bytes=result["runtime_bytes"])
    except BaseException as exc:
        receipt.update(error=type(exc).__name__ + ": " + str(exc),
                       managed_runtime_read_bytes=None, failed_pass_cost_complete=False,
                       partial_manifest_retained=a.output.exists())
    finally:
        # Failure recording uses only the original five-second metadata tail.
        signal.setitimer(signal.ITIMER_REAL, max(.001, started+60-time.monotonic()))
        receipt["elapsed_work_seconds"] = time.monotonic() - started
        receipt["failure_receipt_tail_seconds"] = 5
        body = preparation_receipt_body(receipt, a.output.stat().st_size if a.output.exists() else 0)
        with a.receipt.open("xb") as f:
            f.write(body); f.flush(); os.fsync(f.fileno())
        os.chmod(a.receipt, 0o400)
        print(json.dumps({"status": receipt["status"], "receipt": str(a.receipt),
                          "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}), flush=True)
        signal.setitimer(signal.ITIMER_REAL, 0)
        for sig, handler in handlers.items():
            signal.signal(sig, handler)
    return 0 if receipt["status"] != "REFUSED" else 2


if __name__ == "__main__":
    raise SystemExit(main())

