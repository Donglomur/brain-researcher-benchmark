"""Authenticated generated controls. Pass the reviewed manifest SHA256 explicitly."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import types


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest-sha256", required=True)
    ap.add_argument("--admission-only", action="store_true",
                    help="Only the twelve portable source/binding controls; no inherited lifecycle replay")
    args = ap.parse_args()
    root = Path(__file__).absolute().parent
    path = root / "source_binding.py"
    if any(x.is_symlink() for x in (path, *path.parents)):
        raise ValueError("bootstrap alias")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != 4147:
            raise ValueError("bootstrap extent")
        body = os.read(fd, 4148)
        fields = ("st_dev", "st_ino", "st_mode", "st_size", "st_nlink", "st_mtime_ns", "st_ctime_ns")
        if any(getattr(before, k) != getattr(os.fstat(fd), k) or getattr(before, k) != getattr(path.lstat(), k) for k in fields):
            raise ValueError("bootstrap changed")
        if len(body) != 4147 or hashlib.sha256(body).hexdigest() != "1079a68cb275a35543f02dff2ad973ef2ae2e89b85c72fab9263d00eee89c3ce":
            raise ValueError("bootstrap identity")
    finally:
        os.close(fd)
    helper = types.ModuleType("hybrid_checks_binding"); helper.__file__ = str(path)
    exec(compile(body, str(path), "exec"), helper.__dict__)
    mp = root / "SOURCE_MANIFEST.json"
    raw = helper.exact(mp, {"bytes": mp.lstat().st_size, "sha256": args.manifest_sha256}, 65536)
    manifest = json.loads(raw)
    if manifest["schema"] != "hybrid-complete-portable-source-v1" or not 43 <= len(manifest["files"]) <= 64:
        raise ValueError("manifest schema/roster")
    captured = {}
    total = 0
    for name, pin in manifest["files"].items():
        if Path(name).is_absolute() or ".." in Path(name).parts or str(Path(name)) != name:
            raise ValueError("relative manifest path")
        total += pin["bytes"]
        if total > 4 * 1048576:
            raise ValueError("complete source cap")
        captured[name] = helper.exact(root / name, pin)
    if captured["run_checks.py"] != helper.exact(Path(__file__).absolute(), manifest["files"]["run_checks.py"]):
        raise ValueError("check caller identity")
    prepare = types.ModuleType("hybrid_public_prepare"); prepare.__file__ = str(root / "prepare_operation.py")
    exec(compile(captured["prepare_operation.py"], prepare.__file__, "exec"), prepare.__dict__)
    tests = types.ModuleType("hybrid_public_prepare_tests"); tests.__file__ = str(root / "test_prepare.py")
    exec(compile(captured["test_prepare.py"], tests.__file__, "exec"), tests.__dict__)
    if not tests.run(prepare, root, args.manifest_sha256, whole=not args.admission_only):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
