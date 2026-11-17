"""Pinned, closed source verification and generated checks; no native CLI.

This file and its interpreter are the trusted bootstrap. Obtain the manifest pin
from the independently reviewed release, never from an untrusted adjacent file.
An immutable qualified namespace remains necessary for later contract/native I/O.
"""
import argparse
from contextlib import contextmanager
import hashlib
import importlib
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import types
import unittest

MANIFEST = "SOURCE_MANIFEST.json"
MAX_MEMBER = 1048576
MAX_TOTAL = 4194304
MAX_MEMBERS = 128
SCHEMA = "paper_find050_portable_source_v1"


class PackageError(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise PackageError(message)


def digest(body):
    return hashlib.sha256(body).hexdigest()


def decode(body):
    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    def bad(value):
        raise PackageError("nonfinite JSON token")
    return json.loads(body, object_pairs_hook=pairs, parse_constant=bad)


def relative(value):
    require(type(value) is str and 0 < len(value) <= 512, "bounded member name")
    require(not any(c in value for c in "\\\x00\r\n"), "ordinary member spelling")
    p = PurePosixPath(value)
    require(not p.is_absolute() and all(x not in ("", ".", "..") for x in value.split("/")),
            "canonical confined relative member")
    return value


def absolute(value):
    value = os.fspath(value)
    require(type(value) is str and 0 < len(value) <= 4096, "bounded absolute root")
    require(value.startswith("/") and not value.startswith("//"), "exact POSIX root anchor")
    require(not any(c in value for c in "\\\x00\r\n"), "ordinary root spelling")
    require(all(x not in ("", ".", "..") for x in value.split("/")[1:]), "canonical absolute root")
    p = Path(value)
    for ancestor in reversed((p, *p.parents)):
        info = ancestor.lstat()
        require(stat.S_ISDIR(info.st_mode), "ordinary root ancestors, no symlinks")
    return p


def pin_fields(row):
    require(type(row) is dict and set(row) == {"path", "bytes", "sha256"}, "exact member fields")
    relative(row["path"])
    require(type(row["bytes"]) is int and 0 <= row["bytes"] <= MAX_MEMBER, "bounded member extent")
    sha = row["sha256"]
    require(type(sha) is str and len(sha) == 64 and all(c in "0123456789abcdef" for c in sha), "SHA-256 pin")


def stable_read(path, cap, expected=None):
    """No-follow single-link bounded file read, including before/after identity."""
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 <= before.st_size <= cap,
            "bounded ordinary single-link source")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        initial = os.fstat(fd)
        fields = ("st_dev", "st_ino", "st_mode", "st_size", "st_nlink", "st_mtime_ns", "st_ctime_ns")
        require(all(getattr(before, k) == getattr(initial, k) for k in fields), "same opened source")
        chunks, count = [], 0
        while count < initial.st_size:
            part = os.read(fd, min(65536, initial.st_size - count))
            require(bool(part), "short source read")
            count += len(part)
            chunks.append(part)
        final, leaf = os.fstat(fd), path.lstat()
        require(all(getattr(initial, k) == getattr(final, k) == getattr(leaf, k) for k in fields),
                "stable source identity")
        body = b"".join(chunks)
        if expected is not None:
            require(len(body) == expected["bytes"] and digest(body) == expected["sha256"], "source pin mismatch")
        body.decode("utf-8")
        return body
    finally:
        os.close(fd)


def closed_tree(root, names):
    """Inspect only the declared ordinary source tree; unknown children refuse."""
    expected_dirs = set()
    for name in names:
        expected_dirs.update(str(p) for p in PurePosixPath(name).parents if str(p) != ".")
    require(not (set(names) & expected_dirs), "file/directory role collision")
    seen, directories, pending = set(), set(), [(root, "")]
    entries = 0
    while pending:
        path, prefix = pending.pop()
        with os.scandir(path) as iterator:
            for entry in iterator:
                entries += 1
                require(entries <= MAX_MEMBERS * 8, "bounded tree entries")
                name = prefix + entry.name
                info = entry.stat(follow_symlinks=False)
                if stat.S_ISDIR(info.st_mode):
                    require(name in expected_dirs, "undeclared source directory: " + name)
                    directories.add(name)
                    pending.append((Path(entry.path), name + "/"))
                else:
                    require(name in names, "undeclared source member: " + name)
                    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "ordinary single-link member required")
                    seen.add(name)
    require(seen == set(names) and directories == expected_dirs, "complete closed source tree")


