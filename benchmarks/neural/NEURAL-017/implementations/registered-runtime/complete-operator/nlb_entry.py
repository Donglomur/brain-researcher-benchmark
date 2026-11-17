"""NEURAL-017 standalone source bootstrap; no scientific authority is granted.

Required: python -I -B -X pycache_prefix=ABSOLUTE_FRESH_OWNED_PATH
          nlb_entry.py prepare|campaign ORIGINAL_ARGUMENTS...
The selected trusted entry is outside its acyclic payload manifest. Capture and
compile that fixed payload before any local import. Native children have their
separate unchanged deployment/source admission, not this host bootstrap.
"""
import sys
import os

MANIFEST_BYTES = 12019
MANIFEST_SHA256 = "082738cc4454754de31c5518de82285921ccb2c948b532c8774b1f9b3532e643"


def require_startup():
    if not (sys.flags.isolated == 1 and sys.flags.ignore_environment == 1
            and sys.flags.no_user_site == 1 and sys.flags.dont_write_bytecode == 1
            and sys.dont_write_bytecode is True):
        raise ValueError("supported entry requires actual Python -I -B")
    if any(n == "nlb" or n.startswith("nlb.") for n in sys.modules):
        raise ValueError("NLB namespaces must not be preloaded")
    prefix = sys.pycache_prefix
    if (type(prefix) is not str or not prefix or not os.path.isabs(prefix)
            or os.path.normpath(prefix) != prefix or ".." in prefix.split(os.sep)
            or sys._xoptions.get("pycache_prefix") != prefix):
        raise ValueError("explicit absolute normalized -X pycache_prefix required")
    parent = os.path.dirname(prefix)
    current = parent
    while True:
        if os.path.islink(current):
            raise ValueError("cache parent ancestry must be nonsymlink")
        nxt = os.path.dirname(current)
        if nxt == current:
            break
        current = nxt
    st = os.stat(parent, follow_symlinks=False)
    if (not os.path.isdir(parent) or st.st_uid != os.geteuid()
            or st.st_mode & 0o022):
        raise ValueError("cache parent must be owned and not group/world writable")
    # Exclusive creation is the actual freshness operation. A precheck alone
    # would not establish absence. Existing paths, including symlinks, refuse.
    os.mkdir(prefix, 0o700)
    created = os.stat(prefix, follow_symlinks=False)
    if created.st_uid != os.geteuid() or created.st_mode & 0o777 != 0o700:
        raise ValueError("owned private cache prefix required")
    return prefix, (created.st_dev, created.st_ino)


def capture_source(root):
    import hashlib
    import json
    import stat
    from pathlib import PurePosixPath

    charged = 0

    def read(path, extent, sha):
        nonlocal charged
        if type(extent) is not int or not 0 < extent <= 2**20:
            raise ValueError("bounded positive ordinary source extent")
        flags = os.O_RDONLY | os.O_NOFOLLOW
        fd = os.open(path, flags)
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != extent:
                raise ValueError("exact regular single-link source")
            chunks = []; remaining = extent
            while remaining:
                chunk = os.read(fd, min(65536, remaining))
                charged += len(chunk)
                if not chunk:
                    raise ValueError("short source read")
                chunks.append(chunk); remaining -= len(chunk)
            after = os.fstat(fd)
            if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                raise ValueError("source changed during capture")
            body = b"".join(chunks)
            if hashlib.sha256(body).hexdigest() != sha:
                raise ValueError("selected source SHA-256 mismatch")
            return body
        finally:
            os.close(fd)

    def pairs(rows):
        out = {}
        for k, v in rows:
            if k in out:
                raise ValueError("duplicate manifest key")
            out[k] = v
        return out

    raw = read(os.path.join(root, "SOURCE_MANIFEST.json"), MANIFEST_BYTES, MANIFEST_SHA256)
    manifest = json.loads(raw, object_pairs_hook=pairs)
    if manifest["schema"] != "NLB017_complete_operator_source_v1" or len(manifest["files"]) != 73:
        raise ValueError("exact complete operator payload")
    captured = {}; seen = set(); aggregate = len(raw)
    for row in manifest["files"]:
        if type(row) is not dict or set(row) != {"path", "bytes", "sha256"}:
            raise ValueError("closed source row")
        path = row["path"]; pp = PurePosixPath(path)
        if (type(path) is not str or pp.is_absolute() or str(pp) != path
                or any(p in ("", ".", "..") for p in pp.parts) or path in seen):
            raise ValueError("canonical unique source path")
        seen.add(path); aggregate += row["bytes"]
        if aggregate > 2**20:
            raise ValueError("complete selected source capture cap")
        current = root
        for part in pp.parts[:-1]:
            current = os.path.join(current, part)
            if os.path.islink(current) or not os.path.isdir(current):
                raise ValueError("ordinary source directory ancestry")
        body = read(os.path.join(root, *pp.parts), row["bytes"], row["sha256"])
        if path.startswith("nlb/") and path.endswith(".py"):
            parts = path[:-3].split("/")
            package = parts[-1] == "__init__"
            name = ".".join(parts[:-1] if package else parts)
            captured[name] = (body, os.path.join(root, *pp.parts), package)
    if "nlb" not in captured:
        raise ValueError("captured package root required")
    return captured, charged


def install_captured(captured):
    import importlib.abc
    import importlib.util

    class CapturedSourceLoader(importlib.abc.MetaPathFinder, importlib.abc.Loader):
        def find_spec(self, fullname, path=None, target=None):
            if fullname != "nlb" and not fullname.startswith("nlb."):
                return None
            if fullname not in captured:
                raise ModuleNotFoundError("outside captured NLB source: " + fullname)
            body, filename, package = captured[fullname]
            return importlib.util.spec_from_loader(fullname, self, origin=filename, is_package=package)

        def create_module(self, spec):
            return None

        def exec_module(self, module):
            body, filename, package = captured[module.__name__]
            module.__file__ = filename
            module.__cached__ = None
            if package:
                module.__path__ = []
            exec(compile(body, filename, "exec", dont_inherit=True), module.__dict__)

    loader = CapturedSourceLoader()
    sys.meta_path.insert(0, loader)
    return loader


def main():
    prefix, identity = require_startup()
    entry = os.path.abspath(__file__)
    current = entry
    while True:
        if os.path.islink(current):
            raise ValueError("trusted entry/source ancestry must be nonsymlink")
        nxt = os.path.dirname(current)
        if nxt == current:
            break
        current = nxt
    if not os.path.isfile(entry):
        raise ValueError("ordinary selected standalone entry required")
    root = os.path.dirname(entry)
    captured, source_bytes = capture_source(root)
    loader = install_captured(captured)
    sys._nlb017_bootstrap = {"schema": "NLB017_captured_host_bootstrap_v1",
                            "entry": entry, "manifest_sha256": MANIFEST_SHA256,
                            "cache_prefix": prefix, "cache_identity": identity,
                            "captured_source_bytes": source_bytes}
    if len(sys.argv) < 2 or sys.argv[1] not in ("prepare", "campaign"):
        raise ValueError("select prepare or campaign with original arguments")
    route = sys.argv[1]; args = sys.argv[2:]
    if route == "prepare":
        from nlb.operator_driver import main as selected_main
    else:
        from nlb.cli import main as selected_main
    # The entry dispatches the unchanged actual lifecycle; it does not create
    # review evidence, renew any clock, select resources or authorize effects.
    return selected_main(args)


if __name__ != "__main__":
    raise RuntimeError("invoke this trusted entry as a standalone file")
raise SystemExit(main())