def verify(root, manifest_bytes, manifest_sha256):
    root = absolute(root)
    selected = {"path": MANIFEST, "bytes": manifest_bytes, "sha256": manifest_sha256}
    pin_fields(selected)
    body = stable_read(root / MANIFEST, MAX_MEMBER, selected)
    manifest = decode(body)
    require(type(manifest) is dict and set(manifest) == {"schema", "task_id", "members"}, "exact manifest fields")
    require(manifest["schema"] == SCHEMA and manifest["task_id"] == "PAPER-FIND-050", "selected package identity")
    rows = manifest["members"]
    require(type(rows) is list and 1 <= len(rows) <= MAX_MEMBERS, "bounded manifest roster")
    for row in rows:
        pin_fields(row)
    names = [row["path"] for row in rows]
    require(names == sorted(set(names)) and MANIFEST not in names, "sorted unique nonrecursive manifest")
    require(sum(row["bytes"] for row in rows) + len(body) <= MAX_TOTAL, "bounded package bytes")
    closed_tree(root, {*names, MANIFEST})
    captured = {row["path"]: stable_read(root / row["path"], row["bytes"], row) for row in rows}
    require({"package_tools.py", "README.md", "source/critical/__init__.py",
             "source/contracts/PROGRAMME.json", "source/contracts/GATES.json"} <= captured.keys(), "complete package roles")
    return VerifiedPackage(root, captured, selected)


class CapturedLoader(importlib.abc.Loader):
    def __init__(self, owner, name, path):
        self.owner, self.name, self.path = owner, name, path

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        module.__file__ = str(self.owner.root / self.path)
        module.__cached__ = None
        self.owner.loaded[self.name] = module
        exec(compile(self.owner.captured[self.path], module.__file__, "exec"), vars(module))


class VerifiedPackage(importlib.abc.MetaPathFinder):
    def __init__(self, root, captured, selected):
        self.root, self.captured, self.selected = root, captured, selected
        self.roles = {"critical": "source/critical/__init__.py",
                      "test_native_transport": "source/tests/test_native_transport.py",
                      "test_peer_transport": "tests/test_peer_transport.py",
                      "test_package": "tests/test_package.py"}
        for name in captured:
            if name.startswith("source/critical/") and name.endswith(".py") and not name.endswith("/__init__.py"):
                self.roles["critical." + PurePosixPath(name).stem] = name
        self.loaded = {}
        self.active = False

    def find_spec(self, fullname, path=None, target=None):
        if fullname == "critical" or fullname.startswith("critical.") or fullname in self.roles:
            require(fullname in self.roles, "undeclared critical import")
            return importlib.util.spec_from_loader(fullname, CapturedLoader(self, fullname, self.roles[fullname]),
                                                   is_package=fullname == "critical")
        return None

    @contextmanager
    def installed(self):
        require(not self.active, "single active captured-source context")
        require(not any(k == "critical" or k.startswith("critical.") or k in self.roles for k in sys.modules),
                "refuse preloaded critical/test modules")
        self.active = True
        old_bytecode = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
        sys.meta_path.insert(0, self)
        try:
            yield self
        finally:
            if self in sys.meta_path:
                sys.meta_path.remove(self)
            for name, module in self.loaded.items():
                if sys.modules.get(name) is module:
                    del sys.modules[name]
            self.loaded.clear()
            sys.dont_write_bytecode = old_bytecode
            self.active = False

    def module(self, name):
        require(self.active and name in self.roles, "active selected module required")
        return importlib.import_module(name)

    def describe(self):
        p = decode(self.captured["source/contracts/PROGRAMME.json"])
        c = decode(self.captured["source/contracts/COHORT.json"])
        s = decode(self.captured["source/contracts/SPECTRAL_CONTRACT.json"])
        g = decode(self.captured["source/contracts/GATES.json"])
        return {"task_id": p["task_id"], "operations": [x["id"] for x in p["operations"]],
                "profiles": p["profiles"], "dense_spectra": len(s["dense_outputs"]),
                "dense_output_shapes": sorted({tuple(x["shape"]) for x in s["dense_outputs"].values()}),
                "main_sessions": c["session_count"], "scientific_runtime_gates": g["gates"],
                "source_verification_only": True, "scientific_readiness": "unknown"}

    def author_members(self):
        exposure = decode(self.captured["source/contracts/AUTHOR_EXPOSURE.json"])
        return [{"path": row["path"][7:], "bytes": row["bytes"], "sha256": row["sha256"]}
                for row in exposure["members"] if row["path"].startswith("author/")]

    def verify_author(self, author_root):
        # Explicit operator command only. No download, import, assembly, data I/O,
        # or authority issuance. Both extracted notebook drivers remain required.
        root = absolute(author_root)
        require(root != self.root and root not in self.root.parents and self.root not in root.parents,
                "external author root disjoint from public package")
        rows = self.author_members()
        require(len(rows) == 18, "complete original exposure roster")
        for row in rows:
            pin_fields(row)
        require(sum(x["bytes"] for x in rows) <= MAX_TOTAL, "bounded author source")
        closed_tree(root, {x["path"] for x in rows})
        for row in rows:
            stable_read(root / row["path"], row["bytes"], row)
        return {"verified_external_members": len(rows), "verified_external_bytes": sum(r["bytes"] for r in rows),
                "native_authority_granted": False, "scientific_qualification_granted": False}


def check(package):
    # All leaves requiring native authority remain inert in the inherited suite.
    # The immutable namespace and bootstrap are still trusted prerequisites.
    with package.installed():
        author = package.module("test_native_transport")
        peer = package.module("test_peer_transport")
        controls = package.module("test_package")
        controls.BOOTSTRAP = sys.modules[__name__]
        controls.PACKAGE = package
        suites = [unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in
                  (author.TransportTests, peer.PeerControls, controls.PackageControls)]
        expected = sum(s.countTestCases() for s in suites)
        result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(suites))
        require(result.testsRun == expected and expected >= 25 and result.wasSuccessful()
                and not result.skipped and not result.expectedFailures and not result.unexpectedSuccesses,
                "complete generated control disposition")
        return {"generated_methods": result.testsRun, "failures": 0, "native_runs": 0, "scientific_results": 0}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("verify", "describe", "dependencies", "verify-author", "check"))
    parser.add_argument("--root", required=True, help="canonical absolute package root")
    parser.add_argument("--manifest-bytes", required=True, type=int)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--author-root", help="explicit existing exact external source; only with verify-author")
    args = parser.parse_args(argv)
    require((args.command == "verify-author") == (args.author_root is not None), "author-root only for explicit verify-author")
    package = verify(args.root, args.manifest_bytes, args.manifest_sha256)
    if args.command == "verify":
        result = {"source_members": len(package.captured), "source_bytes": sum(map(len, package.captured.values())),
                  "scientific_qualification_granted": False}
    elif args.command == "describe":
        result = package.describe()
    elif args.command == "dependencies":
        result = {"external_author_members": package.author_members(), "native_prerequisites": "PREREQUISITES.md",
                  "downloaded": False, "bodies_included": False}
    elif args.command == "verify-author":
        result = package.verify_author(args.author_root)
    else:
        result = check(package)
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PackageError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print("package refused: " + str(exc), file=sys.stderr)
        raise SystemExit(2)
